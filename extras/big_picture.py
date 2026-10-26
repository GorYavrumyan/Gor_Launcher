"""
Режим Big Picture (ТВ / диван): крупный полноэкранный интерфейс, которым можно
управлять геймпадом (или клавиатурой), и запуск стрима через Moonlight.

Разделы (переключаются LB / RB):
  Библиотека - игры по группам, строка на группу
  Избранное  - игры с пометкой "избранное"
  Недавние   - последние запущенные игры (из истории)
  Стрим      - хост Sunshine -> приложение -> качество -> запуск Moonlight

Управление:            геймпад      клавиатура
  навигация            D-pad/стик   стрелки
  выбрать / запустить  A            Enter / Пробел
  назад / меню выхода  B            Esc / Backspace
  в избранное          X            F
  действия с игрой     Y            Y
  раздел назад/вперёд  LB / RB      Shift+Tab / Tab (PageUp/PageDown)
  главное меню         Start        M / F10

Пока идёт игра или стрим, окно прячется, ввод игнорируется (иначе геймпад управлял бы
и игрой, и меню одновременно), а после завершения интерфейс возвращается сам.

Окно не знает деталей лаунчера: ему нужен объект с интерфейсом GORLauncher
(games_info, active_sessions, launch_game_from_wheel, save_data, refresh_list).
"""
import os
import time

from PyQt6.QtCore import Qt, QTimer, QPropertyAnimation, QEasingCurve, QRectF, QThread, QTime, pyqtSignal
from PyQt6.QtGui import QColor, QPainter, QPainterPath, QPixmap
from PyQt6.QtWidgets import (QApplication, QFrame, QGraphicsDropShadowEffect, QHBoxLayout, QLabel, QPushButton,
                             QScrollArea, QSizePolicy, QStackedWidget, QTabBar, QVBoxLayout, QWidget)

from gamepad import GamepadReader
from lang_loader import tr

try:
    from launcher_utils import load_pixmap_cached
except Exception:  # запуск вне лаунчера (тесты)
    def load_pixmap_cached(path):
        return QPixmap(path) if path else QPixmap()

# =====================================================================
#  Тема: цвета берутся из активной темы лаунчера (Theme Studio), а не зашиты
# =====================================================================
_DEFAULT_COLORS = {
    "bg": "#0a0a0a", "surface": "#1a1a1a", "surface_alt": "#141414", "border": "#333333",
    "text": "#f0f0f0", "text_muted": "#888888", "accent": "#007acc", "accent_hover": "#0090ee",
    "accent_dark": "#005f9e", "warning": "#ffcc00", "danger": "#d9534f", "success": "#229954",
}


def _luminance(c):
    def lin(v):
        v /= 255.0
        return v / 12.92 if v <= 0.03928 else ((v + 0.055) / 1.055) ** 2.4
    return 0.2126 * lin(c.red()) + 0.7152 * lin(c.green()) + 0.0722 * lin(c.blue())


def contrast_ratio(a, b):
    la, lb = _luminance(QColor(a)), _luminance(QColor(b))
    return (max(la, lb) + 0.05) / (min(la, lb) + 0.05)


def ensure_contrast(fg, bg, minimum=4.5):
    """Подтягивает цвет текста к белому/чёрному ровно настолько, чтобы он читался на ТВ.
    Приглушённые цвета тем (например, тёмно-синий на тёмно-синем) на расстоянии дивана сливаются."""
    f, b = QColor(fg), QColor(bg)
    if not f.isValid():
        f = QColor("#ffffff")
    target = QColor("#ffffff") if _luminance(b) < 0.5 else QColor("#000000")
    for _ in range(30):
        if contrast_ratio(f, b) >= minimum:
            break
        f = QColor(int(f.red() + (target.red() - f.red()) * 0.12),
                   int(f.green() + (target.green() - f.green()) * 0.12),
                   int(f.blue() + (target.blue() - f.blue()) * 0.12))
    return f.name()


def on_color(bg):
    """Читаемый цвет текста ПОВЕРХ заданного фона."""
    return "#ffffff" if _luminance(QColor(bg)) < 0.45 else "#0b1220"


class Theme:
    """Палитра Big Picture = палитра активной темы лаунчера."""

    def __init__(self):
        self.c = dict(_DEFAULT_COLORS)
        self.text_ok = self.c["text"]
        self.muted_ok = self.c["text_muted"]

    def load(self):
        colors = {}
        try:
            from addon_API.themes import themes
            colors = themes.colors()
        except Exception:
            pass
        merged = dict(_DEFAULT_COLORS)
        for key, value in colors.items():
            if key in merged and QColor(value).isValid():
                merged[key] = value
        self.c = merged
        bg = merged["bg"]
        self.text_ok = ensure_contrast(merged["text"], bg, 3.0)        # как в теме, но не хуже 3:1
        self.muted_ok = ensure_contrast(merged["text_muted"], bg, 4.5)
        return self

    def __getitem__(self, key):
        return self.c[key]


THEME = Theme()

# --- палитра кнопок геймпада (стандартные цвета Xbox) ---
GREEN, RED, BLUE, YELLOW = "#3ecf6e", "#ff5d5d", "#4da3ff", "#f5c542"

TABS = ("library", "favorites", "recent", "stream")
CARD_SCALE = 0.78     # масштаб ОБЛОЖКИ относительно обычной карточки (монитор -> ТВ: нужно видеть несколько строк);
                      # тексты и кнопка от него не зависят - на расстоянии дивана они должны быть крупными

STREAM_RESOLUTIONS = [("1280x720", 1280, 720), ("1920x1080", 1920, 1080),
                      ("2560x1440", 2560, 1440), ("3840x2160", 3840, 2160)]
STREAM_FPS = [30, 60, 90, 120]
STREAM_BITRATES = [10000, 20000, 30000, 50000, 80000]   # кбит/с
DEFAULT_STREAM_APPS = ["Desktop", "Steam Big Picture"]
RECENT_LIMIT = 20

_ACTIVE_WORKERS = set()   # держим ссылки на потоки, пока они работают (иначе GC = аварийное завершение)


