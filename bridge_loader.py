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
        subprocess.check_call([sys.executable, "-m", "pip", "install", "--upgrade", "pip"], creationflags=NO_WINDOW_FLAGS)
        subprocess.check_call([sys.executable, "-m", "pip", "install", "-r", req_file], creationflags=NO_WINDOW_FLAGS)
        with open(marker_file, 'w', encoding='utf-8') as f:
            f.write(req_hash)
        print("Все библиотеки успешно установлены!")
    except Exception as e:
        print(f"Ошибка при установке библиотек в {addon_path}: {e}")

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
    gor_py_candidate = os.path.join(base_dir, "GorLauncher.py")

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
    script_path = os.path.join(base_path, "ControlCenter.py")
    
    if os.path.exists(script_path):
        subprocess.Popen([sys.executable, script_path])

def load_addons(launcher):
    base_dir = os.path.dirname(os.path.abspath(sys.argv[0]))
    addons_dir = os.path.join(base_dir, "addons")
    if not os.path.exists(addons_dir): return

    control_center_found = False
    active_addons = []

    for folder in os.listdir(addons_dir):
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
            
            addon_name = config.get("name", folder)
            active_addons.append(addon_name)
            
            start_filename = config.get("start_file")
            if not start_filename: continue

            install_requirements(addon_path)

            core_script = os.path.join(core_dir, start_filename)
            
            if os.path.exists(core_script):
                spec = importlib.util.spec_from_file_location("addon_module", core_script)
                module = importlib.util.module_from_spec(spec)
                spec.loader.exec_module(module)
                if hasattr(module, "init_addon"):
                    module.init_addon(launcher)
        except Exception as e:
            print(f"Ошибка в {folder}: {e}")

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