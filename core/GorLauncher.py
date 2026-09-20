import os
import sys
_THIS_DIR = os.path.dirname(os.path.abspath(__file__))
_PROJECT_ROOT = _THIS_DIR if os.path.exists(os.path.join(_THIS_DIR, "bridge_loader.py")) else os.path.dirname(_THIS_DIR)
for _sub in ("core", "shared", "editors", "remote", "addons_sys", "extras", "GOR_Brauzer"):
    _p = os.path.join(_PROJECT_ROOT, _sub)
    if _p not in sys.path:
        sys.path.insert(0, _p)

import sys
import json
import os
import subprocess
import platform
import uuid
import time
import types
import base64
from urllib.parse import quote
from datetime import datetime
from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QPushButton, QLineEdit, QScrollArea, QLabel, QGridLayout,
    QComboBox, QMenu, QMessageBox, QTabWidget, QToolBar, QSystemTrayIcon,
    QFrame,
)
from PyQt6.QtCore import Qt, QTimer, QUrl
from PyQt6.QtGui import QIcon, QAction, QKeySequence, QShortcut
from PyQt6.QtNetwork import QLocalServer, QLocalSocket, QNetworkAccessManager, QNetworkRequest, QNetworkReply
from PyQt6.QtWebEngineCore import QWebEngineContextMenuRequest

from style_loader import apply_global_style
from fortune_wheel import FortuneWheelDialog
from lang_loader import tr, available_languages, current_language, set_language

from launcher_utils import NO_GROUP_KEY, find_favicon_path, universal_launch, run_editor_process
from process_monitor import EditorMonitor
from history_card import HistoryCard
from game_card import GameCard
from group_widget import GroupWidget
from browser_widget import GORBrowser
from cover_ipc import IPC_SERVER_NAME, encode_message, try_decode_line


with open("version.json", "r", encoding="utf-8") as f:
    version = json.load(f)["version"]


# --- ОТДЕЛЬНОЕ ОКНО ДЛЯ "ОТКРЕПЛЁННОЙ" ВКЛАДКИ ЛАУНЧЕРА ---
class DetachedTabWindow(QMainWindow):
    """Окно, в которое временно переезжает вкладка лаунчера в режиме
    'Отдельное окно'. При закрытии этого окна содержимое автоматически
    возвращается обратно в главное окно лаунчера на своё исходное место."""

    def __init__(self, owner, content_widget, title, icon, original_index):
        super().__init__()
        self._owner = owner
        self._content = content_widget
        self._title = title
        self._icon = icon
        self._original_index = original_index
        self._returned = False

        self.setWindowTitle(tr("launcher.detached_window_title", title=title))
        if icon is not None and not icon.isNull():
            self.setWindowIcon(icon)
        self.resize(1200, 850)

        toolbar = QToolBar()
        toolbar.setMovable(False)
        toolbar.setFloatable(False)
        act_return = QAction(tr("launcher.detached_return_btn"), self)
        act_return.triggered.connect(self.close)
        toolbar.addAction(act_return)
        self.addToolBar(toolbar)

        self.setCentralWidget(content_widget)

        # --- ФИКС "ЧЁРНОГО ЭКРАНА" ---
        # QWebEngineView (вкладка "Браузер") и некоторые другие виджеты с
        # нативным дочерним окном (native child window) не перерисовываются
        # сами после того, как их переносят в другое top-level окно - экран
        # остаётся чёрным, пока не произойдёт resize/repaint. Поэтому сразу
        # после показа окна "пинаем" перерисовку вручную.
        QTimer.singleShot(0, self._kick_repaint)
        QTimer.singleShot(150, self._kick_repaint)

    def _kick_repaint(self):
        """Принудительно форсирует перерисовку контента после переноса
        виджета в новое окно (актуально для QWebEngineView и подобных)."""
        if self._content is None:
            return
        try:
            self._content.hide()
            self._content.show()
            size = self.size()
            self.resize(size.width() + 1, size.height())
            self.resize(size)
        except RuntimeError:
            pass  # виджет уже мог быть удалён/перемещён обратно

    def closeEvent(self, event):
        self._return_content()
        super().closeEvent(event)

    def _return_content(self):
        if self._returned:
            return
        self._returned = True
        content = self.takeCentralWidget()
        if content is not None and self._owner is not None:
            self._owner._reattach_tab(content, self._title, self._icon, self._original_index)