def format_duration(seconds):
    seconds = int(seconds or 0)
    h, m = divmod(seconds // 60, 60)
    if h:
        return tr("big_picture.time_hm", h=h, m=m)
    if m:
        return tr("big_picture.time_m", m=m)
    return tr("big_picture.time_lt_min")


# =====================================================================
#  Плитка (игра или текстовый пункт) - из тех же виджетов, что и обычная карточка
# =====================================================================
class Tile(QWidget):
    """Карточка игры собрана из тех же виджетов и с теми же objectName, что GameCard в
    обычном режиме (GameCard / GameCardImage / GameCardName / GameCardTime / RunGameBtn),
    поэтому тема, QSS и дополнения (красная рамка запущенной игры, золотая рамка избранного)
    применяются к ней автоматически - Big Picture выглядит как лаунчер, а не как отдельная программа."""

    def __init__(self, title, subtitle="", pixmap=None, unit=1.0, kind="game",
                 value="", running=False, favorite=False, data=None, parent=None):
        super().__init__(parent)
        self.title, self.subtitle, self.value, self.data = title, subtitle, value, data
        self._u = unit
        self._kind = kind
        self._selected = False
        self._btn = None
        k = unit * CARD_SCALE

        outer = QVBoxLayout(self)
        margin = int(18 * unit)          # запас под свечение выбранной карточки
        outer.setContentsMargins(margin, margin, margin, margin)
        self._frame = QFrame()
        self._frame.setObjectName("GameCard")
        # свойство "running" включает в теме красную рамку ЗАПУЩЕННОЙ ИГРЫ - у текстовых пунктов
        # (например, выбранный хост) оно не должно ставиться
        self._frame.setProperty("running", bool(running) and kind == "game")
        outer.addWidget(self._frame)
        lay = QVBoxLayout(self._frame)
        m = int(15 * k if kind == "game" else 18 * unit)
        lay.setContentsMargins(m, m, m, m)
        lay.setSpacing(int(12 * k if kind == "game" else 6 * unit))

        if kind == "game":
            img = QLabel()
            img.setObjectName("GameCardImage")
            img.setFixedSize(int(250 * k), int(330 * k))
            img.setProperty("favorite", bool(favorite))
            img.setAlignment(Qt.AlignmentFlag.AlignCenter)
            if pixmap is not None and not pixmap.isNull():
                img.setPixmap(pixmap.scaled(img.size(), Qt.AspectRatioMode.KeepAspectRatioByExpanding,
                                            Qt.TransformationMode.SmoothTransformation))
            else:
                img.setText("🎮")
                img.setProperty("empty", True)
                img.setStyleSheet(f"font-size: {int(100 * k)}px;")
            lay.addWidget(img)
            if running:   # плашка "играет" (в QSS стиль RunningBadge уже есть)
                badge = QLabel(tr("big_picture.running"), img)
                badge.setObjectName("RunningBadge")
                badge.setStyleSheet(f"font-size: {int(12 * unit)}px;")
                badge.adjustSize()
                badge.move(int(8 * unit), int(8 * unit))

            name = QLabel(("⭐️ " if favorite else "") + title)
            name.setObjectName("GameCardName")
            name.setAlignment(Qt.AlignmentFlag.AlignCenter)
            name.setWordWrap(True)
            name_px = max(15, int(22 * unit))
            name.setStyleSheet(f"font-size: {name_px}px;")
            name.setFixedHeight(int(name_px * 2.7))     # ровно две строки: плитки в ряду одной высоты
            name.setFixedWidth(int(250 * k))
            lay.addWidget(name)

            time_lbl = QLabel(subtitle)
            time_lbl.setObjectName("GameCardTime")
            time_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
            time_lbl.setStyleSheet(f"font-size: {max(12, int(17 * unit))}px;")
            lay.addWidget(time_lbl)

            self._btn = QPushButton(tr("game_card.stop") if running else tr("game_card.run"))
            self._btn.setObjectName("RunGameBtn")
            self._btn.setProperty("running", bool(running))
            self._btn.setFixedHeight(int(52 * unit))
            self._btn.setStyleSheet(f"font-size: {max(12, int(17 * unit))}px;")
            self._btn.setFocusPolicy(Qt.FocusPolicy.NoFocus)
            self._btn.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
            lay.addWidget(self._btn)
        else:
            self._frame.setFixedSize(int(280 * unit), int(140 * unit))
            name = QLabel(title)
            name.setObjectName("GameCardName")
            name.setWordWrap(True)
            name.setStyleSheet(f"font-size: {int((20 if not value else 17) * unit)}px;")
            lay.addWidget(name)
            if value:
                val = QLabel(value)
                val.setObjectName("BPValue")
                val.setStyleSheet(f"font-size: {int(34 * unit)}px;")
                lay.addWidget(val)
            lay.addStretch(1)
            if subtitle:
                sub = QLabel(subtitle)
                sub.setObjectName("GameCardTime")
                sub.setStyleSheet(f"font-size: {int(13 * unit)}px;")
                if running:   # "активный" пункт (например, выбранный хост)
                    sub.setStyleSheet(f"font-size: {int(13 * unit)}px; color: {THEME['success']};")
                lay.addWidget(sub)
        self.layout().activate()
        self.setFixedSize(self.sizeHint())

    @property
    def selected(self):
        return self._selected

    def _repolish(self):
        for w in (self._frame, self._btn):
            if w is not None:
                w.style().unpolish(w)
                w.style().polish(w)
                w.update()

    def set_selected(self, selected):
        if selected == self._selected:
            return
        self._selected = selected
        self._frame.setProperty("bpSelected", selected)    # правила для [bpSelected] - в стиле окна
        if self._btn is not None:
            self._btn.setProperty("bpSel", selected)
        self._repolish()
        if selected:
            glow = QGraphicsDropShadowEffect(self._frame)
            glow.setColor(QColor(THEME["accent"]))
            glow.setBlurRadius(int(46 * self._u))
            glow.setOffset(0, 0)
            self._frame.setGraphicsEffect(glow)
        else:
            self._frame.setGraphicsEffect(None)


# =====================================================================
#  Зеркало слоёв оформления обычного окна (api.design: обои, градиенты, звёзды...)
# =====================================================================
class MirrorOverlay(QWidget):
    """Рисует те же слои оформления, что аддоны добавили в обычное окно лаунчера
    (api.design.particles / animated_gradient / wallpaper ...). Слои - общие объекты, поэтому
    Big Picture показывает ровно то оформление, которое выбрал пользователь, каким бы оно ни было."""

    def __init__(self, host, launcher):
        super().__init__(host)
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        self.setAttribute(Qt.WidgetAttribute.WA_NoSystemBackground)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self._launcher = launcher
        self._cache = None
        self._t0 = self._last = time.monotonic()
        self._timer = QTimer(self)
        self._timer.timeout.connect(self.update)
        self.refresh()

    def layers(self):
        try:
            from addon_API.design.overlay import Overlay
            sources = self._launcher.findChildren(Overlay)
        except Exception:
            return []
        return [layer for ov in sources for layer in ov.layers]

    def refresh(self):
        self._cache = None
        if self.isVisible():
            self._sync_timer()
        self.update()

    def _sync_timer(self):
        if any(l.animated for l in self.layers()):
            if not self._timer.isActive():
                self._timer.start(33)
        else:
            self._timer.stop()

    def showEvent(self, event):
        super().showEvent(event)
        self._sync_timer()

    def hideEvent(self, event):
        super().hideEvent(event)
        self._timer.stop()

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self._cache = None

    def paintEvent(self, _event):
        layers = self.layers()
        now = time.monotonic()
        t, dt = now - self._t0, min(0.2, now - self._last)
        self._last = now
        rect = self.rect()
        p = QPainter(self)
        statics = [l for l in layers if not l.animated]
        if statics:
            if self._cache is None or self._cache.size() != rect.size():
                pm = QPixmap(rect.size())
                pm.fill(Qt.GlobalColor.transparent)
                cp = QPainter(pm)
                for l in statics:
                    l.paint(cp, rect, t, dt)
                cp.end()
                self._cache = pm
            p.drawPixmap(0, 0, self._cache)
        for l in layers:
            if l.animated:
                l.paint(p, rect, t, dt)
        p.end()


# =====================================================================
#  Страница со строками плиток и навигацией
# =====================================================================
class NavPage(QScrollArea):
    """Вертикальный список горизонтальных строк плиток с курсором (строка, столбец)."""

    def __init__(self, unit, parent=None):
        super().__init__(parent)
        self._u = unit
        self.setWidgetResizable(True)
        self.setFrameShape(QFrame.Shape.NoFrame)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.setObjectName("BPPage")
        self.viewport().setAutoFillBackground(False)
        self._body = QWidget()
        self._body.setObjectName("BPBody")   # прозрачность - правилом по имени в стиле окна (см. _build_stylesheet)
        self._vbox = QVBoxLayout(self._body)
        self._vbox.setContentsMargins(int(40 * unit), int(4 * unit), int(40 * unit), int(40 * unit))
        self._vbox.setSpacing(int(4 * unit))
        self._vbox.setAlignment(Qt.AlignmentFlag.AlignTop)
        self.setWidget(self._body)
        self._rows = []   # {"key","title","tiles","box","hscroll","anim"}
        self._r = 0
        self._col_pref = 0
        self._vanim = QPropertyAnimation(self.verticalScrollBar(), b"value", self)
        self._vanim.setDuration(240)
        self._vanim.setEasingCurve(QEasingCurve.Type.OutCubic)

    # --- построение ---
    def set_rows(self, rows, keep_position=True):
        prev_key = self._rows[self._r]["key"] if self._rows else None
        prev_col = self._col_pref
        for row in self._rows:
            row["box"].setParent(None)
            row["box"].deleteLater()
        self._rows = []
        for key, title, tiles in rows:
            if not tiles:
                continue
            box = QWidget()
            box.setObjectName("BPRowBox")
            # строка занимает ровно свою высоту; иначе при одной-двух строках она
            # растягивалась на весь экран, а заголовок "уезжал" от плиток
            box.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Fixed)
            lay = QVBoxLayout(box)
            lay.setContentsMargins(0, 0, 0, 0)
            lay.setSpacing(0)
            # заголовок - как у GroupWidget: кнопка-стрелка + название (те же objectName,
            # поэтому цвета/шрифты задаёт тема); кнопка здесь только для вида
            label = QWidget()
            label.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Fixed)
            hl = QHBoxLayout(label)
            hl.setContentsMargins(int(14 * self._u), int(6 * self._u), 0, 0)
            hl.setSpacing(int(6 * self._u))
            tgl = QPushButton("▼")
            tgl.setObjectName("GroupToggleBtn")
            tgl.setFixedSize(int(46 * self._u), int(46 * self._u))
            tgl.setStyleSheet(f"font-size: {int(22 * self._u)}px;")
            tgl.setFocusPolicy(Qt.FocusPolicy.NoFocus)
            tgl.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
            ttl = QLabel(title)
            ttl.setObjectName("GroupTitleLabel")
            ttl.setProperty("favorite", key == "favorites")
            ttl.setStyleSheet(f"font-size: {int(26 * self._u)}px;")
            hl.addWidget(tgl)
            hl.addWidget(ttl)
            hl.addStretch(1)
            lay.addWidget(label)
            hscroll = QScrollArea()
            hscroll.setFrameShape(QFrame.Shape.NoFrame)
            hscroll.setWidgetResizable(True)
            hscroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
            hscroll.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
            hscroll.setObjectName("BPRowScroll")
            hscroll.viewport().setAutoFillBackground(False)
            hscroll.setFixedHeight(tiles[0].height() + 4)
            inner = QWidget()
            inner.setObjectName("BPRowInner")
            hbox = QHBoxLayout(inner)
            hbox.setContentsMargins(0, 0, 0, 0)
            hbox.setSpacing(0)
            for t in tiles:
                hbox.addWidget(t)
            hbox.addStretch(1)
            hscroll.setWidget(inner)
            lay.addWidget(hscroll)
            anim = QPropertyAnimation(hscroll.horizontalScrollBar(), b"value", self)
            anim.setDuration(220)
            anim.setEasingCurve(QEasingCurve.Type.OutCubic)
            self._vbox.addWidget(box)
            self._rows.append({"key": key, "title": title, "tiles": tiles, "box": box,
                               "hscroll": hscroll, "anim": anim})
        self._r = 0
        if keep_position and prev_key is not None:
            for i, row in enumerate(self._rows):
                if row["key"] == prev_key:
                    self._r = i
                    break
        self._col_pref = prev_col if keep_position else 0
        self._apply_selection()
        QTimer.singleShot(0, lambda: self._reveal(animated=False))

    def has_rows(self):
        return bool(self._rows)

    # --- курсор ---
    def _col(self):
        return min(self._col_pref, len(self._rows[self._r]["tiles"]) - 1) if self._rows else 0

    def current(self):
        """(ключ строки, индекс плитки, плитка) или None."""
        if not self._rows:
            return None
        row = self._rows[self._r]
        c = self._col()
        return row["key"], c, row["tiles"][c]

    def move(self, dx, dy):
        if not self._rows:
            return False
        old = (self._r, self._col())
        if dy:
            self._r = max(0, min(len(self._rows) - 1, self._r + dy))
        if dx:
            self._col_pref = max(0, min(len(self._rows[self._r]["tiles"]) - 1, self._col() + dx))
        moved = (self._r, self._col()) != old
        if moved:
            self._apply_selection()
            self._reveal(animated=True)
        return moved

    def _apply_selection(self):
        for ri, row in enumerate(self._rows):
            for ci, tile in enumerate(row["tiles"]):
                tile.set_selected(ri == self._r and ci == self._col())

    def _reveal(self, animated=True):
        if not self._rows:
            return
        row = self._rows[self._r]
        tile = row["tiles"][self._col()]
        # по горизонтали - центрируем плитку в строке
        hbar = row["hscroll"].horizontalScrollBar()
        target = tile.x() + tile.width() / 2 - row["hscroll"].viewport().width() / 2
        self._animate(row["anim"], hbar, int(max(0, min(hbar.maximum(), target))), animated)
        # по вертикали - прокручиваем минимально, чтобы строка ВМЕСТЕ с заголовком была в кадре
        vbar = self.verticalScrollBar()
        box = row["box"]
        gap = 8 * self._u
        top, bottom, view_h = box.y(), box.y() + box.height(), self.viewport().height()
        vt = vbar.value()
        if top - gap < vt:
            vt = top - gap
        elif bottom + gap > vt + view_h:
            vt = bottom + gap - view_h
        self._animate(self._vanim, vbar, int(max(0, min(vbar.maximum(), vt))), animated)

    @staticmethod
    def _animate(anim, bar, target, animated):
        anim.stop()
        if animated and bar.value() != target:
            anim.setStartValue(bar.value())
            anim.setEndValue(target)
            anim.start()
        else:
            bar.setValue(target)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self._reveal(animated=False)


