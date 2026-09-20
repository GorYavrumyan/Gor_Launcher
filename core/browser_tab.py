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

# 2. Определяем BASE_DIR правильно, чтобы настройки не стирались
# Если запущено как .exe, используем путь к экзешнику, а не к временной папке
if getattr(sys, 'frozen', False):
    BASE_DIR = os.path.dirname(sys.executable)
else:
    BASE_DIR = os.path.dirname(os.path.abspath(__file__))

# 3. Применяем пути
_ICO_CANDIDATE = get_resource_path("Gor_Brauzer.ico")
ICON_PATH = _ICO_CANDIDATE if os.path.exists(_ICO_CANDIDATE) else "favicon.ico"
START_PAGE_PATH = get_resource_path("start_page.html")

# --- ИНТЕГРАЦИЯ С GOR LAUNCHER ---
# Раньше браузер хранил закладки/историю/настройки в отдельных файлах
# (bookmarks.json, history.json, settings.json, extensions.json) рядом с собой.
# Теперь всё это лежит ВНУТРИ общего games_data.json лаунчера, в отдельном
# блоке "browser", чтобы не плодить лишние файлы и не терять данные при
# переносе/архивации проекта. DATA_FILE - тот же файл, что использует
# GORLauncher (core/GorLauncher.py: self.data_file = "games_data.json"),
# путь относительный, т.к. лаунчер всегда запускается с cwd = корень проекта.
DATA_FILE = "games_data.json"

# Ключи под-блока "browser" внутри games_data.json (раньше были именами файлов)
BOOKMARKS_FILE = "bookmarks"
HISTORY_FILE = "history"
PASSWORDS_FILE = "passwords"
SETTINGS_FILE = "settings"
EXTENSIONS_FILE = "extensions"
PROFILE_PATH = os.path.join(BASE_DIR, "GOR_Profile")
SEARCH_ENGINES = {
    "Google": "https://google.com/search?q=",
    "Yandex": "https://yandex.ru/search/?text=",
    "Bing": "https://www.bing.com/search?q=",
    "DuckDuckGo": "https://duckduckgo.com/?q="
}


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
        # ВАЖНО: если ссылка открывается ИЗ вкладки инкогнито, новая вкладка
        # тоже должна быть инкогнито - иначе это дыра в приватности
        # (данные "утекли" бы в обычный профиль через window.open()/target=_blank).
        is_incognito = self.profile() == self.ins_browser.incognito_profile
        new_tab_widget = self.ins_browser.add_new_tab(incognito=is_incognito)
        
        # КРИТИЧЕСКОЕ ИСПРАВЛЕНИЕ: возвращаем .page(), а не сам виджет.
        # Это предотвращает вылеты при открытии ссылок в новых окнах.
        return new_tab_widget.page()

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
        # Открывает папку, где лежит файл (кроссплатформенно)
        path = self.download_item.downloadDirectory()
        if os.path.exists(path):
            if hasattr(os, "startfile"):
                os.startfile(path)  # Windows
            elif sys.platform == "darwin":
                subprocess.run(["open", path])
            else:
                subprocess.run(["xdg-open", path])

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

