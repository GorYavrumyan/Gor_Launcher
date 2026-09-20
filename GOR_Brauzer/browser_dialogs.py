"""
browser_dialogs.py
-------------------
Диалоговые окна GOR Browser, работающие через parent (GORBrowser).

Главный экспорт - BrowserSettingsWindow: одно окно настроек с красивыми
вкладками (слева), объединяющее всё, что раньше было раскидано по трём
отдельным диалогам (SettingsDialog / CustomizationManager /
ExtensionManager). Сами разделы реализованы как независимые QWidget-вкладки
(GeneralTab, AppearanceTab, StartPageTab, BackupTab, ExtensionsTab), которые
можно при желании переиспользовать по отдельности.

Все вкладки читают/пишут parent.settings (или parent.extensions) и вызывают
parent.save_data(...) - т.е. ожидают, что parent - это экземпляр GORBrowser
из browser_widget.py.
"""

import base64
import mimetypes

from PyQt6.QtCore import Qt, QSize
from PyQt6.QtGui import QAction, QColor, QFont
from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QComboBox, QCheckBox,
    QSlider, QFileDialog, QColorDialog, QListWidget, QListWidgetItem,
    QInputDialog, QMenu, QLineEdit, QMessageBox, QWidget, QStackedWidget,
    QScrollArea, QFrame, QFontComboBox, QSpinBox,
)

from browser_constants import (
    SEARCH_ENGINES, SETTINGS_FILE, EXTENSIONS_FILE, DEFAULT_SETTINGS,
)
from browser_passwords import open_password_manager
from lang_loader import tr


# ---------------------------------------------------------------------------
# Общий "дизайн-язык" окна настроек: карточки-секции, поля с фокус-эффектом,
# чекбоксы с акцентной заливкой, кнопки с hover/pressed-состояниями.
# Все вкладки настроек собираются из этих же кирпичиков, поэтому изменение
# стиля тут сразу подтягивается везде.
# ---------------------------------------------------------------------------

def _accent():
    return "#4c6ef5"


_FIELD_QSS = """
    QLineEdit, QComboBox {
        background: #1c1e23; color: white; padding: 10px 12px;
        border-radius: 9px; border: 1px solid #34363d;
        selection-background-color: #4c6ef5;
    }
    QLineEdit:hover, QComboBox:hover { border: 1px solid #454852; }
    QLineEdit:focus, QComboBox:focus { border: 1px solid #4c6ef5; background: #202329; }
    QComboBox::drop-down { border: none; width: 24px; }
    QComboBox::down-arrow { image: none; border-left: 4px solid transparent;
        border-right: 4px solid transparent; border-top: 5px solid #9aa0aa; margin-right: 8px; }
"""

_CHECKBOX_QSS = """
    QCheckBox { spacing: 12px; padding: 5px 2px; color: #e7e8ea; font-size: 13px; }
    QCheckBox::indicator {
        width: 19px; height: 19px; border-radius: 6px;
        border: 1.5px solid #43454d; background: #1c1e23;
    }
    QCheckBox::indicator:hover { border: 1.5px solid #5a5d66; }
    QCheckBox::indicator:checked {
        background: #4c6ef5; border: 1.5px solid #4c6ef5;
        image: url(none);
    }
"""


def _button_qss(kind="secondary", accent="#4c6ef5"):
    """kind: 'primary' (акцентная заливка), 'secondary' (тёмная плашка),
    'ghost' (прозрачная с рамкой), 'danger' (для деструктивных действий)."""
    if kind == "primary":
        return f"""
            QPushButton {{
                background: {accent}; color: white; padding: 10px 16px;
                border-radius: 9px; font-weight: 600; border: none;
            }}
            QPushButton:hover {{ background: {_lighten(accent)}; }}
            QPushButton:pressed {{ background: {_darken(accent)}; }}
        """
    if kind == "ghost":
        return """
            QPushButton {
                background: transparent; color: #9aa0aa; padding: 10px 18px;
                border-radius: 9px; border: 1px solid #3a3c44;
            }
            QPushButton:hover { background: #1e2025; color: white; border: 1px solid #4a4d56; }
        """
    if kind == "danger":
        return """
            QPushButton {
                background: #2c1517; color: #ff8f96; padding: 10px 14px;
                border-radius: 9px; font-weight: 600; border: 1px solid #4a2226;
            }
            QPushButton:hover { background: #3a1a1d; border: 1px solid #6b2a2f; }
        """
    # secondary (по умолчанию) - для обычных "плашечных" кнопок-действий
    return """
        QPushButton {
            background: #1e2025; color: #e7e8ea; padding: 10px 14px;
            border-radius: 9px; border: 1px solid #34363d; text-align: left;
        }
        QPushButton:hover { background: #262930; border: 1px solid #454852; }
        QPushButton:pressed { background: #1a1c21; }
    """


def _lighten(hex_color, amount=22):
    return _shift(hex_color, amount)


def _darken(hex_color, amount=22):
    return _shift(hex_color, -amount)


