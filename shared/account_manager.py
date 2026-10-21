"""
Система аккаунтов GOR Launcher.

Идея: у каждого аккаунта — своя папка `accounts/<имя>/`, внутри которой
лежат ЕГО СОБСТВЕННЫЕ:
  - games_data.json   (игры, группы, настройки браузера, история и т.д.)
  - GOR_Profile/       (профиль Chromium со встроенным браузером — куки,
                         пароли, история сайтов)
  - addons/            (папка аддонов, которые пользователь поставил себе
                         через Control Center)

Как это подключается к остальному лаунчеру, БЕЗ переписывания полутора
десятков файлов, которые сейчас читают эти пути напрямую (GorLauncher.py,
browser_tab.py, bridge_loader.py, ControlCenter.py и т.д.):

  На уровне файловой системы, в момент выбора аккаунта (activate_account),
  мы подменяем:
    <корень проекта>/games_data.json   -> ЖЁСТКАЯ ССЫЛКА (hardlink) на
                                           accounts/<имя>/games_data.json
    <корень проекта>/core/GOR_Profile  -> JUNCTION (директория-ссылка) на
                                           accounts/<имя>/GOR_Profile
    <корень проекта>/addons            -> JUNCTION на
                                           accounts/<имя>/addons

  Весь остальной код лаунчера как открывал "games_data.json" /
  "GOR_Profile" / "addons" по старым относительным путям, так и
  продолжает это делать — он просто не знает, что это сейчас указывает
  на конкретную папку аккаунта. Physически данные каждого аккаунта лежат
  отдельно и не пересекаются.

  И junction (/J), и hardlink (/H) — особенность NTFS, которая НЕ требует
  прав администратора и НЕ требует включённого "Режима разработчика"
  (в отличие от настоящих симлинков через mklink без ключа или mklink /D).

Первый раз, когда лаунчер запускают уже с этой системой поверх старой
(одиночной) установки — существующие games_data.json / GOR_Profile /
addons автоматически "усыновляются" тем аккаунтом, который создают
первым (см. _adopt_existing), чтобы никто не потерял свою библиотеку игр.
"""

import os
import sys
import json
import shutil
import hashlib
import subprocess
import platform

NO_WINDOW_FLAGS = subprocess.CREATE_NO_WINDOW if platform.system() == "Windows" else 0


# --------------------------------------------------------------------- #
# Пути
# --------------------------------------------------------------------- #
def get_project_root():
    """Корень проекта — там же, где bridge_loader.py / GOR_Launcher.exe."""
    return os.path.dirname(os.path.abspath(sys.argv[0]))


def get_browser_dir():
    """Папка встроенного браузера (GOR_Brauzer/) - именно там, а не в
    core/, реально создаётся GOR_Profile: browser_widget.py берёт
    PROFILE_PATH из browser_constants.py, где BASE_DIR = папка самого
    browser_constants.py, т.е. GOR_Brauzer/."""
    return os.path.join(get_project_root(), "GOR_Brauzer")


ACCOUNTS_DIRNAME = "accounts"
INDEX_FILENAME = "accounts_index.json"

ROOT_DATA_FILE = "games_data.json"      # корень проекта
ROOT_PROFILE_DIR = "GOR_Profile"        # внутри GOR_Brauzer/
ROOT_ADDONS_DIR = "addons"              # корень проекта
AVATAR_FILENAME = "avatar.png"          # внутри accounts/<имя>/


def get_accounts_dir():
    d = os.path.join(get_project_root(), ACCOUNTS_DIRNAME)
    os.makedirs(d, exist_ok=True)
    return d


def get_account_dir(name):
    return os.path.join(get_accounts_dir(), name)


def _index_path():
    return os.path.join(get_accounts_dir(), INDEX_FILENAME)


# --------------------------------------------------------------------- #
# Индекс аккаунтов (список имён + хэш пароля, если задан)
# --------------------------------------------------------------------- #
def _load_index():
    path = _index_path()
    if not os.path.exists(path):
        return {"accounts": {}, "last_active": None}
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        data.setdefault("accounts", {})
        data.setdefault("last_active", None)
        return data
    except Exception:
        return {"accounts": {}, "last_active": None}


