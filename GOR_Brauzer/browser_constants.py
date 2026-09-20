"""
browser_constants.py
---------------------
Пути, ключи хранения и справочные словари движка GOR Browser.

Здесь и только здесь определяются:
  - как найти ресурсы браузера (иконка, стартовая страница) что в режиме
    разработки, что после сборки в .exe (PyInstaller, sys._MEIPASS);
  - в каком файле и под какими ключами браузер хранит закладки/историю/
    настройки/расширения (общий games_data.json лаунчера, блок "browser");
  - список доступных поисковых систем.

Остальные модули пакета (browser_page, browser_downloads, browser_dialogs,
browser_startpage, browser_widget) импортируют константы отсюда, чтобы не
дублировать эти значения и не хранить их в самом GORBrowser.
"""

import os
import sys


def get_resource_path(relative_path):
    """Путь к ресурсу внутри папки браузера, работает и при обычном
    запуске, и после сборки PyInstaller (--onefile, sys._MEIPASS)."""
    if hasattr(sys, "_MEIPASS"):
        return os.path.join(sys._MEIPASS, relative_path)
    return os.path.join(os.path.dirname(os.path.abspath(__file__)), relative_path)


# Если запущено как .exe - берём папку рядом с exe (иначе настройки/профиль
# при каждом перезапуске "терялись" бы во временной папке _MEIPASS).
if getattr(sys, "frozen", False):
    BASE_DIR = os.path.dirname(sys.executable)
else:
    BASE_DIR = os.path.dirname(os.path.abspath(__file__))

_ICO_CANDIDATE = get_resource_path("Gor_Brauzer.ico")
ICON_PATH = _ICO_CANDIDATE if os.path.exists(_ICO_CANDIDATE) else "favicon.ico"
START_PAGE_PATH = get_resource_path("start_page.html")
PROFILE_PATH = os.path.join(BASE_DIR, "GOR_Profile")

# --- ИНТЕГРАЦИЯ С GOR LAUNCHER ---
# Браузер хранит закладки/историю/настройки/расширения ВНУТРИ общего
# games_data.json лаунчера, в отдельном блоке "browser", чтобы не плодить
# лишние файлы и не терять данные при переносе/архивации проекта.
# DATA_FILE - тот же файл, что использует GorLauncher (core/GorLauncher.py:
# self.data_file = "games_data.json"), путь относительный, т.к. лаунчер
# всегда запускается с cwd = корень проекта.
DATA_FILE = "games_data.json"

# Ключи под-блока "browser" внутри games_data.json (раньше были именами файлов)
BOOKMARKS_FILE = "bookmarks"
HISTORY_FILE = "history"
PASSWORDS_FILE = "passwords"
SETTINGS_FILE = "settings"
EXTENSIONS_FILE = "extensions"

SEARCH_ENGINES = {
    "Google": "https://google.com/search?q=",
    "Yandex": "https://yandex.ru/search/?text=",
    "Bing": "https://www.bing.com/search?q=",
    "DuckDuckGo": "https://duckduckgo.com/?q=",
}

# Те же 4 системы, но в формате "action URL + имя параметра формы", как их
# ждёт поисковая форма стартовой страницы (GOR_Brauzer/start_page.html).
# Раньше пользователь редактировал список поисковиков прямо на странице
# (шестерёнка -> "Поисковые системы"); теперь это часть настроек браузера
# (см. CustomizationManager в browser_dialogs.py), а страница только
# применяет активный движок, который ей передают через
# window.gorApplyNativeSettings({..., engines, engine_idx}).
BUILTIN_STARTPAGE_ENGINES = [
    {"name": "Google", "url": "https://www.google.com/search", "param": "q"},
    {"name": "Yandex", "url": "https://yandex.ru/search/", "param": "text"},
    {"name": "Bing", "url": "https://www.bing.com/search", "param": "q"},
    {"name": "DuckDuckGo", "url": "https://duckduckgo.com/", "param": "q"},
]

