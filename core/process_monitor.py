"""
Фоновые потоки-наблюдатели GorLauncher: слежение за запущенной игрой
(ProcessMonitor) и за окном редактора, пока оно открыто (EditorMonitor).

Вынесены из GorLauncher.py как самостоятельная пара классов - они не
зависят ни от GameCard, ни от GORLauncher, только от subprocess/tasklist.
"""

import subprocess
import time
import platform
import os

from PyQt6.QtCore import QThread, pyqtSignal

from launcher_utils import NO_WINDOW_FLAGS


class ProcessMonitor(QThread):
    """Ждёт завершения запущенной игры и сообщает итоговую длительность
    сессии. После того как основной процесс игры завершился, дополнительно
    ждёт, пока его имя пропадёт из списка процессов ОС - на случай, если
    игра сама себя перезапускает через launcher-обёртку."""
    finished_playing = pyqtSignal(int, dict)

    def __init__(self, process, start_time, game_data):
        super().__init__()
        self.process = process
        self.start_time = start_time
        self.game_data = game_data

    def _sleep(self, seconds):
        """Сон небольшими кусками, чтобы поток можно было остановить
        (requestInterruption) при закрытии лаунчера."""
        end = time.time() + seconds
        while time.time() < end:
            if self.isInterruptionRequested():
                return False
            time.sleep(0.25)
        return True

    def run(self):
        # Ждём основной процесс, но не блокируемся навсегда: опрашиваем,
        # чтобы поток можно было остановить при закрытии лаунчера.
        try:
            while self.process.poll() is None:
                if self.isInterruptionRequested():
                    return
                time.sleep(0.5)
        except Exception:
            pass
        # Момент последнего подтверждённого "игра жива": служебные паузы ниже
        # (2 с + опрос tasklist) в наигранное время не входят.
        last_alive = time.time()

        if not self._sleep(2):
            return
        target_name = os.path.basename(self.game_data.get('path', '')).lower()

        if target_name:
            while True:
                running = False
                try:
                    if platform.system() == 'Windows':
                        output = subprocess.check_output(
                            ['tasklist', '/FO', 'CSV', '/NH'], universal_newlines=True,
                            encoding='cp1251', errors='ignore', creationflags=NO_WINDOW_FLAGS
                        )
                        # Первое поле CSV - имя образа в кавычках. Сравниваем его
                        # ТОЧНО: раньше искали подстроку во всём выводе, и
                        # "launcher.exe" находился внутри "epicgameslauncher.exe" -
                        # сессия не заканчивалась никогда.
                        out_l = output.lower()
                        running = ('"' + target_name + '",') in out_l
                    else:
                        output = subprocess.check_output(['ps', '-e', '-o', 'comm='], universal_newlines=True, errors='ignore')
                        names = {line.strip().lower() for line in output.splitlines()}
                        running = target_name[:15] in names or target_name in names
                except Exception:
                    running = False

                if not running:
                    break
                last_alive = time.time()
                if not self._sleep(5):
                    return

        if self.isInterruptionRequested():
            return
        duration = max(0, int(last_alive - self.start_time))
        self.finished_playing.emit(duration, self.game_data)


class EditorMonitor(QThread):
    """Ждёт закрытия окна редактора (game_editor/group_editor/...),
    запущенного отдельным процессом, и сообщает об этом сигналом -
    по нему GORLauncher перечитывает games_data.json и обновляет список."""
    editor_closed = pyqtSignal()

    def __init__(self, process):
        super().__init__()
        self.process = process

    def run(self):
        if self.process:
            self.process.wait()
            self.editor_closed.emit()
