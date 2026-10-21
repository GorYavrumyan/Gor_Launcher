"""
api.keys - горячие клавиши внутри окна лаунчера.

    api.keys.bind("Ctrl+K", lambda: ...)
    api.keys.bind("F5", fn, context="application")   # работает в любом окне лаунчера (диалоги тоже)
    api.keys.bind("Space", fire, widget=my_canvas)    # только когда фокус в этом виджете

Системные (глобальные) хоткеи, работающие когда лаунчер не в фокусе, Qt не даёт -
для них нужна платформенная библиотека.
"""

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QKeySequence, QShortcut

_CONTEXT = {"window": Qt.ShortcutContext.WindowShortcut,
            "application": Qt.ShortcutContext.ApplicationShortcut,
            "widget": Qt.ShortcutContext.WidgetShortcut,
            "children": Qt.ShortcutContext.WidgetWithChildrenShortcut}


class KeysAPI:
    def __init__(self, api):
        self._api = api
        self._shortcuts = []

    def bind(self, sequence, fn, widget=None, context="window"):
        """Назначить горячую клавишу. Возвращает QShortcut."""
        sc = QShortcut(QKeySequence(sequence), widget or self._api.launcher)
        sc.setContext(_CONTEXT.get(context, Qt.ShortcutContext.WindowShortcut))
        sc.activated.connect(lambda: self._call(fn, sequence))
        self._shortcuts.append(sc)

        def undo():
            sc.setEnabled(False)
            sc.deleteLater()
        self._api._resources.add(undo)
        return sc

    def _call(self, fn, seq):
        try:
            fn()
        except Exception as e:
            import traceback
            traceback.print_exc()
            self._api.log(f"Ошибка в горячей клавише {seq}: {e}", "error")

    def unbind(self, shortcut):
        shortcut.setEnabled(False)
        shortcut.deleteLater()
        if shortcut in self._shortcuts:
            self._shortcuts.remove(shortcut)

    @staticmethod
    def name(event):
        """Читаемое имя нажатой клавиши из QKeyEvent: 'Ctrl+Shift+A'."""
        return QKeySequence(event.keyCombination()).toString()
