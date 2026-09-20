import sys
import os
import json
import subprocess
import re
from datetime import datetime

# --- ПОЛНЫЙ НАБОР ИМПОРТОВ PYQT6 ---
from PyQt6.QtCore import QUrl, Qt, QSize, QPoint
from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QVBoxLayout, QWidget, 
    QLineEdit, QTabWidget, QHBoxLayout, QPushButton, 
    QFrame, QInputDialog, QMessageBox, QFileDialog, 
    QToolButton, QProgressBar, QLabel, QListWidget, QListWidgetItem, 
    QStackedWidget, QMenu, QColorDialog, QDialog, QComboBox, QCheckBox, QSlider
)
from PyQt6.QtGui import QKeySequence, QShortcut, QIcon, QAction, QFont, QColor

# Импорты движка WebEngine (обязательно все эти!)
from PyQt6.QtWebEngineWidgets import QWebEngineView
from PyQt6.QtWebEngineCore import (
    QWebEngineProfile, QWebEnginePage, 
    QWebEngineScript, QWebEngineSettings, 
    QWebEngineDownloadRequest
)

# --- ФУНКЦИЯ ПУТЕЙ GOR ---
def get_resource_path(relative_path):
    """ Получает путь к ресурсу, работает для обычного запуска и для .exe """
    if hasattr(sys, '_MEIPASS'):
        return os.path.join(sys._MEIPASS, relative_path)
    return os.path.join(os.path.dirname(os.path.abspath(__file__)), relative_path)

# Далее идет твой класс GORBrowser...

# 2. Определяем BASE_DIR правильно, чтобы настройки не стирались
# Если запущено как .exe, используем путь к экзешнику, а не к временной папке
if getattr(sys, 'frozen', False):
    BASE_DIR = os.path.dirname(sys.executable)
else:
    BASE_DIR = os.path.dirname(os.path.abspath(__file__))

# 3. Применяем пути
ICON_PATH = get_resource_path("Gor_Brauzer.ico")
START_PAGE_PATH = get_resource_path("start_page.html")

# Файлы данных (будут лежать рядом с .exe)
BOOKMARKS_FILE = os.path.join(BASE_DIR, "bookmarks.json")
HISTORY_FILE = os.path.join(BASE_DIR, "history.json")
PASSWORDS_FILE = os.path.join(BASE_DIR, "passwords.json")
SETTINGS_FILE = os.path.join(BASE_DIR, "settings.json")
EXTENSIONS_FILE = os.path.join(BASE_DIR, "extensions.json")
PROFILE_PATH = os.path.join(BASE_DIR, "GOR_Profile")
SEARCH_ENGINES = {
    "Google": "https://google.com/search?q=",
    "Yandex": "https://yandex.ru/search/?text=",
    "Bing": "http://127.0.0.1:5000",
    "DuckDuckGo": "https://duckduckgo.com/?q="
}


# Функция для поиска ресурсов (иконки, html) внутри .exe
def get_resource_path(relative_path):
    if hasattr(sys, '_MEIPASS'):
        return os.path.join(sys._MEIPASS, relative_path)
    return os.path.join(os.path.dirname(os.path.abspath(__file__)), relative_path)

# Указываем путь к твоей иконке
ICON_PATH = get_resource_path("Gor_Brauzer.ico")


