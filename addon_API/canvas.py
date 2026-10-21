"""
api.canvas - игровой холст: свой игровой цикл, клавиатура, мышь и рисование.
Из него можно сделать игру, визуализацию, анимацию, дашборд - прямо во вкладке лаунчера.

    c = api.canvas.create(fps=60)
    ship = api.canvas.Entity(x=200, y=200, r=14)

    @c.on_update
    def update(dt):                       # dt - секунды с прошлого кадра
        if c.is_down("left", "a"): ship.x -= 240 * dt

    @c.on_draw
    def draw(p, w, h):                    # p - QPainter
        api.canvas.Draw.glow_circle(p, ship.x, ship.y, ship.r, "#00e5ff")

    api.ui.add_tab(c, "🎮 Игра")          # цикл сам засыпает, когда вкладка не видна

Клавиши называются по-простому: "left" "right" "up" "down" "space" "enter" "escape"
"shift" "ctrl" "a".."z" "0".."9" - буквы работают и в русской раскладке (ц/ф/ы/в = w/a/s/d).
"""

import math
import time
import random

from PyQt6.QtCore import Qt, QTimer, QPointF, QRectF
from PyQt6.QtGui import QColor, QPainter, QPen, QBrush, QFont, QPolygonF, QRadialGradient
from PyQt6.QtWidgets import QWidget

from .design import colors as C

_RU = dict(zip("йцукенгшщзхъфывапролджэячсмитьбю", "qwertyuiop[]asdfghjkl;'zxcvbnm,."))
_SPECIAL = {
    Qt.Key.Key_Left: "left", Qt.Key.Key_Right: "right", Qt.Key.Key_Up: "up", Qt.Key.Key_Down: "down",
    Qt.Key.Key_Space: "space", Qt.Key.Key_Return: "enter", Qt.Key.Key_Enter: "enter",
    Qt.Key.Key_Escape: "escape", Qt.Key.Key_Shift: "shift", Qt.Key.Key_Control: "ctrl",
    Qt.Key.Key_Alt: "alt", Qt.Key.Key_Tab: "tab", Qt.Key.Key_Backspace: "backspace",
    Qt.Key.Key_F1: "f1", Qt.Key.Key_F2: "f2", Qt.Key.Key_F3: "f3", Qt.Key.Key_F4: "f4", Qt.Key.Key_F5: "f5",
}


def key_name(event):
    k = event.key()
    if k in _SPECIAL:
        return _SPECIAL[k]
    t = event.text().lower()
    if t:
        return _RU.get(t, t)
    return str(k)


def qcolor(c, alpha=None):
    if isinstance(c, QColor):
        q = QColor(c)
    else:
        r, g, b, a = C.parse(c)
        q = QColor(r, g, b, int(a * 255))
    if alpha is not None:
        q.setAlphaF(alpha)
    return q


# --------------------------------------------------------------------- #
# Математика и сущности
# --------------------------------------------------------------------- #
def clamp(v, lo, hi):
    return max(lo, min(hi, v))


def lerp(a, b, t):
    return a + (b - a) * t


def wrap(v, lo, hi):
    span = hi - lo
    return lo + (v - lo) % span


def dist(ax, ay, bx, by):
    return math.hypot(bx - ax, by - ay)


def angle_to(ax, ay, bx, by):
    return math.atan2(by - ay, bx - ax)


def circles_hit(a, b):
    return (a.x - b.x) ** 2 + (a.y - b.y) ** 2 <= (a.r + b.r) ** 2


class Entity:
    """Простая игровая сущность: позиция, скорость, радиус, угол, «жива ли»."""
    def __init__(self, x=0.0, y=0.0, vx=0.0, vy=0.0, r=10.0, angle=0.0, **extra):
        self.x, self.y, self.vx, self.vy, self.r, self.angle = x, y, vx, vy, r, angle
        self.alive, self.age = True, 0.0
        self.__dict__.update(extra)

    def move(self, dt):
        self.x += self.vx * dt
        self.y += self.vy * dt
        self.age += dt

    def speed(self):
        return math.hypot(self.vx, self.vy)


class Particles:
    """Система частиц: взрывы, искры, дым."""
    def __init__(self):
        self.items = []

    def emit(self, x, y, n=20, speed=140, life=0.7, color="#ffaa33", size=3.0, spread=math.tau, direction=0.0, drag=0.9):
        for _ in range(n):
            a = direction + random.uniform(-spread / 2, spread / 2)
            s = random.uniform(0.25, 1.0) * speed
            self.items.append({"x": x, "y": y, "vx": math.cos(a) * s, "vy": math.sin(a) * s,
                               "life": life * random.uniform(0.6, 1.0), "max": life,
                               "color": color, "size": size * random.uniform(0.6, 1.2), "drag": drag})

    def update(self, dt):
        for p in self.items:
            p["x"] += p["vx"] * dt
            p["y"] += p["vy"] * dt
            k = p["drag"] ** (dt * 60)
            p["vx"] *= k
            p["vy"] *= k
            p["life"] -= dt
        self.items = [p for p in self.items if p["life"] > 0]

    def draw(self, p):
        p.setPen(Qt.PenStyle.NoPen)
        for it in self.items:
            q = qcolor(it["color"], max(0.0, it["life"] / it["max"]))
            p.setBrush(q)
            s = it["size"] * (0.5 + it["life"] / it["max"] * 0.5)
            p.drawEllipse(QPointF(it["x"], it["y"]), s, s)


