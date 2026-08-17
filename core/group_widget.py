"""
Контейнер группы игр в библиотеке: заголовок со сворачиванием, сетка
карточек игр, drag-n-drop приём игр из других групп.
"""


import os
import sys
_THIS_DIR = os.path.dirname(os.path.abspath(__file__))
_PROJECT_ROOT = _THIS_DIR if os.path.exists(os.path.join(_THIS_DIR, "bridge_loader.py")) else os.path.dirname(_THIS_DIR)
for _sub in ("core", "shared", "editors", "remote", "addons_sys", "extras"):
    _p = os.path.join(_PROJECT_ROOT, _sub)
    if _p not in sys.path:
        sys.path.insert(0, _p)

from PyQt6.QtWidgets import QFrame, QVBoxLayout, QHBoxLayout, QWidget, QLabel, QPushButton, QGridLayout, QMenu
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QAction

from game_card import GameCard
from lang_loader import tr


class GroupWidget(QFrame):
    def __init__(self, name, games, parent_launcher, is_favorite=False):
        super().__init__()
        self.group_name = name
        self.games = games
        self.parent_launcher = parent_launcher
        self.is_collapsed = False
        self.is_favorite = is_favorite
        self.setAcceptDrops(True)
        self.init_ui()

    def init_ui(self):
        self.main_vbox = QVBoxLayout(self)
        self.header = QWidget()
        if not self.is_favorite:
            self.header.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
            self.header.customContextMenuRequested.connect(self.show_group_menu)
        h_lay = QHBoxLayout(self.header)
        self.tgl = QPushButton("▼")
        self.tgl.setObjectName("GroupToggleBtn")
        self.tgl.setFixedSize(50, 50)
        self.tgl.clicked.connect(self.toggle)
        lbl = QLabel(self.group_name)
        lbl.setObjectName("GroupTitleLabel")
        lbl.setProperty("favorite", self.is_favorite)
        h_lay.addWidget(self.tgl); h_lay.addWidget(lbl); h_lay.addStretch()
        self.main_vbox.addWidget(self.header)
        self.content = QWidget()
        self.grid = QGridLayout(self.content)
        self.grid.setSpacing(25)
        self.main_vbox.addWidget(self.content)

    def refresh_cards(self, filter_text=""):
        while self.grid.count(): 
            w = self.grid.takeAt(0).widget()
            if w: w.deleteLater()
        c, r = 0, 0; visible_count = 0
        for g in self.games:
            if filter_text.lower() in g['name'].lower():
                self.grid.addWidget(GameCard(g, self.parent_launcher, self.group_name), r, c)
                c += 1; visible_count += 1
                if c > 3: c, r = 0, r + 1
        self.setVisible(visible_count > 0)

    def toggle(self):
        self.is_collapsed = not self.is_collapsed
        self.content.setVisible(not self.is_collapsed)
        self.tgl.setText("▶" if self.is_collapsed else "▼")

    def show_group_menu(self, pos):
        menu = QMenu(self)
        r_act = QAction(tr("group.rename"), self)
        d_act = QAction(tr("group.delete_group"), self)
        r_act.triggered.connect(lambda: self.parent_launcher.edit_group(self.group_name))
        d_act.triggered.connect(lambda: self.parent_launcher.delete_group_confirm(self.group_name))
        menu.addAction(r_act); menu.addAction(d_act)
        menu.exec(self.header.mapToGlobal(pos))

