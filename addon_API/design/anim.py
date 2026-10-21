"""Анимации интерфейса: появление, сдвиг, пульс, тряска, смена цветов."""

import time

from PyQt6.QtCore import QPropertyAnimation, QEasingCurve, QPoint, QTimer, QVariantAnimation
from PyQt6.QtWidgets import QGraphicsOpacityEffect

from . import colors as C
from ._util import safe

_EASING = {
    "linear": "Linear", "in_quad": "InQuad", "out_quad": "OutQuad", "in_out_quad": "InOutQuad",
    "in_cubic": "InCubic", "out_cubic": "OutCubic", "in_out_cubic": "InOutCubic",
    "out_back": "OutBack", "in_back": "InBack", "out_bounce": "OutBounce",
    "out_elastic": "OutElastic", "in_out_sine": "InOutSine", "out_expo": "OutExpo",
}


def _curve(name):
    return QEasingCurve(getattr(QEasingCurve.Type, _EASING.get(name, "OutCubic")))


class AnimMixin:
    def easings(self):
        return list(_EASING)

    def _make_anim(self, obj, prop, start=None, end=None, ms=300, easing="out_cubic", loop=1,
                   delay=0, keys=None, restore=None):
        """Создаёт и запускает анимацию. restore() вызывается, если анимацию прервали
        (reset/выгрузка аддона) до завершения - чтобы виджет не остался в промежуточном виде."""
        a = QPropertyAnimation(obj, prop.encode(), self.launcher)
        a.setDuration(ms)
        a.setEasingCurve(_curve(easing))
        if keys:
            for t, v in keys:
                a.setKeyValueAt(t, v)
        else:
            a.setStartValue(start)
            a.setEndValue(end)
        a.setLoopCount(loop)
        self._anims.append(a)
        state = {"done": False}

        def undo():
            if not state["done"]:
                safe(a.stop)
                if restore:
                    safe(restore)

        def finished():
            state["done"] = True
            if a in self._anims:
                self._anims.remove(a)
            self._res.discard(undo)
        a.finished.connect(finished)
        self._res.add(undo)
        if delay > 0:
            QTimer.singleShot(delay, lambda: a in self._anims and safe(a.start))
        else:
            a.start()
        return a

    def animate(self, target, prop, start, end, ms=300, easing="out_cubic", loop=1, pingpong=False):
        """Анимировать свойство Qt: design.animate("GameCard", "maximumHeight", 0, 200).
        loop=-1 - бесконечно; pingpong=True - туда и обратно."""
        out = []
        for w in self.find_all(target):
            a = QPropertyAnimation(w, prop.encode(), self.launcher)
            a.setDuration(ms)
            a.setEasingCurve(_curve(easing))
            if pingpong:
                a.setKeyValueAt(0, start)
                a.setKeyValueAt(0.5, end)
                a.setKeyValueAt(1, start)
            else:
                a.setStartValue(start)
                a.setEndValue(end)
            a.setLoopCount(loop)
            self._anims.append(a)
            a.start()
            out.append(a)
        return out

    def stop_animations(self):
        for a in list(self._anims):
            safe(a.stop)
        self._anims.clear()

    # ------------------------------ появление ------------------------------ #
    def _drop_effect(self, w, e):
        return lambda: w.graphicsEffect() is e and w.setGraphicsEffect(None)

    def fade_in(self, target, ms=300, start=0.0, end=1.0, easing="out_cubic", delay=0):
        """Плавное появление. Если на виджете уже есть другой эффект (тень, свечение),
        он сохраняется, а сама прозрачность не анимируется."""
        for w in self.find_all(target):
            def go(w=w):
                if w.graphicsEffect() is not None:
                    return
                e = QGraphicsOpacityEffect(w)
                e.setOpacity(start)
                w.setGraphicsEffect(e)
                drop = self._drop_effect(w, e)
                a = self._make_anim(e, "opacity", start, end, ms, easing, 1, delay, restore=drop)
                a.finished.connect(lambda: safe(drop))
            safe(go)

    def fade_out(self, target, ms=300, hide=True, easing="out_cubic"):
        for w in self.find_all(target):
            def go(w=w):
                if w.graphicsEffect() is not None:
                    return
                e = QGraphicsOpacityEffect(w)
                w.setGraphicsEffect(e)
                drop = self._drop_effect(w, e)
                a = self._make_anim(e, "opacity", 1.0, 0.0, ms, easing, restore=drop)

                def done():
                    if hide:
                        w.hide()
                    drop()
                a.finished.connect(lambda: safe(done))
            safe(go)

    def slide_in(self, target, direction="left", distance=60, ms=350, easing="out_cubic", delay=0):
        """Выезд виджета со стороны: left | right | up | down."""
        dx, dy = {"left": (-distance, 0), "right": (distance, 0),
                  "up": (0, -distance), "down": (0, distance)}.get(direction, (-distance, 0))
        for w in self.find_all(target):
            def go(w=w):
                end = w.pos()
                self._make_anim(w, "pos", end + QPoint(dx, dy), end, ms, easing, 1, delay,
                                restore=lambda: w.move(end))
            safe(go)

    def appear(self, target, kind="fade", ms=350, stagger=40, distance=40):
        """Анимация появления НОВЫХ виджетов (например, карточек игр, которые добавят
        или перерисуют позже), с каскадом через stagger мс.
        kind: fade | left | right | up | down.
        Пример: design.appear("GameCard", "up", stagger=50)"""
        counter = [0]

        def apply(w):
            delay = (counter[0] % 12) * stagger
            counter[0] += 1
            if kind == "fade":
                self.fade_in(w, ms=ms, delay=delay)
            else:
                self.fade_in(w, ms=ms, delay=delay)
                self.slide_in(w, kind, distance, ms, delay=delay)
        self.each(target, apply, existing=False)

    # ------------------------------ движение ------------------------------ #
    def pulse(self, target, ms=1400, low=0.45):
        """Бесконечное «дыхание» прозрачности."""
        for w in self.find_all(target):
            def go(w=w):
                if w.graphicsEffect() is not None:
                    return
                e = QGraphicsOpacityEffect(w)
                w.setGraphicsEffect(e)
                self._make_anim(e, "opacity", ms=ms, easing="in_out_sine", loop=-1,
                                keys=[(0, 1.0), (0.5, low), (1, 1.0)],
                                restore=self._drop_effect(w, e))
            safe(go)

    def shake(self, target, distance=8, ms=380):
        """Тряска (ошибка / внимание)."""
        for w in self.find_all(target):
            def go(w=w):
                p = w.pos()
                keys = [(t, p + QPoint(int(distance * off), 0)) for t, off in
                        ((0, 0), (0.15, -1), (0.3, 1), (0.45, -1), (0.6, 1), (0.8, -0.5), (1, 0))]
                self._make_anim(w, "pos", ms=ms, easing="linear", keys=keys, restore=lambda: w.move(p))
            safe(go)

    def bounce(self, target, height=14, ms=520):
        """Подпрыгивание."""
        for w in self.find_all(target):
            def go(w=w):
                p = w.pos()
                self._make_anim(w, "pos", ms=ms, easing="out_bounce",
                                keys=[(0, p), (0.4, p + QPoint(0, -height)), (1, p)],
                                restore=lambda: w.move(p))
            safe(go)

    def animate_tab_switch(self, kind="fade", ms=260):
        """Анимация при переключении вкладок лаунчера. kind: fade | left | right | up | down"""
        tabs = self.launcher.tabs

        def on_change(i):
            w = tabs.widget(i)
            if w is None:
                return
            if kind == "fade":
                self.fade_in(w, ms=ms)
            else:
                self.fade_in(w, ms=ms)
                self.slide_in(w, kind, 40, ms)
        tabs.currentChanged.connect(on_change)
        self._res.add(lambda: safe(lambda: tabs.currentChanged.disconnect(on_change)))

    # ------------------------------ цвета во времени ------------------------------ #
    def stop_color_animation(self):
        if self._color_timer is not None:
            safe(self._color_timer.stop)
            safe(self._color_timer.deleteLater)
            self._color_timer = None

    def animate_accent(self, colors=None, period_ms=8000, fps=4, token="accent"):
        """Акцентный цвет всего лаунчера плавно перетекает по списку цветов (по кругу).
        colors=None - радуга. ВНИМАНИЕ: каждый кадр пересобирает стиль, поэтому fps
        небольшой по умолчанию (4); на слабых ПК не поднимайте выше 8."""
        from ..themes import themes
        self.stop_color_animation()
        t0 = time.monotonic()
        stops = list(colors) if colors else None
        timer = QTimer(self.launcher)

        def tick():
            phase = ((time.monotonic() - t0) * 1000 / period_ms) % 1.0
            if stops is None:
                col = C.rainbow(phase)
            else:
                pos = phase * len(stops)
                i = int(pos) % len(stops)
                col = C.mix(self._fill(stops[i]), self._fill(stops[(i + 1) % len(stops)]), pos - int(pos))
            themes.set_runtime_colors(self._api.root, {token: col})
        timer.timeout.connect(tick)
        timer.start(max(30, int(1000 / fps)))
        self._color_timer = timer
        self._res.add(self.stop_color_animation)
        tick()

    def rainbow(self, period_ms=8000, fps=4):
        self.animate_accent(None, period_ms, fps)

    def breathe_accent(self, color_a, color_b, period_ms=4000, fps=5):
        """Акцент «дышит» между двумя цветами."""
        self.animate_accent([color_a, color_b], period_ms, fps)

    def transition_colors(self, mapping, ms=500, steps=14):
        """Плавный переход цветов лаунчера к новым значениям {роль: цвет}."""
        from ..themes import themes
        start = themes.colors()
        target = {k: self._fill(v) for k, v in mapping.items() if k in start}
        va = QVariantAnimation(self.launcher)
        va.setDuration(ms)
        va.setStartValue(0.0)
        va.setEndValue(1.0)
        last = [-1]

        def step(v):
            idx = int(v * steps)
            if idx == last[0] and v < 1.0:
                return
            last[0] = idx
            themes.set_runtime_colors(self._api.root,
                                      {k: C.mix(start[k], c, v) for k, c in target.items()})
        va.valueChanged.connect(step)
        self._anims.append(va)
        va.start()
        return va
