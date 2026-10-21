"""
Шина событий GOR Launcher.

Лаунчер выбрасывает события (emit_event), аддоны подписываются (api.on).
Ошибка в обработчике НЕ роняет лаунчер: она пишется в лог аддона, а после
MAX_CONSECUTIVE_ERRORS ошибок подряд обработчик отключается сам.
"""

import time
import traceback

MAX_CONSECUTIVE_ERRORS = 5


class Events:
    """Имена встроенных событий (можно использовать вместо строк)."""
    ADDONS_LOADED = "addons_loaded"        # () все аддоны загружены
    GAME_STARTED = "game_started"          # (game_data)
    GAME_FINISHED = "game_finished"        # (duration_sec, game_data)
    GAME_CARD_MENU = "game_card_menu"      # (menu, game_data, card) - добавь свои пункты
    LAUNCHER_CLOSING = "launcher_closing"  # ()
    THEME_CHANGED = "theme_changed"        # (theme_id)
    ADDON_LOADED = "addon_loaded"          # (folder)
    ADDON_UNLOADED = "addon_unloaded"      # (folder)
    LIBRARY_REFRESHED = "library_refreshed"  # () список игр перерисован
    GAME_ADDED = "game_added"              # (game)
    GAME_REMOVED = "game_removed"          # (game)
    GAME_UPDATED = "game_updated"          # (game, changes)
    GAME_MOVED = "game_moved"              # (game, group)
    GROUP_CREATED = "group_created"        # (name)
    GROUP_REMOVED = "group_removed"        # (name)
    GROUP_RENAMED = "group_renamed"        # (old, new)


class _Sub:
    __slots__ = ("event", "callback", "owner", "priority", "once",
                 "errors", "calls", "seconds")

    def __init__(self, event, callback, owner, priority, once):
        self.event, self.callback, self.owner = event, callback, owner
        self.priority, self.once = priority, once
        self.errors = self.calls = 0
        self.seconds = 0.0


class EventBus:
    def __init__(self):
        self._subs = {}

    def subscribe(self, event, callback, owner=None, priority=0, once=False):
        sub = _Sub(event, callback, owner, priority, once)
        lst = self._subs.setdefault(event, [])
        lst.append(sub)
        lst.sort(key=lambda s: -s.priority)   # больший priority - раньше
        return sub

    def unsubscribe(self, sub):
        lst = self._subs.get(sub.event, [])
        if sub in lst:
            lst.remove(sub)

    def unsubscribe_owner(self, owner):
        for lst in self._subs.values():
            lst[:] = [s for s in lst if s.owner != owner]

    def emit(self, event, *args, **kwargs):
        for sub in list(self._subs.get(event, [])) + list(self._subs.get("*", [])):
            start = time.perf_counter()
            try:
                if sub.event == "*":
                    sub.callback(event, *args, **kwargs)
                else:
                    sub.callback(*args, **kwargs)
                sub.errors = 0
            except Exception as e:
                sub.errors += 1
                traceback.print_exc()
                _log(sub.owner, "error", f"Ошибка в обработчике '{event}': {e}")
                if sub.errors >= MAX_CONSECUTIVE_ERRORS:
                    self.unsubscribe(sub)
                    _log(sub.owner, "error",
                         f"Обработчик '{event}' отключён после {MAX_CONSECUTIVE_ERRORS} ошибок подряд")
            finally:
                sub.calls += 1
                sub.seconds += time.perf_counter() - start
                if sub.once:
                    self.unsubscribe(sub)

    def stats(self):
        """{owner: {"calls": N, "seconds": S}} - кто сколько времени тратит."""
        out = {}
        for lst in self._subs.values():
            for s in lst:
                r = out.setdefault(s.owner, {"calls": 0, "seconds": 0.0})
                r["calls"] += s.calls
                r["seconds"] += s.seconds
        return out


def _log(owner, msg_type, message):
    """owner - папка аддона. Логируем в его activity.json (если логгер доступен)."""
    if not owner:
        return
    try:
        from addon_logger import log_activity_for_addon
        log_activity_for_addon(owner, msg_type, message)
    except Exception:
        pass


bus = EventBus()


def emit_event(event, *args, **kwargs):
    """Вызывается из кода ЛАУНЧЕРА. Никогда не бросает исключений наружу."""
    try:
        bus.emit(event, *args, **kwargs)
    except Exception:
        traceback.print_exc()
