import sys
import json
import os
import subprocess
import time
import platform
import uuid
import shlex
from datetime import datetime
from functools import lru_cache
from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, 
    QPushButton, QFileDialog, QLineEdit, QScrollArea, QFrame, 
    QLabel, QInputDialog, QGridLayout, QDialog, QComboBox, QMenu, QMessageBox, QCheckBox, QTabWidget
)
from PyQt6.QtCore import Qt, QSize, QMimeData, QThread, pyqtSignal, QTimer
from PyQt6.QtGui import QKeySequence, QShortcut, QIcon, QPixmap, QDrag, QAction

from style_loader import apply_global_style
from fortune_wheel import FortuneWheelDialog
from lang_loader import tr, available_languages, current_language, set_language

NO_GROUP_KEY = "Без группы"  # внутренний ключ данных - НЕ переводится, чтобы не ломать games_data.json

# Флаг для subprocess.*, чтобы служебные консольные команды (tasklist, taskkill)
# не открывали и не мигали окном терминала на Windows. На других ОС просто 0.
NO_WINDOW_FLAGS = subprocess.CREATE_NO_WINDOW if platform.system() == 'Windows' else 0

def _find_favicon_path():
    """Ищет favicon.ico рядом со скриптом, на уровень выше и в рабочей папке.
    Если нигде не найден - возвращает путь рядом со скриптом (по умолчанию)
    и выводит предупреждение в консоль, чтобы было видно, что иконка не найдена."""
    script_dir = os.path.dirname(os.path.abspath(__file__))
    candidates = []
    if getattr(sys, "frozen", False):
        candidates.append(os.path.dirname(sys.executable))
    candidates.append(script_dir)
    candidates.append(os.getcwd())
    candidates.append(os.path.dirname(script_dir))
    for d in candidates:
        p = os.path.join(d, "favicon.ico")
        if os.path.exists(p):
            return p
    print(f"[GorLauncher] favicon.ico не найден. Проверенные папки: {candidates}")
    return os.path.join(script_dir, "favicon.ico")

@lru_cache(maxsize=512)
def load_pixmap_cached(path):
    """Кэширует QPixmap по пути к файлу, чтобы не читать иконку с диска
    заново при каждом refresh_list."""
    return QPixmap(path) if path else QPixmap()

# --- УНИВЕРСАЛЬНЫЙ ЗАПУСК ФАЙЛОВ ---
def universal_launch(path):
    if platform.system() == 'Windows':
        os.startfile(path)
    elif platform.system() == 'Darwin': # macOS
        subprocess.call(['open', path])
    else: # Linux
        subprocess.call(['xdg-open', path])

# --- УНИВЕРСАЛЬНЫЙ ЗАПУСК РЕДАКТОРОВ (EXE или PY) ---
def run_editor_process(script_name, args=None):
    exe_name = f"{script_name}.exe"
    py_name = f"{script_name}.py"
    
    if os.path.exists(exe_name):
        return subprocess.Popen([exe_name] + (args if args else []))
    else:
        if sys.executable.lower().endswith('.exe') and not 'python' in os.path.basename(sys.executable).lower():
            return subprocess.Popen(["python", py_name] + (args if args else []))
        else:
            return subprocess.Popen([sys.executable, py_name] + (args if args else []))

# --- ПОТОК ДЛЯ МОНИТОРИНГА ПРОЦЕССА ИГРЫ ---
class ProcessMonitor(QThread):
    finished_playing = pyqtSignal(int, dict) 

    def __init__(self, process, start_time, game_data):
        super().__init__()
        self.process = process
        self.start_time = start_time
        self.game_data = game_data

    def run(self):
        try:
            self.process.wait()
        except Exception:
            pass
        
        time.sleep(2)
        target_name = os.path.basename(self.game_data.get('path', '')).lower()
        
        if target_name:
            while True:
                running = False
                try:
                    if platform.system() == 'Windows':
                        output = subprocess.check_output(['tasklist', '/FO', 'CSV'], universal_newlines=True, encoding='cp1251', errors='ignore', creationflags=NO_WINDOW_FLAGS)
                        if target_name in output.lower():
                            running = True
                    else:
                        output = subprocess.check_output(['ps', '-e', '-o', 'comm='], universal_newlines=True, errors='ignore')
                        if target_name in output.lower():
                            running = True
                except Exception:
                    running = False
                
                if not running:
                    break
                time.sleep(5)

        duration = int(time.time() - self.start_time)
        self.finished_playing.emit(duration, self.game_data)

