"""
browser_broadcast.py
----------------------
Real-Time LAN Broadcast (release notes v1.2): мгновенная отправка активной
вкладки или целой сохранённой группы на другие устройства в локальной сети
по UDP, без облаков и серверов - все копии GOR Browser в одной подсети
просто слушают один и тот же UDP-порт широковещательной рассылки.

Формат пакета (JSON, UTF-8, влезает в один UDP-датаграмм):
    {
        "app": "gor-browser",       # маркер "это наш пакет", отсекаем чужой UDP-шум
        "type": "tab" | "group",
        "name": "Заголовок вкладки" | "Название группы",
        "urls": ["https://..."],
        "sender": "DESKTOP-ABC123", # имя компьютера-отправителя (для UI)
    }

GorBroadcastService - единственный объект на GORBrowser:
    - start_listening()   - поднимает приёмный QUdpSocket на broadcast_port
    - send_tab(url, title)      - шлёт одну вкладку всем в сети
    - send_group(group)         - шлёт группу целиком
    - сигнал broadcast_received(dict) - приходят чужие пакеты, слушает
      GORBrowser и показывает всплывающее уведомление (см. BroadcastToast).
"""

import json
import os
import platform
import uuid

from PyQt6.QtCore import QObject, pyqtSignal
from PyQt6.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QFileDialog, QMessageBox
from PyQt6.QtGui import QColor

try:
    from PyQt6.QtNetwork import QUdpSocket, QHostAddress
    NETWORK_AVAILABLE = True
except Exception:
    # На случай сборки без модуля QtNetwork (в стандартной поставке PyQt6
    # он есть всегда, но перестраховка не помешает - фича молча выключается
    # вместо падения всего браузера).
    NETWORK_AVAILABLE = False

PROTOCOL_MARKER = "gor-browser"
MAX_GROUP_TABS_HINT = 10  # "5-10 вкладок" из release notes - не жёсткое ограничение, а ориентир UI


