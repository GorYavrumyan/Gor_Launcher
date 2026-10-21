"""
Дополнительные возможности api.ui: диалоги, формы, окна, таблицы, графики,
встроенный браузер, значки на виджетах, страница настроек «из описания».
"""

import math

from PyQt6.QtCore import Qt, QObject, QEvent, QSize, QPointF, QRectF
from PyQt6.QtGui import QColor, QPainter, QPen, QBrush, QFont, QPainterPath
from PyQt6.QtWidgets import (
    QApplication, QWidget, QDialog, QVBoxLayout, QHBoxLayout, QFormLayout, QLabel, QLineEdit,
    QPlainTextEdit, QSpinBox, QDoubleSpinBox, QCheckBox, QComboBox, QPushButton, QFileDialog,
    QColorDialog, QMessageBox, QInputDialog, QTableWidget, QTableWidgetItem, QHeaderView,
    QProgressDialog, QFrame, QScrollArea, QSizePolicy,
)

from .themes import themes
from .design import colors as C


# --------------------------------------------------------------------- #
# Форма по описанию полей
# --------------------------------------------------------------------- #
class _ColorButton(QPushButton):
    def __init__(self, color="#007acc"):
        super().__init__()
        self.setFixedSize(70, 28)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.set_color(color)
        self.clicked.connect(self._pick)

    def set_color(self, c):
        self._c = c
        self.setStyleSheet("QPushButton { background: %s; border: 2px solid #888; border-radius: 6px; }" % c)

    def color(self):
        return self._c

    def _pick(self):
        col = QColorDialog.getColor(QColor(self._c), self)
        if col.isValid():
            self.set_color(col.name())


class _PathEdit(QWidget):
    def __init__(self, folder=False, flt="Все файлы (*.*)"):
        super().__init__()
        self.folder, self.flt = folder, flt
        lay = QHBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        self.edit = QLineEdit()
        btn = QPushButton("…")
        btn.setFixedWidth(34)
        btn.clicked.connect(self._browse)
        lay.addWidget(self.edit, 1)
        lay.addWidget(btn)

    def _browse(self):
        if self.folder:
            p = QFileDialog.getExistingDirectory(self, "Папка", self.edit.text())
        else:
            p, _ = QFileDialog.getOpenFileName(self, "Файл", self.edit.text(), self.flt)
        if p:
            self.edit.setText(p)


class FormWidget(QWidget):
    """Форма по списку описаний полей (см. api.ui.form). values() / set_values()."""
    def __init__(self, fields, values=None):
        super().__init__()
        self.fields = fields
        self.inputs = {}
        lay = QFormLayout(self)
        lay.setLabelAlignment(Qt.AlignmentFlag.AlignLeft)
        for f in fields:
            t = f.get("type", "text")
            if t == "separator":
                line = QFrame()
                line.setFrameShape(QFrame.Shape.HLine)
                lay.addRow(line)
                continue
            if t == "label":
                lbl = QLabel(f.get("text", ""))
                lbl.setWordWrap(True)
                lay.addRow(lbl)
                continue
            w = self._make(f, t)
            self.inputs[f["key"]] = (t, w)
            label = f.get("label", f["key"])
            if t == "bool":
                lay.addRow(w)
                w.setText(label)
            else:
                lay.addRow(label, w)
            if f.get("hint"):
                w.setToolTip(f["hint"])
        self.set_values({**{f["key"]: f.get("default") for f in fields if "key" in f}, **(values or {})})

    @staticmethod
    def _make(f, t):
        if t == "password":
            w = QLineEdit()
            w.setEchoMode(QLineEdit.EchoMode.Password)
        elif t == "multiline":
            w = QPlainTextEdit()
            w.setFixedHeight(f.get("height", 90))
        elif t == "int":
            w = QSpinBox()
            w.setRange(f.get("min", -2_000_000_000), f.get("max", 2_000_000_000))
        elif t == "float":
            w = QDoubleSpinBox()
            w.setRange(f.get("min", -1e9), f.get("max", 1e9))
            w.setDecimals(f.get("decimals", 2))
        elif t == "bool":
            w = QCheckBox()
        elif t == "choice":
            w = QComboBox()
            w.addItems([str(c) for c in f.get("choices", [])])
        elif t == "color":
            w = _ColorButton()
        elif t in ("file", "folder"):
            w = _PathEdit(folder=(t == "folder"), flt=f.get("filter", "Все файлы (*.*)"))
        else:
            w = QLineEdit()
            if f.get("placeholder"):
                w.setPlaceholderText(f["placeholder"])
        return w

    def set_values(self, values):
        for key, (t, w) in self.inputs.items():
            v = values.get(key)
            if v is None:
                continue
            if t in ("text", "password"):
                w.setText(str(v))
            elif t == "multiline":
                w.setPlainText(str(v))
            elif t in ("int", "float"):
                w.setValue(v)
            elif t == "bool":
                w.setChecked(bool(v))
            elif t == "choice":
                i = w.findText(str(v))
                if i >= 0:
                    w.setCurrentIndex(i)
            elif t == "color":
                w.set_color(v)
            elif t in ("file", "folder"):
                w.edit.setText(str(v))

    def values(self):
        out = {}
        for key, (t, w) in self.inputs.items():
            if t in ("text", "password"):
                out[key] = w.text()
            elif t == "multiline":
                out[key] = w.toPlainText()
            elif t in ("int", "float"):
                out[key] = w.value()
            elif t == "bool":
                out[key] = w.isChecked()
            elif t == "choice":
                out[key] = w.currentText()
            elif t == "color":
                out[key] = w.color()
            else:
                out[key] = w.edit.text()
        return out


