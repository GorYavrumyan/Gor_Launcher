"""
moonlight_stream.py
====================
Модуль интеграции клиента Moonlight (moonlight-qt) в GOR Launcher.

Позволяет стримить игры/рабочий стол с удалённого ПК (на котором запущен
Sunshine-хост) на текущий компьютер по протоколу NVIDIA GameStream/Sunshine.

Состоит из двух частей:
  - PCStreamManager  - "движок" без GUI: поиск moonlight-qt, сопряжение,
                        запуск потока, хранение списка хостов в JSON.
  - StreamModuleUI   - виджет PyQt6, который можно встроить в лаунчер
                        (как отдельную вкладку) или запустить отдельно.

Оформление берётся из общего style.qss через style_loader.py, как и в
остальных модулях проекта (GorLauncher, sunshine_control, ControlCenter и т.д.).
"""

import sys
import os
import json
import shutil
import platform
import subprocess
import random

from PyQt6.QtWidgets import (QApplication, QWidget, QDialog, QVBoxLayout, QHBoxLayout,
                             QLabel, QLineEdit, QPushButton, QComboBox, QMessageBox,
                             QGroupBox, QCheckBox, QSpinBox, QFileDialog)
from PyQt6.QtGui import QIntValidator
from PyQt6.QtCore import Qt, QThread, pyqtSignal

from style_loader import apply_global_style

# Флаг, скрывающий консольное окно при запуске сторонних процессов на Windows
CREATE_NO_WINDOW = 0x08000000 if platform.system() == "Windows" else 0