# =====================================================================
#  Всплывающее меню поверх интерфейса (действия, меню, выход)
# =====================================================================
class OverlayMenu(QWidget):
    def __init__(self, parent, unit):
        super().__init__(parent)
        self._u = unit
        self._items = []
        self._labels = []
        self._index = 0
        self.hide()
        outer = QVBoxLayout(self)
        outer.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._panel = QFrame()
        self._panel.setObjectName("BPPanel")
        self._panel.setStyleSheet(f"QFrame#BPPanel {{ background-color: {THEME['surface_alt']}; border: 2px solid {THEME['border']};"
                                  f" border-radius: {int(22 * unit)}px; }}")
        self._lay = QVBoxLayout(self._panel)
        pad = int(26 * unit)
        self._lay.setContentsMargins(pad, pad, pad, pad)
        self._lay.setSpacing(int(8 * unit))
        self._title = QLabel()
        self._title.setStyleSheet(f"color: {THEME.muted_ok}; font-size: {int(20 * unit)}px; font-weight: 600; border: none; background: transparent;")
        self._lay.addWidget(self._title)
        outer.addWidget(self._panel)

    def paintEvent(self, _e):
        p = QPainter(self)
        p.fillRect(self.rect(), QColor(0, 0, 0, 170))

    def open(self, title, items):
        """items: [(текст, callback)]; callback вызывается после закрытия меню."""
        for lb in self._labels:
            lb.setParent(None)
            lb.deleteLater()
        self._labels = []
        self._items = list(items)
        self._title.setText(title)
        u = self._u
        for text, _cb in self._items:
            lb = QLabel(text)
            lb.setMinimumWidth(int(460 * u))
            self._lay.addWidget(lb)
            self._labels.append(lb)
        self._index = 0
        self._style()
        self.setGeometry(self.parentWidget().rect())
        self.show()
        self.raise_()

    def _style(self):
        u = self._u
        for i, lb in enumerate(self._labels):
            if i == self._index:
                lb.setStyleSheet(f"background-color: {THEME['accent']}; color: {on_color(THEME['accent'])}; border: none;"
                                 f"border-radius: {int(12 * u)}px;"
                                 f"padding: {int(14 * u)}px {int(24 * u)}px; font-size: {int(24 * u)}px; font-weight: 600;")
            else:
                lb.setStyleSheet(f"background: transparent; color: {THEME.text_ok}; border: none;"
                                 f"padding: {int(14 * u)}px {int(24 * u)}px; font-size: {int(24 * u)}px;")

    def close_menu(self):
        self.hide()

    def handle(self, name):
        if name == "up":
            self._index = max(0, self._index - 1)
            self._style()
        elif name == "down":
            self._index = min(len(self._items) - 1, self._index + 1)
            self._style()
        elif name == "a":
            callback = self._items[self._index][1]
            self.close_menu()
            if callback:
                callback()
        elif name in ("b", "start"):
            self.close_menu()


