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
import subprocess
import platform
import uuid
from datetime import datetime
from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QPushButton, QLineEdit, QScrollArea, QLabel, QGridLayout,
    QComboBox, QMenu, QMessageBox, QTabWidget
)
from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtGui import QIcon, QAction

from style_loader import apply_global_style
from fortune_wheel import FortuneWheelDialog
from lang_loader import tr, available_languages, current_language, set_language

from launcher_utils import NO_GROUP_KEY, find_favicon_path, universal_launch, run_editor_process
from process_monitor import EditorMonitor
from history_card import HistoryCard
from game_card import GameCard
from group_widget import GroupWidget


with open("version.json", "r", encoding="utf-8") as f:
    version = json.load(f)["version"]


# --- ГЛАВНОЕ ОКНО ---
class GORLauncher(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle(tr("launcher.window_title") + "   " + version)
        self.setWindowIcon(QIcon(find_favicon_path()))
        self.setMinimumSize(1300, 950)
        self.data_file = "games_data.json"
        self.active_sessions = {}
        self._wheel_monitors = []
        self.load_data()
        self.init_ui()

    def load_data(self):
        if os.path.exists(self.data_file):
            try:
                with open(self.data_file, 'r', encoding='utf-8') as f: 
                    self.games_info = json.load(f)
            except Exception as e:
                print(f"Не удалось прочитать {self.data_file}, создаю новую базу: {e}")
                self.games_info = {"groups": {}, "standalone": [], "history": []}
        else: 
            self.games_info = {"groups": {}, "standalone": [], "history": []}
        if "history" not in self.games_info: self.games_info["history"] = []
        if "groups" not in self.games_info: self.games_info["groups"] = {}
        if "standalone" not in self.games_info: self.games_info["standalone"] = []
        self.migrate_ids()

    def migrate_ids(self):
        changed = False
        all_lists = [self.games_info["standalone"]] + list(self.games_info["groups"].values())
        for lst in all_lists:
            for g in lst:
                if not g.get('id'):
                    g['id'] = str(uuid.uuid4())
                    changed = True
        if changed:
            self.save_data()

    def save_data(self):
        with open(self.data_file, 'w', encoding='utf-8') as f: 
            json.dump(self.games_info, f, indent=4)

    def init_ui(self):
        central = QWidget()
        self.setCentralWidget(central)
        self.main_lay = QVBoxLayout(central)
        header = QHBoxLayout()
        self.stats_lbl = QLabel()
        self.stats_lbl.setObjectName("StatsLabel")
        
        self.burger_btn = QPushButton("☰")
        self.burger_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.burger_btn.setObjectName("BurgerMenuBtn")
        self.burger_btn.setStyleSheet("QPushButton::menu-indicator { image: none; width: 0px; }")

        burger_menu = QMenu(self)

        act_wheel = QAction(tr("launcher.menu_wheel"), self)
        act_wheel.triggered.connect(self.open_fortune_wheel)
        burger_menu.addAction(act_wheel)

        act_sunshine = QAction(tr("launcher.menu_sunshine"), self)
        act_sunshine.triggered.connect(self.run_sunshine)
        burger_menu.addAction(act_sunshine)

        act_exporter = QAction(tr("launcher.menu_exporter"), self)
        act_exporter.triggered.connect(self.open_exporter)
        burger_menu.addAction(act_exporter)

        burger_menu.addSeparator()
        lang_menu = burger_menu.addMenu(tr("launcher.menu_language"))
        active_code = current_language()
        for lang in available_languages():
            act = QAction(("✅ " if lang["code"] == active_code else "") + lang["name"], self)
            act.triggered.connect(lambda checked=False, c=lang["code"], n=lang["name"]: self.change_language(c, n))
            lang_menu.addAction(act)

        self.burger_btn.setMenu(burger_menu)
        
        self.search_bar = QLineEdit()
        self.search_bar.setObjectName("SearchBar")
        self.search_bar.setPlaceholderText(tr("launcher.search_placeholder"))
        self.search_bar.setFixedWidth(300)
        self.search_timer = QTimer(self)
        self.search_timer.setSingleShot(True)
        self.search_timer.timeout.connect(self.refresh_list)
        self.search_bar.textChanged.connect(lambda: self.search_timer.start(250))
        
        header.addWidget(self.stats_lbl)
        header.addWidget(self.search_bar)
        header.addStretch()
        header.addWidget(self.burger_btn)
        self.main_lay.addLayout(header)
        
        self.tabs = QTabWidget()
        self.main_lay.addWidget(self.tabs)
        
        self.lib_tab = QWidget()
        self.lib_lay = QVBoxLayout(self.lib_tab)
        tool_lay = QHBoxLayout()
        btn_add = QPushButton(tr("launcher.add_game_btn")); btn_add.clicked.connect(self.add_game_dialog)
        btn_grp = QPushButton(tr("launcher.add_group_btn")); btn_grp.clicked.connect(self.add_group)
        tool_lay.addWidget(btn_add); tool_lay.addWidget(btn_grp); tool_lay.addStretch()

        sort_lbl = QLabel(tr("launcher.sort_label"))
        self.sort_combo = QComboBox()
        self.sort_combo.setObjectName("SortCombo")
        self.sort_combo.addItem(tr("launcher.sort_default"), "default")
        self.sort_combo.addItem(tr("launcher.sort_name_asc"), "name_asc")
        self.sort_combo.addItem(tr("launcher.sort_name_desc"), "name_desc")
        self.sort_combo.addItem(tr("launcher.sort_playtime_desc"), "playtime_desc")
        self.sort_combo.addItem(tr("launcher.sort_playtime_asc"), "playtime_asc")
        self.sort_combo.addItem(tr("launcher.sort_newest"), "newest")
        self.sort_combo.currentIndexChanged.connect(self.refresh_list)
        tool_lay.addWidget(sort_lbl)
        tool_lay.addWidget(self.sort_combo)

        self.lib_lay.addLayout(tool_lay)
        
        self.scroll_lib = QScrollArea(); self.scroll_lib.setWidgetResizable(True)
        self.lib_cont = QWidget(); self.lib_scroll_lay = QVBoxLayout(self.lib_cont)
        self.lib_scroll_lay.setAlignment(Qt.AlignmentFlag.AlignTop)
        self.scroll_lib.setWidget(self.lib_cont); self.lib_lay.addWidget(self.scroll_lib)
        self.tabs.addTab(self.lib_tab, tr("launcher.tab_library"))
        
        self.fav_tab = QWidget()
        self.fav_lay = QVBoxLayout(self.fav_tab)
        self.scroll_fav = QScrollArea(); self.scroll_fav.setWidgetResizable(True)
        self.fav_cont = QWidget(); self.fav_grid = QGridLayout(self.fav_cont); self.fav_grid.setSpacing(25)
        self.fav_grid.setAlignment(Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignLeft)
        self.scroll_fav.setWidget(self.fav_cont); self.fav_lay.addWidget(self.scroll_fav)
        self.tabs.addTab(self.fav_tab, tr("launcher.tab_favorites"))
        
        self.hist_tab = QWidget()
        self.hist_lay = QVBoxLayout(self.hist_tab)
        hist_tool = QHBoxLayout()
        btn_clear = QPushButton(tr("launcher.clear_history_btn")); btn_clear.clicked.connect(self.clear_history_confirm)
        hist_tool.addStretch(); hist_tool.addWidget(btn_clear)
        self.hist_lay.addLayout(hist_tool)
        
        self.scroll_hist = QScrollArea(); self.scroll_hist.setWidgetResizable(True)
        self.hist_cont = QWidget(); self.hist_grid = QGridLayout(self.hist_cont); self.hist_grid.setSpacing(20)
        self.hist_grid.setAlignment(Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignLeft)
        self.scroll_hist.setWidget(self.hist_cont); self.hist_lay.addWidget(self.scroll_hist)
        self.tabs.addTab(self.hist_tab, tr("launcher.tab_history"))
        
        self.refresh_list()

    def change_language(self, code, name):
        set_language(code)
        reply = QMessageBox.question(
            self, tr("launcher.language_restart_title"),
            tr("launcher.language_restart_text", name=name)
        )
        if reply == QMessageBox.StandardButton.Yes:
            try:
                from bridge_loader import restart_launcher
                restart_launcher(confirm=False)
            except Exception:
                base_dir = os.path.dirname(os.path.abspath(sys.argv[0]))
                subprocess.Popen([sys.executable] + sys.argv, cwd=base_dir)
                QApplication.closeAllWindows()
                sys.exit(0)

    def sort_games_list(self, games):
        """Возвращает отсортированную КОПИЮ списка игр согласно self.sort_combo.
        Сами словари игр не копируются - это те же объекты, что и в self.games_info,
        поэтому редактирование игры продолжает работать как прежде."""
        mode = self.sort_combo.currentData() if hasattr(self, "sort_combo") else "default"
        games = list(games)
        if mode == "name_asc":
            games.sort(key=lambda g: g.get('name', '').lower())
        elif mode == "name_desc":
            games.sort(key=lambda g: g.get('name', '').lower(), reverse=True)
        elif mode == "playtime_desc":
            games.sort(key=lambda g: g.get('playtime_seconds', 0), reverse=True)
        elif mode == "playtime_asc":
            games.sort(key=lambda g: g.get('playtime_seconds', 0))
        elif mode == "newest":
            games.reverse()
        return games

    def sort_groups(self, groups_dict):
        """Возвращает список (имя_группы, игры) из словаря групп,
        отсортированный тем же режимом, что выбран в self.sort_combo.
        Для playtime_* берётся суммарное наигранное время всех игр в группе."""
        mode = self.sort_combo.currentData() if hasattr(self, "sort_combo") else "default"
        items = list(groups_dict.items())
        if mode == "name_asc":
            items.sort(key=lambda kv: kv[0].lower())
        elif mode == "name_desc":
            items.sort(key=lambda kv: kv[0].lower(), reverse=True)
        elif mode == "playtime_desc":
            items.sort(key=lambda kv: sum(g.get('playtime_seconds', 0) for g in kv[1]), reverse=True)
        elif mode == "playtime_asc":
            items.sort(key=lambda kv: sum(g.get('playtime_seconds', 0) for g in kv[1]))
        elif mode == "newest":
            items.reverse()
        return items

    def update_stats(self):
        total_games = len(self.games_info.get("standalone", []))
        for grp in self.games_info.get("groups", {}).values():
            total_games += len(grp)
        total_time = 0
        all_lists = [self.games_info.get("standalone", [])] + list(self.games_info.get("groups", {}).values())
        for lst in all_lists:
            for g in lst:
                total_time += g.get('playtime_seconds', 0)
        h = total_time // 3600
        self.stats_lbl.setText(tr("launcher.stats", count=total_games, hours=h))

    def refresh_list(self):
        filter_text = self.search_bar.text().strip().lower()
        self.update_stats()
        
        # --- БИБЛИОТЕКА ---
        while self.lib_scroll_lay.count():
            item = self.lib_scroll_lay.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        for name, games in self.sort_groups(self.games_info.get("groups", {})):
            gw = GroupWidget(name, self.sort_games_list(games), self)
            gw.refresh_cards(filter_text)
            self.lib_scroll_lay.addWidget(gw)

        st_games = self.games_info.get("standalone", [])
        if st_games:
            gw_st = GroupWidget(tr("launcher.standalone_title"), self.sort_games_list(st_games), self)
            gw_st.refresh_cards(filter_text)
            self.lib_scroll_lay.addWidget(gw_st)

        # --- ИЗБРАННОЕ ---
        while self.fav_grid.count():
            item = self.fav_grid.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        fav_games = []
        all_lists = [self.games_info.get("standalone", [])] + list(self.games_info.get("groups", {}).values())
        for lst in all_lists:
            for g in lst:
                if g.get('favorite', False):
                    fav_games.append(g)

        c, r = 0, 0
        for g in self.sort_games_list(fav_games):
            if filter_text in g['name'].lower():
                self.fav_grid.addWidget(GameCard(g, self, "Избранное"), r, c)
                c += 1
                if c > 3:
                    c, r = 0, r + 1

        # --- ИСТОРИЯ ---
        while self.hist_grid.count():
            item = self.hist_grid.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        c, r = 0, 0
        history_list = self.games_info.get("history", [])
        for idx, entry in enumerate(history_list):
            if filter_text in entry['name'].lower():
                self.hist_grid.addWidget(HistoryCard(entry, idx, self), r, c)
                c += 1
                if c > 4:
                    c, r = 0, r + 1

    def add_game_dialog(self):
        proc = run_editor_process("game_editor", py_subdir="editors")
        monitor = EditorMonitor(proc)
        monitor.editor_closed.connect(self.on_editor_closed)
        self._wheel_monitors.append(monitor)
        monitor.start()

    def edit_game(self, game_data, group_name):
        g_name = group_name if group_name else NO_GROUP_KEY
        gid = game_data.get("id", "")
        proc = run_editor_process("game_editor", [game_data['name'], g_name, gid], py_subdir="editors")
        monitor = EditorMonitor(proc)
        monitor.editor_closed.connect(self.on_editor_closed)
        self._wheel_monitors.append(monitor)
        monitor.start()

    def on_editor_closed(self):
        self.load_data()
        self.refresh_list()

    def add_group(self):
        proc = run_editor_process("group_editor", py_subdir="editors")
        monitor = EditorMonitor(proc)
        monitor.editor_closed.connect(self.on_editor_closed)
        self._wheel_monitors.append(monitor)
        monitor.start()

    def edit_group(self, group_name):
        proc = run_editor_process("group_editor", [group_name], py_subdir="editors")
        monitor = EditorMonitor(proc)
        monitor.editor_closed.connect(self.on_editor_closed)
        self._wheel_monitors.append(monitor)
        monitor.start()

    def delete_group_confirm(self, group_name):
        reply = QMessageBox.question(
            self, tr("group.delete_confirm_title"),
            tr("group.delete_confirm_text", name=group_name),
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        if reply == QMessageBox.StandardButton.Yes:
            if group_name in self.games_info.get("groups", {}):
                games = self.games_info["groups"].pop(group_name)
                self.games_info["standalone"].extend(games)
                self.save_data()
                self.refresh_list()

    def delete_game_confirm(self, game_data, group_name):
        reply = QMessageBox.question(
            self, tr("game_delete.confirm_title"),
            tr("game_delete.confirm_text", name=game_data['name']),
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        if reply == QMessageBox.StandardButton.Yes:
            gid = game_data.get('id')
            if group_name and group_name in self.games_info.get("groups", {}):
                lst = self.games_info["groups"][group_name]
            else:
                lst = self.games_info.get("standalone", [])
            
            for idx, g in enumerate(lst):
                if (gid and g.get('id') == gid) or (g['name'] == game_data['name']):
                    lst.pop(idx)
                    break

            self.save_data()
            self.refresh_list()

    def move_game_to_group(self, game_identifier, target_group):
        found_game = None
        all_lists = [self.games_info["standalone"]] + list(self.games_info["groups"].values())
        
        for lst in all_lists:
            for idx, g in enumerate(lst):
                if g.get('id') == game_identifier or g['name'] == game_identifier:
                    found_game = lst.pop(idx)
                    break
            if found_game:
                break

        if found_game:
            if target_group == tr("launcher.standalone_title") or target_group == NO_GROUP_KEY:
                self.games_info["standalone"].append(found_game)
            else:
                if target_group not in self.games_info["groups"]:
                    self.games_info["groups"][target_group] = []
                self.games_info["groups"][target_group].append(found_game)
            
            self.save_data()
            self.refresh_list()

    def open_fortune_wheel(self):
        dialog = FortuneWheelDialog(self, json_path=self.data_file, launch_callback=self.launch_game_from_wheel)
        dialog.exec()

    def launch_game_from_wheel(self, game_data):
        target_card = None
        for i in range(self.lib_scroll_lay.count()):
            w = self.lib_scroll_lay.itemAt(i).widget()
            if isinstance(w, GroupWidget):
                for j in range(w.grid.count()):
                    card = w.grid.itemAt(j).widget()
                    if isinstance(card, GameCard):
                        if (card.game_data.get('id') and card.game_data.get('id') == game_data.get('id')) or \
                           (card.game_data['name'] == game_data['name']):
                            target_card = card
                            break
            if target_card:
                break
        
        if target_card:
            target_card.handle_main_button()
        else:
            try:
                path = game_data['path']
                universal_launch(path)
            except Exception as e:
                QMessageBox.critical(self, tr("common.error"), tr("game_card.launch_error", error=e))

    def run_sunshine(self):
        try:
            run_editor_process("sunshine_control", py_subdir="remote")
        except Exception as e:
            QMessageBox.critical(self, tr("sunshine_error.title"), tr("sunshine_error.text", error=e))

    def open_exporter(self):
        try:
            run_editor_process("exporter_editor", py_subdir="extras")
        except Exception as e:
            QMessageBox.critical(self, tr("exporter_error.title"), tr("exporter_error.text", error=e))

    def finalize_history_session(self, duration, game_data):
        gid = game_data.get('id')
        found_game = None
        all_lists = [self.games_info["standalone"]] + list(self.games_info["groups"].values())
        
        for lst in all_lists:
            for g in lst:
                if (gid and g.get('id') == gid) or (g['name'] == game_data['name']):
                    g['playtime_seconds'] = g.get('playtime_seconds', 0) + duration
                    found_game = g
                    break
            if found_game:
                break

        now_str = datetime.now().strftime("%d.%m.%Y %H:%M")
        history_entry = {
            "name": game_data['name'],
            "icon": game_data.get('icon', ''),
            "date": now_str,
            "session_time": duration
        }
        self.games_info["history"].insert(0, history_entry)
        self.save_data()
        self.refresh_list()

    def delete_history_entry(self, index):
        if 0 <= index < len(self.games_info.get("history", [])):
            self.games_info["history"].pop(index)
            self.save_data()
            self.refresh_list()

    def clear_history_confirm(self):
        reply = QMessageBox.question(
            self, tr("history_clear.confirm_title"),
            tr("history_clear.confirm_text"),
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        if reply == QMessageBox.StandardButton.Yes:
            self.games_info["history"] = []
            self.save_data()
            self.refresh_list()

if __name__ == "__main__":
    app = QApplication(sys.argv)
    app.setWindowIcon(QIcon(find_favicon_path()))
    apply_global_style(app)
    launcher = GORLauncher()
    launcher.show()
