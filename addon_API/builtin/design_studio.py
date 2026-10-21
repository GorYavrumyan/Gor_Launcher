"""
Студия дизайна: настраивайте лаунчер мышью, а она сама пишет код вашего оформления.

* Все изменения видны сразу (живой предпросмотр).
* Внизу — код `api.design`, который воспроизводит ваш результат. Студия применяет оформление
  ИМЕННО этим кодом, поэтому экспорт гарантированно даёт то же самое.
* Экспорт: тема (themes/), готовый аддон (addons/), код в буфер, рецепт .json.

Написана целиком через публичный addon_API.
"""

import os
import re
import json
import random

from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QTabWidget, QWidget, QFormLayout, QComboBox, QCheckBox,
    QSlider, QSpinBox, QDoubleSpinBox, QPushButton, QLabel, QLineEdit, QPlainTextEdit, QFileDialog,
    QColorDialog, QGridLayout,
)
from PyQt6.QtGui import QColor, QFont

from addon_API import AddonBase
from addon_API.themes import PROJECT_ROOT

DEFAULT = {
    "preset": "",
    "accent_on": False, "accent": "#ff7a18", "palette_on": False, "mode": "dark", "tint": 0.12,
    "radius_mode": "", "radius_value": 1.0,
    "font_family": "", "font_size": 0, "font_scale": 1.0,
    "buttons": "", "tabs": "", "inputs": "", "scrollbars": "",
    "cards": "", "card_radius": 20,
    "fx_shadow": False, "fx_hover_glow": False, "fx_glow_run": False,
    "layers": [],
    "window_opacity": 1.0,
}

LAYERS = {
    "particles:stars": ("звёзды", 'd.particles("stars", 70)'),
    "particles:snow": ("снег", 'd.particles("snow", 80)'),
    "particles:fireflies": ("светлячки", 'd.particles("fireflies", 36, "{{accent_hover}}", 0.8)'),
    "vignette": ("виньетка", "d.vignette(0.5)"),
    "scanlines": ("сканлайны", "d.scanlines(3, 0.10)"),
    "grid": ("сетка", 'd.grid(44, "{{accent}}", 0.08)'),
    "noise": ("зерно", "d.noise(0.05)"),
    "gradient": ("плывущий градиент", 'd.animated_gradient(["{{accent}}", "#7a2dff", "#00d4ff"], 14000, 0.14)'),
}


def recipe_to_lines(r):
    """Рецепт -> строки Python с вызовами api.design (d). Их же выполняет и студия, и экспортированный аддон."""
    L = []
    if r["preset"]:
        L.append(f'd.preset({r["preset"]!r}, clear=False)')
    if r["accent_on"]:
        if r["palette_on"]:
            L.append(f'd.palette({r["accent"]!r}, {r["mode"]!r}, {round(float(r["tint"]), 2)})')
        else:
            L.append(f'd.accent({r["accent"]!r})')
    if r["radius_mode"] == "scale":
        L.append(f'd.radius(scale={round(float(r["radius_value"]), 2)})')
    elif r["radius_mode"] == "px":
        L.append(f'd.radius(px={int(round(float(r["radius_value"])))})')
    if r["font_family"] or r["font_size"]:
        L.append(f'd.font({(r["font_family"] or None)!r}, {(int(r["font_size"]) or None)!r})')
    if abs(float(r["font_scale"]) - 1.0) > 0.01:
        L.append(f'd.font_scale({round(float(r["font_scale"]), 2)})')
    for key in ("buttons", "tabs", "inputs"):
        if r[key]:
            L.append(f'd.{key}({r[key]!r})')
    if r["scrollbars"]:
        L.append(f'd.scrollbars(style={r["scrollbars"]!r})')
    if r["cards"]:
        cr = int(r["card_radius"])
        L.append(f'd.cards(radius={cr}, glass={r["cards"] == "glass"})')
        L.append(f'd.covers(radius={max(0, int(cr * 0.7))})')
    if r["fx_shadow"]:
        L.append('d.shadow("GameCard", blur=26, dy=8)')
    if r["fx_hover_glow"]:
        L.append('d.hover_glow("GameCard", "{{accent}}", 24)')
    if r["fx_glow_run"]:
        L.append('d.glow("RunGameBtn", "{{accent}}", 16, pulse_ms=2400)')
    for key in r["layers"]:
        if key in LAYERS:
            L.append(LAYERS[key][1])
    if float(r["window_opacity"]) < 0.995:
        L.append(f'd.window_opacity({round(float(r["window_opacity"]), 2)})')
    return L


