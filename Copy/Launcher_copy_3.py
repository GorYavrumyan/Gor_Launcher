
import sys
import json
import os
import subprocess
import time
from datetime import datetime
from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, 
    QPushButton, QFileDialog, QLineEdit, QScrollArea, QFrame, 
    QLabel, QInputDialog, QGridLayout, QDialog, QComboBox, QMenu, QMessageBox, QCheckBox, QTabWidget
)
from PyQt6.QtCore import Qt, QSize, QMimeData, QThread, pyqtSignal
from PyQt6.QtGui import QKeySequence, QShortcut, QIcon, QPixmap, QDrag, QAction
from game_editor import GameEditor
from group_editor import GroupEditor

# --- ПОТОК ДЛЯ МОНИТОРИНГА ПРОЦЕССА ИГРЫ ---
class ProcessMonitor(QThread):
    finished_playing = pyqtSignal(int, dict) 

    def __init__(self, process, start_time, game_data):
        super().__init__()
        self.process = process
        self.start_time = start_time
        self.game_data = game_data

    def run(self):
        self.process.wait()  
        duration = int(time.time() - self.start_time)
        self.finished_playing.emit(duration, self.game_data)

# --- КАРТОЧКА ИСТОРИИ ---
class HistoryCard(QFrame):
    def __init__(self, entry, index, parent_launcher):
        super().__init__()
        self.entry = entry
        self.index = index
        self.parent_launcher = parent_launcher
        self.setFixedSize(220, 380)
        self.setObjectName("HistoryCard")
        self.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.customContextMenuRequested.connect(self.show_context_menu)
        self.init_ui()

    def init_ui(self):
        layout = QVBoxLayout(self)
        img = QLabel()
        img.setFixedSize(190, 240)
        pix = QPixmap(self.entry.get('icon', ''))
        if pix.isNull():
            img.setText("🎮")
        else:
            img.setPixmap(pix.scaled(190, 240, Qt.AspectRatioMode.KeepAspectRatioByExpanding, Qt.TransformationMode.SmoothTransformation))
        img.setAlignment(Qt.AlignmentFlag.AlignCenter)
        
        name = QLabel(self.entry['name'])
        name.setAlignment(Qt.AlignmentFlag.AlignCenter)
        
        date_lbl = QLabel(f"📅 {self.entry['date']}")
        
        dur = self.entry.get('session_time', 0)
        h, m = dur // 3600, (dur % 3600) // 60
        time_lbl = QLabel(f"⌛ Сессия: {h}ч {m}м")

        layout.addWidget(img, alignment=Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(name)
        layout.addWidget(date_lbl)
        layout.addWidget(time_lbl)
        layout.addStretch()

    def show_context_menu(self, pos):
        menu = QMenu(self)
        del_act = QAction("🗑️ Удалить запись", self)
        del_act.triggered.connect(lambda: self.parent_launcher.delete_history_entry(self.index))
        menu.addAction(del_act)
        menu.exec(self.mapToGlobal(pos))

# --- КАРТОЧКА ИГРЫ ---
class GameCard(QFrame):
    def __init__(self, game_data, parent_launcher, group_name=None):
        super().__init__()
        self.game_data = game_data
        self.parent_launcher = parent_launcher
        self.group_name = group_name
        self.setFixedSize(280, 520) 
        self.setObjectName("GameCard")
        self.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.customContextMenuRequested.connect(self.show_context_menu)
        self.init_ui()

    def init_ui(self):
        vbox = QVBoxLayout(self)
        vbox.setContentsMargins(15, 15, 15, 15)
        vbox.setSpacing(12)
        
        self.img = QLabel()
        self.img.setFixedSize(250, 330)
        is_fav = self.game_data.get('favorite', False)
        
        pixmap = QPixmap(self.game_data.get('icon', ''))
        if pixmap.isNull():
            self.img.setText("🎮")
        else:
            self.img.setPixmap(pixmap.scaled(250, 330, Qt.AspectRatioMode.KeepAspectRatioByExpanding, Qt.TransformationMode.SmoothTransformation))
        self.img.setAlignment(Qt.AlignmentFlag.AlignCenter)
        
        display_name = ("⭐️ " if is_fav else "") + self.game_data['name']
        name = QLabel(display_name)
        name.setAlignment(Qt.AlignmentFlag.AlignCenter)
        name.setWordWrap(True)

        total_sec = self.game_data.get('playtime_seconds', 0)
        h, m = total_sec // 3600, (total_sec % 3600) // 60
        self.time_lbl = QLabel(f"⏱ {h}ч {m}м")
        self.time_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)

        btn_layout = QHBoxLayout()
        run_btn = QPushButton("ЗАПУСТИТЬ")
        run_btn.setFixedHeight(45)
        run_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        run_btn.clicked.connect(self.run_game)
        
        folder_btn = QPushButton("📁")
        folder_btn.setFixedSize(55, 45)
        folder_btn.clicked.connect(self.open_game_folder)

        btn_layout.addWidget(run_btn)
        btn_layout.addWidget(folder_btn)

        vbox.addWidget(self.img, alignment=Qt.AlignmentFlag.AlignCenter)
        vbox.addWidget(name)
        vbox.addWidget(self.time_lbl)
        vbox.addStretch()
        vbox.addLayout(btn_layout)

    def open_game_folder(self):
        try:
            exe_path = self.game_data['path']
            if os.path.exists(exe_path):
                os.startfile(os.path.dirname(os.path.abspath(exe_path)))
        except: pass

    def show_context_menu(self, pos):
        menu = QMenu(self)
        fav_text = "❌ Убрать из избранного" if self.game_data.get('favorite') else "⭐️ В избранное"
        fav_act = QAction(fav_text, self)
        fav_act.triggered.connect(self.toggle_favorite)
        e_act = QAction("📝 Изменить", self)
        e_act.triggered.connect(lambda: self.parent_launcher.edit_game(self.game_data, self.group_name))
        d_act = QAction("🗑️ Удалить", self)
        d_act.triggered.connect(lambda: self.parent_launcher.delete_game_confirm(self.game_data, self.group_name))
        menu.addAction(fav_act)
        menu.addSeparator()
        menu.addAction(e_act)
        menu.addAction(d_act)
        menu.exec(self.mapToGlobal(pos))

    def toggle_favorite(self):
        self.game_data['favorite'] = not self.game_data.get('favorite', False)
        self.parent_launcher.save_data()
        self.parent_launcher.refresh_list()

    def run_game(self):
        try: 
            full_path = os.path.abspath(self.game_data['path'])
            working_dir = os.path.dirname(full_path)
            args = self.game_data.get('args', '')
            start_t = time.time()
            if full_path.lower().endswith('.bat'):
                proc = subprocess.Popen(f'start /wait "" "{full_path}" {args}', shell=True, cwd=working_dir)
            else:
                cmd = f'"{full_path}" {args}' if args else f'"{full_path}"'
                proc = subprocess.Popen(cmd, shell=True, cwd=working_dir)
            self.monitor = ProcessMonitor(proc, start_t, self.game_data)
            self.monitor.finished_playing.connect(self.parent_launcher.finalize_history_session)
            self.monitor.start()
        except Exception as e: QMessageBox.critical(self, "Ошибка", f"Не удалось запустить:\n{e}")

    def mouseMoveEvent(self, e):
        if e.buttons() == Qt.MouseButton.LeftButton:
            drag = QDrag(self); mime = QMimeData(); mime.setText(self.game_data['name'])
            drag.setMimeData(mime); drag.exec(Qt.DropAction.MoveAction)

