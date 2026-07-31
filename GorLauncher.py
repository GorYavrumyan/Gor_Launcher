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

@lru_cache(maxsize=512)
def load_pixmap_cached(path):
    """Кэширует QPixmap по пути к файлу, чтобы не читать иконку с диска
    заново при каждом refresh_list (поиск, избранное, история и т.д.)."""
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

# --- ПОТОК ДЛЯ МОНИТОРИНГЕ ПРОЦЕССА ИГРЫ ---
class ProcessMonitor(QThread):
    finished_playing = pyqtSignal(int, dict) 

    def __init__(self, process, start_time, game_data):
        super().__init__()
        self.process = process
        self.start_time = start_time
        self.game_data = game_data

    def run(self):
        # Интеллектуальный мониторинг: если процесс сразу завершается (лаунчер-обертка),
        # ожидаем появление дочернего/нового процесса игры в системе, либо держим сессию активной,
        # чтобы лаунчер не думал, что игра закрылась.
        try:
            self.process.wait()
        except Exception:
            pass
        
        # Если это был быстрый файл-лаунчер (файл 1 закрылся, передав управление файлу 2),
        # даем системе время на запуск реального игрового процесса и мониторим его наличие.
        time.sleep(2)
        target_name = os.path.basename(self.game_data.get('path', '')).lower()
        
        if target_name:
            while True:
                running = False
                try:
                    if platform.system() == 'Windows':
                        output = subprocess.check_output(['tasklist', '/FO', 'CSV'], universal_newlines=True, encoding='cp1251', errors='ignore')
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

