import datetime
from addon_API import AddonBase

SUNSET = {
    "name": "Закат", "author": "Пример аддона", "version": "1.0",
    "description": "Тёплые оранжевые тона",
    "colors": {
        "bg": "#140b08", "surface": "#24140e", "surface_alt": "#1c100b",
        "surface_hover": "#33201a", "border": "#4a2d22",
        "text": "#ffeede", "text_muted": "#b58f7a",
        "accent": "#ff7a18", "editor_bg": "#1c100b", "editor_accent": "#e0650c",
    },
}


class Addon(AddonBase):
    def on_load(self, api):
        self.api = api
        # Тема сохраняется в themes/sunset/ и сразу появляется в Theme Studio
        self.theme_id = api.themes.install("sunset", SUNSET)

        api.ui.add_burger_action("🌇 Включить тему «Закат»",
                                 lambda: api.themes.apply(self.theme_id), separator_before=True)

        def toggle_auto():
            on = not api.settings.get("auto_day_night", False)
            api.settings.set("auto_day_night", on)
            api.toast("Автосмена тем: " + ("включена" if on else "выключена"))
            self._auto()
        api.ui.add_burger_action("🌓 Автосмена день/ночь", toggle_auto)

        api.every(10 * 60 * 1000, self._auto)   # проверка раз в 10 минут
        self._auto()

    def _auto(self):
        if not self.api.settings.get("auto_day_night", False):
            return
        hour = datetime.datetime.now().hour
        want = "light" if 8 <= hour < 19 else self.theme_id
        if self.api.themes.current_id() != want:
            self.api.themes.apply(want)
