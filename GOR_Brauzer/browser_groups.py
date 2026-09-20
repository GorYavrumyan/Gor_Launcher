"""
browser_groups.py
-------------------
Сохраняемые группы вкладок GOR Browser (release notes v1.2): создание,
переименование, кастомный цвет, автосохранение в общий games_data.json
(блок "browser" -> "tab_groups") и мгновенный запуск через боковую панель.

Формат одной группы:
    {
        "id": "grp_1700000000000",   # уникальный id (timestamp-based)
        "name": "Код",
        "color": "#4c6ef5",
        "urls": ["https://...", "https://..."],   # 1..N вкладок
        "created": "2026-09-17 14:05",
    }

GORBrowser (browser_widget.py) хранит self.tab_groups - список таких
словарей, читает/пишет его через load_data(TAB_GROUPS_FILE) /
save_data(TAB_GROUPS_FILE, ...), т.е. так же, как bookmarks/history.

Этот модуль отвечает за:
    - GroupsPanel   - QWidget для сайдбара (список групп + кнопки)
    - вспомогательные функции создания/сериализации записи группы
"""

import time

from PyQt6.QtCore import Qt, pyqtSignal, QRectF
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QListWidget,
    QListWidgetItem, QMenu, QInputDialog, QColorDialog, QMessageBox,
    QDialog, QLineEdit, QDialogButtonBox, QTabBar, QToolButton, QApplication,
)
from PyQt6.QtGui import QColor, QAction, QIcon, QPixmap, QFont, QBrush, QPainter, QDrag
from PyQt6.QtCore import QMimeData

from browser_constants import TAB_GROUP_COLORS


class GroupedTabBar(QTabBar):
    """QTabBar главной ленты вкладок браузера с визуальной группировкой в
    духе Firefox/Chrome: у вкладок одной группы под текстом рисуется цветная
    полоска (как подчёркивание группы в Firefox). В отличие от статьи в
    Mozilla, где сама группа - это временное состояние открытых вкладок,
    здесь группа ВСЕГДА привязана к сохранённой записи в tab_groups (см.
    GroupsPanel) - так фишка сохранения групп остаётся, просто вкладки,
    относящиеся к открытой сохранённой группе, теперь ещё и подсвечиваются.

    Требует свойство "gor_group_id" на QWebEngineView вкладки (см.
    GORBrowser.tag_tab_with_group) - выставляется автоматически при
    открытии сохранённой группы и вручную через контекстное меню вкладки."""

    STRIPE_HEIGHT = 3
    TAB_DRAG_MIME = "application/x-gor-tab-index"

    def __init__(self, parent_browser):
        super().__init__()
        self.parent_browser = parent_browser
        self._drag_start_pos = None
        self._drag_tab_index = None

    def _group_for_index(self, index):
        tabs = getattr(self.parent_browser, "tabs", None)
        if tabs is None:
            return None
        widget = tabs.widget(index)
        if not widget:
            return None
        group_id = widget.property("gor_group_id")
        if not group_id:
            return None
        return self.parent_browser.find_tab_group(group_id)

    def tabSizeHint(self, index):
        size = super().tabSizeHint(index)
        if self._group_for_index(index):
            size.setHeight(size.height() + self.STRIPE_HEIGHT)
        return size

    def paintEvent(self, event):
        super().paintEvent(event)
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setPen(Qt.PenStyle.NoPen)
        for i in range(self.count()):
            if not self.isTabVisible(i):
                continue
            group = self._group_for_index(i)
            if not group:
                continue
            rect = self.tabRect(i)
            stripe = QRectF(
                rect.left() + 6, rect.bottom() - self.STRIPE_HEIGHT - 2,
                rect.width() - 12, self.STRIPE_HEIGHT,
            )
            painter.setBrush(QBrush(QColor(group.get("color", "#4c6ef5"))))
            painter.drawRoundedRect(stripe, 1.5, 1.5)
        painter.end()

    # ------------------------------------------------------------------
    # Drag & Drop (пункт 6 ТЗ): перетаскивание вкладки из ленты на панель
    # "Группы" в сайдбаре, чтобы добавить её в группу без контекстного меню.
    # Обычное перетаскивание ВНУТРИ самой ленты (переупорядочивание вкладок)
    # Qt уже умеет из коробки через setMovable(True) - это не трогаем,
    # мы только ДОБАВЛЯЕМ вариант "перетащить наружу, на панель групп".
    # ------------------------------------------------------------------

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self._drag_start_pos = event.position().toPoint()
            self._drag_tab_index = self.tabAt(self._drag_start_pos)
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event):
        if (
            self._drag_tab_index is not None
            and event.buttons() & Qt.MouseButton.LeftButton
            and self._drag_start_pos is not None
            and (event.position().toPoint() - self._drag_start_pos).manhattanLength()
            > QApplication.startDragDistance()
        ):
            drag = QDrag(self)
            mime = QMimeData()
            mime.setData(self.TAB_DRAG_MIME, str(self._drag_tab_index).encode("utf-8"))
            drag.setMimeData(mime)
            drag.exec(Qt.DropAction.CopyAction)
            self._drag_tab_index = None
            return
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event):
        self._drag_tab_index = None
        self._drag_start_pos = None
        super().mouseReleaseEvent(event)


