import os
import sys
_THIS_DIR = os.path.dirname(os.path.abspath(__file__))
_PROJECT_ROOT = _THIS_DIR if os.path.exists(os.path.join(_THIS_DIR, "bridge_loader.py")) else os.path.dirname(_THIS_DIR)
for _sub in ("core", "shared", "editors", "remote", "addons_sys", "extras"):
    _p = os.path.join(_PROJECT_ROOT, _sub)
    if _p not in sys.path:
        sys.path.insert(0, _p)

import sys
import os
import importlib.util
import json
import subprocess
import hashlib
import time
import tempfile
import platform
from PyQt6.QtWidgets import QApplication, QPushButton, QMessageBox
from PyQt6.QtCore import Qt, QProcess, QCoreApplication

from style_loader import apply_global_style
from updater import UpdateWorker, get_local_version, UpdaterDialog
from lang_loader import tr
from addon_logger import log_activity_for_addon
import addon_watchdog

# Добавляем путь для импорта
current_dir = os.path.dirname(os.path.abspath(sys.argv[0]))
if current_dir not in sys.path:
    sys.path.append(current_dir)

# Флаг для subprocess.*, чтобы pip install не мигал окном терминала на Windows.
NO_WINDOW_FLAGS = subprocess.CREATE_NO_WINDOW if platform.system() == 'Windows' else 0

# Попытка импортировать модули безопасным способом
def safe_import(module_name):
    try:
        return importlib.import_module(module_name)
    except ImportError:
        print(f"Модуль {module_name} не найден, пропуск.")
        return None

# Функция для автоматической установки зависимостей
def install_requirements(addon_path):
    req_file = os.path.join(addon_path, "requirements.txt")
    if not os.path.exists(req_file):
        return

    marker_file = os.path.join(addon_path, ".requirements_installed")
    with open(req_file, 'rb') as f:
        req_hash = hashlib.sha256(f.read()).hexdigest()

    if os.path.exists(marker_file):
        try:
            with open(marker_file, 'r', encoding='utf-8') as f:
                if f.read().strip() == req_hash:
                    return  # requirements.txt не менялся - установка уже выполнена
        except Exception:
            pass

    print(f"Обнаружен requirements.txt в {addon_path}. Установка библиотек...")
    try:
        # ВАЖНО: убрали "pip install --upgrade pip" - это лишний сетевой
        # запрос на КАЖДЫЙ старт лаунчера при любой проблеме с маркером,
        # и главная причина, почему запуск мог становиться медленным.
        # Добавили timeout, чтобы не зависать намертво, если сети нет.
        subprocess.check_call(
            [sys.executable, "-m", "pip", "install", "-r", req_file,
             "--quiet", "--disable-pip-version-check"],
            creationflags=NO_WINDOW_FLAGS,
            timeout=60,
        )
        with open(marker_file, 'w', encoding='utf-8') as f:
            f.write(req_hash)
        print("Все библиотеки успешно установлены!")
        log_activity_for_addon(addon_path, "info", "Зависимости установлены")
    except subprocess.TimeoutExpired:
        print(f"Установка библиотек в {addon_path} прервана по таймауту (60 сек, похоже нет сети).")
        # Маркер пишем даже при неудаче - иначе лаунчер будет заново
        # пытаться (и снова виснуть на таймауте) на КАЖДОМ следующем
        # запуске. Чтобы попробовать ещё раз - удали .requirements_installed
        # у аддона вручную (например, после того как подключишься к сети).
        with open(marker_file, 'w', encoding='utf-8') as f:
            f.write(req_hash)
        log_activity_for_addon(addon_path, "error", "Установка зависимостей прервана по таймауту (нет сети?)")
    except Exception as e:
        print(f"Ошибка при установке библиотек в {addon_path}: {e}")
        with open(marker_file, 'w', encoding='utf-8') as f:
            f.write(req_hash)
        log_activity_for_addon(addon_path, "error", f"Ошибка установки зависимостей: {e}")

