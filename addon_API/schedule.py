"""
api.schedule - расписание и простой.

    api.schedule.at("22:30", lambda: api.notify("Пора спать"))            # каждый день
    api.schedule.at("09:00", fn, weekdays=[0, 1, 2, 3, 4])               # по будням (0 = понедельник)
    api.schedule.after(300, fn)                                            # через 5 минут
    api.schedule.every(60, fn)                                             # каждую минуту
    api.schedule.on_idle(600, lambda: ...)    # 10 минут без нажатий в лаунчере
    api.schedule.on_active(lambda: ...)       # пользователь вернулся
"""

import time
import datetime

from PyQt6.QtCore import QObject, QEvent, QTimer
from PyQt6.QtWidgets import QApplication

_INPUT = {QEvent.Type.MouseButtonPress, QEvent.Type.MouseMove, QEvent.Type.KeyPress,
          QEvent.Type.Wheel, QEvent.Type.TouchBegin}


class _ActivityFilter(QObject):
    def __init__(self, owner):
        super().__init__()
        self.owner = owner

    def eventFilter(self, obj, ev):
        if ev.type() in _INPUT:
            self.owner._touch()
        return False


class ScheduleAPI:
    def __init__(self, api):
        self._api = api
        self._last_input = time.time()
        self._was_idle = False
        self._idle_rules = []     # {"seconds", "fn", "fired"}
        self._active_cbs = []
        self._filter = None
        self._poll = None

    # ---------------------------------------------------------- по времени
    def at(self, time_str, fn, weekdays=None):
        """Каждый день в HH:MM (weekdays - необязательный список дней 0..6)."""
        hh, mm = (int(x) for x in time_str.split(":"))
        state = {"last": None}

        def check():
            now = datetime.datetime.now()
            if weekdays is not None and now.weekday() not in weekdays:
                return
            if now.hour == hh and now.minute == mm and state["last"] != now.date():
                state["last"] = now.date()
                fn()
        return self._api.every(15_000, check)

    daily = at

    def every(self, seconds, fn):
        return self._api.every(int(seconds * 1000), fn)

    def after(self, seconds, fn):
        return self._api.later(int(seconds * 1000), fn)

    # ---------------------------------------------------------- простой
    def _ensure_tracking(self):
        if self._filter is not None:
            return
        self._filter = _ActivityFilter(self)
        QApplication.instance().installEventFilter(self._filter)
        self._poll = self._api.every(2000, self._check_idle)

        def undo():
            try:
                QApplication.instance().removeEventFilter(self._filter)
            except Exception:
                pass
        self._api._resources.add(undo)

    def _touch(self):
        self._last_input = time.time()
        if self._was_idle:
            self._was_idle = False
            for r in self._idle_rules:
                r["fired"] = False
            for cb in list(self._active_cbs):
                self._api._safe(cb)()

    def idle_seconds(self):
        """Сколько секунд в лаунчере ничего не нажимали."""
        return time.time() - self._last_input

    def _check_idle(self):
        idle = self.idle_seconds()
        for r in self._idle_rules:
            if not r["fired"] and idle >= r["seconds"]:
                r["fired"] = True
                self._was_idle = True
                self._api._safe(r["fn"])()

    def on_idle(self, seconds, fn):
        self._ensure_tracking()
        self._idle_rules.append({"seconds": seconds, "fn": fn, "fired": False})

    def on_active(self, fn):
        self._ensure_tracking()
        self._active_cbs.append(fn)
