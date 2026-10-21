"""Цвета, окно, шрифты, курсоры, скриншоты, инспектор виджетов (api.design.*)."""

import os
import colorsys

from PyQt6.QtCore import Qt, QObject, QEvent, QTimer
from PyQt6.QtGui import QCursor, QPixmap, QImage, QFont, QFontDatabase, QGuiApplication
from PyQt6.QtWidgets import QApplication, QWidget

from . import colors as C
from ._util import safe

_CURSORS = {"arrow": "ArrowCursor", "pointing": "PointingHandCursor", "cross": "CrossCursor",
            "wait": "WaitCursor", "ibeam": "IBeamCursor", "forbidden": "ForbiddenCursor",
            "busy": "BusyCursor", "open_hand": "OpenHandCursor", "size_all": "SizeAllCursor"}


class ColorsMixin:
    # ------------------------------------------------------------ #
    # Цвета лаунчера (живые, не сохраняются на диск, откатываются)
    # ------------------------------------------------------------ #
    def get_colors(self):
        """Итоговые цвета лаунчера сейчас: {роль: '#hex'}."""
        from ..themes import themes
        return themes.colors()

    def set_colors(self, mapping):
        """Поменять цвета ролей: design.set_colors({"accent": "#ff2d95", "bg": "#0d0014"})."""
        from ..themes import themes
        themes.set_runtime_colors(self._api.root, {k: C.hex_of(self._fill(v)) for k, v in mapping.items()})
        self._sync_light_fix()

    _LIGHT_FIX = """
QLineEdit, QTextEdit, QPlainTextEdit, QComboBox, QSpinBox, QDoubleSpinBox, QListWidget,
QTreeWidget, QTableWidget, QCheckBox, QRadioButton, QGroupBox, QLabel { color: {{text}}; }
QPushButton { color: {{text}}; }
QPushButton:hover, QPushButton:pressed { color: #ffffff; }
QTabBar::tab { color: {{text}}; }
QTabBar::tab:selected { color: #ffffff; }
QMenu::item { color: {{text}}; }
QMenu::item:selected { color: #ffffff; }
QLabel#GameCardName, QLabel#AddonBigName { color: {{text}}; }
QPushButton#RestartBtn, QPushButton#TrayBtn, QPushButton#BurgerMenuBtn { color: {{text}}; }
QPushButton#RestartBtn:hover, QPushButton#TrayBtn:hover, QPushButton#BurgerMenuBtn:hover { color: #ffffff; }
"""

    def _sync_light_fix(self):
        """В style.qss у многих элементов жёстко прописан белый текст. Если фон стал светлым,
        автоматически возвращаем читаемый цвет текста (самым низким приоритетом - любые
        ваши стили его перекроют). Когда фон снова тёмный - убираем."""
        light = not C.is_dark(self.get_colors()["bg"])
        has = "_light_fix" in self._slots
        if light and not has:
            self._slot("_light_fix", self._LIGHT_FIX, front=True)
        elif not light and has:
            self.remove("_light_fix")

    def set_color(self, token, color):
        self.set_colors({token: color})

    def accent(self, color):
        """Сменить акцентный цвет (accent_dark / accent_hover посчитаются сами)."""
        self.set_colors({"accent": color})

    def reset_colors(self):
        from ..themes import themes
        themes.clear_runtime_colors(self._api.root)
        self._sync_light_fix()

    def palette(self, accent, mode="dark", tint=0.12):
        """Целая палитра из ОДНОГО цвета: design.palette("#ff7a18", "dark")"""
        self.set_colors(C.palette_from_accent(self._fill(accent), mode, tint))

    def palette_from_hue(self, hue, mode="dark", saturation=0.8):
        self.set_colors(C.palette_from_hue(hue, mode, saturation))

    def random_palette(self, seed=None, mode="dark"):
        pal = C.random_palette(seed, mode)
        self.set_colors(pal)
        return pal

    def dark_mode(self):
        self.palette(self.get_colors()["accent"], "dark")

    def light_mode(self):
        self.palette(self.get_colors()["accent"], "light")

    def dominant_color(self, image_path):
        """Главный (самый «цветной») цвет картинки -> '#hex'."""
        img = QImage(image_path)
        if img.isNull():
            raise ValueError(f"Не удалось открыть картинку: {image_path}")
        img = img.scaled(64, 64, Qt.AspectRatioMode.KeepAspectRatio).convertToFormat(QImage.Format.Format_RGB32)
        buckets = {}
        for y in range(img.height()):
            for x in range(img.width()):
                c = img.pixelColor(x, y)
                h, s, v = colorsys.rgb_to_hsv(c.redF(), c.greenF(), c.blueF())
                if v < 0.18 or s < 0.22:
                    continue
                b = buckets.setdefault(int(h * 36), [0.0, 0, 0, 0])
                wgt = s * v
                b[0] += wgt
                b[1] += c.red() * wgt; b[2] += c.green() * wgt; b[3] += c.blue() * wgt
        if not buckets:   # серая картинка - берём средний цвет
            c = img.scaled(1, 1, Qt.AspectRatioMode.IgnoreAspectRatio).pixelColor(0, 0)
            return C.to_hex(c.red(), c.green(), c.blue())
        w, r, g, b = max(buckets.values(), key=lambda v: v[0])
        return C.to_hex(r / w, g / w, b / w)

    def palette_from_image(self, image_path, mode="dark"):
        """Подобрать оформление лаунчера под картинку (обои, обложка, логотип)."""
        color = self.dominant_color(image_path)
        self.palette(color, mode)
        return color

    def save_as_theme(self, name, author=""):
        """Сохранить текущее оформление (цвета + все стили api.design) как обычную тему
        в папку themes/ - её потом можно выбрать в Theme Studio без этого аддона.
        (Эффекты, анимации и слои поверх окна в тему не входят - это поведение аддона.)"""
        from ..themes import themes, TOKENS
        cols = {k: v for k, v in self.get_colors().items() if v.lower() != TOKENS[k].lower()}
        qss = "\n\n".join(item[1] for item in self._slots.values())
        data = {"name": name, "author": author, "version": "1.0",
                "description": "Сохранено из api.design", "colors": cols}
        return themes.install(name, data, qss or None)

    def export_qss(self):
        """Итоговый QSS лаунчера целиком (для отладки и копирования)."""
        from ..themes import themes
        return themes.stylesheet()


