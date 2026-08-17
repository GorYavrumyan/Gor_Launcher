import os
import sys
_THIS_DIR = os.path.dirname(os.path.abspath(__file__))
_PROJECT_ROOT = _THIS_DIR if os.path.exists(os.path.join(_THIS_DIR, "bridge_loader.py")) else os.path.dirname(_THIS_DIR)
for _sub in ("core", "shared", "editors", "remote", "addons_sys", "extras"):
    _p = os.path.join(_PROJECT_ROOT, _sub)
    if _p not in sys.path:
        sys.path.insert(0, _p)

import os
import sys
import json

from PyQt6.QtWidgets import (
    QApplication, QDialog, QVBoxLayout, QHBoxLayout,
    QListWidget, QListWidgetItem, QSplitter, QWidget, QTabWidget,
    QPushButton, QMessageBox,
    QStyledItemDelegate, QStyle, QPlainTextEdit
)
from PyQt6.QtWebEngineWidgets import QWebEngineView
from PyQt6.QtCore import Qt, QUrl, QSize, QRect, QRectF, QEvent, QPointF, QTimer
from PyQt6.QtGui import QIcon, QPainter, QColor, QPen, QFont

from style_loader import apply_global_style
from lang_loader import tr


EMPTY_PAGE = """
<html><head><style>
body {{ background:#0a0a0a;color:#666;font-family:'Segoe UI',Arial,sans-serif;
       display:flex;align-items:center;justify-content:center;height:100vh;margin:0;font-size:16px;}}
</style></head><body><div>{text}</div></body></html>
""".format(text=tr("control_center.empty_page_text"))

ERROR_PAGE_TEMPLATE = """
<html><head><style>
body {{background:#0a0a0a;color:#f0f0f0;font-family:'Segoe UI',Arial,sans-serif;
      display:flex;align-items:center;justify-content:center;height:100vh;margin:0;}}
.box {{text-align:center;border:1px solid #333;background:#141414;border-radius:12px;padding:40px 60px;}}
.icon {{font-size:48px;margin-bottom:16px;}}
.title {{color:#e74c3c;font-size:20px;font-weight:bold;margin-bottom:10px;}}
.msg {{color:#ccc;font-size:14px;}}
</style></head><body>
<div class="box"><div class="icon">⚠️</div><div class="title">""" + tr("control_center.load_error_title") + """</div>
<div class="msg">{message}</div></div></body></html>
"""


# ----------------------------------------------------------------------
# Строка аддона в списке: иконка + имя + переключатель (чекбокс-квадрат)
# ----------------------------------------------------------------------
#
# ВАЖНО: раньше строка рисовалась через QWidget, вставленный в
# QListWidgetItem методом setItemWidget(). У этого подхода есть известная
# проблема в Qt/Windows: такие "виджеты в списке" кэшируются в отдельный
# растровый буфер и текст в них может выглядеть размытым, а нативный
# QCheckBox поверх QSS иногда рисуется "сжатым" системным квадратиком,
# игнорируя часть стиля.
#
# Чтобы гарантированно получить чёткий текст и чёткий квадратный чекбокс,
# строка теперь рисуется вручную через QStyledItemDelegate: имя, подпись,
# иконка и чекбокс рисуются напрямую QPainter'ом прямо на холсте списка,
# без промежуточного виджета - поэтому размытия в принципе быть не может.

ROLE_SUBTITLE = Qt.ItemDataRole.UserRole + 1
ROLE_ENABLED = Qt.ItemDataRole.UserRole + 2

ROW_HEIGHT = 60
CHECKBOX_SIZE = 22


