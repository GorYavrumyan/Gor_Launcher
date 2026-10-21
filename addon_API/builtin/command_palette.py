"""
Палитра команд (Ctrl+K): поиск и запуск чего угодно - игр, тем, стилей, вкладок,
команд любых аддонов. Написана через публичный addon_API.
"""

from PyQt6.QtCore import Qt, QEvent, QTimer
from PyQt6.QtWidgets import QDialog, QVBoxLayout, QLineEdit, QListWidget, QListWidgetItem, QLabel

from addon_API import AddonBase


class PaletteDialog(QDialog):
    def __init__(self, api, parent):
        super().__init__(parent, Qt.WindowType.Dialog | Qt.WindowType.FramelessWindowHint)
        self.api = api
        self.setModal(True)
        self.setMinimumWidth(620)
        lay = QVBoxLayout(self)
        lay.setContentsMargins(14, 14, 14, 14)
        self.hint = QLabel("Начните вводить: игра, тема, стиль, вкладка, команда…   (Esc — закрыть)")
        self.hint.setObjectName("PaletteHint")
        self.edit = QLineEdit()
        self.edit.setPlaceholderText("🔍  Что сделать?")
        self.edit.setMinimumHeight(40)
        self.list = QListWidget()
        self.list.setMinimumHeight(320)
        lay.addWidget(self.hint)
        lay.addWidget(self.edit)
        lay.addWidget(self.list)
        self.edit.textChanged.connect(self.refill)
        self.edit.installEventFilter(self)
        self.list.itemActivated.connect(lambda it: self.run_item(it))
        self.list.itemClicked.connect(lambda it: self.run_item(it))
        self.results = []

    def open_at_top(self):
        g = self.parent().geometry()
        self.resize(640, 440)
        self.move(g.center().x() - self.width() // 2, g.top() + 70)
        self.edit.clear()
        self.refill("")
        self.show()
        self.edit.setFocus()

    def refill(self, text=""):
        self.results = self.api.commands.search(text if isinstance(text, str) else self.edit.text(), limit=60)
        self.list.clear()
        for c in self.results:
            line = f"{c.get('icon') + '  ' if c.get('icon') else ''}{c['title']}"
            if c.get("group"):
                line += f"      · {c['group']}"
            self.list.addItem(QListWidgetItem(line))
        if self.results:
            self.list.setCurrentRow(0)

    def eventFilter(self, obj, ev):
        if obj is self.edit and ev.type() == QEvent.Type.KeyPress:
            k = ev.key()
            n = self.list.count()
            row = self.list.currentRow()
            if k == Qt.Key.Key_Down and n:
                self.list.setCurrentRow(min(n - 1, row + 1))
                return True
            if k == Qt.Key.Key_Up and n:
                self.list.setCurrentRow(max(0, row - 1))
                return True
            if k in (Qt.Key.Key_Return, Qt.Key.Key_Enter) and n:
                self.run_item(self.list.currentItem())
                return True
            if k == Qt.Key.Key_Escape:
                self.close()
                return True
        return False

    def run_item(self, item):
        if item is None:
            return
        cmd = self.results[self.list.row(item)]
        self.close()
        QTimer.singleShot(0, lambda: self.api._safe(cmd["fn"])())


class Addon(AddonBase):
    def on_load(self, api):
        self.api = api
        self.dialog = None
        c = api.commands

        # ---- общие команды лаунчера ----
        c.register("random_game", "Запустить случайную игру", lambda: self._random(False),
                   keywords="рандом случайная играть", icon="🎲", group="Игры")
        c.register("random_fav", "Запустить случайную из избранного", lambda: self._random(True),
                   keywords="рандом избранное", icon="⭐", group="Игры")
        c.register("refresh", "Обновить список игр", api.games.refresh, icon="🔄", group="Лаунчер")
        c.register("inspector", "Инспектор элементов (Ctrl+Shift+клик)", lambda: api.design.inspector(True),
                   keywords="селектор qss отладка", icon="🔍", group="Дизайн")
        c.register("screenshot", "Сделать скриншот лаунчера", self._shot, icon="📸", group="Лаунчер")

        # ---- динамические списки ----
        c.provider(self._themes)
        c.provider(self._presets)
        c.provider(self._tabs)
        c.provider(self._games)
        c.provider(self._addons)

        api.keys.bind("Ctrl+K", self.open, context="application")
        api.ui.add_burger_action("⌨ Палитра команд (Ctrl+K)", self.open, separator_before=False)

    # ---------------- провайдеры ----------------
    def _themes(self, q):
        from addon_API import theme_manager
        cur = theme_manager.current_id()
        return [{"title": f"Тема: {t['name']}" + ("  ✔" if t["id"] == cur else ""), "icon": "🎨",
                 "group": "Оформление", "fn": lambda i=t["id"]: theme_manager.apply(i)}
                for t in theme_manager.list()]

    def _presets(self, q):
        d = self.api.design
        return [{"title": f"Стиль: {n} — {desc}", "icon": "✨", "group": "Оформление",
                 "fn": lambda n=n: d.preset(n)} for n, desc in d.preset_info().items()]

    def _tabs(self, q):
        tabs = self.api.launcher.tabs
        return [{"title": f"Вкладка: {tabs.tabText(i)}", "icon": "📑", "group": "Навигация",
                 "fn": lambda i=i: tabs.setCurrentIndex(i)} for i in range(tabs.count())]

    def _games(self, q):
        if not q.strip():
            return []
        g = self.api.games
        out = []
        for game in g.search(q)[:8]:
            if g.is_running(game):
                out.append({"title": f"Остановить: {game['name']}", "icon": "⏹", "group": "Игры",
                            "fn": lambda game=game: g.stop(game)})
            else:
                out.append({"title": f"Запустить: {game['name']}", "icon": "▶", "group": "Игры",
                            "fn": lambda game=game: g.launch(game)})
        return out

    def _addons(self, q):
        if not q.strip():
            return []
        return [{"title": f"Перезагрузить аддон: {self.api.addons.info(a)['name']}", "icon": "🧩",
                 "group": "Аддоны", "fn": lambda a=a: self.api.addons.reload(a)}
                for a in self.api.addons.list(include_builtin=False)]

    # ---------------- действия ----------------
    def _random(self, fav):
        g = self.api.games.launch_random(favorites_only=fav)
        self.api.toast(f"🎲 {g['name']}" if g else "Подходящих игр не нашлось")

    def _shot(self):
        path = self.api.design.screenshot()
        self.api.toast("📸 Сохранено: " + path, 4000)

    def open(self):
        if self.dialog is None:
            self.dialog = PaletteDialog(self.api, self.api.launcher)
        self.dialog.open_at_top()

    def on_unload(self):
        if self.dialog is not None:
            self.dialog.close()
            self.dialog.deleteLater()
