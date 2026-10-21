"""
Кастомизация интерфейса лаунчера из аддонов (api.ui).

Всё, что создано через эти методы, запоминается и убирается при
выключении аддона. Если нужно больше - у аддона всегда есть полный
доступ к api.launcher и ко всему Qt.
"""

from .themes import themes
from .ui_extra import UIExtraMixin


def _destroy(widget):
    """Немедленно убрать виджет из интерфейса и удалить."""
    try:
        widget.hide()
        widget.setParent(None)
        widget.deleteLater()
    except RuntimeError:
        pass   # C++-объект уже удалён


class UIAPI(UIExtraMixin):
    def __init__(self, api):
        self._api = api
        self._res = api._resources
        self.launcher = api.launcher

    # ------------------------------ вкладки ------------------------------ #
    @property
    def tabs(self):
        """Главный QTabWidget лаунчера."""
        return self.launcher.tabs

    def add_tab(self, widget, title, icon=None, index=None, closable=False):
        """Добавить вкладку в главное окно. Возвращает widget."""
        tabs = self.tabs
        if index is None:
            idx = tabs.addTab(widget, title)
        else:
            idx = tabs.insertTab(index, widget, title)
        if icon is not None:
            tabs.setTabIcon(idx, icon)

        def undo():
            i = tabs.indexOf(widget)
            if i != -1:
                tabs.removeTab(i)
            _destroy(widget)
        self._res.add(undo)
        return widget

    def find_tab(self, title):
        """Индекс вкладки по её заголовку (или -1)."""
        for i in range(self.tabs.count()):
            if self.tabs.tabText(i) == title:
                return i
        return -1

    def rename_tab(self, title, new_title):
        i = self.find_tab(title)
        if i != -1:
            self.tabs.setTabText(i, new_title)
            self._res.add(lambda i=i, t=title: self.tabs.setTabText(i, t)
                          if i < self.tabs.count() else None)
        return i != -1

    def hide_tab(self, title, hidden=True):
        """Спрятать/показать любую вкладку лаунчера."""
        i = self.find_tab(title)
        if i != -1:
            self.tabs.setTabVisible(i, not hidden)
            self._res.add(lambda i=i: self.tabs.setTabVisible(i, True)
                          if i < self.tabs.count() else None)
        return i != -1

    def select_tab(self, widget_or_title):
        i = (self.tabs.indexOf(widget_or_title) if not isinstance(widget_or_title, str)
             else self.find_tab(widget_or_title))
        if i != -1:
            self.tabs.setCurrentIndex(i)

    # ---------------------------- кнопки в шапке --------------------------- #
    def _header_layout(self):
        L = self.launcher
        return (L.header_bar.layout() if hasattr(L, "header_bar")
                else L.main_lay.itemAt(0).layout())

    def add_header_button(self, text, callback, tooltip=None, object_name=None,
                          size=38, position=None):
        """Кнопка в шапке лаунчера (рядом с 🔄 и бургер-меню).
        position: индекс в шапке; по умолчанию - перед бургер-меню."""
        from PyQt6.QtWidgets import QPushButton
        from PyQt6.QtCore import Qt
        btn = QPushButton(text)
        if object_name:
            btn.setObjectName(object_name)
        if tooltip:
            btn.setToolTip(tooltip)
        if size:
            btn.setFixedSize(size, size)
        btn.setCursor(Qt.CursorShape.PointingHandCursor)
        btn.clicked.connect(lambda *_: callback())
        lay = self._header_layout()
        burger = getattr(self.launcher, "burger_btn", None)
        if position is not None:
            lay.insertWidget(position, btn)
        elif burger is not None and lay.indexOf(burger) != -1:
            lay.insertWidget(lay.indexOf(burger), btn)
        else:
            lay.addWidget(btn)

        def undo():
            lay.removeWidget(btn)
            _destroy(btn)
        self._res.add(undo)
        return btn

    def add_burger_action(self, text, callback, separator_before=False):
        """Пункт в бургер-меню (☰)."""
        menu = self.launcher.burger_btn.menu()
        if separator_before:
            sep = menu.addSeparator()
            self._res.add(lambda: menu.removeAction(sep))
        act = menu.addAction(text)
        act.triggered.connect(lambda *_: callback())
        self._res.add(lambda: menu.removeAction(act))
        return act

    # -------------------------- меню карточки игры ------------------------- #
    def add_card_action(self, text, callback, separator_before=True):
        """Пункт в контекстном меню карточки игры. callback(game_data)."""
        from .events import Events

        def on_menu(menu, game_data, card=None):
            if separator_before:
                menu.addSeparator()
            act = menu.addAction(text)
            act.triggered.connect(lambda *_: callback(game_data))
        self._api.on(Events.GAME_CARD_MENU, on_menu)

    # ------------------------------- окно --------------------------------- #
    def set_window_title(self, title):
        old = self.launcher.windowTitle()
        self.launcher.setWindowTitle(title)
        self._res.add(lambda: self.launcher.setWindowTitle(old))

    def set_window_icon(self, path):
        from PyQt6.QtGui import QIcon
        old = self.launcher.windowIcon()
        self.launcher.setWindowIcon(QIcon(path))
        self._res.add(lambda: self.launcher.setWindowIcon(old))

    # ------------------------------ стили --------------------------------- #
    def add_style(self, qss):
        """Добавить QSS ко всему лаунчеру. В qss работают {{accent}}, {{bg}}...
        Убирается при выключении аддона."""
        item = themes.add_snippet(self._api.root, qss)
        self._res.add(lambda: themes.remove_snippet(item))
        return item

    def set_widget_style(self, widget, qss):
        """Стиль конкретного виджета (с откатом)."""
        old = widget.styleSheet()
        widget.setStyleSheet(qss)
        self._res.add(lambda: widget.setStyleSheet(old))

    # ------------------------- поиск и вставка виджетов -------------------- #
    def find(self, object_name, cls=None):
        """Найти виджет лаунчера по objectName (и, при желании, по классу)."""
        from PyQt6.QtWidgets import QWidget
        return self.launcher.findChild(cls or QWidget, object_name)

    def insert(self, container, widget, index=None):
        """Вставить виджет в layout контейнера (виджет или имя из find)."""
        if isinstance(container, str):
            container = self.find(container)
        lay = container.layout() if hasattr(container, "layout") and callable(container.layout) else container
        if index is None:
            lay.addWidget(widget)
        else:
            lay.insertWidget(index, widget)

        def undo():
            lay.removeWidget(widget)
            _destroy(widget)
        self._res.add(undo)
        return widget

    # ------------------------------ уведомления --------------------------- #
    def toast(self, text, ms=3000):
        """Всплывающая плашка поверх окна лаунчера (в правом нижнем углу)."""
        from PyQt6.QtWidgets import QLabel
        from PyQt6.QtCore import Qt, QTimer
        c = themes.colors()
        lbl = QLabel(text, self.launcher)
        lbl.setWordWrap(True)
        lbl.setMaximumWidth(340)
        lbl.setStyleSheet(
            "QLabel { background: %s; color: %s; border: 1px solid %s;"
            " border-radius: 10px; padding: 12px 16px; font-size: 13px; }"
            % (c["surface"], c["text"], c["accent"]))
        lbl.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        lbl.adjustSize()
        lbl.move(self.launcher.width() - lbl.width() - 20,
                 self.launcher.height() - lbl.height() - 20)
        lbl.show()
        lbl.raise_()
        QTimer.singleShot(ms, lbl.deleteLater)
        return lbl
