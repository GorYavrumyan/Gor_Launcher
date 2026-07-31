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
        img.setStyleSheet("background-color: #0d0d0d; border-radius: 8px; border: 1px solid #333;")
        
        pix = QPixmap(self.entry.get('icon', ''))
        if pix.isNull():
            img.setText("🎮")
            img.setStyleSheet("font-size: 40px; color: #444; background: #0d0d0d; border-radius: 8px;")
        else:
            img.setPixmap(pix.scaled(190, 240, Qt.AspectRatioMode.KeepAspectRatioByExpanding, Qt.TransformationMode.SmoothTransformation))
        
        img.setAlignment(Qt.AlignmentFlag.AlignCenter)
        
        name = QLabel(self.entry['name'])
        name.setStyleSheet("font-weight: bold; color: #007acc; font-size: 14px;")
        name.setAlignment(Qt.AlignmentFlag.AlignCenter)
        
        date_lbl = QLabel(f"📅 {self.entry['date']}")
        date_lbl.setStyleSheet("color: #888; font-size: 11px;")
        
        dur = self.entry.get('session_time', 0)
        h = dur // 3600
        m = (dur % 3600) // 60
        time_lbl = QLabel(f"⌛ Сессия: {h}ч {m}м")
        time_lbl.setStyleSheet("color: #aaa; font-size: 12px;")

        layout.addWidget(img, alignment=Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(name)
        layout.addWidget(date_lbl)
        layout.addWidget(time_lbl)
        layout.addStretch()

    def show_context_menu(self, pos):
        menu = QMenu(self)
        menu.setStyleSheet("background-color: #252526; color: white;")
        del_act = QAction("🗑️ Удалить запись", self)
        del_act.triggered.connect(lambda: self.parent_launcher.delete_history_entry(self.index))
        menu.addAction(del_act)
        menu.exec(self.mapToGlobal(pos))

# --- ОКНО НАСТРОЙКИ ---
class GameEditDialog(QDialog):
    def __init__(self, parent=None, game_data=None, groups=None, current_group=None):
        super().__init__(parent)
        self.setWindowTitle("Настройка игры GOR")
        self.setFixedWidth(600)
        
        self.game_data = game_data or {
            "name": "", 
            "path": "", 
            "icon": "", 
            "group": "Без группы", 
            "args": "", 
            "playtime_seconds": 0, 
            "favorite": False
        }
        self.groups = groups or []
        self.current_group = current_group or "Без группы"
        self.init_ui()

    def init_ui(self):
        layout = QVBoxLayout(self)
        self.setStyleSheet("background-color: #1e1e1e; color: #e1e1e1; font-size: 14px;")

        layout.addWidget(QLabel("Название мода/игры:"))
        self.name_edit = QLineEdit(self.game_data['name'])
        self.name_edit.setStyleSheet("background-color: #2d2d2d; border: 1px solid #3e3e42; padding: 8px; border-radius: 4px;")
        layout.addWidget(self.name_edit)

        layout.addWidget(QLabel("Файл запуска (exe или bat):"))
        path_layout = QHBoxLayout()
        self.path_edit = QLineEdit(self.game_data['path'])
        self.path_edit.setStyleSheet("background-color: #2d2d2d; border: 1px solid #3e3e42; padding: 8px; border-radius: 4px;")
        
        self.path_btn = QPushButton("📁 Обзор")
        self.path_btn.clicked.connect(self.select_path)
        path_layout.addWidget(self.path_edit)
        path_layout.addWidget(self.path_btn)
        layout.addLayout(path_layout)

        layout.addWidget(QLabel("Аргументы запуска:"))
        self.args_edit = QLineEdit(self.game_data.get('args', ''))
        self.args_edit.setPlaceholderText("-game folder_name")
        self.args_edit.setStyleSheet("background-color: #2d2d2d; border: 1px solid #007acc; padding: 8px; border-radius: 4px;")
        layout.addWidget(self.args_edit)

        layout.addWidget(QLabel("Обложка (PNG/JPG):"))
        icon_layout = QHBoxLayout()
        self.icon_edit = QLineEdit(self.game_data['icon'])
        self.icon_edit.setStyleSheet("background-color: #2d2d2d; border: 1px solid #3e3e42; padding: 8px; border-radius: 4px;")
        
        self.icon_btn = QPushButton("🖼️ Фото")
        self.icon_btn.clicked.connect(self.select_icon)
        icon_layout.addWidget(self.icon_edit)
        icon_layout.addWidget(self.icon_btn)
        layout.addLayout(icon_layout)

        preview_box = QHBoxLayout()
        self.preview_label = QLabel("Нет фото")
        self.preview_label.setFixedSize(200, 260)
        self.preview_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.preview_label.setStyleSheet("border: 2px dashed #444; background: #121212; border-radius: 10px;")
        
        self.fav_check = QCheckBox("⭐️ ДОБАВИТЬ В ИЗБРАННОЕ")
        self.fav_check.setChecked(self.game_data.get('favorite', False))
        self.fav_check.setStyleSheet("font-weight: bold; color: #ffcc00; margin-left: 10px;")
        
        preview_box.addWidget(self.preview_label)
        preview_box.addWidget(self.fav_check)
        preview_box.addStretch()
        layout.addLayout(preview_box)
        
        if self.game_data['icon']: 
            self.update_preview()

        layout.addWidget(QLabel("Назначить в группу:"))
        self.group_box = QComboBox()
        self.group_box.addItem("Без группы")
        self.group_box.addItems(self.groups)
        self.group_box.setCurrentText(self.current_group)
        self.group_box.setStyleSheet("background-color: #2d2d2d; color: white; padding: 8px; border-radius: 4px;")
        layout.addWidget(self.group_box)

        btns = QHBoxLayout()
        save_btn = QPushButton("СОХРАНИТЬ")
        save_btn.setStyleSheet("background-color: #0e639c; font-weight: bold; padding: 15px; border-radius: 8px; margin-top: 10px;")
        save_btn.clicked.connect(self.accept)
        
        cancel_btn = QPushButton("ОТМЕНА")
        cancel_btn.clicked.connect(self.reject)
        
        btns.addWidget(save_btn)
        btns.addWidget(cancel_btn)
        layout.addLayout(btns)

    def select_path(self):
        file, _ = QFileDialog.getOpenFileName(self, "Выбрать файл запуска", "", "Запускные файлы (*.exe *.bat)")
        if file: 
            self.path_edit.setText(file)

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
            "name": self.name_edit.text(), 
            "path": self.path_edit.text(), 
            "icon": self.icon_edit.text(), 
            "group": self.group_box.currentText(),
            "args": self.args_edit.text(),
            "favorite": self.fav_check.isChecked()
        }
        data['playtime_seconds'] = self.game_data.get('playtime_seconds', 0)
        return data

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
        self.img.setStyleSheet(f"background-color: #0d0d0d; border-radius: 12px; border: {'2px solid #ffcc00' if is_fav else '1px solid #333'};")
        
        pixmap = QPixmap(self.game_data.get('icon', ''))
        if pixmap.isNull():
            self.img.setText("🎮")
            self.img.setStyleSheet("font-size: 100px; background-color: #0d0d0d; color: #222; border-radius: 12px;")
        else:
            self.img.setPixmap(pixmap.scaled(250, 330, Qt.AspectRatioMode.KeepAspectRatioByExpanding, Qt.TransformationMode.SmoothTransformation))
        self.img.setAlignment(Qt.AlignmentFlag.AlignCenter)
        
        display_name = ("⭐️ " if is_fav else "") + self.game_data['name']
        name = QLabel(display_name)
        name.setAlignment(Qt.AlignmentFlag.AlignCenter)
        name.setStyleSheet("font-size: 18px; font-weight: bold; color: #ffffff;")
        name.setWordWrap(True)

        total_sec = self.game_data.get('playtime_seconds', 0)
        h = total_sec // 3600
        m = (total_sec % 3600) // 60
        self.time_lbl = QLabel(f"⏱ {h}ч {m}м")
        self.time_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.time_lbl.setStyleSheet("color: #aaa; font-size: 14px;")

        btn_layout = QHBoxLayout()
        run_btn = QPushButton("ЗАПУСТИТЬ")
        run_btn.setFixedHeight(45)
        run_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        run_btn.clicked.connect(self.run_game)
        run_btn.setStyleSheet("font-size: 14px; font-weight: bold; background-color: #007acc; border: none; border-radius: 8px;")
        
        folder_btn = QPushButton("📁")
        folder_btn.setFixedSize(55, 45)
        folder_btn.clicked.connect(self.open_game_folder)
        folder_btn.setStyleSheet("background-color: #333333; font-size: 20px; border: none; border-radius: 8px;")

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
        except: 
            pass

    def show_context_menu(self, pos):
        menu = QMenu(self)
        menu.setStyleSheet("background-color: #252526; color: white;")
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
                if args:
                    cmd = f'"{full_path}" {args}'
                else:
                    cmd = f'"{full_path}"'
                proc = subprocess.Popen(cmd, shell=False, cwd=working_dir)
                
            self.monitor = ProcessMonitor(proc, start_t, self.game_data)
            self.monitor.finished_playing.connect(self.parent_launcher.finalize_history_session)
            self.monitor.start()
        except Exception as e: 
            QMessageBox.critical(self, "Ошибка", f"Не удалось запустить:\n{e}")

    def mouseMoveEvent(self, e):
        if e.buttons() == Qt.MouseButton.LeftButton:
            drag = QDrag(self)
            mime = QMimeData()
            mime.setText(self.game_data['name'])
            drag.setMimeData(mime)
            drag.exec(Qt.DropAction.MoveAction)

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
        self.tgl.setStyleSheet("background:none; color:#007acc; font-size: 24px; border: none;")
        self.tgl.clicked.connect(self.toggle)
        
        display_title = self.group_name
        if self.group_name == "Без группы":
            display_title = "БЕЗ ГРУППЫ"
            
        lbl = QLabel(display_title)
        color = "#ffcc00" if self.is_favorite else "#007acc"
        lbl.setStyleSheet(f"font-weight: bold; font-size: 24px; color: {color};")
        
        h_lay.addWidget(self.tgl)
        h_lay.addWidget(lbl)
        h_lay.addStretch()
        self.main_vbox.addWidget(self.header)
        
        self.content = QWidget()
        self.grid = QGridLayout(self.content)
        self.grid.setSpacing(25)
        self.main_vbox.addWidget(self.content)

    def refresh_cards(self, filter_text=""):
        while self.grid.count(): 
            w = self.grid.takeAt(0).widget()
            if w: 
                w.deleteLater()
                
        c = 0
        r = 0
        visible_count = 0
        for g in self.games:
            if filter_text.lower() in g['name'].lower():
                self.grid.addWidget(GameCard(g, self.parent_launcher, self.group_name), r, c)
                c += 1
                visible_count += 1
                if c > 3: 
                    c = 0
                    r += 1
        self.setVisible(visible_count > 0)

    def toggle(self):
        self.is_collapsed = not self.is_collapsed
        self.content.setVisible(not self.is_collapsed)
        self.tgl.setText("▶" if self.is_collapsed else "▼")

    def show_group_menu(self, pos):
        menu = QMenu(self)
        r_act = QAction("✏️ Переименовать", self)
        d_act = QAction("❌ Удалить группу", self)
        r_act.triggered.connect(lambda: self.parent_launcher.rename_group(self.group_name))
        d_act.triggered.connect(lambda: self.parent_launcher.delete_group_confirm(self.group_name))
        menu.addAction(r_act)
        menu.addAction(d_act)
        menu.exec(self.header.mapToGlobal(pos))

    def dragEnterEvent(self, e): 
        e.accept()
        
    def dragMoveEvent(self, e):
        e.accept()
        
    def dropEvent(self, e): 
        self.parent_launcher.move_game_to_group(e.mimeData().text(), self.group_name)