DEFAULT_GROUP_EMOJI = "🗂️"

# Быстрый набор эмодзи для окна редактирования группы (клик - подставляет
# значение в поле, как в Chrome при выборе иконки группы).
QUICK_GROUP_EMOJIS = ["🗂️", "🎮", "🛠️", "📚", "🎬", "🎵", "💻", "🧪", "🌐", "⭐", "🔥", "🧩"]


def group_emoji(group):
    """Эмодзи группы с фолбэком для записей, сохранённых до появления этого
    поля (старые JSON без ключа "emoji")."""
    return (group.get("emoji") or "").strip() or DEFAULT_GROUP_EMOJI


def group_display_name(group):
    """"Эмодзи + название" - единая точка форматирования подписи группы,
    используется и в панели групп, и в заголовках вкладок/групп в ленте."""
    return f"{group_emoji(group)} {group.get('name', '?')}"


def new_group_record(name, color, urls, emoji=None):
    """Собирает новую запись группы в едином формате (см. докстринг модуля)."""
    return {
        "id": f"grp_{int(time.time() * 1000)}",
        "name": name or "Без названия",
        "color": color or TAB_GROUP_COLORS[0],
        "emoji": (emoji or "").strip() or DEFAULT_GROUP_EMOJI,
        "urls": list(urls),
        "created": time.strftime("%Y-%m-%d %H:%M"),
    }


def _color_dot_icon(hex_color, size=14, open_marker=False):
    """Маленькая цветная точка-иконка для строки списка групп. Если
    open_marker=True - точка рисуется с белой обводкой, обозначая, что
    группа сейчас открыта в браузере (все её вкладки есть среди открытых)."""
    pixmap = QPixmap(size, size)
    pixmap.fill(Qt.GlobalColor.transparent)
    from PyQt6.QtGui import QPainter, QBrush as _QBrush, QPen
    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    painter.setBrush(_QBrush(QColor(hex_color)))
    if open_marker:
        painter.setPen(QPen(QColor("#ffffff"), 1.6))
    else:
        painter.setPen(Qt.PenStyle.NoPen)
    painter.drawEllipse(1, 1, size - 2, size - 2)
    painter.end()
    return QIcon(pixmap)