# --- ПОТОК ДЛЯ МОНИТОРИНГА ЗАКРЫТИЯ РЕДАКТОРОВ ---
class EditorMonitor(QThread):
    editor_closed = pyqtSignal()

    def __init__(self, process):
        super().__init__()
        self.process = process

    def run(self):
        if self.process:
            self.process.wait()
            self.editor_closed.emit()

# --- КАРТОЧКА ИСТОРИИ ---
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

# --- КАРТОЧКА ИГРЫ ---
class GameCard(QFrame):
    def __init__(self, game_data, parent_launcher, group_name=None):
        super().__init__()
        self.game_data = game_data
        self.parent_launcher = parent_launcher
        self.group_name = group_name
        self.setFixedSize(280, 520) 
        self.setObjectName("GameCard")
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.customContextMenuRequested.connect(self.show_context_menu)
        
        self.running_seconds = 0
        self.is_paused = False
        self.is_running = False
        self.active_process = None
        self.monitor = None

        self.game_timer = QTimer(self)
        self.game_timer.timeout.connect(self.update_live_timer)
        
        self.init_ui()
        
        gid = self.game_data.get('id') or self.game_data['name']
        if gid in self.parent_launcher.active_sessions:
            session = self.parent_launcher.active_sessions[gid]
            self.active_process = session['process']
            self.monitor = session['monitor']
            self.running_seconds = int(time.time() - session['start_time'])
            
            self.is_running = True
            self.run_btn.setText(tr("game_card.stop"))
            self.run_btn.setStyleSheet("background-color: #d9534f; color: white;")
            self.pause_timer_btn.setVisible(True)
            self.game_timer.start(1000)

    def init_ui(self):
        vbox = QVBoxLayout(self)
        vbox.setContentsMargins(15, 15, 15, 15)
        vbox.setSpacing(12)
        
        self.img = QLabel()
        self.img.setObjectName("GameCardImage")
        self.img.setFixedSize(250, 330)
        is_fav = self.game_data.get('favorite', False)
        self.img.setProperty("favorite", is_fav)

        pixmap = load_pixmap_cached(self.game_data.get('icon', ''))
        if pixmap.isNull():
            self.img.setText("🎮")
            self.img.setProperty("empty", True)
        else:
            self.img.setPixmap(pixmap.scaled(250, 330, Qt.AspectRatioMode.KeepAspectRatioByExpanding, Qt.TransformationMode.SmoothTransformation))
        self.img.setAlignment(Qt.AlignmentFlag.AlignCenter)
        
        display_name = ("⭐️ " if is_fav else "") + self.game_data['name']
        name = QLabel(display_name)
        name.setObjectName("GameCardName")
        name.setAlignment(Qt.AlignmentFlag.AlignCenter)
        name.setWordWrap(True)

        time_layout = QHBoxLayout()
        time_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        time_layout.setSpacing(8)
        
        total_sec = self.game_data.get('playtime_seconds', 0)
        h, m = total_sec // 3600, (total_sec % 3600) // 60
        self.time_lbl = QLabel(tr("game_card.time_static", h=h, m=m))
        self.time_lbl.setObjectName("GameCardTime")
        self.time_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)

        self.pause_timer_btn = QPushButton("⏸️")
        self.pause_timer_btn.setObjectName("PauseTimerBtn")
        self.pause_timer_btn.setFixedSize(36, 26)
        self.pause_timer_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.pause_timer_btn.setVisible(False)
        self.pause_timer_btn.setStyleSheet("""
            QPushButton#PauseTimerBtn {
                background-color: #222222;
                color: #ffffff;
                border: 1px solid #444444;
                border-radius: 6px;
                font-size: 14px;
                padding: 0px;
                margin: 0px;
            }
            QPushButton#PauseTimerBtn:hover {
                background-color: #333333;
                border: 1px solid #007acc;
            }
            QPushButton#PauseTimerBtn:pressed {
                background-color: #111111;
            }
        """)
        self.pause_timer_btn.clicked.connect(self.toggle_timer_pause)

        time_layout.addWidget(self.time_lbl)
        time_layout.addWidget(self.pause_timer_btn)

        btn_layout = QHBoxLayout()
        self.run_btn = QPushButton(tr("game_card.run"))
        self.run_btn.setObjectName("RunGameBtn")
        self.run_btn.setFixedHeight(45)
        self.run_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.run_btn.clicked.connect(self.handle_main_button)

        folder_btn = QPushButton("📁")
        folder_btn.setObjectName("OpenFolderBtn")
        folder_btn.setFixedSize(55, 45)
        folder_btn.clicked.connect(self.open_game_folder)

        btn_layout.addWidget(self.run_btn)
        btn_layout.addWidget(folder_btn)

        vbox.addWidget(self.img, alignment=Qt.AlignmentFlag.AlignCenter)
        vbox.addWidget(name)
        vbox.addLayout(time_layout)
        vbox.addStretch()
        vbox.addLayout(btn_layout)

    def open_game_folder(self):
        try:
            exe_path = self.game_data['path']
            if os.path.exists(exe_path):
                universal_launch(os.path.dirname(os.path.abspath(exe_path)))
        except Exception as e:
            print(f"Не удалось открыть папку игры: {e}")

    def show_context_menu(self, pos):
        menu = QMenu(self)
        if not self.is_running:
            fav_text = tr("game_card.remove_favorite") if self.game_data.get('favorite') else tr("game_card.add_favorite")
            fav_act = QAction(fav_text, self)
            fav_act.triggered.connect(self.toggle_favorite)
            menu.addAction(fav_act)
            menu.addSeparator()
            e_act = QAction(tr("game_card.edit"), self)
            e_act.triggered.connect(lambda: self.parent_launcher.edit_game(self.game_data, self.group_name))
            menu.addAction(e_act)
            d_act = QAction(tr("game_card.delete"), self)
            d_act.triggered.connect(lambda: self.parent_launcher.delete_game_confirm(self.game_data, self.group_name))
            menu.addAction(d_act)
            menu.addSeparator()
        copy_act = QAction(tr("game_card.copy_path"), self)
        copy_act.triggered.connect(self.copy_path_to_clipboard)
        menu.addAction(copy_act)
        menu.exec(self.mapToGlobal(pos))

    def copy_path_to_clipboard(self):
        QApplication.clipboard().setText(self.game_data.get('path', ''))

    def toggle_favorite(self):
        self.game_data['favorite'] = not self.game_data.get('favorite', False)
        self.parent_launcher.save_data()
        self.parent_launcher.refresh_list()

    def keyPressEvent(self, e):
        if e.key() in (Qt.Key.Key_Return, Qt.Key.Key_Enter):
            self.handle_main_button()
        elif e.key() == Qt.Key.Key_Space:
            self.toggle_favorite()
        elif e.key() == Qt.Key.Key_Delete:
            self.parent_launcher.delete_game_confirm(self.game_data, self.group_name)
        elif e.key() == Qt.Key.Key_E:
            self.parent_launcher.edit_game(self.game_data, self.group_name)
        elif e.key() == Qt.Key.Key_F:
            self.open_game_folder()
        elif e.key() in (Qt.Key.Key_Right, Qt.Key.Key_Down):
            self.focusNextChild()
        elif e.key() in (Qt.Key.Key_Left, Qt.Key.Key_Up):
            self.focusPreviousChild()
        else:
            super().keyPressEvent(e)

    def handle_main_button(self):
        if self.is_running:
            if self.active_process:
                try:
                    if platform.system() == 'Windows':
                        subprocess.run(
                            ["taskkill", "/F", "/T", "/PID", str(self.active_process.pid)],
                            capture_output=True,
                            creationflags=NO_WINDOW_FLAGS
                        )
                    else:
                        self.active_process.terminate()
                except Exception as e:
                    print(f"Ошибка принудительного закрытия процесса: {e}")
            
            self.game_timer.stop()
            self.is_paused = False
            self.is_running = False
            self.pause_timer_btn.setText("⏸️")
            self.pause_timer_btn.setVisible(False)
            self.run_btn.setText(tr("game_card.run"))
            self.run_btn.setStyleSheet("")
            
            total_sec = self.game_data.get('playtime_seconds', 0)
            h, m = total_sec // 3600, (total_sec % 3600) // 60
            self.time_lbl.setText(tr("game_card.time_static", h=h, m=m))
            
            gid = self.game_data.get('id') or self.game_data['name']
            if gid in self.parent_launcher.active_sessions:
                del self.parent_launcher.active_sessions[gid]
            return

        try: 
            path = self.game_data['path']
            if path.lower().endswith(('.exe', '.bat')):
                full_path = os.path.abspath(path)
                working_dir = os.path.dirname(full_path)
                args = self.game_data.get('args', '')
                start_t = time.time()
                
                cmd_list = [full_path]
                if args:
                    cmd_list.extend(shlex.split(args))
                self.active_process = subprocess.Popen(cmd_list, cwd=working_dir)
                
                self.is_running = True
                self.run_btn.setText(tr("game_card.stop"))
                self.run_btn.setStyleSheet("background-color: #d9534f; color: white;")
                self.running_seconds = 0
                self.is_paused = False
                self.pause_timer_btn.setText("⏸️")
                self.pause_timer_btn.setVisible(True)
                self.game_timer.start(1000)

                self.monitor = ProcessMonitor(self.active_process, start_t, self.game_data)
                self.monitor.finished_playing.connect(self.on_game_finished)
                self.monitor.start()

                gid = self.game_data.get('id') or self.game_data['name']
                self.parent_launcher.active_sessions[gid] = {
                    'process': self.active_process,
                    'monitor': self.monitor,
                    'start_time': start_t,
                    'card': self
                }
            else:
                universal_launch(path)
        except Exception as e: 
            QMessageBox.critical(self, tr("common.error"), tr("game_card.launch_error", error=e))

    def update_live_timer(self):
        if not self.is_paused:
            self.running_seconds += 1
            h = self.running_seconds // 3600
            m = (self.running_seconds % 3600) // 60
            s = self.running_seconds % 60
            self.time_lbl.setText(f"⏳ {h:02d}:{m:02d}:{s:02d}")

    def toggle_timer_pause(self):
        self.is_paused = not self.is_paused
        if self.is_paused:
            self.pause_timer_btn.setText("▶️")
        else:
            self.pause_timer_btn.setText("⏸️")

    def on_game_finished(self, duration, game_data):
        self.game_timer.stop()
        self.is_paused = False
        self.is_running = False
        self.pause_timer_btn.setText("⏸️")
        self.pause_timer_btn.setVisible(False)
        self.run_btn.setText(tr("game_card.run"))
        self.run_btn.setStyleSheet("")
        
        gid = self.game_data.get('id') or self.game_data['name']
        if gid in self.parent_launcher.active_sessions:
            del self.parent_launcher.active_sessions[gid]

        self.parent_launcher.finalize_history_session(duration, game_data)

    def mouseDoubleClickEvent(self, e):
        if e.button() == Qt.MouseButton.LeftButton:
            self.handle_main_button()
        else:
            super().mouseDoubleClickEvent(e)

    def mouseMoveEvent(self, e):
        if e.buttons() == Qt.MouseButton.LeftButton:
            drag = QDrag(self); mime = QMimeData()
            mime.setText(self.game_data.get('id') or self.game_data['name'])
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

    def dragEnterEvent(self, e): e.accept()
    def dropEvent(self, e): self.parent_launcher.move_game_to_group(e.mimeData().text(), self.group_name)


