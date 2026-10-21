from addon_API import AddonBase


class Addon(AddonBase):
    def on_load(self, api):
        self.api = api
        self.d = api.design
        self.rainbow_on = False

        # --- пункты в меню ☰: по одному на каждый готовый стиль ---
        names = self.d.presets()
        for i, name in enumerate(names):
            api.ui.add_burger_action(f"🎨 Стиль: {name}", lambda n=name: self.apply(n),
                                     separator_before=(i == 0))
        api.ui.add_burger_action("🌈 Радужный акцент (вкл/выкл)", self.toggle_rainbow)
        api.ui.add_burger_action("🔍 Инспектор (Ctrl+Shift+клик)", lambda: self.d.inspector(True))
        api.ui.add_burger_action("♻ Сбросить дизайн аддона", self.clear)

        # --- запомнить выбранный стиль между запусками ---
        saved = api.settings.get("preset")
        if saved in names:
            api.later(0, lambda: self.apply(saved, toast=False))

    def apply(self, name, toast=True):
        self.rainbow_on = False
        self.d.preset(name)                               # весь лаунчер в новом облике
        self.d.appear("GameCard", "up", stagger=45)       # новые карточки выезжают каскадом
        self.d.pointer_on_buttons()                       # рука над кнопками
        self.api.settings.set("preset", name)
        if toast:
            self.api.toast(f"Стиль «{name}»: {self.d.preset_info(name)}")

    def toggle_rainbow(self):
        self.rainbow_on = not self.rainbow_on
        if self.rainbow_on:
            self.d.rainbow(period_ms=9000, fps=4)
        else:
            self.d.stop_color_animation()
            self.d.reset_colors()

    def clear(self):
        self.d.reset()
        self.api.settings.set("preset", None)
        self.api.toast("Дизайн сброшен")

    def on_unload(self):
        pass   # api.design откатывает всё сам
