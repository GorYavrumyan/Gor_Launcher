"""
Конструктор стилей и готовые пресеты компонентов (api.design.*).

Везде, где принимается цвет, работают шаблоны, которые сами следуют за темой:
    "{{accent}}"  "{{accent@25}}" (прозрачность 25%)  "{{surface+8}}" (светлее)  "{{bg-5}}" (темнее)
Роли: bg surface surface_alt surface_hover border text text_muted accent
      accent_dark accent_hover danger warning success editor_bg editor_accent

Повторный вызов того же пресета ЗАМЕНЯЕТ предыдущий (а не накладывается).
Всё откатывается при выгрузке аддона или api.design.reset().
"""

from . import colors as C

_PX = {"border-radius", "font-size", "min-width", "min-height", "max-width", "max-height",
       "width", "height", "spacing", "border-width", "letter-spacing", "margin", "margin-left",
       "margin-right", "margin-top", "margin-bottom", "padding", "padding-left", "padding-right",
       "padding-top", "padding-bottom", "border-top-left-radius", "border-top-right-radius",
       "border-bottom-left-radius", "border-bottom-right-radius", "outline-radius"}
_ALIAS = {"bg": "background", "fg": "color", "radius": "border-radius", "size": "font-size",
          "weight": "font-weight", "font": "font-family"}


def _val(prop, v):
    if isinstance(v, (tuple, list)):
        if prop.startswith("border") and prop.count("-") <= 1 and len(v) == 2:
            return "%spx solid %s" % (v[0], v[1])
        return " ".join(_val(prop, x) for x in v)
    if isinstance(v, (int, float)) and not isinstance(v, bool):
        return "%spx" % int(v) if prop in _PX else str(v)
    if prop == "font-family" and isinstance(v, str) and '"' not in v and "," not in v:
        return '"%s"' % v
    return str(v)


def css_props(**kw):
    """css_props(radius=12, bg="{{accent}}", border=(2, "{{border}}"), padding=(6, 14))
       -> 'border-radius: 12px; background: {{accent}}; border: 2px solid {{border}}; padding: 6px 14px;'"""
    parts = []
    for k, v in kw.items():
        if v is None or v is False:
            continue
        prop = _ALIAS.get(k, k).replace("_", "-")
        parts.append("%s: %s;" % (prop, _val(prop, v)))
    return " ".join(parts)


def rule(selector, **kw):
    return "%s { %s }" % (selector, css_props(**kw))


def rules(mapping):
    """{selector: {props}} -> QSS"""
    return "\n".join(rule(sel, **props) for sel, props in mapping.items() if props)


def _cap(radius, cap):
    """Qt рисует квадратные углы, если радиус больше половины высоты элемента,
    поэтому для небольших элементов радиус ограничиваем."""
    return radius if radius is None else min(radius, cap)