class WindowMixin:
    # ------------------------------------------------------------ #
    # Окно
    # ------------------------------------------------------------ #
    def window_opacity(self, value):
        """Прозрачность всего окна 0.3..1.0."""
        old = self.launcher.windowOpacity()
        self.launcher.setWindowOpacity(max(0.2, min(1.0, value)))
        self._res.add(lambda: safe(lambda: self.launcher.setWindowOpacity(old)))

    def always_on_top(self, enabled=True):
        win = self.launcher
        old = bool(win.windowFlags() & Qt.WindowType.WindowStaysOnTopHint)
        win.setWindowFlag(Qt.WindowType.WindowStaysOnTopHint, enabled)
        win.show()
        self._res.add(lambda: safe(lambda: (win.setWindowFlag(Qt.WindowType.WindowStaysOnTopHint, old),
                                            win.show())))

    def window_size(self, width, height):
        old = self.launcher.size()
        self.launcher.resize(width, height)
        self._res.add(lambda: safe(lambda: self.launcher.resize(old)))

    def min_size(self, width, height):
        old = self.launcher.minimumSize()
        self.launcher.setMinimumSize(width, height)
        self._res.add(lambda: safe(lambda: self.launcher.setMinimumSize(old)))

    def center_window(self):
        screen = QGuiApplication.primaryScreen().availableGeometry()
        g = self.launcher.frameGeometry()
        g.moveCenter(screen.center())
        self.launcher.move(g.topLeft())

    def fullscreen(self, enabled=True):
        was = self.launcher.isFullScreen()
        (self.launcher.showFullScreen if enabled else self.launcher.showNormal)()
        self._res.add(lambda: safe(lambda: (self.launcher.showFullScreen if was else self.launcher.showNormal)()))

    def screenshot(self, path=None):
        """Сохранить скриншот окна лаунчера в PNG. Возвращает путь."""
        path = path or os.path.join(self._api.data_dir(), "screenshot.png")
        self.launcher.grab().save(path)
        return path

    # ------------------------------------------------------------ #
    # Курсор и шрифты
    # ------------------------------------------------------------ #
    def cursor(self, shape_or_image="arrow", hot_x=0, hot_y=0, target=None):
        """Курсор над окном (или над target): "pointing" | "cross" | "wait" | ... или путь к картинке."""
        if os.path.exists(str(shape_or_image)):
            cur = QCursor(QPixmap(shape_or_image), hot_x, hot_y)
        else:
            cur = QCursor(getattr(Qt.CursorShape, _CURSORS.get(shape_or_image, "ArrowCursor")))
        for w in (self.find_all(target) if target is not None else [self.launcher]):
            w.setCursor(cur)
            self._res.add(lambda w=w: safe(w.unsetCursor))

    def pointer_on_buttons(self):
        """Рука при наведении на все кнопки."""
        self.each(".QPushButton", lambda w: (w.setCursor(QCursor(Qt.CursorShape.PointingHandCursor)),
                                             self._res.add(lambda w=w: safe(w.unsetCursor))))

    def load_font(self, path):
        """Подключить шрифт из файла (.ttf/.otf) -> имя семейства (используйте в design.font)."""
        fid = QFontDatabase.addApplicationFont(path)
        fams = QFontDatabase.applicationFontFamilies(fid) if fid != -1 else []
        if not fams:
            raise ValueError(f"Не удалось загрузить шрифт: {path}")
        self._res.add(lambda: safe(lambda: QFontDatabase.removeApplicationFont(fid)))
        return fams[0]

    def app_font(self, family=None, size=None):
        """Шрифт приложения на уровне Qt (для виджетов без QSS-шрифта)."""
        app = QApplication.instance()
        old = app.font()
        f = QFont(old)
        if family:
            f.setFamily(family)
        if size:
            f.setPointSize(size)
        app.setFont(f)
        self._res.add(lambda: safe(lambda: app.setFont(old)))


