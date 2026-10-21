"""Базовый класс для аддонов нового стиля."""


class AddonBase:
    """
    Пример:

        from addon_API import AddonBase

        class Addon(AddonBase):
            def on_load(self, api):
                api.ui.add_header_button("⭐", lambda: api.ui.toast("Привет!"))

            def on_unload(self):
                pass   # всё, созданное через api, уберётся само
    """
    api = None

    def on_load(self, api):
        pass

    def on_unload(self):
        pass