with open("version.json", "r", encoding="utf-8") as f:
    version = json.load(f)["version"]


# --- ГЛАВНОЕ ОКНО ---
class GORLauncher(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle(tr("launcher.window_title") + "   " + version)
        self.setWindowIcon(QIcon(_find_favicon_path()))
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
        proc = run_editor_process("game_editor")
        monitor = EditorMonitor(proc)
        monitor.editor_closed.connect(self.on_editor_closed)
        self._wheel_monitors.append(monitor)
        monitor.start()

    def edit_game(self, game_data, group_name):
        g_name = group_name if group_name else NO_GROUP_KEY
        gid = game_data.get("id", "")
        proc = run_editor_process("game_editor", [game_data['name'], g_name, gid])
        monitor = EditorMonitor(proc)
        monitor.editor_closed.connect(self.on_editor_closed)
        self._wheel_monitors.append(monitor)
        monitor.start()

    def on_editor_closed(self):
        self.load_data()
        self.refresh_list()

    def add_group(self):
        proc = run_editor_process("group_editor")
        monitor = EditorMonitor(proc)
        monitor.editor_closed.connect(self.on_editor_closed)
        self._wheel_monitors.append(monitor)
        monitor.start()

    def edit_group(self, group_name):
        proc = run_editor_process("group_editor", [group_name])
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
            run_editor_process("sunshine_control")
        except Exception as e:
            QMessageBox.critical(self, tr("sunshine_error.title"), tr("sunshine_error.text", error=e))

    def open_exporter(self):
        try:
            run_editor_process("exporter_editor")
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
    app.setWindowIcon(QIcon(_find_favicon_path()))
    apply_global_style(app)
    launcher = GORLauncher()
    launcher.show()
    sys.exit(app.exec())