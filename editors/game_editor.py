import os
import sys
_THIS_DIR = os.path.dirname(os.path.abspath(__file__))
_PROJECT_ROOT = _THIS_DIR if os.path.exists(os.path.join(_THIS_DIR, "bridge_loader.py")) else os.path.dirname(_THIS_DIR)
for _sub in ("core", "shared", "editors", "remote", "addons_sys", "extras"):
    _p = os.path.join(_PROJECT_ROOT, _sub)
    if _p not in sys.path:
        sys.path.insert(0, _p)

import sys
import os
import json
import uuid
import base64
from PyQt6.QtWidgets import (QApplication, QDialog, QVBoxLayout, QLineEdit, 
                             QPushButton, QHBoxLayout, QLabel, QFileDialog, 
                             QCheckBox, QComboBox, QMessageBox)
from PyQt6.QtCore import Qt, QUrl
from PyQt6.QtGui import QPixmap, QIcon
from PyQt6.QtWebEngineWidgets import QWebEngineView
from PyQt6.QtWebEngineCore import QWebEngineContextMenuRequest
from PyQt6.QtNetwork import QNetworkAccessManager, QNetworkRequest, QLocalSocket

from style_loader import apply_global_style
from lang_loader import tr
from cover_ipc import IPC_SERVER_NAME, encode_message, try_decode_line

# Папка, куда сохраняются обложки, "пойманные" из встроенного браузера
# (см. ImagePickerDialog ниже). Лежит рядом с games_data.json, как и сами
# исходные обложки, добавленные вручную через "Обзор".
COVERS_DIR = "covers"


class _PickerView(QWebEngineView):
    """WebView в режиме выбора обложки.

    ВАЖНО: обычные клики по картинкам НЕ перехватываются - страница ведёт
    себя как в любом другом браузере (можно открыть картинку по ссылке,
    перейти дальше и т.п.). Выбор обложки происходит только через ПРАВЫЙ
    клик: в стандартное контекстное меню Chromium (со всеми его обычными
    пунктами - "Сохранить картинку как", "Копировать" и т.д.) добавляется
    один дополнительный пункт "Использовать как обложку игры", который
    появляется, только если клик пришёлся именно на <img>."""

    def __init__(self, on_image_picked, parent=None):
        super().__init__(parent)
        self._on_image_picked = on_image_picked

    def contextMenuEvent(self, event):
        request = self.lastContextMenuRequest()
        menu = self.createStandardContextMenu()

        if (request.mediaType() == QWebEngineContextMenuRequest.MediaType.MediaTypeImage
                and not request.mediaUrl().isEmpty()):
            media_url = request.mediaUrl().toString()
            menu.addSeparator()
            cover_act = menu.addAction(tr("game_editor.picker_use_as_cover"))
            cover_act.triggered.connect(lambda: self._on_image_picked(media_url))

        menu.exec(event.globalPos())


