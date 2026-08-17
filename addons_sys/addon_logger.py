"""
Общий помощник логирования для аддонов GOR Launcher.

Аддоны работают внутри процесса лаунчера, а Control Center - это ОТДЕЛЬНЫЙ
процесс (см. run_control_center() в bridge_loader.py). Напрямую передать
"что делает аддон" из одного процесса в другой нельзя - поэтому оба
общаются через файл activity.json внутри папки самого аддона:
аддон в него пишет, Control Center его читает раз в секунду
(см. MonitoringTab._refresh() в ControlCenter.py).

Базовые события (аддон найден / загружается / запустился / ошибка при
запуске) bridge_loader.py пишет туда САМ, автоматически, для ЛЮБОГО
аддона - без участия автора аддона.

А вот что-то специфичное про конкретный аддон ("создана вкладка
Калькулятор", "открыт файл проекта" и т.п.) знает только сам аддон -
такие события каждый аддон должен записывать сам, одной строкой:

    from addon_logger import log_activity

    log_activity(__file__, "change", "Создана вкладка Калькулятор")

Первым аргументом ВСЕГДА передавай __file__ своего скрипта - по нему
автоматически вычисляется папка аддона (на два уровня выше core/*.py),
и запись уходит в правильный activity.json.

Допустимые msg_type (влияют только на иконку в логе Control Center):
    "info"    - ℹ️  обычное событие
    "change"  - ✏️  аддон что-то создал/изменил в интерфейсе лаунчера
    "request" - 📨  аддон запросил доступ к чему-либо (файлы, сеть, папки)
    "error"   - ⚠️  что-то пошло не так
"""

import os
import json
from datetime import datetime

MAX_LOG_ENTRIES = 50


def _addon_root_from_file(caller_file):
    """caller_file - это обычно addons/<name>/core/<script>.py.
    Папка самого аддона - на два уровня выше: .../core/.. -> addons/<name>"""
    return os.path.dirname(os.path.dirname(os.path.abspath(caller_file)))


def _write_entry(addon_root, msg_type, message):
    """Низкоуровневая запись одной строки в activity.json указанной папки
    аддона. Никогда не бросает исключение наружу - сбой логирования не
    должен ронять сам аддон."""
    try:
        activity_file = os.path.join(addon_root, "activity.json")

        entries = []
        if os.path.exists(activity_file):
            try:
                with open(activity_file, "r", encoding="utf-8") as f:
                    entries = json.load(f)
            except Exception:
                entries = []

        entries.insert(0, {
            "type": msg_type,
            "message": message,
            "time": datetime.now().strftime("%H:%M:%S"),
        })
        entries = entries[:MAX_LOG_ENTRIES]

        with open(activity_file, "w", encoding="utf-8") as f:
            json.dump(entries, f, ensure_ascii=False, indent=2)
    except Exception as e:
        print(f"[addon_logger] Не удалось записать лог: {e}")


def log_activity(caller_file, msg_type, message):
    """То, что вызывает САМ АДДОН из своего core/*.py:

        log_activity(__file__, "change", "Создана вкладка Калькулятор")
    """
    addon_root = _addon_root_from_file(caller_file)
    _write_entry(addon_root, msg_type, message)


def log_activity_for_addon(addon_root, msg_type, message):
    """То же самое, но когда путь к папке аддона уже известен напрямую
    (используется bridge_loader.py для автоматических системных записей,
    ему не из чего брать __file__ чужого аддона)."""
    _write_entry(addon_root, msg_type, message)