class AddonDelegate(QStyledItemDelegate):
    """Рисует одну строку списка аддонов: иконка + имя + версия слева,
    чёткий квадратный чекбокс справа. on_toggle(addon_path, enabled)
    вызывается при клике по квадрату чекбокса."""

    def __init__(self, on_toggle, parent=None):
        super().__init__(parent)
        self.on_toggle = on_toggle

    def _checkbox_rect(self, option_rect):
        y = option_rect.y() + (option_rect.height() - CHECKBOX_SIZE) // 2
        x = option_rect.right() - CHECKBOX_SIZE - 14
        return QRect(x, y, CHECKBOX_SIZE, CHECKBOX_SIZE)

    def paint(self, painter, option, index):
        painter.save()
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        rect = option.rect
        selected = bool(option.state & QStyle.StateFlag.State_Selected)
        hovered = bool(option.state & QStyle.StateFlag.State_MouseOver)

        # --- фон строки (те же цвета, что и в style.qss для AddonList) ---
        if selected:
            painter.fillRect(rect, QColor("#007acc"))
        elif hovered:
            painter.fillRect(rect, QColor("#1e1e1e"))

        # --- иконка аддона ---
        icon = index.data(Qt.ItemDataRole.DecorationRole)
        content_x = rect.x() + 12
        icon_size = 32
        if icon and not icon.isNull():
            icon.paint(painter, QRect(content_x, rect.y() + (rect.height() - icon_size) // 2,
                                       icon_size, icon_size))
            content_x += icon_size + 12

        checkbox_rect = self._checkbox_rect(rect)
        text_width = checkbox_rect.x() - content_x - 10

        # --- имя аддона (чёткий жирный шрифт) ---
        name = index.data(Qt.ItemDataRole.DisplayRole) or ""
        name_font = QFont(painter.font())
        name_font.setBold(True)
        name_font.setPixelSize(14)
        painter.setFont(name_font)
        painter.setPen(QColor("white") if selected else QColor("#f0f0f0"))
        name_rect = QRect(content_x, rect.y() + 8, text_width, 20)
        painter.drawText(name_rect, Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter, name)

        # --- версия / подпись ---
        subtitle = index.data(ROLE_SUBTITLE) or ""
        if subtitle:
            sub_font = QFont(painter.font())
            sub_font.setBold(False)
            sub_font.setPixelSize(11)
            painter.setFont(sub_font)
            painter.setPen(QColor("#d8ecff") if selected else QColor("#888888"))
            sub_rect = QRect(content_x, rect.y() + 30, text_width, 18)
            painter.drawText(sub_rect, Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter, subtitle)

        # --- чекбокс: чёткий квадрат с галочкой ---
        enabled = bool(index.data(ROLE_ENABLED))
        painter.setPen(QPen(QColor("#005f9e") if enabled else QColor("#444444"), 1.5))
        painter.setBrush(QColor("#007acc") if enabled else QColor("#1a1a1a"))
        painter.drawRoundedRect(QRectF(checkbox_rect), 5, 5)

        if enabled:
            painter.setPen(QPen(QColor("white"), 2.4))
            p1 = QPointF(checkbox_rect.left() + 4, checkbox_rect.center().y() + 1)
            p2 = QPointF(checkbox_rect.center().x() - 1, checkbox_rect.bottom() - 5)
            p3 = QPointF(checkbox_rect.right() - 4, checkbox_rect.top() + 5)
            painter.drawLine(p1, p2)
            painter.drawLine(p2, p3)

        painter.restore()

    def editorEvent(self, event, model, option, index):
        if event.type() == QEvent.Type.MouseButtonRelease:
            if self._checkbox_rect(option.rect).contains(event.pos()):
                addon_path = index.data(Qt.ItemDataRole.UserRole)
                new_state = not bool(index.data(ROLE_ENABLED))
                model.setData(index, new_state, ROLE_ENABLED)
                if self.on_toggle:
                    self.on_toggle(addon_path, new_state)
                return True
        return super().editorEvent(event, model, option, index)

    def sizeHint(self, option, index):
        size = super().sizeHint(option, index)
        size.setHeight(ROW_HEIGHT)
        return size


