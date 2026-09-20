"""
browser_widget.py
-------------------
GORBrowser - главный виджет встроенного браузера GOR Launcher: вкладки,
тулбар навигации, сайдбар закладок/истории, хранение настроек в
games_data.json. Логика, которая раньше жила в одном файле core/browser_tab.py,
теперь разложена по соседним модулям пакета GOR_Brauzer:

    browser_constants.py  - пути и ключи хранения (без них не работает ничего)
    browser_page.py        - GORWebPage (обработка новых вкладок/окон)
    browser_downloads.py   - DownloadItem, DownloadManager
    browser_dialogs.py     - SettingsDialog, CustomizationManager, ExtensionManager
    browser_startpage.py   - генерация start_page.html
    browser_widget.py      - этот файл: сам GORBrowser, который использует всё вышеперечисленное

GorLauncher.py по-прежнему делает `from browser_widget import GORBrowser`
(модуль просто лежит в другой папке - GOR_Brauzer вместо core, путь к ней
добавлен в sys.path в bridge_loader.py / GorLauncher.py).
"""

import base64
import json
import os
import sys
import time
from datetime import datetime, timedelta

from PyQt6.QtCore import QUrl, Qt, QSize, QPoint, QTimer, QBuffer, QIODevice
from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QVBoxLayout, QWidget,
    QLineEdit, QTabWidget, QHBoxLayout, QPushButton,
    QFrame, QInputDialog, QMessageBox, QFileDialog, QColorDialog,
    QToolButton, QProgressBar, QLabel, QListWidget, QListWidgetItem,
    QStackedWidget, QMenu, QDialog, QSplitter, QTabBar,
)
from PyQt6.QtGui import QKeySequence, QShortcut, QIcon, QAction, QColor, QPixmap, QPainter, QFont

from PyQt6.QtWebEngineWidgets import QWebEngineView
from PyQt6.QtWebEngineCore import QWebEngineProfile, QWebEngineSettings, QWebEnginePage, QWebEngineScript

from browser_constants import (
    ICON_PATH, START_PAGE_PATH, PROFILE_PATH, DATA_FILE,
    BOOKMARKS_FILE, HISTORY_FILE, SETTINGS_FILE, EXTENSIONS_FILE,
    SEARCH_ENGINES, DEFAULT_SETTINGS, get_startpage_engines,
    TAB_GROUPS_FILE, SESSION_FILE,
)
from browser_page import GORWebPage
from browser_downloads import DownloadManager
from browser_dialogs import BrowserSettingsWindow, _lighten, _darken
from browser_startpage import write_start_page
from browser_adblock import (
    GorAdBlockInterceptor, install_cosmetic_filter, load_extra_blocklist,
    GorAdBlockUpdater, load_dynamic_blocklist_cache,
)
from browser_passwords import PasswordVault
from lang_loader import tr
from browser_translate import install_vot_translator
from browser_groups import GroupsPanel, TAB_GROUP_COLORS, GroupedTabBar, group_display_name, group_emoji
from browser_broadcast import GorBroadcastService, BroadcastToast

# Порог (мс), после которого вкладка, всё ещё грузящаяся, помечается
# как "не отвечает" (⚠) - см. _check_not_responding().
NOT_RESPONDING_TIMEOUT_MS = 15000

# Шаг и границы масштабирования страницы (Ctrl +/-/0) - см. zoom_in/out/reset.
ZOOM_STEP = 0.1
ZOOM_MIN = 0.25
ZOOM_MAX = 4.0