# Импортируем критический модуль лаунчера
from GorLauncher import GORLauncher

# Импортируем редакторы (опционально)
group_editor = safe_import("group_editor")
game_editor = safe_import("game_editor")
sunshine_control = safe_import("sunshine_control")
exporter_editor = safe_import("exporter_editor")
ControlCenter = safe_import("ControlCenter")

# --------------------------------------------------------------------- #
# Смена языка и перезапуск приложения
# --------------------------------------------------------------------- #
def change_language(lang_code):
    """Устанавливает новый язык и перезапускает интерфейс."""
    from lang_loader import set_language
    set_language(lang_code)
    restart_launcher(confirm=False)

# --------------------------------------------------------------------- #
# Полноценный перезапуск лаунчера через bridge_loader.
# --------------------------------------------------------------------- #
def restart_launcher(confirm=True):
    """Надежный перезапуск GorLauncher с сохранением всех аддонов, обновлений и UI."""
    if confirm:
        reply = QMessageBox.question(
            None, tr("launcher.restart_confirm_title"),
            tr("launcher.restart_confirm_text")
        )
        if reply != QMessageBox.StandardButton.Yes:
            return

    base_dir = os.path.dirname(os.path.abspath(sys.argv[0]))

    # Кандидаты для запускного файла
    bridge_exe_candidate = os.path.join(base_dir, "bridge_loader.exe")
    bridge_py_candidate = os.path.join(base_dir, "bridge_loader.py")
    gor_exe_candidate = os.path.join(base_dir, "GorLauncher.exe")
    gor_py_candidate = os.path.join(base_dir, "core", "GorLauncher.py")

    # Перезапускаем через bridge_loader
    if os.path.isfile(bridge_exe_candidate):
        cmd = [bridge_exe_candidate]
    elif os.path.isfile(bridge_py_candidate):
        cmd = [sys.executable, bridge_py_candidate]
    elif os.path.isfile(gor_exe_candidate):
        cmd = [gor_exe_candidate]
    elif os.path.isfile(gor_py_candidate):
        cmd = [sys.executable, gor_py_candidate]
    else:
        cmd = [sys.executable] + sys.argv

    try:
        creationflags = 0
        if platform.system() == "Windows":
            creationflags = subprocess.DETACHED_PROCESS | subprocess.CREATE_NEW_PROCESS_GROUP
            if hasattr(subprocess, "CREATE_BREAKAWAY_FROM_JOB"):
                creationflags |= subprocess.CREATE_BREAKAWAY_FROM_JOB

        subprocess.Popen(
            cmd,
            cwd=base_dir,
            creationflags=creationflags,
            close_fds=True
        )
    except Exception as e:
        QMessageBox.critical(
            None, tr("launcher.restart_error_title"),
            tr("launcher.restart_error_text", error=e)
        )
        return

    QApplication.closeAllWindows()
    sys.exit(0)


def run_control_center():
    base_path = os.path.dirname(os.path.abspath(sys.argv[0]))
    script_path = os.path.join(base_path, "addons_sys", "ControlCenter.py")
    
    if os.path.exists(script_path):
        subprocess.Popen([sys.executable, script_path])

