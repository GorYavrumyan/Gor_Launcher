"""
Учёт ресурсов аддона: всё, что аддон создал через API (вкладки, кнопки,
подписки, таймеры, стили), запоминается и откатывается при выключении
аддона. Благодаря этому аддон можно выгрузить без перезапуска лаунчера.
"""

import traceback


class Resources:
    def __init__(self):
        self._undo = []

    def add(self, undo_fn):
        """Регистрирует функцию отката. Возвращает её же."""
        self._undo.append(undo_fn)
        return undo_fn

    def discard(self, undo_fn):
        """Убрать функцию отката (если ресурс уже освобождён сам)."""
        try:
            self._undo.remove(undo_fn)
        except ValueError:
            pass

    def cleanup(self):
        # откат в обратном порядке создания
        while self._undo:
            fn = self._undo.pop()
            try:
                fn()
            except Exception:
                traceback.print_exc()