# --- ПОТОК ДЛЯ МОНИТОРИНГЕ ЗАКРЫТИЯ РЕДАКТОРОВ ---
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
        
        date_lbl = QLabel(f"📅 {self.entry['date']}")
        date_lbl.setObjectName("HistoryCardDate")
        
        dur = self.entry.get('session_time', 0)
        h, m = dur // 3600, (dur % 3600) // 60
        time_lbl = QLabel(f"⌛ Сессия: {h}ч {m}м")
        time_lbl.setObjectName("HistoryCardTime")

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
            
            self.run_btn.setText("ОТКЛЮЧИТЬ")
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
        self.time_lbl = QLabel(f"⏱ {h}ч {m}м")
        self.time_lbl.setObjectName("GameCardTime")
        self.time_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)

        # Полностью исправленная кнопка паузы таймера с поддержкой надежного отображения эмодзи и аккуратной высотой
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
        self.run_btn = QPushButton("ЗАПУСТИТЬ")
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
        if self.run_btn.text() == "ОТКЛЮЧИТЬ":
            return
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
        if self.run_btn.text() == "ОТКЛЮЧИТЬ":
            if self.active_process:
                try:
                    if platform.system() == 'Windows':
                        subprocess.run(
                            ["taskkill", "/F", "/T", "/PID", str(self.active_process.pid)],
                            capture_output=True
                        )
                    else:
                        self.active_process.terminate()
                except Exception as e:
                    print(f"Ошибка принудительного закрытия процесса: {e}")
            
            # Возвращаем карточку в исходное состояние
            self.game_timer.stop()
            self.is_paused = False
            self.pause_timer_btn.setText("⏸️")
            self.pause_timer_btn.setVisible(False)
            self.run_btn.setText("ЗАПУСТИТЬ")
            self.run_btn.setStyleSheet("")
            
            total_sec = self.game_data.get('playtime_seconds', 0)
            h, m = total_sec // 3600, (total_sec % 3600) // 60
            self.time_lbl.setText(f"⏱ {h}ч {m}м")
            
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
                
                self.run_btn.setText("ОТКЛЮЧИТЬ")
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
            QMessageBox.critical(self, "Ошибка", f"Не удалось запустить:\n{e}")

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
        self.pause_timer_btn.setText("⏸️")
        self.pause_timer_btn.setVisible(False)
        self.run_btn.setText("ЗАПУСТИТЬ")
        self.run_btn.setStyleSheet("")
        
        gid = self.game_data.get('id') or self.game_data['name']
        if gid in self.parent_launcher.active_sessions:
            del self.parent_launcher.active_sessions[gid]

        self.parent_launcher.finalize_history_session(duration, game_data)

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
        title = QLabel("GOR UNIVERSAL")
        title.setObjectName("AppTitle")
        self.stats_lbl = QLabel()
        self.stats_lbl.setObjectName("StatsLabel")
        
        btn_sunshine = QPushButton("⚙️ SUNSHINE")
        btn_sunshine.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_sunshine.clicked.connect(self.run_sunshine)
        
        btn_exporter = QPushButton("📦 EXPORT")
        btn_exporter.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_exporter.clicked.connect(self.open_exporter)

        btn_wheel = QPushButton("🎡 КОЛЕСО ФОРТУНЫ")
        btn_wheel.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_wheel.clicked.connect(self.open_fortune_wheel)
        
        self.search_bar = QLineEdit()
        self.search_bar.setObjectName("SearchBar")
        self.search_bar.setPlaceholderText("🔍 Поиск по библиотеке...")
        self.search_bar.setFixedWidth(300)
        self.search_timer = QTimer(self)
        self.search_timer.setSingleShot(True)
        self.search_timer.timeout.connect(self.refresh_list)
        self.search_bar.textChanged.connect(lambda: self.search_timer.start(250))
        
        header.addWidget(title)
        header.addStretch()
        header.addWidget(btn_wheel)
        header.addWidget(btn_sunshine)
        header.addWidget(btn_exporter)
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
        self.scroll_lib.setWidget(self.lib_cont); self.lib_lay.addWidget(self.scroll_lib)
        self.tabs.addTab(self.lib_tab, "📚 БИБЛИОТЕКА")
        
        self.fav_tab = QWidget()
        self.fav_lay = QVBoxLayout(self.fav_tab)
        self.scroll_fav = QScrollArea(); self.scroll_fav.setWidgetResizable(True)
        self.fav_cont = QWidget(); self.fav_grid = QGridLayout(self.fav_cont); self.fav_grid.setSpacing(25)
        self.fav_grid.setAlignment(Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignLeft)
        self.scroll_fav.setWidget(self.fav_cont); self.fav_lay.addWidget(self.scroll_fav)
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
        self.scroll_hist.setWidget(self.hist_cont); self.hist_lay.addWidget(self.scroll_hist)
        self.tabs.addTab(self.hist_tab, "📜 ИСТОРИЯ")
        self.update_stats(); self.refresh_list()
        self._setup_shortcuts()

    def _setup_shortcuts(self):
        QShortcut(QKeySequence("Ctrl+F"), self, activated=self.focus_search)
        QShortcut(QKeySequence("Ctrl+N"), self, activated=self.add_game_dialog)
        QShortcut(QKeySequence("Ctrl+G"), self, activated=self.add_group)
        QShortcut(QKeySequence("Ctrl+E"), self, activated=self.open_exporter)
        QShortcut(QKeySequence("Ctrl+Shift+S"), self, activated=self.run_sunshine)
        QShortcut(QKeySequence("Ctrl+Shift+W"), self, activated=self.open_fortune_wheel)
        QShortcut(QKeySequence("F5"), self, activated=self.refresh_list)
        QShortcut(QKeySequence("Ctrl+1"), self, activated=lambda: self.tabs.setCurrentIndex(0))
        QShortcut(QKeySequence("Ctrl+2"), self, activated=lambda: self.tabs.setCurrentIndex(1))
        QShortcut(QKeySequence("Ctrl+3"), self, activated=lambda: self.tabs.setCurrentIndex(2))
        QShortcut(QKeySequence("Ctrl+Tab"), self, activated=self.next_tab)
        QShortcut(QKeySequence("Ctrl+Shift+Tab"), self, activated=self.prev_tab)
        QShortcut(QKeySequence("Ctrl+Home"), self, activated=self.focus_first_card)
        QShortcut(QKeySequence("Escape"), self, activated=self.handle_escape)

    def focus_search(self):
        self.search_bar.setFocus()
        self.search_bar.selectAll()

    def next_tab(self):
        self.tabs.setCurrentIndex((self.tabs.currentIndex() + 1) % self.tabs.count())

    def prev_tab(self):
        self.tabs.setCurrentIndex((self.tabs.currentIndex() - 1) % self.tabs.count())

    def handle_escape(self):
        if self.search_bar.hasFocus() and self.search_bar.text():
            self.search_bar.clear()
        else:
            self.search_bar.clearFocus()
            self.setFocus()

    def focus_first_card(self):
        current = self.tabs.currentWidget()
        if not current:
            return
        cards = current.findChildren(GameCard) + current.findChildren(HistoryCard)
        if cards:
            cards[0].setFocus()

    def run_sunshine(self):
        try: run_editor_process("sunshine_control")
        except Exception as e: QMessageBox.critical(self, "Ошибка", f"Не удалось запустить Sunshine: {e}")

    def open_exporter(self):
        try: run_editor_process("exporter_editor")
        except Exception as e: QMessageBox.critical(self, "Ошибка", f"Не удалось запустить Exporter: {e}")

    def open_fortune_wheel(self):
        dlg = FortuneWheelDialog(
            self,
            json_path=self.data_file,
            launch_callback=self.launch_game_from_wheel,
        )
        dlg.exec()

    def launch_game_from_wheel(self, game_data):
        try:
            path = game_data['path']
            if path.lower().endswith(('.exe', '.bat')):
                full_path = os.path.abspath(path)
                working_dir = os.path.dirname(full_path)
                args = game_data.get('args', '')
                start_t = time.time()
                
                cmd_list = [full_path]
                if args:
                    cmd_list.extend(shlex.split(args))
                proc = subprocess.Popen(cmd_list, cwd=working_dir)
                
                monitor = ProcessMonitor(proc, start_t, game_data)
                monitor.finished_playing.connect(self.finalize_history_session)
                monitor.start()
                self._wheel_monitors.append(monitor)
            else:
                universal_launch(path)
        except Exception as e:
            QMessageBox.critical(self, "Ошибка", f"Не удалось запустить:\n{e}")

    def finalize_history_session(self, seconds, game_data):
        all_games = self.games_info["standalone"][:]
        for g_list in self.games_info["groups"].values(): all_games.extend(g_list)
        gid = game_data.get('id')
        for g in all_games:
            if (gid and g.get('id') == gid) or (not gid and g['name'] == game_data['name']):
                g['playtime_seconds'] = g.get('playtime_seconds', 0) + seconds
                break
        now = datetime.now().strftime("%d.%m.%Y %H:%M")
        entry = {"name": game_data['name'], "icon": game_data.get('icon', ''), "date": now, "session_time": seconds}
        if "history" not in self.games_info: self.games_info["history"] = []
        self.games_info["history"].insert(0, entry) 
        if len(self.games_info["history"]) > 100: self.games_info["history"].pop()
        self.save_data(); self.update_stats(); self.refresh_list()

    def clear_history_confirm(self):
        ret = QMessageBox.question(self, 'Очистка', "Удалить всю историю?", QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
        if ret == QMessageBox.StandardButton.Yes: self.games_info["history"] = []; self.save_data(); self.refresh_list()

    def delete_history_entry(self, index):
        if 0 <= index < len(self.games_info["history"]): self.games_info["history"].pop(index); self.save_data(); self.refresh_list()

    def update_stats(self):
        total_sec = 0; count = 0
        all_games = self.games_info["standalone"][:]
        for g_list in self.games_info["groups"].values(): all_games.extend(g_list)
        for g in all_games: total_sec += g.get('playtime_seconds', 0); count += 1
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

    def on_game_editor_closed(self, *args, **kwargs):
        self.load_data()
        self.refresh_list()
        self.update_stats()

    def on_group_editor_closed(self, *args, **kwargs):
        self.load_data()
        self.refresh_list()

    def add_game_dialog(self):
        try:
            proc = run_editor_process("game_editor")
            self.game_monitor = EditorMonitor(proc)
            self.game_monitor.editor_closed.connect(self.on_game_editor_closed)
            self.game_monitor.start()
        except Exception as e:
            QMessageBox.critical(self, "Ошибка", f"Не удалось запустить редактор:\n{e}")

    def edit_game(self, old, grp):
        try:
            args = [old['name'], grp or "Без группы", old.get('id') or ""]
            proc = run_editor_process("game_editor", args)
            self.game_monitor = EditorMonitor(proc)
            self.game_monitor.editor_closed.connect(self.on_game_editor_closed)
            self.game_monitor.start()
        except Exception as e:
            QMessageBox.critical(self, "Ошибка", f"Не удалось запустить редактор:\n{e}")

    def delete_game_confirm(self, game, group):
        ret = QMessageBox.question(self, 'Удаление', f"Удалить '{game['name']}'?", QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
        if ret == QMessageBox.StandardButton.Yes: self.delete_game(game, group)

    def delete_game(self, game, group, refresh=True):
        lst = self.games_info["groups"].get(group, self.games_info["standalone"]) if group and group != "Без группы" else self.games_info["standalone"]
        gid = game.get("id")
        for i, g in enumerate(lst):
            if (gid and g.get("id") == gid) or (not gid and g["name"] == game["name"]):
                lst.pop(i); break
        if refresh: self.save_data(); self.refresh_list(); self.update_stats()

    def add_group(self):
        try:
            proc = run_editor_process("group_editor")
            self.group_monitor = EditorMonitor(proc)
            self.group_monitor.editor_closed.connect(self.on_group_editor_closed)
            self.group_monitor.start()
        except Exception as e:
            QMessageBox.critical(self, "Ошибка", f"Не удалось запустить редактор групп:\n{e}")

    def edit_group(self, old_name):
        try:
            args = [old_name]
            proc = run_editor_process("group_editor", args)
            self.group_monitor = EditorMonitor(proc)
            self.group_monitor.editor_closed.connect(self.on_group_editor_closed)
            self.group_monitor.start()
        except Exception as e:
            QMessageBox.critical(self, "Ошибка", f"Не удалось запустить редактор групп:\n{e}")

    def delete_group_confirm(self, name):
        ret = QMessageBox.question(self, 'Удаление', f"Удалить группу '{name}'?", QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
        if ret == QMessageBox.StandardButton.Yes:
            self.games_info["standalone"].extend(self.games_info["groups"].pop(name))
            self.save_data(); self.refresh_list()

    def move_game_to_group(self, identifier, target):
        def matches(g):
            return g.get("id") == identifier if g.get("id") else g["name"] == identifier

        game = None
        for i, g in enumerate(self.games_info["standalone"]):
            if matches(g): game = self.games_info["standalone"].pop(i); break
        if not game:
            for gn in self.games_info["groups"]:
                for i, g in enumerate(self.games_info["groups"][gn]):
                    if matches(g): game = self.games_info["groups"][gn].pop(i); break
                if game: break
        if game:
            if target and target != "БЕЗ ГРУППЫ": self.games_info["groups"][target].append(game)
            else: self.games_info["standalone"].append(game)
            self.save_data(); self.refresh_list()

if __name__ == "__main__":
    app = QApplication(sys.argv); app.setStyle("Fusion")
    apply_global_style(app)
    ex = GORLauncher(); ex.show(); sys.exit(app.exec())