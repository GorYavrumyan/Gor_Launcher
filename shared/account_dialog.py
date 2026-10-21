"""
Окна аккаунтов:
  - AccountDialog          - выбор/создание аккаунта при старте лаунчера.
  - AccountSwitcherDialog  - окно "мой аккаунт" внутри уже открытого
                              лаунчера (кнопка с обложкой в шапке) -
                              показывает большую обложку текущего
                              аккаунта и список остальных для переключения.
"""

import os

from PyQt6.QtCore import Qt, QBuffer, QIODevice, QSize
from PyQt6.QtGui import QPixmap, QPainter, QPainterPath, QColor, QFont, QIcon
from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QListWidget,
    QListWidgetItem, QPushButton, QLineEdit, QMessageBox, QStackedWidget,
    QWidget, QFormLayout, QFileDialog, QInputDialog, QComboBox
)

import account_manager as am


DIALOG_STYLE = """
QDialog { background-color: #16171a; }
QLabel { color: #e6e6e6; font-size: 14px; }
QLabel#Title { font-size: 20px; font-weight: 600; color: #ffffff; }
QLabel#BigName { font-size: 18px; font-weight: 600; color: #ffffff; }
QListWidget {
    background-color: #1c1d21; border: 1px solid #2a2b30; border-radius: 8px;
    color: #e6e6e6; font-size: 14px; padding: 4px;
}
QListWidget::item { padding: 8px; border-radius: 6px; }
QListWidget::item:selected { background-color: #4c6ef5; color: white; }
QLineEdit {
    background-color: #1c1d21; border: 1px solid #2a2b30; border-radius: 6px;
    color: #e6e6e6; padding: 8px; font-size: 14px;
}
QLineEdit:focus { border: 1px solid #4c6ef5; }
QPushButton {
    background-color: #2a2b30; border: none; border-radius: 6px;
    color: #e6e6e6; padding: 9px 16px; font-size: 13px;
}
QPushButton:hover { background-color: #35363c; }
QPushButton#Primary { background-color: #4c6ef5; color: white; font-weight: 600; }
QPushButton#Primary:hover { background-color: #3d5ce0; }
QPushButton#Danger:hover { background-color: #e03131; }
QPushButton#AvatarPick { background-color: transparent; border: 2px solid #2a2b30; border-radius: 40px; }
QPushButton#AvatarPick:hover { border: 2px solid #4c6ef5; }
"""

_PALETTE = ["#4c6ef5", "#e8590c", "#2f9e44", "#e03131", "#9c36b5", "#1098ad", "#f08c00", "#37b24d"]


# ------------------------------------------------------------------- #
# Отрисовка круглых обложек (общая для всех окон аккаунтов)
# ------------------------------------------------------------------- #
def _square_crop(pixmap, size):
    side = min(pixmap.width(), pixmap.height())
    x = (pixmap.width() - side) // 2
    y = (pixmap.height() - side) // 2
    cropped = pixmap.copy(x, y, side, side)
    return cropped.scaled(size, size, Qt.AspectRatioMode.KeepAspectRatio,
                           Qt.TransformationMode.SmoothTransformation)


def _placeholder_square(name, size):
    color = QColor(_PALETTE[sum(ord(c) for c in name) % len(_PALETTE)]) if name else QColor("#4c6ef5")
    pm = QPixmap(size, size)
    pm.fill(Qt.GlobalColor.transparent)
    p = QPainter(pm)
    p.setRenderHint(QPainter.RenderHint.Antialiasing)
    p.setBrush(color)
    p.setPen(Qt.PenStyle.NoPen)
    p.drawEllipse(0, 0, size, size)
    p.setPen(QColor("white"))
    font = QFont("Segoe UI", int(size * 0.42), QFont.Weight.Bold)
    p.setFont(font)
    letter = name[0].upper() if name else "?"
    p.drawText(pm.rect(), Qt.AlignmentFlag.AlignCenter, letter)
    p.end()
    return pm


