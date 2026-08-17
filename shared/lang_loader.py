"""
Общий загрузчик языковых пакетов для всех модулей GOR Launcher.

Идея та же, что и у style_loader.py: вместо того, чтобы держать текст
интерфейса внутри кода, все строки хранятся в JSON-файлах внутри папки
`lang/` (например lang/ru.json, lang/en.json, lang/uk.json...).

Чтобы добавить новый язык - просто положи новый файл `lang/<код>.json`
рядом с остальными (скопировав, например, lang/en.json как основу и
переведя значения). Никакой код менять не нужно - язык появится в списке
автоматически (см. available_languages()).

Какой язык сейчас используется - хранится в games_data.json в поле
"language" (например "ru" или "en"). Это единственное, что связывает
языковой пакет с основными данными лаунчера.

Использование в коде:

    from lang_loader import tr

    label = QLabel(tr("launcher.app_title"))
    btn.setText(tr("common.delete"))
    msg = tr("history.session_time", h=2, m=15)   # поддерживает {h}/{m} и т.п.

Если ключ не найден ни в текущем языке, ни в резервном (ru) - вернётся
сам ключ, чтобы приложение не падало и было видно, что перевод забыли
добавить.
"""

import os
import json

LANG_DIRNAME = "lang"
DATA_FILENAME = "games_data.json"
DEFAULT_LANG = "ru"
FALLBACK_LANG = "ru"

def _detect_base_dir():
    """Определяет папку, где реально лежат lang/ и games_data.json.

    ВАЖНО: нельзя использовать os.path.dirname(os.path.abspath(__file__))
    напрямую - это ломается в собранных PyInstaller .exe (--onefile и
    --onedir), потому что там __file__ указывает на временную/внутреннюю
    папку сборки, а не на реальную папку рядом с .exe, где лежат lang/ и
    games_data.json. Именно поэтому в ControlCenter.py, sunshine_control.py
    и fortune_wheel.py, собранных как отдельные .exe, tr() возвращал сырые
    ключи вида "control_center.window_title" - файлы просто не находились.

    Вместо этого используем тот же приём, что и весь остальной проект
    (GorLauncher.py, bridge_loader.py): os.path.dirname(os.path.abspath(sys.argv[0])) -
    это всегда папка реального .exe / .py, который был запущен.

    ПОСЛЕ РАЗБИВКИ ПО ПАПКАМ: сам lang_loader.py теперь лежит в shared/,
    на уровень глубже корня проекта, поэтому старого fallback на __file__
    уже недостаточно - добавили os.getcwd() (актуально при запуске
    editors/*, remote/*, ... - они всегда стартуют с cwd в корне проекта)
    и подъём на уровень выше self (shared/.. = корень проекта)."""
    import sys as _sys
    candidates = [
        os.path.dirname(os.path.abspath(_sys.argv[0])),
        os.getcwd(),
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    ]
    for c in candidates:
        if os.path.isdir(os.path.join(c, LANG_DIRNAME)) or os.path.exists(os.path.join(c, DATA_FILENAME)):
            return c

    # Ничего не нашли - возвращаем первый вариант, чтобы сообщения об
    # ошибках ниже показывали реалистичный путь для диагностики.
    return candidates[0]


_BASE_DIR = _detect_base_dir()
_LANG_DIR = os.path.join(_BASE_DIR, LANG_DIRNAME)
_DATA_FILE = os.path.join(_BASE_DIR, DATA_FILENAME)

_lang_cache = {}          # code -> dict, кэш уже загруженных json-файлов
_current_lang_code = None
_current_dict = {}
_fallback_dict = {}


# --------------------------------------------------------------------- #
# Работа со списком доступных языков
# --------------------------------------------------------------------- #
def available_languages():
    """Возвращает список языков, найденных в папке lang/.

    Каждый элемент - словарь {"code": "ru", "name": "Русский"}.
    Имя языка берётся из ключа "_meta.name" внутри самого json-файла,
    если оно есть, иначе используется код языка.
    """
    result = []
    if not os.path.isdir(_LANG_DIR):
        return result
    for fname in sorted(os.listdir(_LANG_DIR)):
        if not fname.lower().endswith(".json"):
            continue
        code = fname[:-5]
        data = _load_lang_file(code)
        name = data.get("_meta", {}).get("name", code)
        result.append({"code": code, "name": name})
    return result


def _load_lang_file(code):
    if code in _lang_cache:
        return _lang_cache[code]
    path = os.path.join(_LANG_DIR, f"{code}.json")
    data = {}
    if os.path.exists(path):
        try:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
        except Exception as e:
            print(f"[lang_loader] Не удалось прочитать {path}: {e}")
            data = {}
    _lang_cache[code] = data
    return data


# --------------------------------------------------------------------- #
# Текущий язык (хранится в games_data.json -> "language")
# --------------------------------------------------------------------- #
def get_language():
    """Читает текущий выбранный язык из games_data.json.
    Если файла/поля нет - возвращает DEFAULT_LANG, ничего не создавая."""
    if os.path.exists(_DATA_FILE):
        try:
            with open(_DATA_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
            code = data.get("language")
            if code:
                return code
        except Exception:
            pass
    return DEFAULT_LANG


def set_language(code):
    """Сохраняет выбранный язык в games_data.json и сразу активирует его."""
    data = {"groups": {}, "standalone": [], "history": []}
    if os.path.exists(_DATA_FILE):
        try:
            with open(_DATA_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
        except Exception:
            pass
    data["language"] = code
    try:
        with open(_DATA_FILE, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=4, ensure_ascii=False)
    except Exception as e:
        print(f"[lang_loader] Не удалось сохранить язык в {_DATA_FILE}: {e}")
    reload_language(code)


def reload_language(code=None):
    """Перечитывает словарь текущего (или указанного) языка с диска."""
    global _current_lang_code, _current_dict, _fallback_dict
    code = code or get_language()
    _lang_cache.pop(code, None)          # форсируем чтение файла заново
    _current_dict = _load_lang_file(code)
    _current_lang_code = code
    _fallback_dict = _load_lang_file(FALLBACK_LANG) if FALLBACK_LANG != code else _current_dict


def current_language():
    ensure_loaded()
    return _current_lang_code


def ensure_loaded():
    if _current_lang_code is None:
        reload_language()


# --------------------------------------------------------------------- #
# Перевод
# --------------------------------------------------------------------- #
def _lookup(d, dotted_key):
    cur = d
    for part in dotted_key.split("."):
        if not isinstance(cur, dict) or part not in cur:
            return None
        cur = cur[part]
    return cur if isinstance(cur, str) else None


def tr(key, **kwargs):
    """Возвращает переведённую строку по ключу вида 'раздел.имя'.

    Если в строке есть плейсхолдеры вида {h}, {name} и т.п. - передай их
    именованными аргументами: tr("history.session_time", h=2, m=30).
    """
    ensure_loaded()
    value = _lookup(_current_dict, key)
    if value is None:
        value = _lookup(_fallback_dict, key)
    if value is None:
        return key
    if kwargs:
        try:
            return value.format(**kwargs)
        except Exception:
            return value
    return value