class ImagePickerDialog(QDialog):
    """Встроенный браузер в 'режиме выбора обложки': пользователь ищет
    картинку как обычно (поиск, любой сайт), а клик по любому изображению
    на странице сразу скачивает его и закрывает диалог с готовым путём
    к файлу - без ручного сохранения на диск и открытия проводника."""

    def __init__(self, parent=None, initial_query=""):
        super().__init__(parent)
        self.setWindowTitle(tr("game_editor.picker_title"))
        self.resize(1000, 720)
        self.picked_path = None
        self._network = QNetworkAccessManager(self)

        layout = QVBoxLayout(self)

        hint = QLabel(tr("game_editor.picker_hint"))
        hint.setWordWrap(True)
        layout.addWidget(hint)

        nav_layout = QHBoxLayout()
        self.url_edit = QLineEdit()
        self.go_btn = QPushButton(tr("game_editor.picker_go"))
        self.go_btn.clicked.connect(self._navigate)
        self.url_edit.returnPressed.connect(self._navigate)
        nav_layout.addWidget(self.url_edit)
        nav_layout.addWidget(self.go_btn)
        layout.addLayout(nav_layout)

        self.view = _PickerView(self._on_image_picked)
        layout.addWidget(self.view)

        self.status_lbl = QLabel("")
        layout.addWidget(self.status_lbl)

        start_query = initial_query.strip() or "обложка игры"
        self.url_edit.setText(f"https://www.google.com/search?tbm=isch&q={start_query}")
        self._navigate()

    def _navigate(self):
        text = self.url_edit.text().strip()
        if not text:
            return
        if "://" not in text:
            text = f"https://www.google.com/search?tbm=isch&q={text}"
        self.view.setUrl(QUrl(text))

    def _on_image_picked(self, img_url):
        self.status_lbl.setText(tr("game_editor.picker_downloading"))
        self.go_btn.setEnabled(False)

        if img_url.startswith("data:"):
            # Превью в поиске картинок иногда сразу приходят как data:URL -
            # тогда сеть не нужна, декодируем base64 напрямую.
            try:
                header, b64data = img_url.split(",", 1)
                ext = "png"
                if "image/jpeg" in header or "image/jpg" in header:
                    ext = "jpg"
                elif "image/webp" in header:
                    ext = "webp"
                raw = base64.b64decode(b64data)
                self._save_and_close(raw, ext)
            except Exception as e:
                self._fail(str(e))
            return

        qurl = QUrl(img_url)
        req = QNetworkRequest(qurl)
        reply = self._network.get(req)
        reply.finished.connect(lambda: self._on_download_finished(reply, qurl))

    def _on_download_finished(self, reply, qurl):
        from PyQt6.QtNetwork import QNetworkReply
        if reply.error() != QNetworkReply.NetworkError.NoError:
            self._fail(reply.errorString())
            reply.deleteLater()
            return
        raw = bytes(reply.readAll())
        reply.deleteLater()
        ext = os.path.splitext(qurl.path())[1].lstrip(".").split("?")[0][:4] or "jpg"
        if ext.lower() not in ("jpg", "jpeg", "png", "webp", "gif", "bmp"):
            ext = "jpg"
        self._save_and_close(raw, ext)

    def _save_and_close(self, raw_bytes, ext):
        try:
            os.makedirs(COVERS_DIR, exist_ok=True)
            filename = f"{uuid.uuid4().hex}.{ext}"
            full_path = os.path.join(COVERS_DIR, filename)
            with open(full_path, "wb") as f:
                f.write(raw_bytes)
            self.picked_path = full_path
            self.accept()
        except Exception as e:
            self._fail(str(e))

    def _fail(self, message):
        self.status_lbl.setText(tr("game_editor.picker_download_error", error=message))
        self.go_btn.setEnabled(True)

NO_GROUP_KEY = "Без группы"  # внутренний ключ данных - НЕ переводится