class _Inspector(QObject):
    def __init__(self, design):
        super().__init__()
        self.d = design

    def eventFilter(self, obj, ev):
        if ev.type() == QEvent.Type.MouseButtonPress:
            mods = ev.modifiers()
            if (mods & Qt.KeyboardModifier.ControlModifier) and (mods & Qt.KeyboardModifier.ShiftModifier):
                w = QApplication.widgetAt(ev.globalPosition().toPoint())
                if w is not None:
                    text = self.d.selector_for(w)
                    QApplication.clipboard().setText(text)
                    self.d._api.toast("🔍 " + self.d.describe(w) + "\n(селектор скопирован)", 4500)
                return True
        return False


class InspectMixin:
    # ------------------------------------------------------------ #
    # Инспектор: как узнать селектор нужного элемента
    # ------------------------------------------------------------ #
    def describe(self, w):
        cls = w.metaObject().className()
        name = w.objectName()
        props = [n.data().decode() for n in w.dynamicPropertyNames() if not n.data().decode().startswith("_")]
        return "%s%s%s" % (cls, ("#" + name) if name else "", ("  [%s]" % ", ".join(props)) if props else "")

    def selector_for(self, w):
        """QSS-селектор виджета: 'QFrame#GameCard' или просто 'QPushButton'."""
        cls = w.metaObject().className()
        return "%s#%s" % (cls, w.objectName()) if w.objectName() else cls

    def object_names(self):
        """Все objectName в интерфейсе (по ним можно стилизовать): {имя: класс}."""
        out = {}
        for w in QApplication.allWidgets():
            if w.objectName() and not w.objectName().startswith("qt_"):
                out.setdefault(w.objectName(), w.metaObject().className())
        return dict(sorted(out.items()))

    def dump(self, root=None, depth=4):
        """Дерево виджетов текстом (для поиска нужных селекторов)."""
        root = root or self.launcher
        lines = []

        def walk(w, level):
            if level > depth:
                return
            lines.append("  " * level + self.describe(w))
            for ch in w.children():
                if isinstance(ch, QWidget) and not ch.objectName().startswith("qt_"):
                    walk(ch, level + 1)
        walk(root, 0)
        return "\n".join(lines)

    def inspector(self, enabled=True):
        """Ctrl+Shift+клик по любому элементу лаунчера показывает его класс, objectName,
        свойства и копирует QSS-селектор в буфер обмена."""
        if self._inspector is not None:
            safe(lambda: QApplication.instance().removeEventFilter(self._inspector))
            self._inspector = None
        if enabled:
            self._inspector = _Inspector(self)
            QApplication.instance().installEventFilter(self._inspector)

            def off():
                if self._inspector is not None:
                    safe(lambda: QApplication.instance().removeEventFilter(self._inspector))
                    self._inspector = None
            self._res.add(off)