class GroupEditDialog(QDialog):
    """Единое окно редактирования группы: название, цвет, список URL
    (с возможностью удалить отдельную вкладку из группы или добавить
    в неё текущую активную вкладку браузера)."""

    def __init__(self, parent_browser, group):
        super().__init__(parent_browser)
        self.parent_browser = parent_browser
        self.group = group
        self._color = group.get("color", TAB_GROUP_COLORS[0])
        self._emoji = group_emoji(group)
        accent = parent_browser.settings.get("theme_color", "#4c6ef5")

        self.setWindowTitle("Редактировать группу")
        self.setMinimumWidth(420)
        self.setStyleSheet(f"""
            QDialog {{ background: #17181c; color: white; }}
            QLineEdit {{
                background: #1c1e23; color: white; padding: 9px 11px;
                border-radius: 8px; border: 1px solid #34363d;
            }}
            QLineEdit:focus {{ border: 1px solid {accent}; }}
            QListWidget {{
                background: #1c1e23; border-radius: 8px; border: 1px solid #2a2c31; padding: 4px;
            }}
            QListWidget::item {{ padding: 8px; border-radius: 6px; }}
            QListWidget::item:hover {{ background: #22242a; }}
            QLabel[muted="true"] {{ color: #8a8f99; font-size: 11.5px; font-weight: 600; }}
        """)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 18, 20, 18)
        layout.setSpacing(10)

        name_row = QHBoxLayout()
        name_col = QVBoxLayout()
        name_label = QLabel("Название")
        name_label.setProperty("muted", "true")
        name_col.addWidget(name_label)
        self.name_input = QLineEdit(group.get("name", ""))
        name_col.addWidget(self.name_input)
        name_row.addLayout(name_col, 1)

        emoji_col = QVBoxLayout()
        emoji_label = QLabel("Иконка")
        emoji_label.setProperty("muted", "true")
        emoji_col.addWidget(emoji_label)
        self.emoji_input = QLineEdit(self._emoji)
        self.emoji_input.setMaxLength(4)
        self.emoji_input.setFixedWidth(56)
        self.emoji_input.setAlignment(Qt.AlignmentFlag.AlignCenter)
        emoji_col.addWidget(self.emoji_input)
        name_row.addLayout(emoji_col)
        layout.addLayout(name_row)

        quick_row = QHBoxLayout()
        quick_row.setSpacing(4)
        for emoji in QUICK_GROUP_EMOJIS:
            btn = QPushButton(emoji)
            btn.setFixedSize(28, 28)
            btn.setStyleSheet(
                "QPushButton { background: #1c1e23; border-radius: 6px; border: 1px solid #2a2c31; }"
                "QPushButton:hover { border: 1px solid " + accent + "; }"
            )
            btn.clicked.connect(lambda checked=False, e=emoji: self.emoji_input.setText(e))
            quick_row.addWidget(btn)
        quick_row.addStretch()
        layout.addLayout(quick_row)

        color_row = QHBoxLayout()
        color_col = QVBoxLayout()
        color_label = QLabel("Цвет")
        color_label.setProperty("muted", "true")
        color_col.addWidget(color_label)
        self.btn_color = QPushButton("  Изменить цвет")
        self._update_color_btn()
        self.btn_color.clicked.connect(self.pick_color)
        color_col.addWidget(self.btn_color)
        color_row.addLayout(color_col)
        layout.addLayout(color_row)

        urls_label = QLabel(f"Вкладки в группе ({len(group.get('urls', []))})")
        urls_label.setProperty("muted", "true")
        layout.addWidget(urls_label)
        self.url_list = QListWidget()
        self.url_list.setMaximumHeight(160)
        for url in group.get("urls", []):
            self.url_list.addItem(QListWidgetItem(url))
        layout.addWidget(self.url_list)

        url_btn_row = QHBoxLayout()
        btn_add_current = QPushButton("+  Добавить текущую вкладку")
        btn_add_current.clicked.connect(self.add_current_tab)
        btn_remove = QPushButton("✕  Удалить выбранную")
        btn_remove.clicked.connect(self.remove_selected_url)
        url_btn_row.addWidget(btn_add_current)
        url_btn_row.addWidget(btn_remove)
        layout.addLayout(url_btn_row)

        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Save | QDialogButtonBox.StandardButton.Cancel)
        buttons.button(QDialogButtonBox.StandardButton.Save).setText("Сохранить")
        buttons.button(QDialogButtonBox.StandardButton.Cancel).setText("Отмена")
        buttons.accepted.connect(self.save_and_close)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def _update_color_btn(self):
        self.btn_color.setStyleSheet(
            f"background: {self._color}; color: white; padding: 9px 12px; "
            "border-radius: 8px; font-weight: 600; border: 2px solid rgba(255,255,255,40); text-align: left;"
        )

    def pick_color(self):
        color = QColorDialog.getColor(QColor(self._color), self)
        if color.isValid():
            self._color = color.name()
            self._update_color_btn()

    def add_current_tab(self):
        browser = self.parent_browser.tabs.currentWidget()
        if not browser:
            return
        url = browser.url().toString()
        if not url or "start_page.html" in url:
            QMessageBox.information(self, "GOR Browser", "Нечего добавлять - это стартовая страница.")
            return
        existing = [self.url_list.item(i).text() for i in range(self.url_list.count())]
        if url in existing:
            return
        self.url_list.addItem(QListWidgetItem(url))

    def remove_selected_url(self):
        for item in self.url_list.selectedItems():
            self.url_list.takeItem(self.url_list.row(item))

    def save_and_close(self):
        name = self.name_input.text().strip()
        if not name:
            QMessageBox.information(self, "GOR Browser", "Название группы не может быть пустым.")
            return
        urls = [self.url_list.item(i).text() for i in range(self.url_list.count())]
        if not urls:
            QMessageBox.information(self, "GOR Browser", "В группе должна остаться хотя бы одна вкладка.")
            return
        self.group["name"] = name
        self.group["color"] = self._color
        self.group["emoji"] = self.emoji_input.text().strip() or DEFAULT_GROUP_EMOJI
        self.group["urls"] = urls
        self.accept()


