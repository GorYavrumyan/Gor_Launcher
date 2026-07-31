import sys
import json
import os
import subprocess
import time
import shutil
import platform
import webbrowser
from datetime import datetime

from PyQt6.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout,
                             QPushButton, QLineEdit, QLabel, QMessageBox, QHBoxLayout,
                             QGroupBox, QPlainTextEdit, QFrame, QTabWidget)
from PyQt6.QtGui import QColor
from PyQt6.QtCore import Qt, QTimer, QThread, pyqtSignal

from style_loader import apply_global_style

try:
    from PIL import Image
    PIL_AVAILABLE = True
except ImportError:
    PIL_AVAILABLE = False

SUNSHINE_WEB_URL = "https://localhost:47990"


def kill_sunshine():
    """Кроссплатформенное завершение процесса Sunshine."""
    if platform.system() == 'Windows':
        subprocess.run(["taskkill", "/f", "/im", "sunshine.exe"],
                        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    else:
        subprocess.run(["pkill", "-f", "sunshine"],
                        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)


def is_sunshine_running():
    """Проверяет, запущен ли процесс sunshine.exe / sunshine в системе."""
    try:
        if platform.system() == 'Windows':
            result = subprocess.run(
                ["tasklist", "/FI", "IMAGENAME eq sunshine.exe"],
                capture_output=True, text=True, timeout=3
            )
            return "sunshine.exe" in result.stdout.lower()
        else:
            result = subprocess.run(
                ["pgrep", "-f", "sunshine"],
                capture_output=True, text=True, timeout=3
            )
            return result.returncode == 0
    except Exception:
        return False


# ------------------------------------------------------------------
# Фоновые потоки, чтобы длительные операции не блокировали интерфейс
# ------------------------------------------------------------------

class SyncWorker(QThread):
    log_signal = pyqtSignal(str)
    finished_signal = pyqtSignal(bool, str)

    def __init__(self, sunshine_dir, assets_dir, apps_json_path, games_data_path):
        super().__init__()
        self.sunshine_dir = sunshine_dir
        self.assets_dir = assets_dir
        self.apps_json_path = apps_json_path
        self.games_data_path = games_data_path

    def run(self):
        try:
            if not os.path.exists(self.games_data_path):
                self.finished_signal.emit(False, "games_data.json не найден!")
                return

            self.log_signal.emit("Чтение games_data.json...")
            with open(self.games_data_path, 'r', encoding='utf-8') as f:
                data = json.load(f)

            all_games = data.get("standalone", [])
            for grp in data.get("groups", {}).values():
                all_games.extend(grp)

            os.makedirs(self.assets_dir, exist_ok=True)

            sunshine_apps = []
            if os.path.exists(self.apps_json_path):
                try:
                    with open(self.apps_json_path, 'r', encoding='utf-8') as f:
                        existing_data = json.load(f)
                        for app in existing_data.get("apps", []):
                            if app.get("name") in ["Desktop", "Steam Big Picture"]:
                                sunshine_apps.append(app)
                except Exception as e:
                    self.log_signal.emit(f"Предупреждение: ошибка чтения apps.json: {e}")

            self.log_signal.emit(f"Найдено игр: {len(all_games)}")

            for g in all_games:
                raw_icon = g.get("icon", "")
                final_icon_path = ""
                if raw_icon and os.path.exists(raw_icon):
                    if not raw_icon.lower().endswith('.png'):
                        try:
                            safe_name = "".join(
                                [c for c in g["name"] if c.isalnum() or c in (' ', '_', '-')]
                            ).strip()
                            new_icon_path = os.path.join(self.assets_dir, f"{safe_name}.png")
                            if PIL_AVAILABLE:
                                with Image.open(raw_icon) as img:
                                    img.convert("RGBA").save(new_icon_path, "PNG")
                                final_icon_path = new_icon_path
                            else:
                                self.log_signal.emit(
                                    "Pillow не установлен, конвертация иконки пропущена "
                                    f"для '{g['name']}', используется исходный файл."
                                )
                                final_icon_path = raw_icon
                        except Exception as e:
                            self.log_signal.emit(f"Ошибка конвертации иконки '{g['name']}': {e}")
                            final_icon_path = raw_icon
                    else:
                        try:
                            filename = os.path.basename(raw_icon)
                            dest_path = os.path.join(self.assets_dir, filename)
                            shutil.copy2(raw_icon, dest_path)
                            final_icon_path = dest_path
                        except Exception as e:
                            self.log_signal.emit(f"Ошибка копирования иконки '{g['name']}': {e}")
                            final_icon_path = raw_icon

                    if final_icon_path:
                        final_icon_path = os.path.normpath(final_icon_path).replace("\\", "/")

                app_entry = {
                    "name": g["name"],
                    "cmd": os.path.normpath(g["path"]).replace("\\", "/"),
                    "working-dir": os.path.normpath(os.path.dirname(g["path"])).replace("\\", "/"),
                    "auto-detach": True,
                    "wait-all": True,
                    "image-path": final_icon_path
                }
                sunshine_apps.append(app_entry)
                self.log_signal.emit(f"Добавлено: {g['name']}")

            os.makedirs(os.path.dirname(self.apps_json_path), exist_ok=True)
            with open(self.apps_json_path, 'w', encoding='utf-8') as f:
                json.dump({"env": {}, "apps": sunshine_apps}, f, indent=4, ensure_ascii=False)

            self.log_signal.emit("apps.json сохранён. Перезапуск Sunshine...")

            kill_sunshine()
            time.sleep(1.5)
            exe = os.path.join(self.sunshine_dir, "sunshine.exe")
            subprocess.Popen([exe], cwd=self.sunshine_dir)

            self.finished_signal.emit(True, "Конфигурация обновлена и Sunshine перезапущен!")
        except Exception as e:
            self.finished_signal.emit(False, f"Ошибка синхронизации: {e}")


class RestartWorker(QThread):
    log_signal = pyqtSignal(str)
    finished_signal = pyqtSignal(bool, str)

    def __init__(self, sunshine_dir):
        super().__init__()
        self.sunshine_dir = sunshine_dir

    def run(self):
        try:
            self.log_signal.emit("Остановка Sunshine...")
            kill_sunshine()
            time.sleep(1.5)
            exe = os.path.join(self.sunshine_dir, "sunshine.exe")
            self.log_signal.emit("Запуск Sunshine...")
            subprocess.Popen([exe], cwd=self.sunshine_dir)
            self.finished_signal.emit(True, "Sunshine перезапущен.")
        except Exception as e:
            self.finished_signal.emit(False, f"Ошибка перезапуска: {e}")


class CredsWorker(QThread):
    log_signal = pyqtSignal(str)
    finished_signal = pyqtSignal(bool, str)

    def __init__(self, sunshine_dir, user, pwd):
        super().__init__()
        self.sunshine_dir = sunshine_dir
        self.user = user
        self.pwd = pwd

    def run(self):
        try:
            self.log_signal.emit("Остановка Sunshine перед сменой учётных данных...")
            kill_sunshine()
            time.sleep(1.5)
            exe = os.path.join(self.sunshine_dir, "sunshine.exe")

            # ВНИМАНИЕ: sunshine.exe принимает креды только как аргументы командной строки,
            # поэтому пароль на короткое время виден в списке процессов (Task Manager/ps).
            # Это ограничение самого sunshine.exe, а не этого скрипта - изменить без
            # поддержки другого способа передачи кредов на стороне Sunshine нельзя.
            self.log_signal.emit("Применение новых учётных данных...")
            subprocess.run([exe, "--creds", self.user, self.pwd], cwd=self.sunshine_dir)

            self.log_signal.emit("Запуск Sunshine...")
            subprocess.Popen([exe], cwd=self.sunshine_dir)

            self.finished_signal.emit(True, "Данные авторизации применены, процесс запущен.")
        except Exception as e:
            self.finished_signal.emit(False, f"Ошибка применения учётных данных: {e}")


class SunshineControlApp(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Sunshine Control Center")
        self.setFixedSize(480, 640)

        self.base_dir = os.getcwd()
        self.sunshine_dir = os.path.join(self.base_dir, "Sunshine")
        self.assets_dir = os.path.join(self.sunshine_dir, "assets")
        self.apps_json_path = os.path.join(self.sunshine_dir, "config", "apps.json")
        self.games_data_path = os.path.join(self.base_dir, "games_data.json")

        self.active_worker = None
        self.last_status = None

        self.init_ui()
        self.init_status_timer()

    # ------------------------------------------------------------------
    # UI
    # ------------------------------------------------------------------
    def init_ui(self):
        # Оформление теперь берётся из общего style.qss (см. style_loader.py),
        # который применяется глобально к QApplication в блоке __main__.
        central = QWidget()
        central.setObjectName("CentralWidget")
        main_layout = QVBoxLayout(central)
        main_layout.setContentsMargins(20, 20, 20, 20)
        main_layout.setSpacing(14)

        title = QLabel("SUNSHINE CONTROL")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        title.setStyleSheet("font-size: 20px; color: #007acc;")
        main_layout.addWidget(title)

        tabs = QTabWidget()
        main_layout.addWidget(tabs)

        # ===================== ВКЛАДКА: ГЛАВНАЯ =====================
        home_tab = QWidget()
        home_layout = QVBoxLayout(home_tab)
        home_layout.setContentsMargins(12, 16, 12, 12)
        home_layout.setSpacing(16)

        # --- БЛОК: СТАТУС В РЕАЛЬНОМ ВРЕМЕНИ ---
        status_group = QGroupBox("📡 Статус")
        status_layout = QHBoxLayout(status_group)
        status_layout.setSpacing(10)

        self.status_indicator = QFrame()
        self.status_indicator.setFixedSize(16, 16)
        self.status_indicator.setStyleSheet(
            "border-radius: 8px; background-color: #555; border: 1px solid #333;"
        )
        status_layout.addWidget(self.status_indicator)

        self.status_label = QLabel("Проверка...")
        status_layout.addWidget(self.status_label)
        status_layout.addStretch()

        self.btn_web = QPushButton("🌐 Открыть веб-панель")
        self.btn_web.setToolTip(f"Открыть {SUNSHINE_WEB_URL} в браузере по умолчанию")
        self.btn_web.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_web.clicked.connect(self.open_web_panel)
        status_layout.addWidget(self.btn_web)

        home_layout.addWidget(status_group)

        # --- БЛОК: СИНХРОНИЗАЦИЯ И УПРАВЛЕНИЕ ---
        sync_group = QGroupBox("🎮 Управление")
        sync_layout = QVBoxLayout(sync_group)
        sync_layout.setSpacing(12)

        self.btn_sync = QPushButton("🔄 ЗАПУСК И СИНХРОНИЗАЦИЯ SUNSHINE")
        self.btn_sync.setToolTip(
            "Считать games_data.json, обновить apps.json и перезапустить Sunshine"
        )
        self.btn_sync.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_sync.clicked.connect(self.sync_games)
        sync_layout.addWidget(self.btn_sync)

        self.btn_stop = QPushButton("🛑 ПРИНУДИТЕЛЬНО ОСТАНОВИТЬ SUNSHINE")
        self.btn_stop.setObjectName("StopBtn")
        self.btn_stop.setToolTip("Немедленно завершить процесс Sunshine")
        self.btn_stop.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_stop.clicked.connect(self.stop_sunshine)
        sync_layout.addWidget(self.btn_stop)

        home_layout.addWidget(sync_group)
        home_layout.addStretch()

        tabs.addTab(home_tab, "🎮 Главная")

        # ===================== ВКЛАДКА: АВТОРИЗАЦИЯ =====================
        auth_tab = QWidget()
        auth_tab_layout = QVBoxLayout(auth_tab)
        auth_tab_layout.setContentsMargins(12, 16, 12, 12)
        auth_tab_layout.setSpacing(16)

        auth_group = QGroupBox("🔐 Учётные данные")
        auth_layout = QVBoxLayout(auth_group)
        auth_layout.setSpacing(10)

        auth_layout.addWidget(QLabel("Новый логин:"))
        self.user_edit = QLineEdit()
        self.user_edit.setPlaceholderText("Введите логин...")
        auth_layout.addWidget(self.user_edit)

        auth_layout.addSpacing(6)
        auth_layout.addWidget(QLabel("Новый пароль:"))
        self.pass_edit = QLineEdit()
        self.pass_edit.setPlaceholderText("Введите пароль...")
        self.pass_edit.setEchoMode(QLineEdit.EchoMode.Password)
        auth_layout.addWidget(self.pass_edit)

        auth_layout.addSpacing(10)
        self.btn_creds = QPushButton("СОХРАНИТЬ ДАННЫЕ")
        self.btn_creds.setToolTip("Применить новые логин/пароль к Sunshine и перезапустить его")
        self.btn_creds.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_creds.clicked.connect(self.apply_creds)
        auth_layout.addWidget(self.btn_creds)

        auth_tab_layout.addWidget(auth_group)
        auth_tab_layout.addStretch()

        tabs.addTab(auth_tab, "🔐 Авторизация")

        # ===================== ВКЛАДКА: ЖУРНАЛ =====================
        log_tab = QWidget()
        log_tab_layout = QVBoxLayout(log_tab)
        log_tab_layout.setContentsMargins(12, 16, 12, 12)
        log_tab_layout.setSpacing(10)

        log_group = QGroupBox("📝 Журнал событий")
        log_group_layout = QVBoxLayout(log_group)
        self.log_view = QPlainTextEdit()
        self.log_view.setReadOnly(True)
        self.log_view.setMinimumHeight(260)
        log_group_layout.addWidget(self.log_view)

        log_tab_layout.addWidget(log_group)

        tabs.addTab(log_tab, "📝 Журнал")

        self.setCentralWidget(central)
        self.append_log("Приложение запущено.")

    # ------------------------------------------------------------------
    # Логирование
    # ------------------------------------------------------------------
    def append_log(self, message):
        timestamp = datetime.now().strftime("%H:%M:%S")
        self.log_view.appendPlainText(f"[{timestamp}] {message}")

    # ------------------------------------------------------------------
    # Мониторинг статуса
    # ------------------------------------------------------------------
    def init_status_timer(self):
        self.status_timer = QTimer(self)
        self.status_timer.setInterval(2500)  # 2.5 секунды
        self.status_timer.timeout.connect(self.refresh_status)
        self.status_timer.start()
        self.refresh_status()

    def refresh_status(self):
        running = is_sunshine_running()
        if running == self.last_status:
            return
        self.last_status = running
        if running:
            self.status_indicator.setStyleSheet(
                "border-radius: 8px; background-color: #2ecc71; border: 1px solid #1e8449;"
            )
            self.status_label.setText("Sunshine: Работает")
        else:
            self.status_indicator.setStyleSheet(
                "border-radius: 8px; background-color: #e74c3c; border: 1px solid #922b21;"
            )
            self.status_label.setText("Sunshine: Остановлен")

    # ------------------------------------------------------------------
    # Действия
    # ------------------------------------------------------------------
    def set_controls_enabled(self, enabled):
        self.btn_sync.setEnabled(enabled)
        self.btn_stop.setEnabled(enabled)
        self.btn_creds.setEnabled(enabled)

    def open_web_panel(self):
        self.append_log(f"Открытие веб-панели: {SUNSHINE_WEB_URL}")
        webbrowser.open(SUNSHINE_WEB_URL)

    def sync_games(self):
        if not os.path.exists(self.games_data_path):
            QMessageBox.critical(self, "Ошибка", "games_data.json не найден!")
            self.append_log("Ошибка: games_data.json не найден.")
            return

        self.set_controls_enabled(False)
        self.append_log("Запуск синхронизации...")

        self.active_worker = SyncWorker(
            self.sunshine_dir, self.assets_dir, self.apps_json_path, self.games_data_path
        )
        self.active_worker.log_signal.connect(self.append_log)
        self.active_worker.finished_signal.connect(self.on_sync_finished)
        self.active_worker.start()

    def on_sync_finished(self, success, message):
        self.set_controls_enabled(True)
        self.append_log(message)
        if success:
            QMessageBox.information(self, "Успех", message)
        else:
            QMessageBox.critical(self, "Ошибка", message)
        self.refresh_status()

    def stop_sunshine(self):
        self.append_log("Остановка Sunshine...")
        kill_sunshine()
        self.append_log("Процесс Sunshine завершён.")
        QMessageBox.information(self, "Статус", "Процесс Sunshine завершен.")
        self.refresh_status()

    def apply_creds(self):
        user = self.user_edit.text()
        pwd = self.pass_edit.text()
        if not user or not pwd:
            self.append_log("Не заполнены логин или пароль.")
            return

        self.set_controls_enabled(False)
        self.append_log("Применение новых учётных данных...")

        self.active_worker = CredsWorker(self.sunshine_dir, user, pwd)
        self.active_worker.log_signal.connect(self.append_log)
        self.active_worker.finished_signal.connect(self.on_creds_finished)
        self.active_worker.start()

    def on_creds_finished(self, success, message):
        self.set_controls_enabled(True)
        self.append_log(message)
        if success:
            self.pass_edit.clear()
            QMessageBox.information(self, "Готово", message)
        else:
            QMessageBox.critical(self, "Ошибка", message)
        self.refresh_status()


if __name__ == "__main__":
    app = QApplication(sys.argv)
    app.setStyle("Fusion")
    apply_global_style(app)
    ex = SunshineControlApp()
    ex.show()
    sys.exit(app.exec())