# =====================================================================
#  PCStreamManager - управление процессами Moonlight без привязки к GUI
# =====================================================================
class PCStreamManager:
    """
    Отвечает за:
      - автоматический поиск исполняемого файла Moonlight в системе;
      - сопряжение (pairing) с удалённым ПК по IP и PIN-коду;
      - запуск стрима (игра/рабочий стол) с нужными параметрами;
      - хранение списка добавленных хостов в JSON-файле.
    """

    CONFIG_FILE = "moonlight_hosts.json"

    # Стандартные разрешения, которые понимает CLI moonlight-qt через флаги
    RESOLUTION_FLAGS = {
        (1280, 720): "--720",
        (1920, 1080): "--1080",
        (2560, 1440): "--1440",
        (3840, 2160): "--4K",
    }

    def __init__(self):
        self.hosts = self.load_hosts()
        # Путь, который пользователь один раз указал вручную (если автопоиск
        # не сработал) - хранится в том же JSON-файле конфигурации и имеет
        # приоритет над автоматическим поиском
        self.manual_path = self.load_manual_path()
        self.executable_path = self.manual_path or self.find_moonlight_executable()

    # -----------------------------------------------------------------
    # Поиск исполняемого файла Moonlight
    # -----------------------------------------------------------------
    def find_moonlight_executable(self):
        """
        Ищет moonlight-qt в системе:
          0) в папке "Moonlight", лежащей РЯДОМ с этим модулем (например,
             портативная версия Moonlight, распакованная прямо рядом с
             .py/.exe файлом лаунчера) - самый частый случай для
             портативных сборок, поэтому проверяется в первую очередь;
          1) через PATH (shutil.which) - подходит, если Moonlight
             установлен "как положено" и доступен из терминала;
          2) в типичных папках установки Windows/Linux, на случай если
             пользователь не добавил программу в PATH.

        Возвращает полный путь к исполняемому файлу или None, если
        Moonlight не найден нигде.
        """
        system = platform.system()

        # 0) Портативная папка "Moonlight" рядом с самим модулем.
        # Используем os.path.dirname(os.path.abspath(sys.argv[0])), чтобы
        # это работало и при запуске из .py, и из собранного .exe (PyInstaller) -
        # так же, как style_loader.py ищет style.qss рядом с собой.
        local_base_dir = os.path.dirname(os.path.abspath(sys.argv[0]))
        local_exe_names = ["Moonlight.exe", "moonlight.exe"] if system == "Windows" else ["moonlight-qt", "moonlight"]
        local_candidate_dirs = [
            os.path.join(local_base_dir, "Moonlight"),          # ./Moonlight/Moonlight.exe
            os.path.join(local_base_dir, "Moonlight", "Moonlight"),  # на случай вложенной папки
            local_base_dir,                                      # сам модуль лежит прямо рядом с exe
        ]
        for directory in local_candidate_dirs:
            for exe_name in local_exe_names:
                full_path = os.path.join(directory, exe_name)
                if os.path.isfile(full_path):
                    return full_path

        # 1) Поиск через PATH - разные возможные имена бинарника
        candidates_in_path = ["moonlight-qt", "moonlight", "Moonlight"]
        if system == "Windows":
            candidates_in_path = ["moonlight.exe", "Moonlight.exe", "moonlight-qt.exe"] + candidates_in_path

        for name in candidates_in_path:
            found = shutil.which(name)
            if found:
                return found

        # 2) Поиск в типичных папках установки
        possible_dirs = []
        if system == "Windows":
            program_files = os.environ.get("ProgramFiles", "C:/Program Files")
            program_files_x86 = os.environ.get("ProgramFiles(x86)", "C:/Program Files (x86)")
            local_app_data = os.environ.get("LOCALAPPDATA", "")
            possible_dirs = [
                os.path.join(program_files, "Moonlight Game Streaming"),
                os.path.join(program_files_x86, "Moonlight Game Streaming"),
                os.path.join(local_app_data, "Programs", "Moonlight Game Streaming"),
            ]
            exe_names = ["Moonlight.exe", "moonlight.exe"]
        else:
            # Linux: типичные места установки .deb/.rpm/AppImage/flatpak
            possible_dirs = [
                "/usr/bin",
                "/usr/local/bin",
                "/opt/moonlight-qt",
                os.path.expanduser("~/.local/bin"),
                "/var/lib/flatpak/exports/bin",
                os.path.expanduser("~/.local/share/flatpak/exports/bin"),
            ]
            exe_names = ["moonlight-qt", "moonlight", "com.moonlight_stream.Moonlight"]

        for directory in possible_dirs:
            if not directory or not os.path.isdir(directory):
                continue
            for exe_name in exe_names:
                full_path = os.path.join(directory, exe_name)
                if os.path.isfile(full_path):
                    return full_path

        # Не нашли нигде
        return None

    def is_available(self):
        """Проверка, найден ли исполняемый файл Moonlight."""
        return self.executable_path is not None and os.path.isfile(self.executable_path)

    # -----------------------------------------------------------------
    # Ручное указание пути к moonlight.exe (если автопоиск не справился,
    # например программа установлена в нестандартную папку)
    # -----------------------------------------------------------------
    def load_manual_path(self):
        """Загружает вручную указанный путь к Moonlight из конфига, если он там есть."""
        if not os.path.exists(self.CONFIG_FILE):
            return None
        try:
            with open(self.CONFIG_FILE, 'r', encoding='utf-8') as f:
                data = json.load(f)
                path = data.get("manual_moonlight_path")
                if path and os.path.isfile(path):
                    return path
        except Exception:
            pass
        return None

    def set_manual_path(self, path):
        """
        Сохраняет путь к moonlight.exe, указанный пользователем вручную
        (например, через диалог выбора файла в интерфейсе), и делает его
        активным исполняемым файлом для всех последующих операций.
        """
        path = path.strip()
        if not path or not os.path.isfile(path):
            return False

        self.manual_path = path
        self.executable_path = path

        # Сохраняем в тот же JSON, что и список хостов, чтобы не плодить файлы
        data = {"hosts": self.hosts, "manual_moonlight_path": path}
        try:
            with open(self.CONFIG_FILE, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=4, ensure_ascii=False)
        except Exception as e:
            print(f"[PCStreamManager] Не удалось сохранить путь к Moonlight: {e}")
        return True

    # -----------------------------------------------------------------
    # Хранение списка хостов (IP-адресов) в JSON
    # -----------------------------------------------------------------
    def load_hosts(self):
        """Загружает список сохранённых хостов из JSON-файла конфигурации."""
        if not os.path.exists(self.CONFIG_FILE):
            return []
        try:
            with open(self.CONFIG_FILE, 'r', encoding='utf-8') as f:
                data = json.load(f)
                return data.get("hosts", [])
        except Exception:
            return []

    def save_hosts(self):
        """Сохраняет текущий список хостов в JSON-файл конфигурации.

        Ручной путь к Moonlight (manual_moonlight_path) хранится в том же
        файле, поэтому при сохранении списка хостов он бережно сохраняется,
        а не затирается.
        """
        try:
            data = {"hosts": self.hosts}
            if self.manual_path:
                data["manual_moonlight_path"] = self.manual_path
            with open(self.CONFIG_FILE, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=4, ensure_ascii=False)
        except Exception as e:
            print(f"[PCStreamManager] Не удалось сохранить {self.CONFIG_FILE}: {e}")

    def add_host(self, ip):
        """Добавляет IP-адрес в список сохранённых хостов (без дублей)."""
        ip = ip.strip()
        if ip and ip not in self.hosts:
            self.hosts.append(ip)
            self.save_hosts()

    def remove_host(self, ip):
        """Удаляет IP-адрес из списка сохранённых хостов."""
        if ip in self.hosts:
            self.hosts.remove(ip)
            self.save_hosts()

    # -----------------------------------------------------------------
    # Сопряжение с хостом
    # -----------------------------------------------------------------
    def pair_with_host(self, ip, pin, timeout=45):
        """
        Выполняет сопряжение с удалённым ПК по IP-адресу и PIN-коду.

        Реальный CLI moonlight-qt поддерживает действие "pair" с флагом
        "--pin <4 цифры>" (см. официальный исходный код commandlineparser.cpp
        проекта moonlight-stream/moonlight-qt). PIN-код в этой схеме не
        приходит откуда-то с хоста - его нужно один раз придумать/сгенерировать
        на стороне клиента и ввести ОДИН И ТОТ ЖЕ код сразу в двух местах:
        здесь (передаётся Moonlight через "--pin") и в веб-панели Sunshine
        на хосте (https://<ip>:47990 -> раздел PIN), где пользователь должен
        успеть вручную подтвердить тот же код в течение таймаута.

        Возвращает кортеж (success: bool, message: str).
        """
        if not self.is_available():
            return False, ("Moonlight не найден в системе. Установите moonlight-qt "
                           "и убедитесь, что он доступен в PATH.")

        if not ip.strip():
            return False, "Не указан IP-адрес хоста."

        if not (pin.isdigit() and len(pin) == 4):
            return False, "PIN-код должен состоять ровно из 4 цифр."

        command = [self.executable_path, "pair", ip.strip(), "--pin", pin]

        try:
            result = subprocess.run(
                command,
                capture_output=True,
                text=True,
                timeout=timeout,
                creationflags=CREATE_NO_WINDOW
            )
        except FileNotFoundError:
            return False, "Не удалось запустить Moonlight: исполняемый файл не найден."
        except subprocess.TimeoutExpired:
            return False, ("Хост не ответил за отведённое время. Проверьте, что вы "
                           "успели ввести этот же PIN в панели Sunshine, что ПК "
                           "включён, Sunshine запущен и IP-адрес указан верно.")
        except Exception as e:
            return False, f"Ошибка во время сопряжения: {e}"

        output = ((result.stdout or "") + (result.stderr or "")).strip()

        if result.returncode == 0:
            self.add_host(ip.strip())
            return True, "Сопряжение прошло успешно! Хост добавлен в список."
        else:
            return False, f"Не удалось выполнить сопряжение (код {result.returncode}).\n{output}"

    # -----------------------------------------------------------------
    # Запуск стрима
    # -----------------------------------------------------------------
    def start_stream(self, ip, app_name, width=1920, height=1080, fps=60,
                      bitrate=20000, windowed=False):
        """
        Запускает стрим с удалённого ПК в фоновом режиме (не блокируя интерфейс).

        Параметры:
          ip       - IP-адрес хоста (ПК с Sunshine);
          app_name - название приложения на хосте, например "Portal",
                     "Half-Life 2" или "Desktop" (рабочий стол);
          width/height - желаемое разрешение потока;
          fps      - частота кадров;
          bitrate  - битрейт видео в кбит/с;
          windowed - запускать в оконном режиме вместо полноэкранного.

        Возвращает кортеж (success: bool, message: str).
        """
        if not self.is_available():
            return False, ("Moonlight не найден в системе. Установите moonlight-qt "
                           "и убедитесь, что он доступен в PATH.")

        if not ip.strip():
            return False, "Не указан IP-адрес хоста."

        if not app_name.strip():
            return False, "Не указано название приложения для запуска."

        command = [self.executable_path, "stream", ip.strip(), app_name.strip()]

        # Разрешение: используем короткий флаг для стандартных резолюций
        # (--720/--1080/--1440/--4K), для нестандартных - универсальный
        # флаг --resolution <width>x<height> (оба варианта подтверждены
        # официальной справкой "moonlight stream --help").
        resolution_flag = self.RESOLUTION_FLAGS.get((width, height))
        if resolution_flag:
            command.append(resolution_flag)
        else:
            command += ["--resolution", f"{width}x{height}"]

        command += ["--fps", str(fps), "--bitrate", str(bitrate)]
        command += ["--display-mode", "windowed" if windowed else "fullscreen"]

        try:
            # Popen без ожидания результата - стрим открывается в отдельном
            # окне/процессе, лаунчер не должен зависать на время игровой сессии.
            subprocess.Popen(
                command,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                creationflags=CREATE_NO_WINDOW
            )
        except FileNotFoundError:
            return False, "Не удалось запустить Moonlight: исполняемый файл не найден."
        except PermissionError:
            return False, "Недостаточно прав для запуска Moonlight."
        except Exception as e:
            return False, f"Не удалось запустить стрим: {e}"

        self.add_host(ip.strip())
        return True, f"Стрим '{app_name}' с хоста {ip} запускается..."


