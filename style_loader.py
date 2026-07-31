"""
Общий загрузчик стилей для всех модулей GOR Launcher.

Все .py файлы проекта (GorLauncher, bridge_loader, sunshine_control,
ControlCenter, exporter_editor, game_editor, group_editor) читают один
и тот же файл `style.qss`, расположенный рядом с этим модулем, вместо
того чтобы держать оформление внутри кода. Это позволяет менять весь
визуальный стиль лаунчера в одном месте.
"""

import os

STYLE_FILENAME = "style.qss"


def load_stylesheet():
    """Читает style.qss рядом с этим файлом и возвращает его содержимое.

    Если файл не найден или его не удалось прочитать - возвращает
    пустую строку, чтобы приложение не падало и просто использовало
    стандартный вид Qt.
    """
    style_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), STYLE_FILENAME)
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