def _shift(hex_color, amount):
    hex_color = hex_color.lstrip("#")
    if len(hex_color) != 6:
        return "#" + hex_color
    r, g, b = (int(hex_color[i:i + 2], 16) for i in (0, 2, 4))
    r, g, b = (max(0, min(255, c + amount)) for c in (r, g, b))
    return f"#{r:02x}{g:02x}{b:02x}"


def _section_label(text):
    """Оставлено для обратной совместимости - там, где карточка не нужна,
    например маленькие подписи внутри карточки (см. _card)."""
    lbl = QLabel(text)
    lbl.setStyleSheet("color: #9aa0aa; font-size: 11px; font-weight: 700; letter-spacing: 0.6px;")
    return lbl


def _h_rule():
    line = QFrame()
    line.setFrameShape(QFrame.Shape.HLine)
    line.setStyleSheet("color: #2a2c31; max-height: 1px; border: none; background: #24262b;")
    line.setFixedHeight(1)
    return line


def _muted_label(text):
    """Маленькая серая подпись НАД полем ввода внутри карточки (не путать с
    _section_label - это подпись для отдельного поля, а не заголовок всей секции)."""
    lbl = QLabel(text)
    lbl.setStyleSheet("color: #8a8f99; font-size: 11.5px; font-weight: 600;")
    return lbl


def _card(icon, title, accent="#4c6ef5", hint=None):
    """Карточка-секция: скруглённая рамка с лёгкой заливкой, акцентная
    иконка+заголовок сверху, опциональная серая подсказка снизу заголовка.
    Возвращает (card_frame, content_layout) - контент вкладки добавляется
    в content_layout, а card_frame добавляется в layout вкладки целиком."""
    card = QFrame(objectName="SettingsCard")
    card.setStyleSheet(f"""
        QFrame#SettingsCard {{
            background: #17181c; border: 1px solid #262830; border-radius: 14px;
        }}
    """)
    outer = QVBoxLayout(card)
    outer.setContentsMargins(20, 16, 20, 18)
    outer.setSpacing(10)

    head_row = QHBoxLayout()
    head_row.setSpacing(10)
    icon_lbl = QLabel(icon)
    icon_lbl.setStyleSheet(f"font-size: 15px; background: {accent}22; border-radius: 8px; padding: 4px 8px;")
    title_lbl = QLabel(title)
    title_lbl.setStyleSheet("color: white; font-size: 13px; font-weight: 700; letter-spacing: 0.2px;")
    head_row.addWidget(icon_lbl)
    head_row.addWidget(title_lbl)
    head_row.addStretch()
    outer.addLayout(head_row)

    if hint:
        hint_lbl = QLabel(hint)
        hint_lbl.setWordWrap(True)
        hint_lbl.setStyleSheet("color: #6b7280; font-size: 11.5px; margin-bottom: 2px;")
        outer.addWidget(hint_lbl)

    content = QVBoxLayout()
    content.setSpacing(10)
    outer.addLayout(content)
    return card, content


class GeneralTab(QWidget):
    """Поиск по умолчанию + виджеты стартовой страницы (бывший SettingsDialog)."""

    def __init__(self, parent_browser):
        super().__init__()
        self.parent_browser = parent_browser
        s = parent_browser.settings
        accent = s.get("theme_color", "#4c6ef5")

        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 22, 24, 22)
        layout.setSpacing(14)

        card1, c1 = _card("🔍", "Поисковая система", accent, "Используется в адресной строке при вводе не-URL запроса.")
        self.search_combo = QComboBox()
        self.search_combo.addItems(SEARCH_ENGINES.keys())
        self.search_combo.setCurrentText(s.get("search_engine", "Google"))
        self.search_combo.setStyleSheet(_FIELD_QSS)
        c1.addWidget(self.search_combo)
        layout.addWidget(card1)

        card2, c2 = _card("🧩", "Виджеты на главной", accent, "Что показывать на стартовой странице браузера.")
        self.check_clock = QCheckBox("🕐  Показывать часы")
        self.check_clock.setChecked(s.get("show_clock", True))
        self.check_title = QCheckBox("🏷️  Показывать заголовок")
        self.check_title.setChecked(s.get("show_title", True))
        self.check_todo = QCheckBox("📝  Показывать список задач")
        self.check_todo.setChecked(s.get("show_todo", True))
        for cb in (self.check_clock, self.check_title, self.check_todo):
            cb.setStyleSheet(_CHECKBOX_QSS)
            c2.addWidget(cb)
        layout.addWidget(card2)

        # Спящие вкладки (Tab Suspender) - раньше жило в меню ⋮, перенесено
        # сюда по ТЗ (меню ⋮ сокращено до 5 пунктов).
        card3, c3 = _card("💤", "Спящие вкладки", accent,
                           "Фоновые вкладки, неактивные дольше таймаута, выгружаются из памяти.")
        self.check_suspend = QCheckBox("Автоматически выгружать неактивные вкладки из RAM")
        self.check_suspend.setChecked(s.get("tab_suspend_enabled", True))
        self.check_suspend.setStyleSheet(_CHECKBOX_QSS)
        c3.addWidget(self.check_suspend)
        c3.addWidget(_muted_label("Таймаут неактивности (минут)"))
        self.suspend_minutes_spin = QSpinBox()
        self.suspend_minutes_spin.setRange(1, 240)
        self.suspend_minutes_spin.setValue(int(s.get("tab_suspend_minutes", 15)))
        self.suspend_minutes_spin.setStyleSheet(_FIELD_QSS)
        c3.addWidget(self.suspend_minutes_spin)
        layout.addWidget(card3)

        layout.addStretch()

    def apply(self):
        s = self.parent_browser.settings
        s["search_engine"] = self.search_combo.currentText()
        s["show_clock"] = self.check_clock.isChecked()
        s["show_title"] = self.check_title.isChecked()
        s["show_todo"] = self.check_todo.isChecked()
        s["tab_suspend_enabled"] = self.check_suspend.isChecked()
        s["tab_suspend_minutes"] = self.suspend_minutes_spin.value()
        self.parent_browser.save_data(SETTINGS_FILE, s)
        # Живое применение БЕЗ перезагрузки вкладки (в отличие от старого
        # create_start_page()+reload_start_pages() - та связка ничего не
        # чинила: create_start_page() лишь проверяет, что файл существует
        # на диске, а reload_start_pages() просто открывал его заново,
        # что никак не передавало новый search_engine на страницу).
        # push_native_settings_to_pages() уже собирает единый payload
        # (см. _build_startpage_payload) с вычисленным engine_idx.
        self.parent_browser.push_native_settings_to_pages()