def circular_avatar(name, size=64):
    """Круглая обложка аккаунта `name` нужного размера. Если своя обложка
    не задана - генерируется цветной кружок с первой буквой имени."""
    path = am.get_avatar_path(name)
    base = None
    if path:
        pm = QPixmap(path)
        if not pm.isNull():
            base = _square_crop(pm, size)
    if base is None:
        base = _placeholder_square(name, size)

    result = QPixmap(size, size)
    result.fill(Qt.GlobalColor.transparent)
    p = QPainter(result)
    p.setRenderHint(QPainter.RenderHint.Antialiasing)
    clip = QPainterPath()
    clip.addEllipse(0, 0, size, size)
    p.setClipPath(clip)
    p.drawPixmap(0, 0, base)
    p.end()
    return result


def _circle_icon(square_pixmap, size):
    circ = QPixmap(size, size)
    circ.fill(Qt.GlobalColor.transparent)
    p = QPainter(circ)
    p.setRenderHint(QPainter.RenderHint.Antialiasing)
    clip = QPainterPath()
    clip.addEllipse(0, 0, size, size)
    p.setClipPath(clip)
    p.drawPixmap(0, 0, _square_crop(square_pixmap, size))
    p.end()
    return circ


def _pick_and_save_avatar(parent_widget, account_name):
    """Открывает диалог выбора файла картинки и, если пользователь что-то
    выбрал, сохраняет её как обложку `account_name`. Возвращает True, если
    обложка была изменена."""
    file_path, _ = QFileDialog.getOpenFileName(
        parent_widget, "Выбери обложку",
        os.path.expanduser("~"),
        "Изображения (*.png *.jpg *.jpeg *.webp *.bmp)"
    )
    if not file_path:
        return False
    pm = QPixmap(file_path)
    if pm.isNull():
        QMessageBox.warning(parent_widget, "GOR Launcher", "Не получилось открыть эту картинку.")
        return False
    square = _square_crop(pm, 256)
    buf = QBuffer()
    buf.open(QIODevice.OpenModeFlag.WriteOnly)
    square.save(buf, "PNG")
    am.save_avatar_png(account_name, bytes(buf.data()))
    buf.close()
    return True