# =====================================================================
#  Фоновая загрузка списка приложений хоста
# =====================================================================
class AppListWorker(QThread):
    done = pyqtSignal(str, list, str)   # ip, приложения, ошибка

    def __init__(self, manager, ip):
        super().__init__()
        self._manager, self._ip = manager, ip

    def run(self):
        try:
            apps, err = self._manager.list_apps(self._ip)
        except Exception as e:
            apps, err = [], str(e)
        self.done.emit(self._ip, apps, err or "")


# =====================================================================
#  Главное окно
# =====================================================================
class BigPictureWindow(QWidget):
    exited = pyqtSignal(bool)   # True - закрыть и сам лаунчер

    _KEYMAP = {
        Qt.Key.Key_Left: "left", Qt.Key.Key_Right: "right", Qt.Key.Key_Up: "up", Qt.Key.Key_Down: "down",
        Qt.Key.Key_Return: "a", Qt.Key.Key_Enter: "a", Qt.Key.Key_Space: "a",
        Qt.Key.Key_Escape: "b", Qt.Key.Key_Backspace: "b",
        Qt.Key.Key_F: "x", Qt.Key.Key_X: "x", Qt.Key.Key_Y: "y",
        Qt.Key.Key_Tab: "rb", Qt.Key.Key_PageDown: "rb", Qt.Key.Key_Backtab: "lb", Qt.Key.Key_PageUp: "lb",
        Qt.Key.Key_M: "start", Qt.Key.Key_F10: "start", Qt.Key.Key_Menu: "start",
    }

    def __init__(self, launcher, gamepad_reader=None, stream_manager=None):
        super().__init__()
        self._launcher = launcher
        self._mgr = stream_manager
        self._mgr_loaded = stream_manager is not None
        screen = QApplication.primaryScreen()
        height = screen.size().height() if screen else 1080
        self._u = max(0.6, height / 1080.0)
        self._suspended = False
        self._finished = False
        self._done_fn = None
        self._suspend_info = None

        self._tab = self._settings().get("last_tab", 0)
        if not isinstance(self._tab, int) or not 0 <= self._tab < len(TABS):
            self._tab = 0
        self._host = None
        self._apps = None          # None - загружаем, список - готово
        self._app_worker = None

        self.setObjectName("BigPicture")
        self.setWindowTitle("GorLauncher - Big Picture")
        self.setWindowFlag(Qt.WindowType.FramelessWindowHint, True)
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        THEME.load()   # цвета - из активной темы лаунчера
        try:
            self.setFont(launcher.font())   # шрифт, который лаунчер использует сейчас (в т.ч. заданный аддоном)
        except Exception:
            pass
        self.setStyleSheet(self._build_stylesheet())
        self._build_ui()

        self._overlay = OverlayMenu(self, self._u)
        self._reader = gamepad_reader if gamepad_reader is not None else GamepadReader(parent=self)
        self._reader.pressed.connect(self.handle_input)
        self._reader.connectionChanged.connect(self._on_gamepad_connection)
        self._on_gamepad_connection(self._reader.connected)

        self._clock = QTimer(self)
        self._clock.timeout.connect(self._tick_clock)
        self._clock.start(1000)
        self._tick_clock()
        self._wait_timer = QTimer(self)
        self._wait_timer.timeout.connect(self._check_resume)
        self._toast_timer = QTimer(self)
        self._toast_timer.setSingleShot(True)
        self._toast_timer.timeout.connect(lambda: self._toast.hide())

        self._rebuild(keep=False)

    # ------------------------------------------------------------------ #
    # построение интерфейса
    # ------------------------------------------------------------------ #
    def _build_stylesheet(self):
        """Стиль окна = стиль самого окна лаунчера (его дополняют аддоны оформления: стеклянные
        карточки и т.п.) + немного правил, которых в обычном режиме нет (выбранная плитка)."""
        u = self._u
        try:
            inherited = self._launcher.styleSheet() or ""
        except Exception:
            inherited = ""
        c = THEME
        return inherited + f"""
#BigPicture {{ background-color: {c['bg']}; }}
/* Структурные контейнеры прозрачны ПО ИМЕНИ. Нельзя задавать им "голый" background: transparent -
   такой стиль каскадом перебивает тему у ВСЕХ потомков (кнопок, карточек, плашки статистики). */
QWidget#BPTop, QWidget#BPHints, QWidget#BPBody, QWidget#BPRowBox, QWidget#BPRowInner {{ background: transparent; }}
QScrollArea#BPPage, QScrollArea#BPRowScroll {{ background: transparent; border: none; }}
QScrollArea#BPPage QWidget#qt_scrollarea_viewport, QScrollArea#BPRowScroll QWidget#qt_scrollarea_viewport {{ background: transparent; }}
QFrame#GameCard[bpSelected="true"] {{ border: 3px solid {c['accent']}; }}
QPushButton#RunGameBtn[bpSel="true"][running="false"] {{ background-color: {c['accent_hover']}; color: {on_color(c['accent_hover'])}; }}
QLabel#BPValue {{ color: {c['accent']}; font-weight: bold; background: transparent; }}
QTabBar::tab {{ font-size: {int(19 * u)}px; padding: {int(11 * u)}px {int(22 * u)}px; margin-right: {int(8 * u)}px; }}
QLabel#StatsLabel {{ font-size: {int(18 * u)}px; padding: {int(8 * u)}px {int(16 * u)}px; }}
QLabel#BPToast {{ background-color: {c['surface_alt']}; color: {c.text_ok}; border: 2px solid {c['border']};
                 border-radius: {int(16 * u)}px; padding: {int(14 * u)}px {int(28 * u)}px; font-size: {int(24 * u)}px; }}
"""

    def _build_ui(self):
        u = self._u
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        # --- шапка: логотип, статистика, вкладки (как в обычном режиме), часы ---
        top = QWidget()
        top.setObjectName("BPTop")
        top.setFixedHeight(int(96 * u))
        tl = QHBoxLayout(top)
        tl.setContentsMargins(int(40 * u), int(12 * u), int(40 * u), int(4 * u))
        tl.setSpacing(int(16 * u))
        logo = self._make_logo(int(60 * u))
        if logo is not None:
            tl.addWidget(logo)
        self._stats = QLabel()
        self._stats.setObjectName("StatsLabel")
        tl.addWidget(self._stats)
        tl.addSpacing(int(10 * u))
        self._tabbar = QTabBar()
        self._tabbar.setExpanding(False)
        self._tabbar.setDrawBase(False)
        self._tabbar.setUsesScrollButtons(False)
        self._tabbar.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self._tabbar.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)   # управление - только геймпад/клавиатура
        for text in (tr("launcher.tab_library"), tr("launcher.tab_favorites"), tr("launcher.tab_history"),
                     "📺 " + tr("big_picture.tab_stream").upper()):
            self._tabbar.addTab(text)
        tl.addWidget(self._tabbar)
        tl.addStretch(1)
        self._clock_label = QLabel()
        self._clock_label.setStyleSheet(f"color: {THEME.text_ok}; font-size: {int(30 * u)}px; font-weight: 600; background: transparent;")
        tl.addWidget(self._clock_label)
        root.addWidget(top)

        self._page = NavPage(u)
        self._empty = QLabel()
        self._empty.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._empty.setWordWrap(True)
        self._empty.setStyleSheet(f"color: {THEME.muted_ok}; font-size: {int(28 * u)}px; background: transparent;")
        self._stack = QStackedWidget()
        self._stack.setStyleSheet("QStackedWidget { background: transparent; }")
        self._stack.addWidget(self._page)
        self._stack.addWidget(self._empty)
        root.addWidget(self._stack, 1)

        hints = QWidget()
        hints.setObjectName("BPHints")
        hints.setFixedHeight(int(70 * u))
        hl = QHBoxLayout(hints)
        hl.setContentsMargins(int(40 * u), 0, int(40 * u), int(10 * u))
        hl.setSpacing(int(28 * u))
        for key, color, text in (("A", GREEN, "hint_ok"), ("B", RED, "hint_back"), ("X", BLUE, "hint_favorite"),
                                 ("Y", YELLOW, "hint_actions"), ("LB RB", "#6b7488", "hint_section"), ("≡", "#6b7488", "hint_menu")):
            hl.addWidget(self._hint_chip(key, color, tr(f"big_picture.{text}")))
        hl.addStretch(1)
        self._pad_label = QLabel()
        self._pad_label.setStyleSheet(f"color: {THEME.muted_ok}; font-size: {int(18 * u)}px; background: transparent;")
        hl.addWidget(self._pad_label)
        root.addWidget(hints)

        self._toast = QLabel(self)
        self._toast.setObjectName("BPToast")
        self._toast.hide()

        # слои оформления обычного окна рисуются поверх содержимого - как и в лаунчере
        self._mirror = MirrorOverlay(self, self._launcher)
        self._mirror.setGeometry(self.rect())
        self._mirror.show()
        self._mirror.raise_()

    def _make_logo(self, size):
        path = os.path.join(os.getcwd(), "logo.png")
        pm = QPixmap(path) if os.path.exists(path) else QPixmap()
        if pm.isNull():
            return None
        pm = pm.scaled(size, size, Qt.AspectRatioMode.KeepAspectRatioByExpanding, Qt.TransformationMode.SmoothTransformation)
        out = QPixmap(size, size)
        out.fill(Qt.GlobalColor.transparent)
        p = QPainter(out)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        clip = QPainterPath()
        clip.addEllipse(QRectF(0, 0, size, size))
        p.setClipPath(clip)
        p.drawPixmap((size - pm.width()) // 2, (size - pm.height()) // 2, pm)
        p.end()
        lb = QLabel()
        lb.setPixmap(out)
        lb.setFixedSize(size, size)
        lb.setStyleSheet("background: transparent;")
        return lb

    def _hint_chip(self, key, color, text):
        u = self._u
        w = QWidget()
        w.setStyleSheet("background: transparent;")
        lay = QHBoxLayout(w)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(int(10 * u))
        badge = QLabel(key)
        badge.setAlignment(Qt.AlignmentFlag.AlignCenter)
        wide = len(key) > 1
        size = int(34 * u)
        badge.setFixedSize(int(size * (1.9 if wide else 1)), size)
        badge.setStyleSheet(f"background-color: {color}; color: {on_color(color)}; font-weight: 800;"
                            f"font-size: {int(17 * u)}px; border-radius: {size // 2 if not wide else int(10 * u)}px;")
        lay.addWidget(badge)
        label = QLabel(text)
        label.setStyleSheet(f"color: {THEME.muted_ok}; font-size: {int(19 * u)}px; background: transparent;")
        lay.addWidget(label)
        return w

    def _style_tabs(self):
        self._tabbar.setCurrentIndex(self._tab)

    def _stats_text(self):
        lbl = getattr(self._launcher, "stats_lbl", None)
        if lbl is not None:   # тот же текст, что в шапке обычного окна
            return lbl.text()
        games = self._all_games()
        hours = sum(g.get("playtime_seconds", 0) for g in games) // 3600
        return tr("launcher.stats", count=len(games), hours=hours)

    # ------------------------------------------------------------------ #
    # данные
    # ------------------------------------------------------------------ #
    def _settings(self):
        info = self._launcher.games_info
        s = info.get("big_picture")
        if not isinstance(s, dict):
            s = {}
            info["big_picture"] = s
        return s

    def _save_settings(self):
        try:
            self._launcher.save_data()
        except Exception as e:
            print(f"[big_picture] не удалось сохранить настройки: {e}")

    def _all_games(self):
        # порядок как в строках "Библиотеки": сначала группы, потом игры без группы
        info = self._launcher.games_info
        games = []
        for lst in info.get("groups", {}).values():
            games.extend(lst)
        games.extend(info.get("standalone", []))
        return games

    @staticmethod
    def _gid(game):
        return game.get("id") or game.get("name")

    def _game_tile(self, game):
        running = self._gid(game) in self._launcher.active_sessions
        seconds = game.get("playtime_seconds", 0)
        subtitle = tr("game_card.time_static", h=seconds // 3600, m=(seconds % 3600) // 60)   # как на обычной карточке
        return Tile(game.get("name", "?"), subtitle, load_pixmap_cached(game.get("icon", "")), self._u, "game",
                    running=running, favorite=bool(game.get("favorite")), data=game)

    def _game_rows(self):
        info = self._launcher.games_info
        name = TABS[self._tab]
        if name == "library":
            rows = [(f"group:{g}", g, [self._game_tile(x) for x in lst]) for g, lst in info.get("groups", {}).items()]
            rows.append(("standalone", tr("launcher.standalone_title"), [self._game_tile(x) for x in info.get("standalone", [])]))
            return rows
        if name == "favorites":
            return [("favorites", tr("big_picture.tab_favorites"),
                     [self._game_tile(g) for g in self._all_games() if g.get("favorite")])]
        by_name = {g.get("name"): g for g in self._all_games()}   # недавние
        seen, tiles = set(), []
        for entry in info.get("history", []):
            n = entry.get("name")
            if n in seen or n not in by_name:
                continue
            seen.add(n)
            tiles.append(self._game_tile(by_name[n]))
            if len(tiles) >= RECENT_LIMIT:
                break
        return [("recent", tr("big_picture.tab_recent"), tiles)]

    # --- стрим ---
    def _manager(self):
        if not self._mgr_loaded:
            self._mgr_loaded = True
            try:
                from moonlight_cantrol import PCStreamManager
                self._mgr = PCStreamManager()
            except Exception as e:
                print(f"[big_picture] Moonlight недоступен: {e}")
                self._mgr = None
        return self._mgr

    def _quality(self):
        q = self._settings().setdefault("stream", {})
        res = q.get("res") if q.get("res") in [r[0] for r in STREAM_RESOLUTIONS] else "1920x1080"
        fps = q.get("fps") if q.get("fps") in STREAM_FPS else 60
        bitrate = q.get("bitrate") if q.get("bitrate") in STREAM_BITRATES else 20000
        return res, fps, bitrate

    def _stream_rows(self):
        """Возвращает (строки, сообщение_вместо_страницы)."""
        mgr = self._manager()
        if mgr is None or not mgr.is_available():
            return [], tr("big_picture.stream_no_moonlight")
        hosts = list(mgr.hosts)
        if not hosts:
            return [], tr("big_picture.stream_no_hosts")
        if self._host not in hosts:
            last = self._settings().get("last_host")
            self._host = last if last in hosts else (hosts[0] if len(hosts) == 1 else None)
            if self._host:
                self._load_apps()
        u = self._u
        rows = [("hosts", tr("big_picture.stream_hosts"),
                 [Tile(ip, ("✓ " if ip == self._host else "● ") + "Sunshine", None, u, "text",
                       running=(ip == self._host), data=ip) for ip in hosts])]
        if self._host:
            if self._apps is None:
                apps_tiles = [Tile(tr("big_picture.stream_loading"), "", None, u, "text", data=None)]
            else:
                apps_tiles = [Tile(a, self._host, None, u, "text", data=a) for a in self._apps]
            rows.append(("apps", tr("big_picture.stream_apps"), apps_tiles))
            res, fps, bitrate = self._quality()
            hint = tr("big_picture.stream_hint_cycle")
            rows.append(("quality", tr("big_picture.stream_quality"), [
                Tile(tr("big_picture.stream_resolution"), hint, None, u, "text", value=res, data="res"),
                Tile(tr("big_picture.stream_fps"), hint, None, u, "text", value=str(fps), data="fps"),
                Tile(tr("big_picture.stream_bitrate"), hint, None, u, "text", value=f"{bitrate // 1000} Mbps", data="bitrate"),
            ]))
        else:
            rows.append(("hint", tr("big_picture.stream_select_host"), []))
        return rows, ""

    def _load_apps(self):
        mgr = self._mgr
        self._apps = None
        ip = self._host
        worker = AppListWorker(mgr, ip)
        self._app_worker = worker
        _ACTIVE_WORKERS.add(worker)
        worker.finished.connect(lambda w=worker: _ACTIVE_WORKERS.discard(w))
        worker.done.connect(self._on_apps_loaded)
        worker.start()

    def _on_apps_loaded(self, ip, apps, error):
        if ip != self._host or self._finished:
            return   # пользователь успел выбрать другой хост / выйти
        if apps:
            self._apps = apps
        else:
            self._apps = list(DEFAULT_STREAM_APPS)
            if error:
                self._toast_msg(tr("big_picture.stream_apps_default", error=error), 5000)
        if TABS[self._tab] == "stream":
            self._rebuild(keep=True)

    # ------------------------------------------------------------------ #
    # отображение
    # ------------------------------------------------------------------ #
    def _rebuild(self, keep=True):
        self._style_tabs()
        self._stats.setText(self._stats_text())
        name = TABS[self._tab]
        message = ""
        if name == "stream":
            rows, message = self._stream_rows()
        else:
            rows = self._game_rows()
            if not any(tiles for _k, _t, tiles in rows):
                message = tr(f"big_picture.empty_{name}")
        self._page.set_rows(rows, keep_position=keep)
        if message or not self._page.has_rows():
            self._empty.setText(message)
            self._stack.setCurrentWidget(self._empty)
        else:
            self._stack.setCurrentWidget(self._page)

    def refresh(self):
        self._rebuild(keep=True)

    def _tick_clock(self):
        self._clock_label.setText(QTime.currentTime().toString("HH:mm"))

    def _on_gamepad_connection(self, connected):
        self._pad_label.setText(tr("big_picture.gamepad_on") if connected else tr("big_picture.gamepad_off"))

    def _toast_msg(self, text, ms=3500):
        self._toast.setText(text)
        self._toast.adjustSize()
        self._toast.move((self.width() - self._toast.width()) // 2,
                         self.height() - self._toast.height() - int(110 * self._u))
        self._toast.show()
        self._toast.raise_()
        self._toast_timer.start(ms)

    # ------------------------------------------------------------------ #
    # жизненный цикл
    # ------------------------------------------------------------------ #
    def start(self):
        self.showFullScreen()
        self.setFocus()
        self._reader.start()
        self._reader.resync()

    def _finish(self, quit_app):
        if self._finished:
            return
        self.shutdown()
        self.exited.emit(quit_app)

    def shutdown(self):
        """Останавливает таймеры и опрос геймпада; безопасно вызывать повторно."""
        self._finished = True
        for t in (self._clock, self._wait_timer, self._toast_timer):
            t.stop()
        self._reader.stop()
        self.hide()

    def closeEvent(self, event):
        self.shutdown()
        super().closeEvent(event)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        if hasattr(self, "_mirror"):
            self._mirror.setGeometry(self.rect())
            self._mirror.raise_()
        if hasattr(self, "_overlay") and self._overlay.isVisible():
            self._overlay.setGeometry(self.rect())

    # --- пауза на время игры / стрима ---
    def _suspend(self, done_fn, kind):
        self._suspended = True
        self._done_fn = done_fn
        self._suspend_info = (kind, time.time())
        self._reader.set_paused(True)
        self.hide()
        self._wait_timer.start(1000)

    def _check_resume(self):
        if self._done_fn is None or not self._done_fn():
            return
        self._wait_timer.stop()
        kind, started = self._suspend_info or ("game", time.time())
        self._done_fn = None
        self._suspended = False
        self._reader.set_paused(False)
        self._rebuild(keep=True)
        self.showFullScreen()
        self.raise_()
        self.activateWindow()
        self.setFocus()
        if kind == "stream":
            self._toast_msg(tr("big_picture.stream_ended"))
        else:
            self._toast_msg(tr("big_picture.session_done", time=format_duration(time.time() - started)))

    # ------------------------------------------------------------------ #
    # ввод
    # ------------------------------------------------------------------ #
    def keyPressEvent(self, event):
        name = self._KEYMAP.get(event.key())
        if name is None:
            super().keyPressEvent(event)
            return
        event.accept()
        if event.isAutoRepeat() and name not in ("left", "right", "up", "down"):
            return
        self.handle_input(name)

    def handle_input(self, name):
        if self._suspended or self._finished:
            return
        if self._overlay.isVisible():
            self._overlay.handle(name)
            return
        if name in ("left", "right", "up", "down"):
            self._page.move({"left": -1, "right": 1}.get(name, 0), {"up": -1, "down": 1}.get(name, 0))
        elif name == "a":
            self._activate()
        elif name == "b":
            self._open_exit_menu()
        elif name == "x":
            self._on_x()
        elif name == "y":
            self._open_actions()
        elif name in ("lb", "rb"):
            self._switch_tab(-1 if name == "lb" else 1)
        elif name == "start":
            self._open_main_menu()

    def _switch_tab(self, delta):
        self._tab = (self._tab + delta) % len(TABS)
        self._settings()["last_tab"] = self._tab
        self._save_settings()
        self._rebuild(keep=False)

    # ------------------------------------------------------------------ #
    # действия
    # ------------------------------------------------------------------ #
    def _current_game(self):
        if TABS[self._tab] == "stream":
            return None
        cur = self._page.current()
        return cur[2].data if cur else None

    def _activate(self):
        cur = self._page.current()
        if cur is None:
            return
        key, _idx, tile = cur
        if TABS[self._tab] != "stream":
            self._launch(tile.data)
        elif key == "hosts":
            self._select_host(tile.data)
        elif key == "apps" and tile.data:
            self._start_stream(tile.data)
        elif key == "quality":
            self._cycle_quality(tile.data, +1)

    def _on_x(self):
        if TABS[self._tab] == "stream":
            cur = self._page.current()
            if cur and cur[0] == "quality":
                self._cycle_quality(cur[2].data, -1)
            return
        self._toggle_favorite(self._current_game())

    def _launch(self, game):
        if not game:
            return
        launcher = self._launcher
        if self._gid(game) in launcher.active_sessions:
            self._toast_msg(tr("big_picture.already_running"))
            return
        try:
            launcher.launch_game_from_wheel(game)
        except Exception as e:
            self._toast_msg(f"{tr('big_picture.launch_failed')}: {e}", 5000)
            return
        if self._gid(game) in launcher.active_sessions:
            self._suspend(lambda: not launcher.active_sessions, "game")
        else:
            self._toast_msg(tr("big_picture.launch_failed"))

    def _toggle_favorite(self, game):
        if not game:
            return
        game["favorite"] = not game.get("favorite", False)
        self._launcher.save_data()
        try:
            self._launcher.refresh_list()   # обычное окно лаунчера остаётся в актуальном состоянии
        except Exception:
            pass
        self._rebuild(keep=True)

    def _open_actions(self):
        game = self._current_game()
        if not game:
            return
        fav = tr("big_picture.action_fav_remove") if game.get("favorite") else tr("big_picture.action_fav_add")
        self._overlay.open(game.get("name", ""), [
            (tr("big_picture.action_play"), lambda: self._launch(game)),
            (fav, lambda: self._toggle_favorite(game)),
            (tr("big_picture.action_cancel"), None),
        ])

    def _open_main_menu(self):
        self._overlay.open(tr("big_picture.menu_title"), [
            (tr("big_picture.menu_resume"), None),
            (tr("big_picture.menu_exit"), lambda: self._finish(False)),
            (tr("big_picture.menu_quit"), lambda: self._finish(True)),
        ])

    def _open_exit_menu(self):
        self._open_main_menu()

    # --- стрим ---
    def _select_host(self, ip):
        if ip != self._host:
            self._host = ip
            self._settings()["last_host"] = ip
            self._save_settings()
            self._load_apps()
        self._rebuild(keep=True)

    def _cycle_quality(self, kind, step):
        res, fps, bitrate = self._quality()
        q = self._settings().setdefault("stream", {})
        if kind == "res":
            names = [r[0] for r in STREAM_RESOLUTIONS]
            q["res"] = names[(names.index(res) + step) % len(names)]
        elif kind == "fps":
            q["fps"] = STREAM_FPS[(STREAM_FPS.index(fps) + step) % len(STREAM_FPS)]
        elif kind == "bitrate":
            q["bitrate"] = STREAM_BITRATES[(STREAM_BITRATES.index(bitrate) + step) % len(STREAM_BITRATES)]
        self._save_settings()
        self._rebuild(keep=True)

    def _start_stream(self, app_name):
        mgr = self._manager()
        if mgr is None or not self._host:
            return
        res, fps, bitrate = self._quality()
        width, height = next((w, h) for n, w, h in STREAM_RESOLUTIONS if n == res)
        ok, message = mgr.start_stream(self._host, app_name, width=width, height=height, fps=fps, bitrate=bitrate)
        if not ok:
            self._toast_msg(tr("big_picture.stream_error", error=message), 6000)
            return
        proc = getattr(mgr, "last_process", None)
        if proc is None:
            self._toast_msg(tr("big_picture.stream_starting", app=app_name))
            return
        self._suspend(lambda: proc.poll() is not None, "stream")