class AppearanceTab(QWidget):
    """Внешний вид: цвета/шрифт/прозрачность + всё, что раньше жило на
    отдельной вкладке "Стартовая страница" (бренд/фон/блюр/интерактивность) -
    вкладка объединена сюда по ТЗ, чтобы не плодить разделы "ни о чём"."""

    def __init__(self, parent_browser):
        super().__init__()
        self.parent_browser = parent_browser
        s = parent_browser.settings
        self._bg_data = s.get("bg_data", "")
        self._bg_type = s.get("bg_type", "")

        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 22, 24, 22)
        layout.setSpacing(14)

        self.current_accent = s.get("theme_color", "#4c6ef5")
        card1, c1 = _card("🎨", "Цвета интерфейса", self.current_accent)
        row1 = QHBoxLayout()
        row1.setSpacing(10)
        accent_col = QVBoxLayout()
        accent_col.addWidget(_muted_label("Акцентный цвет"))
        self.btn_color = QPushButton("  Изменить")
        self.btn_color.setStyleSheet(self._swatch_qss(self.current_accent))
        self.btn_color.clicked.connect(self.pick_accent_color)
        accent_col.addWidget(self.btn_color)
        top_col = QVBoxLayout()
        top_col.addWidget(_muted_label("Цвет верхней панели"))
        self.current_top_color = s.get("top_bar_color", "#16171a")
        self.btn_top_color = QPushButton("  Изменить")
        self.btn_top_color.setStyleSheet(self._swatch_qss(self.current_top_color, bordered=True))
        self.btn_top_color.clicked.connect(self.pick_top_color)
        top_col.addWidget(self.btn_top_color)
        row1.addLayout(accent_col)
        row1.addLayout(top_col)
        c1.addLayout(row1)
        layout.addWidget(card1)

        # Шрифт (пункт 3.2 ТЗ): QFontComboBox (семейство) + QSpinBox (кегль) -
        # применяются реально (см. GORBrowser.update_styles): и к самому
        # Qt-приложению (QApplication.setFont), и к рендерингу веб-страниц
        # (QWebEngineSettings.globalSettings()), а не только к CSS этого окна.
        card2, c2 = _card("🔤", "Шрифт и прозрачность", self.current_accent,
                           "Применяется и к интерфейсу приложения, и к отображению веб-страниц.")
        c2.addWidget(_muted_label("Шрифт"))
        self.font_combo = QFontComboBox()
        self.font_combo.setCurrentFont(QFont(s.get("font_family", "Segoe UI")))
        self.font_combo.setStyleSheet(_FIELD_QSS)
        c2.addWidget(self.font_combo)
        c2.addWidget(_muted_label("Размер шрифта"))
        self.font_size_spin = QSpinBox()
        self.font_size_spin.setRange(7, 24)
        self.font_size_spin.setSuffix(" pt")
        self.font_size_spin.setValue(int(s.get("font_size", 10)))
        self.font_size_spin.setStyleSheet(_FIELD_QSS)
        c2.addWidget(self.font_size_spin)
        c2.addWidget(_muted_label("Прозрачность блоков"))
        self.opacity_slider = QSlider(Qt.Orientation.Horizontal)
        self.opacity_slider.setRange(10, 100)
        self.opacity_slider.setValue(int(s.get("ui_opacity", 0.8) * 100))
        c2.addWidget(self.opacity_slider)
        layout.addWidget(card2)

        # --- Перенесено со старой вкладки "Стартовая страница" ---
        card3, c3 = _card("🏷️", "Название системы", self.current_accent,
                           "Отображается в шапке стартовой страницы браузера.")
        self.brand_input = QLineEdit(s.get("brand_text", "GOR // OS"))
        self.brand_input.setStyleSheet(_FIELD_QSS)
        c3.addWidget(self.brand_input)
        layout.addWidget(card3)

        card4, c4 = _card("🖼️", "Фон стартовой страницы", self.current_accent)
        btn_bg_row = QHBoxLayout()
        btn_bg_row.setSpacing(8)
        btn_bg = QPushButton("📁  Загрузить файл")
        btn_bg.setStyleSheet(_button_qss("secondary"))
        btn_bg.clicked.connect(self.pick_background)
        btn_bg_clear = QPushButton("✕  Убрать фон")
        btn_bg_clear.setStyleSheet(_button_qss("secondary"))
        btn_bg_clear.clicked.connect(self.clear_background)
        btn_bg_row.addWidget(btn_bg)
        btn_bg_row.addWidget(btn_bg_clear)
        c4.addLayout(btn_bg_row)
        self.bg_status_label = QLabel(self._bg_status_text())
        self.bg_status_label.setStyleSheet("color: #888; font-size: 11px;")
        c4.addWidget(self.bg_status_label)

        c4.addWidget(_muted_label("Размытие фона"))
        self.blur_slider = QSlider(Qt.Orientation.Horizontal)
        self.blur_slider.setRange(0, 20)
        self.blur_slider.setValue(int(s.get("bg_blur", 0)))
        c4.addWidget(self.blur_slider)

        self.check_bg_interactive = QCheckBox("Разрешить клики сквозь панель по HTML-фону")
        self.check_bg_interactive.setChecked(bool(s.get("bg_interactive", False)))
        self.check_bg_interactive.setStyleSheet(_CHECKBOX_QSS)
        c4.addWidget(self.check_bg_interactive)
        layout.addWidget(card4)

        btn_reset = QPushButton("⚠️  Сбросить оформление к заводским настройкам")
        btn_reset.setStyleSheet(_button_qss("danger"))
        btn_reset.clicked.connect(self.reset_appearance)
        layout.addWidget(btn_reset)

        layout.addStretch()

    @staticmethod
    def _swatch_qss(color, bordered=False):
        border = f"border: 2px solid {_lighten(color, 40)};" if bordered else "border: 2px solid rgba(255,255,255,40);"
        return f"""
            QPushButton {{
                background: {color}; color: white; padding: 11px 14px;
                border-radius: 9px; {border} font-weight: 600; text-align: left;
            }}
            QPushButton:hover {{ border: 2px solid white; }}
        """

    def pick_accent_color(self):
        color = QColorDialog.getColor(QColor(self.current_accent), self)
        if color.isValid():
            self.current_accent = color.name()
            self.btn_color.setStyleSheet(self._swatch_qss(self.current_accent))

    def pick_top_color(self):
        color = QColorDialog.getColor(QColor(self.current_top_color), self)
        if color.isValid():
            self.current_top_color = color.name()
            self.btn_top_color.setStyleSheet(self._swatch_qss(self.current_top_color, bordered=True))

    def _bg_status_text(self):
        if not self._bg_data:
            return "Фон не задан (тёмный по умолчанию)"
        kind = "HTML" if self._bg_type == "html" else "изображение"
        return f"Установлен фон: {kind}"

    def pick_background(self):
        file, _ = QFileDialog.getOpenFileName(
            self, "Выберите фон", "",
            "Изображения и HTML (*.png *.jpg *.jpeg *.gif *.webp *.html *.htm)"
        )
        if not file:
            return
        try:
            with open(file, "rb") as f:
                raw = f.read()
        except OSError as e:
            QMessageBox.warning(self, "Ошибка", f"Не удалось прочитать файл:\n{e}")
            return

        mime, _ = mimetypes.guess_type(file)
        is_html = file.lower().endswith((".html", ".htm")) or mime == "text/html"
        if not mime:
            mime = "text/html" if is_html else "application/octet-stream"

        b64 = base64.b64encode(raw).decode("ascii")
        self._bg_data = f"data:{mime};base64,{b64}"
        self._bg_type = "html" if is_html else "image"
        self.bg_status_label.setText(self._bg_status_text())

    def clear_background(self):
        self._bg_data = ""
        self._bg_type = ""
        self.bg_status_label.setText(self._bg_status_text())

    def reset_appearance(self):
        confirm = QMessageBox.question(
            self, "GOR Browser",
            "Сбросить акцент, бренд, фон, блюр и шрифт к заводским настройкам?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        if confirm != QMessageBox.StandardButton.Yes:
            return

        s = self.parent_browser.settings
        for key in ("brand_text", "bg_data", "bg_type", "bg_blur", "bg_interactive",
                    "theme_color", "top_bar_color", "font_family", "font_size", "ui_opacity"):
            s[key] = DEFAULT_SETTINGS[key]
        self.parent_browser.save_data(SETTINGS_FILE, s)

        self._bg_data = ""
        self._bg_type = ""
        self.current_accent = s["theme_color"]
        self.current_top_color = s["top_bar_color"]
        self.btn_color.setStyleSheet(self._swatch_qss(self.current_accent))
        self.btn_top_color.setStyleSheet(self._swatch_qss(self.current_top_color, bordered=True))
        self.font_combo.setCurrentFont(QFont(s["font_family"]))
        self.font_size_spin.setValue(int(s["font_size"]))
        self.opacity_slider.setValue(int(s["ui_opacity"] * 100))
        self.brand_input.setText(s["brand_text"])
        self.bg_status_label.setText(self._bg_status_text())
        self.blur_slider.setValue(0)
        self.check_bg_interactive.setChecked(False)

        self.parent_browser.update_styles()
        self.parent_browser.push_native_settings_to_pages()
        self.parent_browser.run_js_on_start_pages("window.gorResetAll && window.gorResetAll();")

    def apply(self):
        s = self.parent_browser.settings
        s["theme_color"] = self.current_accent
        s["top_bar_color"] = self.current_top_color
        s["font_family"] = self.font_combo.currentFont().family()
        s["font_size"] = self.font_size_spin.value()
        s["ui_opacity"] = self.opacity_slider.value() / 100
        s["brand_text"] = self.brand_input.text().strip() or "GOR // OS"
        s["bg_data"] = self._bg_data
        s["bg_type"] = self._bg_type
        s["bg_blur"] = self.blur_slider.value()
        s["bg_interactive"] = self.check_bg_interactive.isChecked()
        self.parent_browser.save_data(SETTINGS_FILE, s)
        self.parent_browser.update_styles()
        self.parent_browser.push_native_settings_to_pages()


class BackupTab(QWidget):
    """Экспорт/импорт резервной копии стартовой страницы."""

    def __init__(self, parent_browser):
        super().__init__()
        self.parent_browser = parent_browser
        accent = parent_browser.settings.get("theme_color", "#4c6ef5")

        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 22, 24, 22)
        layout.setSpacing(14)

        card, c = _card(
            "💾", "Резервная копия", accent,
            "Полный снимок: настройки, история, закладки, группы вкладок, расширения "
            "и виджеты стартовой страницы - в один JSON-файл и обратно.",
        )
        btn_export = QPushButton("⬇  Экспортировать резервную копию")
        btn_export.setStyleSheet(_button_qss("secondary"))
        btn_export.clicked.connect(lambda: self.parent_browser.export_backup_to_file(self))
        btn_import = QPushButton("⬆  Импортировать резервную копию")
        btn_import.setStyleSheet(_button_qss("secondary"))
        btn_import.clicked.connect(lambda: self.parent_browser.import_backup_from_file(self))
        c.addWidget(btn_export)
        c.addWidget(btn_import)
        layout.addWidget(card)

        layout.addStretch()

    def apply(self):
        pass  # экспорт/импорт применяются сразу по клику, сохранять больше нечего


