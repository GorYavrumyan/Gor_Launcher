import sys
import os
import importlib.util
import json
import subprocess
import hashlib
from PyQt6.QtWidgets import QApplication, QPushButton
from PyQt6.QtCore import Qt

from style_loader import apply_global_style
from updater import UpdateWorker, get_local_version, UpdaterDialog

# Добавляем путь для импорта
current_dir = os.path.dirname(os.path.abspath(sys.argv[0]))
if current_dir not in sys.path:
    sys.path.append(current_dir)

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
        subprocess.check_call([sys.executable, "-m", "pip", "install", "--upgrade", "pip"])
        subprocess.check_call([sys.executable, "-m", "pip", "install", "-r", req_file])
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

def run_control_center():
    # Исправленный путь: берем директорию самого приложения
    base_path = os.path.dirname(os.path.abspath(sys.argv[0]))
    script_path = os.path.join(base_path, "ControlCenter.py")
    
    if os.path.exists(script_path):
        # Запускаем, явно указывая полный путь к файлу
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

            # Автоматическая установка библиотек перед загрузкой кода
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
        btn = QPushButton("⚙️ ADDON MANAGER")
        btn.setCursor(Qt.CursorShape.PointingHandCursor)
        btn.clicked.connect(run_control_center)
        header_lay = launcher.main_lay.itemAt(0).layout()
        header_lay.insertWidget(2, btn)


# --------------------------------------------------------------------- #
# Фоновая проверка обновлений при каждом запуске лаунчера.
#
# Проверка выполняется в отдельном QThread (см. updater.UpdateWorker),
# поэтому не блокирует интерфейс лаунчера. Если найдена версия новее
# текущей - в шапке лаунчера появляется кнопка "ЕСТЬ ОБНОВЛЕНИЕ", по
# нажатию на которую открывается обычное окно UpdaterDialog. Если
# обновлений нет или проверка не удалась (например, нет интернета) -
# лаунчер просто продолжает работать как обычно, никаких окон/ошибок
# пользователю не показывается.
# --------------------------------------------------------------------- #
def check_updates_in_background(launcher):
    current_version = get_local_version()

    checker = UpdateWorker(UpdateWorker.MODE_CHECK, current_version)
    # Храним ссылку на поток на самом объекте лаунчера, чтобы его не
    # удалил сборщик мусора до завершения проверки.
    launcher._update_checker = checker

    def on_check_result(info):
        remote_version = info.get("version")
        if remote_version and remote_version != current_version:
            show_update_available_button(launcher, remote_version)

    def on_finished(success, message):
        # Тихо игнорируем ошибку проверки (нет сети и т.п.) - это фоновая
        # проверка, она не должна мешать пользователю пользоваться лаунчером.
        if not success:
            print(f"[updater] Фоновая проверка обновлений: {message}")

    checker.check_result_signal.connect(on_check_result)
    checker.finished_signal.connect(on_finished)
    checker.start()


def show_update_available_button(launcher, remote_version):
    # Если кнопка уже была добавлена (например, при повторном вызове) -
    # не дублируем её.
    if getattr(launcher, "_update_btn_added", False):
        return
    launcher._update_btn_added = True

    def open_updater():
        dialog = UpdaterDialog(launcher)
        dialog.exec()

    btn = QPushButton(f"⬆️ ЕСТЬ ОБНОВЛЕНИЕ ({remote_version})")
    btn.setCursor(Qt.CursorShape.PointingHandCursor)
    btn.clicked.connect(open_updater)
    header_lay = launcher.main_lay.itemAt(0).layout()
    header_lay.insertWidget(2, btn)


if __name__ == "__main__":
    app = QApplication(sys.argv)
    apply_global_style(app)
    launcher = GORLauncher()
    load_addons(launcher)
    launcher.show()
    check_updates_in_background(launcher)
    sys.exit(app.exec())