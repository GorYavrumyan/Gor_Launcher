import math
import random

from addon_API import AddonBase, Events

TAU = math.tau
SIZES = {3: 38, 2: 22, 1: 12}          # радиус астероида по размеру
POINTS = {3: 20, 2: 50, 1: 100}        # очки за уничтожение


class Game:
    """Вся игровая логика. Рисует и обновляет себя через холст api.canvas."""

    def __init__(self, api):
        self.api = api
        cv = api.canvas
        self.cv = cv
        self.c = cv.create(fps=60, bg="#04040c", min_size=(560, 380))
        self.w, self.h = 800, 520
        self.stars = cv.Starfield(self.w, self.h, 140)
        self.parts = cv.Particles()
        self.colors = api.design.get_colors()
        self.state, self.paused = "menu", False
        self.hi = api.settings.get("hi", 0)
        self.sound = api.settings.get("sound", True)
        self.score = self.wave = 0
        self.shake = 0.0
        self.reset_world()

        self.c.on_update(self.update)
        self.c.on_draw(self.draw)
        self.c.on_key_down(self.key_down)
        self.c.on_resize(self.on_resize)
        api.on(Events.THEME_CHANGED, lambda *_: setattr(self, "colors", api.design.get_colors()))

    # ------------------------------------------------------------ мир
    def reset_world(self):
        cv = self.cv
        self.ship = cv.Entity(self.w / 2, self.h / 2, r=11, angle=-math.pi / 2, lives=3, invuln=0.0, cd=0.0)
        self.bullets, self.rocks = [], []
        self.score, self.wave = 0, 0

    def on_resize(self, w, h):
        self.w, self.h = w, h
        self.stars.resize(w, h)

    def spawn_wave(self):
        self.wave += 1
        n = min(3 + self.wave, 11)
        for _ in range(n):
            while True:
                x, y = random.uniform(0, self.w), random.uniform(0, self.h)
                if self.cv.dist(x, y, self.ship.x, self.ship.y) > 170:
                    break
            self.rocks.append(self.make_rock(x, y, 3))

    def make_rock(self, x, y, size):
        speed = random.uniform(30, 70) * (1 + 0.08 * self.wave) * (4 - size) ** 0.5
        a = random.uniform(0, TAU)
        r = SIZES[size]
        pts = []
        for i in range(11):
            ang = TAU * i / 11
            k = random.uniform(0.72, 1.12)
            pts.append((math.cos(ang) * r * k, math.sin(ang) * r * k))
        return self.cv.Entity(x, y, math.cos(a) * speed, math.sin(a) * speed, r=r, size=size,
                              angle=random.uniform(0, TAU), spin=random.uniform(-1.4, 1.4), pts=pts)

    def sfx(self, kind):
        if not self.sound:
            return
        au = self.api.audio
        if kind == "shoot":
            au.tone(880, 70, 0.18, "square", slide=-520)
        elif kind == "boom":
            au.noise(230, 0.35)
        elif kind == "small":
            au.noise(90, 0.2)
        elif kind == "die":
            au.tone(300, 420, 0.3, "saw", slide=-260)

    # ------------------------------------------------------------ ввод
    def key_down(self, k):
        if k == "m":
            self.sound = not self.sound
            self.api.settings.set("sound", self.sound)
        if self.state in ("menu", "over") and k in ("space", "enter"):
            self.start()
        elif self.state == "play" and k in ("p", "escape"):
            self.paused = not self.paused

    def start(self):
        self.reset_world()
        self.state, self.paused = "play", False
        self.spawn_wave()

    # ------------------------------------------------------------ логика
    def update(self, dt):
        self.stars.update(dt, 22 if self.state != "play" else 40)
        self.parts.update(dt)
        self.shake = max(0.0, self.shake - dt * 2.2)
        if self.state != "play" or self.paused:
            if self.state == "menu":                     # на заставке астероиды дрейфуют
                for r in self.rocks:
                    self.move_wrap(r, dt)
            return
        cv, s = self.c, self.ship
        # управление кораблём
        if cv.is_down("left", "a"):
            s.angle -= 4.2 * dt
        if cv.is_down("right", "d"):
            s.angle += 4.2 * dt
        if cv.is_down("up", "w"):
            s.vx += math.cos(s.angle) * 330 * dt
            s.vy += math.sin(s.angle) * 330 * dt
            for _ in range(2):
                self.parts.emit(s.x - math.cos(s.angle) * 12, s.y - math.sin(s.angle) * 12, 1, 110, 0.35,
                                "#ffb347", 2.6, 0.5, s.angle + math.pi)
        drag = 0.992 if not cv.is_down("down", "s") else 0.95
        k = drag ** (dt * 60)
        s.vx, s.vy = s.vx * k, s.vy * k
        sp = s.speed()
        if sp > 420:
            s.vx, s.vy = s.vx / sp * 420, s.vy / sp * 420
        self.move_wrap(s, dt)
        s.invuln = max(0.0, s.invuln - dt)
        s.cd = max(0.0, s.cd - dt)
        if cv.is_down("space") and s.cd <= 0:
            s.cd = 0.17
            b = self.cv.Entity(s.x + math.cos(s.angle) * 14, s.y + math.sin(s.angle) * 14,
                               s.vx + math.cos(s.angle) * 540, s.vy + math.sin(s.angle) * 540, r=2.6)
            self.bullets.append(b)
            self.sfx("shoot")
        # пули
        for b in self.bullets:
            self.move_wrap(b, dt)
            if b.age > 1.05:
                b.alive = False
        # астероиды
        for r in self.rocks:
            self.move_wrap(r, dt)
            r.angle += r.spin * dt
        self.collide()
        self.bullets = [b for b in self.bullets if b.alive]
        if not self.rocks and self.state == "play":
            self.score += 100 * self.wave
            self.spawn_wave()

    def move_wrap(self, e, dt):
        e.move(dt)
        e.x = self.cv.wrap(e.x, -e.r, self.w + e.r)
        e.y = self.cv.wrap(e.y, -e.r, self.h + e.r)

    def collide(self):
        cv, s = self.cv, self.ship
        for b in self.bullets:
            if not b.alive:
                continue
            for r in self.rocks:
                if r.alive and cv.circles_hit(b, r):
                    b.alive = r.alive = False
                    self.break_rock(r)
                    break
        self.rocks = [r for r in self.rocks if r.alive]
        if s.invuln <= 0:
            for r in self.rocks:
                if cv.circles_hit(s, r):
                    self.ship_hit()
                    break

    def break_rock(self, r):
        self.score += POINTS[r.size]
        self.parts.emit(r.x, r.y, 10 + r.size * 6, 150, 0.8, self.colors["text_muted"], 2.6)
        self.sfx("boom" if r.size == 3 else "small")
        self.shake = max(self.shake, 0.12 * r.size)
        if r.size > 1:
            for _ in range(2):
                self.rocks.append(self.make_rock(r.x, r.y, r.size - 1))

    def ship_hit(self):
        s = self.ship
        self.parts.emit(s.x, s.y, 46, 260, 1.1, "#ff7a45", 3.4)
        self.parts.emit(s.x, s.y, 24, 180, 0.9, "#ffffff", 2.2)
        self.sfx("die")
        self.shake = 0.7
        s.lives -= 1
        if s.lives <= 0:
            self.state = "over"
            if self.score > self.hi:
                self.hi = self.score
                self.api.settings.set("hi", self.hi)
            return
        s.x, s.y, s.vx, s.vy, s.invuln = self.w / 2, self.h / 2, 0, 0, 2.6
        s.angle = -math.pi / 2

    # ------------------------------------------------------------ рисование
    def draw(self, p, w, h):
        D, c = self.cv.Draw, self.colors
        accent, text, muted = c["accent_hover"], c["text"], c["text_muted"]
        t = self.c.time
        if self.shake > 0:
            p.translate(random.uniform(-1, 1) * self.shake * 10, random.uniform(-1, 1) * self.shake * 10)
        self.stars.draw(p, t)
        # астероиды
        for r in self.rocks:
            D.polygon(p, r.pts, fill="rgba(160,170,200,0.07)", stroke=muted, width=2.0, x=r.x, y=r.y, angle=r.angle)
        # пули
        for b in self.bullets:
            D.glow_circle(p, b.x, b.y, 2.6, "#ffe066", 3.2)
        self.parts.draw(p)
        # корабль
        s = self.ship
        if self.state == "play" and not (s.invuln > 0 and int(t * 12) % 2 == 0):
            body = [(16, 0), (-11, -10), (-6, 0), (-11, 10)]
            if self.c.is_down("up", "w") and not self.paused:
                flame = random.uniform(10, 20)
                D.polygon(p, [(-7, -4), (-7 - flame, 0), (-7, 4)], fill="#ffb347", x=s.x, y=s.y, angle=s.angle)
            D.glow_circle(p, s.x, s.y, 3, accent, 4.5)
            D.polygon(p, body, fill="rgba(0,229,255,0.12)", stroke=accent, width=2.4, x=s.x, y=s.y, angle=s.angle)
            if s.invuln > 0:
                D.circle(p, s.x, s.y, 22, stroke="rgba(120,220,255,0.45)", width=1.5)
        p.resetTransform()
        # HUD
        D.text(p, 18, 14, f"СЧЁТ  {self.score}", 18, text, bold=True)
        D.text(p, w / 2, 14, f"РЕКОРД  {max(self.hi, self.score)}", 15, muted, align="center")
        D.text(p, w - 18, 14, f"ВОЛНА {self.wave}", 15, muted, align="right")
        for i in range(max(0, s.lives)):
            D.polygon(p, [(9, 0), (-6, -5.5), (-3, 0), (-6, 5.5)], stroke=accent, width=1.8,
                      x=w - 24 - i * 24, y=52, angle=-math.pi / 2)
        D.text(p, 18, h - 26, "← → поворот   ↑ тяга   ↓ тормоз   Пробел огонь   P пауза   M звук " +
               ("🔊" if self.sound else "🔇"), 12, muted)
        if self.state == "menu":
            D.text(p, w / 2, h * 0.30, "К О С М О Л Ё Т", 52, accent, align="center", bold=True)
            D.text(p, w / 2, h * 0.30 + 66, "Вы — пилот. Вокруг астероиды. Лаунчер — ваш корабль.", 16, text, align="center")
            if int(t * 2) % 2 == 0:
                D.text(p, w / 2, h * 0.62, "нажмите ПРОБЕЛ", 22, text, align="center", bold=True)
        elif self.state == "over":
            D.text(p, w / 2, h * 0.34, "КОРАБЛЬ УНИЧТОЖЕН", 40, c["danger"], align="center", bold=True)
            D.text(p, w / 2, h * 0.34 + 56, f"счёт {self.score}   ·   волна {self.wave}", 20, text, align="center")
            if int(t * 2) % 2 == 0:
                D.text(p, w / 2, h * 0.62, "ПРОБЕЛ — ещё раз", 20, text, align="center", bold=True)
        elif self.paused:
            D.text(p, w / 2, h * 0.45, "ПАУЗА", 44, text, align="center", bold=True)


class Addon(AddonBase):
    def on_load(self, api):
        self.api = api
        self.game = Game(api)
        api.ui.add_tab(self.game.c, "🚀 Космолёт")
        goto = lambda: (api.ui.select_tab("🚀 Космолёт"), self.game.c.setFocus())
        api.ui.add_burger_action("🚀 Космолёт", goto)
        api.commands.register("play", "Играть в Космолёт", goto, keywords="игра аркада астероиды",
                              icon="🚀", group="Развлечения")

    def on_unload(self):
        pass   # холст, команды, меню и подписки уберутся сами