class ExtensionsTab(QWidget):
    """Менеджер простых JS-расширений (бывший ExtensionManager)."""

    def __init__(self, parent_browser):
        super().__init__()
        self.parent_browser = parent_browser
        accent = parent_browser.settings.get('theme_color', '#4c6ef5')

        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 22, 24, 22)
        layout.setSpacing(14)

        card, c = _card("🧩", "Установленные скрипты", accent, "Простые JS-расширения, выполняются на каждой странице.")
        self.list_widget = QListWidget()
        self.list_widget.setStyleSheet(
            "QListWidget { background: #1c1e23; border-radius: 10px; border: 1px solid #2a2c31; padding: 4px; } "
            "QListWidget::item { padding: 10px; border-radius: 7px; } "
            "QListWidget::item:hover { background: #22242a; } "
            "QListWidget::item:selected { background: #2a2c34; }"
        )
        self.list_widget.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.list_widget.customContextMenuRequested.connect(self.show_ext_menu)
        c.addWidget(self.list_widget)

        btn_add = QPushButton("+  Добавить JS расширение")
        btn_add.setStyleSheet(_button_qss("primary", accent))
        btn_add.clicked.connect(self.add_extension)
        c.addWidget(btn_add)
        layout.addWidget(card, 1)

        self.refresh_list()

    def refresh_list(self):
        self.list_widget.clear()
        for ext in self.parent_browser.extensions:
            item = QListWidgetItem(f"📜 {ext['name']}")
            self.list_widget.addItem(item)

    def show_ext_menu(self, pos):
        item = self.list_widget.itemAt(pos)
        if item:
            menu = QMenu(self)
            del_act = QAction("Удалить расширение", self)
            del_act.triggered.connect(lambda: self.delete_ext(item.text()[2:].strip()))
            menu.addAction(del_act)
            menu.exec(self.list_widget.mapToGlobal(pos))

    def add_extension(self):
        name, ok1 = QInputDialog.getText(self, "Новое расширение", "Название:")
        if ok1 and name:
            code, ok2 = QInputDialog.getMultiLineText(self, "Код", "Вставьте JavaScript код:")
            if ok2 and code:
                self.parent_browser.extensions.append({"name": name, "code": code})
                self.parent_browser.save_data(EXTENSIONS_FILE, self.parent_browser.extensions)
                self.parent_browser.apply_extensions()
                self.refresh_list()

    def delete_ext(self, name):
        self.parent_browser.extensions = [x for x in self.parent_browser.extensions if x['name'] != name]
        self.parent_browser.save_data(EXTENSIONS_FILE, self.parent_browser.extensions)
        self.parent_browser.apply_extensions()
        self.refresh_list()

    def apply(self):
        pass  # изменения расширений уже сохраняются сразу по месту


