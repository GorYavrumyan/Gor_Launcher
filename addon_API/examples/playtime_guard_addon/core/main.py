import datetime

from PyQt6.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton

from addon_API import AddonBase, Events

DAYS = ["Пн", "Вт", "Ср", "Чт", "Пт", "Сб", "Вс"]


class Addon(AddonBase):
    def on_load(self, api):
        self.api = api
        self.sessions = api.db.collection("sessions")     # своя база аддона

        # --- вкладка: сводка + график за неделю + таблица ---
        page = QWidget()
        lay = QVBoxLayout(page)
        self.summary = QLabel()
        self.summary.setObjectName("GuardSummary")
        lay.addWidget(self.summary)
        self.chart = api.ui.chart("bar", [], "Минут игры за 7 дней", unit="мин")
        lay.addWidget(self.chart, 2)
        self.table = api.ui.table(["Игра", "Начало", "Минут"])
        lay.addWidget(self.table, 2)
        row = QHBoxLayout()
        b = QPushButton("⚙ Настройки")
        b.clicked.connect(self.settings)
        row.addWidget(b)
        row.addStretch(1)
        lay.addLayout(row)
        api.ui.add_tab(page, "⏱ Время")

        # --- перехват запуска игры: лимит в день ---
        api.before("before_game_launch", self.check_limit)
        # --- запись сессий ---
        api.on(Events.GAME_FINISHED, self.record)
        # --- напоминание по расписанию ---
        api.schedule.at(api.settings.get("remind_at", "23:00"),
                        lambda: api.notify("Уже поздно — не пора ли закончить на сегодня?"))
        # --- команда и сервис для других аддонов ---
        api.commands.register("today", "Сколько я сегодня играл", self.show_today, icon="⏱", group="Время")
        api.expose("today_minutes", self.today_minutes)
        self.refresh()

    # ------------------------------------------------------------ данные
    @staticmethod
    def day(ts=None):
        return (ts or datetime.datetime.now()).strftime("%Y-%m-%d")

    def today_minutes(self):
        return self.sessions.sum("seconds", {"day": self.day()}) // 60

    def record(self, duration, game):
        now = datetime.datetime.now()
        self.sessions.insert({"game": game.get("name", "?"), "seconds": int(duration),
                              "day": self.day(now), "time": now.strftime("%H:%M")})
        self.refresh()

    # ------------------------------------------------------------ перехватчик
    def check_limit(self, game):
        s = self.api.settings
        if not s.get("enabled", True):
            return True
        used, limit = self.today_minutes(), int(s.get("daily_limit_min", 180))
        if used < limit:
            return True
        return self.api.ui.confirm(
            f"Сегодня вы уже играли {used} мин (лимит {limit}).\nВсё равно запустить «{game.get('name')}»?")

    # ------------------------------------------------------------ интерфейс
    def refresh(self):
        today = datetime.date.today()
        data = []
        for i in range(6, -1, -1):
            d = today - datetime.timedelta(days=i)
            mins = self.sessions.sum("seconds", {"day": d.strftime("%Y-%m-%d")}) // 60
            data.append((f"{DAYS[d.weekday()]} {d.day}", mins))
        self.chart.set_data(data)
        limit = int(self.api.settings.get("daily_limit_min", 180))
        used = self.today_minutes()
        self.summary.setText(f"Сегодня: {used} мин из {limit}  ·  осталось {max(0, limit - used)} мин")
        rows = self.sessions.find({"day": self.day()}, sort="_id", reverse=True, limit=20)
        self.api.ui.fill_table(self.table, [[r["game"], r["time"], r["seconds"] // 60] for r in rows])

    def show_today(self):
        self.api.toast(f"⏱ Сегодня сыграно: {self.today_minutes()} мин")

    def settings(self):
        s = self.api.settings
        res = self.api.ui.form("Страж времени", [
            {"key": "enabled", "label": "Включить лимит", "type": "bool"},
            {"key": "daily_limit_min", "label": "Лимит в день, минут", "type": "int", "min": 5, "max": 1440},
            {"key": "remind_at", "label": "Напоминание в (ЧЧ:ММ)", "type": "text"},
        ], s.all())
        if res:
            for k, v in res.items():
                s.set(k, v)
            self.refresh()
            self.api.toast("Сохранено (время напоминания применится после перезагрузки аддона)")

    def on_unload(self):
        pass   # вкладка, перехватчик, расписание, сервис, команда - всё откатится само
