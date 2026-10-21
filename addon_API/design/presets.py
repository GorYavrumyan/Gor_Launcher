"""
Готовые стили целиком: одна строка - весь лаунчер в новом облике.

    api.design.preset("neon")
    api.design.presets()          # список имён
Пресеты - это просто наборы вызовов api.design, поэтому их удобно читать,
копировать и дорабатывать под себя. Всё откатывается через api.design.reset().
"""


def _glass(d):
    d.buttons("glass", radius=14)
    d.inputs("glass", radius=12)
    d.search_bar(radius=16, bg="rgba(255,255,255,0.06)", border="rgba(255,255,255,0.14)")
    d.cards(radius=24, glass=True)
    d.covers(radius=16)
    d.tabs("pill", radius=14)
    d.scrollbars(style="thin")
    d.menus(radius=14)
    d.tooltips(radius=10)
    d.vignette(0.35)
    d.gradient_overlay(["{{accent}}", "#7a2dff"], 135, 0.10)


def _neon(d):
    d.buttons("neon", radius=8)
    d.inputs("outline", radius=8)
    d.search_bar(radius=10, border="{{accent@45}}", focus="{{accent_hover}}")
    d.cards(radius=16, border="{{accent@30}}", hover="{{accent_hover}}", background="{{bg+2}}")
    d.covers(radius=10, border="{{accent@30}}")
    d.tabs("underline")
    d.scrollbars(handle="{{accent@55}}", hover="{{accent_hover}}")
    d.progress()
    d.vignette(0.5)
    d.hover_glow("GameCard", "{{accent}}", 26)
    d.glow("RunGameBtn", "{{accent}}", 16, pulse_ms=2400)


def _minimal(d):
    d.radius(scale=0.5)
    d.buttons("ghost", radius=6)
    d.inputs("underline")
    d.tabs("minimal")
    d.cards(radius=10, border="{{surface_hover}}", background="{{surface}}", hover="{{border}}")
    d.covers(radius=8)
    d.scrollbars(style="thin")
    d.menus(radius=6)


def _cyberpunk(d):
    d.palette("#fcee0a", "dark", 0.05)
    d.set_color("danger", "#ff2a6d")
    d.sharp()
    d.font("Consolas", None)
    d.buttons("outline", radius=2)
    d.inputs("outline", radius=2)
    d.cards(radius=2, border="{{accent@28}}", hover="{{accent}}", background="{{bg+3}}")
    d.covers(radius=2)
    d.tabs("boxed", radius=2)
    d.scrollbars(radius=0, handle="{{accent@50}}", hover="{{accent}}")
    d.grid(48, "{{accent}}", 0.06)
    d.scanlines(3, 0.08)
    d.vignette(0.6)
    d.noise(0.03)
    d.hover_glow("GameCard", "{{accent}}", 22)


def _terminal(d):
    d.palette("#00e050", "dark", 0.05)
    d.set_colors({"text": "#33ff66", "text_muted": "#1fa044"})
    d.sharp()
    d.font("Consolas", None)
    d.buttons("outline", radius=0)
    d.inputs("outline", radius=0)
    d.cards(radius=0, border="{{accent@40}}", hover="{{accent}}", background="{{bg+1}}")
    d.covers(radius=0)
    d.tabs("boxed", radius=0)
    d.scrollbars(radius=0)
    d.scanlines(2, 0.16)
    d.vignette(0.5)


def _soft(d):
    d.palette("#7c9cff", "light", 0.06)
    d.buttons("solid", radius=18)
    d.inputs("filled", radius=14)
    d.search_bar(radius=16)
    d.cards(radius=28, border="{{border}}", hover="{{accent}}", background="{{surface}}")
    d.covers(radius=18)
    d.tabs("segmented", radius=14)
    d.scrollbars(style="thin", handle="{{border}}")
    d.menus(radius=14)
    d.shadow("GameCard", blur=26, dy=8, alpha=0.18)


def _aurora(d):
    d.buttons("glass", radius=14)
    d.cards(radius=22, glass=True)
    d.tabs("pill", radius=14)
    d.scrollbars(style="thin")
    d.animated_gradient(["{{accent}}", "#7a2dff", "#00d4ff"], 16000, 0.13)
    d.particles("fireflies", 34, "{{accent_hover}}", 0.8)
    d.vignette(0.4)


PRESETS = {
    "glass":     ("Стекло: полупрозрачные карточки, мягкая градиентная дымка", _glass),
    "neon":      ("Неон: контурные кнопки, свечение карточек при наведении", _neon),
    "minimal":   ("Минимализм: плоско, мало скруглений, тонкие линии", _minimal),
    "cyberpunk": ("Киберпанк: жёлтый акцент, сетка, сканлайны, острые углы", _cyberpunk),
    "terminal":  ("Терминал: зелёный на чёрном, моноширинный шрифт, ЭЛТ-строки", _terminal),
    "soft":      ("Мягкий светлый: пастельные тона, большие скругления, тени", _soft),
    "aurora":    ("Аврора: плывущий градиент и светлячки поверх стекла", _aurora),
}


class PresetMixin:
    def presets(self):
        """Имена готовых стилей."""
        return list(PRESETS)

    def preset_info(self, name=None):
        """{имя: описание} или описание одного пресета."""
        if name:
            return PRESETS[name][0]
        return {k: v[0] for k, v in PRESETS.items()}

    def preset(self, name, clear=True):
        """Применить готовый стиль целиком. clear=True - сначала убрать всё, что этот
        аддон менял через api.design, clear=False - наложить поверх."""
        if name not in PRESETS:
            raise KeyError(f"Нет пресета '{name}'. Доступны: {', '.join(PRESETS)}")
        if clear:
            self.reset()
        with self.batch():
            PRESETS[name][1](self)