# --- ГЛАВНОЕ ОКНО ---
class GORLauncher(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle(tr("launcher.window_title") + "   " + version)
        self.setWindowIcon(QIcon(find_favicon_path()))
        self.setMinimumSize(1300, 950)
        # Кастомная панель заголовка (frameless-окно) была здесь в патче 2/4,
        # но откатана по явному запросу: системная рамка ОС нужна для
        # корректной работы Snap Layouts (Win+стрелки), системных анимаций
        # и теней окна на Windows. См. _build_title_bar/_edge_at/etc. в
        # истории патчей, если понадобится восстановить.
        self.data_file = "games_data.json"
        self.active_sessions = {}
        self._wheel_monitors = []

        # --- дочерние окна/процессы лаунчера (редактор игры/группы,
        # Sunshine, экспортёр, Control Center, колесо фортуны) - нужны,
        # чтобы при закрытии/перезапуске главного окна закрыть их все разом ---
        self._child_processes = []           # subprocess.Popen активных редакторов/утилит
        self._active_wheel_dialog = None     # открытый сейчас QDialog колеса фортуны (если есть)

        # --- системный трей: лаунчер прячется в трей при запуске игры и
        # возвращается обратно, когда ВСЕ запущенные из него игры закрыты ---
        self.tray_icon = None
        self._state_before_tray = None

        # --- состояние режимов отображения вкладок (обычный / развёрнутый /
        # весь экран / отдельное окно) ---
        self._tab_view_mode = "normal"       # "normal" | "expanded" | "fullscreen"
        self._tab_view_index = None          # индекс вкладки, к которой применён expanded/fullscreen
        self._detached_windows = {}          # widget -> DetachedTabWindow

        # --- IPC-сервер "выбор обложки из браузера" (см. shared/cover_ipc.py) ---
        # GameEditor - отдельный процесс, поэтому кнопка "Найти в браузере"
        # не открывает своё окно, а стучится сюда: главный лаунчер сам
        # переключает вкладку на "Браузер", открывает там служебную вкладку
        # и присылает редактору путь к скачанной картинке.
        self._cover_ipc_server = None
        self._cover_ipc_buffers = {}   # QLocalSocket -> накопленный байт-буфер
        self._cover_ipc_pending = {}   # QLocalSocket -> {"view": QWebEngineView}
        self._cover_network = QNetworkAccessManager(self)

        self.load_data()
        self.init_ui()
        self._start_cover_ipc_server()

        esc_shortcut = QShortcut(QKeySequence(Qt.Key.Key_Escape), self)
        esc_shortcut.activated.connect(self._on_escape_pressed)

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
        if "browser" not in self.games_info: self.games_info["browser"] = {}
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
        header.setContentsMargins(10, 6, 10, 6)
        header.setSpacing(8)
        self.stats_lbl = QLabel()
        self.stats_lbl.setObjectName("StatsLabel")
        
        self.burger_btn = QPushButton("☰")
        self.burger_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.burger_btn.setObjectName("BurgerMenuBtn")
        self.burger_btn.setFixedSize(30, 30)
        self.burger_btn.setStyleSheet("QPushButton::menu-indicator { image: none; width: 0px; }")

        burger_menu = QMenu(self)

        act_wheel = QAction(tr("launcher.menu_wheel"), self)
        act_wheel.triggered.connect(self.open_fortune_wheel)
        burger_menu.addAction(act_wheel)

        act_sunshine = QAction(tr("launcher.menu_sunshine"), self)
        act_sunshine.triggered.connect(self.run_sunshine)
        burger_menu.addAction(act_sunshine)

        act_moonlight = QAction(tr("launcher.menu_moonlight"), self)
        act_moonlight.triggered.connect(self.run_moonlight)
        burger_menu.addAction(act_moonlight)

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

        self.tray_btn = QPushButton("🔽")
        self.tray_btn.setObjectName("TrayBtn")
        self.tray_btn.setToolTip(tr("launcher.tray_minimize_tooltip"))
        self.tray_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.tray_btn.setFixedSize(30, 30)
        self.tray_btn.clicked.connect(self.minimize_to_tray)

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
        header.addWidget(self.tray_btn)
        header.addWidget(self.burger_btn)

        # Шапка завёрнута в QWidget (а не просто QHBoxLayout), чтобы её
        # можно было прятать целиком в режимах "развернуть вкладку"/"весь экран"
        self.header_bar = QWidget()
        self.header_bar.setLayout(header)
        self.main_lay.addWidget(self.header_bar)
        
        self.tabs = QTabWidget()
        self.main_lay.addWidget(self.tabs)

        # Контекстное меню на панели вкладок лаунчера (НЕ вкладки браузера!)
        self.tabs.tabBar().setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.tabs.tabBar().customContextMenuRequested.connect(self._show_tab_context_menu)
        
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

        # --- ВКЛАДКА "БРАУЗЕР" (встроенный GOR Browser) ---
        self.browser_tab = GORBrowser()
        self.tabs.addTab(self.browser_tab, tr("launcher.tab_browser"))

        self.refresh_list()

    # ------------------------------------------------------------------ #
    # РЕЖИМЫ ОТОБРАЖЕНИЯ ВКЛАДОК ЛАУНЧЕРА
    # (развернуть на всё окно / на весь экран / отдельное окно)
    # ------------------------------------------------------------------ #
    def _show_tab_context_menu(self, pos):
        bar = self.tabs.tabBar()
        index = bar.tabAt(pos)
        if index < 0:
            return

        is_expanded = (self._tab_view_mode == "expanded" and self._tab_view_index == index)
        is_fullscreen = (self._tab_view_mode == "fullscreen" and self._tab_view_index == index)

        menu = QMenu(self)

        act_expand = QAction(tr("launcher.tab_menu_expand_window"), self)
        act_expand.setCheckable(True)
        act_expand.setChecked(is_expanded)
        act_expand.triggered.connect(lambda checked, i=index: self.set_tab_expand_window(i, checked))
        menu.addAction(act_expand)

        act_full = QAction(tr("launcher.tab_menu_fullscreen"), self)
        act_full.setCheckable(True)
        act_full.setChecked(is_fullscreen)
        act_full.triggered.connect(lambda checked, i=index: self.set_tab_fullscreen(i, checked))
        menu.addAction(act_full)

        menu.addSeparator()

        act_detach = QAction(tr("launcher.tab_menu_detach"), self)
        act_detach.triggered.connect(lambda checked=False, i=index: self.detach_tab(i))
        menu.addAction(act_detach)

        if self._tab_view_mode != "normal":
            menu.addSeparator()
            act_restore = QAction(tr("launcher.tab_menu_restore"), self)
            act_restore.triggered.connect(lambda checked=False: self._restore_tab_view())
            menu.addAction(act_restore)

        menu.exec(bar.mapToGlobal(pos))

    def set_tab_expand_window(self, index, checked):
        """Развернуть указанную вкладку на всё окно лаунчера (прячет верхнюю
        панель поиска/бургер-меню, оставляя саму панель вкладок - чтобы можно
        было в любой момент вернуть обычный вид через то же контекстное меню)."""
        if checked:
            self._tab_view_mode = "expanded"
            self._tab_view_index = index
            self.tabs.setCurrentIndex(index)
            self.header_bar.setVisible(False)
            if self.isFullScreen():
                self.showNormal()
        else:
            self._restore_tab_view()

    def set_tab_fullscreen(self, index, checked):
        """Развернуть указанную вкладку на весь экран (полноэкранный режим
        окна + скрытая верхняя панель)."""
        if checked:
            self._tab_view_mode = "fullscreen"
            self._tab_view_index = index
            self.tabs.setCurrentIndex(index)
            self.header_bar.setVisible(False)
            self.showFullScreen()
        else:
            self._restore_tab_view()

    def _restore_tab_view(self):
        """Вернуть обычный вид: верхняя панель видна, окно не на весь экран."""
        self._tab_view_mode = "normal"
        self._tab_view_index = None
        self.header_bar.setVisible(True)
        if self.isFullScreen():
            self.showNormal()

    def _on_escape_pressed(self):
        if self._tab_view_mode == "fullscreen":
            self._restore_tab_view()

    def detach_tab(self, index):
        """Открепить вкладку в отдельное окно. После закрытия этого окна
        вкладка автоматически возвращается обратно в главное окно на своё
        исходное место."""
        if index < 0 or index >= self.tabs.count():
            return

        widget = self.tabs.widget(index)
        title = self.tabs.tabText(index)
        icon = self.tabs.tabIcon(index)

        # Если для этой вкладки был активен режим "развернуть"/"весь экран" -
        # сначала вернуть обычный вид главного окна.
        if self._tab_view_mode != "normal" and self._tab_view_index == index:
            self._restore_tab_view()

        self.tabs.removeTab(index)

        win = DetachedTabWindow(self, widget, title, icon, index)
        self._detached_windows[widget] = win
        win.show()
        win.raise_()
        win.activateWindow()

    def _reattach_tab(self, widget, title, icon, original_index):
        """Вызывается отдельным окном при закрытии - возвращает вкладку
        обратно в self.tabs на (по возможности) её исходное место."""
        self._detached_windows.pop(widget, None)
        idx = min(max(original_index, 0), self.tabs.count())
        if icon is not None and not icon.isNull():
            self.tabs.insertTab(idx, widget, icon, title)
        else:
            self.tabs.insertTab(idx, widget, title)
        self.tabs.setCurrentIndex(idx)

        # Тот же "пинок" перерисовки, что и в DetachedTabWindow - иначе
        # виджет (особенно вкладка "Браузер" на QWebEngineView) может
        # остаться чёрным после возврата в главное окно.
        def _kick():
            try:
                widget.hide()
                widget.show()
            except RuntimeError:
                pass
        QTimer.singleShot(0, _kick)
        QTimer.singleShot(150, _kick)

    # ------------------------------------------------------------------ #
    # СИСТЕМНЫЙ ТРЕЙ: сворачиваем лаунчер при запуске игры, возвращаем
    # обратно, когда ВСЕ запущенные из лаунчера игры закрыты.
    # ------------------------------------------------------------------ #
    def _init_tray_icon(self):
        if self.tray_icon is not None:
            return
        if not QSystemTrayIcon.isSystemTrayAvailable():
            return

        self.tray_icon = QSystemTrayIcon(QIcon(find_favicon_path()), self)
        self.tray_icon.setToolTip(tr("launcher.window_title"))

        tray_menu = QMenu()
        act_open = QAction(tr("launcher.tray_open"), self)
        act_open.triggered.connect(self.restore_from_tray)
        tray_menu.addAction(act_open)
        tray_menu.addSeparator()
        act_quit = QAction(tr("launcher.tray_quit"), self)
        act_quit.triggered.connect(self.close)
        tray_menu.addAction(act_quit)
        self.tray_icon.setContextMenu(tray_menu)

        self.tray_icon.activated.connect(self._on_tray_activated)

    def _on_tray_activated(self, reason):
        if reason in (QSystemTrayIcon.ActivationReason.Trigger,
                      QSystemTrayIcon.ActivationReason.DoubleClick):
            self.restore_from_tray()

    def minimize_to_tray(self):
        """Прячет главное окно лаунчера в системный трей (вызывается при
        запуске игры)."""
        self._init_tray_icon()
        if self.tray_icon is None:
            # На системе нет трея (или он недоступен) - просто сворачиваем
            # окно обычным способом, чтобы не потерять функциональность.
            self.showMinimized()
            return
        if not self.isHidden():
            self._state_before_tray = self.windowState()
        self.tray_icon.show()
        self.hide()
        if self.tray_icon.supportsMessages():
            self.tray_icon.showMessage(
                tr("launcher.tray_title"),
                tr("launcher.tray_hidden_text"),
                QSystemTrayIcon.MessageIcon.Information,
                2500
            )

    def restore_from_tray(self):
        """Возвращает главное окно лаунчера обратно из трея (вызывается,
        когда все запущенные из лаунчера игры закрыты, или по клику на
        значок трея)."""
        state = self._state_before_tray if self._state_before_tray is not None else Qt.WindowState.WindowNoState
        self.setWindowState(state)
        self.show()
        self.raise_()
        self.activateWindow()
        if self.tray_icon is not None:
            self.tray_icon.hide()

    def on_game_session_changed(self):
        """Вызывается из GameCard при запуске/остановке/завершении игры.
        Сворачивает лаунчер в трей, пока запущена хотя бы одна игра, и
        возвращает обратно, когда игр не осталось."""
        if len(self.active_sessions) > 0:
            self.minimize_to_tray()
        else:
            self.restore_from_tray()

    def on_game_started(self, game_data):
        """Вызывается GameCard РОВНО В МОМЕНТ успешного запуска игры (до
        on_game_session_changed) - пункты ТЗ "Сейчас в игре" и "Авто-группа
        Гайды по [Игра]":
          1. Пишет запись now_playing в games_data.json → browser.now_playing,
             чтобы стартовая страница браузера могла её показать.
          2. Если у игры привязана группа гайдов (см. GameCard.pick_guide_group),
             просит вкладку браузера открыть эту группу.
        """
        self._write_now_playing(game_data)
        browser_tab = getattr(self, "browser_tab", None)
        if browser_tab is not None:
            try:
                browser_tab.push_now_playing(game_data)
            except Exception:
                pass
        guide_group_id = game_data.get("guide_group_id")
        if guide_group_id and browser_tab is not None:
            try:
                browser_tab.open_group_by_id(guide_group_id)
            except Exception:
                pass

    def _write_now_playing(self, game_data):
        """Точечно обновляет ТОЛЬКО data['browser']['now_playing'] прямо в
        games_data.json на диске - читаем файл заново непосредственно перед
        записью (а не self.games_info из памяти), точно так же, как это
        делает GORBrowser.save_data() для своих ключей. Так мы не рискуем
        затереть блок "browser", который параллельно мог обновить сам
        браузер (закладки/история/сессия), и наоборот - не затираем данные
        игр/групп, если что-то попытается прочитать их между этим вызовом и
        обычным self.save_data()."""
        try:
            if os.path.exists(self.data_file):
                with open(self.data_file, "r", encoding="utf-8") as f:
                    data = json.load(f)
            else:
                data = {}
        except Exception:
            data = {}
        if not isinstance(data.get("browser"), dict):
            data["browser"] = {}
        data["browser"]["now_playing"] = {
            "name": game_data.get("name", "?"),
            "icon": game_data.get("icon", ""),
            "started": datetime.now().isoformat(),
            "wiki_url": game_data.get("wiki_url", ""),
            "forum_url": game_data.get("forum_url", ""),
            "discord_url": game_data.get("discord_url", ""),
        }
        try:
            with open(self.data_file, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=4)
        except Exception:
            pass  # виджет "Сейчас в игре" просто не обновится - не критично

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
        self._track_process(proc)

    def edit_game(self, game_data, group_name):
        g_name = group_name if group_name else NO_GROUP_KEY
        gid = game_data.get("id", "")
        proc = run_editor_process("game_editor", [game_data['name'], g_name, gid], py_subdir="editors")
        self._track_process(proc)

    def on_editor_closed(self):
        self.load_data()
        self.refresh_list()
        self._child_processes = [p for p in self._child_processes if p.poll() is None]

    def _track_process(self, proc):
        """Регистрирует запущенный дочерний процесс (редактор игры/группы,
        Sunshine, экспортёр, Control Center...), чтобы:
        1) знать о нём и уметь закрыть/завершить вместе с главным окном;
        2) как и раньше, обновлять список игр, когда окно редактора закрывается."""
        if proc is None:
            return
        self._child_processes.append(proc)
        monitor = EditorMonitor(proc)
        monitor.editor_closed.connect(self.on_editor_closed)
        self._wheel_monitors.append(monitor)
        monitor.start()

    def add_group(self):
        proc = run_editor_process("group_editor", py_subdir="editors")
        self._track_process(proc)

    def edit_group(self, group_name):
        proc = run_editor_process("group_editor", [group_name], py_subdir="editors")
        self._track_process(proc)

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
        self._active_wheel_dialog = dialog
        try:
            dialog.exec()
        finally:
            self._active_wheel_dialog = None

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
            proc = run_editor_process("sunshine_control", py_subdir="remote")
            self._track_process(proc)
        except Exception as e:
            QMessageBox.critical(self, tr("sunshine_error.title"), tr("sunshine_error.text", error=e))

    def run_moonlight(self):
        try:
            proc = run_editor_process("moonlight_cantrol", py_subdir="remote")
            self._track_process(proc)
        except Exception as e:
            QMessageBox.critical(self, tr("moonlight_error.title"), tr("moonlight_error.text", error=e))

    # ----------------------------------------------------------------- #
    # IPC "выбор обложки из браузера" - см. shared/cover_ipc.py.
    # GameEditor - отдельный процесс, и не может сам управлять вкладками
    # главного окна, поэтому просит об этом нас через QLocalSocket.
    # ----------------------------------------------------------------- #
    def _start_cover_ipc_server(self):
        # На случай, если предыдущий запуск лаунчера завершился аварийно и
        # не освободил канал - убираем возможный "хвост" перед listen().
        QLocalServer.removeServer(IPC_SERVER_NAME)
        self._cover_ipc_server = QLocalServer(self)
        self._cover_ipc_server.newConnection.connect(self._on_cover_ipc_connection)
        if not self._cover_ipc_server.listen(IPC_SERVER_NAME):
            # Не критично: значит просто не будет работать "живая" интеграция
            # с браузером, GameEditor тихо откатится на своё старое окно.
            print(f"[GorLauncher] Не удалось запустить IPC-сервер обложек: "
                  f"{self._cover_ipc_server.errorString()}")

    def _on_cover_ipc_connection(self):
        while self._cover_ipc_server.hasPendingConnections():
            socket = self._cover_ipc_server.nextPendingConnection()
            if socket is None:
                continue
            self._cover_ipc_buffers[socket] = b""
            socket.readyRead.connect(lambda s=socket: self._on_cover_ipc_ready_read(s))
            socket.disconnected.connect(lambda s=socket: self._cleanup_cover_ipc_socket(s))

    def _on_cover_ipc_ready_read(self, socket):
        self._cover_ipc_buffers[socket] = self._cover_ipc_buffers.get(socket, b"") + bytes(socket.readAll())
        while True:
            msg, rest = try_decode_line(self._cover_ipc_buffers[socket])
            self._cover_ipc_buffers[socket] = rest
            if msg is None:
                break
            self._handle_cover_ipc_message(socket, msg)

    def _cleanup_cover_ipc_socket(self, socket):
        self._cover_ipc_buffers.pop(socket, None)
        pending = self._cover_ipc_pending.pop(socket, None)
        # Если редактор игры закрылся/отвалился раньше, чем пользователь
        # успел выбрать картинку - служебная вкладка браузера больше не
        # нужна, закрываем её, чтобы не висела зря.
        if pending and pending.get("view") is not None:
            self._close_cover_picker_tab(pending["view"])
        socket.deleteLater()

    def _handle_cover_ipc_message(self, socket, msg):
        if msg.get("cmd") == "pick_cover":
            query = str(msg.get("query") or "").strip() or "обложка игры"
            self._open_cover_picker_tab(socket, query)

    def _open_cover_picker_tab(self, socket, query):
        """Переключается на вкладку 'Браузер' и открывает в ней НОВУЮ
        вкладку в режиме выбора обложки - только в этой конкретной вкладке
        появляется пункт 'Использовать как обложку' в контекстном меню
        картинок, и только у неё зафиксирован заголовок, чтобы сразу было
        видно, что вкладка не обычная."""
        # Поднимаем главное окно поверх остальных - иначе пользователь может
        # не заметить, что что-то произошло (окно редактора игры - другое окно).
        self.showNormal() if self.isMinimized() else None
        self.raise_()
        self.activateWindow()

        browser_index = self.tabs.indexOf(self.browser_tab)
        if browser_index != -1:
            self.tabs.setCurrentIndex(browser_index)

        search_url = QUrl(f"https://www.google.com/search?tbm=isch&q={quote(query)}")
        view = self.browser_tab.add_new_tab(qurl=search_url, label="Обложка")

        # Эмодзи-значок теперь отдельной иконкой слева от текста (пункт 9
        # ТЗ), а не префиксом в самом заголовке - см. GORBrowser.update_tab_icon.
        label = ("Обложка: " + query)[:24]
        view.setProperty("gor_cover_picker_label", label)
        idx = self.browser_tab.tabs.indexOf(view)
        if idx != -1:
            self.browser_tab.tabs.setTabText(idx, label)
            self.browser_tab.update_tab_icon(view, view.icon())
            self.browser_tab.tabs.setTabToolTip(
                idx,
                "Служебная вкладка выбора обложки.\n"
                "Правый клик по картинке → «Использовать как обложку игры»."
            )

        # Патчим contextMenuEvent ТОЛЬКО этого конкретного QWebEngineView -
        # у остальных вкладок браузера (в т.ч. открытых позже) пункт
        # "Использовать как обложку" не появляется.
        launcher = self

        def _picker_context_menu_event(view_self, event):
            request = view_self.lastContextMenuRequest()
            menu = view_self.createStandardContextMenu()
            if (request.mediaType() == QWebEngineContextMenuRequest.MediaType.MediaTypeImage
                    and not request.mediaUrl().isEmpty()):
                media_url = request.mediaUrl().toString()
                menu.addSeparator()
                act = menu.addAction("🖼️ Использовать как обложку игры")
                act.triggered.connect(
                    lambda: launcher._grab_cover_for_ipc(socket, view_self, media_url)
                )
            menu.exec(event.globalPos())

        view.contextMenuEvent = types.MethodType(_picker_context_menu_event, view)
        self._cover_ipc_pending[socket] = {"view": view}

    def _grab_cover_for_ipc(self, socket, view, img_url):
        if img_url.startswith("data:"):
            # Превью в поиске картинок иногда сразу приходят как data:URL -
            # тогда сеть не нужна, декодируем base64 напрямую.
            try:
                header, b64data = img_url.split(",", 1)
                ext = "png"
                if "image/jpeg" in header or "image/jpg" in header:
                    ext = "jpg"
                elif "image/webp" in header:
                    ext = "webp"
                raw = base64.b64decode(b64data)
                self._finish_cover_grab(socket, view, raw, ext)
            except Exception as e:
                self._reply_cover_ipc_error(socket, str(e))
            return

        qurl = QUrl(img_url)
        reply = self._cover_network.get(QNetworkRequest(qurl))
        reply.finished.connect(lambda: self._on_cover_ipc_download_finished(socket, view, reply, qurl))

    def _on_cover_ipc_download_finished(self, socket, view, reply, qurl):
        if reply.error() != QNetworkReply.NetworkError.NoError:
            self._reply_cover_ipc_error(socket, reply.errorString())
            reply.deleteLater()
            return
        raw = bytes(reply.readAll())
        reply.deleteLater()
        ext = os.path.splitext(qurl.path())[1].lstrip(".").split("?")[0][:4] or "jpg"
        if ext.lower() not in ("jpg", "jpeg", "png", "webp", "gif", "bmp"):
            ext = "jpg"
        self._finish_cover_grab(socket, view, raw, ext)

    def _finish_cover_grab(self, socket, view, raw_bytes, ext):
        try:
            os.makedirs("covers", exist_ok=True)
            full_path = os.path.abspath(os.path.join("covers", f"{uuid.uuid4().hex}.{ext}"))
            with open(full_path, "wb") as f:
                f.write(raw_bytes)
        except Exception as e:
            self._reply_cover_ipc_error(socket, str(e))
            return

        if socket.state() == QLocalSocket.LocalSocketState.ConnectedState:
            socket.write(encode_message({"cover_path": full_path}))
            socket.flush()

        self._cover_ipc_pending.pop(socket, None)
        self._close_cover_picker_tab(view)

    def _reply_cover_ipc_error(self, socket, message):
        if socket.state() == QLocalSocket.LocalSocketState.ConnectedState:
            socket.write(encode_message({"error": message}))
            socket.flush()

    def _close_cover_picker_tab(self, view):
        try:
            idx = self.browser_tab.tabs.indexOf(view)
            if idx != -1:
                self.browser_tab.close_tab(idx)
        except RuntimeError:
            pass  # вкладка/виджет уже удалены (например, окно браузера закрыто)

    def open_exporter(self):
        try:
            proc = run_editor_process("exporter_editor", py_subdir="extras")
            self._track_process(proc)
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

    def closeEvent(self, event):
        # Прячем иконку трея, если она была показана - иначе после закрытия
        # лаунчера в трее останется "призрак" значка.
        if self.tray_icon is not None:
            self.tray_icon.hide()

        # Закрываем все открепленные окна вкладок вместе с главным окном,
        # чтобы они не оставались висеть сами по себе.
        for win in list(self._detached_windows.values()):
            win.close()

        # Закрываем диалог "Колесо фортуны", если он ещё открыт (иначе он
        # останется висеть отдельным окном после закрытия главного).
        if self._active_wheel_dialog is not None:
            try:
                self._active_wheel_dialog.reject()
            except RuntimeError:
                pass
            self._active_wheel_dialog = None

        # Закрываем/завершаем все вспомогательные окна-процессы (редактор
        # игры, редактор группы, Sunshine, экспортёр, Control Center) -
        # чтобы при закрытии или перезапуске главного окна они закрывались
        # или перезапускались вместе с ним, а не оставались сиротами.
        self._close_child_processes()

        # Останавливаем IPC-сервер "выбор обложки" и рвём все висящие
        # соединения - иначе GameEditor будет ждать ответ, который уже
        # никогда не придёт.
        if self._cover_ipc_server is not None:
            for socket in list(self._cover_ipc_buffers.keys()):
                socket.disconnectFromServer()
            self._cover_ipc_server.close()

        # Штатное закрытие - помечаем сессию браузера как "чисто завершённую"
        # (см. GORBrowser.mark_session_closed_cleanly), чтобы при следующем
        # запуске НЕ предлагалось восстановление вкладок после краша: если
        # этот код успел выполниться, значит краша не было.
        if hasattr(self, "browser_tab") and self.browser_tab is not None:
            try:
                self.browser_tab.mark_session_closed_cleanly()
            except Exception:
                pass

        super().closeEvent(event)

    def _close_child_processes(self):
        """Аккуратно завершает все зарегистрированные дочерние процессы
        (см. self._track_process): сперва просит закрыться (terminate),
        коротко ждёт, и добивает (kill) тех, кто не закрылся сам."""
        procs = list(self._child_processes)
        for proc in procs:
            try:
                if proc.poll() is None:
                    proc.terminate()
            except Exception:
                pass

        deadline = time.time() + 2.0
        for proc in procs:
            try:
                if proc.poll() is None:
                    remaining = deadline - time.time()
                    proc.wait(timeout=max(remaining, 0))
            except Exception:
                pass

        for proc in procs:
            try:
                if proc.poll() is None:
                    proc.kill()
            except Exception:
                pass

        self._child_processes = []

if __name__ == "__main__":
    app = QApplication(sys.argv)
    app.setWindowIcon(QIcon(find_favicon_path()))
    apply_global_style(app)
    launcher = GORLauncher()
    launcher.show()