# --------------------------------------------------------------------- #
# Графики без зависимостей
# --------------------------------------------------------------------- #
class ChartWidget(QWidget):
    """Столбцы / линия / круг / горизонтальные столбцы, цвета из текущей темы."""
    def __init__(self, kind="bar", data=None, title="", color=None, unit=""):
        super().__init__()
        self.kind, self.title, self.unit, self._color = kind, title, unit, color
        self.data = []
        self.setMinimumSize(280, 180)
        self.set_data(data or [])

    def set_data(self, data):
        if isinstance(data, dict):
            data = list(data.items())
        self.data = [(str(k), float(v)) for k, v in data]
        self.update()

    def _fmt(self, v):
        s = ("%.1f" % v).rstrip("0").rstrip(".") if v != int(v) else str(int(v))
        return s + (" " + self.unit if self.unit else "")

    def paintEvent(self, ev):
        c = themes.colors()
        accent = self._color or c["accent"]
        text, muted, grid = QColor(c["text"]), QColor(c["text_muted"]), QColor(c["border"])
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        w, h = self.width(), self.height()
        # свой фон из темы: график читаем на любом родителе
        p.setBrush(QBrush(QColor(c["surface_alt"])))
        p.setPen(QPen(grid, 1))
        p.drawRoundedRect(QRectF(0.5, 0.5, w - 1, h - 1), 10, 10)
        top = 8
        if self.title:
            f = QFont(self.font())
            f.setBold(True)
            p.setFont(f)
            p.setPen(text)
            p.drawText(QRectF(0, 0, w, 24), Qt.AlignmentFlag.AlignCenter, self.title)
            top = 30
        if not self.data:
            p.setPen(muted)
            p.drawText(QRectF(0, 0, w, h), Qt.AlignmentFlag.AlignCenter, "Нет данных")
            return
        n = len(self.data)
        vmax = max(v for _, v in self.data) or 1
        if self.kind == "pie":
            self._pie(p, w, h, top, text, muted, accent)
            return
        left, bottom = 14, 22
        area = QRectF(left, top, w - left - 10, h - top - bottom)
        p.setPen(QPen(grid, 1))
        for i in range(5):
            y = area.bottom() - area.height() * i / 4
            p.drawLine(QPointF(area.left(), y), QPointF(area.right(), y))
        if self.kind == "hbar":
            row = area.height() / n
            for i, (label, v) in enumerate(self.data):
                bw = max(2, (area.width() - 80 - 78) * v / vmax)
                r = QRectF(area.left() + 80, area.top() + i * row + row * 0.18, max(2, bw), row * 0.64)
                p.setBrush(QBrush(QColor(accent)))
                p.setPen(Qt.PenStyle.NoPen)
                p.drawRoundedRect(r, 4, 4)
                p.setPen(muted)
                lab = p.fontMetrics().elidedText(label, Qt.TextElideMode.ElideRight, 72)
                p.drawText(QRectF(area.left(), r.top(), 76, r.height()), Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter, lab)
                p.setPen(text)
                p.drawText(QRectF(r.right() + 4, r.top(), 80, r.height()), Qt.AlignmentFlag.AlignVCenter, self._fmt(v))
            return
        step = area.width() / n
        pts = []
        for i, (label, v) in enumerate(self.data):
            x = area.left() + step * (i + 0.5)
            y = area.bottom() - area.height() * v / (vmax * 1.18)      # запас под подпись
            pts.append(QPointF(x, y))
            p.setPen(muted)
            lab = p.fontMetrics().elidedText(label, Qt.TextElideMode.ElideRight, int(step - 4))
            p.drawText(QRectF(x - step / 2, area.bottom() + 2, step, bottom), Qt.AlignmentFlag.AlignCenter, lab)
        if self.kind == "line":
            path = QPainterPath(pts[0])
            for pt in pts[1:]:
                path.lineTo(pt)
            p.setPen(QPen(QColor(accent), 2.5))
            p.setBrush(Qt.BrushStyle.NoBrush)
            p.drawPath(path)
            for (label, v), pt in zip(self.data, pts):
                p.setBrush(QBrush(QColor(accent)))
                p.setPen(Qt.PenStyle.NoPen)
                p.drawEllipse(pt, 4, 4)
                p.setPen(text)
                p.drawText(QRectF(pt.x() - 30, pt.y() - 22, 60, 16), Qt.AlignmentFlag.AlignCenter, self._fmt(v))
        else:
            bw = step * 0.62
            for (label, v), pt in zip(self.data, pts):
                r = QRectF(pt.x() - bw / 2, pt.y(), bw, area.bottom() - pt.y())
                g = QBrush(QColor(accent))
                p.setBrush(g)
                p.setPen(Qt.PenStyle.NoPen)
                p.drawRoundedRect(r, 4, 4)
                p.setPen(text)
                p.drawText(QRectF(pt.x() - 30, pt.y() - 18, 60, 16), Qt.AlignmentFlag.AlignCenter, self._fmt(v))

    def _pie(self, p, w, h, top, text, muted, accent):
        total = sum(v for _, v in self.data) or 1
        size = min(w * 0.42, h - top - 10)
        rect = QRectF(14, top + (h - top - size) / 2, size, size)
        start = 90 * 16
        base = QColor(accent)
        for i, (label, v) in enumerate(self.data):
            span = int(-360 * 16 * v / total)
            col = QColor(C.hue_shift(base.name(), i * 360 / max(1, len(self.data))))
            p.setBrush(QBrush(col))
            p.setPen(QPen(QColor(themes.colors()["bg"]), 2))
            p.drawPie(rect, start, span)
            start += span
            ly = top + 6 + i * 20
            p.setBrush(QBrush(col))
            p.setPen(Qt.PenStyle.NoPen)
            p.drawRoundedRect(QRectF(rect.right() + 18, ly + 3, 12, 12), 3, 3)
            p.setPen(text)
            avail = int(w - rect.right() - 44)
            txt = p.fontMetrics().elidedText(f"{label}  {self._fmt(v)} ({v / total * 100:.0f}%)",
                                             Qt.TextElideMode.ElideRight, max(40, avail))
            p.drawText(QRectF(rect.right() + 36, ly, max(40, avail), 18), Qt.AlignmentFlag.AlignVCenter, txt)