# =====================================================================
#  Фоновые потоки, чтобы сетевые операции не блокировали интерфейс
# =====================================================================
class PairWorker(QThread):
    """Выполняет сопряжение с хостом в отдельном потоке."""
    finished_signal = pyqtSignal(bool, str)

    def __init__(self, manager, ip, pin):
        super().__init__()
        self.manager = manager
        self.ip = ip
        self.pin = pin

    def run(self):
        success, message = self.manager.pair_with_host(self.ip, self.pin)
        self.finished_signal.emit(success, message)


# =====================================================================
#  Диалог ввода PIN-кода для сопряжения
# =====================================================================
class PinDialog(QDialog):
    """
    Диалог сопряжения. Важно понимать реальный механизм пары Moonlight/Sunshine:
    PIN-код для сопряжения НЕ приходит откуда-то с хоста - его нужно один
    раз придумать (или сгенерировать) на стороне клиента и ввести ОДИН
    И ТОТ ЖЕ код сразу в двух местах:
      1) в этом диалоге (передаётся в Moonlight через флаг "--pin");
      2) в веб-панели Sunshine на хосте (https://<ip>:47990 -> раздел PIN).

    Поэтому диалог сам генерирует случайный 4-значный код и показывает
    его крупно, а пользователю остаётся только скопировать его в Sunshine.
    """

    def __init__(self, parent=None, ip=""):
        super().__init__(parent)
        self.setWindowTitle("Сопряжение с хостом")
        self.setObjectName("EditorDialog")
        self.setFixedWidth(400)

        # Генерируем случайный 4-значный PIN сразу при открытии диалога
        self.generated_pin = f"{random.randint(0, 9999):04d}"

        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(12)

        info = QLabel(
            f"1. Откройте на хосте {ip} веб-панель Sunshine:\n"
            f"   https://{ip}:47990 -> раздел «PIN»\n\n"
            f"2. Введите там код, показанный ниже, и нажмите Send.\n\n"
            f"3. Затем нажмите «ПОДТВЕРДИТЬ» здесь."
        )
        info.setWordWrap(True)
        layout.addWidget(info)

        # Крупное поле с самим PIN-кодом - его нужно скопировать в Sunshine.
        # Оставляем редактируемым на случай, если пользователь хочет
        # придумать свой код вместо сгенерированного.
        self.pin_edit = QLineEdit(self.generated_pin)
        self.pin_edit.setObjectName("ArgsInput")
        self.pin_edit.setMaxLength(4)
        self.pin_edit.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.pin_edit.setValidator(QIntValidator(0, 9999, self))
        self.pin_edit.setStyleSheet("font-size: 28px; font-weight: bold; letter-spacing: 6px;")
        layout.addWidget(self.pin_edit)

        regenerate_btn = QPushButton("🔄 Сгенерировать другой PIN")
        regenerate_btn.clicked.connect(self.regenerate_pin)
        layout.addWidget(regenerate_btn)

        btn_layout = QHBoxLayout()
        self.ok_btn = QPushButton("ПОДТВЕРДИТЬ")
        self.ok_btn.clicked.connect(self.try_accept)
        cancel_btn = QPushButton("ОТМЕНА")
        cancel_btn.setObjectName("CancelBtn")
        cancel_btn.clicked.connect(self.reject)
        btn_layout.addWidget(self.ok_btn)
        btn_layout.addWidget(cancel_btn)
        layout.addLayout(btn_layout)

    def regenerate_pin(self):
        """Генерирует новый случайный PIN, если пользователь хочет его сменить."""
        self.pin_edit.setText(f"{random.randint(0, 9999):04d}")

    def try_accept(self):
        pin = self.pin_edit.text().strip().zfill(4)
        if len(pin) != 4 or not pin.isdigit():
            QMessageBox.warning(self, "Ошибка", "PIN-код должен состоять ровно из 4 цифр!")
            return
        self.pin_edit.setText(pin)
        self.accept()

    def get_pin(self):
        return self.pin_edit.text().strip().zfill(4)


