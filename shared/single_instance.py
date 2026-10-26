"""
Защита от двойного запуска лаунчера + пересылка команды уже работающему экземпляру.

Зачем: два экземпляра одновременно пишут в один games_data.json и профиль браузера (гонка и потеря данных).
Особенно это важно для телевизора: Sunshine запускает приложение "GorLauncher Big Picture" командой
`bridge_loader.py --bigpicture`, а лаунчер на ПК к этому моменту обычно уже открыт.

Как работает:
  * основной экземпляр слушает локальный сокет (QLocalServer; имя зависит от папки проекта);
  * новый экземпляр сначала пытается подключиться: если получилось - отправляет команду и завершается;
      "show"        - показать окно основного экземпляра;
      "bigpicture"  - открыть в нём Big Picture. Новый процесс при этом НЕ завершается сразу, а ждёт,
                      пока основной экземпляр не закроет соединение (когда Big Picture закрыт). Это важно
                      для Sunshine: стрим живёт, пока жив запущенный им процесс.
  * флаг --new-instance отключает проверку (его добавляет перезапуск лаунчера: старый процесс ещё не успел выйти).
"""
import hashlib
import os

from PyQt6.QtCore import QObject, QTimer, pyqtSignal
from PyQt6.QtNetwork import QLocalServer, QLocalSocket


def server_name(project_root):
    key = os.path.abspath(project_root).lower().encode("utf-8")
    return "GorLauncher-" + hashlib.md5(key).hexdigest()[:12]


def forward_to_running(project_root, command, wait_for_close=False, connect_timeout_ms=800):
    """True - команда передана работающему экземпляру (текущий процесс должен завершиться)."""
    sock = QLocalSocket()
    sock.connectToServer(server_name(project_root))
    if not sock.waitForConnected(connect_timeout_ms):
        return False
    sock.write((command + "\n").encode("utf-8"))
    sock.flush()
    sock.waitForBytesWritten(1500)
    if wait_for_close:
        # блокируемся (без цикла событий), пока основной экземпляр не закроет соединение
        while sock.state() == QLocalSocket.LocalSocketState.ConnectedState:
            sock.waitForDisconnected(1000)
    else:
        sock.disconnectFromServer()
    return True


class SingleInstanceServer(QObject):
    """Слушает команды от повторных запусков. command(текст, сокет): сокет закрывает обработчик."""
    command = pyqtSignal(str, object)

    RETRY_MS, RETRY_TIMES = 500, 20

    def __init__(self, project_root, parent=None):
        super().__init__(parent)
        self._name = server_name(project_root)
        self._server = QLocalServer(self)
        self._server.newConnection.connect(self._on_connection)
        self._retries = 0
        self._timer = QTimer(self)
        self._timer.timeout.connect(self._retry)

    def listen(self):
        """Если имя занято (например, после перезапуска старый процесс ещё не вышел) - пробуем ещё
        несколько секунд в фоне."""
        if self._try_listen():
            return True
        self._timer.start(self.RETRY_MS)
        return False

    def _try_listen(self):
        QLocalServer.removeServer(self._name)   # на Unix убирает файл от упавшего процесса; на Windows ничего не делает
        return self._server.listen(self._name)

    def _retry(self):
        self._retries += 1
        if self._try_listen() or self._retries >= self.RETRY_TIMES:
            self._timer.stop()

    @property
    def listening(self):
        return self._server.isListening()

    def close(self):
        self._timer.stop()
        self._server.close()

    def _on_connection(self):
        while self._server.hasPendingConnections():
            sock = self._server.nextPendingConnection()
            sock.readyRead.connect(lambda s=sock: self._read(s))
            if sock.bytesAvailable():
                self._read(sock)

    def _read(self, sock):
        while sock.canReadLine():
            line = bytes(sock.readLine()).decode("utf-8", errors="replace").strip()
            if line:
                self.command.emit(line, sock)
