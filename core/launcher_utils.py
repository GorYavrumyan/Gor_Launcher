"""
Общие утилиты лаунчера: поиск иконки, кэш обложек, запуск файлов и
процессов-редакторов.

Вынесены из GorLauncher.py, чтобы не раздувать главный файл - этими же
функциями (universal_launch, run_editor_process) пользуются несколько
разных модулей (GameCard, GORLauncher), поэтому им самое место в общем
файле, а не внутри конкретного класса.
"""

import sys
import os
import subprocess
import platform
from functools import lru_cache
from PyQt6.QtGui import QPixmap

NO_GROUP_KEY = "Без группы"  # внутренний ключ данных - НЕ переводится, чтобы не ломать games_data.json

# Флаг для subprocess.*, чтобы служебные консольные команды (tasklist, taskkill)
# не открывали и не мигали окном терминала на Windows. На других ОС просто 0.
NO_WINDOW_FLAGS = subprocess.CREATE_NO_WINDOW if platform.system() == 'Windows' else 0


def find_favicon_path():
    """Ищет favicon.ico рядом со скриптом, на уровень выше и в рабочей папке.
    Если нигде не найден - возвращает путь рядом со скриптом (по умолчанию)
    и выводит предупреждение в консоль, чтобы было видно, что иконка не найдена."""
    script_dir = os.path.dirname(os.path.abspath(__file__))
    candidates = []
    if getattr(sys, "frozen", False):
        candidates.append(os.path.dirname(sys.executable))
    candidates.append(script_dir)
    candidates.append(os.getcwd())
    candidates.append(os.path.dirname(script_dir))
    for d in candidates:
        p = os.path.join(d, "favicon.ico")
        if os.path.exists(p):
            return p
    print(f"[launcher_utils] favicon.ico не найден. Проверенные папки: {candidates}")
    return os.path.join(script_dir, "favicon.ico")


@lru_cache(maxsize=512)
def load_pixmap_cached(path):
    """Кэширует QPixmap по пути к файлу, чтобы не читать иконку с диска
    заново при каждом refresh_list."""
    return QPixmap(path) if path else QPixmap()


def universal_launch(path):
    """Открывает файл/папку средствами ОС (аналог двойного клика в проводнике)."""
    if platform.system() == 'Windows':
        os.startfile(path)
    elif platform.system() == 'Darwin':  # macOS
        subprocess.call(['open', path])
    else:  # Linux
        subprocess.call(['xdg-open', path])


def run_editor_process(script_name, args=None, py_subdir=None):
    """Запускает редактор (game_editor/group_editor/...) как отдельный
    процесс - .exe, если он собран, иначе .py тем же интерпретатором.

    .exe всегда ищем ПЛОСКО в корне проекта - именно так собираются и
    распространяются готовые .exe (рядом с GOR_Launcher.exe), независимо
    от того, как разложены исходники .py на диске у разработчика.

    py_subdir - подпапка исходника .py (например "editors", "remote",
    "extras") на время разработки, пока .exe ещё не собран. Используется
    только для запуска .py - самого исполняемого файла это не касается."""
    exe_name = f"{script_name}.exe"
    py_name = f"{script_name}.py"
    py_path = os.path.join(py_subdir, py_name) if py_subdir else py_name

    if os.path.exists(exe_name):
        return subprocess.Popen([exe_name] + (args if args else []))
    else:
        if sys.executable.lower().endswith('.exe') and 'python' not in os.path.basename(sys.executable).lower():
            return subprocess.Popen(["python", py_path] + (args if args else []))
        else:
            return subprocess.Popen([sys.executable, py_path] + (args if args else []))