class Starfield:
    """Звёздное небо с параллаксом."""
    def __init__(self, w, h, n=130):
        self.w, self.h = w, h
        self.stars = [[random.uniform(0, w), random.uniform(0, h), random.choice((0.25, 0.5, 1.0)),
                       random.uniform(0, 6.28)] for _ in range(n)]

    def resize(self, w, h):
        for s in self.stars:
            s[0] = s[0] / max(1, self.w) * w
            s[1] = s[1] / max(1, self.h) * h
        self.w, self.h = w, h

    def update(self, dt, speed=40.0):
        for s in self.stars:
            s[1] += speed * s[2] * dt
            if s[1] > self.h:
                s[1], s[0] = 0, random.uniform(0, self.w)

    def draw(self, p, t=0.0, color="#ffffff"):
        p.setPen(Qt.PenStyle.NoPen)
        for x, y, depth, ph in self.stars:
            a = 0.35 + 0.65 * depth * (0.6 + 0.4 * math.sin(t * 2 + ph))
            p.setBrush(qcolor(color, min(1.0, a)))
            r = 0.6 + depth * 1.2
            p.drawEllipse(QPointF(x, y), r, r)


class Draw:
    """Быстрые рисовалки. Все цвета - строки ('#ff0', 'rgba(...)')."""
    @staticmethod
    def circle(p, x, y, r, fill=None, stroke=None, width=1.5):
        p.setBrush(QBrush(qcolor(fill)) if fill else Qt.BrushStyle.NoBrush)
        p.setPen(QPen(qcolor(stroke), width) if stroke else Qt.PenStyle.NoPen)
        p.drawEllipse(QPointF(x, y), r, r)

    @staticmethod
    def rect(p, x, y, w, h, fill=None, stroke=None, width=1.5, radius=0):
        p.setBrush(QBrush(qcolor(fill)) if fill else Qt.BrushStyle.NoBrush)
        p.setPen(QPen(qcolor(stroke), width) if stroke else Qt.PenStyle.NoPen)
        if radius:
            p.drawRoundedRect(QRectF(x, y, w, h), radius, radius)
        else:
            p.drawRect(QRectF(x, y, w, h))

    @staticmethod
    def line(p, x1, y1, x2, y2, color="#ffffff", width=2.0):
        p.setPen(QPen(qcolor(color), width, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap))
        p.drawLine(QPointF(x1, y1), QPointF(x2, y2))

    @staticmethod
    def polygon(p, points, fill=None, stroke=None, width=2.0, x=0, y=0, angle=0.0):
        """Многоугольник; points - [(x, y)] относительно (x, y), повёрнутый на angle (радианы)."""
        ca, sa = math.cos(angle), math.sin(angle)
        poly = QPolygonF([QPointF(x + px * ca - py * sa, y + px * sa + py * ca) for px, py in points])
        p.setBrush(QBrush(qcolor(fill)) if fill else Qt.BrushStyle.NoBrush)
        p.setPen(QPen(qcolor(stroke), width, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap,
                      Qt.PenJoinStyle.RoundJoin) if stroke else Qt.PenStyle.NoPen)
        p.drawPolygon(poly)

    @staticmethod
    def glow_circle(p, x, y, r, color="#00e5ff", glow=2.6):
        g = QRadialGradient(QPointF(x, y), r * glow)
        c0, c1 = qcolor(color, 0.55), qcolor(color, 0.0)
        g.setColorAt(0.0, c0)
        g.setColorAt(1.0, c1)
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QBrush(g))
        p.drawEllipse(QPointF(x, y), r * glow, r * glow)
        p.setBrush(QBrush(qcolor(color)))
        p.drawEllipse(QPointF(x, y), r, r)

    @staticmethod
    def text(p, x, y, text, size=14, color="#ffffff", align="left", bold=False, family=None):
        f = QFont(family) if family else QFont(p.font())
        f.setPixelSize(int(size))
        f.setBold(bold)
        p.setFont(f)
        p.setPen(qcolor(color))
        fm = p.fontMetrics()
        w = fm.horizontalAdvance(text)
        px = x - w / 2 if align == "center" else (x - w if align == "right" else x)
        p.drawText(QPointF(px, y + fm.ascent() * 0.8), text)


