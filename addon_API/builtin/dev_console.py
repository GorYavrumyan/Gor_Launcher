"""
Консоль разработчика (Ctrl+`): живой Python прямо внутри лаунчера.
В ней уже есть: launcher, api, d (api.design), games, themes, app, manager, A(id) - api другого аддона.
Можно менять что угодно «на лету»: d.preset("neon"), games.launch("Hades"), launcher.tabs.count() ...
Это ваш собственный Python с полным доступом - не вставляйте сюда чужой код, которому не доверяете.
"""

import io
import code
import contextlib
import traceback

from PyQt6.QtCore import Qt, QEvent
from PyQt6.QtGui import QFont, QTextCursor
from PyQt6.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QPlainTextEdit, QLineEdit,
                             QLabel, QPushButton, QApplication, QFileDialog)

from addon_API import AddonBase

HELP = """Консоль лаунчера. Доступно:
  launcher   - главное окно          api    - API этой консоли
  d          - api.design            games  - api.games (игры)
  themes     - менеджер тем          app    - QApplication
  manager    - загрузчик аддонов     A(id)  - api другого аддона
  Qt         - модули PyQt6 (Qt.QtWidgets, Qt.QtCore, Qt.QtGui)
Примеры:  d.preset('neon')   games.search('half')   launcher.tabs.count()
          d.particles('snow', 80)   api.toast('привет')   print(d.object_names())
Многострочный код вводится как в обычной консоли Python (пустая строка завершает блок).
Кнопка «Скрипт…» выполняет .py файл.  Стрелки ↑↓ - история.   clear() - очистить вывод."""


class ConsoleDialog(QDialog):
    def __init__(self, api):
        super().__init__(api.launcher)
        self.api = api
        self.setWindowTitle("📟 Консоль лаунчера")
        self.resize(780, 520)
        import PyQt6.QtWidgets, PyQt6.QtCore, PyQt6.QtGui
        from addon_API import theme_manager, manager

        class _Qt:
            QtWidgets, QtCore, QtGui = PyQt6.QtWidgets, PyQt6.QtCore, PyQt6.QtGui
        ns = {"launcher": api.launcher, "api": api, "d": api.design, "games": api.games,
              "themes": theme_manager, "app": QApplication.instance(), "manager": manager,
              "A": api.addons.api_of, "Qt": _Qt, "clear": self._clear, "help": lambda: print(HELP)}
        self.interp = code.InteractiveConsole(ns)
        self.history, self.hpos, self.more = [], 0, False

        lay = QVBoxLayout(self)
        self.out = QPlainTextEdit()
        self.out.setReadOnly(True)
        f = QFont("Consolas")
        f.setStyleHint(QFont.StyleHint.Monospace)
        f.setPointSize(10)
        self.out.setFont(f)
        row = QHBoxLayout()
        self.prompt = QLabel(">>>")
        self.prompt.setFont(f)
        self.inp = QLineEdit()
        self.inp.setFont(f)
        self.inp.returnPressed.connect(self.run_line)
        self.inp.installEventFilter(self)
        btn = QPushButton("Скрипт…")
        btn.clicked.connect(self.run_script)
        row.addWidget(self.prompt)
        row.addWidget(self.inp, 1)
        row.addWidget(btn)
        lay.addWidget(self.out, 1)
        lay.addLayout(row)
        self.write("GOR Launcher · консоль разработчика. help() — подсказка.\n")

    def write(self, text):
        self.out.moveCursor(QTextCursor.MoveOperation.End)
        self.out.insertPlainText(text)
        self.out.moveCursor(QTextCursor.MoveOperation.End)

    def _clear(self):
        self.out.clear()

    def eventFilter(self, obj, ev):
        if obj is self.inp and ev.type() == QEvent.Type.KeyPress and self.history:
            if ev.key() == Qt.Key.Key_Up:
                self.hpos = max(0, self.hpos - 1)
                self.inp.setText(self.history[self.hpos])
                return True
            if ev.key() == Qt.Key.Key_Down:
                self.hpos = min(len(self.history), self.hpos + 1)
                self.inp.setText(self.history[self.hpos] if self.hpos < len(self.history) else "")
                return True
        return False

    def execute(self, line):
        """Выполнить одну строку как в REPL. Возвращает True, если нужен ввод продолжения."""
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf), contextlib.redirect_stderr(buf):
            try:
                more = self.interp.push(line)
            except Exception:
                traceback.print_exc()
                more = False
        text = buf.getvalue()
        if text:
            self.write(text if text.endswith("\n") else text + "\n")
        return more

    def run_line(self):
        line = self.inp.text()
        self.inp.clear()
        self.write(f"{self.prompt.text()} {line}\n")
        if line.strip():
            self.history.append(line)
        self.hpos = len(self.history)
        self.more = self.execute(line)
        self.prompt.setText("..." if self.more else ">>>")

    def run_script(self):
        path, _ = QFileDialog.getOpenFileName(self, "Скрипт Python", "", "Python (*.py)")
        if not path:
            return
        self.write(f">>> exec({path!r})\n")
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf), contextlib.redirect_stderr(buf):
            try:
                with open(path, "r", encoding="utf-8") as f:
                    exec(compile(f.read(), path, "exec"), self.interp.locals)
            except Exception:
                traceback.print_exc()
        self.write(buf.getvalue())


class Addon(AddonBase):
    def on_load(self, api):
        self.dialog = None

        def open_console():
            if self.dialog is None:
                self.dialog = ConsoleDialog(api)
            self.dialog.show()
            self.dialog.raise_()
            self.dialog.inp.setFocus()
        self.open_console = open_console
        api.keys.bind("Ctrl+`", open_console, context="application")
        api.commands.register("console", "Консоль разработчика (Python)", open_console,
                              keywords="python repl скрипт отладка", icon="📟", group="Разработка")
        api.ui.add_burger_action("📟 Консоль разработчика (Ctrl+`)", open_console)

    def on_unload(self):
        if self.dialog is not None:
            self.dialog.close()
            self.dialog.deleteLater()