class GorBroadcastService(QObject):
    """Обёртка над парой UDP-сокетов (приём + отправка). Один экземпляр на
    GORBrowser, живёт всё время работы браузера."""

    broadcast_received = pyqtSignal(dict)

    def __init__(self, port=51888, parent=None):
        super().__init__(parent)
        self.port = port
        self._recv_socket = None
        self._send_socket = None
        # Уникальный id ЭТОГО запущенного процесса браузера - генерируется
        # заново при каждом старте. Раньше отсев "не показывать своё же
        # сообщение" делался по platform.node() (имя ПК), из-за чего ДВА
        # процесса GOR Browser на одной машине глушили друг друга - второй
        # просто никогда не видел пакеты первого. Теперь отсеиваем строго
        # по instance_id, так что LAN Broadcast работает и между двумя
        # процессами на одном ПК (для тестов/локальной отладки).
        self.instance_id = uuid.uuid4().hex
        if NETWORK_AVAILABLE:
            self._send_socket = QUdpSocket(self)

    def start_listening(self):
        """Поднимает приёмный сокет. Безопасно вызывать повторно (например,
        при смене порта в настройках) - предыдущий сокет закрывается."""
        if not NETWORK_AVAILABLE:
            return False
        if self._recv_socket is not None:
            self._recv_socket.close()
            self._recv_socket.deleteLater()
        self._recv_socket = QUdpSocket(self)
        bound = self._recv_socket.bind(
            QHostAddress.SpecialAddress.AnyIPv4, self.port,
            QUdpSocket.BindFlag.ShareAddress | QUdpSocket.BindFlag.ReuseAddressHint,
        )
        if bound:
            self._recv_socket.readyRead.connect(self._on_ready_read)
        return bound

    def stop_listening(self):
        if self._recv_socket is not None:
            self._recv_socket.close()

    def set_port(self, port):
        self.port = port
        self.start_listening()

    def _on_ready_read(self):
        while self._recv_socket.hasPendingDatagrams():
            datagram, _host, _port = self._recv_socket.readDatagram(self._recv_socket.pendingDatagramSize())
            try:
                data = json.loads(bytes(datagram).decode("utf-8"))
            except Exception:
                continue
            if not isinstance(data, dict) or data.get("app") != PROTOCOL_MARKER:
                continue
            # Не показываем уведомление о собственном же пакете (широковещание
            # приходит и отправителю тоже, если он слушает тот же порт).
            # Фильтр строго по instance_id этого процесса, а НЕ по имени ПК -
            # иначе второй процесс GOR Browser на том же компьютере тоже
            # считался бы "собой" и его пакеты молча отбрасывались бы.
            if data.get("instance_id") == self.instance_id:
                continue
            self.broadcast_received.emit(data)

    # ------------------------------------------------------------------

    def _send(self, payload: dict) -> bool:
        if not NETWORK_AVAILABLE or self._send_socket is None:
            return False
        payload = dict(payload)
        payload["app"] = PROTOCOL_MARKER
        payload.setdefault("sender", f"{platform.node()} (PID {os.getpid()})")
        # instance_id - см. __init__: позволяет получателю (в т.ч. второму
        # процессу GOR Browser на этом же ПК) корректно отличить "чужой"
        # пакет от "своего же эха", не полагаясь на имя компьютера.
        payload["instance_id"] = self.instance_id
        data = json.dumps(payload, ensure_ascii=False).encode("utf-8")

        sent_any = False
        # 1) Обычная широковещательная отправка - как и раньше, это основной
        #    путь доставки всем GOR Browser в локальной сети.
        written = self._send_socket.writeDatagram(data, QHostAddress.SpecialAddress.Broadcast, self.port)
        sent_any = sent_any or written != -1

        # 2) Явный дубль на loopback (127.0.0.1) - раньше отправка "самому
        #    себе" (два процесса на одном ПК, тесты, локальный IPC) не была
        #    гарантирована: далеко не везде и не всегда широковещательный
        #    пакет доставляется обратно на loopback-интерфейс (зависит от ОС,
        #    сетевых адаптеров и файрвола). Требование задачи - убрать эти
        #    ограничения и гарантировать работу "в том числе на одном и том
        #    же ПК" - поэтому дублируем пакет напрямую на 127.0.0.1, без
        #    какой-либо проверки/фильтрации по IP отправителя или получателя.
        written_local = self._send_socket.writeDatagram(data, QHostAddress.SpecialAddress.LocalHost, self.port)
        sent_any = sent_any or written_local != -1

        return sent_any

    def send_tab(self, url: str, title: str = "") -> bool:
        return self._send({"type": "tab", "name": title or url, "urls": [url]})

    def send_group(self, group: dict) -> bool:
        return self._send({
            "type": "group",
            "name": group.get("name", "Группа вкладок"),
            "urls": list(group.get("urls", [])),
        })

    def send_clipboard(self, text: str) -> bool:
        """Общий буфер обмена по LAN (пункт ТЗ) - рассылает текст всем
        GOR Browser в сети; см. GORBrowser._on_local_clipboard_changed /
        _handle_incoming_clipboard - работает только когда фича включена в
        настройках у ОБЕИХ сторон (по умолчанию выключена - это буфер
        обмена, там могут быть пароли/токены, включать нужно осознанно)."""
        return self._send({"type": "clipboard", "text": text})

    def send_bookmarks(self, bookmarks: list) -> bool:
        """Синхронизация закладок по LAN (пункт ТЗ) - рассылает ПОЛНЫЙ
        текущий список закладок; получатели добавляют себе те, которых у
        них ещё нет (merge по URL, см. _handle_incoming_bookmark_sync).
        Без центрального сервера/облака - просто "последний присланный
        снимок побеждает" для новых записей, существующие не трогаем."""
        return self._send({"type": "bookmark_sync", "bookmarks": list(bookmarks)})


