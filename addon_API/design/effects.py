"""Поиск виджетов и графические эффекты: тени, свечение, размытие, прозрачность."""

import traceback

from PyQt6.QtCore import QObject, QEvent, QPropertyAnimation, QEasingCurve
from PyQt6.QtGui import QColor
from PyQt6.QtWidgets import (
    QApplication, QWidget, QGraphicsDropShadowEffect, QGraphicsOpacityEffect,
    QGraphicsBlurEffect, QGraphicsColorizeEffect,
)

from . import colors as C
from ._util import safe


def make_matcher(target):
    """target: QWidget | "ObjectName" | "#ObjectName" | ".QPushButton" (класс) |
    функция-предикат | список из перечисленного."""
    if isinstance(target, QWidget):
        return lambda w: w is target
    if callable(target):
        return target
    if isinstance(target, (list, tuple, set)):
        ms = [make_matcher(t) for t in target]
        return lambda w: any(m(w) for m in ms)
    t = str(target).strip()
    if t.startswith("."):
        cls = t[1:]
        return lambda w: w.inherits(cls)
    if t.startswith("#"):
        t = t[1:]
    return lambda w: w.objectName() == t


class _PolishFilter(QObject):
    """Ловит появление НОВЫХ виджетов (первый Polish) и применяет к ним правила."""
    def __init__(self):
        super().__init__()
        self.watchers = []

    def eventFilter(self, obj, ev):
        if ev.type() == QEvent.Type.Polish and isinstance(obj, QWidget) and self.watchers:
            for w in list(self.watchers):
                if obj.property(w["key"]):
                    continue
                try:
                    if w["match"](obj):
                        obj.setProperty(w["key"], True)
                        w["fn"](obj)
                except Exception:
                    traceback.print_exc()
        return False


class _HoverFx(QObject):
    def __init__(self, widget, make):
        super().__init__(widget)
        self.w, self.make = widget, make
        widget.installEventFilter(self)

    def eventFilter(self, obj, ev):
        t = ev.type()
        if t == QEvent.Type.Enter:
            self.w.setGraphicsEffect(self.make(self.w))
        elif t == QEvent.Type.Leave:
            self.w.setGraphicsEffect(None)
        return False