class CustomizationManager(QDialog):
    def __init__(self, parent):
        super().__init__(parent)
        self.parent = parent
        self.setWindowTitle("Кастомизация GOR Browser")
        self.setFixedSize(400, 550)
        self.setStyleSheet(f"background-color: #1c1d21; color: white; font-family: '{self.parent.settings.get('font_family', 'Segoe UI')}';")
        
        layout = QVBoxLayout(self)
        layout.addWidget(QLabel("🎨 Акцентный цвет (кнопки, часы):"))
        self.btn_color = QPushButton("Выбрать акцент")
        self.current_accent = self.parent.settings.get("theme_color", "#4c6ef5")
        self.btn_color.setStyleSheet(f"background: {self.current_accent}; padding: 10px; border-radius: 5px; border: none;")
        self.btn_color.clicked.connect(self.pick_accent_color)
        layout.addWidget(self.btn_color)

        layout.addWidget(QLabel("📟 Цвет верхней панели (TopBar):"))
        self.btn_top_color = QPushButton("Выбрать цвет панели")
        self.current_top_color = self.parent.settings.get("top_bar_color", "#16171a")
        self.btn_top_color.setStyleSheet(f"background: {self.current_top_color}; padding: 10px; border-radius: 5px; border: 1px solid #444;")
        self.btn_top_color.clicked.connect(self.pick_top_color)
        layout.addWidget(self.btn_top_color)

        layout.addSpacing(10)
        layout.addWidget(QLabel("🔤 Шрифт интерфейса:"))
        self.font_combo = QComboBox()
        self.font_combo.addItems(["Segoe UI", "Roboto", "Arial", "Consolas", "Verdana", "Open Sans"])
        self.font_combo.setCurrentText(self.parent.settings.get("font_family", "Segoe UI"))
        self.font_combo.setStyleSheet("background: #2c2e33; color: white; padding: 5px;")
        layout.addWidget(self.font_combo)

        layout.addSpacing(10)
        layout.addWidget(QLabel("🖼️ Фон стартовой страницы:"))
        bg_path = self.parent.settings.get("bg_image", "")
        self.bg_path_label = QLabel(os.path.basename(bg_path) if bg_path else "Стандартный темный")
        self.bg_path_label.setStyleSheet("color: #888; font-size: 10px;")
        btn_bg = QPushButton("Выбрать изображение")
        btn_bg.setStyleSheet("background: #2c2e33; padding: 8px; border-radius: 5px;")
        btn_bg.clicked.connect(self.pick_background)
        layout.addWidget(btn_bg)
        layout.addWidget(self.bg_path_label)

        layout.addWidget(QLabel("✨ Прозрачность блоков (0.1 - 1.0):"))
        self.opacity_slider = QSlider(Qt.Orientation.Horizontal)
        self.opacity_slider.setRange(10, 100)
        self.opacity_slider.setValue(int(self.parent.settings.get("ui_opacity", 0.8) * 100))
        layout.addWidget(self.opacity_slider)

        layout.addStretch()
        btn_save = QPushButton("СОХРАНИТЬ И ПРИМЕНИТЬ")
        btn_save.setStyleSheet(f"background: {self.current_accent}; color: white; padding: 15px; border-radius: 8px; font-weight: bold;")
        btn_save.clicked.connect(self.apply_changes)
        layout.addWidget(btn_save)

    def pick_accent_color(self):
        color = QColorDialog.getColor()
        if color.isValid():
            self.current_accent = color.name()
            self.btn_color.setStyleSheet(f"background: {self.current_accent}; padding: 10px; border-radius: 5px; border: none;")

    def pick_top_color(self):
        color = QColorDialog.getColor()
        if color.isValid():
            self.current_top_color = color.name()
            self.btn_top_color.setStyleSheet(f"background: {self.current_top_color}; padding: 10px; border-radius: 5px; border: 1px solid #444;")

    def pick_background(self):
        file, _ = QFileDialog.getOpenFileName(self, "Выберите фон", "", "Images (*.png *.jpg *.jpeg)")
        if file:
            self.parent.settings["bg_image"] = file
            self.bg_path_label.setText(os.path.basename(file))

    def apply_changes(self):
        self.parent.settings["theme_color"] = self.current_accent
        self.parent.settings["top_bar_color"] = self.current_top_color
        self.parent.settings["font_family"] = self.font_combo.currentText()
        self.parent.settings["ui_opacity"] = self.opacity_slider.value() / 100
        self.parent.save_data(SETTINGS_FILE, self.parent.settings)
        self.parent.create_start_page()
        self.parent.update_styles()
        self.parent.reload_start_pages()
        self.accept()

# --- ИСПРАВЛЕННЫЙ МЕТОД CREATEWINDOW ---

class GORWebPage(QWebEnginePage):
    """Специальный класс страницы для обработки новых окон GOR-Browser"""
    def __init__(self, profile, parent=None):
        super().__init__(profile, parent)
        self.ins_browser = None # Устанавливается в методе add_new_tab

    def createWindow(self, _type):
        """
        Метод вызывается, когда браузер хочет открыть новую вкладку (например, через Target='_blank').
        Мы вызываем наш метод создания вкладки, но возвращаем именно ОБЪЕКТ СТРАНИЦЫ.
        """
        # Создаем новую вкладку через существующий метод основного окна
        if self.ins_browser:
            new_tab_widget = self.ins_browser.add_new_tab()

            # КРИТИЧЕСКОЕ ИСПРАВЛЕНИЕ: возвращаем .page(), а не сам виджет.
            # Это предотвращает вылеты при открытии ссылок в новых окнах.
            return new_tab_widget.page()

        # Если ins_browser не установлен - не падаем, а отдаём поведение по умолчанию
        return super().createWindow(_type)

# --- КОНЕЦ ИСПРАВЛЕНИЯ ---