class GORBrowser(QWidget):  # ИСПРАВЛЕНО: QWidget вместо QMainWindow для корректного встраивания
    def __init__(self, parent=None):
        super().__init__(parent)
        
        # Базовые параметры (setWindowTitle и setWindowIcon игнорируются внутри вкладки, но оставлены)
        self.setWindowIcon(QIcon(ICON_PATH))
        self.setWindowTitle("GOR Browser - Professional Edition")
        # resize не нужен для виджета во вкладке, но оставляем для сохранения объема кода
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

        # --- ИСПРАВЛЕННЫЙ МАКЕТ ---
        # Мы создаем основной Layout ОДИН РАЗ здесь или используем существующий.
        # Это решает проблему "already has a layout"
        if self.layout() is None:
            self.main_layout = QVBoxLayout(self)
        else:
            self.main_layout = self.layout()

        self.main_layout.setContentsMargins(0, 0, 0, 0)
        self.main_layout.setSpacing(0)

        # Инициализация всех систем интерфейса
        # ВАЖНО: Внутри init_ui теперь используется self.main_layout.addWidget()
        self.init_ui() 
        
        self.setup_shortcuts()
        self.refresh_sidebar_bookmarks()
        self.refresh_sidebar_history()
        
        # Запуск первой вкладки
        self.add_new_tab(self.start_url, "🏠 Главная")
        # Менеджер загрузок
        self.download_manager = DownloadManager(self)
        self.profile.downloadRequested.connect(self.on_download_requested)

    def _read_full_data(self):
        """Читает целиком games_data.json лаунчера (groups/standalone/history/browser)."""
        if os.path.exists(DATA_FILE):
            try:
                with open(DATA_FILE, "r", encoding="utf-8") as file:
                    data = json.load(file)
                    if isinstance(data, dict):
                        return data
            except Exception:
                pass
        return {}

    def load_data(self, key):
        """Загружает под-раздел браузера (bookmarks/history/settings/extensions)
        из общего блока "browser" в games_data.json. Ничего не удаляет и не
        трогает остальные данные лаунчера (игры, группы, историю запусков)."""
        data = self._read_full_data()
        browser_block = data.get("browser", {})
        if not isinstance(browser_block, dict):
            browser_block = {}
        return browser_block.get(key, {} if key == SETTINGS_FILE else [])

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

    def save_data(self, key, value):
        """Сохраняет под-раздел браузера обратно в общий games_data.json
        лаунчера, в блок "browser", не затрагивая данные игр/групп/истории
        запусков (они читаются и пишутся обратно как есть)."""
        data = self._read_full_data()
        if not isinstance(data.get("browser"), dict):
            data["browser"] = {}
        data["browser"][key] = value
        with open(DATA_FILE, "w", encoding="utf-8") as file:
            json.dump(data, file, ensure_ascii=False, indent=4)

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

    def update_styles(self):
        """Метод для применения стилей интерфейса"""
        accent = self.settings.get("theme_color", "#4c6ef5")
        top_bg = self.settings.get("top_bar_color", "#16171a")
        font = self.settings.get("font_family", "Segoe UI")
        
        self.setStyleSheet(f"""
            QWidget {{ font-family: '{font}'; color: white; }}
            #TopBar {{ background-color: {top_bg}; border-bottom: 1px solid #333; }}
            #Sidebar {{ background-color: #16171a; border-right: 1px solid #333; min-width: 250px; }}
            QLineEdit {{ background: #2c2e33; border-radius: 5px; padding: 8px; color: white; border: 1px solid #444; }}
            QLineEdit:focus {{ border: 1px solid {accent}; }}
            #NavBtn, #AddTabBtn, #SidebarBtn {{ 
                background: transparent; border-radius: 5px; padding: 5px; font-size: 16px; 
            }}
            #NavBtn:hover, #AddTabBtn:hover {{ background: #3c3f45; }}
            QTabWidget::pane {{ border-top: 1px solid #333; background: #0b0c0d; }}
            QTabBar::tab {{
                background: #1c1d21; border-right: 1px solid #333;
                padding: 8px 8px 8px 14px; margin: 0px;
                min-width: 60px; max-width: 180px;
            }}
            QTabBar::tab:selected {{ background: #0b0c0d; border-bottom: 2px solid {accent}; }}
            QTabBar::close-button {{
                subcontrol-position: right;
                border-radius: 3px;
                margin: 2px;
                padding: 1px;
            }}
            QTabBar::close-button:hover {{ background: #3c3f45; }}
            QProgressBar::chunk {{ background-color: {accent}; }}
            QListWidget {{ background: transparent; border: none; outline: none; }}
            QListWidget::item {{ padding: 10px; border-bottom: 1px solid #222; }}
            QListWidget::item:selected {{ background: {accent}; color: white; }}
        """)

    def init_ui(self):
        """Инициализация интерфейса: Сайдбар слева, Контент справа"""
        self.update_styles()
        
        # 1. Полная очистка макета, чтобы избежать конфликтов (ошибка QLayout)
        if self.layout() is not None:
            old_layout = self.layout()
            while old_layout.count():
                item = old_layout.takeAt(0)
                if item.widget():
                    item.widget().deleteLater()
            self.main_layout = old_layout
        else:
            self.main_layout = QVBoxLayout(self)

        self.main_layout.setContentsMargins(0, 0, 0, 0)
        self.main_layout.setSpacing(0)

        # --- СОЗДАЕМ ГОРИЗОНТАЛЬНУЮ ОСНОВУ ---
        # Это главный секрет: создаем виджет, который держит ЛЕВО и ПРАВО в ряд
        horizontal_container = QWidget()
        hbox = QHBoxLayout(horizontal_container) # Здесь именно QHBoxLayout
        hbox.setContentsMargins(0, 0, 0, 0)
        hbox.setSpacing(0)

        # --- САЙДБАР (ЗАКЛАДКИ И ИСТОРИЯ) ---
        self.sidebar = QFrame(objectName="Sidebar")
        self.sidebar.setFixedWidth(250) # Фиксируем ширину, чтобы не прыгал
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

        # --- ОСНОВНОЙ КОНТЕНТ (Правая часть) ---
        right_container = QWidget()
        right_layout = QVBoxLayout(right_container)
        right_layout.setContentsMargins(0, 0, 0, 0)
        right_layout.setSpacing(0)

        # (Твой существующий код TopBar, Progress и Tabs)
        self.top_bar = QFrame(objectName="TopBar")
        nav_layout = QHBoxLayout(self.top_bar)
        self.btn_side = QPushButton("≡", objectName="NavBtn")
        self.btn_side.clicked.connect(lambda: self.sidebar.setVisible(not self.sidebar.isVisible()))
        
        self.back_btn = QPushButton("‹", objectName="NavBtn")
        self.back_btn.clicked.connect(lambda: self.tabs.currentWidget().back() if self.tabs.currentWidget() else None)
        self.fwd_btn = QPushButton("›", objectName="NavBtn")
        self.fwd_btn.clicked.connect(lambda: self.tabs.currentWidget().forward() if self.tabs.currentWidget() else None)
        self.home_btn = QPushButton("🏠", objectName="NavBtn")
        self.home_btn.clicked.connect(lambda: self.tabs.currentWidget().setUrl(self.start_url) if self.tabs.currentWidget() else None)
        
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
        self.tabs.setIconSize(QSize(16, 16))  # Размер favicon во вкладках
        self.tabs.setUsesScrollButtons(True)
        self.tabs.tabBar().setElideMode(Qt.TextElideMode.ElideRight)
        self.tabs.tabCloseRequested.connect(self.close_tab)
        
        self.add_tab_btn = QToolButton(objectName="AddTabBtn")
        self.add_tab_btn.setText("+")
        self.add_tab_btn.clicked.connect(lambda: self.add_new_tab())
        self.tabs.setCornerWidget(self.add_tab_btn, Qt.Corner.TopRightCorner)

        right_layout.addWidget(self.top_bar)
        right_layout.addWidget(self.progress)
        right_layout.addWidget(self.tabs)

        # --- СБОРКА В ГОРИЗОНТАЛЬНЫЙ РЯД ---
        hbox.addWidget(self.sidebar)         # ПЕРВЫМ добавляем сайдбар (лево)
        hbox.addWidget(right_container, 1)   # ВТОРЫМ браузер (право, коэффициент 1 чтобы растянулся)

        # Добавляем все это в окно
        self.main_layout.addWidget(horizontal_container)
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
            # ВАЖНО: храним ссылки в self, иначе PyQt соберет объекты
            # мусорщиком и окно DevTools закроется сразу же после открытия.
            self._dev_view = QWebEngineView()
            browser.page().setDevToolsPage(self._dev_view.page())
            self._dev_dialog = QDialog(self)
            self._dev_dialog.setWindowTitle("GOR DevTools Engine")
            self._dev_dialog.resize(900, 600)
            layout = QVBoxLayout(self._dev_dialog)
            layout.setContentsMargins(0, 0, 0, 0)
            layout.addWidget(self._dev_view)
            self._dev_dialog.show()

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
        browser.iconChanged.connect(lambda icon, b=browser: self.update_tab_icon(b, icon))
        return browser

    def update_tab_icon(self, browser, icon):
        """Устанавливает favicon сайта на вкладке (реальный источник иконок в GOR)"""
        index = self.tabs.indexOf(browser)
        if index == -1:
            return
        if browser.property("gor_cover_picker_label"):
            # У служебной вкладки "выбор обложки" всегда одна и та же
            # иконка - настоящий favicon сайта её бы затёр и вкладку
            # стало бы не отличить от обычной.
            return
        url_str = browser.url().toString()
        if "start_page.html" in url_str:
            # На стартовой странице своя иконка (эмодзи-дом) — favicon не нужен
            self.tabs.setTabIcon(index, QIcon())
        elif not icon.isNull():
            self.tabs.setTabIcon(index, icon)

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
            # Служебные вкладки (например "режим выбора обложки", который
            # открывает GameEditor через IPC - см. GorLauncher.py) держат
            # свой заголовок ФИКСИРОВАННЫМ, чтобы пользователь всегда видел,
            # что это не обычная вкладка, даже когда внутри неё загружаются
            # обычные сайты со своими title.
            fixed_label = browser.property("gor_cover_picker_label")
            if fixed_label:
                self.tabs.setTabText(index, fixed_label)
                return
            url_str = browser.url().toString()
            if "start_page.html" in url_str:
                # Домашняя страница - всегда просто иконка домика (или маски для инкогнито),
                # без имени файла start_page.html
                is_incognito = browser.page().profile() == self.incognito_profile
                self.tabs.setTabText(index, "🕵️" if is_incognito else "🏠")
            else:
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