DEFAULT_SETTINGS = {
    "theme_color": "#4c6ef5",
    "top_bar_color": "#16171a",
    "font_family": "Segoe UI",
    "font_size": 10,                         # базовый кегль интерфейса и веб-страниц (пункт 3 ТЗ)
    "search_engine": "Google",
    "show_clock": True,
    "show_title": True,
    "show_todo": True,
    "ui_opacity": 0.9,
    "bg_image": "",

    # --- Перенесено из start_page.html (бывшая шестерёнка / bg-modal) ---
    "brand_text": "GOR // OS",              # название системы в шапке стартовой страницы
    "custom_engines": [],                    # доп. поисковики: [{"name","url","param"}, ...]
    "active_engine_idx": 0,                  # индекс в (BUILTIN_STARTPAGE_ENGINES + custom_engines)
    "bg_data": "",                           # data:...;base64,... фон стартовой страницы (картинка/HTML)
    "bg_type": "",                           # "image" | "html" | ""
    "bg_blur": 0,                            # px, размытие фона
    "bg_interactive": False,                 # разрешить клики "сквозь" HTML-фон

    # --- Новые фичи v1.2: AdBlock / VOT-переводчик / LAN-broadcast ---
    "adblock_enabled": True,                 # встроенный блокировщик рекламы (uBlock Engine)
    "vot_enabled": True,                     # закадровый переводчик видео (VOT Engine)
    "broadcast_enabled": True,               # приём вкладок/групп по локальной сети (UDP)
    "broadcast_port": 51888,                 # UDP-порт вещания/приёма GOR Browser

    # --- LAN: общий буфер обмена и синхронизация закладок ---
    # Выключены по умолчанию: это расшаривает данные (текст из буфера
    # обмена, закладки) всем GOR Browser в подсети - осознанный opt-in,
    # а не поведение "из коробки".
    "lan_clipboard_enabled": False,
    "lan_bookmark_sync_enabled": False,

    # --- Динамический AdBlock: фоновое обновление списка с GitHub ---
    "adblock_dynamic_update_enabled": True,
    "adblock_update_interval_hours": 24,
    "adblock_last_update": "",               # ISO-таймстамп последнего успешного обновления
    "adblock_update_url": "",                # пусто = DEFAULT_DYNAMIC_ADBLOCK_URL (StevenBlack/hosts)

    # --- Tab Suspender: автовыгрузка неактивных вкладок из RAM ---
    "tab_suspend_enabled": True,
    "tab_suspend_minutes": 15,               # неактивна дольше этого - выгружается
}

# Ключ под-блока "browser" в games_data.json, где хранятся сохранённые
# группы вкладок (см. browser_groups.py).
TAB_GROUPS_FILE = "tab_groups"

# Ключ под-блока "browser" в games_data.json для Session Restore (см.
# GORBrowser.mark_session_closed_cleanly / _write_session_state в
# browser_widget.py): {"active": bool, "tabs": [{"url","pinned"}, ...]}.
# "active" остаётся True, пока приложение открыто; при штатном закрытии
# лаунчер (GorLauncher.closeEvent) переводит его в False. Если следующий
# запуск видит "active": True - значит прошлый раз приложение не закрылось
# штатно (крах/kill), и можно предложить восстановить вкладки.
SESSION_FILE = "session"

# Порт по умолчанию для LAN Broadcast (см. browser_broadcast.py). Пользователь
# может переопределить его в settings["broadcast_port"].
DEFAULT_BROADCAST_PORT = 51888

# Палитра цветов, доступных при создании/перекрашивании группы вкладок.
TAB_GROUP_COLORS = [
    "#4c6ef5", "#f03e3e", "#2f9e44", "#f59f00",
    "#ae3ec9", "#1098ad", "#e64980", "#495057",
]


def get_startpage_engines(settings):
    """Возвращает полный список поисковиков стартовой страницы: 4 встроенных
    + пользовательские, добавленные через CustomizationManager. Единая точка
    правды и для диалога настроек, и для payload'а, который уходит в JS."""
    custom = settings.get("custom_engines") or []
    return list(BUILTIN_STARTPAGE_ENGINES) + list(custom)