# ------------------------------------------------------------------- #
# AccountDialog - выбор/создание аккаунта при старте лаунчера
# ------------------------------------------------------------------- #
class AccountDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("GOR Launcher — выбор аккаунта")
        self.setFixedSize(420, 520)
        self.setStyleSheet(DIALOG_STYLE)
        self.selected_account = None
        self._new_avatar_pixmap = None  # обложка, выбранная в форме создания (256x256, ещё не на диске)

        outer = QVBoxLayout(self)
        outer.setContentsMargins(24, 24, 24, 24)
        outer.setSpacing(14)

        self.stack = QStackedWidget()
        outer.addWidget(self.stack)

        self._build_list_page()
        self._build_create_page()
        self._build_login_page()

        self.stack.setCurrentWidget(self.list_page)
        self._refresh_list()

    # ------------------------------------------------------------- #
    # Страница 1: список аккаунтов
    # ------------------------------------------------------------- #
    def _build_list_page(self):
        page = QWidget()
        lay = QVBoxLayout(page)
        lay.setSpacing(12)

        title = QLabel("Выбери аккаунт")
        title.setObjectName("Title")
        lay.addWidget(title)

        self.list_widget = QListWidget()
        self.list_widget.setIconSize(QSize(36, 36))
        self.list_widget.itemDoubleClicked.connect(self._on_enter_clicked)
        lay.addWidget(self.list_widget, 1)

        row = QHBoxLayout()
        new_btn = QPushButton("➕ Новый аккаунт")
        new_btn.clicked.connect(lambda: self.stack.setCurrentWidget(self.create_page))
        del_btn = QPushButton("🗑 Удалить")
        del_btn.setObjectName("Danger")
        del_btn.clicked.connect(self._on_delete_clicked)
        row.addWidget(new_btn)
        row.addWidget(del_btn)
        lay.addLayout(row)

        enter_btn = QPushButton("Войти →")
        enter_btn.setObjectName("Primary")
        enter_btn.clicked.connect(self._on_enter_clicked)
        lay.addWidget(enter_btn)

        self.list_page = page
        self.stack.addWidget(page)

    def _refresh_list(self):
        self.list_widget.clear()
        last_active = am.get_last_active()
        select_row = 0
        for i, name in enumerate(am.list_accounts()):
            suffix = " 🔒" if am.account_has_password(name) else ""
            item = QListWidgetItem(QIcon(circular_avatar(name, 36)), f"  {name}{suffix}")
            item.setData(Qt.ItemDataRole.UserRole, name)
            self.list_widget.addItem(item)
            if name == last_active:
                select_row = i
        if self.list_widget.count() == 0:
            self.stack.setCurrentWidget(self.create_page)
        else:
            self.list_widget.setCurrentRow(select_row)

    def _current_name(self):
        item = self.list_widget.currentItem()
        return item.data(Qt.ItemDataRole.UserRole) if item else None

    def _on_enter_clicked(self):
        name = self._current_name()
        if not name:
            QMessageBox.warning(self, "GOR Launcher", "Сначала выбери аккаунт из списка.")
            return
        if am.account_has_password(name):
            self.login_target = name
            self.login_name_label.setText(f"Аккаунт: {name}")
            self.login_pass_field.clear()
            self.stack.setCurrentWidget(self.login_page)
            self.login_pass_field.setFocus()
        else:
            self.selected_account = name
            self.accept()

    def _on_delete_clicked(self):
        name = self._current_name()
        if not name:
            return

        if am.account_has_password(name):
            pwd, ok = QInputDialog.getText(
                self, "Подтверди удаление",
                f"Аккаунт «{name}» защищён паролем.\n"
                "Введи пароль, чтобы безвозвратно удалить его вместе со "
                "всеми играми, историей браузера и аддонами:",
                QLineEdit.EchoMode.Password
            )
            if not ok:
                return
            if not am.verify_password(name, pwd):
                QMessageBox.warning(self, "GOR Launcher", "Неверный пароль — удаление отменено.")
                return
        else:
            reply = QMessageBox.question(
                self, "Удалить аккаунт?",
                f"Удалить аккаунт «{name}» и ВСЕ его данные (игры, историю "
                "браузера, аддонов)? Это действие необратимо.",
            )
            if reply != QMessageBox.StandardButton.Yes:
                return

        ok, err = am.delete_account(name)
        if not ok:
            QMessageBox.critical(self, "GOR Launcher", err)
            return
        self._refresh_list()

    # ------------------------------------------------------------- #
    # Страница 2: создание аккаунта
    # ------------------------------------------------------------- #
    def _build_create_page(self):
        page = QWidget()
        lay = QVBoxLayout(page)
        lay.setSpacing(14)

        title = QLabel("Новый аккаунт")
        title.setObjectName("Title")
        lay.addWidget(title)

        avatar_row = QHBoxLayout()
        avatar_row.addStretch(1)
        self.avatar_btn = QPushButton()
        self.avatar_btn.setObjectName("AvatarPick")
        self.avatar_btn.setFixedSize(80, 80)
        self.avatar_btn.setIconSize(QSize(76, 76))
        self.avatar_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.avatar_btn.setToolTip("Выбрать обложку")
        self.avatar_btn.clicked.connect(self._on_pick_avatar)
        avatar_row.addWidget(self.avatar_btn)
        avatar_row.addStretch(1)
        lay.addLayout(avatar_row)
        self._refresh_avatar_preview()

        hint = QLabel("Нажми на кружок, чтобы выбрать картинку (необязательно)")
        hint.setAlignment(Qt.AlignmentFlag.AlignCenter)
        hint.setStyleSheet("color: #8a8b90; font-size: 12px;")
        lay.addWidget(hint)

        form = QFormLayout()
        form.setSpacing(10)
        self.new_name_field = QLineEdit()
        self.new_name_field.setPlaceholderText("Например: Vova")
        self.new_pass_field = QLineEdit()
        self.new_pass_field.setPlaceholderText("Необязательно")
        self.new_pass_field.setEchoMode(QLineEdit.EchoMode.Password)
        form.addRow(QLabel("Имя аккаунта:"), self.new_name_field)
        form.addRow(QLabel("Пароль:"), self.new_pass_field)
        # язык интерфейса — у каждого аккаунта свой (accounts/<имя>/preferences.json)
        self.new_lang_combo = QComboBox()
        try:
            from lang_loader import available_languages, get_language
            for lang in available_languages():
                self.new_lang_combo.addItem(lang["name"], lang["code"])
            i = self.new_lang_combo.findData(get_language())
            if i >= 0:
                self.new_lang_combo.setCurrentIndex(i)
        except Exception:
            pass
        form.addRow(QLabel("Язык интерфейса:"), self.new_lang_combo)
        lay.addLayout(form)
        lay.addStretch(1)

        row = QHBoxLayout()
        back_btn = QPushButton("← Назад")
        back_btn.clicked.connect(lambda: self.stack.setCurrentWidget(self.list_page))
        create_btn = QPushButton("Создать и войти")
        create_btn.setObjectName("Primary")
        create_btn.clicked.connect(self._on_create_clicked)
        row.addWidget(back_btn)
        row.addWidget(create_btn)
        lay.addLayout(row)

        self.create_page = page
        self.stack.addWidget(page)

    def _refresh_avatar_preview(self):
        if self._new_avatar_pixmap is not None:
            base = self._new_avatar_pixmap
        else:
            base = _placeholder_square(self.new_name_field.text().strip() if hasattr(self, "new_name_field") else "", 76)
        self.avatar_btn.setIcon(QIcon(_circle_icon(base, 76)))

    def _on_pick_avatar(self):
        file_path, _ = QFileDialog.getOpenFileName(
            self, "Выбери обложку", os.path.expanduser("~"),
            "Изображения (*.png *.jpg *.jpeg *.webp *.bmp)"
        )
        if not file_path:
            return
        pm = QPixmap(file_path)
        if pm.isNull():
            QMessageBox.warning(self, "GOR Launcher", "Не получилось открыть эту картинку.")
            return
        self._new_avatar_pixmap = _square_crop(pm, 256)  # запишем на диск после создания аккаунта
        self._refresh_avatar_preview()

    def _on_create_clicked(self):
        name = self.new_name_field.text().strip()
        password = self.new_pass_field.text()
        ok, err = am.create_account(name, password, language=self.new_lang_combo.currentData())
        if not ok:
            QMessageBox.warning(self, "GOR Launcher", err)
            return
        if self._new_avatar_pixmap is not None:
            buf = QBuffer()
            buf.open(QIODevice.OpenModeFlag.WriteOnly)
            self._new_avatar_pixmap.save(buf, "PNG")
            am.save_avatar_png(name, bytes(buf.data()))
            buf.close()
        self.selected_account = name
        self.accept()

    # ------------------------------------------------------------- #
    # Страница 3: ввод пароля для входа
    # ------------------------------------------------------------- #
    def _build_login_page(self):
        page = QWidget()
        lay = QVBoxLayout(page)
        lay.setSpacing(14)

        title = QLabel("Вход")
        title.setObjectName("Title")
        lay.addWidget(title)

        self.login_name_label = QLabel("")
        lay.addWidget(self.login_name_label)

        self.login_pass_field = QLineEdit()
        self.login_pass_field.setPlaceholderText("Пароль")
        self.login_pass_field.setEchoMode(QLineEdit.EchoMode.Password)
        self.login_pass_field.returnPressed.connect(self._on_login_submit)
        lay.addWidget(self.login_pass_field)
        lay.addStretch(1)

        row = QHBoxLayout()
        back_btn = QPushButton("← Назад")
        back_btn.clicked.connect(lambda: self.stack.setCurrentWidget(self.list_page))
        login_btn = QPushButton("Войти")
        login_btn.setObjectName("Primary")
        login_btn.clicked.connect(self._on_login_submit)
        row.addWidget(back_btn)
        row.addWidget(login_btn)
        lay.addLayout(row)

        self.login_page = page
        self.stack.addWidget(page)

    def _on_login_submit(self):
        password = self.login_pass_field.text()
        if not am.verify_password(self.login_target, password):
            QMessageBox.warning(self, "GOR Launcher", "Неверный пароль.")
            self.login_pass_field.clear()
            return
        self.selected_account = self.login_target
        self.accept()