class NetworkSecurityTab(QWidget):
    """AdBlock / VOT-переводчик / LAN Broadcast - три новые фичи v1.2.
    Переключатели дёргают install_*()/service.set_port() сразу в apply(),
    т.е. работают без перезапуска браузера."""

    def __init__(self, parent_browser):
        super().__init__()
        self.parent_browser = parent_browser
        s = parent_browser.settings
        accent = s.get("theme_color", "#4c6ef5")

        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 22, 24, 22)
        layout.setSpacing(14)

        card1, c1 = _card(
            "🛡️", "Блокировщик рекламы (uBlock Engine)", accent,
            "Сетевая фильтрация + скрытие пустых рекламных блоков на странице.",
        )
        self.check_adblock = QCheckBox("Блокировать рекламу и трекеры")
        self.check_adblock.setChecked(s.get("adblock_enabled", True))
        self.check_adblock.setStyleSheet(_CHECKBOX_QSS)
        c1.addWidget(self.check_adblock)
        self.check_adblock_dyn = QCheckBox("Автообновление списка блокировки с GitHub")
        self.check_adblock_dyn.setChecked(s.get("adblock_dynamic_update_enabled", True))
        self.check_adblock_dyn.setStyleSheet(_CHECKBOX_QSS)
        c1.addWidget(self.check_adblock_dyn)
        last_update = s.get("adblock_last_update", "")
        update_text = f"Последнее обновление: {last_update[:16].replace('T', ' ')}" if last_update else "Список ещё ни разу не обновлялся"
        self.adblock_status_label = QLabel(update_text)
        self.adblock_status_label.setStyleSheet("color: #888; font-size: 11px;")
        c1.addWidget(self.adblock_status_label)
        btn_adblock_now = QPushButton("🔄  Обновить список блокировки сейчас")
        btn_adblock_now.setStyleSheet(_button_qss("secondary"))
        btn_adblock_now.clicked.connect(self._adblock_update_now)
        c1.addWidget(btn_adblock_now)
        layout.addWidget(card1)

        card2, c2 = _card(
            "🌐", "Закадровый переводчик (VOT Engine)", accent,
            "Работает как нативная замена Tampermonkey-скрипту vot.user.js. Положите файл "
            "vot.user.js рядом с браузером, чтобы включить сам движок перевода — без него "
            "кнопка будет отображаться, но переводить не сможет.",
        )
        self.check_vot = QCheckBox("Показывать кнопку «Перевести видео»")
        self.check_vot.setChecked(s.get("vot_enabled", True))
        self.check_vot.setStyleSheet(_CHECKBOX_QSS)
        c2.addWidget(self.check_vot)
        layout.addWidget(card2)

        card3, c3 = _card(
            "📡", "LAN Broadcast", accent,
            "Все копии GOR Browser в одной локальной сети должны использовать один и тот же порт.",
        )
        self.check_broadcast = QCheckBox("Принимать вкладки/группы от других GOR Browser в сети")
        self.check_broadcast.setChecked(s.get("broadcast_enabled", True))
        self.check_broadcast.setStyleSheet(_CHECKBOX_QSS)
        c3.addWidget(self.check_broadcast)

        port_row = QHBoxLayout()
        port_row.setSpacing(10)
        port_col = QVBoxLayout()
        port_col.addWidget(_muted_label("UDP-порт"))
        self.port_input = QLineEdit(str(s.get("broadcast_port", 51888)))
        self.port_input.setStyleSheet(_FIELD_QSS)
        self.port_input.setFixedWidth(140)
        port_col.addWidget(self.port_input)
        port_row.addLayout(port_col)
        port_row.addStretch()
        c3.addLayout(port_row)
        layout.addWidget(card3)

        # LAN: общий буфер обмена + синхронизация закладок - раньше жили в
        # меню ⋮, перенесены сюда по ТЗ.
        card4, c4 = _card(
            "🔗", "LAN: буфер обмена и закладки", accent,
            "Расшаривает данные всем GOR Browser в сети - выключено по умолчанию.",
        )
        self.check_lan_clipboard = QCheckBox("📋  Общий буфер обмена по LAN")
        self.check_lan_clipboard.setChecked(s.get("lan_clipboard_enabled", False))
        self.check_lan_clipboard.setStyleSheet(_CHECKBOX_QSS)
        c4.addWidget(self.check_lan_clipboard)
        self.check_lan_bookmarks = QCheckBox("🔖  Синхронизация закладок по LAN")
        self.check_lan_bookmarks.setChecked(s.get("lan_bookmark_sync_enabled", False))
        self.check_lan_bookmarks.setStyleSheet(_CHECKBOX_QSS)
        c4.addWidget(self.check_lan_bookmarks)
        btn_bm_sync_now = QPushButton("🔗  Отправить свои закладки в сеть сейчас")
        btn_bm_sync_now.setStyleSheet(_button_qss("secondary"))
        btn_bm_sync_now.clicked.connect(
            lambda: self.parent_browser.broadcast_service.send_bookmarks(self.parent_browser.bookmarks)
        )
        c4.addWidget(btn_bm_sync_now)
        layout.addWidget(card4)

        # Пароли - живут в отдельном зашифрованном хранилище (browser_passwords.py),
        # здесь только точка входа.
        card5, c5 = _card("🔑", "Менеджер паролей", accent,
                           "Локальное шифрованное хранилище (AES/Fernet). Мастер-пароль нигде не хранится.")
        btn_passwords = QPushButton("🔑  Открыть менеджер паролей")
        btn_passwords.setStyleSheet(_button_qss("secondary"))
        btn_passwords.clicked.connect(
            lambda: open_password_manager(self.parent_browser, self.parent_browser.password_vault)
        )
        c5.addWidget(btn_passwords)
        layout.addWidget(card5)

        # Приватность: очистка кук/кеша (пункт 3.4 ТЗ - раньше отсутствовало).
        card6, c6 = _card("🧹", "Приватность", accent,
                           "Немедленная очистка, без ожидания закрытия браузера.")
        btn_row = QHBoxLayout()
        btn_row.setSpacing(8)
        btn_clear_cookies = QPushButton("🍪  Очистить куки")
        btn_clear_cookies.setStyleSheet(_button_qss("secondary"))
        btn_clear_cookies.clicked.connect(lambda: self.parent_browser.clear_cookies(self))
        btn_clear_cache = QPushButton("🗑️  Очистить кеш")
        btn_clear_cache.setStyleSheet(_button_qss("secondary"))
        btn_clear_cache.clicked.connect(lambda: self.parent_browser.clear_http_cache(self))
        btn_row.addWidget(btn_clear_cookies)
        btn_row.addWidget(btn_clear_cache)
        c6.addLayout(btn_row)
        layout.addWidget(card6)

        layout.addStretch()

    def _adblock_update_now(self):
        self.parent_browser.adblock_updater.update_now(self.parent_browser.settings.get("adblock_update_url") or None)
        self.adblock_status_label.setText("Обновление запущено в фоне...")

    def apply(self):
        import os
        from browser_adblock import install_cosmetic_filter
        from browser_translate import install_vot_translator

        s = self.parent_browser.settings
        s["adblock_enabled"] = self.check_adblock.isChecked()
        s["adblock_dynamic_update_enabled"] = self.check_adblock_dyn.isChecked()
        s["vot_enabled"] = self.check_vot.isChecked()
        s["broadcast_enabled"] = self.check_broadcast.isChecked()
        s["lan_clipboard_enabled"] = self.check_lan_clipboard.isChecked()
        s["lan_bookmark_sync_enabled"] = self.check_lan_bookmarks.isChecked()
        try:
            s["broadcast_port"] = int(self.port_input.text().strip())
        except ValueError:
            pass  # оставляем прежнее значение, если введена не цифра
        self.parent_browser.save_data(SETTINGS_FILE, s)

        # Применяем сразу, без перезапуска браузера.
        self.parent_browser.adblock_interceptor.set_enabled(s["adblock_enabled"])
        install_cosmetic_filter(self.parent_browser.profile, s["adblock_enabled"])
        base_dir = os.path.dirname(os.path.abspath(__file__))
        install_vot_translator(self.parent_browser.profile, base_dir, s["vot_enabled"])
        if s["broadcast_enabled"]:
            self.parent_browser.broadcast_service.set_port(s["broadcast_port"])
        else:
            self.parent_browser.broadcast_service.stop_listening()


