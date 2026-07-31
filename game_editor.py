import sys
import os
import json
import uuid
from PyQt6.QtWidgets import (QApplication, QDialog, QVBoxLayout, QLineEdit, 
                             QPushButton, QHBoxLayout, QLabel, QFileDialog, 
                             QCheckBox, QComboBox, QMessageBox)
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QPixmap

from style_loader import apply_global_style

class GameEditor(QDialog):
    def __init__(self, parent=None, game_data=None, groups=None, current_group=None):
        super().__init__(parent)
        self.data_file = "games_data.json"
        self.setWindowTitle("Настройка игры GOR")
        self.setObjectName("EditorDialog")
        self.setFixedWidth(600)
        
        # Загружаем структуру данных
        self.all_data = self.load_json()
        
        # Защита: собираем существующие группы из JSON, исключая повторение "Без группы"
        existing_groups = list(self.all_data.get("groups", {}).keys())
        self.groups = groups or [g for g in existing_groups if g != "Без группы"]
        
        # Безопасное сохранение оригинального имени/id для проверки при редактировании
        self.original_name = game_data['name'] if (game_data and 'name' in game_data) else None
        self.original_id = game_data.get('id') if game_data else None
        
        self.game_data = game_data or {
            "id": None, "name": "", "path": "", "root_path": "", "icon": "", 
            "group": "Без группы", "args": "", 
            "playtime_seconds": 0, "favorite": False
        }
        self.current_group = current_group or self.game_data.get("group", "Без группы")
        
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
        layout.addWidget(QLabel("Название мода/игры:"))
        self.name_edit = QLineEdit(self.game_data.get('name', ''))
        layout.addWidget(self.name_edit)

        # --- ПУТЬ К ФАЙЛУ ---
        layout.addWidget(QLabel("Файл запуска (любой тип файла):"))
        path_layout = QHBoxLayout()
        self.path_edit = QLineEdit(self.game_data.get('path', ''))
        self.path_btn = QPushButton("📁 Обзор")
        self.path_btn.clicked.connect(self.select_path)
        path_layout.addWidget(self.path_edit)
        path_layout.addWidget(self.path_btn)
        layout.addLayout(path_layout)

        # --- КОРНЕВАЯ ПАПКА ---
        layout.addWidget(QLabel("Корневая папка игры:"))
        root_path_layout = QHBoxLayout()
        self.root_path_edit = QLineEdit(self.game_data.get('root_path', ''))
        self.root_path_btn = QPushButton("📂 Папка")
        self.root_path_btn.clicked.connect(self.select_root_path)
        root_path_layout.addWidget(self.root_path_edit)
        root_path_layout.addWidget(self.root_path_btn)
        layout.addLayout(root_path_layout)

        # --- АРГУМЕНТЫ (выделены акцентной рамкой через objectName ArgsInput) ---
        layout.addWidget(QLabel("Аргументы запуска:"))
        self.args_edit = QLineEdit(self.game_data.get('args', ''))
        self.args_edit.setObjectName("ArgsInput")
        self.args_edit.setPlaceholderText("-game folder_name")
        layout.addWidget(self.args_edit)

        # --- ОБЛОЖКА ---
        layout.addWidget(QLabel("Обложка (PNG/JPG):"))
        icon_layout = QHBoxLayout()
        self.icon_edit = QLineEdit(self.game_data.get('icon', ''))
        self.icon_btn = QPushButton("🖼️ Фото")
        self.icon_btn.clicked.connect(self.select_icon)
        icon_layout.addWidget(self.icon_edit)
        icon_layout.addWidget(self.icon_btn)
        layout.addLayout(icon_layout)

        preview_box = QHBoxLayout()
        self.preview_label = QLabel("Нет фото")
        self.preview_label.setObjectName("PreviewLabel")
        self.preview_label.setFixedSize(200, 260)
        self.preview_label.setAlignment(Qt.AlignmentFlag.AlignCenter)

        self.fav_check = QCheckBox("⭐️ ДОБАВИТЬ В ИЗБРАННОЕ")
        self.fav_check.setObjectName("FavCheck")
        self.fav_check.setChecked(self.game_data.get('favorite', False))

        preview_box.addWidget(self.preview_label)
        preview_box.addWidget(self.fav_check)
        preview_box.addStretch()
        layout.addLayout(preview_box)
        
        if self.game_data.get('icon'): self.update_preview()

        # --- ВЫБОР ГРУППЫ ---
        layout.addWidget(QLabel("Назначить в группу:"))
        self.group_box = QComboBox()
        self.group_box.addItem("Без группы")
        self.group_box.addItems(self.groups)
        self.group_box.setCurrentText(self.current_group)
        layout.addWidget(self.group_box)

        # --- КНОПКИ ---
        btns = QHBoxLayout()
        save_btn = QPushButton("СОХРАНИТЬ")
        save_btn.clicked.connect(self.save_and_accept)

        cancel_btn = QPushButton("ОТМЕНА")
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
            QMessageBox.warning(self, "Ошибка", "Название игры не может быть пустым!")
            return

        if self.name_exists(name, exclude_id=self.original_id):
            QMessageBox.warning(self, "Ошибка", "Игра с таким именем уже существует!")
            return

        if self.original_name:
            lst, idx = self._find_entry(self.original_name, self.original_id)
            if lst is not None:
                lst.pop(idx)

        new_data = self.get_data()
        target_group = new_data.pop('group')
        
        if target_group == "Без группы":
            self.all_data["standalone"].append(new_data)
        else:
            if target_group not in self.all_data["groups"]:
                self.all_data["groups"][target_group] = []
            self.all_data["groups"][target_group].append(new_data)
        
        self.save_json(self.all_data)
        self.accept()

    def select_path(self):
        file, _ = QFileDialog.getOpenFileName(self, "Выбрать файл запуска", "", "Все файлы (*.*)")
        if file: self.path_edit.setText(file)

    def select_root_path(self):
        folder = QFileDialog.getExistingDirectory(self, "Выбрать корневую папку игры")
        if folder: self.root_path_edit.setText(folder)

    def select_icon(self):
        file, _ = QFileDialog.getOpenFileName(self, "Выбрать обложку", "", "Images (*.png *.jpg *.jpeg)")
        if file: 
            self.icon_edit.setText(file)
            self.update_preview()

    def update_preview(self):
        path = self.icon_edit.text()
        if os.path.exists(path):
            pix = QPixmap(path)
            self.preview_label.setPixmap(pix.scaled(200, 260, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation))
        else:
            self.preview_label.setText("Файл не найден")

    def get_data(self):
        data = {
            "id": self.original_id or str(uuid.uuid4()),
            "name": self.name_edit.text(), 
            "path": self.path_edit.text(), 
            "root_path": self.root_path_edit.text(),
            "icon": self.icon_edit.text(), 
            "group": self.group_box.currentText(),
            "args": self.args_edit.text(),
            "favorite": self.fav_check.isChecked()
        }
        data['playtime_seconds'] = self.game_data.get('playtime_seconds', 0)
        return data

if __name__ == "__main__":
    app = QApplication(sys.argv)
    app.setStyle("Fusion")
    apply_global_style(app)
    
    found_game = None
    found_group = "Без группы"
    
    if len(sys.argv) > 1:
        search_name = sys.argv[1]
        search_group = sys.argv[2] if len(sys.argv) > 2 else "Без группы"
        search_id = sys.argv[3] if len(sys.argv) > 3 and sys.argv[3] else None
        
        dummy = GameEditor(game_data=None)
        
        if search_group == "Без группы" or search_group == "БЕЗ ГРУППЫ":
            candidates = dummy.all_data.get("standalone", [])
            target_group_name = "Без группы"
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