# --- ГЛАВНОЕ ОКНО ---
class GORLauncher(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("GOR Launcher PRO v3.0")
        self.setMinimumSize(1300, 950)
        self.data_file = "games_data.json"
        
        self.sunshine_dir = os.path.join(os.getcwd(), "Sunshine")
        self.sunshine_exe = os.path.join(self.sunshine_dir, "sunshine.exe")
        self.apps_json_path = os.path.join(self.sunshine_dir, "config", "apps.json")
        
        self.load_data()
        self.init_ui()

    def sync_games_with_sunshine(self):
        try:
            all_games = self.games_info["standalone"][:]
            for grp in self.games_info["groups"].values():
                all_games.extend(grp)
            
            covers_dir = os.path.join(self.sunshine_dir, "covers")
            os.makedirs(covers_dir, exist_ok=True)
            
            sunshine_apps = []
            for g in all_games:
                icon_path = g.get("icon", "")
                
                if icon_path and os.path.exists(icon_path):
                    if not icon_path.lower().endswith('.png'):
                        try:
                            safe_name = "".join([c for c in g["name"] if c.isalnum() or c in (' ', '_', '-')]).strip()
                            new_icon_path = os.path.join(covers_dir, f"{safe_name}.png")
                            pixmap = QPixmap(icon_path)
                            if not pixmap.isNull():
                                pixmap.save(new_icon_path, "PNG")
                                icon_path = new_icon_path
                        except:
                            pass
                    icon_path = os.path.normpath(icon_path).replace("\\", "/")
                else:
                    icon_path = ""

                app_entry = {
                    "name": g["name"],
                    "cmd": os.path.normpath(g["path"]).replace("\\", "/"),
                    "working-dir": os.path.normpath(os.path.dirname(g["path"])).replace("\\", "/"),
                    "auto-detach": True,
                    "image-path": icon_path
                }
                if g.get("args"):
                    app_entry["cmd"] = f'"{app_entry["cmd"]}" {g["args"]}'
                sunshine_apps.append(app_entry)
            
            new_config = {
                "env": {},
                "apps": sunshine_apps
            }
            
            os.makedirs(os.path.dirname(self.apps_json_path), exist_ok=True)
            with open(self.apps_json_path, 'w', encoding='utf-8') as f:
                json.dump(new_config, f, indent=4, ensure_ascii=False)
            
            try:
                os.system("taskkill /f /im sunshine.exe")
            except:
                pass
            time.sleep(1.5)
            
            if os.path.exists(self.sunshine_exe):
                subprocess.Popen([self.sunshine_exe], cwd=self.sunshine_dir)
            else:
                subprocess.Popen(["sunshine.exe"])
                
            QMessageBox.information(self, "Успех", "Sunshine синхронизирован и перезапущен!")
        except Exception as e:
            QMessageBox.critical(self, "Ошибка", f"Не удалось обновить Sunshine: {e}")

    def change_sunshine_creds_dialog(self):
        user, ok1 = QInputDialog.getText(self, "Sunshine Авторизация", "Введите НОВЫЙ ЛОГИН для веб-панели:")
        if not ok1 or not user:
            return
            
        passwd, ok2 = QInputDialog.getText(self, "Sunshine Авторизация", "Введите НОВЫЙ ПАРОЛЬ:", QLineEdit.EchoMode.Password)
        if not ok2 or not passwd:
            return
            
        try:
            try:
                os.system("taskkill /f /im sunshine.exe")
            except:
                pass
            time.sleep(1.5)
            
            if os.path.exists(self.sunshine_exe):
                subprocess.run([self.sunshine_exe, "--creds", user, passwd], cwd=self.sunshine_dir)
                subprocess.Popen([self.sunshine_exe], cwd=self.sunshine_dir)
            else:
                subprocess.run(["sunshine.exe", "--creds", user, passwd])
                subprocess.Popen(["sunshine.exe"])
                
            QMessageBox.information(self, "Успех", "Логин и пароль Sunshine успешно изменены!\nСервис перезапущен.")
        except Exception as e:
            QMessageBox.critical(self, "Ошибка", f"Не удалось изменить данные авторизации: {e}")

    def load_data(self):
        if os.path.exists(self.data_file):
            try:
                with open(self.data_file, 'r', encoding='utf-8') as f: 
                    self.games_info = json.load(f)
            except: 
                self.games_info = {"groups": {}, "standalone": [], "history": []}
        else: 
            self.games_info = {"groups": {}, "standalone": [], "history": []}
            
        if "history" not in self.games_info: 
            self.games_info["history"] = []

    def save_data(self):
        with open(self.data_file, 'w', encoding='utf-8') as f: 
            json.dump(self.games_info, f, indent=4)

    def init_ui(self):
        self.setStyleSheet("""
            QMainWindow { background-color: #0a0a0a; }
            QWidget { background-color: #0a0a0a; color: #f0f0f0; }
            QTabWidget::pane { border: 1px solid #333; background: #0a0a0a; }
            QTabBar::tab { background: #1a1a1a; padding: 15px 30px; margin: 2px; border-radius: 8px 8px 0 0; min-width: 150px; }
            QTabBar::tab:selected { background: #007acc; font-weight: bold; }
            QPushButton { background-color: #1a1a1a; border-radius: 12px; padding: 10px; color: white; border: 1px solid #333; }
            QPushButton:hover { background-color: #007acc; }
            QFrame#GameCard, QFrame#HistoryCard { background-color: #141414; border: 1px solid #222; border-radius: 20px; }
            QFrame#GameCard:hover, QFrame#HistoryCard:hover { border: 2px solid #007acc; }
        """)
        
        central = QWidget()
        self.setCentralWidget(central)
        self.main_lay = QVBoxLayout(central)
        
        header = QHBoxLayout()
        title = QLabel("GOR UNIVERSAL")
        title.setStyleSheet("font-size: 28px; font-weight: bold; color: #007acc;")
        
        self.stats_lbl = QLabel()
        self.stats_lbl.setStyleSheet("color: #888; font-size: 14px; background: #111; padding: 10px; border-radius: 10px;")
        
        self.search_bar = QLineEdit()
        self.search_bar.setPlaceholderText("🔍 Поиск по библиотеке...")
        self.search_bar.setStyleSheet("background: #1a1a1a; border-radius: 15px; padding: 8px 20px; border: 1px solid #333;")
        self.search_bar.setFixedWidth(300)
        self.search_bar.textChanged.connect(self.refresh_list)
        
        header.addWidget(title)
        header.addStretch()
        header.addWidget(self.stats_lbl)
        header.addWidget(self.search_bar)
        self.main_lay.addLayout(header)

        self.tabs = QTabWidget()
        self.main_lay.addWidget(self.tabs)

        self.lib_tab = QWidget()
        self.lib_lay = QVBoxLayout(self.lib_tab)
        tool_lay = QHBoxLayout()
        
        btn_add = QPushButton("➕ ДОБАВИТЬ ИГРУ")
        btn_add.clicked.connect(self.add_game_dialog)
        
        btn_grp = QPushButton("📁 НОВАЯ ГРУППА")
        btn_grp.clicked.connect(self.add_group)
        
        btn_sync = QPushButton("🔄 СИНХРОНИЗИРОВАТЬ SUNSHINE")
        btn_sync.clicked.connect(self.sync_games_with_sunshine)
        
        btn_creds = QPushButton("🔐 СМЕНИТЬ ПАРОЛЬ SUNSHINE")
        btn_creds.clicked.connect(self.change_sunshine_creds_dialog)
        
        tool_lay.addWidget(btn_add)
        tool_lay.addWidget(btn_grp)
        tool_lay.addWidget(btn_sync)
        tool_lay.addWidget(btn_creds)
        tool_lay.addStretch()
        self.lib_lay.addLayout(tool_lay)
        
        self.scroll_lib = QScrollArea()
        self.scroll_lib.setWidgetResizable(True)
        self.scroll_lib.setStyleSheet("border:none;")
        
        self.lib_cont = QWidget()
        self.lib_scroll_lay = QVBoxLayout(self.lib_cont)
        self.lib_scroll_lay.setAlignment(Qt.AlignmentFlag.AlignTop)
        self.scroll_lib.setWidget(self.lib_cont)
        self.lib_lay.addWidget(self.scroll_lib)
        self.tabs.addTab(self.lib_tab, "📚 БИБЛИОТЕКА")

        self.fav_tab = QWidget()
        self.fav_lay = QVBoxLayout(self.fav_tab)
        
        self.scroll_fav = QScrollArea()
        self.scroll_fav.setWidgetResizable(True)
        self.scroll_fav.setStyleSheet("border:none;")
        
        self.fav_cont = QWidget()
        self.fav_grid = QGridLayout(self.fav_cont)
        self.fav_grid.setSpacing(25)
        self.fav_grid.setAlignment(Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignLeft)
        self.scroll_fav.setWidget(self.fav_cont)
        self.fav_lay.addWidget(self.scroll_fav)
        self.tabs.addTab(self.fav_tab, "⭐️ ИЗБРАННОЕ")

        self.hist_tab = QWidget()
        self.hist_lay = QVBoxLayout(self.hist_tab)
        hist_tool = QHBoxLayout()
        
        btn_clear = QPushButton("🗑️ ОЧИСТИТЬ ИСТОРИЮ")
        btn_clear.clicked.connect(self.clear_history_confirm)
        hist_tool.addStretch()
        hist_tool.addWidget(btn_clear)
        self.hist_lay.addLayout(hist_tool)
        
        self.scroll_hist = QScrollArea()
        self.scroll_hist.setWidgetResizable(True)
        self.scroll_hist.setStyleSheet("border:none;")
        
        self.hist_cont = QWidget()
        self.hist_grid = QGridLayout(self.hist_cont)
        self.hist_grid.setSpacing(25)
        self.hist_grid.setAlignment(Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignLeft)
        self.scroll_hist.setWidget(self.hist_cont)
        self.hist_lay.addWidget(self.scroll_hist)
        self.tabs.addTab(self.hist_tab, "📜 ИСТОРИЯ")

        self.update_stats()
        self.refresh_list()

    def finalize_history_session(self, seconds, game_data):
        all_games = self.games_info["standalone"][:]
        for g_list in self.games_info["groups"].values(): 
            all_games.extend(g_list)
            
        for g in all_games:
            if g['name'] == game_data['name']:
                g['playtime_seconds'] = g.get('playtime_seconds', 0) + seconds
                break
                
        now = datetime.now().strftime("%d.%m.%Y %H:%M")
        entry = {
            "name": game_data['name'], 
            "icon": game_data.get('icon', ''), 
            "date": now, 
            "session_time": seconds
        }
        self.games_info["history"].insert(0, entry) 
        if len(self.games_info["history"]) > 100: 
            self.games_info["history"].pop()
            
        self.save_data()
        self.update_stats()
        self.refresh_list()

    def clear_history_confirm(self):
        ret = QMessageBox.question(self, 'Очистка', "Удалить всю историю?", QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
        if ret == QMessageBox.StandardButton.Yes:
            self.games_info["history"] = []
            self.save_data()
            self.refresh_list()

    def delete_history_entry(self, index):
        if 0 <= index < len(self.games_info["history"]):
            self.games_info["history"].pop(index)
            self.save_data()
            self.refresh_list()

    def update_stats(self):
        total_sec = 0
        count = 0
        all_games = self.games_info["standalone"][:]
        for g_list in self.games_info["groups"].values(): 
            all_games.extend(g_list)
            
        for g in all_games: 
            total_sec += g.get('playtime_seconds', 0)
            count += 1
            
        h = total_sec // 3600
        m = (total_sec % 3600) // 60
        self.stats_lbl.setText(f"📊 Игр: {count} | ⌛ Всего: {h}ч {m}м")

    def refresh_list(self):
        filter_text = self.search_bar.text().lower()
        while self.lib_scroll_lay.count():
            child = self.lib_scroll_lay.takeAt(0)
            if child.widget(): 
                child.widget().deleteLater()
                
        all_games = self.games_info["standalone"][:]
        for g_list in self.games_info["groups"].values(): 
            all_games.extend(g_list)
            
        while self.fav_grid.count():
            w = self.fav_grid.takeAt(0).widget()
            if w: 
                w.deleteLater()
                
        fav_list = [g for g in all_games if g.get('favorite')]
        c = 0
        r = 0
        for g in fav_list:
            self.fav_grid.addWidget(GameCard(g, self), r, c)
            c += 1
            if c > 4: 
                c = 0
                r += 1
                
        while self.hist_grid.count():
            w = self.hist_grid.takeAt(0).widget()
            if w: 
                w.deleteLater()
                
        for i, entry in enumerate(self.games_info["history"]):
            self.hist_grid.addWidget(HistoryCard(entry, i, self), i // 5, i % 5)
            
        for gn, gg in self.games_info["groups"].items():
            grp_w = GroupWidget(gn, gg, self)
            self.lib_scroll_lay.addWidget(grp_w)
            grp_w.refresh_cards(filter_text)
            
        st_w = GroupWidget("Без группы", self.games_info["standalone"], self)
        self.lib_scroll_lay.addWidget(st_w)
        st_w.refresh_cards(filter_text)

    def add_game_dialog(self):
        dlg = GameEditDialog(self, groups=list(self.games_info["groups"].keys()))
        if dlg.exec():
            d = dlg.get_data()
            t = d.pop('group')
            if t == "Без группы": 
                self.games_info["standalone"].append(d)
            else: 
                self.games_info["groups"][t].append(d)
            self.save_data()
            self.refresh_list()
            self.update_stats()

    def edit_game(self, old, grp):
        self.delete_game(old, grp, refresh=False)
        dlg = GameEditDialog(self, game_data=old, groups=list(self.games_info["groups"].keys()), current_group=grp or "Без группы")
        if dlg.exec():
            d = dlg.get_data()
            t = d.pop('group')
            if t == "Без группы": 
                self.games_info["standalone"].append(d)
            else: 
                self.games_info["groups"][t].append(d)
        else:
            if grp and grp in self.games_info["groups"]: 
                self.games_info["groups"][grp].append(old)
            else: 
                self.games_info["standalone"].append(old)
        self.save_data()
        self.refresh_list()
        self.update_stats()

    def delete_game_confirm(self, game, group):
        ret = QMessageBox.question(self, 'Удаление', f"Удалить '{game['name']}'?", QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
        if ret == QMessageBox.StandardButton.Yes: 
            self.delete_game(game, group)

    def delete_game(self, game, group, refresh=True):
        if group and group != "Без группы":
            lst = self.games_info["groups"].get(group, self.games_info["standalone"])
        else:
            lst = self.games_info["standalone"]
            
        for i, g in enumerate(lst):
            if g["name"] == game["name"]: 
                lst.pop(i)
                break
                
        if refresh: 
            self.save_data()
            self.refresh_list()
            self.update_stats()

    def rename_group(self, old):
        n, ok = QInputDialog.getText(self, "Переименовать", "Новое имя:", text=old)
        if ok and n and n != old:
            self.games_info["groups"][n] = self.games_info["groups"].pop(old)
            self.save_data()
            self.refresh_list()

    def add_group(self):
        n, ok = QInputDialog.getText(self, "Группа", "Имя:")
        if ok and n and n not in self.games_info["groups"]:
            self.games_info["groups"][n] = []
            self.save_data()
            self.refresh_list()

    def delete_group_confirm(self, name):
        ret = QMessageBox.question(self, 'Удаление', f"Удалить группу '{name}'?", QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
        if ret == QMessageBox.StandardButton.Yes:
            self.games_info["standalone"].extend(self.games_info["groups"].pop(name))
            self.save_data()
            self.refresh_list()

    def move_game_to_group(self, name, target):
        game = None
        for i, g in enumerate(self.games_info["standalone"]):
            if g["name"] == name: 
                game = self.games_info["standalone"].pop(i)
                break
                
        if not game:
            for gn in self.games_info["groups"]:
                for i, g in enumerate(self.games_info["groups"][gn]):
                    if g["name"] == name: 
                        game = self.games_info["groups"][gn].pop(i)
                        break
                        
        if game:
            if target and target != "Без группы" and target != "БЕЗ ГРУППЫ": 
                self.games_info["groups"][target].append(game)
            else: 
                self.games_info["standalone"].append(game)
            self.save_data()
            self.refresh_list()

if __name__ == "__main__":
    app = QApplication(sys.argv)
    app.setStyle("Fusion")
    ex = GORLauncher()
    ex.show()
    sys.exit(app.exec())