class BrowserSettingsWindow(QDialog):
    """Единое красивое окно настроек GOR Browser: боковое меню разделов
    слева (QListWidget, как в VS Code/Telegram - надёжная и всегда
    горизонтальная альтернатива QTabWidget(West), у которого Qt по
    умолчанию рисует текст повёрнутым на 90°), контент справа
    (QStackedWidget), общая кнопка "Сохранить и применить" внизу."""

    def __init__(self, parent_browser):
        super().__init__(parent_browser)
        self.parent_browser = parent_browser
        accent = parent_browser.settings.get("theme_color", "#4c6ef5")
        font = parent_browser.settings.get("font_family", "Segoe UI")

        self.setWindowTitle("Настройки GOR Browser")
        self.setMinimumSize(760, 600)
        self.resize(860, 660)

        self.setStyleSheet(f"""
            QDialog {{
                font-family: '{font}';
                color: white;
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                    stop:0 #16171b, stop:1 #111216);
            }}
            QScrollArea {{ border: none; background: transparent; }}
            QScrollBar:vertical {{
                background: transparent; width: 9px; margin: 4px 2px 4px 0;
            }}
            QScrollBar::handle:vertical {{
                background: #33353c; border-radius: 4px; min-height: 30px;
            }}
            QScrollBar::handle:vertical:hover {{ background: #454850; }}
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{ height: 0; }}
            QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical {{ background: transparent; }}
            QSlider::groove:horizontal {{ height: 4px; background: #2a2c31; border-radius: 2px; }}
            QSlider::handle:horizontal {{
                background: {accent}; width: 16px; height: 16px; margin: -6px 0; border-radius: 8px;
                border: 2px solid #16171b;
            }}
            QSlider::handle:horizontal:hover {{ background: {_lighten(accent)}; }}
            QSlider::sub-page:horizontal {{ background: {accent}; border-radius: 2px; }}
            QComboBox QAbstractItemView {{
                background: #1c1e23; color: white; selection-background-color: {accent};
                border: 1px solid #34363d; border-radius: 8px; padding: 4px;
            }}
        """)

        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)

        # --- Шапка: акцентная иконка-бейдж + заголовок/подзаголовок -------
        header = QFrame()
        header.setStyleSheet("background: #17181c; border-bottom: 1px solid #232529;")
        header_layout = QHBoxLayout(header)
        header_layout.setContentsMargins(26, 20, 26, 20)
        header_layout.setSpacing(14)

        badge = QLabel("⚙️")
        badge.setFixedSize(42, 42)
        badge.setAlignment(Qt.AlignmentFlag.AlignCenter)
        badge.setStyleSheet(f"""
            background: qlineargradient(x1:0, y1:0, x2:1, y2:1, stop:0 {accent}, stop:1 {_darken(accent, 30)});
            border-radius: 12px; font-size: 18px;
        """)
        header_layout.addWidget(badge)

        title_col = QVBoxLayout()
        title_col.setSpacing(2)
        title = QLabel("Настройки GOR Browser")
        title.setStyleSheet("font-size: 16px; font-weight: 700; color: white;")
        subtitle = QLabel("Внешний вид, стартовая страница, безопасность и сеть")
        subtitle.setStyleSheet("font-size: 11.5px; color: #7d818b;")
        title_col.addWidget(title)
        title_col.addWidget(subtitle)
        header_layout.addLayout(title_col)
        header_layout.addStretch()
        outer.addWidget(header)

        # --- Тело: боковое меню (список разделов) + стек страниц справа ---
        body = QFrame()
        body.setStyleSheet("background: transparent;")
        body_layout = QHBoxLayout(body)
        body_layout.setContentsMargins(0, 0, 0, 0)
        body_layout.setSpacing(0)

        self.nav_list = QListWidget(objectName="SettingsNav")
        self.nav_list.setFixedWidth(224)
        self.nav_list.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.nav_list.setStyleSheet(f"""
            QListWidget#SettingsNav {{
                background: #131418; border: none; border-right: 1px solid #232529;
                padding: 14px 10px; outline: none;
            }}
            QListWidget#SettingsNav::item {{
                color: #8a8f99; padding: 11px 14px; border-radius: 11px;
                margin-bottom: 4px; font-size: 12.5px;
            }}
            QListWidget#SettingsNav::item:hover {{ background: #1e2025; color: #e7e8ea; }}
            QListWidget#SettingsNav::item:selected {{
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                    stop:0 {accent}, stop:1 {_darken(accent, 18)});
                color: white; font-weight: 600;
            }}
        """)
        self.stack = QStackedWidget()

        body_layout.addWidget(self.nav_list)
        body_layout.addWidget(self.stack, 1)
        outer.addWidget(body, 1)

        self.section_tabs = [
            (tr("browser.settings.tab_general"), GeneralTab(parent_browser)),
            (tr("browser.settings.tab_appearance"), AppearanceTab(parent_browser)),
            (tr("browser.settings.tab_backup"), BackupTab(parent_browser)),
            (tr("browser.settings.tab_security"), NetworkSecurityTab(parent_browser)),
            (tr("browser.settings.tab_extensions"), ExtensionsTab(parent_browser)),
        ]
        for label, widget in self.section_tabs:
            scroll = QScrollArea()
            scroll.setWidgetResizable(True)
            scroll.setWidget(widget)
            self.stack.addWidget(scroll)
            item = QListWidgetItem(label)
            item.setSizeHint(QSize(0, 42))
            self.nav_list.addItem(item)

        self.nav_list.currentRowChanged.connect(self.stack.setCurrentIndex)
        self.nav_list.setCurrentRow(0)

        # --- Футер -----------------------------------------------------
        footer = QFrame()
        footer.setStyleSheet("background: #17181c; border-top: 1px solid #232529;")
        footer_layout = QHBoxLayout(footer)
        footer_layout.setContentsMargins(26, 16, 26, 16)
        footer_layout.setSpacing(10)
        footer_layout.addStretch()
        btn_cancel = QPushButton("Отмена")
        btn_cancel.setStyleSheet(_button_qss("ghost"))
        btn_cancel.clicked.connect(self.reject)
        btn_save = QPushButton("✓  Сохранить и применить")
        btn_save.setStyleSheet(_button_qss("primary", accent))
        btn_save.clicked.connect(self.apply_all)
        footer_layout.addWidget(btn_cancel)
        footer_layout.addWidget(btn_save)
        outer.addWidget(footer)

    def apply_all(self):
        for _, widget in self.section_tabs:
            widget.apply()
        self.accept()
