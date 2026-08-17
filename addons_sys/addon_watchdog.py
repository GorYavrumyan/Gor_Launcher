"""
Автоматическое наблюдение за тем, что делают аддоны.

ГЛАВНАЯ ИДЕЯ: логирование НЕ должно зависеть от того, захочет ли автор
аддона сам о себе что-то написать - иначе вредоносный или просто
небрежно написанный аддон будет молчать. Поэтому здесь не "аддон сам
докладывает", а лаунчер САМ перехватывает ключевые системные функции
(запись файлов, запуск процессов, сетевые подключения, создание новых
вкладок в интерфейсе) один раз при старте - и дальше видит ЛЮБОЙ вызов
этих функций из кода ЛЮБОГО аддона, что бы автор аддона по этому поводу
ни думал.

Как это работает технически:
1. install() один раз подменяет (monkey-patch) несколько системных
   функций/методов на свои обёртки.
2. Обёртка сначала честно делает то же самое, что делала бы настоящая
   функция (поведение аддона не меняется и не ломается).
3. Затем обёртка смотрит вверх по стеку вызовов (inspect.stack()) и
   ищет файл, который физически лежит внутри папки addons/<name>/ -
   это и есть код аддона, который сделал вызов.
4. Если такой файл найден - событие автоматически пишется в
   activity.json ИМЕННО ЭТОГО аддона через addon_logger, без единой
   строчки кода со стороны автора аддона.

ЧЕСТНО О ГРАНИЦАХ ЭТОГО ПОДХОДА:
Это перехват на уровне Python API, а не полноценная ОС-песочница.
Технически подготовленный злоумышленник в принципе может попытаться
обойти это (например, вызвать нужную функцию через ctypes или другой
низкоуровневый путь в обход Python-обёрток ниже). Но для абсолютного
большинства аддонов - включая случайно или намеренно вредоносные,
написанные на обычном Python без специального обхода - это даёт
реальную, невыключаемую видимость происходящего.
"""

import os
import sys
import builtins
import subprocess
import socket

from addon_logger import log_activity_for_addon

_addons_dir = None
_patched = False


# --------------------------------------------------------------------- #
# Определяем, из кода какого аддона (если вообще из аддона) пришёл вызов
# --------------------------------------------------------------------- #
# Определяем, из кода какого аддона (если вообще из аддона) пришёл вызов.
#
# ВАЖНО: используем sys._getframe()/frame.f_back вручную, а НЕ
# inspect.stack() - inspect.stack() для КАЖДОГО кадра стека читает и
# кэширует содержимое исходного файла с диска (чтобы дать "контекст
# строки кода"), который нам тут вообще не нужен. На стеке даже средней
# глубины это стоит по несколько миллисекунд, а если вызывается часто -
# счёт идёт на секунды (именно так лаунчер и тормозил).
# --------------------------------------------------------------------- #
def _addon_root_for_current_call():
    if not _addons_dir:
        return None
    frame = sys._getframe(1) if hasattr(sys, "_getframe") else None
    try:
        while frame is not None:
            filename = os.path.abspath(frame.f_code.co_filename)
            if filename.startswith(_addons_dir + os.sep):
                rel = os.path.relpath(filename, _addons_dir)
                folder = rel.split(os.sep)[0]
                return os.path.join(_addons_dir, folder)
            frame = frame.f_back
    except Exception:
        pass
    finally:
        del frame  # рвём ссылку на кадры стека, чтобы не мешать сборщику мусора
    return None


# Защита от рекурсии: запись лога сама делает open() на запись, а это
# ровно то, что мы перехватываем. Без этой защиты получается "лог
# логирует сам себя" до бесконечности (точнее, до предела глубины
# рекурсии Python) - именно это и грузило CPU на 8+ секунд.
_logging_in_progress = False


def _log_if_from_addon(msg_type, message):
    global _logging_in_progress
    if _logging_in_progress:
        return
    addon_root = _addon_root_for_current_call()
    if not addon_root:
        return
    _logging_in_progress = True
    try:
        log_activity_for_addon(addon_root, msg_type, message)
    finally:
        _logging_in_progress = False


# --------------------------------------------------------------------- #
# open() на запись/добавление/эксклюзив - "аддон записал файл"
# --------------------------------------------------------------------- #
_real_open = builtins.open


def _watched_open(file, mode="r", *args, **kwargs):
    result = _real_open(file, mode, *args, **kwargs)
    if isinstance(mode, str) and any(c in mode for c in ("w", "a", "x", "+")):
        _log_if_from_addon("change", f"Запись в файл: {file}")
    return result


# --------------------------------------------------------------------- #
# subprocess.Popen(...) - "аддон запустил процесс"
# --------------------------------------------------------------------- #
_real_popen_init = subprocess.Popen.__init__


def _watched_popen_init(self, args, *a, **kw):
    try:
        cmd = args if isinstance(args, str) else " ".join(str(x) for x in args)
    except Exception:
        cmd = str(args)
    _log_if_from_addon("request", f"Запуск процесса: {cmd}")
    return _real_popen_init(self, args, *a, **kw)


# --------------------------------------------------------------------- #
# socket.connect(...) - "аддон открыл сетевое соединение"
# (через это же в итоге идут requests/urllib/http.client)
# --------------------------------------------------------------------- #
_real_socket_connect = socket.socket.connect


def _watched_socket_connect(self, address, *a, **kw):
    _log_if_from_addon("request", f"Сетевое подключение: {address}")
    return _real_socket_connect(self, address, *a, **kw)


# --------------------------------------------------------------------- #
# QTabWidget.addTab(...) - "аддон добавил вкладку в интерфейс лаунчера"
# --------------------------------------------------------------------- #
def _patch_qt_widgets():
    try:
        from PyQt6.QtWidgets import QTabWidget
    except Exception:
        return

    real_add_tab = QTabWidget.addTab

    def _watched_add_tab(self, widget, *args, **kwargs):
        idx = real_add_tab(self, widget, *args, **kwargs)
        label = args[0] if args else kwargs.get("label", "")
        _log_if_from_addon("change", f"Создана новая вкладка интерфейса: {label}")
        return idx

    QTabWidget.addTab = _watched_add_tab


# --------------------------------------------------------------------- #
# Точка входа - вызывается ОДИН РАЗ при старте лаунчера, до load_addons()
# --------------------------------------------------------------------- #
def install(addons_dir):
    global _addons_dir, _patched
    if _patched:
        return
    _addons_dir = os.path.abspath(addons_dir)

    builtins.open = _watched_open
    subprocess.Popen.__init__ = _watched_popen_init
    socket.socket.connect = _watched_socket_connect
    _patch_qt_widgets()

    _patched = True