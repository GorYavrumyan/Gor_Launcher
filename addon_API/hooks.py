"""
Перехватчики: аддон может ВМЕШАТЬСЯ в действия лаунчера, а не только слушать.

  api.before("before_game_launch", fn)   - fn(game) вернёт False -> запуск ОТМЕНЁН
  api.filter("game_launch_args", fn)     - fn(value, game) вернёт новое значение

Встроенные точки (их вызывает сам лаунчер):
  before_game_launch(game)           -> False отменяет запуск игры
  game_launch_args(args, game)       -> можно дописать/изменить аргументы запуска

Свои точки можно делать в любом аддоне:
    if api.allow("my_action", data): ...        # спросить у всех, можно ли
    value = api.apply("my_filter", value, ctx)  # пропустить значение через фильтры
Ошибка в обработчике не ломает действие: пишется в лог аддона и игнорируется.
"""

import traceback

from .events import _log


class _Hook:
    __slots__ = ("name", "cb", "owner", "priority")

    def __init__(self, name, cb, owner, priority):
        self.name, self.cb, self.owner, self.priority = name, cb, owner, priority


class HookBus:
    def __init__(self):
        self._before = {}
        self._filters = {}

    @staticmethod
    def _add(table, name, cb, owner, priority):
        h = _Hook(name, cb, owner, priority)
        lst = table.setdefault(name, [])
        lst.append(h)
        lst.sort(key=lambda x: -x.priority)
        return h

    def before(self, name, cb, owner=None, priority=0):
        return self._add(self._before, name, cb, owner, priority)

    def filter(self, name, cb, owner=None, priority=0):
        return self._add(self._filters, name, cb, owner, priority)

    def remove(self, hook):
        for table in (self._before, self._filters):
            lst = table.get(hook.name, [])
            if hook in lst:
                lst.remove(hook)

    def remove_owner(self, owner):
        for table in (self._before, self._filters):
            for lst in table.values():
                lst[:] = [h for h in lst if h.owner != owner]

    def allow(self, name, *args, **kwargs):
        """False, если хотя бы один обработчик вернул False."""
        for h in list(self._before.get(name, [])):
            try:
                if h.cb(*args, **kwargs) is False:
                    return False
            except Exception as e:
                traceback.print_exc()
                _log(h.owner, "error", f"Ошибка в перехватчике '{name}': {e}")
        return True

    def apply(self, name, value, *args, **kwargs):
        for h in list(self._filters.get(name, [])):
            try:
                out = h.cb(value, *args, **kwargs)
                if out is not None:
                    value = out
            except Exception as e:
                traceback.print_exc()
                _log(h.owner, "error", f"Ошибка в фильтре '{name}': {e}")
        return value


hooks = HookBus()


def allow(name, *args, **kwargs):
    """Вызывается из кода ЛАУНЧЕРА. Никогда не бросает исключений."""
    try:
        return hooks.allow(name, *args, **kwargs)
    except Exception:
        traceback.print_exc()
        return True


def apply_filter(name, value, *args, **kwargs):
    try:
        return hooks.apply(name, value, *args, **kwargs)
    except Exception:
        traceback.print_exc()
        return value