class SettingsDialog(QDialog):
    def __init__(self, parent):
        super().__init__(parent)
        self.parent = parent
        self.setWindowTitle("Настройки GOR Browser")
        self.setFixedSize(350, 420)
        self.setStyleSheet(f"background-color: #1c1d21; color: white; font-family: '{parent.settings.get('font_family', 'Segoe UI')}';")

        layout = QVBoxLayout(self)
        layout.addWidget(QLabel("🔍 Поисковая система:"))
        self.search_combo = QComboBox()
        self.search_combo.addItems(SEARCH_ENGINES.keys())
        self.search_combo.setCurrentText(self.parent.settings.get("search_engine", "Google"))
        self.search_combo.setStyleSheet("background: #2c2e33; color: white; padding: 8px; border-radius: 5px; border: 1px solid #444;")
        layout.addWidget(self.search_combo)

        layout.addSpacing(20)
        layout.addWidget(QLabel("🧩 Виджеты на главной:"))
        self.check_clock = QCheckBox("Показывать часы")
        self.check_clock.setChecked(self.parent.settings.get("show_clock", True))
        self.check_title = QCheckBox("Показывать заголовок")
        self.check_title.setChecked(self.parent.settings.get("show_title", True))
        self.check_todo = QCheckBox("Показывать заметки")
        self.check_todo.setChecked(self.parent.settings.get("show_todo", True))

        for cb in [self.check_clock, self.check_title, self.check_todo]:
            cb.setStyleSheet("QCheckBox { spacing: 10px; padding: 5px; } QCheckBox::indicator { width: 18px; height: 18px; }")
            layout.addWidget(cb)

        layout.addStretch()
        btn_save = QPushButton("ПРИМЕНИТЬ ИЗМЕНЕНИЯ")
        btn_save.setStyleSheet(f"background: {parent.settings.get('theme_color', '#4c6ef5')}; color: white; padding: 12px; border-radius: 6px; font-weight: bold; border: none;")
        btn_save.clicked.connect(self.save_settings)
        layout.addWidget(btn_save)

    def save_settings(self):
        self.parent.settings["search_engine"] = self.search_combo.currentText()
        self.parent.settings["show_clock"] = self.check_clock.isChecked()
        self.parent.settings["show_title"] = self.check_title.isChecked()
        self.parent.settings["show_todo"] = self.check_todo.isChecked()
        self.parent.save_data(SETTINGS_FILE, self.parent.settings)
        self.parent.create_start_page()
        self.parent.reload_start_pages()
        self.accept()

class ExtensionManager(QDialog):
    def __init__(self, parent):
        super().__init__(parent)
        self.parent = parent
        self.setWindowTitle("Менеджер расширений GOR")
        self.resize(400, 500)
        self.setStyleSheet(f"background-color: #1c1d21; color: white;")
        layout = QVBoxLayout(self)
        self.list_widget = QListWidget()
        self.list_widget.setStyleSheet("QListWidget::item { padding: 10px; border-bottom: 1px solid #333; }")
        btn_add = QPushButton("+ Добавить JS расширение")
        btn_add.setStyleSheet(f"background: {parent.settings.get('theme_color', '#4c6ef5')}; padding: 10px; border-radius: 5px; font-weight: bold;")
        btn_add.clicked.connect(self.add_extension)
        layout.addWidget(QLabel("Установленные скрипты:"))
        layout.addWidget(self.list_widget)
        layout.addWidget(btn_add)
        self.refresh_list()

    def refresh_list(self):
        self.list_widget.clear()
        for ext in self.parent.extensions:
            item = QListWidgetItem(f"📜 {ext['name']}")
            self.list_widget.addItem(item)
        self.list_widget.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.list_widget.customContextMenuRequested.connect(self.show_ext_menu)

    def show_ext_menu(self, pos):
        item = self.list_widget.itemAt(pos)
        if item:
            menu = QMenu(self)
            del_act = QAction("Удалить расширение", self)
            del_act.triggered.connect(lambda: self.delete_ext(item.text()[3:]))
            menu.addAction(del_act)
            menu.exec(self.list_widget.mapToGlobal(pos))

    def add_extension(self):
        name, ok1 = QInputDialog.getText(self, "Новое расширение", "Название:")
        if ok1 and name:
            code, ok2 = QInputDialog.getMultiLineText(self, "Код", "Вставьте JavaScript код:")
            if ok2 and code:
                self.parent.extensions.append({"name": name, "code": code})
                self.parent.save_data(EXTENSIONS_FILE, self.parent.extensions)
                self.parent.apply_extensions()
                self.refresh_list()

    def delete_ext(self, name):
        self.parent.extensions = [x for x in self.parent.extensions if x['name'] != name]
        self.parent.save_data(EXTENSIONS_FILE, self.parent.extensions)
        self.parent.apply_extensions()
        self.refresh_list()

