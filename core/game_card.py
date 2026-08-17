"""
Карточка одной игры в библиотеке/избранном (кнопка запуска, таймер
сессии, drag-n-drop между группами, контекстное меню).
"""


import os
import sys
_THIS_DIR = os.path.dirname(os.path.abspath(__file__))
_PROJECT_ROOT = _THIS_DIR if os.path.exists(os.path.join(_THIS_DIR, "bridge_loader.py")) else os.path.dirname(_THIS_DIR)
for _sub in ("core", "shared", "editors", "remote", "addons_sys", "extras"):
    _p = os.path.join(_PROJECT_ROOT, _sub)
    if _p not in sys.path:
        sys.path.insert(0, _p)

import os
import sys
import subprocess
import time
import platform
import shlex

from PyQt6.QtWidgets import QFrame, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QMenu, QMessageBox, QApplication
from PyQt6.QtCore import Qt, QMimeData, QTimer
from PyQt6.QtGui import QDrag, QAction

from launcher_utils import NO_WINDOW_FLAGS, load_pixmap_cached, universal_launch
from process_monitor import ProcessMonitor
from lang_loader import tr


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