class EffectsMixin:
    # ------------------------------------------------------------ #
    # Поиск виджетов
    # ------------------------------------------------------------ #
    def find_all(self, target):
        """Все виджеты, подходящие под target (см. make_matcher)."""
        m = make_matcher(target)
        return [w for w in QApplication.allWidgets() if safe(lambda w=w: m(w))]

    def each(self, target, fn, future=True, existing=True):
        """Вызвать fn(widget) для всех подходящих виджетов; future=True - и для тех,
        что появятся позже (например, новые карточки игр); existing=False - только для
        будущих. Откатывается при reset()."""
        m = make_matcher(target)
        self._counter += 1
        # имя динамического свойства Qt обязано быть ASCII, а папка аддона может быть любой (хоть русской)
        key = "_dsg_%x_%d" % (abs(hash(self._api.root)) & 0xFFFFFF, self._counter)
        for w in QApplication.allWidgets():
            if safe(lambda w=w: m(w)):
                w.setProperty(key, True)
                if existing:
                    safe(lambda w=w: fn(w))
        if future:
            if self._polish is None:
                self._polish = _PolishFilter()
                QApplication.instance().installEventFilter(self._polish)
                self._res.add(self._drop_polish)
            watcher = {"match": m, "fn": fn, "key": key}
            self._polish.watchers.append(watcher)
            self._res.add(lambda: watcher in self._polish.watchers and self._polish.watchers.remove(watcher))

    def _drop_polish(self):
        if self._polish is not None:
            safe(lambda: QApplication.instance().removeEventFilter(self._polish))
            self._polish = None

    # ------------------------------------------------------------ #
    # Эффекты
    # ------------------------------------------------------------ #
    def qcolor(self, color, alpha=None):
        """'{{accent}}' / '#hex' / 'rgba(...)' -> QColor."""
        r, g, b, a = C.parse(self._fill(color))
        return QColor(r, g, b, int((a if alpha is None else alpha) * 255))

    def _put_effect(self, w, effect):
        w.setGraphicsEffect(effect)
        self._res.add(lambda: safe(lambda: w.graphicsEffect() is effect and w.setGraphicsEffect(None)))

    def shadow(self, target, blur=24, dx=0, dy=6, color="#000000", alpha=0.55):
        """Тень под виджетами. Пример: design.shadow("GameCard", blur=30, dy=8)
        (на виджете одновременно может быть один эффект: тень/свечение/размытие/прозрачность)"""
        def apply(w):
            e = QGraphicsDropShadowEffect(w)
            e.setBlurRadius(blur)
            e.setOffset(dx, dy)
            e.setColor(self.qcolor(color, alpha))
            self._put_effect(w, e)
        self.each(target, apply)

    def glow(self, target, color="{{accent}}", radius=26, alpha=0.9, pulse_ms=0):
        """Неоновое свечение. pulse_ms>0 - «дыхание» свечения."""
        def apply(w):
            e = QGraphicsDropShadowEffect(w)
            e.setBlurRadius(radius)
            e.setOffset(0, 0)
            e.setColor(self.qcolor(color, alpha))
            self._put_effect(w, e)
            if pulse_ms > 0:
                a = QPropertyAnimation(e, b"blurRadius", e)
                a.setDuration(pulse_ms)
                a.setKeyValueAt(0, radius * 0.35)
                a.setKeyValueAt(0.5, radius)
                a.setKeyValueAt(1, radius * 0.35)
                a.setEasingCurve(QEasingCurve.Type.InOutSine)
                a.setLoopCount(-1)
                a.start()
                self._anims.append(a)
        self.each(target, apply)

    def hover_glow(self, target, color="{{accent}}", radius=24, alpha=0.85):
        """Свечение только при наведении курсора (отлично для карточек игр)."""
        def make(w):
            e = QGraphicsDropShadowEffect(w)
            e.setBlurRadius(radius)
            e.setOffset(0, 0)
            e.setColor(self.qcolor(color, alpha))
            return e

        def apply(w):
            f = _HoverFx(w, make)

            def undo():
                w.removeEventFilter(f)
                f.deleteLater()
                w.setGraphicsEffect(None)
            self._res.add(lambda: safe(undo))
        self.each(target, apply)

    def hover_shadow(self, target, blur=28, dy=10, alpha=0.6):
        """Тень «поднимает» виджет при наведении."""
        def make(w):
            e = QGraphicsDropShadowEffect(w)
            e.setBlurRadius(blur)
            e.setOffset(0, dy)
            e.setColor(QColor(0, 0, 0, int(alpha * 255)))
            return e

        def apply(w):
            f = _HoverFx(w, make)
            self._res.add(lambda: safe(lambda: (w.removeEventFilter(f), f.deleteLater(),
                                                w.setGraphicsEffect(None))))
        self.each(target, apply)

    def opacity(self, target, value):
        """Прозрачность виджетов 0..1."""
        def apply(w):
            e = QGraphicsOpacityEffect(w)
            e.setOpacity(value)
            self._put_effect(w, e)
        self.each(target, apply)

    def blur(self, target, radius=8):
        """Размытие виджетов."""
        def apply(w):
            e = QGraphicsBlurEffect(w)
            e.setBlurRadius(radius)
            self._put_effect(w, e)
        self.each(target, apply)

    def colorize(self, target, color="{{accent}}", strength=0.6):
        """Окрасить виджет в цвет (удобно для иконок и обложек)."""
        def apply(w):
            e = QGraphicsColorizeEffect(w)
            e.setColor(self.qcolor(color, 1.0))
            e.setStrength(strength)
            self._put_effect(w, e)
        self.each(target, apply)

    def clear_effects(self, target):
        """Снять все эффекты с виджетов."""
        for w in self.find_all(target):
            safe(lambda w=w: w.setGraphicsEffect(None))