class GroupsPanel(QWidget):
    """Панель "Группы" для сайдбара GORBrowser (третья вкладка в
    sidebar_stack, рядом с "Закладки"/"История"). Использует
    parent_browser.tab_groups как единственный источник правды и вызывает
    его же методы сохранения/запуска групп.

    Группа считается "открытой прямо сейчас", если ВСЕ её URL присутствуют
    среди открытых (не инкогнито) вкладок браузера - это чисто наблюдаемое
    состояние (см. get_open_tab_urls в GORBrowser), а не отдельный флаг,
    поэтому индикатор всегда актуален и не может "рассинхронизироваться"."""

    open_group_requested = pyqtSignal(str)
    broadcast_group_requested = pyqtSignal(str)

    def __init__(self, parent_browser):
        super().__init__()
        self.parent_browser = parent_browser

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        toolbar = QHBoxLayout()
        toolbar.setContentsMargins(8, 6, 8, 6)
        btn_save_session = QPushButton("💾 Сохранить текущую сессию")
        btn_save_session.setObjectName("SidebarFilter")
        btn_save_session.clicked.connect(self.save_current_session)
        toolbar.addWidget(btn_save_session)
        layout.addLayout(toolbar)

        self.list = QListWidget(objectName="GroupsList")
        self.list.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.list.customContextMenuRequested.connect(self.show_group_menu)
        self.list.itemDoubleClicked.connect(self.on_item_double_clicked)
        # Drag & Drop (пункт 6 ТЗ): принимаем вкладку, перетащенную из ленты
        # (см. GroupedTabBar выше) - drop на строку группы добавляет эту
        # вкладку в группу.
        self.list.setAcceptDrops(True)
        self.list.dragEnterEvent = self._drag_enter_event
        self.list.dragMoveEvent = self._drag_move_event
        self.list.dropEvent = self._drop_event
        layout.addWidget(self.list, 1)

        self.refresh()

    def _drag_enter_event(self, event):
        if event.mimeData().hasFormat(GroupedTabBar.TAB_DRAG_MIME):
            event.acceptProposedAction()
        else:
            event.ignore()

    def _drag_move_event(self, event):
        if event.mimeData().hasFormat(GroupedTabBar.TAB_DRAG_MIME):
            event.acceptProposedAction()
        else:
            event.ignore()

    def _drop_event(self, event):
        mime = event.mimeData()
        if not mime.hasFormat(GroupedTabBar.TAB_DRAG_MIME):
            event.ignore()
            return
        item = self.list.itemAt(event.position().toPoint())
        if item is None:
            event.ignore()
            return
        group_id = item.data(Qt.ItemDataRole.UserRole)
        if not group_id:
            event.ignore()
            return
        try:
            tab_index = int(bytes(mime.data(GroupedTabBar.TAB_DRAG_MIME)).decode("utf-8"))
        except (ValueError, UnicodeDecodeError):
            event.ignore()
            return
        self.parent_browser.add_tab_to_group(tab_index, group_id)
        self.refresh()
        event.acceptProposedAction()

    # ------------------------------------------------------------------

    def refresh(self):
        self.list.clear()
        groups = self.parent_browser.tab_groups
        if not groups:
            placeholder = QListWidgetItem("Пока нет сохранённых групп")
            placeholder.setFlags(Qt.ItemFlag.NoItemFlags)
            self.list.addItem(placeholder)
            return

        open_urls = set(self.parent_browser.get_open_tab_urls())

        for group in groups:
            urls = group.get("urls", [])
            count = len(urls)
            is_open = bool(urls) and set(urls).issubset(open_urls)
            group_id = group.get("id")

            item = QListWidgetItem()
            item.setData(Qt.ItemDataRole.UserRole, group_id)
            item.setToolTip("Двойной клик - открыть все вкладки группы. Перетащите вкладку сюда, чтобы добавить её в группу.")
            self.list.addItem(item)

            # Кнопка-сворачиватель (пункт 6 ТЗ): показываем/скрываем вкладки
            # группы В ОДИН КЛИК прямо в строке списка, без контекстного
            # меню - доступна только когда группа реально открыта в
            # браузере (иначе сворачивать нечего).
            row = QWidget()
            row_layout = QHBoxLayout(row)
            row_layout.setContentsMargins(10, 6, 6, 6)
            row_layout.setSpacing(6)

            icon_label = QLabel()
            icon_label.setPixmap(_color_dot_icon(group.get("color", "#4c6ef5"), open_marker=is_open).pixmap(14, 14))
            row_layout.addWidget(icon_label)

            text = f"{group_display_name(group)}  ·  {count} вкл."
            if is_open:
                text += "   ●  Открыта"
            text_label = QLabel(text)
            if is_open:
                bold_font = text_label.font()
                bold_font.setBold(True)
                text_label.setFont(bold_font)
            row_layout.addWidget(text_label, 1)

            if is_open:
                is_collapsed = group_id in self.parent_browser.collapsed_group_ids
                btn_collapse = QToolButton()
                btn_collapse.setText("👁️" if is_collapsed else "🙈")
                btn_collapse.setToolTip("Показать вкладки группы" if is_collapsed else "Свернуть вкладки группы")
                btn_collapse.setAutoRaise(True)
                btn_collapse.clicked.connect(lambda checked=False, gid=group_id: self._toggle_collapse(gid))
                row_layout.addWidget(btn_collapse)

                tint = QColor(group.get("color", "#4c6ef5"))
                row.setStyleSheet(
                    f"background: rgba({tint.red()}, {tint.green()}, {tint.blue()}, 35);"
                )

            item.setSizeHint(row.sizeHint())
            self.list.setItemWidget(item, row)

    def _toggle_collapse(self, group_id):
        """Кнопка-сворачиватель в строке списка - без контекстного меню."""
        self.parent_browser.toggle_group_collapse(group_id)
        self.refresh()

    def on_item_double_clicked(self, item):
        group_id = item.data(Qt.ItemDataRole.UserRole)
        if group_id:
            self.open_group_requested.emit(group_id)

    def save_current_session(self):
        """Собирает URL всех открытых (не инкогнито) вкладок в новую
        группу - "Broadcast сохранённой группы" из release notes работает
        именно с такими группами."""
        browser = self.parent_browser
        urls = browser.get_open_tab_urls()
        if not urls:
            QMessageBox.information(self, "GOR Browser", "Нет открытых вкладок для сохранения (кроме стартовой страницы).")
            return

        name, ok = QInputDialog.getText(self, "Новая группа", "Название группы (например, «Код», «Игры», «Учёба»):")
        if not ok or not name.strip():
            return
        color, ok2 = self._pick_color()
        if not ok2:
            color = TAB_GROUP_COLORS[len(browser.tab_groups) % len(TAB_GROUP_COLORS)]
        emoji, _ = QInputDialog.getText(
            self, "Иконка группы", "Эмодзи для группы (необязательно):", text=DEFAULT_GROUP_EMOJI,
        )

        group = new_group_record(name.strip(), color, urls, emoji=emoji)
        browser.tab_groups.append(group)
        browser.save_tab_groups()
        self.refresh()

    def _pick_color(self):
        dlg = QColorDialog(QColor(TAB_GROUP_COLORS[0]), self)
        if dlg.exec():
            return dlg.selectedColor().name(), True
        return None, False

    def show_group_menu(self, pos):
        item = self.list.itemAt(pos)
        if not item:
            return
        group_id = item.data(Qt.ItemDataRole.UserRole)
        if not group_id:
            return

        menu = QMenu(self)
        act_open = QAction("▶️  Открыть все вкладки группы", self)
        act_open.triggered.connect(lambda: self.open_group_requested.emit(group_id))
        act_broadcast = QAction("📡  Отправить группу в сеть (LAN Broadcast)", self)
        act_broadcast.triggered.connect(lambda: self.broadcast_group_requested.emit(group_id))
        act_edit = QAction("✏️  Редактировать группу", self)
        act_edit.triggered.connect(lambda: self.edit_group(group_id))
        act_delete = QAction("🗑️  Удалить группу", self)
        act_delete.triggered.connect(lambda: self.delete_group(group_id))

        menu.addAction(act_open)
        menu.addAction(act_broadcast)
        menu.addSeparator()
        menu.addAction(act_edit)
        menu.addAction(act_delete)
        menu.exec(self.list.mapToGlobal(pos))

    def _find_group(self, group_id):
        for g in self.parent_browser.tab_groups:
            if g.get("id") == group_id:
                return g
        return None

    def edit_group(self, group_id):
        """Открывает единое окно редактирования (название + цвет + список
        вкладок) - см. GroupEditDialog."""
        group = self._find_group(group_id)
        if not group:
            return
        dlg = GroupEditDialog(self.parent_browser, dict(group))
        if dlg.exec():
            group["name"] = dlg.group["name"]
            group["color"] = dlg.group["color"]
            group["urls"] = dlg.group["urls"]
            self.parent_browser.save_tab_groups()
            self.refresh()

    def delete_group(self, group_id):
        group = self._find_group(group_id)
        if not group:
            return
        reply = QMessageBox.question(
            self, "Удалить группу",
            f"Удалить группу «{group.get('name')}»? Вкладки не закроются, удалится только сохранённый список.",
        )
        if reply == QMessageBox.StandardButton.Yes:
            self.parent_browser.tab_groups = [g for g in self.parent_browser.tab_groups if g.get("id") != group_id]
            self.parent_browser.save_tab_groups()
            self.refresh()
