"""
Карточка одной записи истории игровых сессий (вкладка "История").
"""


import os
import sys
_THIS_DIR = os.path.dirname(os.path.abspath(__file__))
_PROJECT_ROOT = _THIS_DIR if os.path.exists(os.path.join(_THIS_DIR, "bridge_loader.py")) else os.path.dirname(_THIS_DIR)
for _sub in ("core", "shared", "editors", "remote", "addons_sys", "extras"):
    _p = os.path.join(_PROJECT_ROOT, _sub)
    if _p not in sys.path:
        sys.path.insert(0, _p)

from PyQt6.QtWidgets import QFrame, QVBoxLayout, QLabel, QMenu
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QAction

from launcher_utils import load_pixmap_cached
from lang_loader import tr


class HistoryCard(QFrame):
    def __init__(self, entry, index, parent_launcher):
        super().__init__()
        self.entry = entry
        self.index = index
        self.parent_launcher = parent_launcher
        self.setFixedSize(220, 380)
        self.setObjectName("HistoryCard")
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.customContextMenuRequested.connect(self.show_context_menu)
        self.init_ui()

    def init_ui(self):
        layout = QVBoxLayout(self)
        img = QLabel()
        img.setObjectName("HistoryCardImage")
        img.setFixedSize(190, 240)
        pix = load_pixmap_cached(self.entry.get('icon', ''))
        if pix.isNull():
            img.setText("🎮")
            img.setProperty("empty", True)
        else:
            img.setPixmap(pix.scaled(190, 240, Qt.AspectRatioMode.KeepAspectRatioByExpanding, Qt.TransformationMode.SmoothTransformation))
        img.setAlignment(Qt.AlignmentFlag.AlignCenter)

        name = QLabel(self.entry['name'])
        name.setObjectName("HistoryCardName")
        name.setAlignment(Qt.AlignmentFlag.AlignCenter)

        date_lbl = QLabel(tr("history_card.date_prefix", date=self.entry['date']))
        date_lbl.setObjectName("HistoryCardDate")

        dur = self.entry.get('session_time', 0)
        h, m = dur // 3600, (dur % 3600) // 60
        time_lbl = QLabel(tr("history_card.session_time", h=h, m=m))
        time_lbl.setObjectName("HistoryCardTime")

        layout.addWidget(img, alignment=Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(name)
        layout.addWidget(date_lbl)
        layout.addWidget(time_lbl)
        layout.addStretch()

    def show_context_menu(self, pos):
        menu = QMenu(self)
        del_act = QAction(tr("history_card.delete_entry"), self)
        del_act.triggered.connect(lambda: self.parent_launcher.delete_history_entry(self.index))
        menu.addAction(del_act)
        menu.exec(self.mapToGlobal(pos))

    def keyPressEvent(self, e):
        if e.key() == Qt.Key.Key_Delete:
            self.parent_launcher.delete_history_entry(self.index)
        elif e.key() in (Qt.Key.Key_Right, Qt.Key.Key_Down):
            self.focusNextChild()
        elif e.key() in (Qt.Key.Key_Left, Qt.Key.Key_Up):
            self.focusPreviousChild()
        else:
            super().keyPressEvent(e)
