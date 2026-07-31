import os
import sys
import json
import random
from datetime import datetime

from PyQt6.QtWidgets import (
    QApplication, QDialog, QVBoxLayout, QHBoxLayout,
    QListWidget, QListWidgetItem, QSplitter, QWidget, QTabWidget,
    QLabel, QFrame, QPushButton, QMessageBox, QScrollArea,
    QStyledItemDelegate, QStyle
)
from PyQt6.QtWebEngineWidgets import QWebEngineView
from PyQt6.QtCore import Qt, QUrl, QSize, QRect, QRectF, QEvent, QPointF
from PyQt6.QtGui import QIcon, QPainter, QColor, QPen, QFont

from style_loader import apply_global_style


EMPTY_PAGE = """
<html><head><style>
body { background:#0a0a0a;color:#666;font-family:'Segoe UI',Arial,sans-serif;
       display:flex;align-items:center;justify-content:center;height:100vh;margin:0;font-size:16px;}
</style></head><body><div>⬅️ Выберите аддон слева, чтобы открыть его интерфейс</div></body></html>
"""

ERROR_PAGE_TEMPLATE = """
<html><head><style>
body {{background:#0a0a0a;color:#f0f0f0;font-family:'Segoe UI',Arial,sans-serif;
      display:flex;align-items:center;justify-content:center;height:100vh;margin:0;}}
.box {{text-align:center;border:1px solid #333;background:#141414;border-radius:12px;padding:40px 60px;}}
.icon {{font-size:48px;margin-bottom:16px;}}
.title {{color:#e74c3c;font-size:20px;font-weight:bold;margin-bottom:10px;}}
.msg {{color:#ccc;font-size:14px;}}
</style></head><body>
<div class="box"><div class="icon">⚠️</div><div class="title">Не удалось загрузить аддон</div>
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
# Карточка-контейнер вкладки мониторинга.
# Стиль (фон/рамка/скругление) берётся из style.qss: QFrame#MonitorCard,
# заголовок карточки — QLabel#CardTitle.
# ----------------------------------------------------------------------
def make_card(title_text=None):
    frame = QFrame()
    frame.setObjectName("MonitorCard")
    lay = QVBoxLayout(frame)
    lay.setContentsMargins(16, 14, 16, 14)
    lay.setSpacing(10)
    if title_text:
        title = QLabel(title_text)
        title.setObjectName("CardTitle")
        lay.addWidget(title)
    return frame, lay


# ----------------------------------------------------------------------
# Вкладка "Мониторинг" — динамически перестраивается под выбранный аддон
# ----------------------------------------------------------------------
class MonitoringTab(QWidget):

    def __init__(self, on_action, parent=None):
        super().__init__(parent)
        self.on_action = on_action  # callback(addon_path, action_name)
        self.current_addon = None

        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        content = QWidget()
        self.root_lay = QVBoxLayout(content)
        self.root_lay.setContentsMargins(16, 16, 16, 16)
        self.root_lay.setSpacing(14)
        scroll.setWidget(content)
        outer.addWidget(scroll)

        # --- Карточка статуса ---
        self.status_card, status_lay = make_card("Статус аддона")
        header = QHBoxLayout()
        self.big_name = QLabel("—")
        self.big_name.setObjectName("AddonBigName")
        self.status_pill = QLabel("НЕИЗВЕСТНО")
        self.status_pill.setObjectName("StatusPill")
        header.addWidget(self.big_name, stretch=1)
        header.addWidget(self.status_pill, alignment=Qt.AlignmentFlag.AlignRight)
        status_lay.addLayout(header)

        self.status_desc = QLabel("Выберите аддон слева, чтобы увидеть подробности.")
        self.status_desc.setObjectName("AddonRowSub")
        self.status_desc.setWordWrap(True)
        status_lay.addWidget(self.status_desc)

        self.root_lay.addWidget(self.status_card)

        # --- Карточка лога активности ---
        self.log_card, log_lay = make_card("Лог активности / запросы аддона")
        self.log_list = QListWidget()
        self.log_list.setObjectName("ActivityLog")
        self.log_list.setMinimumHeight(220)
        log_lay.addWidget(self.log_list)
        self.root_lay.addWidget(self.log_card)

        # --- Карточка интерактивных элементов управления ---
        self.controls_card, ctrl_lay = make_card("Управление аддоном")
        btn_row = QHBoxLayout()

        # Акцентная кнопка (стиль #PrimaryBtn из style.qss)
        self.approve_btn = QPushButton("✅ Подтвердить запрос")
        self.approve_btn.setObjectName("PrimaryBtn")
        self.approve_btn.clicked.connect(lambda: self._fire("approve"))

        # Обычная кнопка — без objectName, берёт базовый стиль QPushButton
        self.restart_btn = QPushButton("🔁 Перезапустить аддон")
        self.restart_btn.clicked.connect(lambda: self._fire("restart"))

        # Красная "опасная" кнопка — переиспользуем уже существующий
        # в style.qss стиль #StopBtn (тот же, что и для остановки процесса)
        self.revoke_btn = QPushButton("⛔ Отклонить / Отключить")
        self.revoke_btn.setObjectName("StopBtn")
        self.revoke_btn.clicked.connect(lambda: self._fire("revoke"))

        btn_row.addWidget(self.approve_btn)
        btn_row.addWidget(self.restart_btn)
        btn_row.addWidget(self.revoke_btn)
        ctrl_lay.addLayout(btn_row)

        self.root_lay.addWidget(self.controls_card)
        self.root_lay.addStretch()

        self._set_enabled(False)

    def _fire(self, action_name):
        if self.current_addon and self.on_action:
            self.on_action(self.current_addon, action_name)

    def _set_enabled(self, value):
        for w in (self.approve_btn, self.restart_btn, self.revoke_btn):
            w.setEnabled(value)

    def show_empty(self):
        self.current_addon = None
        self.big_name.setText("—")
        self.status_desc.setText("Выберите аддон слева, чтобы увидеть подробности.")
        self._set_status_pill(None)
        self.log_list.clear()
        self._set_enabled(False)

    def _set_status_pill(self, enabled):
        """Переключает индикатор активности через динамическое свойство
        state="on"/"off" (тот же приём, что и favorite=true у GameCard
        в GorLauncher), чтобы цвет брался из style.qss, а не из кода."""
        if enabled is None:
            self.status_pill.setText("НЕИЗВЕСТНО")
            self.status_pill.setProperty("state", "")
        elif enabled:
            self.status_pill.setText("● АКТИВЕН")
            self.status_pill.setProperty("state", "on")
        else:
            self.status_pill.setText("● ВЫКЛЮЧЕН")
            self.status_pill.setProperty("state", "off")
        # переприменяем стиль после смены динамического свойства
        self.status_pill.style().unpolish(self.status_pill)
        self.status_pill.style().polish(self.status_pill)

    def update_for_addon(self, addon_info):
        """addon_info: dict с ключами name, path, enabled, config"""
        self.current_addon = addon_info["path"]
        self.big_name.setText(addon_info["name"])
        self._set_status_pill(addon_info["enabled"])

        config = addon_info.get("config", {})
        desc = config.get("description") or "Описание для этого аддона не указано в config.json."
        version = config.get("version", "—")
        self.status_desc.setText(f"{desc}\nВерсия: {version}")

        self.log_list.clear()
        entries = self._load_activity(addon_info["path"])
        if not entries:
            self.log_list.addItem(QListWidgetItem("Нет записей активности для этого аддона."))
        else:
            icons = {"request": "📨", "change": "✏️", "info": "ℹ️", "error": "⚠️"}
            for entry in entries:
                icon = icons.get(entry.get("type", "info"), "•")
                text = f"{icon}  [{entry.get('time', '--:--')}]  {entry.get('message', '')}"
                self.log_list.addItem(QListWidgetItem(text))

        self._set_enabled(True)

    def _load_activity(self, addon_path):
        """Пытается прочитать activity.json внутри папки аддона.
        Если файла нет — возвращает несколько демонстрационных записей,
        чтобы UI можно было проверить сразу без реальных логов."""
        activity_file = os.path.join(addon_path, "activity.json")
        if os.path.exists(activity_file):
            try:
                with open(activity_file, 'r', encoding='utf-8') as f:
                    return json.load(f)
            except Exception:
                pass

        # Демонстрационные записи (fallback), если реального лога нет
        sample_actions = [
            ("request", "Аддон запросил доступ к папке сохранений."),
            ("change", "Изменена настройка разрешения экрана до 1920x1080."),
            ("info", "Аддон инициализирован без ошибок."),
            ("error", "Не удалось найти файл конфигурации потоковой передачи."),
        ]
        now = datetime.now()
        return [
            {"type": t, "message": m, "time": now.strftime("%H:%M")}
            for t, m in random.sample(sample_actions, k=min(3, len(sample_actions)))
        ]


# ----------------------------------------------------------------------
# Основное окно Control Center
# ----------------------------------------------------------------------
class ControlCenter(QDialog):

    def __init__(self):
        super().__init__()
        self.setWindowTitle("GOR Control Center - Управление аддонами")
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
        self.tabs.addTab(self.web_view, "🌐 Просмотр")

        # Вкладка 2: мониторинг аддона
        self.monitoring_tab = MonitoringTab(on_action=self.handle_monitor_action)
        self.tabs.addTab(self.monitoring_tab, "📊 Мониторинг")

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
            item.setData(ROLE_SUBTITLE, f"v{version}" if version else "версия неизвестна")
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
                    message=f"Файл index.html не найден по пути:<br><code>{web_path}</code>"
                )
            )
            return
        self.web_view.setUrl(QUrl.fromLocalFile(web_path))

    def on_load_finished(self, ok):
        if not ok:
            self.web_view.setHtml(
                ERROR_PAGE_TEMPLATE.format(
                    message="Аддон не смог загрузиться. Проверьте файлы web/index.html."
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
            QMessageBox.warning(self, "Ошибка сохранения", str(e))

    # ------------------------------------------------------------------
    # Обработка кнопок на карточке "Управление аддоном"
    # ------------------------------------------------------------------
    def handle_monitor_action(self, addon_path, action_name):
        info = self.addons_by_path.get(addon_path)
        if not info:
            return

        if action_name == "approve":
            QMessageBox.information(self, "Готово", f"Запрос аддона «{info['name']}» подтверждён.")
        elif action_name == "restart":
            QMessageBox.information(self, "Перезапуск", f"Аддон «{info['name']}» будет перезапущен.")
        elif action_name == "revoke":
            reply = QMessageBox.question(
                self, "Отключение аддона",
                f"Отключить «{info['name']}»?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
            )
            if reply == QMessageBox.StandardButton.Yes:
                info["enabled"] = False
                self._save_active_addons()
                self.monitoring_tab.update_for_addon(info)
                self._refresh_row_checkbox(addon_path, False)

    def _refresh_row_checkbox(self, addon_path, enabled):
        """Обновляет чекбокс в списке слева, когда аддон отключается через
        кнопку на вкладке мониторинга (сам чекбокс теперь рисуется
        делегатом, так что просто обновляем данные и просим перерисовать)."""
        for i in range(self.addon_list.count()):
            item = self.addon_list.item(i)
            if item.data(Qt.ItemDataRole.UserRole) == addon_path:
                item.setData(ROLE_ENABLED, enabled)
                break
        self.addon_list.viewport().update()


if __name__ == "__main__":
    # Корректная политика масштабирования при дробном DPI (125%/150% в Windows) -
    # без неё виджеты, вставленные через setItemWidget() в QListWidget
    # (наша строка аддона с именем и тумблером), могут рендериться "смазанными".
    if hasattr(Qt, "HighDpiScaleFactorRoundingPolicy"):
        QApplication.setHighDpiScaleFactorRoundingPolicy(
            Qt.HighDpiScaleFactorRoundingPolicy.PassThrough
        )

    app = QApplication(sys.argv)

    # Fusion нужен, чтобы кастомный QSS для ::indicator у QCheckBox (тумблер
    # включения аддона) рисовался полностью средствами Qt, а не нативным
    # стилем Windows - иначе чекбокс выглядит как сжатый системный квадратик.
    app.setStyle("Fusion")

    apply_global_style(app)  # общий стиль из style.qss - тот же, что и у остальных модулей
    window = ControlCenter()
    window.show()
    sys.exit(app.exec())