# --------------------------------------------------------------------- #
# Холст
# --------------------------------------------------------------------- #
class GameCanvas(QWidget):
    def __init__(self, fps=60, bg="#050510", min_size=(480, 320)):
        super().__init__()
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.setMouseTracking(True)
        self.setMinimumSize(*min_size)
        self.setAttribute(Qt.WidgetAttribute.WA_OpaquePaintEvent)
        self.fps, self.bg = fps, qcolor(bg)
        self.keys = set()
        self.time, self.frame = 0.0, 0
        self.mouse = (0, 0)
        self._upd, self._drw, self._kd, self._ku, self._mouse_cbs, self._rsz = [], [], [], [], [], []
        self._timer = QTimer(self)
        self._timer.timeout.connect(self._tick)
        self._last = None
        self._want = False

    # --- подписки (можно использовать как декораторы) ---
    def on_update(self, fn):
        self._upd.append(fn)
        return fn

    def on_draw(self, fn):
        self._drw.append(fn)
        return fn

    def on_key_down(self, fn):
        self._kd.append(fn)
        return fn

    def on_key_up(self, fn):
        self._ku.append(fn)
        return fn

    def on_mouse(self, fn):
        """fn(kind, x, y, button): kind = press | release | move"""
        self._mouse_cbs.append(fn)
        return fn

    def on_resize(self, fn):
        self._rsz.append(fn)
        return fn

    # --- управление ---
    def start(self):
        self._want = True
        if self.isVisible():
            self._last = time.monotonic()
            self._timer.start(max(1, int(1000 / self.fps)))

    def stop(self):
        self._want = False
        self._timer.stop()

    @property
    def running(self):
        return self._timer.isActive()

    def is_down(self, *names):
        return any(n in self.keys for n in names)

    def step(self, dt=1 / 60, frames=1):
        """Ручной шаг игры (для тестов и записи): обновляет логику без таймера."""
        for _ in range(frames):
            self._advance(dt)
        self.update()

    def _advance(self, dt):
        self.time += dt
        self.frame += 1
        for cb in list(self._upd):
            cb(dt)

    def _tick(self):
        now = time.monotonic()
        dt = min(0.05, now - (self._last or now))
        self._last = now
        self._advance(dt)
        self.update()

    # --- события Qt ---
    def showEvent(self, e):
        super().showEvent(e)
        if self._want:
            self.start()
        self.setFocus()

    def hideEvent(self, e):
        super().hideEvent(e)
        self._timer.stop()
        self.keys.clear()

    def resizeEvent(self, e):
        super().resizeEvent(e)
        for cb in list(self._rsz):
            cb(self.width(), self.height())

    def paintEvent(self, e):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        p.fillRect(self.rect(), self.bg)
        for cb in list(self._drw):
            cb(p, self.width(), self.height())
        p.end()

    def keyPressEvent(self, e):
        if e.isAutoRepeat():
            return
        n = key_name(e)
        self.keys.add(n)
        for cb in list(self._kd):
            cb(n)
        e.accept()

    def keyReleaseEvent(self, e):
        if e.isAutoRepeat():
            return
        n = key_name(e)
        self.keys.discard(n)
        for cb in list(self._ku):
            cb(n)
        e.accept()

    def focusOutEvent(self, e):
        self.keys.clear()
        super().focusOutEvent(e)

    def _mouse(self, kind, e):
        pos = e.position()
        self.mouse = (pos.x(), pos.y())
        for cb in list(self._mouse_cbs):
            cb(kind, pos.x(), pos.y(), e.button() if kind != "move" else None)

    def mousePressEvent(self, e):
        self.setFocus()
        self._mouse("press", e)

    def mouseReleaseEvent(self, e):
        self._mouse("release", e)

    def mouseMoveEvent(self, e):
        self._mouse("move", e)


class CanvasAPI:
    # удобные имена прямо на api.canvas
    Entity, Particles, Starfield, Draw = Entity, Particles, Starfield, Draw
    clamp, lerp, wrap, dist, angle_to, circles_hit = (staticmethod(f) for f in
                                                      (clamp, lerp, wrap, dist, angle_to, circles_hit))
    qcolor = staticmethod(qcolor)
    random = random

    def __init__(self, api):
        self._api = api

    def create(self, fps=60, bg="#050510", min_size=(480, 320), autostart=True):
        """Создать холст. Он сам останавливается, когда скрыт, и при выгрузке аддона."""
        c = GameCanvas(fps, bg, min_size)

        def undo():
            try:
                c.stop()
                c.deleteLater()
            except RuntimeError:
                pass
        self._api._resources.add(undo)
        if autostart:
            c.start()
        return c