class DownloadItem(QWidget):
    def __init__(self, download_item: QWebEngineDownloadRequest, parent=None):
        super().__init__(parent)
        self.download_item = download_item
        layout = QHBoxLayout(self) # Используем горизонтальный лейаут для кнопок в ряд
        
        # Информация о файле и прогресс
        info_layout = QVBoxLayout()
        self.label = QLabel(download_item.downloadFileName())
        self.pbar = QProgressBar()
        self.pbar.setFixedHeight(10)
        info_layout.addWidget(self.label)
        info_layout.addWidget(self.pbar)
        layout.addLayout(info_layout)
        
        # Кнопка открытия папки
        self.btn_open = QPushButton("📂")
        self.btn_open.setFixedSize(35, 35)
        self.btn_open.setEnabled(False)
        self.btn_open.setToolTip("Открыть папку")
        self.btn_open.clicked.connect(self.open_folder)
        
        # Кнопка отмены
        self.btn_cancel = QPushButton("❌")
        self.btn_cancel.setFixedSize(35, 35)
        self.btn_cancel.setToolTip("Отменить")
        self.btn_cancel.clicked.connect(lambda: self.download_item.cancel())
        
        layout.addWidget(self.btn_open)
        layout.addWidget(self.btn_cancel)
        
        download_item.receivedBytesChanged.connect(self.update_progress)
        download_item.stateChanged.connect(self.handle_state)

    def update_progress(self):
        total = self.download_item.totalBytes()
        received = self.download_item.receivedBytes()
        
        # Перевод в Мегабайты
        total_mb = total / (1024 * 1024)
        received_mb = received / (1024 * 1024)
        
        self.label.setText(f"{self.download_item.downloadFileName()} ({received_mb:.1f} / {total_mb:.1f} MB)")
        
        if total > 0:
            self.pbar.setValue(int(received / total * 100))

    def open_folder(self):
        # Открывает папку, где лежит файл
        path = self.download_item.downloadDirectory()
        if os.path.exists(path):
            os.startfile(path)

    def handle_state(self, state):
        if state == QWebEngineDownloadRequest.DownloadState.DownloadCompleted:
            self.label.setText(f"✅ {self.download_item.downloadFileName()}")
            self.btn_open.setEnabled(True)
            self.btn_cancel.hide()
        elif state == QWebEngineDownloadRequest.DownloadState.DownloadCancelled:
            self.label.setText(f"❌ Отменено: {self.download_item.downloadFileName()}")
            self.btn_cancel.setEnabled(False)
        elif state == QWebEngineDownloadRequest.DownloadState.DownloadInterrupted:
            self.label.setText(f"⚠️ Ошибка: {self.download_item.downloadFileName()}")


class DownloadManager(QDialog):
    def __init__(self, parent):
        super().__init__(parent)
        self.setWindowTitle("Загрузки GOR")
        self.resize(500, 400)
        self.setStyleSheet("background-color: #1c1d21; color: white;")
        
        self.layout = QVBoxLayout(self)
        
        # Шапка менеджера
        header = QHBoxLayout()
        header.addWidget(QLabel("📦 ТЕКУЩИЕ ЗАГРУЗКИ"))
        btn_clear = QPushButton("Очистить список")
        btn_clear.clicked.connect(self.clear_finished)
        btn_clear.setStyleSheet("background: #2c2e33; padding: 5px; border-radius: 4px;")
        header.addWidget(btn_clear)
        self.layout.addLayout(header)

        self.list_widget = QListWidget()
        self.layout.addWidget(self.list_widget)

    def add_download(self, download_item):
        item = QListWidgetItem(self.list_widget)
        widget = DownloadItem(download_item)
        item.setSizeHint(widget.sizeHint())
        self.list_widget.addItem(item)
        self.list_widget.setItemWidget(item, widget)
        self.show()

    def clear_finished(self):
        # Удаляем из списка только те элементы, где загрузка не идет
        for i in range(self.list_widget.count() - 1, -1, -1):
            item = self.list_widget.item(i)
            widget = self.list_widget.itemWidget(item)
            state = widget.download_item.state()
            if state != QWebEngineDownloadRequest.DownloadState.DownloadInProgress:
                self.list_widget.takeItem(i)