def recipe_to_addon_code(r, title):
    body = "\n".join("            " + line for line in recipe_to_lines(r)) or "            pass"
    return (f'"""{title} — создано в Студии дизайна (addon_API)."""\n\n'
            "from addon_API import AddonBase\n\n\n"
            "class Addon(AddonBase):\n"
            "    def on_load(self, api):\n"
            "        d = api.design\n"
            "        with d.batch():\n" + body + "\n\n"
            "    def on_unload(self):\n"
            "        pass   # api.design откатит всё сам\n")


def slugify(name):
    s = re.sub(r"[^\w\-]+", "_", name.strip().lower(), flags=re.UNICODE).strip("_")
    return s or "my_style"


class StudioDialog(QDialog):
    def __init__(self, api):
        super().__init__(api.launcher)
        self.api, self.d = api, api.design
        self.r = json.loads(json.dumps(DEFAULT))
        self.setWindowTitle("🎛 Студия дизайна")
        self.resize(860, 640)
        self.controls = {}
        self._timer = QTimer(self)
        self._timer.setSingleShot(True)
        self._timer.timeout.connect(self.apply)

        root = QVBoxLayout(self)
        tabs = QTabWidget()
        tabs.addTab(self._tab_base(), "Основа")
        tabs.addTab(self._tab_shape(), "Форма")
        tabs.addTab(self._tab_text(), "Текст")
        tabs.addTab(self._tab_fx(), "Эффекты и слои")
        tabs.addTab(self._tab_export(), "Экспорт")
        root.addWidget(tabs, 3)
        root.addWidget(QLabel("Код этого оформления (api.design) — именно он сейчас применён:"))
        self.code = QPlainTextEdit()
        self.code.setReadOnly(True)
        f = QFont("Consolas")
        f.setStyleHint(QFont.StyleHint.Monospace)
        f.setPointSize(10)
        self.code.setFont(f)
        root.addWidget(self.code, 2)
        self.sync()

    # ------------------------------------------------------------ рецепт
    def set(self, **kw):
        """Изменить рецепт программно (и из интерфейса): set(preset="neon", accent_on=True, ...)."""
        for k, v in kw.items():
            if k not in self.r:
                raise KeyError(f"Нет параметра '{k}'. Есть: {', '.join(self.r)}")
            self.r[k] = v
        self.sync()
        self.apply()

    def _changed(self, key, value):
        self.r[key] = value
        self._timer.start(130)           # применяем не на каждый пиксель ползунка

    def apply(self):
        lines = recipe_to_lines(self.r)
        self.code.setPlainText("d = api.design\nwith d.batch():\n" + "\n".join("    " + l for l in lines)
                               if lines else "# ничего не изменено — это стандартное оформление")
        d = self.d
        d.reset()
        ns = {"d": d}
        with d.batch():
            for line in lines:
                try:
                    exec(line, ns)
                except Exception as e:
                    self.code.appendPlainText(f"# ⚠ ошибка в строке «{line}»: {e}")

    # ------------------------------------------------------------ привязка виджетов
    def _combo(self, key, options, labels=None):
        c = QComboBox()
        for i, o in enumerate(options):
            c.addItem((labels[i] if labels else o) or "— не менять —", o)
        c.currentIndexChanged.connect(lambda i, c=c, k=key: self._changed(k, c.itemData(i)))
        self.controls[key] = c
        return c

    def _check(self, key, text):
        c = QCheckBox(text)
        c.toggled.connect(lambda v, k=key: self._changed(k, v))
        self.controls[key] = c
        return c

    def _slider(self, key, lo, hi, scale=100.0):
        s = QSlider(Qt.Orientation.Horizontal)
        s.setRange(lo, hi)
        s.valueChanged.connect(lambda v, k=key: self._changed(k, v / scale))
        s._scale = scale
        self.controls[key] = s
        return s

    def _spin(self, key, lo, hi, step=1, double=False):
        s = QDoubleSpinBox() if double else QSpinBox()
        s.setRange(lo, hi)
        s.setSingleStep(step)
        s.valueChanged.connect(lambda v, k=key: self._changed(k, v))
        self.controls[key] = s
        return s

    def sync(self):
        """Показать значения рецепта в виджетах (без повторного применения)."""
        for key, w in self.controls.items():
            w.blockSignals(True)
            v = self.r[key]
            if isinstance(w, QComboBox):
                i = w.findData(v)
                w.setCurrentIndex(max(0, i))
            elif isinstance(w, QCheckBox):
                w.setChecked(bool(v))
            elif isinstance(w, QSlider):
                w.setValue(int(round(float(v) * w._scale)))
            elif isinstance(w, (QSpinBox, QDoubleSpinBox)):
                w.setValue(v)
            elif isinstance(w, QLineEdit):
                w.setText(str(v))
            w.blockSignals(False)
        for key, w in self.layer_checks.items():
            w.blockSignals(True)
            w.setChecked(key in self.r["layers"])
            w.blockSignals(False)
        self._paint_accent()

    # ------------------------------------------------------------ вкладки
    def _tab_base(self):
        w = QWidget()
        f = QFormLayout(w)
        f.addRow("Готовый стиль", self._combo("preset", [""] + self.d.presets()))
        f.addRow(self._check("accent_on", "Задать свой акцентный цвет"))
        self.accent_btn = QPushButton("выбрать цвет…")
        self.accent_btn.clicked.connect(self._pick_accent)
        f.addRow("Акцент", self.accent_btn)
        f.addRow(self._check("palette_on", "Построить из него ВСЮ палитру"))
        f.addRow("Режим палитры", self._combo("mode", ["dark", "light"], ["тёмная", "светлая"]))
        f.addRow("Подкраска фона", self._slider("tint", 0, 40))
        dice = QPushButton("🎲 Случайный стиль")
        dice.clicked.connect(self.randomize)
        f.addRow(dice)
        return w

    def _tab_shape(self):
        w = QWidget()
        f = QFormLayout(w)
        f.addRow("Скругления", self._combo("radius_mode", ["", "scale", "px"], ["", "множитель", "пиксели"]))
        f.addRow("Значение", self._spin("radius_value", 0, 30, 0.1, double=True))
        f.addRow("Карточки игр", self._combo("cards", ["", "solid", "glass"], ["", "плотные", "стеклянные"]))
        f.addRow("Радиус карточек", self._spin("card_radius", 0, 40))
        f.addRow("Кнопки", self._combo("buttons", [""] + self.d.button_styles()))
        f.addRow("Вкладки", self._combo("tabs", ["", "pill", "underline", "boxed", "segmented", "minimal"]))
        f.addRow("Поля ввода", self._combo("inputs", ["", "filled", "outline", "underline", "glass"]))
        f.addRow("Полосы прокрутки", self._combo("scrollbars", ["", "rounded", "thin", "hidden"]))
        return w

    def _tab_text(self):
        w = QWidget()
        f = QFormLayout(w)
        fam = self._combo("font_family", ["", "Consolas", "Segoe UI", "Georgia", "Courier New", "Arial",
                                          "Verdana", "Comic Sans MS", "Trebuchet MS"])
        f.addRow("Шрифт", fam)
        f.addRow("Размер (0 — не менять)", self._spin("font_size", 0, 24))
        f.addRow("Масштаб всех шрифтов", self._slider("font_scale", 80, 150))
        return w

    def _tab_fx(self):
        w = QWidget()
        g = QGridLayout(w)
        g.addWidget(QLabel("<b>Эффекты</b>"), 0, 0)
        g.addWidget(self._check("fx_shadow", "тень под карточками"), 1, 0)
        g.addWidget(self._check("fx_hover_glow", "свечение карточек при наведении"), 2, 0)
        g.addWidget(self._check("fx_glow_run", "пульсирующее свечение кнопки «Запустить»"), 3, 0)
        g.addWidget(QLabel("<b>Слои поверх окна</b>"), 0, 1)
        self.layer_checks = {}
        for i, (key, (title, _)) in enumerate(LAYERS.items()):
            c = QCheckBox(title)
            c.toggled.connect(lambda on, k=key: self._toggle_layer(k, on))
            self.layer_checks[key] = c
            g.addWidget(c, 1 + i, 1)
        g.addWidget(QLabel("Прозрачность окна"), 5, 0)
        g.addWidget(self._slider("window_opacity", 40, 100), 6, 0)
        g.setRowStretch(12, 1)
        return w

    def _tab_export(self):
        w = QWidget()
        v = QVBoxLayout(w)
        row = QHBoxLayout()
        row.addWidget(QLabel("Название:"))
        self.name = QLineEdit("Мой стиль")
        row.addWidget(self.name, 1)
        v.addLayout(row)
        for text, fn in (("💾 Сохранить как тему (themes/)", self.export_theme),
                         ("🧩 Установить как аддон (addons/)", self.export_addon),
                         ("📋 Копировать код в буфер", self.copy_code),
                         ("📤 Сохранить рецепт (.json)", self.save_recipe),
                         ("📥 Загрузить рецепт (.json)", self.load_recipe),
                         ("♻ Сбросить всё", self.reset_recipe)):
            b = QPushButton(text)
            b.clicked.connect(fn)
            v.addWidget(b)
        self.status = QLabel("")
        self.status.setWordWrap(True)
        v.addWidget(self.status)
        v.addStretch(1)
        return w

    # ------------------------------------------------------------ действия
    def _paint_accent(self):
        col = self.r["accent"]
        self.accent_btn.setStyleSheet("QPushButton { background: %s; color: %s; }" % (
            col, self.d.color.contrast_text(col)))

    def _pick_accent(self):
        c = QColorDialog.getColor(QColor(self.r["accent"]), self, "Акцентный цвет")
        if c.isValid():
            self.set(accent=c.name(), accent_on=True)

    def _toggle_layer(self, key, on):
        layers = [x for x in self.r["layers"] if x != key]
        if on:
            layers.append(key)
        self._changed("layers", layers)

    def randomize(self):
        rnd = random.Random()
        self.set(preset=rnd.choice([""] + self.d.presets()), accent_on=True, accent=self.d.color.rainbow(rnd.random()),
                 palette_on=rnd.random() < 0.6, mode="dark", tint=round(rnd.uniform(0.04, 0.25), 2),
                 radius_mode="scale", radius_value=round(rnd.uniform(0.5, 1.7), 1),
                 buttons=rnd.choice([""] + self.d.button_styles()), tabs=rnd.choice(["", "pill", "underline", "segmented"]),
                 cards=rnd.choice(["", "glass", "solid"]), card_radius=rnd.choice([8, 16, 24, 30]),
                 layers=rnd.sample(list(LAYERS), rnd.choice([0, 1, 2])), fx_hover_glow=rnd.random() < 0.5)

    def reset_recipe(self):
        self.r = json.loads(json.dumps(DEFAULT))
        self.sync()
        self.apply()
        self._say("Сброшено — стандартное оформление")

    def _say(self, text):
        self.status.setText(text)
        self.api.toast(text)

    def export_theme(self):
        name = self.name.text().strip() or "Мой стиль"
        tid = self.d.save_as_theme(name, author="Студия дизайна")
        acc = self.api.themes.account_name()
        where = f"accounts/{acc}/themes/{tid}/" if acc else f"themes/{tid}/"
        head = (f"Тема сохранена для аккаунта «{acc}»: {where}" if acc else f"Тема сохранена: {where}")
        self._say(head + " — выберите её в Theme Studio (🎨). "
                  "Эффекты и слои в тему не входят — для них экспортируйте аддон.")
        return tid

    def install_addon(self, name=None):
        name = name or self.name.text().strip() or "Мой стиль"
        base = slugify(name)
        root, folder, n = os.path.join(PROJECT_ROOT, "addons"), base, 1
        while os.path.exists(os.path.join(root, folder)):
            n += 1
            folder = f"{base}_{n}"
        path = os.path.join(root, folder)
        os.makedirs(os.path.join(path, "core"))
        with open(os.path.join(path, "config.json"), "w", encoding="utf-8") as f:
            json.dump({"name": name, "version": "1.0", "author": "Студия дизайна",
                       "description": "Оформление, созданное в Студии дизайна (addon_API).",
                       "start_file": "main.py", "min_api": 1}, f, ensure_ascii=False, indent=2)
        with open(os.path.join(path, "core", "main.py"), "w", encoding="utf-8") as f:
            f.write(recipe_to_addon_code(self.r, name))
        return path

    def export_addon(self):
        path = self.install_addon()
        self._say(f"Аддон создан: {path}\nВключите его в Control Center и перезапустите лаунчер.")

    def copy_code(self):
        self.api.system.clipboard_set(recipe_to_addon_code(self.r, self.name.text() or "Мой стиль"))
        self._say("Код аддона скопирован в буфер обмена")

    def save_recipe(self):
        path, _ = QFileDialog.getSaveFileName(self, "Сохранить рецепт", "style.json", "JSON (*.json)")
        if path:
            with open(path, "w", encoding="utf-8") as f:
                json.dump(self.r, f, ensure_ascii=False, indent=2)
            self._say("Рецепт сохранён: " + path)

    def load_recipe(self, path=None):
        path = path or QFileDialog.getOpenFileName(self, "Загрузить рецепт", "", "JSON (*.json)")[0]
        if path:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
            self.r = {**json.loads(json.dumps(DEFAULT)), **{k: v for k, v in data.items() if k in DEFAULT}}
            self.sync()
            self.apply()
            self._say("Рецепт загружен")


class Addon(AddonBase):
    def on_load(self, api):
        self.dialog = None

        def open_studio():
            if self.dialog is None:
                self.dialog = StudioDialog(api)
                self.dialog.apply()
            self.dialog.show()
            self.dialog.raise_()
        self.open_studio = open_studio
        api.ui.add_burger_action("🎛 Студия дизайна", open_studio)
        api.commands.register("studio", "Студия дизайна (настроить оформление мышью)", open_studio,
                              keywords="тема стиль цвета конструктор оформление", icon="🎛", group="Оформление")

    def on_unload(self):
        if self.dialog is not None:
            self.dialog.close()
            self.dialog.deleteLater()
