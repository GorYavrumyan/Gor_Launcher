"""
Кроссплатформенные помощники (Windows / Linux / macOS).

Собирает в одном месте всё, что раньше было завязано на Windows:
  * ссылки на папки (junction на Windows, symlink на Linux/macOS);
  * запуск игр (Windows: как есть; Linux: нативные файлы напрямую,
    .exe/.bat через Wine или Proton-обёртку, например GOR_WINE="umu-run");
  * остановка процесса вместе с дочерними;
  * поиск Sunshine.

Модуль не импортирует Qt и безопасен для импорта откуда угодно.
"""
import os
import re
import shlex
import shutil
import signal
import subprocess
import platform
import threading

IS_WINDOWS = platform.system() == "Windows"
IS_MAC = platform.system() == "Darwin"
IS_LINUX = platform.system() == "Linux"

NO_WINDOW_FLAGS = subprocess.CREATE_NO_WINDOW if IS_WINDOWS else 0

_WIN_PATH_RE = re.compile(r"^[A-Za-z]:[\\/]")
_WINE_EXTS = (".exe", ".bat", ".cmd", ".msi")
_NATIVE_EXTS = (".sh", ".appimage", ".x86_64", ".x86", ".run", ".bin", ".py")


# --------------------------------------------------------------------- #
# Python для запуска лаунчера
# --------------------------------------------------------------------- #
def gui_python(project_root):
    """Интерпретатор для запуска лаунчера: встроенный runtime/ на Windows,
    иначе текущий Python (на Linux это системный python3 / venv)."""
    import sys
    if IS_WINDOWS:
        for name in ("pythonw.exe", "python.exe"):
            p = os.path.join(project_root, "runtime", name)
            if os.path.exists(p):
                return p
    return sys.executable


# --------------------------------------------------------------------- #
# Ссылки на папки
# --------------------------------------------------------------------- #
def make_dir_link(link_path, target_dir):
    """Создаёт 'живую' ссылку link_path -> target_dir.
    Windows: junction (mklink /J, без прав администратора).
    Linux/macOS: символическая ссылка. Возвращает True при успехе."""
    try:
        if IS_WINDOWS:
            subprocess.run(["cmd", "/c", "mklink", "/J", link_path, target_dir],
                           check=True, capture_output=True, creationflags=NO_WINDOW_FLAGS)
        else:
            os.symlink(os.path.abspath(target_dir), link_path, target_is_directory=True)
        return True
    except Exception as e:
        print(f"[platform_utils] ссылка {link_path} -> {target_dir} не создана: {e}")
        return False


# --------------------------------------------------------------------- #
# Запуск игр
# --------------------------------------------------------------------- #
def is_windows_path(path):
    return bool(_WIN_PATH_RE.match(path or ""))


def _has_exec_magic(path):
    """ELF-бинарник или скрипт с shebang. Нужно, потому что на exFAT/NTFS-разделах
    ВСЕ файлы выглядят исполняемыми - по одному биту X_OK судить нельзя."""
    try:
        with open(path, "rb") as f:
            head = f.read(4)
        return head.startswith(b"\x7fELF") or head.startswith(b"#!")
    except OSError:
        return False


def is_game_process(path):
    """Нужно ли запускать `path` как процесс (с учётом времени игры), а не
    открывать средствами ОС. Windows: .exe/.bat. Linux: ещё и нативные файлы."""
    low = (path or "").lower()
    if low.endswith((".exe", ".bat")):
        return True
    if IS_WINDOWS:
        return False
    if is_windows_path(path) or low.endswith(_WINE_EXTS + _NATIVE_EXTS):
        return True
    return os.path.isfile(path) and os.access(path, os.X_OK) and _has_exec_magic(path)


def find_wine():
    """Команда-обёртка для Windows-игр на Linux (список argv) или None.
    Переопределяется переменной окружения GOR_WINE, например 'umu-run' или 'wine64'."""
    custom = os.environ.get("GOR_WINE", "").strip()
    if custom:
        return shlex.split(custom)
    for name in ("wine", "wine64", "umu-run"):
        p = shutil.which(name)
        if p:
            return [p]
    return None


