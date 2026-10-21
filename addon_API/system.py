"""
api.system - операционная система: процессы, папки, буфер обмена, экраны.

    s = api.system
    s.run(["notepad.exe"])                                  # запустить программу
    s.run("dir", shell=True, on_done=lambda r: print(r.stdout))   # с результатом, без зависаний
    s.open("https://example.com");  s.open_folder(r"C:\\Games")
    s.clipboard_set("текст");  s.clipboard_get()
    s.is_running("steam.exe");  s.kill("notepad.exe");  s.processes()
    s.idle_seconds()      # сколько секунд пользователь ничего не нажимал (Windows)
"""

import os
import sys
import shutil
import platform
import subprocess


class RunResult:
    def __init__(self, returncode, stdout, stderr):
        self.returncode, self.stdout, self.stderr = returncode, stdout, stderr

    @property
    def ok(self):
        return self.returncode == 0

    def __repr__(self):
        return f"<RunResult code={self.returncode}>"


class SystemAPI:
    def __init__(self, api):
        self._api = api
        self.is_windows = platform.system() == "Windows"
        self.is_mac = platform.system() == "Darwin"
        self.is_linux = platform.system() == "Linux"

    def info(self):
        return {"os": platform.system(), "release": platform.release(), "machine": platform.machine(),
                "python": sys.version.split()[0], "user": os.environ.get("USERNAME") or os.environ.get("USER"),
                "cpu_count": os.cpu_count()}

    def env(self, name, default=None):
        return os.environ.get(name, default)

    def which(self, command):
        return shutil.which(command)

    # ----------------------------------------------------------- запуск
    def run(self, cmd, on_done=None, wait=False, cwd=None, shell=False, timeout=None):
        """Запустить команду (список или строка с shell=True).
        - on_done задан: выполняется в фоне, результат (RunResult) приходит в on_done;
        - wait=True: дождаться и вернуть RunResult (блокирует интерфейс!);
        - иначе: просто запустить и вернуть Popen."""
        kw = dict(cwd=cwd, shell=shell)
        if self.is_windows:
            kw["creationflags"] = getattr(subprocess, "CREATE_NO_WINDOW", 0)

        def blocking():
            p = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout,
                               errors="replace", **kw)
            return RunResult(p.returncode, p.stdout, p.stderr)

        if on_done is not None:
            self._api.background(blocking, on_done, lambda e: on_done(RunResult(-1, "", str(e))))
            return None
        if wait:
            return blocking()
        return subprocess.Popen(cmd, **kw)

    def open(self, target):
        """Открыть файл, папку или ссылку программой по умолчанию."""
        from PyQt6.QtGui import QDesktopServices
        from PyQt6.QtCore import QUrl
        url = QUrl(target) if "://" in str(target) else QUrl.fromLocalFile(str(target))
        return QDesktopServices.openUrl(url)

    def open_folder(self, path):
        folder = path if os.path.isdir(path) else os.path.dirname(path)
        return self.open(folder)

    # ----------------------------------------------------------- буфер обмена
    def clipboard_get(self):
        from PyQt6.QtWidgets import QApplication
        return QApplication.clipboard().text()

    def clipboard_set(self, text):
        from PyQt6.QtWidgets import QApplication
        QApplication.clipboard().setText(str(text))

    # ----------------------------------------------------------- экраны
    def screens(self):
        from PyQt6.QtGui import QGuiApplication
        out = []
        for s in QGuiApplication.screens():
            g = s.geometry()
            out.append({"name": s.name(), "width": g.width(), "height": g.height(),
                        "x": g.x(), "y": g.y(), "dpi": s.logicalDotsPerInch(),
                        "scale": s.devicePixelRatio(), "primary": s is QGuiApplication.primaryScreen()})
        return out

    # ----------------------------------------------------------- процессы
    def processes(self):
        """[{'pid': .., 'name': ..}] - через psutil, если он есть, иначе tasklist/ps."""
        try:
            import psutil
            return [{"pid": p.info["pid"], "name": p.info["name"] or ""}
                    for p in psutil.process_iter(["pid", "name"])]
        except ImportError:
            pass
        out = []
        try:
            if self.is_windows:
                txt = subprocess.run(["tasklist", "/FO", "CSV", "/NH"], capture_output=True, text=True,
                                     errors="replace", creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0)).stdout
                import csv
                for row in csv.reader(txt.splitlines()):
                    if len(row) >= 2 and row[1].isdigit():
                        out.append({"pid": int(row[1]), "name": row[0]})
            else:
                txt = subprocess.run(["ps", "-eo", "pid=,comm="], capture_output=True, text=True).stdout
                for line in txt.splitlines():
                    pid, _, name = line.strip().partition(" ")
                    if pid.isdigit():
                        out.append({"pid": int(pid), "name": name.strip()})
        except Exception:
            pass
        return out

    def is_running(self, name):
        low = name.lower()
        return any(p["name"].lower() == low for p in self.processes())

    def kill(self, pid_or_name):
        """Завершить процесс по pid или по имени. Возвращает число завершённых."""
        pids = [pid_or_name] if isinstance(pid_or_name, int) else \
            [p["pid"] for p in self.processes() if p["name"].lower() == str(pid_or_name).lower()]
        n = 0
        for pid in pids:
            try:
                if self.is_windows:
                    subprocess.run(["taskkill", "/F", "/PID", str(pid)], capture_output=True,
                                   creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
                else:
                    os.kill(pid, 15)
                n += 1
            except Exception:
                pass
        return n

    def idle_seconds(self):
        """Секунды без ввода пользователя (только Windows, иначе None)."""
        if not self.is_windows:
            return None
        try:
            import ctypes

            class LASTINPUTINFO(ctypes.Structure):
                _fields_ = [("cbSize", ctypes.c_uint), ("dwTime", ctypes.c_uint)]
            info = LASTINPUTINFO()
            info.cbSize = ctypes.sizeof(info)
            ctypes.windll.user32.GetLastInputInfo(ctypes.byref(info))
            return (ctypes.windll.kernel32.GetTickCount() - info.dwTime) / 1000.0
        except Exception:
            return None

    def beep(self):
        from PyQt6.QtWidgets import QApplication
        QApplication.beep()