class WikiSearchOverlay(QDialog):
    """Оверлей «Быстрый поиск по вики» (пункт ТЗ): всплывает по хоткею
    (см. GORBrowser._setup_shortcuts - Ctrl+Shift+K) поверх окна браузера,
    независимо от того, какая вкладка сейчас активна. Ищет по вики-ресурсу
    ТЕКУЩЕЙ игры (см. "Сейчас в игре" - browser.load_data("now_playing")):
    если известен wiki_url конкретной игры - ищет через "site:домен запрос",
    иначе - обычный запрос "{игра} wiki {запрос}"; если игра вообще не
    запускалась - просто обычный поисковый запрос.

    ВАЖНО (сознательный охват): хоткей работает, пока ФОКУС ВНУТРИ ОКНА GOR
    Browser (Qt.ShortcutContext.ApplicationShortcut) - это НЕ перехват на
    уровне ОС (что потребовало бы platform-specific нативных хуков и не
    сработало бы, если окно свёрнуто/не в фокусе). Для быстрого поиска по
    вики во время игры этого достаточно: обычно игра запущена в отдельном
    окне/фуллскрине, а не поверх свёрнутого браузера.
    """

    def __init__(self, parent_browser):
        super().__init__(parent_browser, Qt.WindowType.Popup | Qt.WindowType.FramelessWindowHint)
        self.parent_browser = parent_browser
        self.setObjectName("WikiSearchOverlay")
        self.setFixedWidth(520)
        self.setStyleSheet(
            "#WikiSearchOverlay { background: #1c1d21; border: 1px solid #383a40; border-radius: 12px; }"
            "QLabel { color: #9aa0aa; font-size: 11px; }"
            "QLineEdit { background: #111214; color: white; border: 1px solid #333; "
            "border-radius: 8px; padding: 10px 14px; font-size: 15px; }"
        )
        layout = QVBoxLayout(self)
        layout.setContentsMargins(14, 12, 14, 12)

        now_playing = parent_browser.load_data("now_playing") or {}
        game_name = now_playing.get("name") if isinstance(now_playing, dict) else None
        wiki_url = now_playing.get("wiki_url") if isinstance(now_playing, dict) else None

        label_text = f"📖 Поиск по вики: {game_name}" if game_name else "📖 Поиск по вики (игра ещё не запускалась)"
        self.info_label = QLabel(label_text)
        layout.addWidget(self.info_label)

        self.input = QLineEdit()
        self.input.setPlaceholderText("Введите запрос и нажмите Enter...")
        self.input.returnPressed.connect(self._on_search)
        layout.addWidget(self.input)

        self._game_name = game_name
        self._wiki_domain = None
        if wiki_url:
            try:
                from urllib.parse import urlparse
                self._wiki_domain = urlparse(wiki_url).netloc or None
            except Exception:
                self._wiki_domain = None

    def showEvent(self, event):
        super().showEvent(event)
        self.input.setFocus()

    def keyPressEvent(self, event):
        if event.key() == Qt.Key.Key_Escape:
            self.close()
            return
        super().keyPressEvent(event)

    def _on_search(self):
        query = self.input.text().strip()
        if not query:
            self.close()
            return
        from urllib.parse import quote
        if self._wiki_domain:
            url = f"https://www.google.com/search?q=site:{quote(self._wiki_domain)}+{quote(query)}"
        elif self._game_name:
            url = f"https://www.google.com/search?q={quote(self._game_name)}+wiki+{quote(query)}"
        else:
            url = f"https://www.google.com/search?q={quote(query)}"
        self.parent_browser.add_new_tab(QUrl(url), f"📖 {query}"[:15])
        self.close()

    def _position_center(self):
        try:
            parent_rect = self.parent_browser.rect()
            top_left = self.parent_browser.mapToGlobal(parent_rect.topLeft())
            x = top_left.x() + (parent_rect.width() - self.width()) // 2
            y = top_left.y() + max(60, parent_rect.height() // 4)
            self.move(x, y)
        except Exception:
            pass


class GORBrowser(QWidget):  # QWidget (не QMainWindow) для корректного встраивания вкладкой
    def __init__(self, parent=None):
        super().__init__(parent)

        self.setWindowIcon(QIcon(ICON_PATH))
        self.setWindowTitle("GOR Browser - Professional Edition")
        self.resize(1300, 850)

        # --- НАСТРОЙКИ ---
        raw_settings = self.load_data(SETTINGS_FILE)
        if isinstance(raw_settings, dict) and raw_settings:
            self.settings = raw_settings
        else:
            self.settings = dict(DEFAULT_SETTINGS)

        # --- Инициализация профиля и движка ---
        if not os.path.exists(PROFILE_PATH):
            os.makedirs(PROFILE_PATH)
        self.profile = QWebEngineProfile("GOR_Profile", self)
        self.profile.setPersistentStoragePath(PROFILE_PATH)
        self.profile.setPersistentCookiesPolicy(QWebEngineProfile.PersistentCookiesPolicy.AllowPersistentCookies)
        # Пункт 5 ТЗ (оптимизация загрузки) - явно включаем дисковый HTTP-кеш
        # вместо кеша только в памяти (дефолт QtWebEngine не всегда disk-based
        # для непостоянных профилей) и даём ему разумный размер, чтобы
        # повторные посещения не перекачивали одно и то же заново.
        self.profile.setHttpCacheType(QWebEngineProfile.HttpCacheType.DiskHttpCache)
        self.profile.setHttpCacheMaximumSize(256 * 1024 * 1024)  # 256 МБ

        s = self.profile.settings()
        s.setAttribute(QWebEngineSettings.WebAttribute.LocalStorageEnabled, True)
        s.setAttribute(QWebEngineSettings.WebAttribute.JavascriptCanAccessClipboard, True)
        s.setAttribute(QWebEngineSettings.WebAttribute.ScrollAnimatorEnabled, True)
        s.setAttribute(QWebEngineSettings.WebAttribute.FullScreenSupportEnabled, True)
        # Пункт 4 ТЗ: иконочные шрифты (FontAwesome/Material Icons/<i></i>)
        # на страницах требуют, чтобы JS и подгрузка изображений/веб-фонтов
        # были явно включены (а не полагались на дефолты Qt, которые могут
        # отличаться между версиями PyQt6-WebEngine), а локальные страницы
        # (стартовая, file://) могли подтягивать шрифты с удалённых CDN.
        s.setAttribute(QWebEngineSettings.WebAttribute.JavascriptEnabled, True)
        s.setAttribute(QWebEngineSettings.WebAttribute.AutoLoadImages, True)
        s.setAttribute(QWebEngineSettings.WebAttribute.LocalContentCanAccessRemoteUrls, True)

        # --- AdBlock (uBlock Engine): сетевой интерцептор + косметика ---
        # ВАЖНО: интерцептор ставится на профиль РОВНО ОДИН РАЗ, ДО первой
        # вкладки. Дальше он живёт всё время работы браузера, а
        # включение/выключение в настройках просто дергает set_enabled().
        base_dir = os.path.dirname(os.path.abspath(__file__))
        load_extra_blocklist(base_dir)
        load_dynamic_blocklist_cache(base_dir)  # то, что уже скачали в прошлый раз (см. ниже)
        self.adblock_interceptor = GorAdBlockInterceptor(self)
        self.adblock_interceptor.set_enabled(self.settings.get("adblock_enabled", True))
        self.profile.setUrlRequestInterceptor(self.adblock_interceptor)
        install_cosmetic_filter(self.profile, self.settings.get("adblock_enabled", True))

        # Динамический AdBlock (пункт ТЗ) - фоновое обновление списка
        # блокировки с GitHub вместо статического набора доменов. Кэш уже
        # подгружен строкой выше (load_dynamic_blocklist_cache) - работает
        # сразу; здесь просто запускаем сам механизм обновления по таймеру.
        self.adblock_updater = GorAdBlockUpdater(base_dir, self)
        self.adblock_updater.update_finished.connect(self._on_adblock_update_finished)
        self._adblock_update_timer = QTimer(self)
        self._adblock_update_timer.timeout.connect(self._maybe_run_adblock_update)
        self._adblock_update_timer.start(60 * 60 * 1000)  # проверяем раз в час, обновляем по settings-интервалу
        if self.settings.get("adblock_dynamic_update_enabled", True):
            QTimer.singleShot(5000, self._maybe_run_adblock_update)  # не грузим сеть в первую секунду старта

        # Локальный менеджер паролей (AES/Fernet через `cryptography`, см.
        # browser_passwords.py) - хранилище лежит рядом с профилем браузера,
        # разблокируется мастер-паролем пользователя за сессию.
        self.password_vault = PasswordVault(os.path.join(base_dir, "passwords.vault"))

        # --- VOT Engine: закадровый переводчик видео ---
        install_vot_translator(self.profile, base_dir, self.settings.get("vot_enabled", True))

        self.incognito_profile = QWebEngineProfile(self)
        self.bookmarks = self.load_data(BOOKMARKS_FILE)
        self.history = self.load_data(HISTORY_FILE)
        # Сохранённые группы вкладок (см. browser_groups.py) - хранятся в
        # том же games_data.json, блок "browser" -> "tab_groups".
        self.tab_groups = self.load_data(TAB_GROUPS_FILE) or []
        # Какие группы сейчас свёрнуты в ленте вкладок (см. GroupedTabBar /
        # toggle_group_collapse) - чисто состояние текущей сессии, в JSON
        # не сохраняется (при следующем запуске все группы развёрнуты).
        self.collapsed_group_ids = set()

        # Пользовательские JS-расширения (UserScripts, пункт 5 ТЗ) -
        # загружаем сохранённые ранее (раньше здесь стояла пустая заглушка
        # "[]", из-за которой список расширений никогда не переживал
        # перезапуск браузера, даже если ExtensionsTab исправно писал их
        # в EXTENSIONS_FILE - см. apply_extensions() ниже, тоже был стаб).
        raw_extensions = self.load_data(EXTENSIONS_FILE)
        self.extensions = raw_extensions if isinstance(raw_extensions, list) else []
        self.apply_extensions()  # инжектит их в profile.scripts() сразу при старте

        # Стек закрытых вкладок для восстановления (Ctrl+Shift+T) -
        # хранит последние NOT_RESPONDING_TIMEOUT-независимые записи
        # {"url", "label", "incognito"}, максимум 20 штук.
        self.closed_tabs = []
        # Виджеты вкладок, закреплённых пользователем (📌), см. toggle_pin_tab().
        self.pinned_tabs = set()
        self._fullscreen_active = False
        self._pre_fullscreen_sidebar_visible = False

        # --- Session Restore: обнаружение некорректного завершения ---
        # Если "active" всё ещё True с прошлого запуска - значит closeEvent
        # лаунчера тогда не отработал (крах/kill/отключение питания), и есть
        # смысл предложить восстановить вкладки. Список читаем СЕЙЧАС (до
        # перезаписи), а сам файл сразу помечаем "active": True для текущего
        # запуска - если этот запуск тоже упадёт, следующий увидит то же самое.
        raw_session = self.load_data(SESSION_FILE)
        if not isinstance(raw_session, dict):
            raw_session = {}
        self._pending_restore_tabs = (
            raw_session.get("tabs") or [] if raw_session.get("active") else []
        )
        self.save_data(SESSION_FILE, {"active": True, "tabs": raw_session.get("tabs") or []})
        self._session_closed_cleanly = False
        # Debounce-таймер для записи сессии на диск - навигация/открытие
        # вкладок может происходить очень часто, а нам достаточно писать
        # актуальное состояние раз в ~1.5с простоя, а не на каждое событие.
        self._session_save_timer = QTimer(self)
        self._session_save_timer.setSingleShot(True)
        self._session_save_timer.timeout.connect(self._write_session_state)

        # --- Tab Suspender: автовыгрузка неактивных фоновых вкладок ---
        self.suspend_timer = QTimer(self)
        self.suspend_timer.timeout.connect(self._check_suspend_inactive_tabs)
        self.suspend_timer.start(60_000)  # проверяем раз в минуту

        # Стартовая страница
        self.create_start_page()
        self.start_url = QUrl.fromLocalFile(START_PAGE_PATH)

        if self.layout() is None:
            self.main_layout = QVBoxLayout(self)
        else:
            self.main_layout = self.layout()

        self.main_layout.setContentsMargins(0, 0, 0, 0)
        self.main_layout.setSpacing(0)

        self.init_ui()

        self.setup_shortcuts()
        self.refresh_sidebar_bookmarks()
        self.refresh_sidebar_history()

        # Запуск первой вкладки
        self.add_new_tab(self.start_url, "🏠 Главная")
        # Менеджер загрузок
        self.download_manager = DownloadManager(self)
        self.profile.downloadRequested.connect(self.on_download_requested)

        # --- Real-Time LAN Broadcast ---
        self.broadcast_service = GorBroadcastService(
            port=self.settings.get("broadcast_port", 51888), parent=self
        )
        if self.settings.get("broadcast_enabled", True):
            self.broadcast_service.start_listening()
        self.broadcast_service.broadcast_received.connect(self.on_broadcast_received)

        # LAN: общий буфер обмена - слушаем системный буфер обмена этого ПК
        # и, если фича включена в настройках, рассылаем изменения в сеть
        # (см. _on_local_clipboard_changed / _handle_incoming_clipboard).
        self._suppress_clipboard_broadcast = False
        self._clipboard = QApplication.clipboard()
        self._clipboard.dataChanged.connect(self._on_local_clipboard_changed)

        # Предложение восстановить сессию показываем ПОСЛЕ полной отрисовки
        # окна (небольшая задержка), чтобы диалог не выскакивал поверх ещё
        # не отрисованного браузера.
        if self._pending_restore_tabs:
            QTimer.singleShot(400, self._offer_session_restore)

    # ------------------------------------------------------------------
    # Хранение данных (games_data.json, блок "browser")
    # ------------------------------------------------------------------

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

    # ------------------------------------------------------------------
    # Группы вкладок (browser_groups.py)
    # ------------------------------------------------------------------

    def save_tab_groups(self):
        """Персистит self.tab_groups в games_data.json (см. save_data)."""
        self.save_data(TAB_GROUPS_FILE, self.tab_groups)

    def get_open_tab_urls(self):
        """URL всех открытых (не инкогнито, кроме стартовой страницы)
        вкладок - используется и для сохранения новой группы, и для
        индикатора "эта группа сейчас открыта" в GroupsPanel. Безопасен к
        вызову ДО создания self.tabs (GroupsPanel строится в init_ui()
        раньше самого QTabWidget и сразу дергает refresh())."""
        tabs = getattr(self, "tabs", None)
        if tabs is None:
            return []
        urls = []
        for i in range(tabs.count()):
            tab = tabs.widget(i)
            if not tab:
                continue
            if tab.page().profile() == self.incognito_profile:
                continue
            url = tab.url().toString()
            if url and "start_page.html" not in url:
                urls.append(url)
        return urls

    def find_tab_group(self, group_id):
        """Ищет сохранённую группу по id - общая точка входа и для
        GroupsPanel, и для GroupedTabBar (подсветка в ленте вкладок)."""
        for g in self.tab_groups:
            if g.get("id") == group_id:
                return g
        return None

    def tag_tab_with_group(self, browser_widget, group_id):
        """Помечает открытую вкладку как принадлежащую группе - именно это
        свойство читает GroupedTabBar, чтобы нарисовать цветную полоску под
        вкладкой (визуально как в Firefox/Chrome)."""
        browser_widget.setProperty("gor_group_id", group_id)
        self.tabs.tabBar().update()
        self.refresh_groups_panel()

    def untag_tab_from_group(self, index):
        """Убирает вкладку из визуальной группы (полоска пропадёт), НЕ
        трогая сам сохранённый список URL группы - это разные вещи: одно
        про то, что сейчас подсвечено в ленте, другое - что лежит в JSON."""
        widget = self.tabs.widget(index)
        if not widget:
            return
        widget.setProperty("gor_group_id", None)
        self.tabs.tabBar().update()
        self.refresh_groups_panel()

    def open_group_by_id(self, group_id):
        """Открывает все вкладки сохранённой группы одним кликом
        ("Мгновенный запуск сохраненных групп" из release notes) и сразу
        помечает их как принадлежащие группе, чтобы в ленте вкладок
        появилась цветная полоска, как в Firefox/Chrome."""
        group = self.find_tab_group(group_id)
        if not group:
            return
        for url in group.get("urls", []):
            tab_widget = self.add_new_tab(QUrl(url), group_display_name(group)[:15])
            self.tag_tab_with_group(tab_widget, group_id)

    def create_group_from_tab(self, index):
        """Аналог "Add Tab to New Group" из Firefox/Chrome - создаёт НОВУЮ
        сохранённую группу прямо из одной открытой вкладки (сразу же
        сохраняется в tab_groups, так что фишка сохранения работает и тут,
        просто отправная точка - не "сохранить сессию", а один клик по
        вкладке)."""
        browser = self.tabs.widget(index)
        if not browser:
            return
        url = browser.url().toString()
        if not url or "start_page.html" in url:
            QMessageBox.information(self, "GOR Browser", "Нельзя сгруппировать стартовую страницу.")
            return

        name, ok = QInputDialog.getText(self, "Новая группа", "Название группы:")
        if not ok or not name.strip():
            return
        dlg = QColorDialog(QColor(TAB_GROUP_COLORS[len(self.tab_groups) % len(TAB_GROUP_COLORS)]), self)
        color = TAB_GROUP_COLORS[len(self.tab_groups) % len(TAB_GROUP_COLORS)]
        if dlg.exec():
            color = dlg.selectedColor().name()
        emoji, _ = QInputDialog.getText(
            self, "Иконка группы", "Эмодзи для группы (необязательно):", text="🗂️",
        )

        from browser_groups import new_group_record
        group = new_group_record(name.strip(), color, [url], emoji=emoji)
        self.tab_groups.append(group)
        self.save_tab_groups()
        self.tag_tab_with_group(browser, group["id"])

    def add_tab_to_group(self, index, group_id):
        """Добавляет уже открытую вкладку в существующую сохранённую
        группу - и подсвечивает её в ленте, и дописывает URL в сохранённый
        список (если такого URL там ещё нет)."""
        browser = self.tabs.widget(index)
        group = self.find_tab_group(group_id)
        if not browser or not group:
            return
        url = browser.url().toString()
        if url and url not in group.get("urls", []):
            group.setdefault("urls", []).append(url)
            self.save_tab_groups()
        self.tag_tab_with_group(browser, group_id)

    def toggle_group_collapse(self, group_id):
        """Сворачивает/разворачивает группу в ленте вкладок - как клик по
        заголовку группы в Firefox. Технически: все вкладки группы, кроме
        первой, скрываются через setTabVisible(False); первая временно
        становится "заголовком" с текстом "▸ Название (N)"."""
        indexes = [
            i for i in range(self.tabs.count())
            if self.tabs.widget(i) and self.tabs.widget(i).property("gor_group_id") == group_id
        ]
        if not indexes:
            return
        group = self.find_tab_group(group_id)
        name = group.get("name", "Группа") if group else "Группа"
        bar = self.tabs.tabBar()
        head_index = indexes[0]
        head_widget = self.tabs.widget(head_index)

        if group_id in self.collapsed_group_ids:
            # Развернуть
            self.collapsed_group_ids.discard(group_id)
            for i in indexes:
                bar.setTabVisible(i, True)
            head_widget.setProperty("gor_group_collapsed_header", False)
            orig = head_widget.property("gor_orig_title")
            if orig:
                self.tabs.setTabText(head_index, orig)
        else:
            # Свернуть
            self.collapsed_group_ids.add(group_id)
            head_widget.setProperty("gor_orig_title", self.tabs.tabText(head_index))
            head_widget.setProperty("gor_group_collapsed_header", True)
            emoji = group_emoji(group) if group else "▸"
            self.tabs.setTabText(head_index, f"{emoji} {name} ({len(indexes)})")
            for i in indexes[1:]:
                bar.setTabVisible(i, False)
            if self.tabs.currentIndex() in indexes[1:]:
                self.tabs.setCurrentIndex(head_index)
        bar.update()

    def refresh_groups_panel(self):
        """Безопасный вызов GroupsPanel.refresh() - панель создаётся в
        init_ui() уже ПОСЛЕ первой вкладки, поэтому в моменты между началом
        __init__ и init_ui() атрибута ещё может не быть."""
        panel = getattr(self, "groups_panel", None)
        if panel is not None:
            panel.refresh()

    # ------------------------------------------------------------------
    # Session Restore (восстановление сессии при сбое)
    # ------------------------------------------------------------------

    def _schedule_session_save(self):
        """Планирует запись текущего списка вкладок на диск с небольшой
        задержкой (debounce) - вызывается часто (навигация, открытие/
        закрытие вкладок), поэтому не пишем на диск синхронно на каждое
        событие."""
        timer = getattr(self, "_session_save_timer", None)
        if timer is not None:
            timer.start(1500)

    def _write_session_state(self):
        """Пишет актуальный список открытых (не инкогнито) вкладок в
        games_data.json - именно эти данные предлагаются к восстановлению
        при следующем запуске, если приложение закроется некорректно."""
        tabs = getattr(self, "tabs", None)
        if tabs is None:
            return
        entries = []
        for i in range(tabs.count()):
            browser = tabs.widget(i)
            if not browser:
                continue
            if browser.page().profile() == self.incognito_profile:
                continue
            url = browser.url().toString()
            if not url or "start_page.html" in url:
                continue
            entries.append({"url": url, "pinned": browser in self.pinned_tabs})
        self.save_data(SESSION_FILE, {"active": not self._session_closed_cleanly, "tabs": entries})

    def mark_session_closed_cleanly(self):
        """Вызывается лаунчером из GORLauncher.closeEvent ПРИ ШТАТНОМ
        закрытии приложения: немедленно (без debounce) пишет "active": False,
        чтобы следующий запуск НЕ считал это крахом и не предлагал
        восстановление вкладок. Заодно блокирует менеджер паролей (обнуляет
        ключ и расшифрованные записи в памяти)."""
        self._session_closed_cleanly = True
        timer = getattr(self, "_session_save_timer", None)
        if timer is not None:
            timer.stop()
        self._write_session_state()
        vault = getattr(self, "password_vault", None)
        if vault is not None:
            vault.lock()

    def _offer_session_restore(self):
        """Показывает диалог восстановления вкладок после обнаруженного
        некорректного завершения прошлой сессии (см. __init__)."""
        pending = self._pending_restore_tabs
        self._pending_restore_tabs = []
        if not pending:
            return
        reply = QMessageBox.question(
            self, "GOR Browser",
            f"Похоже, в прошлый раз браузер закрылся некорректно (сбой или "
            f"аварийное завершение).\n\nВосстановить {len(pending)} "
            f"ранее открытых вкладок(у)?",
        )
        if reply != QMessageBox.StandardButton.Yes:
            return
        for entry in pending:
            if isinstance(entry, dict):
                url, pinned = entry.get("url"), bool(entry.get("pinned"))
            else:
                url, pinned = entry, False
            if not url:
                continue
            tab_widget = self.add_new_tab(QUrl(url), url[:24])
            if pinned:
                idx = self.tabs.indexOf(tab_widget)
                if idx != -1:
                    self.toggle_pin_tab(idx)

    # ------------------------------------------------------------------
    # Tab Suspender (автовыгрузка неактивных фоновых вкладок из RAM)
    # ------------------------------------------------------------------

    def _check_suspend_inactive_tabs(self):
        """Раз в минуту (см. self.suspend_timer) проверяет все фоновые
        вкладки и выгружает из памяти те, что неактивны дольше настроенного
        порога - экономия RAM/CPU, полезно во время игр. Не трогает:
        текущую активную вкладку, закреплённые (📌), уже выгруженные,
        стартовую страницу и вкладки, которые сейчас проигрывают звук."""
        if not self.settings.get("tab_suspend_enabled", True):
            return
        threshold_s = max(1, int(self.settings.get("tab_suspend_minutes", 15))) * 60
        now = time.time()
        current = self.tabs.currentWidget()
        for i in range(self.tabs.count()):
            browser = self.tabs.widget(i)
            if not browser or browser is current:
                continue
            if browser in self.pinned_tabs:
                continue
            if browser.property("gor_suspended"):
                continue
            url_str = browser.url().toString()
            if not url_str or "start_page.html" in url_str:
                continue
            try:
                if browser.page().recentlyAudible():
                    continue
            except Exception:
                pass
            last_active = browser.property("gor_last_active_ts")
            last_active = float(last_active) if last_active else now
            if now - last_active >= threshold_s:
                self._suspend_tab(i, browser)

    def _suspend_tab(self, index, browser):
        """Переводит страницу вкладки в состояние Discarded (см.
        QWebEnginePage.LifecycleState) - движок освобождает память/процесс
        рендерера, сохраняя при этом URL для восстановления по клику."""
        try:
            browser.page().setLifecycleState(QWebEnginePage.LifecycleState.Discarded)
        except Exception:
            return
        browser.setProperty("gor_suspended", True)
        current_text = self.tabs.tabText(index)
        if not current_text.startswith("💤 "):
            browser.setProperty("gor_pre_suspend_title", current_text)
            self.tabs.setTabText(index, "💤 " + current_text)
        self.tabs.setTabToolTip(index, "Вкладка выгружена из памяти (была неактивна) - клик восстановит её")

    def _wake_tab_if_suspended(self, browser, index):
        """Возвращает выгруженную вкладку в активное состояние - вызывается
        при переключении на неё (см. on_tab_changed)."""
        if not browser or not browser.property("gor_suspended"):
            return
        try:
            browser.page().setLifecycleState(QWebEnginePage.LifecycleState.Active)
        except Exception:
            pass
        browser.setProperty("gor_suspended", False)
        orig = browser.property("gor_pre_suspend_title")
        if orig:
            self.tabs.setTabText(index, orig)
        self.tabs.setTabToolTip(index, "")

    def broadcast_group_by_id(self, group_id):
        """Отправляет сохранённую группу в локальную сеть (LAN Broadcast)."""
        group = self.find_tab_group(group_id)
        if not group:
            return
        if not self.settings.get("broadcast_enabled", True):
            QMessageBox.information(self, "GOR Browser", "LAN Broadcast выключен в настройках.")
            return
        ok = self.broadcast_service.send_group(group)
        if not ok:
            QMessageBox.warning(self, "GOR Browser", "Не удалось отправить группу в сеть (проверьте подключение к LAN).")

    def send_current_tab_to_network(self):
        """Отправка активной вкладки в сеть по UDP - "Отправка вкладки в
        сеть" из release notes."""
        browser = self.tabs.currentWidget()
        if not browser:
            return
        if not self.settings.get("broadcast_enabled", True):
            QMessageBox.information(self, "GOR Browser", "LAN Broadcast выключен в настройках.")
            return
        url = browser.url().toString()
        title = browser.page().title() or url
        if "start_page.html" in url:
            QMessageBox.information(self, "GOR Browser", "Нечего отправлять - это стартовая страница.")
            return
        ok = self.broadcast_service.send_tab(url, title)
        if ok:
            self.statusBar_message(f"📡 Вкладка отправлена в сеть: {title[:40]}")
        else:
            QMessageBox.warning(self, "GOR Browser", "Не удалось отправить вкладку в сеть (проверьте подключение к LAN).")

    def statusBar_message(self, text, timeout_ms=3000):
        """Лёгкое всплывающее сообщение в заголовке окна на пару секунд -
        в этом виджете нет полноценного statusBar (QWidget, не QMainWindow),
        поэтому используем временную подмену window title как самый простой
        ненавязчивый способ дать пользователю обратную связь."""
        original = self.windowTitle()
        self.setWindowTitle(f"{text}")
        QTimer.singleShot(timeout_ms, lambda: self.setWindowTitle(original))

    def on_broadcast_received(self, payload):
        """Пришёл UDP-пакет от другого GOR Browser в сети. Буфер обмена и
        синхронизация закладок обрабатываются молча (без тоста - см.
        статус-сообщение внутри их хендлеров), вкладки/группы по-прежнему
        показывают тост «Открыть все» / «Сохранить в JSON» ("Быстрый приём"
        из release notes)."""
        ptype = payload.get("type")
        if ptype == "clipboard":
            self._handle_incoming_clipboard(payload)
            return
        if ptype == "bookmark_sync":
            self._handle_incoming_bookmark_sync(payload)
            return
        toast = BroadcastToast(self, payload)
        toast.show()
        # Держим ссылку, иначе PyQt соберёт объект мусорщиком сразу после show().
        if not hasattr(self, "_active_toasts"):
            self._active_toasts = []
        self._active_toasts.append(toast)
        toast.destroyed.connect(lambda: self._active_toasts.remove(toast) if toast in self._active_toasts else None)

    # ------------------------------------------------------------------
    # LAN: общий буфер обмена
    # ------------------------------------------------------------------

    def _on_local_clipboard_changed(self):
        """Реагирует на ЛЮБОЕ изменение системного буфера обмена этого ПК -
        если фича включена в настройках, рассылает новый текст остальным
        GOR Browser в сети. self._suppress_clipboard_broadcast защищает от
        зацикливания: когда МЫ САМИ пишем в буфер обмена входящий текст
        (см. _handle_incoming_clipboard), это тоже вызывает dataChanged, и
        без защиты пакет улетел бы обратно в сеть."""
        if self._suppress_clipboard_broadcast:
            return
        if not self.settings.get("lan_clipboard_enabled", False):
            return
        text = self._clipboard.text()
        if not text or not text.strip():
            return
        self.broadcast_service.send_clipboard(text)

    def _handle_incoming_clipboard(self, payload):
        if not self.settings.get("lan_clipboard_enabled", False):
            return  # фича выключена локально - молча игнорируем чужой буфер обмена
        text = payload.get("text", "")
        if not text:
            return
        self._suppress_clipboard_broadcast = True
        try:
            self._clipboard.setText(text)
        finally:
            self._suppress_clipboard_broadcast = False
        sender = payload.get("sender", "устройство в сети")
        preview = text if len(text) <= 40 else text[:40] + "…"
        self.statusBar_message(f"📋 Буфер обмена обновлён из сети ({sender}): {preview}", 3000)

    # ------------------------------------------------------------------
    # LAN: синхронизация закладок
    # ------------------------------------------------------------------

    def _maybe_broadcast_bookmarks(self):
        """Вызывается после любого изменения self.bookmarks (добавление/
        редактирование/удаление) - если синхронизация включена, рассылает
        ПОЛНЫЙ актуальный список остальным GOR Browser в сети."""
        if self.settings.get("lan_bookmark_sync_enabled", False):
            self.broadcast_service.send_bookmarks(self.bookmarks)

    def _handle_incoming_bookmark_sync(self, payload):
        if not self.settings.get("lan_bookmark_sync_enabled", False):
            return
        incoming = payload.get("bookmarks", [])
        if not isinstance(incoming, list):
            return
        existing_urls = {bm.get("url") for bm in self.bookmarks}
        added = 0
        for bm in incoming:
            if not isinstance(bm, dict) or not bm.get("url"):
                continue
            if bm["url"] in existing_urls:
                continue  # не перетираем локальные закладки - только добавляем новые
            self.bookmarks.append({"name": (bm.get("name") or bm["url"])[:80], "url": bm["url"]})
            existing_urls.add(bm["url"])
            added += 1
        if added:
            self.save_data(BOOKMARKS_FILE, self.bookmarks)
            self.refresh_sidebar_bookmarks()
            sender = payload.get("sender", "устройство в сети")
            self.statusBar_message(f"🔗 Закладки: +{added} новых от {sender}", 3000)


    # ------------------------------------------------------------------
    # Загрузки
    # ------------------------------------------------------------------

    def on_download_requested(self, download):
        """Обработка загрузок файлов."""
        path, _ = QFileDialog.getSaveFileName(self, "Сохранить файл", download.suggestedFileName())
        if path:
            download.setDownloadDirectory(os.path.dirname(path))
            download.setDownloadFileName(os.path.basename(path))
            download.accept()
            self.download_manager.add_download(download)
        else:
            download.interrupt()

    # ------------------------------------------------------------------
    # Стартовая страница и оформление
    # ------------------------------------------------------------------

    def create_start_page(self):
        """Стартовая страница теперь - готовый файл GOR_Brauzer/start_page.html
        (кастомный дашборд с ярлыками, поиском и своими настройками на
        localStorage), и он больше НЕ перезаписывается на лету при каждом
        запуске/изменении настроек, как было раньше.

        Старая логика генерации (write_start_page из browser_startpage.py)
        никуда не делась - она используется только как аварийный резерв,
        если файл start_page.html вдруг отсутствует (переустановка,
        случайное удаление и т.п.), чтобы браузер не остался без домашней
        страницы вообще."""
        if not os.path.exists(START_PAGE_PATH):
            write_start_page(self.settings)

    def reload_start_pages(self):
        """Перезагрузка всех открытых стартовых страниц."""
        for i in range(self.tabs.count()):
            browser = self.tabs.widget(i)
            if browser and "start_page.html" in browser.url().toString():
                browser.reload()

    def _build_startpage_payload(self):
        """Собирает те же настройки, что раньше редактировались прямо на
        стартовой странице (акцент/бренд/фон/блюр/интерактивность/поисковики),
        в один JSON-словарь для window.gorApplyNativeSettings(...) на стороне
        JS (GOR_Brauzer/start_page.html).

        search_engine - ЕДИНСТВЕННАЯ точка выбора поисковика (GeneralTab в
        browser_dialogs.py): engine_idx для стартовой страницы вычисляется
        ЗДЕСЬ из него же (по совпадению имени с BUILTIN_STARTPAGE_ENGINES),
        а не хранится отдельным независимым полем - раньше search_engine
        двигал только адресную строку, а active_engine_idx (стартовая
        страница) жил сам по себе и никогда не обновлялся при смене
        поисковика в настройках."""
        s = self.settings
        engines = get_startpage_engines(s)
        engine_name = s.get("search_engine", "Google")
        engine_idx = next((i for i, e in enumerate(engines) if e.get("name") == engine_name), 0)
        return {
            "accent": s.get("theme_color", "#4c6ef5"),
            "brand": s.get("brand_text", "GOR // OS"),
            "engines": engines,
            "engine_idx": engine_idx,
            "bg_data": s.get("bg_data", ""),
            "bg_type": s.get("bg_type", ""),
            "bg_blur": s.get("bg_blur", 0),
            "bg_interactive": bool(s.get("bg_interactive", False)),
            "now_playing": self.load_data("now_playing") or None,
            "show_clock": bool(s.get("show_clock", True)),
            "show_title": bool(s.get("show_title", True)),
            "show_todo": bool(s.get("show_todo", True)),
        }

    def push_now_playing(self, game_data):
        """"Сейчас в игре" (пункт ТЗ) - живое обновление виджета на ВСЕХ
        открытых стартовых страницах прямо сейчас, без ожидания перезагрузки
        вкладки. GorLauncher вызывает это из on_game_started() - лаунчер и
        браузер работают в одном процессе (self.browser_tab - обычный
        Python-объект), поэтому это прямой вызов, а не IPC."""
        payload = {"now_playing": {
            "name": game_data.get("name", "?"),
            "icon": game_data.get("icon", ""),
            "wiki_url": game_data.get("wiki_url", ""),
            "forum_url": game_data.get("forum_url", ""),
            "discord_url": game_data.get("discord_url", ""),
        }}
        js = f"window.gorApplyNativeSettings && window.gorApplyNativeSettings({json.dumps(payload, ensure_ascii=False)});"
        self.run_js_on_start_pages(js)

    def run_js_on_start_pages(self, js_code):
        """Выполняет произвольный JS на всех открытых вкладках стартовой
        страницы. Используется и для точечного push_native_settings_to_pages,
        и для команд вроде window.gorResetAll() (см. CustomizationManager)."""
        for i in range(self.tabs.count()):
            browser = self.tabs.widget(i)
            if browser and "start_page.html" in browser.url().toString():
                browser.page().runJavaScript(js_code)

    def push_native_settings_to_pages(self):
        """Отправляет текущие self.settings во все открытые стартовые
        страницы без перезагрузки вкладки (в отличие от старого
        reload_start_pages(), который требовал, чтобы страница сама умела
        прочитать новые настройки из localStorage при загрузке).

        Настройки редактируются в CustomizationManager (Python), а
        применяет их сама страница через window.gorApplyNativeSettings(...),
        используя ту же логику (setSystemAccentColor/applyBackground/...),
        что раньше запускалась кликами по ⚙ прямо на странице."""
        payload = json.dumps(self._build_startpage_payload(), ensure_ascii=False)
        self.run_js_on_start_pages(f"window.gorApplyNativeSettings && window.gorApplyNativeSettings({payload});")

    def sync_start_page_settings(self, browser):
        """Как push_native_settings_to_pages, но только для одной, только
        что загрузившейся вкладки - чтобы свежая стартовая страница сразу
        показывала актуальные акцент/бренд/фон, а не ждала следующего
        изменения настроек."""
        payload = json.dumps(self._build_startpage_payload(), ensure_ascii=False)
        browser.page().runJavaScript(f"window.gorApplyNativeSettings && window.gorApplyNativeSettings({payload});")

    def get_first_start_page_browser(self):
        """Первая открытая вкладка стартовой страницы (нужна как источник
        для экспорта - JS с данными localStorage должен выполняться внутри
        уже загруженной страницы, а не "в вакууме")."""
        for i in range(self.tabs.count()):
            b = self.tabs.widget(i)
            if b and "start_page.html" in b.url().toString():
                return b
        return None

    def export_backup_to_file(self, dialog_parent):
        """Полная резервная копия (пункт 3.3 ТЗ): настройки, история,
        закладки, группы вкладок, расширения - ВСЁ одним JSON-файлом.
        Раньше эта кнопка сохраняла только localStorage стартовой страницы
        (ярлыки/дела/заметки/виджеты) - теперь это лишь один из разделов
        итогового файла ("start_page"), а не единственное, что сохраняется."""
        def _finish(start_page_json):
            payload = {
                "gor_backup_version": 1,
                "exported_at": datetime.now().isoformat(),
                "settings": self.settings,
                "history": self.history,
                "bookmarks": self.bookmarks,
                "tab_groups": self.tab_groups,
                "extensions": self.extensions,
                # Строка JSON от самой страницы (ярлыки/дела/заметки/виджеты) -
                # кладём как есть, распарсим при импорте только когда решим,
                # что с ней делать (см. import_backup_from_file).
                "start_page_raw": start_page_json or "",
            }
            default_name = f"gor-browser-backup-{datetime.now().strftime('%Y-%m-%d')}.json"
            path, _ = QFileDialog.getSaveFileName(
                dialog_parent, "Сохранить резервную копию", default_name, "JSON (*.json)"
            )
            if not path:
                return
            try:
                with open(path, "w", encoding="utf-8") as f:
                    json.dump(payload, f, ensure_ascii=False, indent=2)
            except OSError as e:
                QMessageBox.warning(dialog_parent, "GOR Browser", f"Не удалось сохранить файл:\n{e}")
                return
            QMessageBox.information(
                dialog_parent, "GOR Browser",
                "Резервная копия сохранена: настройки, история, закладки, группы вкладок и расширения."
            )

        browser = self.get_first_start_page_browser()
        if browser:
            browser.page().runJavaScript(
                "window.gorNativeExportBackup ? window.gorNativeExportBackup() : '';", _finish
            )
        else:
            _finish("")

    def import_backup_from_file(self, dialog_parent):
        """Импорт полной резервной копии (обратная операция к
        export_backup_to_file) - валидирует формат, перезаписывает
        настройки/историю/закладки/группы/расширения и перезагружает
        интерфейс, чтобы изменения сразу стали видны."""
        path, _ = QFileDialog.getOpenFileName(dialog_parent, "Открыть резервную копию", "", "JSON (*.json)")
        if not path:
            return
        try:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
        except (OSError, json.JSONDecodeError) as e:
            QMessageBox.warning(dialog_parent, "GOR Browser", f"Не удалось прочитать файл:\n{e}")
            return
        if not isinstance(data, dict) or "gor_backup_version" not in data:
            QMessageBox.warning(
                dialog_parent, "GOR Browser",
                "Это не похоже на резервную копию GOR Browser (нет метки формата)."
            )
            return

        confirm = QMessageBox.question(
            dialog_parent, "GOR Browser",
            "Импорт заменит ВСЕ текущие настройки, историю, закладки, группы вкладок "
            "и расширения содержимым файла. Продолжить?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        if confirm != QMessageBox.StandardButton.Yes:
            return

        if isinstance(data.get("settings"), dict):
            self.settings = data["settings"]
            self.save_data(SETTINGS_FILE, self.settings)
        if isinstance(data.get("history"), list):
            self.history = data["history"]
            self.save_data(HISTORY_FILE, self.history)
        if isinstance(data.get("bookmarks"), list):
            self.bookmarks = data["bookmarks"]
            self.save_data(BOOKMARKS_FILE, self.bookmarks)
        if isinstance(data.get("tab_groups"), list):
            self.tab_groups = data["tab_groups"]
            self.save_tab_groups()
        if isinstance(data.get("extensions"), list):
            self.extensions = data["extensions"]
            self.save_data(EXTENSIONS_FILE, self.extensions)
            self.apply_extensions()

        # Раздел стартовой страницы (ярлыки/дела/заметки/виджеты) - тем же
        # путём, что и раньше, через JS-функцию самой страницы.
        start_page_raw = data.get("start_page_raw")
        if start_page_raw:
            payload = json.dumps(start_page_raw)  # безопасно экранируем как JS-строку
            self.run_js_on_start_pages(f"window.gorNativeImportBackup && window.gorNativeImportBackup({payload});")

        self.update_styles()
        self.refresh_sidebar_bookmarks()
        self.refresh_groups_panel()
        self.push_native_settings_to_pages()
        QMessageBox.information(dialog_parent, "GOR Browser", "Резервная копия импортирована.")

    def clear_cookies(self, dialog_parent=None):
        """Приватность (пункт 3.4 ТЗ) - немедленная очистка кук основного
        профиля, без ожидания перезапуска браузера. Инкогнито-профиль не
        трогаем: он и так эфемерный (данные не переживают закрытие вкладки)."""
        confirm = QMessageBox.question(
            dialog_parent or self, "GOR Browser",
            "Удалить все сохранённые куки? Потребуется заново войти на большинстве сайтов.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        if confirm != QMessageBox.StandardButton.Yes:
            return
        self.profile.cookieStore().deleteAllCookies()
        QMessageBox.information(dialog_parent or self, "GOR Browser", "Куки удалены.")

    def clear_http_cache(self, dialog_parent=None):
        """Приватность (пункт 3.4 ТЗ) - очистка дискового HTTP-кеша."""
        self.profile.clearHttpCache()
        QMessageBox.information(dialog_parent or self, "GOR Browser", "Кеш очищен.")

    def apply_extensions(self):
        """Внедряет пользовательские JS-расширения на каждую загружаемую
        страницу через QWebEngineScript (пункт 5 ТЗ: базовый менеджер
        UserScripts). РАНЬШЕ ЭТО БЫЛА ЗАГЛУШКА: метод просто чистил
        profile.scripts() и ничего не добавлял обратно, так что все
        расширения, добавленные через ExtensionsTab, молча переставали
        работать сразу после сохранения (и не переживали перезапуск,
        поскольку self.extensions тоже не читался из EXTENSIONS_FILE)."""
        scripts = self.profile.scripts()
        # Убираем только НАШИ скрипты (по имени с префиксом), чтобы не
        # случайно снести служебные скрипты AdBlock/VOT/cosmetic-filter,
        # которые тоже регистрируются в этом же QWebEngineProfile.
        for old in [sc for sc in scripts.toList() if sc.name().startswith("gor-ext-")]:
            scripts.remove(old)
        for ext in self.extensions:
            name = str(ext.get("name", "")).strip()
            code = ext.get("code", "")
            if not name or not code:
                continue
            script = QWebEngineScript()
            script.setName(f"gor-ext-{name}")
            script.setSourceCode(code)
            script.setInjectionPoint(QWebEngineScript.InjectionPoint.DocumentReady)
            script.setWorldId(QWebEngineScript.ScriptWorldId.ApplicationWorld)
            script.setRunsOnSubFrames(False)
            scripts.insert(script)

    def update_styles(self):
        """Применение стилей интерфейса."""
        accent = self.settings.get("theme_color", "#4c6ef5")
        top_bg = self.settings.get("top_bar_color", "#16171a")
        font = self.settings.get("font_family", "Segoe UI")
        font_size = int(self.settings.get("font_size", 10))

        # Шрифт интерфейса (пункт 3.2 ТЗ): раньше font_family влиял ТОЛЬКО
        # на CSS этого QWidget'а (т.е. фактически ни на что, кроме мелких
        # деталей внутри самого браузера) - теперь применяется реально:
        # 1) ко всему Qt-приложению (меню лаунчера, диалоги и т.д.);
        # 2) к рендерингу веб-страниц через QWebEngineSettings.
        app = QApplication.instance()
        if app is not None:
            app.setFont(QFont(font, font_size))
        try:
            web_settings = QWebEngineSettings.globalSettings()
            web_settings.setFontFamily(QWebEngineSettings.FontFamily.StandardFont, font)
            web_settings.setFontSize(QWebEngineSettings.FontSize.DefaultFontSize, font_size)
        except Exception:
            pass  # на некоторых сборках PyQt6-WebEngine globalSettings() может отсутствовать

        self.setStyleSheet(f"""
            QWidget {{ font-family: '{font}'; font-size: {font_size}pt; color: white; }}
            #TopBar {{
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                    stop:0 {_lighten(top_bg, 10)}, stop:1 {_darken(top_bg, 6)});
                border-bottom: 1px solid {_darken(top_bg, 18) if top_bg != '#000000' else '#000'};
            }}
            #Sidebar {{ background-color: #16171a; border-right: 1px solid #333; }}
            #MainSplitter::handle {{ background-color: #222327; }}
            #MainSplitter::handle:hover {{ background-color: {accent}; }}
            QLineEdit {{ background: #2c2e33; border-radius: 5px; padding: 8px; color: white; border: 1px solid #444; }}
            QLineEdit:focus {{ border: 1px solid {accent}; }}
            #NavBtn, #AddTabBtn, #SidebarBtn {{ 
                background: transparent; border-radius: 5px; padding: 5px; font-size: 16px; 
            }}
            #NavBtn:hover, #AddTabBtn:hover {{ background: #3c3f45; }}
            #SidebarBtn {{
                font-size: 10px; font-weight: bold; padding: 10px 4px; color: #868e96;
            }}
            #SidebarBtn:hover {{ color: {accent}; background: transparent; }}
            QTabWidget::pane {{ border-top: 1px solid #333; background: #0b0c0d; }}
            QTabBar::tab {{
                background: #1c1d21; border-right: 1px solid #333;
                padding: 8px 8px 8px 14px; margin: 0px;
                min-width: 60px; max-width: 180px;
            }}
            QTabBar::tab:selected {{ background: #0b0c0d; border-bottom: 2px solid {accent}; }}
            #TabCloseBtn {{
                background: transparent; border: none; border-radius: 4px;
                color: #9aa0aa; font-size: 11px; font-weight: bold;
                padding: 2px; margin: 2px;
            }}
            #TabCloseBtn:hover {{ background: {accent}; color: white; }}
            #TabCloseBtn:pressed {{ background: {_darken(accent, 20)}; }}
            QProgressBar::chunk {{ background-color: {accent}; }}
            QListWidget {{ background: transparent; border: none; outline: none; }}
            QListWidget::item {{ padding: 10px; border-bottom: 1px solid #222; }}
            QListWidget::item:selected {{ background: {accent}; color: white; }}
            #SidebarFilter {{
                margin: 8px; padding: 6px 10px; border-radius: 12px;
                background: #26282e; border: 1px solid #333; font-size: 12px;
            }}
            #FindBar {{ background: #1c1d21; border-bottom: 1px solid {accent}; }}
            #FindCount {{ color: #888; padding: 0 6px; font-size: 12px; }}
        """)

    # ------------------------------------------------------------------
    # Построение интерфейса
    # ------------------------------------------------------------------

    def init_ui(self):
        """Сайдбар слева, контент справа."""
        self.update_styles()

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

        horizontal_container = QWidget()
        hbox = QHBoxLayout(horizontal_container)
        hbox.setContentsMargins(0, 0, 0, 0)
        hbox.setSpacing(0)

        # --- САЙДБАР (ЗАКЛАДКИ И ИСТОРИЯ) ---
        self.sidebar = QFrame(objectName="Sidebar")
        self.sidebar.setMinimumWidth(180)
        self.sidebar.setMaximumWidth(520)
        side_v_layout = QVBoxLayout(self.sidebar)

        side_nav = QFrame()
        side_nav_layout = QHBoxLayout(side_nav)
        btn_switch_bm = QPushButton("ЗАКЛАДКИ", objectName="SidebarBtn")
        btn_switch_hist = QPushButton("ИСТОРИЯ", objectName="SidebarBtn")
        btn_switch_groups = QPushButton("ГРУППЫ", objectName="SidebarBtn")
        btn_switch_bm.clicked.connect(lambda: self.sidebar_stack.setCurrentIndex(0))
        btn_switch_hist.clicked.connect(lambda: self.sidebar_stack.setCurrentIndex(1))
        btn_switch_groups.clicked.connect(lambda: (self.sidebar_stack.setCurrentIndex(2), self.groups_panel.refresh()))
        side_nav_layout.addWidget(btn_switch_bm)
        side_nav_layout.addWidget(btn_switch_hist)
        side_nav_layout.addWidget(btn_switch_groups)

        self.sidebar_stack = QStackedWidget()

        # --- Вкладка "Закладки": строка поиска + список ---
        bm_page = QWidget()
        bm_page_layout = QVBoxLayout(bm_page)
        bm_page_layout.setContentsMargins(0, 0, 0, 0)
        bm_page_layout.setSpacing(0)
        self.bookmark_filter = QLineEdit(objectName="SidebarFilter")
        self.bookmark_filter.setPlaceholderText("🔎 Поиск по закладкам...")
        self.bookmark_filter.textChanged.connect(self.refresh_sidebar_bookmarks)
        self.bookmark_list = QListWidget(objectName="BookmarkList")
        self.bookmark_list.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.bookmark_list.customContextMenuRequested.connect(self.show_bookmark_menu)
        self.bookmark_list.itemClicked.connect(self.on_sidebar_item_clicked)
        bm_page_layout.addWidget(self.bookmark_filter)
        bm_page_layout.addWidget(self.bookmark_list)

        # --- Вкладка "История": строка поиска + список ---
        hist_page = QWidget()
        hist_page_layout = QVBoxLayout(hist_page)
        hist_page_layout.setContentsMargins(0, 0, 0, 0)
        hist_page_layout.setSpacing(0)
        self.history_filter = QLineEdit(objectName="SidebarFilter")
        self.history_filter.setPlaceholderText("🔎 Поиск по истории...")
        self.history_filter.textChanged.connect(self.refresh_sidebar_history)
        self.history_list = QListWidget(objectName="HistoryList")
        self.history_list.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.history_list.customContextMenuRequested.connect(self.show_history_menu)
        self.history_list.itemClicked.connect(self.on_sidebar_item_clicked)
        hist_page_layout.addWidget(self.history_filter)
        hist_page_layout.addWidget(self.history_list)

        self.sidebar_stack.addWidget(bm_page)
        self.sidebar_stack.addWidget(hist_page)

        # --- Вкладка "Группы": сохранённые группы вкладок ---
        self.groups_panel = GroupsPanel(self)
        self.groups_panel.open_group_requested.connect(self.open_group_by_id)
        self.groups_panel.broadcast_group_requested.connect(self.broadcast_group_by_id)
        self.sidebar_stack.addWidget(self.groups_panel)

        side_v_layout.addWidget(side_nav)
        side_v_layout.addWidget(self.sidebar_stack)
        self.sidebar.hide()

        # --- ОСНОВНОЙ КОНТЕНТ (правая часть) ---
        right_container = QWidget()
        right_layout = QVBoxLayout(right_container)
        right_layout.setContentsMargins(0, 0, 0, 0)
        right_layout.setSpacing(0)

        self.top_bar = QFrame(objectName="TopBar")
        nav_layout = QHBoxLayout(self.top_bar)
        self.btn_side = QPushButton("≡", objectName="NavBtn")
        self.btn_side.clicked.connect(lambda: self.sidebar.setVisible(not self.sidebar.isVisible()))

        self.back_btn = QPushButton("‹", objectName="NavBtn")
        self.back_btn.clicked.connect(lambda: self.tabs.currentWidget().back() if self.tabs.currentWidget() else None)
        self.fwd_btn = QPushButton("›", objectName="NavBtn")
        self.fwd_btn.clicked.connect(lambda: self.tabs.currentWidget().forward() if self.tabs.currentWidget() else None)
        self.reload_btn = QPushButton("⟳", objectName="NavBtn")
        self.reload_btn.setToolTip("Обновить страницу")
        self.reload_btn.clicked.connect(self.on_reload_stop_clicked)
        self.home_btn = QPushButton("🏠", objectName="NavBtn")
        self.home_btn.clicked.connect(lambda: self.tabs.currentWidget().setUrl(self.start_url) if self.tabs.currentWidget() else None)

        # Индикатор безопасности протокола (🔒 HTTPS / ⚠ HTTP) слева от
        # адресной строки - показывает предупреждение, если сайт отдаётся
        # по незащищённому HTTP.
        self.security_indicator = QLabel("", objectName="SecurityIndicator")
        self.security_indicator.setFixedWidth(22)
        self.security_indicator.setAlignment(Qt.AlignmentFlag.AlignCenter)

        self.url_bar = QLineEdit()
        self.url_bar.setPlaceholderText("Введите URL или поисковый запрос... (Ctrl+L)")
        self.url_bar.returnPressed.connect(self.navigate_to_url)

        self.btn_incog = QPushButton("🕵️", objectName="NavBtn")
        self.btn_incog.clicked.connect(lambda: self.add_new_tab(self.start_url, "🕵️ Инкогнито", incognito=True))
        self.add_bookmark_btn = QPushButton("★", objectName="NavBtn")
        self.add_bookmark_btn.clicked.connect(self.add_bookmark_dialog)
        self.btn_broadcast = QPushButton("📡", objectName="NavBtn")
        self.btn_broadcast.setToolTip("Отправить активную вкладку в локальную сеть (LAN Broadcast)")
        self.btn_broadcast.clicked.connect(self.send_current_tab_to_network)
        self.btn_more = QPushButton("⋮", objectName="NavBtn")
        self.btn_more.clicked.connect(self.show_more_menu)

        nav_layout.addWidget(self.btn_side)
        nav_layout.addWidget(self.back_btn)
        nav_layout.addWidget(self.fwd_btn)
        nav_layout.addWidget(self.reload_btn)
        nav_layout.addWidget(self.home_btn)
        nav_layout.addWidget(self.security_indicator)
        nav_layout.addWidget(self.url_bar)
        nav_layout.addWidget(self.btn_incog)
        nav_layout.addWidget(self.add_bookmark_btn)
        nav_layout.addWidget(self.btn_broadcast)
        nav_layout.addWidget(self.btn_more)

        self.progress = QProgressBar()
        self.progress.setFixedHeight(2)
        self.progress.setTextVisible(False)
        self.progress.hide()

        # --- Панель поиска по странице (Ctrl+F) ---
        self.find_bar = QFrame(objectName="FindBar")
        self.find_bar.hide()
        find_layout = QHBoxLayout(self.find_bar)
        find_layout.setContentsMargins(8, 6, 8, 6)
        self.find_input = QLineEdit()
        self.find_input.setPlaceholderText("Найти на странице...")
        self.find_input.textChanged.connect(lambda text: self.do_find(text))
        self.find_input.returnPressed.connect(lambda: self.do_find(self.find_input.text(), backward=False, advance=True))
        self.find_count_label = QLabel("")
        self.find_count_label.setObjectName("FindCount")
        btn_find_prev = QPushButton("˄", objectName="NavBtn")
        btn_find_prev.setToolTip("Предыдущее совпадение (Shift+Enter)")
        btn_find_prev.clicked.connect(lambda: self.do_find(self.find_input.text(), backward=True, advance=True))
        btn_find_next = QPushButton("˅", objectName="NavBtn")
        btn_find_next.setToolTip("Следующее совпадение (Enter)")
        btn_find_next.clicked.connect(lambda: self.do_find(self.find_input.text(), backward=False, advance=True))
        btn_find_close = QPushButton("✕", objectName="NavBtn")
        btn_find_close.clicked.connect(self.close_find_bar)
        find_layout.addWidget(self.find_input, 1)
        find_layout.addWidget(self.find_count_label)
        find_layout.addWidget(btn_find_prev)
        find_layout.addWidget(btn_find_next)
        find_layout.addWidget(btn_find_close)

        self.tabs = QTabWidget()
        self.tabs.setTabBar(GroupedTabBar(self))
        self.tabs.setTabsClosable(True)
        self.tabs.setMovable(True)
        self.tabs.setIconSize(QSize(16, 16))
        self.tabs.setUsesScrollButtons(True)
        self.tabs.tabBar().setElideMode(Qt.TextElideMode.ElideRight)
        self.tabs.tabCloseRequested.connect(self.close_tab)
        self.tabs.currentChanged.connect(self.on_tab_changed)
        self.tabs.tabBar().setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.tabs.tabBar().customContextMenuRequested.connect(self.show_tab_context_menu)

        self.add_tab_btn = QToolButton(objectName="AddTabBtn")
        self.add_tab_btn.setText("+")
        self.add_tab_btn.clicked.connect(lambda: self.add_new_tab())
        self.tabs.setCornerWidget(self.add_tab_btn, Qt.Corner.TopRightCorner)

        right_layout.addWidget(self.top_bar)
        right_layout.addWidget(self.progress)
        right_layout.addWidget(self.find_bar)
        right_layout.addWidget(self.tabs)

        # Сайдбар и основной контент лежат в QSplitter, а не просто в HBox -
        # это даёт перетаскиваемую границу (resizable sidebar), как просили:
        # пользователь может менять ширину боковой панели мышью, граница не
        # уезжает за пределы min/max ширины, заданных на self.sidebar выше.
        self.main_splitter = QSplitter(Qt.Orientation.Horizontal, objectName="MainSplitter")
        self.main_splitter.setHandleWidth(4)
        self.main_splitter.setChildrenCollapsible(False)
        self.main_splitter.addWidget(self.sidebar)
        self.main_splitter.addWidget(right_container)
        self.main_splitter.setStretchFactor(0, 0)
        self.main_splitter.setStretchFactor(1, 1)
        self.main_splitter.setSizes([250, 1050])
        hbox.addWidget(self.main_splitter)

        self.main_layout.addWidget(horizontal_container)

    # ------------------------------------------------------------------
    # Меню / DevTools
    # ------------------------------------------------------------------

    def show_more_menu(self):
        """Главное меню (⋮) - НАМЕРЕННО короткое (5 пунктов): всё остальное,
        что раньше было здесь (LAN, AdBlock, Tab Suspender, пароли, вики-
        поиск), теперь живёт в соответствующих вкладках "Настроек браузера"
        (см. BrowserSettingsWindow) - здесь только самое частое/быстрое."""
        menu = QMenu(self)
        act_set = QAction(tr("browser.menu.settings"), self)
        act_set.triggered.connect(lambda: BrowserSettingsWindow(self).exec())
        act_find = QAction(tr("browser.menu.find_on_page"), self)
        act_find.triggered.connect(self.open_find_bar)
        act_dev = QAction(tr("browser.menu.devtools"), self)
        act_dev.triggered.connect(self.toggle_devtools)
        act_restore = QAction(tr("browser.menu.restore_tab"), self)
        act_restore.triggered.connect(self.restore_closed_tab)
        act_save_group = QAction(tr("browser.menu.save_session_as_group"), self)
        act_save_group.triggered.connect(self.groups_panel.save_current_session)

        menu.addAction(act_set)
        menu.addAction(act_find)
        menu.addAction(act_dev)
        menu.addAction(act_restore)
        menu.addAction(act_save_group)
        menu.exec(self.btn_more.mapToGlobal(QPoint(0, self.btn_more.height())))

    # ------------------------------------------------------------------
    # Динамический AdBlock (фоновое обновление списка с GitHub)
    # ------------------------------------------------------------------

    def _maybe_run_adblock_update(self):
        """Вызывается по часовому таймеру (см. __init__) - реально запускает
        скачивание, только если это включено в настройках И с прошлого
        успешного обновления прошло достаточно времени (интервал тоже из
        настроек, по умолчанию 24 часа). Ручной вызов из меню (⋮ → «Обновить
        список блокировки сейчас») обходит эту проверку намеренно."""
        if not self.settings.get("adblock_dynamic_update_enabled", True):
            return
        interval_h = max(1, int(self.settings.get("adblock_update_interval_hours", 24)))
        last_iso = self.settings.get("adblock_last_update", "")
        if last_iso:
            try:
                last_dt = datetime.fromisoformat(last_iso)
                if datetime.now() - last_dt < timedelta(hours=interval_h):
                    return
            except Exception:
                pass  # битая дата в настройках - просто обновляем сейчас
        self.adblock_updater.update_now(self.settings.get("adblock_update_url") or None)

    def _on_adblock_update_finished(self, added_count, error):
        self.settings["adblock_last_update"] = datetime.now().isoformat()
        self.save_data(SETTINGS_FILE, self.settings)
        if error:
            self.statusBar_message(f"🛡️ AdBlock: обновление не удалось ({error})", 3000)
        else:
            self.statusBar_message(f"🛡️ AdBlock: список блокировки обновлён (+{added_count} доменов)", 3000)

    def _toggle_adblock_dynamic_update(self, checked):
        self.settings["adblock_dynamic_update_enabled"] = checked
        self.save_data(SETTINGS_FILE, self.settings)
        if checked:
            self._maybe_run_adblock_update()

    def _maybe_run_adblock_update_forced(self):
        """«Обновить сейчас» из меню ⋮ - в отличие от _maybe_run_adblock_update
        игнорирует и флаг включения, и таймер интервала: пользователь явно
        попросил обновить прямо сейчас."""
        self.adblock_updater.update_now(self.settings.get("adblock_update_url") or None)

    def _toggle_lan_clipboard(self, checked):
        self.settings["lan_clipboard_enabled"] = checked
        self.save_data(SETTINGS_FILE, self.settings)
        if checked:
            self.statusBar_message("📋 Общий буфер обмена по LAN включён", 2500)

    def _toggle_lan_bookmark_sync(self, checked):
        self.settings["lan_bookmark_sync_enabled"] = checked
        self.save_data(SETTINGS_FILE, self.settings)
        if checked:
            self.statusBar_message("🔗 Синхронизация закладок по LAN включена", 2500)
            self.broadcast_service.send_bookmarks(self.bookmarks)

    def _toggle_tab_suspender_enabled(self, checked):
        self.settings["tab_suspend_enabled"] = checked
        self.save_data(SETTINGS_FILE, self.settings)

    def _ask_tab_suspender_timeout(self):
        current = int(self.settings.get("tab_suspend_minutes", 15))
        minutes, ok = QInputDialog.getInt(
            self, "Таймаут спящих вкладок",
            "Через сколько минут неактивности выгружать вкладку из памяти:",
            current, 1, 240,
        )
        if ok:
            self.settings["tab_suspend_minutes"] = minutes
            self.save_data(SETTINGS_FILE, self.settings)

    def toggle_devtools(self):
        """Запуск панели разработчика."""
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

    # ------------------------------------------------------------------
    # Управление вкладками
    # ------------------------------------------------------------------

    def add_new_tab(self, qurl=None, label="Новая вкладка", incognito=False):
        """Создание новой вкладки в движке."""
        if qurl is None:
            qurl = self.start_url
        browser = QWebEngineView()
        prof = self.incognito_profile if incognito else self.profile
        page = GORWebPage(prof, browser)
        page.ins_browser = self
        browser.setPage(page)
        browser.setUrl(qurl)
        index = self.tabs.addTab(browser, label)
        self.tabs.setCurrentIndex(index)
        # Пункт 8 (крестик закрытия вкладки): штатная Qt-иконка close-button
        # на этой тёмной теме почти не видна (низкий контраст, зависит от
        # стиля ОС) - вместо борьбы с QSS::close-button ставим свой надёжный
        # QToolButton с "✕" (тот же helper, что уже использовался для
        # возврата крестика открепляемым вкладкам - см. toggle_pin_tab).
        self.tabs.tabBar().setTabButton(index, QTabBar.ButtonPosition.RightSide, self._make_tab_close_button(browser))
        browser.setProperty("gor_last_active_ts", time.time())
        browser.urlChanged.connect(lambda q, b=browser: self.on_url_changed(q, b))
        browser.loadStarted.connect(lambda b=browser: self.on_load_started(b))
        browser.loadFinished.connect(lambda ok, b=browser: self.on_load_finished_state(b, ok))
        browser.loadFinished.connect(lambda _, b=browser: self.update_tab_title(b))
        browser.loadFinished.connect(lambda ok, b=browser: self.sync_start_page_settings(b) if ok and "start_page.html" in b.url().toString() else None)
        browser.loadProgress.connect(self.update_progress)
        browser.iconChanged.connect(lambda icon, b=browser: self.update_tab_icon(b, icon))
        page.fullScreenRequested.connect(self.handle_fullscreen_request)
        self._schedule_session_save()
        return browser

    def _emoji_tab_icon(self, emoji):
        """Пункт 9 (индикаторы типа вкладки): рендерит эмодзи в QIcon и
        кеширует результат - используется для значков Инкогнито/Главная/
        Обложка СЛЕВА от заголовка вкладки (через setTabIcon), а не префиксом
        в самом тексте, как было раньше."""
        cache = getattr(self, "_emoji_icon_cache", None)
        if cache is None:
            cache = self._emoji_icon_cache = {}
        icon = cache.get(emoji)
        if icon is not None:
            return icon
        pixmap = QPixmap(32, 32)
        pixmap.fill(Qt.GlobalColor.transparent)
        painter = QPainter(pixmap)
        font = painter.font()
        font.setPointSize(18)
        painter.setFont(font)
        painter.drawText(pixmap.rect(), Qt.AlignmentFlag.AlignCenter, emoji)
        painter.end()
        icon = QIcon(pixmap)
        cache[emoji] = icon
        return icon

    def update_tab_icon(self, browser, icon):
        """Устанавливает иконку вкладки - единая точка правды и для
        настоящих favicon'ов сайтов, и для значков спецтипов вкладок
        (Инкогнито 🕵️/Главная 🏠/Обложка 🖼️, пункт 9 ТЗ) - чтобы эти два
        источника не перетирали друг друга в непредсказуемом порядке
        (iconChanged сайта может сработать в любой момент)."""
        index = self.tabs.indexOf(browser)
        if index == -1:
            return
        if browser.property("gor_cover_picker_label"):
            # У служебной вкладки "выбор обложки" всегда одна и та же
            # иконка - настоящий favicon сайта её бы затёр и вкладку
            # стало бы не отличить от обычной.
            self.tabs.setTabIcon(index, self._emoji_tab_icon("🖼️"))
            return
        url_str = browser.url().toString()
        if "start_page.html" in url_str:
            is_incognito = browser.page().profile() == self.incognito_profile
            self.tabs.setTabIcon(index, self._emoji_tab_icon("🕵️" if is_incognito else "🏠"))
        elif not icon.isNull():
            self.tabs.setTabIcon(index, icon)

    def update_progress(self, p):
        """Обновление индикатора загрузки."""
        self.progress.setValue(p)
        self.progress.setVisible(p < 100)

    def on_url_changed(self, qurl, browser):
        """Событие при смене адреса."""
        url_str = qurl.toString()
        if browser == self.tabs.currentWidget():
            self.url_bar.setText("" if "start_page.html" in url_str else url_str)
            self.update_security_indicator(url_str)
        if browser.page().profile() != self.incognito_profile and "start_page.html" not in url_str:
            self.add_to_history(browser.page().title() or url_str, url_str, browser.icon())
        self.refresh_groups_panel()
        self._schedule_session_save()

    def update_security_indicator(self, url_str):
        """Обновляет иконку слева от адресной строки в зависимости от
        протокола: 🔒 для HTTPS, ⚠ (жёлтым) для незащищённого HTTP, пусто
        для служебных страниц (стартовая, file://, chrome:// и т.п.)."""
        scheme = QUrl(url_str).scheme().lower()
        if not url_str or "start_page.html" in url_str or scheme not in ("http", "https"):
            self.security_indicator.setText("")
            self.security_indicator.setToolTip("")
            self.security_indicator.setStyleSheet("")
            return
        if scheme == "https":
            self.security_indicator.setText("🔒")
            self.security_indicator.setToolTip("Соединение защищено (HTTPS)")
            self.security_indicator.setStyleSheet("color: #2f9e44; font-size: 13px;")
        else:
            self.security_indicator.setText("⚠")
            self.security_indicator.setToolTip(
                "Небезопасное соединение (HTTP) - данные передаются без шифрования"
            )
            self.security_indicator.setStyleSheet("color: #f59f00; font-weight: bold; font-size: 13px;")

    def _icon_to_data_uri(self, icon):
        """Пункт 4 ТЗ: сериализует QIcon в data:image/png;base64,... для
        хранения favicon'а прямо в JSON-записи закладки/истории (переживает
        перезапуск браузера, не только текущую сессию)."""
        if icon is None or icon.isNull():
            return ""
        pixmap = icon.pixmap(16, 16)
        if pixmap.isNull():
            return ""
        buf = QBuffer()
        buf.open(QIODevice.OpenModeFlag.WriteOnly)
        pixmap.save(buf, "PNG")
        b64 = base64.b64encode(bytes(buf.data())).decode("ascii")
        return f"data:image/png;base64,{b64}" if b64 else ""

    def _icon_from_data_uri(self, data_uri):
        """Обратная операция - для рендера favicon'а в сайдбаре истории/
        закладок (см. refresh_sidebar_bookmarks/refresh_sidebar_history)."""
        if not data_uri or not data_uri.startswith("data:image"):
            return None
        try:
            b64_part = data_uri.split(",", 1)[1]
            raw = base64.b64decode(b64_part)
        except (IndexError, ValueError, base64.binascii.Error):
            return None
        pixmap = QPixmap()
        if not pixmap.loadFromData(raw):
            return None
        return QIcon(pixmap)

    def add_to_history(self, title, url, icon=None):
        """Добавление записи в историю GOR. icon - favicon текущей вкладки
        (пункт 4 ТЗ) - сохраняется вместе с записью как base64 PNG."""
        time_str = datetime.now().strftime("%H:%M")
        self.history.insert(0, {
            "title": title, "url": url, "time": time_str,
            "favicon": self._icon_to_data_uri(icon),
        })
        self.history = self.history[:150]
        self.save_data(HISTORY_FILE, self.history)
        self.refresh_sidebar_history()

    def update_tab_title(self, browser):
        """Обновление текста на вкладке."""
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
                self.update_tab_icon(browser, browser.icon())
                return
            # Пока вкладка служит "заголовком" свёрнутой группы (см.
            # toggle_group_collapse), её текст не должен затираться реальным
            # title() загруженной страницы.
            if browser.property("gor_group_collapsed_header"):
                return
            url_str = browser.url().toString()
            if "start_page.html" in url_str:
                is_incognito = browser.page().profile() == self.incognito_profile
                base_text = tr("browser.tab.incognito_label") if is_incognito else tr("browser.tab.home_label")
            else:
                title = browser.page().title() or "Загрузка..."
                base_text = title[:15]

            prefix = ""
            if browser.property("gor_not_responding"):
                prefix += "⚠️ "
            if browser in self.pinned_tabs:
                prefix += "📌 "
            self.tabs.setTabText(index, prefix + base_text)
            # Значок (Инкогнито/Главная/favicon) - отдельно от текста,
            # см. update_tab_icon (пункт 9 ТЗ).
            self.update_tab_icon(browser, browser.icon())

    def navigate_to_url(self):
        """Переход по введенному адресу или поиск."""
        text = self.url_bar.text().strip()
        if not text:
            return
        engine_name = self.settings.get("search_engine", "Google")
        search_url = SEARCH_ENGINES.get(engine_name, SEARCH_ENGINES["Google"])
        url = QUrl(f"{search_url}{text}") if "." not in text else QUrl(text if "://" in text else "http://" + text)
        self.tabs.currentWidget().setUrl(url)

    def setup_shortcuts(self):
        """Горячие клавиши GOR."""
        QShortcut(QKeySequence("Ctrl+T"), self).activated.connect(lambda: self.add_new_tab())
        QShortcut(QKeySequence("Ctrl+W"), self).activated.connect(lambda: self.close_tab(self.tabs.currentIndex()))
        QShortcut(QKeySequence("Ctrl+H"), self).activated.connect(lambda: self.sidebar.setVisible(not self.sidebar.isVisible()))
        QShortcut(QKeySequence("F12"), self).activated.connect(self.toggle_devtools)

        # --- Новые горячие клавиши ---
        QShortcut(QKeySequence("Ctrl+F"), self).activated.connect(self.open_find_bar)
        QShortcut(QKeySequence("Ctrl+L"), self).activated.connect(self.focus_url_bar)
        QShortcut(QKeySequence("Ctrl+Shift+T"), self).activated.connect(self.restore_closed_tab)
        QShortcut(QKeySequence("Ctrl+="), self).activated.connect(self.zoom_in)
        QShortcut(QKeySequence("Ctrl++"), self).activated.connect(self.zoom_in)
        QShortcut(QKeySequence("Ctrl+-"), self).activated.connect(self.zoom_out)
        QShortcut(QKeySequence("Ctrl+0"), self).activated.connect(self.zoom_reset)
        QShortcut(QKeySequence("Escape"), self).activated.connect(self.on_escape_pressed)

        # Ctrl+1..Ctrl+8 - переключение на вкладку по её позиции в ленте
        # (как в Chrome/Firefox); Ctrl+9 - всегда последняя вкладка.
        for i in range(1, 9):
            QShortcut(QKeySequence(f"Ctrl+{i}"), self).activated.connect(
                lambda pos=i - 1: self.focus_tab_by_position(pos)
            )
        QShortcut(QKeySequence("Ctrl+9"), self).activated.connect(
            lambda: self.focus_tab_by_position(self.tabs.count() - 1)
        )

        # «Быстрый поиск по вики» (пункт ТЗ) - ApplicationShortcut, чтобы
        # срабатывал независимо от того, какой дочерний виджет (в т.ч.
        # веб-страница) сейчас в фокусе внутри окна браузера.
        wiki_shortcut = QShortcut(QKeySequence("Ctrl+Shift+K"), self)
        wiki_shortcut.setContext(Qt.ShortcutContext.ApplicationShortcut)
        wiki_shortcut.activated.connect(self.open_wiki_search_overlay)

    def on_escape_pressed(self):
        """Esc: сначала закрывает поиск по странице (если открыт), иначе
        выходит из полноэкранного видео (если оно активно)."""
        if self.find_bar.isVisible():
            self.close_find_bar()
        elif self._fullscreen_active:
            browser = self.tabs.currentWidget()
            if browser:
                browser.page().runJavaScript("document.exitFullscreen && document.exitFullscreen();")

    # ------------------------------------------------------------------
    # Поиск по странице (Ctrl+F)
    # ------------------------------------------------------------------

    def open_find_bar(self):
        browser = self.tabs.currentWidget()
        if not browser:
            return
        self.find_bar.show()
        self.find_input.setFocus()
        self.find_input.selectAll()
        if self.find_input.text():
            self.do_find(self.find_input.text())

    def close_find_bar(self):
        browser = self.tabs.currentWidget()
        if browser:
            browser.page().findText("")
        self.find_bar.hide()
        self.find_count_label.setText("")

    def do_find(self, text, backward=False, advance=False):
        """Запускает поиск текста на текущей вкладке. advance=True означает,
        что это переход к след./пред. совпадению (Enter / кнопки ˄˅), а не
        обычная перепечатка текста в поле."""
        browser = self.tabs.currentWidget()
        if not browser:
            return
        if not text:
            browser.page().findText("")
            self.find_count_label.setText("")
            return
        flags = QWebEnginePage.FindFlag.FindBackward if backward else QWebEnginePage.FindFlag(0)

        def _on_result(result):
            try:
                total = result.numberOfMatches()
                active = result.activeMatch()
            except AttributeError:
                # Более старые версии PyQt6/Qt могут не поддерживать
                # структурированный результат - просто скрываем счётчик.
                self.find_count_label.setText("")
                return
            self.find_count_label.setText(f"{active}/{total}" if total else "0/0")

        browser.page().findText(text, flags, _on_result)

    # ------------------------------------------------------------------
    # Масштаб страницы (Ctrl +/-/0)
    # ------------------------------------------------------------------

    def zoom_in(self):
        browser = self.tabs.currentWidget()
        if browser:
            browser.setZoomFactor(min(ZOOM_MAX, round(browser.zoomFactor() + ZOOM_STEP, 2)))

    def zoom_out(self):
        browser = self.tabs.currentWidget()
        if browser:
            browser.setZoomFactor(max(ZOOM_MIN, round(browser.zoomFactor() - ZOOM_STEP, 2)))

    def zoom_reset(self):
        browser = self.tabs.currentWidget()
        if browser:
            browser.setZoomFactor(1.0)

    # ------------------------------------------------------------------
    # Адресная строка (Ctrl+L)
    # ------------------------------------------------------------------

    def focus_url_bar(self):
        self.url_bar.setFocus()
        self.url_bar.selectAll()

    # ------------------------------------------------------------------
    # Reload/Stop и индикатор "страница не отвечает"
    # ------------------------------------------------------------------

    def on_reload_stop_clicked(self):
        browser = self.tabs.currentWidget()
        if not browser:
            return
        if browser.property("gor_loading"):
            browser.stop()
        else:
            browser.reload()

    def on_load_started(self, browser):
        browser.setProperty("gor_loading", True)
        if browser == self.tabs.currentWidget():
            self.reload_btn.setText("✕")
            self.reload_btn.setToolTip("Остановить загрузку")
        QTimer.singleShot(NOT_RESPONDING_TIMEOUT_MS, lambda b=browser: self._check_not_responding(b))

    def on_load_finished_state(self, browser, ok):
        browser.setProperty("gor_loading", False)
        was_not_responding = bool(browser.property("gor_not_responding"))
        browser.setProperty("gor_not_responding", False)
        if browser == self.tabs.currentWidget():
            self.reload_btn.setText("⟳")
            self.reload_btn.setToolTip("Обновить страницу")
        if was_not_responding:
            self.update_tab_title(browser)

    def _check_not_responding(self, browser):
        """Срабатывает через NOT_RESPONDING_TIMEOUT_MS после начала загрузки.
        Если вкладка к этому моменту всё ещё грузится - помечаем как ⚠."""
        if browser.property("gor_loading"):
            browser.setProperty("gor_not_responding", True)
            self.update_tab_title(browser)

    def on_tab_changed(self, index):
        """При переключении вкладки - обновляем адресную строку и
        состояние кнопки reload/stop под свежевыбранную вкладку."""
        browser = self.tabs.widget(index)
        if not browser:
            return
        self._wake_tab_if_suspended(browser, index)
        browser.setProperty("gor_last_active_ts", time.time())
        url_str = browser.url().toString()
        self.url_bar.setText("" if "start_page.html" in url_str else url_str)
        self.update_security_indicator(url_str)
        self.reload_btn.setText("✕" if browser.property("gor_loading") else "⟳")
        if self.find_bar.isVisible():
            self.close_find_bar()

    def focus_tab_by_position(self, position):
        """Ctrl+1..Ctrl+9: переключает на вкладку по позиции в ленте
        (0-based), включая закреплённые - они всегда идут первыми."""
        if 0 <= position < self.tabs.count():
            self.tabs.setCurrentIndex(position)

    def open_wiki_search_overlay(self):
        """Ctrl+Shift+K - показывает WikiSearchOverlay поверх окна браузера
        (см. класс выше). Держим ссылку в self, иначе PyQt соберёт диалог
        мусорщиком сразу после show() (тот же паттерн, что и у BroadcastToast)."""
        self._wiki_overlay = WikiSearchOverlay(self)
        self._wiki_overlay._position_center()
        self._wiki_overlay.show()

    # ------------------------------------------------------------------
    # Полноэкранное видео (YouTube и т.п.)
    # ------------------------------------------------------------------

    def handle_fullscreen_request(self, request):
        """QWebEnginePage.fullScreenRequested: сайт (например, плеер
        YouTube) просит развернуть <video> на весь экран. Разворачиваем
        браузер внутри лаунчера на всю доступную область, пряча тулбар,
        вкладки и сайдбар; выход - Esc или повторный клик по видео."""
        request.accept()
        if request.toggleOn():
            self._fullscreen_active = True
            self._pre_fullscreen_sidebar_visible = self.sidebar.isVisible()
            self.sidebar.hide()
            self.top_bar.hide()
            self.tabs.tabBar().hide()
            self.progress.hide()
            self.find_bar.hide()
        else:
            self._fullscreen_active = False
            self.top_bar.show()
            self.tabs.tabBar().show()
            if self._pre_fullscreen_sidebar_visible:
                self.sidebar.show()

    def close_tab(self, i):
        """Закрытие активной вкладки (с сохранением в стек для Ctrl+Shift+T)."""
        if self.tabs.count() > 1:
            self._push_closed_tab(i)
            self.tabs.removeTab(i)
        else:
            self.tabs.currentWidget().setUrl(self.start_url)
        self.refresh_groups_panel()
        self._schedule_session_save()

    def _push_closed_tab(self, i):
        """Запоминает закрываемую вкладку для последующего восстановления.
        ВАЖНО: приватные (инкогнито) вкладки в стек НЕ попадают вообще -
        Ctrl+Shift+T должен работать только с публичной историей закрытых
        вкладок, иначе приватный URL "утекает" через обычное восстановление
        (это и была ошибка: закрытая инкогнито-вкладка выживала в памяти
        сессии и восстанавливалась по хоткею)."""
        browser = self.tabs.widget(i)
        if not browser:
            return
        if browser.page().profile() == self.incognito_profile:
            self.pinned_tabs.discard(browser)
            return  # не сохраняем НИЧЕГО про приватную вкладку - ни URL, ни факт её существования
        url_str = browser.url().toString()
        if "start_page.html" in url_str:
            return  # не засоряем стек стартовыми страницами
        self.closed_tabs.append({
            "url": url_str,
            "label": self.tabs.tabText(i),
        })
        self.closed_tabs = self.closed_tabs[-20:]
        self.pinned_tabs.discard(browser)

    def restore_closed_tab(self):
        """Ctrl+Shift+T: переоткрывает последнюю закрытую ПУБЛИЧНУЮ вкладку.
        Стек closed_tabs по построению (см. _push_closed_tab) никогда не
        содержит инкогнито-записей, поэтому здесь даже не нужно повторно
        проверять флаг - восстановление инкогнито-вкладок этим путём
        архитектурно невозможно."""
        if not self.closed_tabs:
            return
        entry = self.closed_tabs.pop()
        self.add_new_tab(QUrl(entry["url"]), entry["label"], incognito=False)

    # ------------------------------------------------------------------
    # Контекстное меню вкладок (правый клик по табу)
    # ------------------------------------------------------------------

    def show_tab_context_menu(self, pos):
        index = self.tabs.tabBar().tabAt(pos)
        if index == -1:
            return
        browser = self.tabs.widget(index)
        is_pinned = browser in self.pinned_tabs
        group_id = browser.property("gor_group_id")
        group = self.find_tab_group(group_id) if group_id else None

        menu = QMenu(self)
        act_dup = QAction("⧉  Дублировать вкладку", self)
        act_dup.triggered.connect(lambda: self.duplicate_tab(index))
        act_pin = QAction((tr("browser.tab.unpin") if is_pinned else tr("browser.tab.pin")), self)
        act_pin.triggered.connect(lambda: self.toggle_pin_tab(index))
        act_close = QAction(tr("browser.tab.close"), self)
        act_close.triggered.connect(lambda: self.close_tab(index))
        act_close_others = QAction(tr("browser.tab.close_others"), self)
        act_close_others.triggered.connect(lambda: self.close_other_tabs(index))
        act_close_right = QAction(tr("browser.tab.close_right"), self)
        act_close_right.triggered.connect(lambda: self.close_tabs_to_right(index))

        menu.addAction(act_dup)
        menu.addAction(act_pin)
        menu.addSeparator()

        # --- Группировка вкладки (визуально как в Firefox/Chrome) ---------
        if group:
            is_collapsed = group_id in self.collapsed_group_ids
            act_collapse = QAction(
                ("👁  Развернуть группу «%s»" if is_collapsed else "🙈  Свернуть группу «%s»") % group.get("name", "?"),
                self,
            )
            act_collapse.triggered.connect(lambda: self.toggle_group_collapse(group_id))
            act_ungroup = QAction(f"➖  Убрать вкладку из группы «{group.get('name', '?')}»", self)
            act_ungroup.triggered.connect(lambda: self.untag_tab_from_group(index))
            menu.addAction(act_collapse)
            menu.addAction(act_ungroup)
        else:
            group_menu = QMenu("➕  Добавить в группу", menu)
            if self.tab_groups:
                for g in self.tab_groups:
                    act_g = QAction(g.get("name", "?"), self)
                    act_g.triggered.connect(lambda checked=False, gid=g["id"]: self.add_tab_to_group(index, gid))
                    group_menu.addAction(act_g)
                group_menu.addSeparator()
            act_new_group = QAction("🆕  Новая группа из этой вкладки...", self)
            act_new_group.triggered.connect(lambda: self.create_group_from_tab(index))
            group_menu.addAction(act_new_group)
            menu.addMenu(group_menu)
        menu.addSeparator()

        menu.addAction(act_close)
        menu.addAction(act_close_others)
        menu.addAction(act_close_right)
        menu.exec(self.tabs.tabBar().mapToGlobal(pos))

    def duplicate_tab(self, index):
        browser = self.tabs.widget(index)
        if not browser:
            return
        incognito = browser.page().profile() == self.incognito_profile
        self.add_new_tab(browser.url(), self.tabs.tabText(index), incognito=incognito)

    def toggle_pin_tab(self, index):
        browser = self.tabs.widget(index)
        if not browser:
            return
        bar = self.tabs.tabBar()
        if browser in self.pinned_tabs:
            self.pinned_tabs.discard(browser)
            bar.setTabButton(index, QTabBar.ButtonPosition.RightSide, self._make_tab_close_button(browser))
        else:
            self.pinned_tabs.add(browser)
            # Закреплённая вкладка переезжает в начало (после других
            # закреплённых), как в обычных браузерах.
            pinned_count = sum(1 for i in range(self.tabs.count()) if self.tabs.widget(i) in self.pinned_tabs)
            self.tabs.tabBar().moveTab(index, max(0, pinned_count - 1))
            new_index = self.tabs.indexOf(browser)
            # Закреплённые вкладки не показывают крестик закрытия (как в
            # Chrome/Firefox) - закрыть их всё равно можно через контекстное
            # меню/среднюю кнопку мыши, но случайный клик по ✕ их не сносит.
            bar.setTabButton(new_index, QTabBar.ButtonPosition.RightSide, None)
        self.update_tab_title(browser)
        self._schedule_session_save()

    def _make_tab_close_button(self, browser):
        """Кнопка-крестик закрытия вкладки, привязанная к КОНКРЕТНОМУ
        виджету вкладки (а не к позиции, которая может сдвинуться при
        перетаскивании/закреплении других вкладок) - используется, чтобы
        вернуть крестик открепляемой вкладке (см. toggle_pin_tab)."""
        btn = QToolButton()
        btn.setText("✕")
        btn.setObjectName("TabCloseBtn")
        btn.setCursor(Qt.CursorShape.PointingHandCursor)
        btn.setAutoRaise(True)
        btn.clicked.connect(lambda checked=False, b=browser: self.close_tab(self.tabs.indexOf(b)))
        return btn

    def close_other_tabs(self, keep_index):
        keep_widget = self.tabs.widget(keep_index)
        for i in reversed(range(self.tabs.count())):
            widget = self.tabs.widget(i)
            if widget is not keep_widget and widget not in self.pinned_tabs:
                self._push_closed_tab(i)
                self.tabs.removeTab(i)
        self.refresh_groups_panel()
        self._schedule_session_save()

    def close_tabs_to_right(self, index):
        for i in reversed(range(index + 1, self.tabs.count())):
            if self.tabs.widget(i) in self.pinned_tabs:
                continue
            self._push_closed_tab(i)
            self.tabs.removeTab(i)
        self.refresh_groups_panel()
        self._schedule_session_save()

    # ------------------------------------------------------------------
    # Закладки и история (сайдбар)
    # ------------------------------------------------------------------

    def refresh_sidebar_bookmarks(self):
        query = self.bookmark_filter.text().strip().lower() if hasattr(self, "bookmark_filter") else ""
        self.bookmark_list.clear()
        for bm in self.bookmarks:
            if query and query not in bm['name'].lower() and query not in bm['url'].lower():
                continue
            item = QListWidgetItem(bm['name'])
            # Пункт 4 ТЗ: реальный favicon сайта вместо статичной эмодзи "⭐".
            icon = self._icon_from_data_uri(bm.get("favicon", "")) or self._emoji_tab_icon("⭐")
            item.setIcon(icon)
            item.setData(Qt.ItemDataRole.UserRole, bm['url'])
            self.bookmark_list.addItem(item)

    def refresh_sidebar_history(self):
        query = self.history_filter.text().strip().lower() if hasattr(self, "history_filter") else ""
        self.history_list.clear()
        for h in self.history:
            title = h.get('title', '...')
            url = h.get('url', '')
            if query and query not in title.lower() and query not in url.lower():
                continue
            t = h.get('time', '--:--')
            n = title[:30]
            item = QListWidgetItem(f"{t}  {n}")
            # Пункт 4 ТЗ: реальный favicon сайта вместо статичной эмодзи "🕒".
            icon = self._icon_from_data_uri(h.get("favicon", "")) or self._emoji_tab_icon("🕒")
            item.setIcon(icon)
            item.setData(Qt.ItemDataRole.UserRole, url)
            self.history_list.addItem(item)

    def show_bookmark_menu(self, pos):
        item = self.bookmark_list.itemAt(pos)
        if item:
            menu = QMenu()
            edit_act = QAction("Редактировать закладку", self)
            edit_act.triggered.connect(lambda: self.edit_bookmark(item))
            del_act = QAction("Удалить закладку", self)
            del_act.triggered.connect(lambda: self.delete_item(item, "bm"))
            menu.addAction(edit_act)
            menu.addAction(del_act)
            menu.exec(self.bookmark_list.mapToGlobal(pos))

    def edit_bookmark(self, item):
        """Редактирование имени и адреса уже существующей закладки (а не
        только удаление, как раньше)."""
        old_url = item.data(Qt.ItemDataRole.UserRole)
        bm = next((x for x in self.bookmarks if x['url'] == old_url), None)
        if not bm:
            return
        name, ok1 = QInputDialog.getText(self, "Редактировать закладку", "Имя закладки:", text=bm['name'])
        if not (ok1 and name.strip()):
            return
        url, ok2 = QInputDialog.getText(self, "Редактировать закладку", "Адрес:", text=bm['url'])
        if not (ok2 and url.strip()):
            return
        bm['name'] = name.strip()
        bm['url'] = url.strip()
        self.save_data(BOOKMARKS_FILE, self.bookmarks)
        self.refresh_sidebar_bookmarks()
        self._maybe_broadcast_bookmarks()

    def show_history_menu(self, pos):
        item = self.history_list.itemAt(pos)
        if item:
            menu = QMenu()
            del_act = QAction("Удалить из истории", self)
            del_act.triggered.connect(lambda: self.delete_item(item, "hist"))
            menu.addAction(del_act)
            menu.exec(self.history_list.mapToGlobal(pos))

    def delete_item(self, item, mode):
        url = item.data(Qt.ItemDataRole.UserRole)
        if mode == "bm":
            self.bookmarks = [x for x in self.bookmarks if x['url'] != url]
            self.save_data(BOOKMARKS_FILE, self.bookmarks)
            self.refresh_sidebar_bookmarks()
            # Удаление НЕ рассылаем в сеть: наша схема синка - "только
            # добавлять недостающее по URL" (см. _handle_incoming_bookmark_sync),
            # без этого удаление у одного удаляло бы закладку у всех.
        else:
            self.history = [x for x in self.history if x['url'] != url]
            self.save_data(HISTORY_FILE, self.history)
            self.refresh_sidebar_history()

    def on_sidebar_item_clicked(self, item):
        target_url = item.data(Qt.ItemDataRole.UserRole)
        if target_url:
            self.tabs.currentWidget().setUrl(QUrl(target_url))

    def add_bookmark_dialog(self):
        browser = self.tabs.currentWidget()
        name, ok = QInputDialog.getText(self, "Новая закладка", "Имя закладки:", text=browser.page().title()[:20])
        if ok and name:
            self.bookmarks.append({
                "name": name, "url": browser.url().toString(),
                "favicon": self._icon_to_data_uri(browser.icon()),
            })
            self.save_data(BOOKMARKS_FILE, self.bookmarks)
            self.refresh_sidebar_bookmarks()
            self._maybe_broadcast_bookmarks()


# --- ЗАПУСК КАК ОТДЕЛЬНОГО ПРИЛОЖЕНИЯ (для теста движка вне лаунчера) ---
if __name__ == "__main__":
    app = QApplication(sys.argv)

    test_window = QMainWindow()
    test_window.setWindowTitle("GOR Browser Engine Test")
    test_window.resize(1200, 800)

    browser_widget = GORBrowser()

    test_window.setCentralWidget(browser_widget)

    test_window.show()
    sys.exit(app.exec())