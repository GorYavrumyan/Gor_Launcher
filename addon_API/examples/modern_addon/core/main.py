from PyQt6.QtWidgets import QWidget, QVBoxLayout, QLabel

from addon_API import AddonBase, Events


class Addon(AddonBase):
    def on_load(self, api):
        self.api = api
        api.add_translations({
            "ru": {"title": "Статистика", "played": "Сыграно всего: {m} мин"},
            "en": {"title": "Stats", "played": "Total played: {m} min"},
        })

        # --- вкладка ---
        page = QWidget()
        lay = QVBoxLayout(page)
        self.label = QLabel()
        lay.addWidget(self.label)
        lay.addStretch(1)
        api.ui.add_tab(page, "📊 " + api.tr("title"))
        self._refresh()

        # --- кнопка в шапке и пункт в меню карточки игры ---
        api.ui.add_header_button("📊", lambda: api.toast(self.label.text()),
                                 tooltip=api.tr("title"))
        api.ui.add_card_action("📊 Сколько я в это играл?",
                               lambda game: api.toast(f"{game.get('name', '?')}"))

        # --- события ---
        api.on(Events.GAME_FINISHED, self._on_finished)

        # --- свой кусочек оформления (с подстановкой цвета темы) ---
        api.ui.add_style("QLabel#ModernAddonLabel { color: {{accent}}; font-size: 18px; }")
        self.label.setObjectName("ModernAddonLabel")

    def _on_finished(self, duration, game):
        total = self.api.settings.get("total_seconds", 0) + int(duration)
        self.api.settings.set("total_seconds", total)
        self._refresh()
        self.api.notify(f"{game.get('name', 'Игра')}: +{duration // 60} мин")

    def _refresh(self):
        minutes = self.api.settings.get("total_seconds", 0) // 60
        self.label.setText(self.api.tr("played", m=minutes))

    def on_unload(self):
        pass  # вкладка, кнопка, стиль и подписки уберутся сами
