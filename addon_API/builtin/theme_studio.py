"""
Theme Studio - встроенный аддон: выбор темы и настройка каждого цвета
лаунчера вживую. Написан целиком через публичный addon_API - тот же API,
что доступен любому аддону.
"""

import os

from PyQt6.QtWidgets import (
    QDialog, QHBoxLayout, QVBoxLayout, QListWidget, QListWidgetItem, QPushButton,
    QLabel, QScrollArea, QWidget, QColorDialog, QInputDialog, QFileDialog,
    QMessageBox,
)
from PyQt6.QtGui import QColor, QDesktopServices
from PyQt6.QtCore import Qt, QUrl

from addon_API import AddonBase, Events
from addon_API.themes import TOKENS, TOKEN_TITLES, THEMES_DIR, DEFAULT_THEME_ID


class ThemeStudioDialog(QDialog):
    def __init__(self, api, parent=None):
        super().__init__(parent)
        self.api = api
        self.themes = api.themes
        self.setWindowTitle("🎨 Темы и оформление")
        self.resize(780, 560)

        root = QHBoxLayout(self)

        # ---------------- слева: список тем ----------------
        left = QVBoxLayout()
        left.addWidget(QLabel("Темы"))
        self.list = QListWidget()
        self.list.itemClicked.connect(self._on_theme_clicked)
        left.addWidget(self.list, 1)
        row = QHBoxLayout()
        btn_import = QPushButton("Импорт…")
        btn_import.clicked.connect(self._import)
        btn_delete = QPushButton("Удалить")
        btn_delete.clicked.connect(self._delete)
        row.addWidget(btn_import)
        row.addWidget(btn_delete)
        left.addLayout(row)
        btn_folder = QPushButton("📁 Папка тем")
        btn_folder.clicked.connect(self._open_folder)
        left.addWidget(btn_folder)
        root.addLayout(left, 2)

        # ---------------- справа: цвета ----------------
        right = QVBoxLayout()
        self.info = QLabel()
        self.info.setWordWrap(True)
        right.addWidget(self.info)
        right.addWidget(QLabel("Цвета (нажмите на цветной квадрат, изменения видны сразу)"))

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        holder = QWidget()
        self.rows = QVBoxLayout(holder)
        self.swatches = {}
        for token in TOKENS:
            line = QHBoxLayout()
            line.addWidget(QLabel(TOKEN_TITLES.get(token, token)), 1)
            hex_lbl = QLabel()
            hex_lbl.setMinimumWidth(70)
            sw = QPushButton()
            sw.setFixedSize(54, 28)
            sw.setCursor(Qt.CursorShape.PointingHandCursor)
            sw.clicked.connect(lambda _=False, t=token: self._pick(t))
            line.addWidget(hex_lbl)
            line.addWidget(sw)
            self.rows.addLayout(line)
            self.swatches[token] = (sw, hex_lbl)
        self.rows.addStretch(1)
        scroll.setWidget(holder)
        right.addWidget(scroll, 1)

        bottom = QHBoxLayout()
        btn_reset = QPushButton("Сбросить правки")
        btn_reset.clicked.connect(self._reset)
        btn_save = QPushButton("💾 Сохранить как тему…")
        btn_save.clicked.connect(self._save_as)
        btn_close = QPushButton("Закрыть")
        btn_close.clicked.connect(self.close)
        bottom.addWidget(btn_reset)
        bottom.addWidget(btn_save)
        bottom.addStretch(1)
        bottom.addWidget(btn_close)
        right.addLayout(bottom)
        root.addLayout(right, 3)

        self.reload()

    # ---------------------------------------------------------------- #
    def reload(self):
        current = self.themes.current_id()
        self.list.clear()
        for t in self.themes.list():
            title = t["name"] + (f"  —  {t['author']}" if t.get("author") else "")
            mark = "👤 " if t.get("scope") == "account" else ""      # 👤 - тема только этого аккаунта
            item = QListWidgetItem(("✔ " if t["id"] == current else "    ") + mark + title)
            item.setData(Qt.ItemDataRole.UserRole, t["id"])
            self.list.addItem(item)
        theme = next((t for t in self.themes.list() if t["id"] == current), {})
        desc = theme.get("description") or ""
        over = len(self.themes.overrides())
        acc = self.themes.account_name()
        owner = f"Аккаунт: <b>{acc}</b> — тема и цвета запоминаются за ним<br>" if acc else ""
        self.info.setText(f"{owner}<b>{theme.get('name', current)}</b><br>{desc}"
                          + (f"<br><i>Личных правок цвета: {over}</i>" if over else ""))
        for token, color in self.themes.colors().items():
            sw, hex_lbl = self.swatches[token]
            sw.setStyleSheet(f"QPushButton {{ background: {color}; border: 2px solid #888;"
                             f" border-radius: 6px; padding: 0; min-height: 0; }}")
            hex_lbl.setText(color)

    def _on_theme_clicked(self, item):
        self.themes.apply(item.data(Qt.ItemDataRole.UserRole))
        self.reload()

    def _pick(self, token):
        start = QColor(self.themes.colors()[token])
        color = QColorDialog.getColor(start, self, TOKEN_TITLES.get(token, token))
        if color.isValid():
            self.themes.set_color(token, color.name())
            self.reload()

    def _reset(self):
        self.themes.reset_overrides()
        self.reload()

    def _save_as(self):
        name, ok = QInputDialog.getText(self, "Сохранить тему", "Название темы:")
        if ok and name.strip():
            tid = self.themes.save_current_as(name.strip())
            self.themes.apply(tid)
            self.reload()
            self.api.toast(f"Тема «{name.strip()}» сохранена")

    def _import(self):
        path, _ = QFileDialog.getOpenFileName(self, "Импорт темы", "", "Тема (*.json)")
        if path:
            try:
                tid = self.themes.import_file(path)
                self.themes.apply(tid)
                self.reload()
            except Exception as e:
                QMessageBox.warning(self, "Ошибка импорта", str(e))

    def _delete(self):
        item = self.list.currentItem()
        if not item:
            return
        tid = item.data(Qt.ItemDataRole.UserRole)
        if tid == DEFAULT_THEME_ID:
            QMessageBox.information(self, "Тема", "Стандартную тему удалить нельзя.")
            return
        if QMessageBox.question(self, "Удалить тему", f"Удалить тему «{tid}»?") == \
                QMessageBox.StandardButton.Yes:
            if not self.themes.delete(tid):
                QMessageBox.information(self, "Тема", "Это общая тема: её нельзя удалить из аккаунта, "
                                                      "чтобы не пропала у остальных. Удаляются только ваши темы (👤).")
            self.reload()

    def _open_folder(self):
        os.makedirs(THEMES_DIR, exist_ok=True)
        QDesktopServices.openUrl(QUrl.fromLocalFile(THEMES_DIR))


class Addon(AddonBase):
    def on_load(self, api):
        self.dialog = None

        def open_studio():
            if self.dialog is None:
                self.dialog = ThemeStudioDialog(api, api.launcher)
            self.dialog.reload()
            self.dialog.show()
            self.dialog.raise_()
            self.dialog.activateWindow()

        self.open_studio = open_studio
        api.ui.add_header_button("🎨", open_studio, tooltip="Темы и оформление",
                                 object_name="ThemeStudioBtn")
        api.ui.add_burger_action("🎨 Темы и оформление…", open_studio, separator_before=True)
        api.on(Events.THEME_CHANGED, lambda tid: self.dialog and self.dialog.isVisible()
               and self.dialog.reload())

    def on_unload(self):
        if self.dialog is not None:
            self.dialog.close()
            self.dialog.deleteLater()