class GameEditor(QDialog):
    def __init__(self, parent=None, game_data=None, groups=None, current_group=None):
        super().__init__(parent)
        self.data_file = "games_data.json"
        self.setWindowTitle(tr("game_editor.title"))
        self.setObjectName("EditorDialog")
        self.setFixedWidth(600)
        self._cover_ipc_socket = None   # см. select_icon_from_browser()
        
        # Загружаем структуру данных
        self.all_data = self.load_json()
        
        # Защита: собираем существующие группы из JSON, исключая повторение "Без группы"
        existing_groups = list(self.all_data.get("groups", {}).keys())
        self.groups = groups or [g for g in existing_groups if g != NO_GROUP_KEY]
        
        # Безопасное сохранение оригинального имени/id для проверки при редактировании
        self.original_name = game_data['name'] if (game_data and 'name' in game_data) else None
        self.original_id = game_data.get('id') if game_data else None
        
        self.game_data = game_data or {
            "id": None, "name": "", "path": "", "root_path": "", "icon": "", 
            "group": NO_GROUP_KEY, "args": "", 
            "playtime_seconds": 0, "favorite": False
        }
        self.current_group = current_group or self.game_data.get("group", NO_GROUP_KEY)
        
        self.init_ui()

    def load_json(self):
        if not os.path.exists(self.data_file):
            default_data = {"groups": {}, "standalone": [], "history": []}
            with open(self.data_file, 'w', encoding='utf-8') as f:
                json.dump(default_data, f, indent=4)
            return default_data
        with open(self.data_file, 'r', encoding='utf-8') as f:
            try:
                data = json.load(f)
                if "groups" not in data: data["groups"] = {}
                if "standalone" not in data: data["standalone"] = []
                return data
            except:
                return {"groups": {}, "standalone": [], "history": []}

    def save_json(self, data):
        with open(self.data_file, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=4)

    def init_ui(self):
        # Оформление диалога (тема #EditorDialog) берётся из общего
        # style.qss - см. style_loader.py, применяется глобально к
        # QApplication в блоке __main__.
        layout = QVBoxLayout(self)

        # --- НАЗВАНИЕ ---
        layout.addWidget(QLabel(tr("game_editor.name_label")))
        self.name_edit = QLineEdit(self.game_data.get('name', ''))
        layout.addWidget(self.name_edit)

        # --- ПУТЬ К ФАЙЛУ ---
        layout.addWidget(QLabel(tr("game_editor.path_label")))
        path_layout = QHBoxLayout()
        self.path_edit = QLineEdit(self.game_data.get('path', ''))
        self.path_btn = QPushButton(tr("common.browse"))
        self.path_btn.clicked.connect(self.select_path)
        path_layout.addWidget(self.path_edit)
        path_layout.addWidget(self.path_btn)
        layout.addLayout(path_layout)

        # --- КОРНЕВАЯ ПАПКА ---
        layout.addWidget(QLabel(tr("game_editor.root_label")))
        root_path_layout = QHBoxLayout()
        self.root_path_edit = QLineEdit(self.game_data.get('root_path', ''))
        self.root_path_btn = QPushButton(tr("game_editor.root_btn"))
        self.root_path_btn.clicked.connect(self.select_root_path)
        root_path_layout.addWidget(self.root_path_edit)
        root_path_layout.addWidget(self.root_path_btn)
        layout.addLayout(root_path_layout)

        # --- АРГУМЕНТЫ (выделены акцентной рамкой через objectName ArgsInput) ---
        layout.addWidget(QLabel(tr("game_editor.args_label")))
        self.args_edit = QLineEdit(self.game_data.get('args', ''))
        self.args_edit.setObjectName("ArgsInput")
        self.args_edit.setPlaceholderText(tr("game_editor.args_placeholder"))
        layout.addWidget(self.args_edit)

        # --- ОБЛОЖКА ---
        layout.addWidget(QLabel(tr("game_editor.icon_label")))
        icon_layout = QHBoxLayout()
        self.icon_edit = QLineEdit(self.game_data.get('icon', ''))
        self.icon_btn = QPushButton(tr("game_editor.icon_btn"))
        self.icon_btn.clicked.connect(self.select_icon)
        self.icon_browser_btn = QPushButton(tr("game_editor.icon_browser_btn"))
        self.icon_browser_btn.clicked.connect(self.select_icon_from_browser)
        icon_layout.addWidget(self.icon_edit)
        icon_layout.addWidget(self.icon_btn)
        icon_layout.addWidget(self.icon_browser_btn)
        layout.addLayout(icon_layout)

        self.icon_ipc_status_lbl = QLabel("")
        self.icon_ipc_status_lbl.setObjectName("IconIpcStatusLabel")
        self.icon_ipc_status_lbl.setWordWrap(True)
        self.icon_ipc_status_lbl.hide()
        layout.addWidget(self.icon_ipc_status_lbl)

        preview_box = QHBoxLayout()
        self.preview_label = QLabel(tr("game_editor.no_photo"))
        self.preview_label.setObjectName("PreviewLabel")
        self.preview_label.setFixedSize(200, 260)
        self.preview_label.setAlignment(Qt.AlignmentFlag.AlignCenter)

        self.fav_check = QCheckBox(tr("game_editor.favorite_check"))
        self.fav_check.setObjectName("FavCheck")
        self.fav_check.setChecked(self.game_data.get('favorite', False))

        preview_box.addWidget(self.preview_label)
        preview_box.addWidget(self.fav_check)
        preview_box.addStretch()
        layout.addLayout(preview_box)
        
        if self.game_data.get('icon'): self.update_preview()

        # --- ВЫБОР ГРУППЫ ---
        # Отображаемый текст переведён, но реальное значение ("Без группы")
        # хранится как userData, чтобы не ломать сохранённые games_data.json
        layout.addWidget(QLabel(tr("game_editor.group_label")))
        self.group_box = QComboBox()
        self.group_box.addItem(tr("common.no_group"), NO_GROUP_KEY)
        for g in self.groups:
            self.group_box.addItem(g, g)
        idx = self.group_box.findData(self.current_group)
        if idx == -1:
            idx = self.group_box.findText(self.current_group)
        if idx != -1:
            self.group_box.setCurrentIndex(idx)
        layout.addWidget(self.group_box)

        # --- КНОПКИ ---
        btns = QHBoxLayout()
        save_btn = QPushButton(tr("common.save"))
        save_btn.clicked.connect(self.save_and_accept)

        cancel_btn = QPushButton(tr("common.cancel"))
        cancel_btn.setObjectName("CancelBtn")
        cancel_btn.clicked.connect(self.reject)

        btns.addWidget(save_btn)
        btns.addWidget(cancel_btn)
        layout.addLayout(btns)

    def _find_entry(self, name, gid):
        """Ищет запись игры по id (приоритет) или по имени (для старых записей без id).
        Возвращает (list_ref, index) или (None, None)."""
        lists_to_check = [self.all_data["standalone"]] + list(self.all_data["groups"].values())
        if gid:
            for lst in lists_to_check:
                for i, g in enumerate(lst):
                    if g.get('id') == gid:
                        return lst, i
        for lst in lists_to_check:
            for i, g in enumerate(lst):
                if g.get('name') == name and not g.get('id'):
                    return lst, i
        return None, None

    def name_exists(self, name, exclude_id=None):
        """Проверяет, занято ли имя другой игрой (кроме редактируемой)."""
        all_games = self.all_data["standalone"][:]
        for g_list in self.all_data["groups"].values():
            all_games.extend(g_list)
        for g in all_games:
            if g.get('name') == name and g.get('id') != exclude_id:
                return True
        return False

    def save_and_accept(self):
        name = self.name_edit.text().strip()
        if not name:
            QMessageBox.warning(self, tr("common.error"), tr("game_editor.name_empty_error"))
            return

        if self.name_exists(name, exclude_id=self.original_id):
            QMessageBox.warning(self, tr("common.error"), tr("game_editor.name_exists_error"))
            return

        if self.original_name:
            lst, idx = self._find_entry(self.original_name, self.original_id)
            if lst is not None:
                lst.pop(idx)

        new_data = self.get_data()
        target_group = new_data.pop('group')
        
        if target_group == NO_GROUP_KEY:
            self.all_data["standalone"].append(new_data)
        else:
            if target_group not in self.all_data["groups"]:
                self.all_data["groups"][target_group] = []
            self.all_data["groups"][target_group].append(new_data)
        
        self.save_json(self.all_data)
        self.accept()

    def select_path(self):
        file, _ = QFileDialog.getOpenFileName(self, tr("game_editor.select_launch_file"), "", tr("common.all_files"))
        if file: self.path_edit.setText(file)

    def select_root_path(self):
        folder = QFileDialog.getExistingDirectory(self, tr("game_editor.select_root_folder"))
        if folder: self.root_path_edit.setText(folder)

    def select_icon(self):
        file, _ = QFileDialog.getOpenFileName(self, tr("game_editor.select_cover"), "", tr("common.images_filter"))
        if file: 
            self.icon_edit.setText(file)
            self.update_preview()

    def closeEvent(self, event):
        # Если редактор закрывают, пока висит незавершённый запрос "выбор
        # обложки" - обрываем соединение. Сервер (главный лаунчер) увидит
        # disconnected и сам закроет служебную вкладку браузера.
        self._cleanup_cover_ipc_socket()
        super().closeEvent(event)

    def select_icon_from_browser(self):
        """Просит ГЛАВНЫЙ процесс лаунчера (если он запущен) переключиться
        на вкладку "Браузер" и открыть там служебную вкладку выбора
        обложки - см. shared/cover_ipc.py. Если лаунчер почему-то
        недоступен (например, редактор запущен отдельно для отладки) -
        тихо откатываемся на старое отдельное окно ImagePickerDialog."""
        self._cover_ipc_buffer = b""
        socket = QLocalSocket(self)
        self._cover_ipc_socket = socket

        def _on_connected():
            query = self.name_edit.text().strip() or "обложка игры"
            socket.write(encode_message({"cmd": "pick_cover", "query": query}))
            socket.flush()
            self.icon_ipc_status_lbl.setText(tr("game_editor.picker_switch_hint"))
            self.icon_ipc_status_lbl.show()

        def _on_ready_read():
            self._cover_ipc_buffer += bytes(socket.readAll())
            while True:
                msg, rest = try_decode_line(self._cover_ipc_buffer)
                self._cover_ipc_buffer = rest
                if msg is None:
                    break
                self._on_cover_ipc_message(msg)

        def _on_error(_err=None):
            self._cleanup_cover_ipc_socket()
            self._open_legacy_image_picker()

        socket.connected.connect(_on_connected)
        socket.readyRead.connect(_on_ready_read)
        socket.errorOccurred.connect(_on_error)
        socket.connectToServer(IPC_SERVER_NAME)

    def _on_cover_ipc_message(self, msg):
        if "cover_path" in msg:
            self.icon_edit.setText(msg["cover_path"])
            self.update_preview()
            self.icon_ipc_status_lbl.hide()
            self._cleanup_cover_ipc_socket()
            self.raise_()
            self.activateWindow()
        elif "error" in msg:
            self.icon_ipc_status_lbl.hide()
            self._cleanup_cover_ipc_socket()
            QMessageBox.warning(self, tr("common.error"), tr("game_editor.picker_download_error", error=msg["error"]))

    def _cleanup_cover_ipc_socket(self):
        if self._cover_ipc_socket is not None:
            self._cover_ipc_socket.disconnectFromServer()
            self._cover_ipc_socket.deleteLater()
            self._cover_ipc_socket = None

    def _open_legacy_image_picker(self):
        """Запасной вариант, если главный лаунчер недоступен по IPC:
        собственное отдельное окно браузера, как раньше."""
        self.icon_ipc_status_lbl.hide()
        dialog = ImagePickerDialog(self, initial_query=self.name_edit.text())
        if dialog.exec() and dialog.picked_path:
            self.icon_edit.setText(dialog.picked_path)
            self.update_preview()

    def update_preview(self):
        path = self.icon_edit.text()
        if os.path.exists(path):
            pix = QPixmap(path)
            self.preview_label.setPixmap(pix.scaled(200, 260, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation))
        else:
            self.preview_label.setText(tr("game_editor.file_not_found"))

    def get_data(self):
        data = {
            "id": self.original_id or str(uuid.uuid4()),
            "name": self.name_edit.text(), 
            "path": self.path_edit.text(), 
            "root_path": self.root_path_edit.text(),
            "icon": self.icon_edit.text(), 
            "group": self.group_box.currentData() if self.group_box.currentData() is not None else self.group_box.currentText(),
            "args": self.args_edit.text(),
            "favorite": self.fav_check.isChecked()
        }
        data['playtime_seconds'] = self.game_data.get('playtime_seconds', 0)
        return data