# =====================================================================
#  StreamModuleUI - виджет со всем интерфейсом стриминга
# =====================================================================
class StreamModuleUI(QWidget):
    """
    Виджет для встраивания в GOR Launcher (например, отдельной вкладкой)
    либо для самостоятельного запуска. Позволяет пользователю указать
    IP хоста, выбрать приложение/рабочий стол, выполнить сопряжение
    и запустить поток через Moonlight.
    """

    # Стандартный набор приложений - "Рабочий стол" почти всегда
    # доступен в Sunshine "из коробки", остальное - примеры популярных игр
    DEFAULT_APPS = ["Desktop", "Portal", "Half-Life 2", "Steam Big Picture"]

    RESOLUTIONS = {
        "1280x720 (HD)": (1280, 720),
        "1920x1080 (Full HD)": (1920, 1080),
        "2560x1440 (QHD)": (2560, 1440),
        "3840x2160 (4K)": (3840, 2160),
    }

    def __init__(self, parent=None):
        super().__init__(parent)
        self.manager = PCStreamManager()
        self.pair_worker = None
        self.init_ui()

        self.refresh_availability_status()

    def refresh_availability_status(self):
        """Обновляет строку статуса и видимость кнопки ручного выбора Moonlight."""
        if self.manager.is_available():
            self.locate_btn.setVisible(False)
            self.status_label.setText(f"✅ Moonlight найден: {self.manager.executable_path}")
        else:
            self.locate_btn.setVisible(True)
            self.status_label.setText(
                "⚠ Moonlight не найден автоматически. Установите moonlight-qt "
                "либо укажите путь к Moonlight.exe вручную кнопкой ниже."
            )

    def locate_moonlight_manually(self):
        """
        Открывает диалог выбора файла, чтобы пользователь указал путь
        к Moonlight.exe вручную - полезно, если программа установлена
        в нестандартную папку и автопоиск её не нашёл.
        """
        if platform.system() == "Windows":
            file_filter = "Moonlight (Moonlight.exe moonlight.exe);;Все файлы (*.*)"
        else:
            file_filter = "Все файлы (*)"

        path, _ = QFileDialog.getOpenFileName(
            self, "Укажите путь к Moonlight.exe", "", file_filter
        )
        if not path:
            return

        if self.manager.set_manual_path(path):
            QMessageBox.information(self, "Готово", f"Moonlight найден:\n{path}")
        else:
            QMessageBox.warning(self, "Ошибка", "Выбранный файл не существует или недоступен.")

        self.refresh_availability_status()

    def init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(15)

        title = QLabel("🖥️ PC-to-PC стриминг (Moonlight)")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        title.setStyleSheet("font-size: 18px; font-weight: bold;")
        layout.addWidget(title)

        # --- Блок хоста ---
        host_box = QGroupBox("Удалённый ПК (хост Sunshine)")
        host_lay = QVBoxLayout(host_box)

        self.saved_hosts_combo = QComboBox()
        self.saved_hosts_combo.addItem("— выбрать сохранённый хост —")
        self.saved_hosts_combo.addItems(self.manager.hosts)
        self.saved_hosts_combo.currentTextChanged.connect(self.on_saved_host_selected)
        host_lay.addWidget(self.saved_hosts_combo)

        ip_layout = QHBoxLayout()
        self.ip_edit = QLineEdit()
        self.ip_edit.setPlaceholderText("IP-адрес хоста, например 192.168.1.10")
        ip_layout.addWidget(self.ip_edit)
        self.pair_btn = QPushButton("🔗 Сопряжение (Pair)")
        self.pair_btn.clicked.connect(self.open_pair_dialog)
        ip_layout.addWidget(self.pair_btn)
        host_lay.addLayout(ip_layout)

        layout.addWidget(host_box)

        # --- Блок параметров стрима ---
        stream_box = QGroupBox("Параметры стрима")
        stream_lay = QVBoxLayout(stream_box)

        stream_lay.addWidget(QLabel("Приложение / рабочий стол:"))
        self.app_combo = QComboBox()
        self.app_combo.setEditable(True)
        self.app_combo.addItems(self.DEFAULT_APPS)
        stream_lay.addWidget(self.app_combo)

        res_fps_layout = QHBoxLayout()
        res_col = QVBoxLayout()
        res_col.addWidget(QLabel("Разрешение:"))
        self.resolution_combo = QComboBox()
        self.resolution_combo.addItems(self.RESOLUTIONS.keys())
        self.resolution_combo.setCurrentText("1920x1080 (Full HD)")
        res_col.addWidget(self.resolution_combo)
        res_fps_layout.addLayout(res_col)

        fps_col = QVBoxLayout()
        fps_col.addWidget(QLabel("FPS:"))
        self.fps_combo = QComboBox()
        self.fps_combo.addItems(["30", "60", "90", "120"])
        self.fps_combo.setCurrentText("60")
        fps_col.addWidget(self.fps_combo)
        res_fps_layout.addLayout(fps_col)
        stream_lay.addLayout(res_fps_layout)

        stream_lay.addWidget(QLabel("Битрейт (кбит/с):"))
        self.bitrate_spin = QSpinBox()
        self.bitrate_spin.setRange(500, 150000)
        self.bitrate_spin.setSingleStep(1000)
        self.bitrate_spin.setValue(20000)
        stream_lay.addWidget(self.bitrate_spin)

        self.windowed_check = QCheckBox("Запускать в оконном режиме")
        stream_lay.addWidget(self.windowed_check)

        layout.addWidget(stream_box)

        # --- Статус и кнопка запуска ---
        self.status_label = QLabel("")
        self.status_label.setWordWrap(True)
        self.status_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self.status_label)

        # Кнопка на случай, если автопоиск не нашёл Moonlight -
        # позволяет один раз указать путь к .exe вручную (см. refresh_availability_status)
        self.locate_btn = QPushButton("📁 Указать путь к Moonlight.exe вручную")
        self.locate_btn.setObjectName("CancelBtn")
        self.locate_btn.clicked.connect(self.locate_moonlight_manually)
        self.locate_btn.setVisible(False)
        layout.addWidget(self.locate_btn)

        self.stream_btn = QPushButton("🚀 Запустить стрим")
        self.stream_btn.setObjectName("ExportBtn")
        self.stream_btn.clicked.connect(self.launch_stream)
        layout.addWidget(self.stream_btn)

    # -------------------------------------------------------------
    # Обработчики UI
    # -------------------------------------------------------------
    def on_saved_host_selected(self, text):
        """Подставляет IP из списка сохранённых хостов в поле ввода."""
        if text and not text.startswith("—"):
            self.ip_edit.setText(text)

    def open_pair_dialog(self):
        """Открывает диалог сопряжения и, при подтверждении, запускает pairing."""
        if not self.manager.is_available():
            QMessageBox.critical(
                self, "Moonlight не найден",
                "Не удалось найти moonlight-qt в системе.\n"
                "Установите Moonlight, либо укажите путь к Moonlight.exe "
                "вручную кнопкой \"📁 Указать путь к Moonlight.exe вручную\" ниже."
            )
            return

        ip = self.ip_edit.text().strip()
        if not ip:
            QMessageBox.warning(self, "Ошибка", "Сначала укажите IP-адрес хоста!")
            return

        dialog = PinDialog(self, ip)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            pin = dialog.get_pin()
            self.pair_btn.setEnabled(False)
            self.status_label.setText("Выполняется сопряжение, подождите...")

            # Сопряжение может занять время (ожидание ответа хоста),
            # поэтому выполняем его в фоновом потоке
            self.pair_worker = PairWorker(self.manager, ip, pin)
            self.pair_worker.finished_signal.connect(self.on_pair_finished)
            self.pair_worker.start()

    def on_pair_finished(self, success, message):
        self.pair_btn.setEnabled(True)
        self.status_label.setText(message)

        if success:
            QMessageBox.information(self, "Готово", message)
            # Обновляем список сохранённых хостов в комбобоксе
            self.saved_hosts_combo.blockSignals(True)
            self.saved_hosts_combo.clear()
            self.saved_hosts_combo.addItem("— выбрать сохранённый хост —")
            self.saved_hosts_combo.addItems(self.manager.hosts)
            self.saved_hosts_combo.blockSignals(False)
        else:
            QMessageBox.warning(self, "Ошибка сопряжения", message)

    def launch_stream(self):
        """Запускает стрим с текущими параметрами интерфейса."""
        if not self.manager.is_available():
            QMessageBox.critical(
                self, "Moonlight не найден",
                "Не удалось найти moonlight-qt в системе.\n"
                "Установите Moonlight, либо укажите путь к Moonlight.exe "
                "вручную кнопкой \"📁 Указать путь к Moonlight.exe вручную\" ниже."
            )
            return

        ip = self.ip_edit.text().strip()
        if not ip:
            QMessageBox.warning(self, "Ошибка", "Укажите IP-адрес хоста!")
            return

        app_name = self.app_combo.currentText().strip()
        if not app_name:
            QMessageBox.warning(self, "Ошибка", "Выберите приложение или рабочий стол!")
            return

        width, height = self.RESOLUTIONS[self.resolution_combo.currentText()]
        fps = int(self.fps_combo.currentText())
        bitrate = self.bitrate_spin.value()
        windowed = self.windowed_check.isChecked()

        success, message = self.manager.start_stream(
            ip=ip, app_name=app_name, width=width, height=height,
            fps=fps, bitrate=bitrate, windowed=windowed
        )

        self.status_label.setText(message)
        if not success:
            QMessageBox.warning(self, "Не удалось запустить стрим", message)


# =====================================================================
#  Точка входа для самостоятельного запуска модуля
# =====================================================================
if __name__ == "__main__":
    app = QApplication(sys.argv)
    apply_global_style(app)

    widget = StreamModuleUI()
    widget.setWindowTitle("GOR Launcher - PC Stream (Moonlight)")
    widget.resize(480, 640)
    widget.show()

    sys.exit(app.exec())