class StyleMixin:
    # ------------------------------------------------------------ #
    # Базовые инструменты
    # ------------------------------------------------------------ #
    def _slot(self, name, qss, front=False):
        """Поставить QSS в именованный слот (старое содержимое слота заменяется)."""
        old = self._slots.pop(name, None)
        if old is not None:
            from ..themes import themes
            themes.remove_snippet(old)
        if qss:
            from ..themes import themes
            item = themes.add_snippet(self._api.root, qss, front)
            self._slots[name] = item
        return qss

    def qss(self, raw, slot=None):
        """Добавить произвольный QSS (с шаблонами {{accent}}...). slot - имя, чтобы потом заменить."""
        self._counter += 1
        return self._slot(slot or f"raw{self._counter}", raw)

    def css(self, selector, slot=None, hover=None, pressed=None, focus=None,
            disabled=None, checked=None, **props):
        """Правило из Python:
            design.css("QPushButton#RunGameBtn", radius=14, bg="{{accent}}",
                       hover={"bg": "{{accent_hover}}"}, pressed={"bg": "{{accent_dark}}"})"""
        blocks = {selector: props}
        for state, d in (("hover", hover), ("pressed", pressed), ("focus", focus),
                         ("disabled", disabled), ("checked", checked)):
            if d:
                blocks[f"{selector}:{state}"] = d
        return self.qss(rules(blocks), slot=slot or f"css:{selector}")

    def remove(self, slot):
        """Убрать стиль по имени слота (например 'buttons', 'cards', 'css:QLabel')."""
        old = self._slots.pop(slot, None)
        if old is not None:
            from ..themes import themes
            themes.remove_snippet(old)
            return True
        return False

    def widget_style(self, target, **props):
        """Inline-стиль на конкретные виджеты (по objectName/классу/виджету) + откат.
        Работает и на виджетах, которые появятся позже."""
        qss = css_props(**props)

        def apply(w):
            old = w.styleSheet()
            w.setStyleSheet((old + " " if old else "") + self._fill(qss))
            self._res.add(lambda w=w, old=old: _safe(lambda: w.setStyleSheet(old)))
        self.each(target, apply)

    def _fill(self, qss):
        from ..themes import _fill_template, themes
        return _fill_template(qss, themes.colors(), None)

    # ------------------------------------------------------------ #
    # Глобальные параметры
    # ------------------------------------------------------------ #
    def radius(self, scale=None, px=None):
        """Скругления ВСЕГО лаунчера: scale=1.5 (в полтора раза круглее) или px=0 (всё острое)."""
        from ..themes import themes
        if px is not None:
            themes.set_radius(self._api.root, "px", px)
        elif scale is not None:
            themes.set_radius(self._api.root, "scale", scale)

    def sharp(self):
        self.radius(px=0)

    def rounded(self, factor=1.6):
        self.radius(scale=factor)

    def font(self, family=None, size=None, weight=None, selector="QWidget"):
        """Шрифт интерфейса: design.font("Segoe UI", 13) / design.font(selector="QLabel#GameCardName", weight="bold")"""
        self.css(selector, slot=f"font:{selector}", font=family, size=size, weight=weight)

    def font_scale(self, factor):
        """Увеличить/уменьшить ВСЕ размеры шрифта в стилях лаунчера (1.2 = на 20% крупнее)."""
        from ..themes import themes
        themes.set_font_scale(self._api.root, factor)

    def global_style(self, **props):
        """Свойства для всех виджетов сразу: design.global_style(font="Consolas", color="#0f0")."""
        self.css("QWidget", slot="global", **props)

    # ------------------------------------------------------------ #
    # Кнопки
    # ------------------------------------------------------------ #
    _BUTTON_STYLES = {
        "flat":     (dict(bg="{{surface}}", color="{{text}}", border=(1, "{{border}}")),
                     dict(bg="{{accent}}", color="#ffffff", border=(1, "{{accent}}")),
                     dict(bg="{{accent_dark}}")),
        "solid":    (dict(bg="{{accent}}", color="#ffffff", border=(1, "{{accent}}")),
                     dict(bg="{{accent_hover}}", border=(1, "{{accent_hover}}")),
                     dict(bg="{{accent_dark}}")),
        "outline":  (dict(bg="transparent", color="{{accent}}", border=(2, "{{accent}}")),
                     dict(bg="{{accent@20}}"), dict(bg="{{accent@35}}")),
        "ghost":    (dict(bg="transparent", color="{{text}}", border=(1, "transparent")),
                     dict(bg="{{surface_hover}}"), dict(bg="{{surface}}")),
        "neon":     (dict(bg="{{accent@6}}", color="{{accent_hover}}", border=(2, "{{accent}}")),
                     dict(bg="{{accent@22}}", color="#ffffff", border=(2, "{{accent_hover}}")),
                     dict(bg="{{accent@38}}")),
        "glass":    (dict(bg="rgba(255,255,255,0.06)", color="{{text}}", border=(1, "rgba(255,255,255,0.16)")),
                     dict(bg="rgba(255,255,255,0.14)", border=(1, "{{accent}}")),
                     dict(bg="rgba(255,255,255,0.22)")),
        "gradient": (dict(bg=C.gradient(["{{accent_hover}}", "{{accent_dark}}"], 90), color="#ffffff",
                          border=(1, "{{accent_dark}}")),
                     dict(bg=C.gradient(["{{accent_hover+8}}", "{{accent}}"], 90)),
                     dict(bg=C.gradient(["{{accent_dark}}", "{{accent}}"], 90))),
        "pill":     (dict(bg="{{surface}}", color="{{text}}", border=(1, "{{border}}"), radius=18),
                     dict(bg="{{accent}}", color="#ffffff", border=(1, "{{accent}}")),
                     dict(bg="{{accent_dark}}")),
    }

    def button_styles(self):
        return list(self._BUTTON_STYLES)

    # кнопки со своим #id в style.qss: без них общий стиль их бы не перебил
    # (Stop / Success / Cancel - «смысловые», их цвет не трогаем)
    _NAMED_BUTTONS = ("RunGameBtn", "OpenFolderBtn", "GroupToggleBtn", "RestartBtn",
                      "TrayBtn", "BurgerMenuBtn", "PrimaryBtn", "ExportBtn", "PauseTimerBtn")

    def buttons(self, style="flat", radius=None, padding=None, font_size=None,
                font_weight=None, selector="QPushButton", include_named=True):
        """Стиль ВСЕХ кнопок (включая «Запустить», шапку и т.п.; include_named=False - только
        обычные). style: flat | solid | outline | ghost | neon | glass | gradient | pill"""
        normal, hover, pressed = self._BUTTON_STYLES[style]
        sels = [selector] + ([f"QPushButton#{n}" for n in self._NAMED_BUTTONS] if include_named else [])
        join = lambda suffix: ", ".join(s + suffix for s in sels)
        normal = dict(normal)
        normal.setdefault("radius", 10)
        if radius is not None:
            normal["radius"] = _cap(radius, 18)   # больше - Qt рисует квадратные углы
        normal.update(padding=padding, font_size=font_size, font_weight=font_weight)
        self._slot("buttons", rules({join(""): normal, join(":hover"): hover,
                                     join(":pressed"): pressed}))

    def play_button(self, style="solid", radius=14, color="{{success}}", hover=None, text="#ffffff"):
        """Кнопка «Запустить» на карточках игр (RunGameBtn)."""
        sel = "QPushButton#RunGameBtn"
        hv = hover or "{{success+8}}"
        if style == "outline":
            n = dict(bg="transparent", color=color, border=(2, color), radius=radius)
            h = dict(bg="{{success@20}}")
        elif style == "gradient":
            n = dict(bg=C.gradient([hv, color], 90), color=text, border="none", radius=radius)
            h = dict(bg=C.gradient([hv + "", hv], 90))
        else:
            n = dict(bg=color, color=text, border="none", radius=radius)
            h = dict(bg=hv)
        self._slot("play_button", rules({sel: n, sel + ":hover": h}))

    # ------------------------------------------------------------ #
    # Поля ввода / списки / меню / прочее
    # ------------------------------------------------------------ #
    def inputs(self, style="filled", radius=8, focus="{{accent}}", padding=None):
        """Поля ввода. style: filled | outline | underline | glass"""
        sel = "QLineEdit, QTextEdit, QPlainTextEdit, QSpinBox, QDoubleSpinBox"
        radius = _cap(radius, 15)
        base = dict(radius=radius, padding=padding)
        if style == "outline":
            n = dict(bg="transparent", border=(2, "{{border}}"), **base)
        elif style == "underline":
            n = dict(bg="transparent", border="none", border_bottom="2px solid {{border}}",
                     radius=0, padding=padding)
        elif style == "glass":
            n = dict(bg="rgba(255,255,255,0.06)", border=(1, "rgba(255,255,255,0.16)"), **base)
        else:
            n = dict(bg="{{surface}}", border=(1, "{{border}}"), **base)
        f = dict(border_color=focus)
        if style == "underline":
            f = dict(border_bottom="2px solid %s" % focus)
        self._slot("inputs", rules({sel: n,
                                    "QLineEdit:focus, QTextEdit:focus, QPlainTextEdit:focus, "
                                    "QSpinBox:focus, QDoubleSpinBox:focus": f}))

    def search_bar(self, radius=16, border="{{border}}", focus="{{warning}}", bg="{{surface}}", padding=None):
        sel = "QLineEdit#SearchBar"
        radius = _cap(radius, 16)
        self._slot("search_bar", rules({
            sel: dict(radius=radius, bg=bg, border=(1, border), padding=padding),
            sel + ":focus": dict(border=(1, focus))}))

    def combos(self, radius=8, bg="{{surface}}", border="{{border}}", hover="{{accent}}",
               popup_bg="{{surface_alt}}"):
        radius = _cap(radius, 15)
        self._slot("combos", rules({
            "QComboBox": dict(radius=radius, bg=bg, border=(1, border)),
            "QComboBox:hover, QComboBox:focus": dict(border=(1, hover)),
            "QComboBox QAbstractItemView": dict(bg=popup_bg, border=(1, border),
                                                selection_background_color=hover, outline="0")}))

    def checkboxes(self, size=18, radius=5, checked="{{accent}}", border="{{border}}"):
        self._slot("checkboxes", rules({
            "QCheckBox::indicator": dict(width=size, height=size, radius=radius,
                                         border=(2, border), bg="transparent"),
            "QCheckBox::indicator:hover": dict(border=(2, checked)),
            "QCheckBox::indicator:checked": dict(bg=checked, border=(2, checked))}))

    def lists(self, radius=10, item_radius=8, selected="{{accent}}", hover="{{surface_hover}}",
              bg="{{surface_alt}}", border="{{border}}", item_padding=6):
        self._slot("lists", rules({
            "QListWidget, QTreeWidget, QTableWidget": dict(radius=radius, bg=bg, border=(1, border), outline="0"),
            "QListWidget::item": dict(radius=item_radius, padding=item_padding),
            "QListWidget::item:hover": dict(bg=hover),
            "QListWidget::item:selected": dict(bg=selected, color="#ffffff")}))

    def menus(self, radius=10, bg="{{surface_alt}}", border="{{border}}", selected="{{accent}}",
              item_radius=6, padding="7px 22px"):
        self._slot("menus", rules({
            "QMenu": dict(bg=bg, border=(1, border), radius=radius, padding=6),
            "QMenu::item": dict(padding=padding, radius=item_radius, margin=2),
            "QMenu::item:selected": dict(bg=selected, color="#ffffff"),
            "QMenu::separator": dict(height=1, bg=border, margin="5px 8px")}))

    def tooltips(self, bg="{{surface}}", fg="{{text}}", border="{{accent}}", radius=8, padding=6):
        self._slot("tooltips", rules({"QToolTip": dict(bg=bg, color=fg, border=(1, border),
                                                       radius=radius, padding=padding)}))

    def progress(self, height=10, radius=None, bg="{{surface}}", fill="{{accent}}", gradient=True):
        r = radius if radius is not None else height // 2
        fill_bg = C.gradient(["{{accent_dark}}", "{{accent_hover}}"], 0) if gradient and fill == "{{accent}}" else fill
        self._slot("progress", rules({
            "QProgressBar": dict(height=height, max_height=height, radius=r, bg=bg, border="none",
                                 color="transparent", text_align="center"),
            "QProgressBar::chunk": dict(radius=r, bg=fill_bg)}))

    def dialogs(self, bg=None, radius=None):
        self._slot("dialogs", rules({"QDialog": dict(bg=bg, radius=radius)}))

    def labels(self, color=None, size=None, weight=None, selector="QLabel"):
        self._slot(f"labels:{selector}", rules({selector: dict(color=color, font_size=size, font_weight=weight)}))

    # ------------------------------------------------------------ #
    # Вкладки и скроллбары
    # ------------------------------------------------------------ #
    def tabs(self, style="pill", radius=10, spacing=4, selected="{{accent}}", padding="8px 18px",
             font_weight="bold"):
        """Вкладки. style: pill | underline | boxed | segmented | minimal"""
        radius = _cap(radius, 16)
        t, ts, th = "QTabBar::tab", "QTabBar::tab:selected", "QTabBar::tab:hover:!selected"
        common = dict(padding=padding, font_weight=font_weight, margin_right=spacing)
        if style == "underline":
            m = {t: dict(bg="transparent", color="{{text_muted}}", border="none",
                         border_bottom="3px solid transparent", radius=0, **common),
                 ts: dict(color="{{text}}", border_bottom=f"3px solid {selected}", bg="transparent"),
                 th: dict(color="{{text}}", bg="{{surface@50}}"),
                 "QTabWidget::pane": dict(border="none", border_top="1px solid {{border}}")}
        elif style == "boxed":
            m = {t: dict(bg="{{surface}}", color="{{text_muted}}", border=(1, "{{border}}"),
                         radius=0, border_bottom="none",
                         border_top_left_radius=radius, border_top_right_radius=radius, **common),
                 ts: dict(bg="{{surface_alt}}", color="{{text}}", border=(1, selected), border_bottom="none"),
                 th: dict(bg="{{surface_hover}}"),
                 "QTabWidget::pane": dict(border=(1, "{{border}}"), radius=radius)}
        elif style == "segmented":
            m = {t: dict(bg="{{surface}}", color="{{text_muted}}", border=(1, "{{border}}"),
                         radius=0, margin_right=0, padding=padding, font_weight=font_weight),
                 ts: dict(bg=selected, color="#ffffff", border=(1, selected)),
                 th: dict(bg="{{surface_hover}}"),
                 "QTabBar::tab:first": dict(border_top_left_radius=radius, border_bottom_left_radius=radius),
                 "QTabBar::tab:last": dict(border_top_right_radius=radius, border_bottom_right_radius=radius),
                 "QTabWidget::pane": dict(border="none")}
        elif style == "minimal":
            m = {t: dict(bg="transparent", color="{{text_muted}}", border="none", radius=0, **common),
                 ts: dict(color=selected, bg="transparent"),
                 th: dict(color="{{text}}"),
                 "QTabWidget::pane": dict(border="none")}
        else:  # pill
            m = {t: dict(bg="{{surface}}", color="{{text_muted}}", border=(1, "{{border}}"), radius=radius, **common),
                 ts: dict(bg=selected, color="#ffffff", border=(1, selected)),
                 th: dict(bg="{{surface_hover}}", color="{{text}}"),
                 "QTabWidget::pane": dict(border="none", border_top="1px solid {{border}}")}
        self._slot("tabs", rules(m))

    def scrollbars(self, width=10, radius=None, handle="{{border}}", hover="{{accent}}",
                   track="transparent", margin=2, style="rounded"):
        """Полосы прокрутки. style: rounded | thin | hidden"""
        if style == "hidden":
            self._slot("scrollbars", "QScrollBar:vertical, QScrollBar:horizontal { width: 0px; height: 0px; background: transparent; }")
            return
        if style == "thin":
            width, margin = 6, 1
        r = radius if radius is not None else width // 2
        v = "QScrollBar:vertical"
        h = "QScrollBar:horizontal"
        self._slot("scrollbars", rules({
            v: dict(width=width + margin * 2, bg=track, margin=0, border="none"),
            h: dict(height=width + margin * 2, bg=track, margin=0, border="none"),
            "QScrollBar::handle:vertical": dict(bg=handle, radius=r, min_height=30, margin=f"0px {margin}px"),
            "QScrollBar::handle:horizontal": dict(bg=handle, radius=r, min_width=30, margin=f"{margin}px 0px"),
            "QScrollBar::handle:vertical:hover, QScrollBar::handle:horizontal:hover": dict(bg=hover),
            "QScrollBar::add-line, QScrollBar::sub-line": dict(width=0, height=0, bg="none", border="none"),
            "QScrollBar::add-page, QScrollBar::sub-page": dict(bg="none")}))

    # ------------------------------------------------------------ #
    # Карточки игр, обложки, группы, шапка
    # ------------------------------------------------------------ #
    def cards(self, radius=20, border_width=1, border="{{surface_hover}}", hover="{{accent}}",
              background="{{surface_alt}}", hover_background=None, running="{{danger}}",
              focus="{{warning}}", glass=False):
        """Карточки игр и истории (GameCard / HistoryCard)."""
        sel = "QFrame#GameCard, QFrame#HistoryCard"
        hov = "QFrame#GameCard:hover, QFrame#HistoryCard:hover"
        if glass:
            background, border = "rgba(255,255,255,0.05)", "rgba(255,255,255,0.14)"
        self._slot("cards", rules({
            sel: dict(radius=radius, bg=background, border=(border_width, border)),
            hov: dict(border=(max(2, border_width), hover), bg=hover_background),
            "QFrame#GameCard:focus, QFrame#HistoryCard:focus": dict(border=(3, focus)),
            'QFrame#GameCard[running="true"], QFrame#GameCard[running="true"]:hover':
                dict(border=(2, running))}))

    def covers(self, radius=12, border_width=1, border="{{border}}", favorite="{{warning}}", bg="{{bg-2}}"):
        """Обложки игр (GameCardImage), у избранных своя рамка."""
        sel = "QLabel#GameCardImage"
        self._slot("covers", rules({
            sel: dict(radius=radius, bg=bg, border=(border_width, border)),
            sel + '[favorite="true"]': dict(border=(max(2, border_width), favorite))}))

    def card_text(self, name_color=None, name_size=None, name_weight=None, time_color=None, time_size=None):
        self._slot("card_text", rules({
            "QLabel#GameCardName": dict(color=name_color, font_size=name_size, font_weight=name_weight),
            "QLabel#GameCardTime": dict(color=time_color, font_size=time_size)}))

    def group_headers(self, color="{{text}}", size=None, weight="bold", button_bg=None, button_radius=None):
        self._slot("group_headers", rules({
            "QLabel#GroupTitleLabel": dict(color=color, font_size=size, font_weight=weight),
            "QPushButton#GroupToggleBtn": dict(bg=button_bg, radius=button_radius)}))

    def header(self, bg=None, border_bottom=None, radius=None, padding=None):
        """Шапка лаунчера (с кнопками ⟳ 🎨 ☰)."""
        bar = getattr(self.launcher, "header_bar", None)
        if bar is None:
            return
        if not bar.objectName():
            bar.setObjectName("GorHeaderBar")
            self._res.add(lambda: _safe(lambda: bar.setObjectName("")))
        self._slot("header", rules({"QWidget#%s" % bar.objectName(): dict(
            bg=bg, border_bottom=border_bottom, radius=radius, padding=padding)}))

    def search_and_sort(self, radius=14):
        self.search_bar(radius=radius)
        self.combos(radius=radius)

    def clear_style(self):
        """Убрать ВСЕ стили, добавленные через design (но оставить эффекты и анимации)."""
        from ..themes import themes
        for slot in list(self._slots):
            self.remove(slot)


def _safe(fn):
    try:
        fn()
    except RuntimeError:
        pass