if __name__ == "__main__":
    app = QApplication(sys.argv)
    app.setStyle("Fusion")
    app.setWindowIcon(QIcon(os.path.join(os.path.dirname(os.path.abspath(__file__)), "favicon.ico")))
    apply_global_style(app)
    
    found_game = None
    found_group = NO_GROUP_KEY
    
    if len(sys.argv) > 1:
        search_name = sys.argv[1]
        search_group = sys.argv[2] if len(sys.argv) > 2 else NO_GROUP_KEY
        search_id = sys.argv[3] if len(sys.argv) > 3 and sys.argv[3] else None
        
        dummy = GameEditor(game_data=None)
        
        if search_group == NO_GROUP_KEY or search_group == "БЕЗ ГРУППЫ":
            candidates = dummy.all_data.get("standalone", [])
            target_group_name = NO_GROUP_KEY
        else:
            candidates = dummy.all_data.get("groups", {}).get(search_group, [])
            target_group_name = search_group

        # Сначала пытаемся найти по id (надёжно даже при совпадающих именах),
        # и только если id не передали (старый вызов) - по имени.
        if search_id:
            for g in candidates:
                if g.get("id") == search_id:
                    found_game = g
                    found_group = target_group_name
                    break
        if found_game is None:
            for g in candidates:
                if g["name"] == search_name:
                    found_game = g
                    found_group = target_group_name
                    break
                        
    editor = GameEditor(game_data=found_game, current_group=found_group)
    editor.show()
    sys.exit(app.exec())