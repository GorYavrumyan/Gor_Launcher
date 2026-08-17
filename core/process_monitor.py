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

    def run(self):
        try:
            self.process.wait()
        except Exception:
            pass

        time.sleep(2)
        target_name = os.path.basename(self.game_data.get('path', '')).lower()

        if target_name:
            while True:
                running = False
                try:
                    if platform.system() == 'Windows':
                        output = subprocess.check_output(
                            ['tasklist', '/FO', 'CSV'], universal_newlines=True,
                            encoding='cp1251', errors='ignore', creationflags=NO_WINDOW_FLAGS
                        )
                        if target_name in output.lower():
                            running = True
                    else:
                        output = subprocess.check_output(['ps', '-e', '-o', 'comm='], universal_newlines=True, errors='ignore')
                        if target_name in output.lower():
                            running = True
                except Exception:
                    running = False

                if not running:
                    break
                time.sleep(5)

        duration = int(time.time() - self.start_time)
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