def _split_args(args, windows_style=False):
    if not args:
        return []
    if not windows_style:
        return shlex.split(args)
    # обратные слэши в путях не должны съедаться; кавычки снимаем сами
    return [t[1:-1] if len(t) > 1 and t[0] == t[-1] == '"' else t
            for t in shlex.split(args, posix=False)]


def launch_unix(path, args=""):
    """Запуск игры на Linux/macOS. Возвращает subprocess.Popen.
    Процесс запускается в собственной сессии - его можно остановить вместе с детьми."""
    low = path.lower()
    if is_windows_path(path) or low.endswith(_WINE_EXTS):
        wine = find_wine()
        if not wine:
            raise RuntimeError(
                "Для запуска Windows-игр на Linux нужен Wine (или Proton через umu-run).\n"
                "Установите wine либо задайте переменную GOR_WINE, например GOR_WINE=umu-run.")
        if is_windows_path(path):
            target, cwd = path, os.path.expanduser("~")
        else:
            target = os.path.abspath(path)
            cwd = os.path.dirname(target)
        prefix = wine + (["cmd", "/c"] if low.endswith((".bat", ".cmd")) else [])
        cmd = prefix + [target] + _split_args(args, windows_style=True)
        return subprocess.Popen(cmd, cwd=cwd, start_new_session=True)

    full = os.path.abspath(path)
    cwd = os.path.dirname(full)
    if low.endswith(".py"):
        import sys
        cmd = [sys.executable, full]
    elif low.endswith(".sh") and not os.access(full, os.X_OK):
        cmd = ["bash", full]
    elif low.endswith(".appimage") and not os.access(full, os.X_OK):
        raise RuntimeError(f"Файл не исполняемый. Выполните: chmod +x \"{full}\"")
    else:
        if not os.access(full, os.X_OK):
            raise RuntimeError(f"Файл не исполняемый. Выполните: chmod +x \"{full}\"")
        cmd = [full]
    return subprocess.Popen(cmd + _split_args(args), cwd=cwd, start_new_session=True)


def kill_process_tree(proc, grace=3.0):
    """Завершает процесс и всех его потомков. Windows: taskkill /T.
    Linux: SIGTERM всей группе процессов, через `grace` секунд - SIGKILL."""
    if proc is None:
        return
    if IS_WINDOWS:
        subprocess.run(["taskkill", "/F", "/T", "/PID", str(proc.pid)],
                       capture_output=True, creationflags=NO_WINDOW_FLAGS)
        return
    try:
        pgid = os.getpgid(proc.pid)
    except OSError:
        pgid = None
    own_group = pgid is not None and pgid == proc.pid   # запущен через start_new_session
    try:
        if own_group:
            os.killpg(pgid, signal.SIGTERM)
        else:
            proc.terminate()
    except OSError:
        return

    def _force():
        try:
            if proc.poll() is None or own_group:
                if own_group:
                    os.killpg(pgid, signal.SIGKILL)
                else:
                    proc.kill()
        except OSError:
            pass
    t = threading.Timer(grace, _force)
    t.daemon = True
    t.start()


def open_path(path):
    """Открыть файл/папку средствами ОС (двойной клик в проводнике)."""
    if IS_WINDOWS:
        os.startfile(path)  # noqa: S606 - только Windows
    elif IS_MAC:
        subprocess.Popen(["open", path])
    else:
        subprocess.Popen(["xdg-open", path], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)


# --------------------------------------------------------------------- #
# Sunshine
# --------------------------------------------------------------------- #
def sunshine_binary(sunshine_dir):
    """Путь к исполняемому файлу Sunshine. Windows: <папка>/sunshine.exe.
    Linux: бинарник в папке, иначе `sunshine` из PATH (deb/AppImage/flatpak-обёртка)."""
    if IS_WINDOWS:
        return os.path.join(sunshine_dir, "sunshine.exe")
    local = os.path.join(sunshine_dir, "sunshine")
    if os.path.isfile(local):
        return local
    return shutil.which("sunshine") or local


def sunshine_apps_json(base_dir):
    """Где лежит apps.json. Windows: рядом с лаунчером (портативная копия Sunshine).
    Linux: ~/.config/sunshine - там его читает системный sunshine."""
    if IS_WINDOWS:
        return os.path.join(base_dir, "Sunshine", "config", "apps.json")
    return os.path.join(os.path.expanduser("~"), ".config", "sunshine", "apps.json")
