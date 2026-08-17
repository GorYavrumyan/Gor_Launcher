import os
import sys
_THIS_DIR = os.path.dirname(os.path.abspath(__file__))
_PROJECT_ROOT = _THIS_DIR if os.path.exists(os.path.join(_THIS_DIR, "bridge_loader.py")) else os.path.dirname(_THIS_DIR)
for _sub in ("core", "shared", "editors", "remote", "addons_sys", "extras"):
    _p = os.path.join(_PROJECT_ROOT, _sub)
    if _p not in sys.path:
        sys.path.insert(0, _p)

import sys
import json
import os
from PyQt6.QtWidgets import (QApplication, QDialog, QVBoxLayout, QLineEdit, 
                             QPushButton, QLabel, QMessageBox, QHBoxLayout)
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QIcon

from style_loader import apply_global_style
from lang_loader import tr

class GroupEditor(QDialog):
    # Добавили аргумент old_name=None, чтобы редактор понимал режим работы
    def __init__(self, parent=None, old_name=None):
        super().__init__(parent)
        self.old_name = old_name
        self.data_file = "games_data.json"
        
        # Определяем режим работы и заголовок
        if self.old_name:
            self.setWindowTitle(tr("group_editor.title_edit"))
        else:
            self.setWindowTitle(tr("group_editor.title_create"))

        self.setObjectName("EditorDialog")
        self.setFixedWidth(400)
        # Оформление (тема #EditorDialog) берётся из общего style.qss,
        # применяется глобально к QApplication в блоке __main__.

        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(15)
        
        # Заголовок
        self.lbl = QLabel(tr("group_editor.label"))
        self.lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self.lbl)
        
        self.name_edit = QLineEdit()
        self.name_edit.setPlaceholderText(tr("group_editor.placeholder"))
        
        # Если редактируем - вставляем текущее имя
        if self.old_name:
            self.name_edit.setText(self.old_name)
            
        layout.addWidget(self.name_edit)
        
        # Кнопки
        btn_layout = QHBoxLayout()
        self.save_btn = QPushButton(tr("common.save"))
        self.save_btn.clicked.connect(self.save_group)
        cancel_btn = QPushButton(tr("common.cancel"))
        cancel_btn.setObjectName("CancelBtn")
        cancel_btn.clicked.connect(self.reject)
        
        btn_layout.addWidget(self.save_btn)
        btn_layout.addWidget(cancel_btn)
        layout.addLayout(btn_layout)

    def save_group(self):
        name = self.name_edit.text().strip()
        if not name: 
            QMessageBox.warning(self, tr("common.error"), tr("group_editor.name_empty_error"))
            return

        if os.path.exists(self.data_file):
            with open(self.data_file, 'r', encoding='utf-8') as f:
                try:
                    data = json.load(f)
                except:
                    data = {"groups": {}, "standalone": [], "history": []}
        else:
            data = {"groups": {}, "standalone": [], "history": []}

        # --- ИСПРАВЛЕННАЯ ЛОГИКА СОХРАНЕНИЯ (СОХРАНЯЕМ ПОРЯДОК) ---
        if self.old_name:
            # Режим редактирования
            if name != self.old_name:
                if name in data["groups"]:
                    QMessageBox.warning(self, tr("common.error"), tr("group_editor.name_exists_edit_error"))
                    return
                
                # Создаем новый словарь, перенося ключи и сохраняя их очередность
                new_groups = {}
                for key, value in data["groups"].items():
                    if key == self.old_name:
                        new_groups[name] = value  # Вставляем новое имя на старое место
                    else:
                        new_groups[key] = value
                data["groups"] = new_groups
            # Если имя не изменилось, оставляем как есть
        else:
            # Режим создания
            if name in data["groups"]:
                QMessageBox.warning(self, tr("common.error"), tr("group_editor.name_exists_create_error"))
                return
            data["groups"][name] = []
        # -----------------------------------------------------------

        with open(self.data_file, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=4)
        
        self.accept()

if __name__ == "__main__":
    app = QApplication(sys.argv)
    app.setWindowIcon(QIcon(os.path.join(os.path.dirname(os.path.abspath(__file__)), "favicon.ico")))
    apply_global_style(app)

    # Обработка параметров запуска, переданных из консоли/лаунчера
    # Пример вызова через терминал: python group_editor.py "Имя_Группы"
    target_group = None
    if len(sys.argv) > 1:
        target_group = sys.argv[1]
        
    editor = GroupEditor(old_name=target_group)
    editor.show()
    sys.exit(app.exec())