# --- 1. СНАЧАЛА ПОЛУЧАЕМ НАСТРОЙКИ (ИСПРАВЛЕНО: show_todo) ---
        show_clock = self.settings.get("show_clock", True)
        show_title = self.settings.get("show_title", True)
        show_notes = self.settings.get("show_todo", True) # Ключ изменен на show_todo для синхронизации с JSON

        # --- 2. ФОРМИРУЕМ HTML-БЛОКИ (ЕСЛИ FALSE, БУДЕТ ПУСТАЯ СТРОКА) ---
        clock_html = '<div id="clock">00:00</div>' if show_clock else ''
        title_html = '<h1 id="title">GOR CORE</h1>' if show_title else ''
        
        # Если show_notes (взятый из show_todo) == False, этот блок полностью исчезнет
        if show_notes:
            notes_html = """
            <div id="notes-wrapper">
                <div id="notes-container">
                    <div class="notes-header">
                        <span>ЛИЧНЫЕ ЗАМЕТКИ</span>
                        <button onclick="addNote()">НОВАЯ ЗАМЕТКА +</button>
                    </div>
                    <div id="notes-list"></div>
                </div>
            </div>
            """
        else:
            notes_html = ""

        # --- 3. ЗАПИСЫВАЕМ ВСЁ В ФАЙЛ (ВИЗУАЛ И СКРИПТЫ СОХРАНЕНЫ ПОЛНОСТЬЮ) ---
        with open(START_PAGE_PATH, "w", encoding="utf-8") as f:
            f.write(f"""<!DOCTYPE html>
            <html>
            <head>
                <meta charset="UTF-8">
                <style>
                    * {{ box-sizing: border-box; }}
                    html, body {{
                        height: 100%; margin: 0; padding: 0;
                        overflow: hidden; background: #0b0c0d;
                        color: white; font-family: '{font}', sans-serif;
                    }}
                    body {{ display: flex; flex-direction: column; align-items: center; padding-top: 5vh; }}
                    #clock {{ font-size: 110px; font-weight: 100; color: {accent}; margin-bottom: 5px; }}
                    #title {{ margin-bottom: 30px; letter-spacing: 8px; font-weight: 300; color: #555; }}
                    .search-container {{ width: 600px; margin-bottom: 20px; flex-shrink: 0; }}
                    .search-box {{
                        background: rgba(28, 29, 33, {opacity}); 
                        border-radius: 40px; border: 1px solid rgba(255,255,255,0.1); 
                        display: flex; align-items: center; padding: 5px 25px;
                    }}
                    input {{ flex: 1; background: transparent; border:none; color:white; padding:15px; outline:none; font-size:18px; }}

                    /* СТИЛИ ЗАМЕТОК: ШИРИНА 600px, БЕЗ СКРОЛЛА ОКНА */
                    #notes-wrapper {{ width: 600px; display: flex; justify-content: center; flex-grow: 1; overflow: hidden; margin-bottom: 60px; }}
                    #notes-container {{ width: 100%; background: rgba(20, 21, 24, 0.6); border: 1px solid #333; border-radius: 20px; display: flex; flex-direction: column; max-height: 100%; }}
                    .notes-header {{ padding: 15px 20px; border-bottom: 1px solid #333; display: flex; justify-content: space-between; font-size: 10px; letter-spacing: 3px; color: {accent}; font-weight: bold; flex-shrink: 0; }}
                    .notes-header button {{ background: transparent; border: 1px solid {accent}; color: {accent}; border-radius: 5px; cursor: pointer; padding: 3px 10px; font-size: 10px; }}
                    
                    /* СКРОЛЛ ТОЛЬКО ВНУТРИ СПИСКА */
                    #notes-list {{ overflow-y: auto; padding: 15px; display: grid; grid-template-columns: 1fr 1fr; gap: 10px; }}
                    #notes-list::-webkit-scrollbar {{ width: 0px; }} /* Скрываем полосу прокрутки */
                    
                    .note-item {{ background: #1c1d21; padding: 12px; border-radius: 10px; font-size: 14px; border-left: 4px solid {accent}; cursor: pointer; }}
                    
                    #ctx-menu {{ position: fixed; background: #2c2e33; border: 1px solid #444; border-radius: 8px; display: none; z-index: 1000; min-width: 150px; }}
                    .ctx-item {{ padding: 12px; cursor: pointer; font-size: 13px; }}
                    .ctx-item:hover {{ background: {accent}; }}
                    .footer-info {{ position: fixed; bottom: 20px; color: #333; font-size: 12px; letter-spacing: 2px; }}
                </style>
            </head>
            <body>
                {clock_html}
                {title_html}
                
                <div class="search-container">
                    <div class="search-box">
                        <input type="text" id="searchInput" placeholder="Поиск в системе..." onkeypress="handleSearch(event)">
                    </div>
                </div>

                {notes_html}

                <div id="ctx-menu">
                    <div class="ctx-item" onclick="editNote()">✏️ Редактировать</div>
                    <div class="ctx-item" style="color: #ff5555;" onclick="deleteNoteWithConfirm()">🗑️ Удалить</div>
                </div>

                <div class="footer-info">SYSTEM ENGINE v3.0</div>
                
                <script>
                    let notes = JSON.parse(localStorage.getItem('gor_notes') || '[]');
                    let selectedNoteIndex = -1;

                    function saveNotes() {{
                        localStorage.setItem('gor_notes', JSON.stringify(notes));
                        renderNotes();
                    }}

                    function addNote() {{
                        const text = prompt("О чем вы думаете?");
                        if (text) {{ notes.push(text); saveNotes(); }}
                    }}

                    function renderNotes() {{
                        const list = document.getElementById('notes-list');
                        if (!list) return; 
                        list.innerHTML = '';
                        notes.forEach((note, index) => {{
                            const div = document.createElement('div');
                            div.className = 'note-item';
                            div.innerText = note;
                            div.oncontextmenu = (e) => showMenu(e, index);
                            list.appendChild(div);
                        }});
                    }}

                    function showMenu(e, index) {{
                        e.preventDefault();
                        selectedNoteIndex = index;
                        const menu = document.getElementById('ctx-menu');
                        if (menu) {{
                            menu.style.display = 'block';
                            menu.style.left = e.pageX + 'px';
                            menu.style.top = e.pageY + 'px';
                        }}
                    }}

                    function deleteNoteWithConfirm() {{
                        if (confirm("Удалить заметку?")) {{ notes.splice(selectedNoteIndex, 1); saveNotes(); }}
                        hideMenu();
                    }}

                    function editNote() {{
                        const newText = prompt("Изменить:", notes[selectedNoteIndex]);
                        if (newText) {{ notes[selectedNoteIndex] = newText; saveNotes(); }}
                        hideMenu();
                    }}

                    function hideMenu() {{ 
                        const menu = document.getElementById('ctx-menu');
                        if(menu) menu.style.display = 'none'; 
                    }}
                    window.onclick = hideMenu;

                    function updateTime() {{ 
                        const clockEl = document.getElementById('clock');
                        if (clockEl) {{
                            const now = new Date(); 
                            clockEl.innerText = now.getHours().toString().padStart(2, '0') + ":" + now.getMinutes().toString().padStart(2, '0'); 
                        }}
                    }}
                    setInterval(updateTime, 1000); updateTime();
                    renderNotes();

                    function handleSearch(event) {{
                        if (event.key === 'Enter') {{
                            window.location.href = '{search_url}' + encodeURIComponent(event.target.value);
                        }}
                    }}
                </script>
            </body></html>""")

# --- ЗАПУСК ПРИЛОЖЕНИЯ ---
if __name__ == "__main__":
    app = QApplication(sys.argv)
    
    # Создаем временное главное окно для теста, если запускаем файл отдельно
    test_window = QMainWindow() 
    test_window.setWindowTitle("GOR Browser Engine Test")
    test_window.resize(1200, 800)
    
    # Создаем браузер
    browser_widget = GORBrowser() 
    
    # Вставляем виджет внутрь окна
    test_window.setCentralWidget(browser_widget)
    
    test_window.show()
    sys.exit(app.exec())