# ----------------------------------------------------------------------
# Вкладка "Мониторинг" — простое текстовое поле с логом выбранного аддона
# ----------------------------------------------------------------------
class MonitoringTab(QWidget):

    # Как часто перечитываем activity.json выбранного аддона с диска.
    REFRESH_INTERVAL_MS = 1000

    def __init__(self, parent=None):
        super().__init__(parent)
        self.current_addon = None
        self._last_text = None  # чтобы не дёргать QPlainTextEdit, если ничего не изменилось

        outer = QVBoxLayout(self)
        outer.setContentsMargins(16, 16, 16, 16)

        self.log_text = QPlainTextEdit()
        self.log_text.setObjectName("ActivityLog")
        self.log_text.setReadOnly(True)
        self.log_text.setPlaceholderText(tr("control_center.select_addon_hint"))
        outer.addWidget(self.log_text)

        # Живое обновление: аддон в реальном времени пишет свои события в
        # activity.json (см. addons/system_monitor/core/monitor.py), а этот
        # таймер сам, без участия пользователя, раз в секунду перечитывает
        # файл и подтягивает новые записи в текстовое поле.
        self._refresh_timer = QTimer(self)
        self._refresh_timer.timeout.connect(self._refresh)
        self._refresh_timer.start(self.REFRESH_INTERVAL_MS)

    def show_empty(self):
        self.current_addon = None
        self._last_text = None
        self.log_text.clear()

    def update_for_addon(self, addon_info):
        """addon_info: dict с ключами name, path, enabled, config"""
        self.current_addon = addon_info["path"]
        self._last_text = None  # форсируем немедленную перерисовку
        self._refresh()

    def _refresh(self):
        """Вызывается и сразу при выборе аддона, и каждую секунду таймером -
        подтягивает актуальное содержимое activity.json в текстовое поле."""
        if not self.current_addon:
            return

        entries = self._load_activity(self.current_addon)
        icons = {"request": "📨", "change": "✏️", "info": "ℹ️", "error": "⚠️"}

        if not entries:
            text = tr("control_center.no_activity")
        else:
            lines = []
            for entry in entries:
                icon = icons.get(entry.get("type", "info"), "•")
                lines.append(f"{icon}  [{entry.get('time', '--:--')}]  {entry.get('message', '')}")
            text = "\n".join(lines)

        if text == self._last_text:
            return  # ничего нового - не перерисовываем и не сбиваем прокрутку/выделение
        self._last_text = text
        self.log_text.setPlainText(text)

    def _load_activity(self, addon_path):
        """Читает activity.json внутри папки аддона - это ЕДИНСТВЕННЫЙ
        источник записей лога. Файл пишет сам аддон в рантайме (см.
        addons/system_monitor/core/monitor.py как пример) - здесь ничего
        не выдумывается и не подставляется, если аддон ничего не писал -
        лог просто пуст."""
        activity_file = os.path.join(addon_path, "activity.json")
        if not os.path.exists(activity_file):
            return []
        try:
            with open(activity_file, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception:
            return []


# ----------------------------------------------------------------------
# Основное окно Control Center
# ----------------------------------------------------------------------
class ControlCenter(QDialog):

    def __init__(self):
        super().__init__()
        self.setWindowTitle(tr("control_center.window_title"))
        self.resize(1200, 760)

        self.current_web_path = None
        self.addons_by_path = {}  # addon_path -> info dict

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        splitter = QSplitter(Qt.Orientation.Horizontal)
        splitter.setHandleWidth(6)
        splitter.setChildrenCollapsible(False)

        # ---------------- Левая панель: список аддонов ----------------
        self.addon_list = QListWidget()
        self.addon_list.setObjectName("AddonList")
        self.addon_list.setMinimumWidth(260)
        self.addon_list.setMaximumWidth(360)
        self.addon_list.setIconSize(QSize(28, 28))
        self.addon_list.itemClicked.connect(self.on_addon_selected)
        # Делегат рисует имя/подпись/чекбокс сам - без setItemWidget(),
        # поэтому текст не размывается, а чекбокс всегда чёткий квадрат.
        self.addon_list.setItemDelegate(AddonDelegate(on_toggle=self.on_toggle_addon, parent=self.addon_list))
        self.addon_list.setMouseTracking(True)  # для наведения (State_MouseOver) в делегате

        # ---------------- Правая панель: вкладки -----------------------
        self.tabs = QTabWidget()

        # Вкладка 1: просмотр HTML аддона
        self.web_view = QWebEngineView()
        self.web_view.loadFinished.connect(self.on_load_finished)
        self.web_view.setHtml(EMPTY_PAGE)
        self.tabs.addTab(self.web_view, tr("control_center.tab_view"))

        # Вкладка 2: мониторинг аддона (простое текстовое поле с логом)
        self.monitoring_tab = MonitoringTab()
        self.tabs.addTab(self.monitoring_tab, tr("control_center.tab_monitoring"))

        splitter.addWidget(self.addon_list)
        splitter.addWidget(self.tabs)
        splitter.setStretchFactor(0, 0)
        splitter.setStretchFactor(1, 1)
        splitter.setSizes([300, 900])

        layout.addWidget(splitter)

        self.scan_addons()

    # ------------------------------------------------------------------
    # Сканирование аддонов и наполнение списка строками с чекбоксами
    # ------------------------------------------------------------------
    def scan_addons(self):
        base_path = os.path.dirname(os.path.abspath(sys.argv[0]))
        addons_dir = os.path.join(base_path, "addons")
        data_path = os.path.join(base_path, "games_data.json")

        active_addons = []
        if os.path.exists(data_path):
            try:
                with open(data_path, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    active_addons = data.get("addons_list", [])
            except Exception:
                pass

        if not os.path.exists(addons_dir):
            return

        for folder in sorted(os.listdir(addons_dir)):
            addon_path = os.path.join(addons_dir, folder)
            config_path = os.path.join(addon_path, "config.json")
            web_path = os.path.join(addon_path, "web", "index.html")
            icon_path = os.path.join(addon_path, "favicon.png")

            if not (os.path.exists(config_path) and os.path.exists(web_path)):
                continue

            try:
                with open(config_path, 'r', encoding='utf-8') as f:
                    config = json.load(f)
            except Exception:
                config = {}

            name = config.get("name", folder)
            enabled = folder in active_addons or name in active_addons

            info = {
                "name": name,
                "folder": folder,
                "path": addon_path,
                "web_path": web_path,
                "icon_path": icon_path if os.path.exists(icon_path) else None,
                "config": config,
                "enabled": enabled,
            }
            self.addons_by_path[addon_path] = info

            item = QListWidgetItem(name)
            item.setData(Qt.ItemDataRole.UserRole, addon_path)
            version = config.get("version")
            item.setData(ROLE_SUBTITLE, f"v{version}" if version else tr("control_center.version_unknown"))
            item.setData(ROLE_ENABLED, enabled)
            if info["icon_path"]:
                item.setIcon(QIcon(info["icon_path"]))
            item.setSizeHint(QSize(0, ROW_HEIGHT))
            self.addon_list.addItem(item)

    # ------------------------------------------------------------------
    # Клик по аддону в списке -> обновляем обе вкладки
    # ------------------------------------------------------------------
    def on_addon_selected(self, item):
        addon_path = item.data(Qt.ItemDataRole.UserRole)
        info = self.addons_by_path.get(addon_path)
        if not info:
            return

        # Вкладка "Просмотр"
        self.current_web_path = info["web_path"]
        self._load_web(info["web_path"])

        # Вкладка "Мониторинг"
        self.monitoring_tab.update_for_addon(info)

    def _load_web(self, web_path):
        if not web_path or not os.path.exists(web_path):
            self.web_view.setHtml(
                ERROR_PAGE_TEMPLATE.format(
                    message=tr("control_center.web_not_found", path=web_path)
                )
            )
            return
        self.web_view.setUrl(QUrl.fromLocalFile(web_path))

    def on_load_finished(self, ok):
        if not ok:
            self.web_view.setHtml(
                ERROR_PAGE_TEMPLATE.format(
                    message=tr("control_center.addon_load_failed")
                )
            )

    # ------------------------------------------------------------------
    # Переключатель в списке: включить/выключить аддон без открытия
    # ------------------------------------------------------------------
    def on_toggle_addon(self, addon_path, enabled):
        info = self.addons_by_path.get(addon_path)
        if not info:
            return
        info["enabled"] = enabled
        self._save_active_addons()

        # Если сейчас открыт этот же аддон на вкладке мониторинга — обновим статус
        if self.monitoring_tab.current_addon == addon_path:
            self.monitoring_tab.update_for_addon(info)

    def _save_active_addons(self):
        """Синхронизирует список включённых аддонов обратно в games_data.json"""
        base_path = os.path.dirname(os.path.abspath(sys.argv[0]))
        data_path = os.path.join(base_path, "games_data.json")

        data = {"groups": {}, "standalone": [], "history": []}
        if os.path.exists(data_path):
            try:
                with open(data_path, 'r', encoding='utf-8') as f:
                    data = json.load(f)
            except Exception:
                pass

        data["addons_list"] = [
            info["folder"] for info in self.addons_by_path.values() if info["enabled"]
        ]

        try:
            with open(data_path, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=4, ensure_ascii=False)
        except Exception as e:
            QMessageBox.warning(self, tr("control_center.save_error_title"), str(e))

if __name__ == "__main__":
    # Корректная политика масштабирования при дробном DPI (125%/150% в Windows) -
    # без неё виджеты, вставленные через setItemWidget() в QListWidget
    # (наша строка аддона с именем и тумблером), могут рендериться "смазанными".
    if hasattr(Qt, "HighDpiScaleFactorRoundingPolicy"):
        QApplication.setHighDpiScaleFactorRoundingPolicy(
            Qt.HighDpiScaleFactorRoundingPolicy.PassThrough
        )

    app = QApplication(sys.argv)
    app.setWindowIcon(QIcon(os.path.join(os.path.dirname(os.path.abspath(__file__)), "favicon.ico")))

    # Fusion нужен, чтобы кастомный QSS для ::indicator у QCheckBox (тумблер
    # включения аддона) рисовался полностью средствами Qt, а не нативным
    # стилем Windows - иначе чекбокс выглядит как сжатый системный квадратик.
    app.setStyle("Fusion")

    apply_global_style(app)  # общий стиль из style.qss - тот же, что и у остальных модулей
    window = ControlCenter()
    window.show()
    sys.exit(app.exec())