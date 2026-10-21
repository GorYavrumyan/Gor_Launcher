"""
Предпочтения аккаунтов GOR Launcher: язык интерфейса, тема и всё, что должно быть «своё у каждого».

У каждого аккаунта есть файл  accounts/<имя>/preferences.json:

    {
      "language": "en",
      "theme": {"active": "forest", "overrides": {"accent": "#ff2d95"}},
      "addons": {"my_addon": {"любой ключ": "любое значение"}}
    }

Какой аккаунт активен, определяется так: переменная окружения GOR_ACTIVE_ACCOUNT (её ставит
account_manager.activate_account, а дочерние процессы лаунчера — редакторы, Control Center —
её наследуют); если её нет — «последний активный» из accounts/accounts_index.json.
Если аккаунтов нет вовсе (старая установка без системы аккаунтов) — активного аккаунта нет,
и всё работает по-старому, глобально.

Модуль — чистый Python без PyQt, его безопасно импортировать откуда угодно
(lang_loader, style_loader, account_manager).
"""

import os
import json
import tempfile

_PKG_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(_PKG_DIR)
ACCOUNTS_DIR = os.path.join(PROJECT_ROOT, "accounts")
INDEX_FILE = os.path.join(ACCOUNTS_DIR, "accounts_index.json")
PREFS_FILE = "preferences.json"
ENV_VAR = "GOR_ACTIVE_ACCOUNT"


def _read_json(path, default):
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        return data if isinstance(data, type(default)) else default
    except Exception:
        return default


def _write_json_atomic(path, data):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=os.path.dirname(path), prefix=".prefs_", suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        os.replace(tmp, path)
    except Exception:
        try:
            os.remove(tmp)
        except OSError:
            pass
        raise


# --------------------------------------------------------------------- #
# Какие аккаунты есть и какой активен
# --------------------------------------------------------------------- #
def list_accounts():
    idx = _read_json(INDEX_FILE, {})
    names = list((idx.get("accounts") or {}).keys())
    if names:
        return names
    if os.path.isdir(ACCOUNTS_DIR):
        return sorted(d for d in os.listdir(ACCOUNTS_DIR)
                      if os.path.isdir(os.path.join(ACCOUNTS_DIR, d)))
    return []


def active_name():
    """Имя активного аккаунта или None (если системы аккаунтов нет)."""
    name = os.environ.get(ENV_VAR)
    if name and os.path.isdir(os.path.join(ACCOUNTS_DIR, name)):
        return name
    last = _read_json(INDEX_FILE, {}).get("last_active")
    if last and os.path.isdir(os.path.join(ACCOUNTS_DIR, last)):
        return last
    return None


def account_dir(name=None):
    name = name or active_name()
    return os.path.join(ACCOUNTS_DIR, name) if name else None


def themes_dir(name=None):
    """Папка собственных тем аккаунта (или None)."""
    d = account_dir(name)
    return os.path.join(d, "themes") if d else None


# --------------------------------------------------------------------- #
# Предпочтения
# --------------------------------------------------------------------- #
def prefs_path(name=None):
    d = account_dir(name)
    return os.path.join(d, PREFS_FILE) if d else None


def get_prefs(name=None):
    p = prefs_path(name)
    return _read_json(p, {}) if p else {}


def save_prefs(data, name=None):
    p = prefs_path(name)
    if p is None:
        return False
    _write_json_atomic(p, data)
    return True


def pref(key, default=None, name=None):
    return get_prefs(name).get(key, default)


def set_pref(key, value, name=None):
    p = prefs_path(name)
    if p is None:
        return False
    data = _read_json(p, {})
    data[key] = value
    _write_json_atomic(p, data)
    return True


def ns_get(namespace, key, default=None, name=None):
    """Значение из личного пространства аддона (preferences.json -> addons -> <namespace>)."""
    return (get_prefs(name).get("addons", {}).get(namespace, {})).get(key, default)


def ns_set(namespace, key, value, name=None):
    p = prefs_path(name)
    if p is None:
        return False
    data = _read_json(p, {})
    data.setdefault("addons", {}).setdefault(namespace, {})[key] = value
    _write_json_atomic(p, data)
    return True


def ns_all(namespace, name=None):
    return dict(get_prefs(name).get("addons", {}).get(namespace, {}))