# --- ГРУППА ---
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
        self.tgl.setFixedSize(50, 50)
        self.tgl.clicked.connect(self.toggle)
        lbl = QLabel(self.group_name)
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
        r_act = QAction("✏️ Переименовать", self)
        d_act = QAction("❌ Удалить группу", self)
        r_act.triggered.connect(lambda: self.parent_launcher.edit_group(self.group_name))
        d_act.triggered.connect(lambda: self.parent_launcher.delete_group_confirm(self.group_name))
        menu.addAction(r_act); menu.addAction(d_act)
        menu.exec(self.header.mapToGlobal(pos))

    def dragEnterEvent(self, e): e.accept()
    def dropEvent(self, e): self.parent_launcher.move_game_to_group(e.mimeData().text(), self.group_name)

# --- ГЛАВНОЕ ОКНО ---
class GORLauncher(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("GOR Launcher PRO v3.0")
        self.setMinimumSize(1300, 950)
        self.data_file = "games_data.json"
        
        if not os.path.exists("styles"): os.makedirs("styles")
        
        self.load_data()
        self.init_ui()

    def load_stylesheet(self, style_name):
        style_path = os.path.join("styles", f"{style_name}.qss")
        if os.path.exists(style_path):
            with open(style_path, "r", encoding="utf-8") as f:
                self.setStyleSheet(f.read())

    def load_data(self):
        if os.path.exists(self.data_file):
            try:
                with open(self.data_file, 'r', encoding='utf-8') as f: 
                    self.games_info = json.load(f)
            except: 
                self.games_info = {"groups": {}, "standalone": [], "history": []}
        else: 
            self.games_info = {"groups": {}, "standalone": [], "history": []}
        
        if "history" not in self.games_info: self.games_info["history"] = []
        if "groups" not in self.games_info: self.games_info["groups"] = {}
        if "standalone" not in self.games_info: self.games_info["standalone"] = []

    def save_data(self):
        with open(self.data_file, 'w', encoding='utf-8') as f: 
            json.dump(self.games_info, f, indent=4)

    def init_ui(self):
        central = QWidget()
        self.setCentralWidget(central)
        self.main_lay = QVBoxLayout(central)
        
        header = QHBoxLayout()
        title = QLabel("GOR UNIVERSAL")
        self.stats_lbl = QLabel()
        
        self.theme_combo = QComboBox()
        self.theme_combo.addItems([f.replace(".qss", "") for f in os.listdir("styles") if f.endswith(".qss")])
        self.theme_combo.currentTextChanged.connect(self.load_stylesheet)
        
        btn_sunshine = QPushButton("⚙️ SUNSHINE")
        btn_sunshine.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_sunshine.clicked.connect(self.run_sunshine)

        self.search_bar = QLineEdit()
        self.search_bar.setPlaceholderText("🔍 Поиск по библиотеке...")
        self.search_bar.setFixedWidth(300)
        self.search_bar.textChanged.connect(self.refresh_list)
        
        header.addWidget(title)
        header.addWidget(QLabel("🎨"))
        header.addWidget(self.theme_combo)
        header.addStretch()
        header.addWidget(btn_sunshine)
        header.addWidget(self.stats_lbl)
        header.addWidget(self.search_bar)
        self.main_lay.addLayout(header)

        self.tabs = QTabWidget()
        self.main_lay.addWidget(self.tabs)

        self.lib_tab = QWidget()
        self.lib_lay = QVBoxLayout(self.lib_tab)
        tool_lay = QHBoxLayout()
        btn_add = QPushButton("➕ ДОБАВИТЬ ИГРУ"); btn_add.clicked.connect(self.add_game_dialog)
        btn_grp = QPushButton("📁 НОВАЯ ГРУППА"); btn_grp.clicked.connect(self.add_group)
        tool_lay.addWidget(btn_add); tool_lay.addWidget(btn_grp); tool_lay.addStretch()
        self.lib_lay.addLayout(tool_lay)
        self.scroll_lib = QScrollArea(); self.scroll_lib.setWidgetResizable(True)
        self.lib_cont = QWidget(); self.lib_scroll_lay = QVBoxLayout(self.lib_cont)
        self.lib_scroll_lay.setAlignment(Qt.AlignmentFlag.AlignTop)
        self.scroll_lib.setWidget(self.lib_cont)
        self.lib_lay.addWidget(self.scroll_lib)
        self.tabs.addTab(self.lib_tab, "📚 БИБЛИОТЕКА")

        self.fav_tab = QWidget()
        self.fav_lay = QVBoxLayout(self.fav_tab)
        self.scroll_fav = QScrollArea(); self.scroll_fav.setWidgetResizable(True)
        self.fav_cont = QWidget(); self.fav_grid = QGridLayout(self.fav_cont); self.fav_grid.setSpacing(25)
        self.fav_grid.setAlignment(Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignLeft)
        self.scroll_fav.setWidget(self.fav_cont)
        self.fav_lay.addWidget(self.scroll_fav)
        self.tabs.addTab(self.fav_tab, "⭐️ ИЗБРАННОЕ")

        self.hist_tab = QWidget()
        self.hist_lay = QVBoxLayout(self.hist_tab)
        hist_tool = QHBoxLayout()
        btn_clear = QPushButton("🗑️ ОЧИСТИТЬ ИСТОРИЮ"); btn_clear.clicked.connect(self.clear_history_confirm)
        hist_tool.addStretch(); hist_tool.addWidget(btn_clear)
        self.hist_lay.addLayout(hist_tool)
        self.scroll_hist = QScrollArea(); self.scroll_hist.setWidgetResizable(True)
        self.hist_cont = QWidget(); self.hist_grid = QGridLayout(self.hist_cont); self.hist_grid.setSpacing(25)
        self.hist_grid.setAlignment(Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignLeft)
        self.scroll_hist.setWidget(self.hist_cont)
        self.hist_lay.addWidget(self.scroll_hist)
        self.tabs.addTab(self.hist_tab, "📜 ИСТОРИЯ")

        self.update_stats(); self.refresh_list()

    def run_sunshine(self):
        try:
            subprocess.Popen([sys.executable, "sunshine_control.py"])
        except Exception as e:
            QMessageBox.critical(self, "Ошибка", f"Не удалось запустить Sunshine:\n{e}")

    def finalize_history_session(self, seconds, game_data):
        all_games = self.games_info["standalone"][:]
        for g_list in self.games_info["groups"].values(): all_games.extend(g_list)
        for g in all_games:
            if g['name'] == game_data['name']:
                g['playtime_seconds'] = g.get('playtime_seconds', 0) + seconds
                break
        now = datetime.now().strftime("%d.%m.%Y %H:%M")
        entry = {"name": game_data['name'], "icon": game_data.get('icon', ''), "date": now, "session_time": seconds}
        
        if "history" not in self.games_info: self.games_info["history"] = []
        self.games_info["history"].insert(0, entry) 
        if len(self.games_info["history"]) > 100: self.games_info["history"].pop()
        
        self.save_data()
        self.update_stats()
        self.refresh_list()

    def clear_history_confirm(self):
        ret = QMessageBox.question(self, 'Очистка', "Удалить всю историю?", QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
        if ret == QMessageBox.StandardButton.Yes:
            self.games_info["history"] = []; self.save_data(); self.refresh_list()

    def delete_history_entry(self, index):
        if 0 <= index < len(self.games_info["history"]):
            self.games_info["history"].pop(index); self.save_data(); self.refresh_list()

    def update_stats(self):
        total_sec = 0; count = 0
        all_games = self.games_info["standalone"][:]
        for g_list in self.games_info["groups"].values(): all_games.extend(g_list)
        for g in all_games: 
            total_sec += g.get('playtime_seconds', 0)
            count += 1
        h = total_sec // 3600; m = (total_sec % 3600) // 60
        self.stats_lbl.setText(f"📊 Игр: {count} | ⌛ Всего: {h}ч {m}м")

    def refresh_list(self):
        filter_text = self.search_bar.text().lower()
        while self.lib_scroll_lay.count():
            child = self.lib_scroll_lay.takeAt(0)
            if child.widget(): child.widget().deleteLater()
        all_games = self.games_info["standalone"][:]
        for g_list in self.games_info["groups"].values(): all_games.extend(g_list)
        while self.fav_grid.count():
            w = self.fav_grid.takeAt(0).widget()
            if w: w.deleteLater()
        fav_list = [g for g in all_games if g.get('favorite')]
        c, r = 0, 0
        for g in fav_list:
            self.fav_grid.addWidget(GameCard(g, self), r, c)
            c += 1
            if c > 4: c, r = 0, r + 1
        while self.hist_grid.count():
            w = self.hist_grid.takeAt(0).widget()
            if w: w.deleteLater()
        for i, entry in enumerate(self.games_info["history"]):
            self.hist_grid.addWidget(HistoryCard(entry, i, self), i // 5, i % 5)
        for gn, gg in self.games_info["groups"].items():
            grp_w = GroupWidget(gn, gg, self)
            self.lib_scroll_lay.addWidget(grp_w)
            grp_w.refresh_cards(filter_text)
        st_w = GroupWidget("БЕЗ ГРУППЫ", self.games_info["standalone"], self)
        self.lib_scroll_lay.addWidget(st_w)
        st_w.refresh_cards(filter_text)

    def add_game_dialog(self):
        dlg = GameEditor(self)
        if dlg.exec():
            self.load_data(); self.refresh_list(); self.update_stats()

    def edit_game(self, old, grp):
        dlg = GameEditor(self, game_data=old, current_group=grp or "Без группы")
        if dlg.exec():
            self.load_data(); self.refresh_list(); self.update_stats()

    def delete_game_confirm(self, game, group):
        ret = QMessageBox.question(self, 'Удаление', f"Удалить '{game['name']}'?", QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
        if ret == QMessageBox.StandardButton.Yes: self.delete_game(game, group)

    def delete_game(self, game, group, refresh=True):
        lst = self.games_info["groups"].get(group, self.games_info["standalone"]) if group and group != "Без группы" else self.games_info["standalone"]
        for i, g in enumerate(lst):
            if g["name"] == game["name"]: lst.pop(i); break
        if refresh: self.save_data(); self.refresh_list(); self.update_stats()

    def add_group(self):
        dlg = GroupEditor(self)
        if dlg.exec():
            self.load_data(); self.refresh_list()

    def edit_group(self, old_name):
        dlg = GroupEditor(self, old_name=old_name)
        if dlg.exec():
            self.load_data(); self.refresh_list()

    def delete_group_confirm(self, name):
        ret = QMessageBox.question(self, 'Удаление', f"Удалить группу '{name}'?", QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
        if ret == QMessageBox.StandardButton.Yes:
            self.games_info["standalone"].extend(self.games_info["groups"].pop(name))
            self.save_data(); self.refresh_list()

    def move_game_to_group(self, name, target):
        game = None
        for i, g in enumerate(self.games_info["standalone"]):
            if g["name"] == name: game = self.games_info["standalone"].pop(i); break
        if not game:
            for gn in self.games_info["groups"]:
                for i, g in enumerate(self.games_info["groups"][gn]):
                    if g["name"] == name: game = self.games_info["groups"][gn].pop(i); break
        if game:
            if target and target != "БЕЗ ГРУППЫ": self.games_info["groups"][target].append(game)
            else: self.games_info["standalone"].append(game)
            self.save_data(); self.refresh_list()

if __name__ == "__main__":
    app = QApplication(sys.argv); app.setStyle("Fusion")
    ex = GORLauncher(); ex.show(); sys.exit(app.exec())