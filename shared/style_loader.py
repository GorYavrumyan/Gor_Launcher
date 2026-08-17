"""
Общий загрузчик стилей для всех модулей GOR Launcher.

Все .py файлы проекта (GorLauncher, bridge_loader, sunshine_control,
ControlCenter, exporter_editor, game_editor, group_editor) читают один
и тот же файл `style.qss`, расположенный в КОРНЕ проекта, вместо того
чтобы держать оформление внутри кода. Это позволяет менять весь
визуальный стиль лаунчера в одном месте.

ВАЖНО: этот файл лежит в shared/, а style.qss - в корне проекта, рядом
с bridge_loader.py. Поэтому "рядом с собой" тут не работает - ищем
корень проекта так же надёжно, как это делает lang_loader.py.
"""

import os
import sys

STYLE_FILENAME = "style.qss"


def _detect_base_dir():
    """Определяет папку, где реально лежит style.qss.

    Пробуем по порядку: папка запущенного скрипта (sys.argv[0] - работает
    и для .exe, и для запуска bridge_loader.py/GorLauncher.py из корня),
    текущая рабочая директория (актуально для editors/*, remote/*, ... -
    они всегда запускаются с cwd в корне проекта), и в последнюю очередь -
    on уровень выше самого этого файла (shared/.. = корень проекта)."""
    candidates = [
        os.path.dirname(os.path.abspath(sys.argv[0])),
        os.getcwd(),
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    ]
    for c in candidates:
        if os.path.exists(os.path.join(c, STYLE_FILENAME)):
            return c
    return candidates[0]


_BASE_DIR = _detect_base_dir()


def load_stylesheet():
    """Читает style.qss из корня проекта и возвращает его содержимое.

    Если файл не найден или его не удалось прочитать - возвращает
    пустую строку, чтобы приложение не падало и просто использовало
    стандартный вид Qt.
    """
    style_path = os.path.join(_BASE_DIR, STYLE_FILENAME)
    if not os.path.exists(style_path):
        print(f"[style_loader] Файл {STYLE_FILENAME} не найден по пути: {style_path}")
        return ""
    try:
        with open(style_path, 'r', encoding='utf-8') as f:
            return f.read()
    except Exception as e:
        print(f"[style_loader] Не удалось прочитать {STYLE_FILENAME}: {e}")
        return ""


def apply_global_style(app):
    """Применяет общий style.qss ко всему приложению (QApplication)."""
    app.setStyleSheet(load_stylesheet())