# --------------------------------------------------------------------- #
# Значок на углу виджета
# --------------------------------------------------------------------- #
class _BadgeFilter(QObject):
    def __init__(self, host, label, corner):
        super().__init__(host)
        self.host, self.label, self.corner = host, label, corner
        host.installEventFilter(self)
        self.place()

    def place(self):
        l, h = self.label, self.host
        l.adjustSize()
        x = h.width() - l.width() - 6 if "r" in self.corner else 6
        y = h.height() - l.height() - 6 if "b" in self.corner else 6
        l.move(x, y)
        l.raise_()

    def eventFilter(self, obj, ev):
        if ev.type() in (QEvent.Type.Resize, QEvent.Type.Show):
            self.place()
        return False


class UIExtraMixin:
    # ------------------------------------------------------------ диалоги
    def _title(self, title):
        return title or self._api.name

    def info(self, text, title=None):
        QMessageBox.information(self.launcher, self._title(title), text)

    def warn(self, text, title=None):
        QMessageBox.warning(self.launcher, self._title(title), text)

    def error(self, text, title=None):
        QMessageBox.critical(self.launcher, self._title(title), text)

    def confirm(self, text, title=None, default=False):
        """Вопрос Да/Нет -> True/False."""
        btn = QMessageBox.StandardButton
        r = QMessageBox.question(self.launcher, self._title(title), text, btn.Yes | btn.No,
                                 btn.Yes if default else btn.No)
        return r == btn.Yes

    def prompt(self, text, default="", title=None):
        """Ввод строки -> str или None."""
        v, ok = QInputDialog.getText(self.launcher, self._title(title), text, text=default)
        return v if ok else None

    def choose(self, text, options, title=None, current=0):
        """Выбор из списка -> выбранная строка или None."""
        v, ok = QInputDialog.getItem(self.launcher, self._title(title), text, [str(o) for o in options], current, False)
        return v if ok else None

    def pick_file(self, title="Выберите файл", filters="Все файлы (*.*)", start=""):
        p, _ = QFileDialog.getOpenFileName(self.launcher, title, start, filters)
        return p or None

    def pick_files(self, title="Выберите файлы", filters="Все файлы (*.*)", start=""):
        ps, _ = QFileDialog.getOpenFileNames(self.launcher, title, start, filters)
        return ps

    def pick_folder(self, title="Выберите папку", start=""):
        p = QFileDialog.getExistingDirectory(self.launcher, title, start)
        return p or None

    def save_file(self, title="Сохранить как", filters="Все файлы (*.*)", start=""):
        p, _ = QFileDialog.getSaveFileName(self.launcher, title, start, filters)
        return p or None

    def pick_color(self, initial="#007acc", title="Выберите цвет"):
        c = QColorDialog.getColor(QColor(initial), self.launcher, title)
        return c.name() if c.isValid() else None

    # ------------------------------------------------------------ формы
    def form_widget(self, fields, values=None):
        """Виджет-форма (для встраивания): .values() / .set_values()."""
        return FormWidget(fields, values)

    def form(self, title, fields, values=None, ok="Сохранить", cancel="Отмена"):
        """Модальная форма по описанию полей -> dict значений или None (отмена).
        Типы полей: text password multiline int float bool choice color file folder label separator."""
        dlg = QDialog(self.launcher)
        dlg.setWindowTitle(title)
        lay = QVBoxLayout(dlg)
        fw = FormWidget(fields, values)
        lay.addWidget(fw)
        row = QHBoxLayout()
        row.addStretch(1)
        b_cancel, b_ok = QPushButton(cancel), QPushButton(ok)
        b_ok.setDefault(True)
        b_cancel.clicked.connect(dlg.reject)
        b_ok.clicked.connect(dlg.accept)
        row.addWidget(b_cancel)
        row.addWidget(b_ok)
        lay.addLayout(row)
        dlg.setMinimumWidth(420)
        return fw.values() if dlg.exec() == QDialog.DialogCode.Accepted else None

    def settings_tab(self, fields, title="⚙ Настройки"):
        """Готовая вкладка настроек аддона: поля из описания, значения хранятся в api.settings.
        Возвращает виджет-форму. Нажатие «Сохранить» записывает всё в settings.json."""
        api = self._api
        page = QWidget()
        lay = QVBoxLayout(page)
        fw = FormWidget(fields, api.settings.all())
        lay.addWidget(fw)
        btn = QPushButton("Сохранить")

        def save():
            for k, v in fw.values().items():
                api.settings.set(k, v)
            self.toast("Настройки сохранены")
        btn.clicked.connect(save)
        lay.addWidget(btn, 0, Qt.AlignmentFlag.AlignLeft)
        lay.addStretch(1)
        self.add_tab(page, title)
        return fw

    # ------------------------------------------------------------ окна
    def window(self, title, widget, size=None, modal=False, on_close=None):
        """Отдельное окно с вашим виджетом. Закрывается само при выгрузке аддона."""
        dlg = QDialog(self.launcher)
        dlg.setWindowTitle(title)
        lay = QVBoxLayout(dlg)
        lay.setContentsMargins(6, 6, 6, 6)
        lay.addWidget(widget)
        if size:
            dlg.resize(*size)
        dlg.setModal(modal)
        if on_close:
            dlg.finished.connect(lambda *_: on_close())
        dlg.show()

        def undo():
            try:
                dlg.close()
                dlg.deleteLater()
            except RuntimeError:
                pass
        self._res.add(undo)
        return dlg

    def progress(self, text="Подождите…", maximum=100, cancellable=False):
        """Окно прогресса: p = api.ui.progress(); p.setValue(30); p.close()."""
        dlg = QProgressDialog(text, "Отмена" if cancellable else None, 0, maximum, self.launcher)
        dlg.setWindowModality(Qt.WindowModality.WindowModal)
        dlg.setMinimumDuration(0)
        dlg.setAutoClose(True)
        self._res.add(lambda: dlg.close())
        return dlg

    # ------------------------------------------------------------ таблицы, графики, веб
    def table(self, columns, rows=(), on_row_click=None):
        """Таблица: columns - заголовки, rows - список списков."""
        t = QTableWidget(0, len(columns))
        t.setHorizontalHeaderLabels(columns)
        t.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        t.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        t.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        t.verticalHeader().setVisible(False)
        self.fill_table(t, rows)
        if on_row_click:
            t.cellClicked.connect(lambda r, c: on_row_click(r))
        return t

    @staticmethod
    def fill_table(table, rows):
        table.setRowCount(len(rows))
        for r, row in enumerate(rows):
            for c, val in enumerate(row):
                table.setItem(r, c, QTableWidgetItem(str(val)))

    def chart(self, kind="bar", data=None, title="", color=None, unit=""):
        """График: kind = bar | hbar | line | pie; data - [(подпись, значение)] или dict.
        Возвращает виджет с методом set_data()."""
        return ChartWidget(kind, data, title, color, unit)

    def web_view(self, url=None, html=None):
        """Встроенный браузер (QtWebEngine) -> виджет или None, если WebEngine недоступен."""
        try:
            from PyQt6.QtWebEngineWidgets import QWebEngineView
            from PyQt6.QtCore import QUrl
        except Exception:
            return None
        v = QWebEngineView()
        if html is not None:
            v.setHtml(html)
        elif url:
            v.load(QUrl(url))
        return v

    def add_web_tab(self, title, url=None, html=None):
        v = self.web_view(url, html)
        if v is None:
            return None
        self.add_tab(v, title)
        return v

    # ------------------------------------------------------------ значки
    def badge(self, target, text, color="{{danger}}", fg="#ffffff", corner="tr", future=True):
        """Маленький значок на углу виджетов: api.ui.badge("GameCard", "NEW").
        corner: tr | tl | br | bl. Подхватывает и новые виджеты."""
        d = self._api.design

        def apply(w):
            lbl = QLabel(text, w)
            lbl.setStyleSheet("QLabel { background: %s; color: %s; border-radius: 8px; "
                              "padding: 2px 8px; font-size: 11px; font-weight: bold; }"
                              % (d._fill(color), fg))
            lbl.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
            lbl.show()
            f = _BadgeFilter(w, lbl, corner)

            def undo():
                try:
                    w.removeEventFilter(f)
                    lbl.setParent(None)
                    lbl.deleteLater()
                except RuntimeError:
                    pass
            self._res.add(undo)
        d.each(target, apply, future=future)