def _read_stored_addons_list(base_dir):
    """Читает поле 'addons_list' напрямую из games_data.json на диске.

    ВАЖНО: читаем именно с диска, а не launcher.games_info, потому что
    к моменту вызова load_addons() файл на диске - единственный источник
    правды о том, что пользователь включил/выключил в Control Center
    (Control Center - отдельный процесс и пишет прямо в файл).

    Возвращает:
      - None, если ключа "addons_list" в файле никогда не было
        (совсем свежая установка) - в этом случае считаем, что включены
        ВСЕ найденные аддоны, чтобы не ломать поведение "положил папку -
        она заработала" для тех, кто ещё не открывал Control Center.
      - list[str], если ключ есть - это явный список ВКЛЮЧЁННЫХ аддонов
        (по имени папки, как их пишет ControlCenter._save_active_addons).
    """
    data_path = os.path.join(base_dir, "games_data.json")
    if not os.path.exists(data_path):
        return None
    try:
        with open(data_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        if "addons_list" not in data:
            return None
        return data.get("addons_list") or []
    except Exception:
        return None


def load_addons(launcher):
    base_dir = os.path.dirname(os.path.abspath(sys.argv[0]))
    addons_dir = os.path.join(base_dir, "addons")
    if not os.path.exists(addons_dir): return

    # Включаем автоматическое наблюдение за аддонами ДО того, как загрузим
    # хоть один из них - перехват файлов/процессов/сети/UI-вызовов работает
    # независимо от того, что по этому поводу думает автор аддона
    # (см. addon_watchdog.py).
    addon_watchdog.install(addons_dir)

    stored_list = _read_stored_addons_list(base_dir)
    has_explicit_list = stored_list is not None

    control_center_found = False
    active_addons = []  # аддоны, реально загруженные в этот раз (по имени папки)

    for folder in sorted(os.listdir(addons_dir)):
        addon_path = os.path.join(addons_dir, folder)
        config_path = os.path.join(addon_path, "config.json")
        core_dir = os.path.join(addon_path, "core")
        web_dir = os.path.join(addon_path, "web")

        if not (os.path.exists(config_path) and os.path.exists(core_dir) and os.path.exists(web_dir)):
            continue

        control_center_found = True

        try:
            with open(config_path, 'r', encoding='utf-8') as f:
                config = json.load(f)
        except Exception as e:
            print(f"Ошибка чтения config.json в {folder}: {e}")
            continue

        addon_name = config.get("name", folder)

        # Проверяем и по имени папки, и по отображаемому имени - так же,
        # как это делает ControlCenter.scan_addons() при определении enabled.
        is_enabled = True
        if has_explicit_list:
            is_enabled = folder in stored_list or addon_name in stored_list

        if not is_enabled:
            print(f"[bridge_loader] Аддон '{addon_name}' отключён в Control Center - пропуск загрузки.")
            continue

        active_addons.append(folder)

        # Эти записи пишет САМ bridge_loader, а не аддон - они появятся в
        # логе Control Center для ЛЮБОГО аддона автоматически, даже если
        # его код вообще ничего не сообщает о себе сам.
        log_activity_for_addon(addon_path, "info", f"Аддон обнаружен, версия {config.get('version', '—')}")

        try:
            start_filename = config.get("start_file")
            if not start_filename:
                log_activity_for_addon(addon_path, "error", "В config.json не указан start_file")
                continue

            install_requirements(addon_path)

            core_script = os.path.join(core_dir, start_filename)

            if os.path.exists(core_script):
                log_activity_for_addon(addon_path, "info", f"Загрузка модуля: {start_filename}")
                # Уникальное имя модуля на каждый аддон (folder), а не одно
                # общее "addon_module" на всех - иначе при нескольких
                # аддонах возможны коллизии имён модулей.
                spec = importlib.util.spec_from_file_location(f"addon_module_{folder}", core_script)
                module = importlib.util.module_from_spec(spec)
                spec.loader.exec_module(module)
                if hasattr(module, "init_addon"):
                    module.init_addon(launcher)
                log_activity_for_addon(addon_path, "info", "Аддон успешно запущен")
            else:
                log_activity_for_addon(addon_path, "error", f"Файл {start_filename} не найден в core/")
        except Exception as e:
            print(f"Ошибка в {folder}: {e}")
            log_activity_for_addon(addon_path, "error", f"Ошибка запуска: {e}")

    # Перезаписываем addons_list только тем, что реально включено и
    # загружено сейчас - так отключённые в Control Center аддоны остаются
    # отключёнными и на следующий запуск, а не "воскресают" сами собой.
    launcher.games_info["addons_list"] = active_addons
    launcher.save_data()

    if control_center_found:
        btn = QPushButton(tr("launcher.addon_manager_btn"))
        btn.setCursor(Qt.CursorShape.PointingHandCursor)
        btn.clicked.connect(run_control_center)
        header_lay = launcher.main_lay.itemAt(0).layout()
        
        # Размещаем кнопку возле кнопки перезапуска и бургер-меню справа
        restart_btn = launcher.findChild(QPushButton, "RestartBtn")
        if restart_btn and header_lay.indexOf(restart_btn) != -1:
            header_lay.insertWidget(header_lay.indexOf(restart_btn), btn)
        elif hasattr(launcher, 'burger_btn') and header_lay.indexOf(launcher.burger_btn) != -1:
            header_lay.insertWidget(header_lay.indexOf(launcher.burger_btn), btn)
        else:
            header_lay.addWidget(btn)


def add_restart_button(launcher):
    """Добавляет кнопку перезапуска."""
    btn = QPushButton("🔄")
    btn.setObjectName("RestartBtn")
    btn.setToolTip(tr("launcher.restart_tooltip"))
    btn.setCursor(Qt.CursorShape.PointingHandCursor)
    btn.setFixedSize(38, 38)
    btn.clicked.connect(lambda: restart_launcher(confirm=True))
    
    header_lay = launcher.main_lay.itemAt(0).layout()
    burger_idx = header_lay.indexOf(launcher.burger_btn)
    if burger_idx != -1:
        header_lay.insertWidget(burger_idx, btn)
    else:
        header_lay.addWidget(btn)


def update_widget_style_property(widget, prop_name, prop_value):
    """Вспомогательная функция для обновления динамических свойств QSS."""
    widget.setProperty(prop_name, prop_value)
    widget.style().unpolish(widget)
    widget.style().polish(widget)


# --------------------------------------------------------------------- #
# Фоновая проверка обновлений при каждом запуске лаунчера.
# --------------------------------------------------------------------- #
def check_updates_in_background(launcher):
    current_version = get_local_version()

    checker = UpdateWorker(UpdateWorker.MODE_CHECK, current_version)
    launcher._update_checker = checker

    def on_check_result(info):
        remote_version = info.get("version")
        if remote_version and remote_version != current_version:
            show_update_available_button(launcher, remote_version)

    def on_finished(success, message):
        if not success:
            print(f"[updater] Фоновая проверка обновлений: {message}")

    checker.check_result_signal.connect(on_check_result)
    checker.finished_signal.connect(on_finished)
    checker.start()


def show_update_available_button(launcher, remote_version):
    if getattr(launcher, "_update_btn_added", False):
        return
    launcher._update_btn_added = True

    def open_updater():
        dialog = UpdaterDialog(launcher)
        dialog.exec()

    btn = QPushButton(tr("launcher.update_available_btn", version=remote_version))
    btn.setCursor(Qt.CursorShape.PointingHandCursor)
    btn.clicked.connect(open_updater)
    header_lay = launcher.main_lay.itemAt(0).layout()
    
    # Размещаем кнопку обновления левее кнопки ADDON MANAGER или перезапуска
    restart_btn = launcher.findChild(QPushButton, "RestartBtn")
    if restart_btn and header_lay.indexOf(restart_btn) != -1:
        header_lay.insertWidget(header_lay.indexOf(restart_btn), btn)
    elif hasattr(launcher, 'burger_btn') and header_lay.indexOf(launcher.burger_btn) != -1:
        header_lay.insertWidget(header_lay.indexOf(launcher.burger_btn), btn)
    else:
        header_lay.addWidget(btn)


if __name__ == "__main__":
    app = QApplication(sys.argv)
    apply_global_style(app)
    launcher = GORLauncher()
    load_addons(launcher)
    add_restart_button(launcher)
    launcher.show()
    check_updates_in_background(launcher)
    sys.exit(app.exec())