def _save_index(data):
    with open(_index_path(), "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def list_accounts():
    """Список имён аккаунтов, отсортированный по алфавиту."""
    return sorted(_load_index()["accounts"].keys(), key=str.lower)


def get_last_active():
    return _load_index().get("last_active")


def account_exists(name):
    return name in _load_index()["accounts"]


def account_has_password(name):
    info = _load_index()["accounts"].get(name) or {}
    return bool(info.get("password_hash"))


def get_avatar_path(name):
    """Путь к обложке аккаунта, если она задана, иначе None."""
    path = os.path.join(get_account_dir(name), AVATAR_FILENAME)
    return path if os.path.exists(path) else None


def save_avatar_png(name, png_bytes):
    """Сохраняет уже готовые PNG-байты (обрезку/масштабирование делает
    UI-слой, у него есть QPixmap) как обложку аккаунта."""
    os.makedirs(get_account_dir(name), exist_ok=True)
    path = os.path.join(get_account_dir(name), AVATAR_FILENAME)
    with open(path, "wb") as f:
        f.write(png_bytes)
    return path


def remove_avatar(name):
    path = os.path.join(get_account_dir(name), AVATAR_FILENAME)
    if os.path.exists(path):
        os.remove(path)


def _hash_password(password, salt):
    return hashlib.sha256((salt + password).encode("utf-8")).hexdigest()


def verify_password(name, password):
    info = _load_index()["accounts"].get(name)
    if not info or not info.get("password_hash"):
        return True  # у аккаунта нет пароля — пускаем без проверки
    return _hash_password(password, info.get("salt", "")) == info["password_hash"]


def create_account(name, password="", language=None):
    """Создаёт новый аккаунт (папку + запись в индексе). Возвращает
    (True, None) при успехе или (False, "причина") при ошибке.
    language - язык интерфейса этого аккаунта (например "en"); тема нового аккаунта - стандартная."""
    name = (name or "").strip()
    if not name:
        return False, "Имя аккаунта не может быть пустым"
    if any(c in name for c in '\\/:*?"<>|'):
        return False, "Имя аккаунта содержит запрещённые символы"
    if account_exists(name):
        return False, "Аккаунт с таким именем уже существует"

    idx = _load_index()
    entry = {}
    if password:
        salt = hashlib.sha256(os.urandom(16)).hexdigest()[:16]
        entry["salt"] = salt
        entry["password_hash"] = _hash_password(password, salt)
    idx["accounts"][name] = entry
    _save_index(idx)

    os.makedirs(get_account_dir(name), exist_ok=True)
    try:   # свои предпочтения аккаунта: язык и тема (addon_API/accounts.py)
        from addon_API import accounts as _accounts
        prefs = {"theme": {"active": "default", "overrides": {}}}
        if language:
            prefs["language"] = language
        _accounts.save_prefs(prefs, name)
    except Exception as e:
        print(f"[account_manager] Не удалось записать предпочтения аккаунта: {e}")
    return True, None


def delete_account(name):
    """Удаляет аккаунт из индекса и его папку с данными. Нельзя удалить
    активный (заблокированный ссылками) аккаунт — сначала переключись."""
    idx = _load_index()
    if name not in idx["accounts"]:
        return False, "Аккаунт не найден"
    if idx.get("last_active") == name:
        return False, "Нельзя удалить текущий активный аккаунт"
    del idx["accounts"][name]
    _save_index(idx)
    shutil.rmtree(get_account_dir(name), ignore_errors=True)
    return True, None


# --------------------------------------------------------------------- #
# Низкоуровневые операции подмены путей (junction / hardlink)
# --------------------------------------------------------------------- #
def _run_mklink(args):
    try:
        subprocess.run(
            ["cmd", "/c", "mklink"] + args,
            check=True, capture_output=True,
            creationflags=NO_WINDOW_FLAGS,
        )
        return True
    except Exception as e:
        print(f"[account_manager] mklink {args} не удался: {e}")
        return False


def _unlink_dir_point(path):
    """Снимает junction (или удаляет пустую папку) по пути `path`, не
    трогая то, на что она указывала. Возвращает True, если по пути
    осталась НАСТОЯЩАЯ директория с данными (значит — требуется миграция)."""
    if not os.path.isdir(path):
        return False
    try:
        os.rmdir(path)  # для junction снимает только ссылку; для пустой папки — удаляет её
        return False
    except OSError:
        return True  # непустая настоящая папка — реальные данные


def _link_dir(link_path, target_dir):
    os.makedirs(target_dir, exist_ok=True)
    had_real_data = _unlink_dir_point(link_path)
    if had_real_data:
        # Первая миграция: переносим существующие файлы в папку аккаунта,
        # если она ещё пуста, иначе — просто оставляем как есть и не трогаем.
        if not os.listdir(target_dir):
            for item in os.listdir(link_path):
                shutil.move(os.path.join(link_path, item), os.path.join(target_dir, item))
        shutil.rmtree(link_path, ignore_errors=True)

    ok = _run_mklink(["/J", link_path, target_dir])
    if not ok:
        # Резервный вариант, если junction почему-то не создался (не NTFS
        # и т.п.) — обычная копия. Хуже (не живая ссылка), но не ломает запуск.
        print(f"[account_manager] Резервный режим: копирую {target_dir} -> {link_path}")
        shutil.copytree(target_dir, link_path, dirs_exist_ok=True)
    return ok


def _link_file(link_path, target_file):
    if not os.path.exists(target_file):
        # ещё нет данных аккаунта — либо усыновляем то, что лежит в корне
        # (если это реальный файл, не общая ссылка), либо создаём пустой
        if os.path.exists(link_path):
            try:
                nlink = os.stat(link_path).st_nlink
            except OSError:
                nlink = 1
            if nlink <= 1:
                shutil.move(link_path, target_file)
            else:
                os.remove(link_path)
                with open(target_file, "w", encoding="utf-8") as f:
                    json.dump({}, f)
        else:
            with open(target_file, "w", encoding="utf-8") as f:
                json.dump({}, f)
    elif os.path.exists(link_path):
        try:
            os.remove(link_path)
        except OSError:
            pass

    try:
        os.link(target_file, link_path)
        return True
    except OSError as e:
        print(f"[account_manager] Жёсткая ссылка не удалась ({e}), копирую файл вместо неё.")
        shutil.copyfile(target_file, link_path)
        return False


# --------------------------------------------------------------------- #
# Активация аккаунта
# --------------------------------------------------------------------- #
def activate_account(name):
    """Переключает лаунчер на аккаунт `name`: подменяет games_data.json,
    core/GOR_Profile и addons ссылками на accounts/<name>/..."""
    if not account_exists(name):
        raise ValueError(f"Аккаунт '{name}' не найден")

    root = get_project_root()
    acc_dir = get_account_dir(name)
    os.makedirs(acc_dir, exist_ok=True)

    _link_file(os.path.join(root, ROOT_DATA_FILE), os.path.join(acc_dir, ROOT_DATA_FILE))
    _link_dir(os.path.join(get_browser_dir(), ROOT_PROFILE_DIR), os.path.join(acc_dir, ROOT_PROFILE_DIR))
    _link_dir(os.path.join(root, ROOT_ADDONS_DIR), os.path.join(acc_dir, ROOT_ADDONS_DIR))

    idx = _load_index()
    idx["last_active"] = name
    _save_index(idx)
    os.environ["GOR_ACTIVE_ACCOUNT"] = name
    _apply_account_preferences(name, root, acc_dir)


def _apply_account_preferences(name, root, acc_dir):
    """Язык и тема у каждого аккаунта свои (accounts/<имя>/preferences.json).
    - Старый аккаунт (создан до этой системы): «усыновляет» то, что было общим - язык из его
      games_data.json и тему из общего themes/_state.json, и дальше живёт со своими.
    - Язык синхронизируется и в games_data.json аккаунта (для кода, который читает его напрямую).
    - Язык интерфейса сразу перечитывается."""
    try:
        import sys as _s
        if root not in _s.path:
            _s.path.append(root)
        from addon_API import accounts as _accounts
        prefs = _accounts.get_prefs(name)
        changed = False
        data_path = os.path.join(acc_dir, ROOT_DATA_FILE)

        if not prefs.get("language"):
            try:
                with open(data_path, "r", encoding="utf-8") as f:
                    lang = (json.load(f) or {}).get("language")
            except Exception:
                lang = None
            if lang:
                prefs["language"] = lang
                changed = True
        elif os.path.exists(data_path):
            try:   # поправляем games_data.json на месте (не ломаем жёсткую ссылку)
                with open(data_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                if isinstance(data, dict) and data.get("language") != prefs["language"]:
                    data["language"] = prefs["language"]
                    with open(data_path, "w", encoding="utf-8") as f:
                        json.dump(data, f, indent=4, ensure_ascii=False)
            except Exception as e:
                print(f"[account_manager] Не удалось синхронизировать язык: {e}")

        if "theme" not in prefs:
            legacy = os.path.join(root, "themes", "_state.json")
            try:
                with open(legacy, "r", encoding="utf-8") as f:
                    state = json.load(f)
            except Exception:
                state = {}
            prefs["theme"] = {"active": state.get("active", "default"),
                              "overrides": state.get("overrides", {})}
            changed = True

        if changed:
            _accounts.save_prefs(prefs, name)
        try:
            import lang_loader
            lang_loader.reload_language()
        except Exception:
            pass
    except Exception as e:
        print(f"[account_manager] Предпочтения аккаунта не применены: {e}")