class GORBrowser(QMainWindow):
    def __init__(self):
        super().__init__()
        
        # Установка иконки и базовых параметров окна
        self.setWindowIcon(QIcon(ICON_PATH))
        self.setWindowTitle("GOR Browser - Professional Edition")
        self.resize(1300, 850)
        
        # --- СЕКЦИЯ НАСТРОЕК (БЕЗ ДИНАМИЧЕСКОЙ КАСТОМИЗАЦИИ) ---
        raw_settings = self.load_data(SETTINGS_FILE)
        if isinstance(raw_settings, dict) and raw_settings:
            self.settings = raw_settings
        else:
            # Стандартная темная тема GOR, больше не меняется динамически
            self.settings = {
                "theme_color": "#4c6ef5", 
                "top_bar_color": "#16171a",
                "font_family": "Segoe UI",
                "search_engine": "Google",
                "show_clock": True,
                "show_title": True,
                "show_todo": True,
                "ui_opacity": 0.9,
                "bg_image": ""
            }
        
        # Инициализация профиля и движка
        if not os.path.exists(PROFILE_PATH): os.makedirs(PROFILE_PATH)
        self.profile = QWebEngineProfile("GOR_Profile", self)
        self.profile.setPersistentStoragePath(PROFILE_PATH)
        self.profile.setPersistentCookiesPolicy(QWebEngineProfile.PersistentCookiesPolicy.AllowPersistentCookies)
        
        s = self.profile.settings()
        s.setAttribute(QWebEngineSettings.WebAttribute.LocalStorageEnabled, True)
        s.setAttribute(QWebEngineSettings.WebAttribute.JavascriptCanAccessClipboard, True)
        s.setAttribute(QWebEngineSettings.WebAttribute.ScrollAnimatorEnabled, True)
        s.setAttribute(QWebEngineSettings.WebAttribute.FullScreenSupportEnabled, True)

        self.incognito_profile = QWebEngineProfile(self) 
        self.bookmarks = self.load_data(BOOKMARKS_FILE)
        self.history = self.load_data(HISTORY_FILE)
        
        # Заглушка для расширений (чтобы не удалять строки)
        self.extensions = [] 
        
        # Стартовая страница
        self.create_start_page() 
        self.start_url = QUrl.fromLocalFile(START_PAGE_PATH)

        # Инициализация всех систем интерфейса
        self.init_ui()
        self.setup_shortcuts()
        self.refresh_sidebar_bookmarks()
        self.refresh_sidebar_history()
        
        # Запуск первой вкладки
        self.add_new_tab(self.start_url, "🏠 Главная")

        # Менеджер загрузок
        self.download_manager = DownloadManager(self)
        self.profile.downloadRequested.connect(self.on_download_requested)

    def load_data(self, f):
        """Метод безопасной загрузки данных GOR"""
        if os.path.exists(f):
            try:
                with open(f, "r", encoding="utf-8") as file: return json.load(file)
            except: return [] if "settings" not in f else {}
        return [] if "settings" not in f else {}

    def on_download_requested(self, download):
        """Обработка загрузок файлов"""
        path, _ = QFileDialog.getSaveFileName(self, "Сохранить файл", download.suggestedFileName())
        if path:
            download.setDownloadDirectory(os.path.dirname(path))
            download.setDownloadFileName(os.path.basename(path))
            download.accept()
            self.download_manager.add_download(download)
        else:
            download.interrupt()

    def save_data(self, f, d):
        """Сохранение данных в JSON"""
        with open(f, "w", encoding="utf-8") as file: 
            json.dump(d, file, ensure_ascii=False, indent=4)

    def reload_start_pages(self):
        """Перезагрузка всех открытых стартовых страниц"""
        for i in range(self.tabs.count()):
            browser = self.tabs.widget(i)
            if browser and "start_page.html" in browser.url().toString():
                browser.reload()

    def apply_extensions(self):
        """Заглушка системы расширений (функционал вырезан)"""
        # Система расширений отключена для повышения производительности ядра
        self.profile.scripts().clear()
        pass 

    def init_ui(self):
        """Инициализация главного графического интерфейса"""
        self.update_styles()
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        main_layout = QHBoxLayout(central_widget)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        # САЙДБАР (ЗАКЛАДКИ И ИСТОРИЯ)
        self.sidebar = QFrame(objectName="Sidebar")
        side_v_layout = QVBoxLayout(self.sidebar)
        side_nav = QFrame()
        side_nav_layout = QHBoxLayout(side_nav)
        btn_switch_bm = QPushButton("ЗАКЛАДКИ", objectName="SidebarBtn")
        btn_switch_hist = QPushButton("ИСТОРИЯ", objectName="SidebarBtn")
        btn_switch_bm.clicked.connect(lambda: self.sidebar_stack.setCurrentIndex(0))
        btn_switch_hist.clicked.connect(lambda: self.sidebar_stack.setCurrentIndex(1))
        side_nav_layout.addWidget(btn_switch_bm)
        side_nav_layout.addWidget(btn_switch_hist)
        
        self.sidebar_stack = QStackedWidget()
        self.bookmark_list = QListWidget(objectName="BookmarkList")
        self.bookmark_list.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.bookmark_list.customContextMenuRequested.connect(self.show_bookmark_menu)
        self.bookmark_list.itemClicked.connect(self.on_sidebar_item_clicked)
        
        self.history_list = QListWidget(objectName="HistoryList")
        self.history_list.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.history_list.customContextMenuRequested.connect(self.show_history_menu)
        self.history_list.itemClicked.connect(self.on_sidebar_item_clicked)
        
        self.sidebar_stack.addWidget(self.bookmark_list)
        self.sidebar_stack.addWidget(self.history_list)
        side_v_layout.addWidget(side_nav)
        side_v_layout.addWidget(self.sidebar_stack)
        self.sidebar.hide() 

        # ОСНОВНОЙ КОНТЕНТ
        right_container = QWidget()
        right_layout = QVBoxLayout(right_container)
        right_layout.setContentsMargins(0, 0, 0, 0)
        right_layout.setSpacing(0)

        self.top_bar = QFrame(objectName="TopBar")
        nav_layout = QHBoxLayout(self.top_bar)
        self.btn_side = QPushButton("≡", objectName="NavBtn")
        self.btn_side.clicked.connect(lambda: self.sidebar.setVisible(not self.sidebar.isVisible()))
        self.back_btn = QPushButton("‹", objectName="NavBtn")
        self.back_btn.clicked.connect(lambda: self.tabs.currentWidget().back())
        self.fwd_btn = QPushButton("›", objectName="NavBtn")
        self.fwd_btn.clicked.connect(lambda: self.tabs.currentWidget().forward())
        self.home_btn = QPushButton("🏠", objectName="NavBtn")
        self.home_btn.clicked.connect(lambda: self.tabs.currentWidget().setUrl(self.start_url))
        self.url_bar = QLineEdit()
        self.url_bar.setPlaceholderText("Введите URL или поисковый запрос...")
        self.url_bar.returnPressed.connect(self.navigate_to_url)
        self.btn_incog = QPushButton("🕵️", objectName="NavBtn")
        self.btn_incog.clicked.connect(lambda: self.add_new_tab(self.start_url, "🕵️ Инкогнито", incognito=True))
        self.add_bookmark_btn = QPushButton("★", objectName="NavBtn")
        self.add_bookmark_btn.clicked.connect(self.add_bookmark_dialog)
        self.btn_more = QPushButton("⋮", objectName="NavBtn")
        self.btn_more.clicked.connect(self.show_more_menu)

        nav_layout.addWidget(self.btn_side)
        nav_layout.addWidget(self.back_btn)
        nav_layout.addWidget(self.fwd_btn)
        nav_layout.addWidget(self.home_btn)
        nav_layout.addWidget(self.url_bar)
        nav_layout.addWidget(self.btn_incog)
        nav_layout.addWidget(self.add_bookmark_btn)
        nav_layout.addWidget(self.btn_more)

        self.progress = QProgressBar()
        self.progress.setFixedHeight(2)
        self.progress.setTextVisible(False)
        self.progress.hide()

        self.tabs = QTabWidget()
        self.tabs.setTabsClosable(True)
        self.tabs.setMovable(True)
        self.tabs.tabCloseRequested.connect(self.close_tab)
        self.add_tab_btn = QToolButton(objectName="AddTabBtn")
        self.add_tab_btn.setText("+")
        self.add_tab_btn.clicked.connect(lambda: self.add_new_tab())
        self.tabs.setCornerWidget(self.add_tab_btn, Qt.Corner.TopRightCorner)

        right_layout.addWidget(self.top_bar)
        right_layout.addWidget(self.progress)
        right_layout.addWidget(self.tabs)
        main_layout.addWidget(self.sidebar)
        main_layout.addWidget(right_container)

    def update_styles(self):
        """Применение визуального стиля GOR-Dark"""
        accent = self.settings.get("theme_color", "#4c6ef5")
        top_color = self.settings.get("top_bar_color", "#16171a")
        font = self.settings.get("font_family", "Segoe UI")
        
        self.setStyleSheet(f"""
            QMainWindow {{ background-color: #0b0c0d; font-family: '{font}'; }}
            #TopBar {{ background-color: {top_color}; padding: 4px 8px; border-bottom: 1px solid #25262b; }}
            #Sidebar {{ background-color: #1c1b22; border-right: 1px solid #25262b; min-width: 220px; }}
            #SidebarBtn {{ background: transparent; color: #868e96; border: none; font-size: 10px; font-weight: bold; padding: 10px; }}
            #SidebarBtn:hover {{ color: {accent}; }}
            #BookmarkList, #HistoryList {{ background: transparent; border: none; color: #cfcfd8; font-size: 11px; outline: none; }}
            #BookmarkList::item, #HistoryList::item {{ padding: 8px; border-radius: 4px; }}
            #BookmarkList::item:hover, #HistoryList::item:hover {{ background-color: #2b2a33; }}
            QLineEdit {{ background-color: #1c1d21; color: #ced4da; border-radius: 6px; padding: 4px 12px; border: 1px solid #2c2e33; }}
            QLineEdit:focus {{ border: 1px solid {accent}; }}
            QPushButton#NavBtn {{ background-color: transparent; color: #868e96; font-size: 18px; width: 30px; height: 30px; border-radius: 4px; border: none; }}
            QPushButton#NavBtn:hover {{ background-color: #2c2e33; color: {accent}; }}
            QProgressBar::chunk {{ background-color: {accent}; }}
            QTabWidget::pane {{ border: none; }}
            QTabBar::tab {{ background: #16171a; color: #868e96; padding: 8px 15px; border: 1px solid #25262b; border-bottom: none; min-width: 120px; }}
            QTabBar::tab:selected {{ background: #1c1d21; color: {accent}; border-bottom: 2px solid {accent}; }}
            QMenu {{ background-color: #1c1d21; color: white; border: 1px solid #2c2e33; padding: 5px; }}
            QMenu::item {{ padding: 8px 25px; border-radius: 4px; }}
            QMenu::item:selected {{ background-color: {accent}; }}
            #AddTabBtn {{ background: transparent; color: white; font-size: 16px; border: none; padding: 5px; }}
        """)

    def show_more_menu(self):
        """Меню настроек и инструментов (вырезана кастомизация)"""
        menu = QMenu(self)
        act_set = QAction("⚙️ Настройки браузера", self)
        act_set.triggered.connect(lambda: SettingsDialog(self).exec())
        act_dev = QAction("🛠️ Инструменты разработчика (F12)", self)
        act_dev.triggered.connect(self.toggle_devtools)
        
        menu.addAction(act_set)
        menu.addAction(act_dev)
        menu.exec(self.btn_more.mapToGlobal(QPoint(0, self.btn_more.height())))

    def toggle_devtools(self):
        """Запуск панели разработчика"""
        browser = self.tabs.currentWidget()
        if browser:
            dev_view = QWebEngineView()
            browser.page().setDevToolsPage(dev_view.page())
            dev_dialog = QDialog(self)
            dev_dialog.setWindowTitle("GOR DevTools Engine")
            dev_dialog.resize(900, 600)
            layout = QVBoxLayout(dev_dialog)
            layout.setContentsMargins(0,0,0,0)
            layout.addWidget(dev_view)
            dev_dialog.show()

    def add_new_tab(self, qurl=None, label="Новая вкладка", incognito=False):
        """Создание новой вкладки в движке"""
        if qurl is None: qurl = self.start_url
        browser = QWebEngineView()
        prof = self.incognito_profile if incognito else self.profile
        page = GORWebPage(prof, browser)
        page.ins_browser = self
        browser.setPage(page)
        browser.setUrl(qurl)
        index = self.tabs.addTab(browser, label)
        self.tabs.setCurrentIndex(index)
        browser.urlChanged.connect(lambda q, b=browser: self.on_url_changed(q, b))
        browser.loadFinished.connect(lambda _, b=browser: self.update_tab_title(b))
        browser.loadProgress.connect(self.update_progress)
        return browser

    def update_progress(self, p):
        """Обновление индикатора загрузки"""
        self.progress.setValue(p)
        self.progress.setVisible(p < 100)

    def on_url_changed(self, qurl, browser):
        """Событие при смене адреса"""
        url_str = qurl.toString()
        if browser == self.tabs.currentWidget():
            self.url_bar.setText("" if "start_page.html" in url_str else url_str)
        if browser.page().profile() != self.incognito_profile and "start_page.html" not in url_str:
            self.add_to_history(browser.page().title() or url_str, url_str)

    def add_to_history(self, title, url):
        """Добавление записи в историю GOR"""
        time_str = datetime.now().strftime("%H:%M")
        self.history.insert(0, {"title": title, "url": url, "time": time_str})
        self.history = self.history[:150] # Лимит истории расширен
        self.save_data(HISTORY_FILE, self.history)
        self.refresh_sidebar_history()

    def update_tab_title(self, browser):
        """Обновление текста на вкладке"""
        index = self.tabs.indexOf(browser)
        if index != -1:
            title = browser.page().title() or "Загрузка..."
            self.tabs.setTabText(index, title[:15])

    def navigate_to_url(self):
        """Переход по введенному адресу или поиск"""
        text = self.url_bar.text().strip()
        if not text: return
        engine_name = self.settings.get("search_engine", "Google")
        search_url = SEARCH_ENGINES.get(engine_name, SEARCH_ENGINES["Google"])
        url = QUrl(f"{search_url}{text}") if "." not in text else QUrl(text if "://" in text else "http://" + text)
        self.tabs.currentWidget().setUrl(url)

    def refresh_sidebar_bookmarks(self):
        """Обновление списка закладок в сайдбаре"""
        self.bookmark_list.clear()
        for bm in self.bookmarks:
            item = QListWidgetItem(f"⭐ {bm['name']}")
            item.setData(Qt.ItemDataRole.UserRole, bm['url'])
            self.bookmark_list.addItem(item)

    def refresh_sidebar_history(self):
        """Обновление списка истории в сайдбаре"""
        self.history_list.clear()
        for h in self.history:
            t = h.get('time', '--:--')
            n = h.get('title', '...')[:30]
            item = QListWidgetItem(f"🕒 {t} {n}")
            item.setData(Qt.ItemDataRole.UserRole, h.get('url'))
            self.history_list.addItem(item)

    def show_bookmark_menu(self, pos):
        """Контекстное меню закладок"""
        item = self.bookmark_list.itemAt(pos)
        if item:
            menu = QMenu()
            del_act = QAction("Удалить закладку", self)
            del_act.triggered.connect(lambda: self.delete_item(item, "bm"))
            menu.addAction(del_act)
            menu.exec(self.bookmark_list.mapToGlobal(pos))

    def show_history_menu(self, pos):
        """Контекстное меню истории"""
        item = self.history_list.itemAt(pos)
        if item:
            menu = QMenu()
            del_act = QAction("Удалить из истории", self)
            del_act.triggered.connect(lambda: self.delete_item(item, "hist"))
            menu.addAction(del_act)
            menu.exec(self.history_list.mapToGlobal(pos))

    def delete_item(self, item, mode):
        """Удаление элементов из БД"""
        url = item.data(Qt.ItemDataRole.UserRole)
        if mode == "bm":
            self.bookmarks = [x for x in self.bookmarks if x['url'] != url]
            self.save_data(BOOKMARKS_FILE, self.bookmarks)
            self.refresh_sidebar_bookmarks()
        else:
            self.history = [x for x in self.history if x['url'] != url]
            self.save_data(HISTORY_FILE, self.history)
            self.refresh_sidebar_history()

    def on_sidebar_item_clicked(self, item):
        """Переход по ссылке из сайдбара"""
        target_url = item.data(Qt.ItemDataRole.UserRole)
        if target_url:
            self.tabs.currentWidget().setUrl(QUrl(target_url))

    def add_bookmark_dialog(self):
        """Диалог добавления новой закладки"""
        browser = self.tabs.currentWidget()
        name, ok = QInputDialog.getText(self, "Новая закладка", "Имя закладки:", text=browser.page().title()[:20])
        if ok and name:
            self.bookmarks.append({"name": name, "url": browser.url().toString()})
            self.save_data(BOOKMARKS_FILE, self.bookmarks)
            self.refresh_sidebar_bookmarks()

    def setup_shortcuts(self):
        """Настройка горячих клавиш GOR"""
        QShortcut(QKeySequence("Ctrl+T"), self).activated.connect(lambda: self.add_new_tab())
        QShortcut(QKeySequence("Ctrl+W"), self).activated.connect(lambda: self.close_tab(self.tabs.currentIndex()))
        QShortcut(QKeySequence("Ctrl+H"), self).activated.connect(lambda: self.sidebar.setVisible(not self.sidebar.isVisible()))
        QShortcut(QKeySequence("F12"), self).activated.connect(self.toggle_devtools)

    def close_tab(self, i):
        """Закрытие активной вкладки"""
        if self.tabs.count() > 1: self.tabs.removeTab(i)
        else: self.tabs.currentWidget().setUrl(self.start_url)

    def create_start_page(self):
        """Генерация быстрой стартовой страницы (БЕЗ AI И КАСТОМИЗАЦИИ)"""
        accent = self.settings.get("theme_color", "#4c6ef5")
        opacity = 0.9
        font = self.settings.get("font_family", "Segoe UI")
        engine_name = self.settings.get("search_engine", "Google")
        search_url = SEARCH_ENGINES.get(engine_name, SEARCH_ENGINES["Google"])

        with open(START_PAGE_PATH, "w", encoding="utf-8") as f:
            f.write(f"""<!DOCTYPE html>
            <html>
            <head>
                <meta charset="UTF-8">
                <style>
                    body {{ 
                        background: #0b0c0d;
                        color:white; font-family:'{font}', sans-serif; 
                        display:flex; flex-direction:column; align-items:center; 
                        padding-top:100px; margin:0; min-height: 100vh;
                    }}
                    #clock {{ font-size:110px; font-weight:100; color:{accent}; margin-bottom: 10px; }}
                    #title {{ margin-bottom:40px; letter-spacing: 8px; font-weight: 300; text-align: center; color: #555; }}
                    .search-container {{ width: 600px; }}
                    .search-box {{
                        background: rgba(28, 29, 33, {opacity}); border-radius: 40px; 
                        border: 1px solid rgba(255,255,255,0.1); display: flex; align-items: center; padding: 5px 25px;
                    }}
                    input {{ flex:1; background:transparent; border:none; color:white; padding:15px; outline:none; font-size:18px; }}
                    .footer-info {{ position: fixed; bottom: 20px; color: #333; font-size: 12px; letter-spacing: 2px; }}
                </style>
                <body>
                    <div id="clock">00:00</div>
                    <h1 id="title">GOR CORE</h1>
                    <div class="search-container">
                        <div class="search-box">
                            <input type="text" id="searchInput" placeholder="Поиск в {engine_name}..." onkeypress="handleSearch(event)">
                        </div>
                    </div>
                    <div class="footer-info">SYSTEM ENGINE v3.0</div>
                    <script>
                        function updateTime() {{ 
                            const now = new Date(); 
                            document.getElementById('clock').innerText = now.getHours().toString().padStart(2, '0') + ":" + now.getMinutes().toString().padStart(2, '0'); 
                        }}
                        setInterval(updateTime, 1000); updateTime();
                        function handleSearch(event) {{
                            if (event.key === 'Enter') {{
                                window.location.href = '{search_url}' + encodeURIComponent(event.target.value);
                            }}
                        }}
                    </script>
                </body></html>""")
if __name__ == "__main__":
    # Мы убрали запуск subprocess.Popen([sys.executable, "app.py"]), 
    # так как сервер Flask для ИИ нам больше не нужен.

    app = QApplication(sys.argv)
    
    # Можно добавить базовую настройку стиля, чтобы браузер сразу выглядел круто
    app.setStyle("Fusion") 
    
    window = GORBrowser()
    window.show()
    sys.exit(app.exec())