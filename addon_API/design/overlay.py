"""
Слои оформления поверх окна лаунчера: обои, виньетка, сканлайны, сетка, шум,
градиенты, частицы. Слои прозрачны для мыши - кликать сквозь них можно как обычно.
Статические слои кэшируются, анимированные рисуются на лету (~30 кадров/с).
"""

import math
import time
import random

from PyQt6.QtCore import Qt, QObject, QEvent, QTimer, QPointF, QRectF, QSize
from PyQt6.QtGui import (
    QPainter, QPixmap, QColor, QImage, QLinearGradient, QRadialGradient, QPen, QBrush,
)
from PyQt6.QtWidgets import QWidget

from ._util import safe


# --------------------------------------------------------------------- #
# Слои
# --------------------------------------------------------------------- #
class Layer:
    animated = False
    opacity = 1.0

    def paint(self, p, rect, t, dt):
        pass

    def remove(self):
        ov = getattr(self, "_overlay", None)
        if ov is not None:
            ov.remove(self)


class ImageLayer(Layer):
    def __init__(self, path, opacity, mode):
        self.pix = QPixmap(path)
        self.opacity, self.mode = opacity, mode
        self._scaled, self._key = None, None

    def paint(self, p, rect, t, dt):
        if self.pix.isNull():
            return
        w, h = rect.width(), rect.height()
        p.setOpacity(self.opacity)
        if self.mode == "tile":
            p.drawTiledPixmap(rect, self.pix)
        elif self.mode == "stretch":
            p.drawPixmap(rect, self.pix)
        elif self.mode == "center":
            p.drawPixmap((w - self.pix.width()) // 2, (h - self.pix.height()) // 2, self.pix)
        else:
            aspect = (Qt.AspectRatioMode.KeepAspectRatioByExpanding if self.mode == "cover"
                      else Qt.AspectRatioMode.KeepAspectRatio)
            key = (w, h, self.mode)
            if self._key != key:
                self._scaled = self.pix.scaled(QSize(w, h), aspect, Qt.TransformationMode.SmoothTransformation)
                self._key = key
            sx, sy = (w - self._scaled.width()) // 2, (h - self._scaled.height()) // 2
            p.drawPixmap(sx, sy, self._scaled)
        p.setOpacity(1.0)


class TintLayer(Layer):
    def __init__(self, color, opacity):
        self.color, self.opacity = QColor(color), opacity

    def paint(self, p, rect, t, dt):
        c = QColor(self.color)
        c.setAlphaF(self.opacity)
        p.fillRect(rect, c)


class GradientLayer(Layer):
    def __init__(self, colors, angle, opacity):
        self.colors, self.angle, self.opacity = [QColor(c) for c in colors], angle, opacity

    def _grad(self, rect, angle):
        rad = math.radians(angle)
        dx, dy = math.cos(rad), math.sin(rad)
        cx, cy, w, h = rect.width() / 2, rect.height() / 2, rect.width(), rect.height()
        g = QLinearGradient(cx - dx * w / 2, cy - dy * h / 2, cx + dx * w / 2, cy + dy * h / 2)
        n = max(1, len(self.colors) - 1)
        for i, c in enumerate(self.colors):
            c = QColor(c)
            c.setAlphaF(self.opacity)
            g.setColorAt(i / n, c)
        return g

    def paint(self, p, rect, t, dt):
        p.fillRect(rect, QBrush(self._grad(rect, self.angle)))


class AnimatedGradientLayer(GradientLayer):
    animated = True

    def __init__(self, colors, period_ms, opacity):
        super().__init__(colors, 0, opacity)
        self.period = period_ms

    def paint(self, p, rect, t, dt):
        angle = (t * 1000 / self.period) * 360
        p.fillRect(rect, QBrush(self._grad(rect, angle)))


class VignetteLayer(Layer):
    def __init__(self, strength, color):
        self.strength, self.color = strength, QColor(color)

    def paint(self, p, rect, t, dt):
        w, h = rect.width(), rect.height()
        g = QRadialGradient(QPointF(w / 2, h / 2), max(w, h) * 0.75)
        inner, outer = QColor(self.color), QColor(self.color)
        inner.setAlphaF(0)
        outer.setAlphaF(max(0.0, min(1.0, self.strength)))
        g.setColorAt(0.45, inner)
        g.setColorAt(1.0, outer)
        p.fillRect(rect, QBrush(g))


class ScanlineLayer(Layer):
    def __init__(self, spacing, alpha, color):
        self.spacing, self.color = max(2, spacing), QColor(color)
        self.color.setAlphaF(alpha)

    def paint(self, p, rect, t, dt):
        p.setPen(QPen(self.color, 1))
        for y in range(0, rect.height(), self.spacing):
            p.drawLine(0, y, rect.width(), y)


class GridLayer(Layer):
    def __init__(self, spacing, color, alpha, thickness):
        self.spacing, self.thickness = max(8, spacing), thickness
        self.color = QColor(color)
        self.color.setAlphaF(alpha)

    def paint(self, p, rect, t, dt):
        p.setPen(QPen(self.color, self.thickness))
        for x in range(0, rect.width(), self.spacing):
            p.drawLine(x, 0, x, rect.height())
        for y in range(0, rect.height(), self.spacing):
            p.drawLine(0, y, rect.width(), y)


class NoiseLayer(Layer):
    def __init__(self, alpha):
        rnd = random.Random(7)
        img = QImage(128, 128, QImage.Format.Format_ARGB32)
        for y in range(128):
            for x in range(128):
                v = rnd.randint(0, 255)
                img.setPixelColor(x, y, QColor(v, v, v, int(255 * alpha)))
        self.tile = QPixmap.fromImage(img)

    def paint(self, p, rect, t, dt):
        p.drawTiledPixmap(rect, self.tile)


class ParticlesLayer(Layer):
    animated = True
    KINDS = ("stars", "snow", "rain", "fireflies", "bubbles")

    def __init__(self, kind, count, color, speed):
        self.kind, self.color, self.speed = kind, QColor(color), speed
        rnd = random.Random(11)
        self.items = [dict(x=rnd.random(), y=rnd.random(), vx=rnd.uniform(-0.03, 0.03),
                           vy=rnd.uniform(0.5, 1.0), r=rnd.uniform(1, 3.2), ph=rnd.uniform(0, 6.28))
                      for _ in range(count)]

    def paint(self, p, rect, t, dt):
        w, h = rect.width(), rect.height()
        k, spd = self.kind, self.speed
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        for it in self.items:
            if k == "snow":
                it["y"] += it["vy"] * 0.06 * spd * dt
                it["x"] += math.sin(t * 0.8 + it["ph"]) * 0.02 * dt
            elif k == "rain":
                it["y"] += (0.9 + it["vy"]) * 0.9 * spd * dt
            elif k == "bubbles":
                it["y"] -= it["vy"] * 0.05 * spd * dt
                it["x"] += math.sin(t + it["ph"]) * 0.01 * dt
            elif k == "fireflies":
                it["x"] += (math.sin(t * 0.7 + it["ph"]) * 0.03 + it["vx"]) * spd * dt
                it["y"] += math.cos(t * 0.6 + it["ph"]) * 0.025 * spd * dt
            it["x"] %= 1.0
            it["y"] %= 1.0
            x, y = it["x"] * w, it["y"] * h
            c = QColor(self.color)
            if k == "stars":
                c.setAlphaF(0.25 + 0.75 * (0.5 + 0.5 * math.sin(t * spd * 1.6 + it["ph"])))
                p.setBrush(c); p.setPen(Qt.PenStyle.NoPen)
                p.drawEllipse(QPointF(x, y), it["r"] * 0.7, it["r"] * 0.7)
            elif k == "snow":
                c.setAlphaF(0.8)
                p.setBrush(c); p.setPen(Qt.PenStyle.NoPen)
                p.drawEllipse(QPointF(x, y), it["r"], it["r"])
            elif k == "rain":
                c.setAlphaF(0.45)
                p.setPen(QPen(c, 1))
                p.drawLine(QPointF(x, y), QPointF(x - 2, y + 12))
            elif k == "bubbles":
                c.setAlphaF(0.55)
                p.setBrush(Qt.BrushStyle.NoBrush); p.setPen(QPen(c, 1.2))
                p.drawEllipse(QPointF(x, y), it["r"] * 2.2, it["r"] * 2.2)
            else:  # fireflies
                a = 0.35 + 0.65 * (0.5 + 0.5 * math.sin(t * 1.5 + it["ph"]))
                g = QRadialGradient(QPointF(x, y), it["r"] * 5)
                c0, c1 = QColor(self.color), QColor(self.color)
                c0.setAlphaF(a)
                c1.setAlphaF(0)
                g.setColorAt(0, c0)
                g.setColorAt(1, c1)
                p.setBrush(QBrush(g)); p.setPen(Qt.PenStyle.NoPen)
                p.drawEllipse(QPointF(x, y), it["r"] * 5, it["r"] * 5)


# --------------------------------------------------------------------- #
# Виджет-оверлей
# --------------------------------------------------------------------- #
class Overlay(QWidget):
    def __init__(self, host):
        super().__init__(host)
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        self.setAttribute(Qt.WidgetAttribute.WA_NoSystemBackground)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.layers = []
        self._cache = None
        self._t0 = self._last = time.monotonic()
        self._timer = QTimer(self)
        self._timer.timeout.connect(self.update)
        host.installEventFilter(self)
        self.setGeometry(host.rect())
        self.show()
        self.raise_()

    def add(self, layer):
        layer._overlay = self
        self.layers.append(layer)
        self._cache = None
        self._sync_timer()
        self.update()

    def remove(self, layer):
        if layer in self.layers:
            self.layers.remove(layer)
            self._cache = None
            self._sync_timer()
            self.update()

    def _sync_timer(self):
        if any(l.animated for l in self.layers):
            if not self._timer.isActive():
                self._timer.start(33)
        else:
            self._timer.stop()

    def eventFilter(self, obj, ev):
        if obj is self.parent():
            t = ev.type()
            if t == QEvent.Type.Resize:
                self.setGeometry(self.parent().rect())
                self._cache = None
            elif t in (QEvent.Type.ChildAdded, QEvent.Type.LayoutRequest):
                QTimer.singleShot(0, lambda: safe(self.raise_))
        return False

    def paintEvent(self, ev):
        now = time.monotonic()
        t, dt = now - self._t0, min(0.2, now - self._last)
        self._last = now
        rect = self.rect()
        p = QPainter(self)
        statics = [l for l in self.layers if not l.animated]
        if statics:
            if self._cache is None or self._cache.size() != rect.size():
                pm = QPixmap(rect.size())
                pm.fill(Qt.GlobalColor.transparent)
                cp = QPainter(pm)
                for l in statics:
                    l.paint(cp, rect, t, dt)
                cp.end()
                self._cache = pm
            p.drawPixmap(0, 0, self._cache)
        for l in self.layers:
            if l.animated:
                l.paint(p, rect, t, dt)
        p.end()


# --------------------------------------------------------------------- #
# Методы api.design
# --------------------------------------------------------------------- #
class OverlayMixin:
    def _ov(self):
        if self._overlay is None:
            self._overlay = Overlay(self.launcher)
            self._res.add(self.clear_overlay)
        return self._overlay

    def _layer(self, layer):
        self._ov().add(layer)
        self._res.add(lambda: safe(layer.remove))
        return layer

    def wallpaper(self, path, opacity=0.25, mode="cover"):
        """Картинка-обои. mode: cover | contain | stretch | center | tile.
        Рисуется ПОВЕРХ интерфейса полупрозрачно (поэтому opacity небольшой),
        мышь проходит сквозь неё."""
        return self._layer(ImageLayer(path, opacity, mode))

    def tint(self, color="{{accent}}", opacity=0.08):
        """Лёгкая заливка цветом всего окна."""
        return self._layer(TintLayer(self.qcolor(color, 1.0), opacity))

    def vignette(self, strength=0.55, color="#000000"):
        """Затемнение по краям."""
        return self._layer(VignetteLayer(strength, self.qcolor(color, 1.0)))

    def scanlines(self, spacing=3, alpha=0.10, color="#000000"):
        """Ретро-строки как на ЭЛТ-мониторе."""
        return self._layer(ScanlineLayer(spacing, alpha, self.qcolor(color, 1.0)))

    def grid(self, spacing=44, color="{{accent}}", alpha=0.07, thickness=1):
        """Сетка (киберпанк-стиль)."""
        return self._layer(GridLayer(spacing, self.qcolor(color, 1.0), alpha, thickness))

    def noise(self, alpha=0.04):
        """Зерно/шум плёнки."""
        return self._layer(NoiseLayer(alpha))

    def gradient_overlay(self, colors=("{{accent}}", "#7a2dff"), angle=135, opacity=0.12):
        """Градиентная дымка поверх окна."""
        return self._layer(GradientLayer([self.qcolor(c, 1.0) for c in colors], angle, opacity))

    def animated_gradient(self, colors=("{{accent}}", "#7a2dff", "#00d4ff"), period_ms=14000, opacity=0.12):
        """Медленно вращающийся градиент (aurora)."""
        return self._layer(AnimatedGradientLayer([self.qcolor(c, 1.0) for c in colors], period_ms, opacity))

    def particles(self, kind="stars", count=60, color="#ffffff", speed=1.0):
        """Частицы: stars | snow | rain | fireflies | bubbles"""
        return self._layer(ParticlesLayer(kind, count, self.qcolor(color, 1.0), speed))

    def clear_overlay(self):
        """Убрать все слои."""
        if self._overlay is not None:
            ov, self._overlay = self._overlay, None
            safe(ov._timer.stop)
            safe(ov.hide)
            safe(lambda: ov.parent().removeEventFilter(ov))
            safe(ov.deleteLater)