# ------------------------------------------------------------------- #
# AccountSwitcherDialog - открывается кнопкой-обложкой внутри лаунчера
# ------------------------------------------------------------------- #
class AccountSwitcherDialog(QDialog):
    """`on_switch_confirmed(name)` вызывается, когда пользователь выбрал
    другой аккаунт и подтвердил перезапуск - им обычно передают функцию,
    которая переключает ссылки и перезапускает bridge_loader.py."""

    def __init__(self, current_account, on_switch_confirmed, parent=None):
        super().__init__(parent)
        self.current_account = current_account
        self.on_switch_confirmed = on_switch_confirmed
        self.setWindowTitle("GOR Launcher — мой аккаунт")
        self.setFixedSize(380, 520)
        self.setStyleSheet(DIALOG_STYLE)

        lay = QVBoxLayout(self)
        lay.setContentsMargins(24, 24, 24, 24)
        lay.setSpacing(12)

        self.big_avatar_label = QLabel()
        self.big_avatar_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._refresh_big_avatar()
        lay.addWidget(self.big_avatar_label)

        name_label = QLabel(current_account)
        name_label.setObjectName("BigName")
        name_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        lay.addWidget(name_label)

        change_avatar_btn = QPushButton("🖼 Сменить обложку")
        change_avatar_btn.clicked.connect(self._on_change_avatar)
        lay.addWidget(change_avatar_btn)

        sep = QLabel("Переключиться на другой аккаунт:")
        sep.setStyleSheet("color: #8a8b90; margin-top: 8px;")
        lay.addWidget(sep)

        self.list_widget = QListWidget()
        self.list_widget.setIconSize(QSize(36, 36))
        self.list_widget.itemDoubleClicked.connect(self._on_switch_clicked)
        lay.addWidget(self.list_widget, 1)
        self._refresh_others_list()

        row = QHBoxLayout()
        close_btn = QPushButton("Закрыть")
        close_btn.clicked.connect(self.reject)
        switch_btn = QPushButton("Переключиться →")
        switch_btn.setObjectName("Primary")
        switch_btn.clicked.connect(self._on_switch_clicked)
        row.addWidget(close_btn)
        row.addWidget(switch_btn)
        lay.addLayout(row)

    def _refresh_big_avatar(self):
        self.big_avatar_label.setPixmap(circular_avatar(self.current_account, 140))

    def _refresh_others_list(self):
        self.list_widget.clear()
        for name in am.list_accounts():
            if name == self.current_account:
                continue
            suffix = " 🔒" if am.account_has_password(name) else ""
            item = QListWidgetItem(QIcon(circular_avatar(name, 36)), f"  {name}{suffix}")
            item.setData(Qt.ItemDataRole.UserRole, name)
            self.list_widget.addItem(item)

    def _on_change_avatar(self):
        if _pick_and_save_avatar(self, self.current_account):
            self._refresh_big_avatar()

    def _on_switch_clicked(self):
        item = self.list_widget.currentItem()
        if not item:
            QMessageBox.information(self, "GOR Launcher", "Выбери аккаунт из списка снизу.")
            return
        target = item.data(Qt.ItemDataRole.UserRole)

        if am.account_has_password(target):
            pwd, ok = QInputDialog.getText(
                self, "Пароль", f"Пароль аккаунта «{target}»:",
                QLineEdit.EchoMode.Password
            )
            if not ok:
                return
            if not am.verify_password(target, pwd):
                QMessageBox.warning(self, "GOR Launcher", "Неверный пароль.")
                return

        reply = QMessageBox.question(
            self, "Перезапустить лаунчер?",
            f"Чтобы переключиться на «{target}», лаунчер нужно перезапустить.\n"
            "Перезапустить сейчас?",
        )
        if reply != QMessageBox.StandardButton.Yes:
            return

        self.accept()
        self.on_switch_confirmed(target)