class BroadcastToast(QWidget):
    """Компактное всплывающее уведомление о принятой вкладке/группе -
    "Быстрый приём" из release notes: кнопки «Открыть все» и «Сохранить в
    JSON», без модальных блокирующих диалогов поверх работы пользователя."""

    def __init__(self, parent_browser, payload: dict):
        super().__init__(parent_browser, Qt_WindowFlags(parent_browser))
        self.parent_browser = parent_browser
        self.payload = payload

        self.setObjectName("BroadcastToast")
        self.setFixedWidth(320)
        self.setStyleSheet(
            "#BroadcastToast { background: #1c1d21; border: 1px solid #383a40; border-radius: 10px; }"
            "QLabel { color: white; }"
            "QPushButton { background: #4c6ef5; color: white; padding: 6px 10px; border-radius: 6px; border: none; }"
            "QPushButton#Secondary { background: #2a2c31; }"
        )

        layout = QVBoxLayout(self)
        layout.setContentsMargins(14, 12, 14, 12)

        kind = "группу вкладок" if payload.get("type") == "group" else "вкладку"
        title = QLabel(f"📡 {payload.get('sender', 'Устройство в сети')} прислал(о) {kind}")
        title.setWordWrap(True)
        title.setStyleSheet("font-weight: 600;")
        layout.addWidget(title)

        name_label = QLabel(payload.get("name", ""))
        name_label.setWordWrap(True)
        name_label.setStyleSheet("color: #9aa0aa; font-size: 12px;")
        layout.addWidget(name_label)

        count = len(payload.get("urls", []))
        count_label = QLabel(f"{count} ссылок(a)")
        count_label.setStyleSheet("color: #9aa0aa; font-size: 11px;")
        layout.addWidget(count_label)

        btn_row = QHBoxLayout()
        btn_open = QPushButton("Открыть все")
        btn_open.clicked.connect(self.open_all)
        btn_save = QPushButton("Сохранить в JSON", objectName="Secondary")
        btn_save.clicked.connect(self.save_json)
        btn_dismiss = QPushButton("✕", objectName="Secondary")
        btn_dismiss.setFixedWidth(32)
        btn_dismiss.clicked.connect(self.close)
        btn_row.addWidget(btn_open)
        btn_row.addWidget(btn_save)
        btn_row.addWidget(btn_dismiss)
        layout.addLayout(btn_row)

        self.adjustSize()
        self._position_bottom_right()

    def _position_bottom_right(self):
        """Ставим тост в правый нижний угол окна браузера, поверх контента,
        не перекрывая тулбар/адресную строку."""
        try:
            geo = self.parent_browser.geometry()
            top_left = self.parent_browser.mapToGlobal(self.parent_browser.rect().bottomRight())
            x = top_left.x() - self.width() - 24
            y = top_left.y() - self.height() - 24
            self.move(max(x, 0), max(y, 0))
        except Exception:
            pass

    def open_all(self):
        for url in self.payload.get("urls", []):
            self.parent_browser.add_new_tab(_to_qurl(url), self.payload.get("name", "Из сети") [:15])
        self.close()

    def save_json(self):
        path, _ = QFileDialog.getSaveFileName(
            self, "Сохранить принятые вкладки", f"{self.payload.get('name', 'broadcast')}.json", "JSON (*.json)"
        )
        if path:
            with open(path, "w", encoding="utf-8") as f:
                json.dump(self.payload, f, ensure_ascii=False, indent=2)
            QMessageBox.information(self, "GOR Browser", "Сохранено.")
        self.close()


def _to_qurl(url_str):
    from PyQt6.QtCore import QUrl
    return QUrl(url_str)


def Qt_WindowFlags(parent_browser):
    """Небольшой хелпер, чтобы не тянуть Qt.WindowType в импорты модуля
    напрямую при статическом анализе - тост открывается как обычное дочернее
    окно поверх браузера (не диалог, чтобы не блокировать работу)."""
    from PyQt6.QtCore import Qt
    return Qt.WindowType.Tool | Qt.WindowType.FramelessWindowHint
