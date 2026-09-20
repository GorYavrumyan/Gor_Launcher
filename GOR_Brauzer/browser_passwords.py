"""
browser_passwords.py
----------------------
Локальный менеджер паролей GOR Browser (пункт ТЗ: "Простая система хранения
паролей с локальным шифрованием (AES / Cryptography)").

Схема шифрования:
    - Мастер-пароль пользователя НИКОГДА не хранится на диске.
    - При создании хранилища генерируется случайная соль (16 байт), из
      мастер-пароля + соли через PBKDF2-HMAC-SHA256 (390 000 итераций -
      актуальная на 2024-2025 рекомендация OWASP) выводится 32-байтный ключ.
    - Ключ используется для Fernet (симметричное AES-128-CBC + HMAC-SHA256
      аутентификация, из пакета `cryptography` - т.е. именно "AES /
      Cryptography", как и просили в ТЗ).
    - Все записи (сайт/логин/пароль/заметка) хранятся ТОЛЬКО в
      зашифрованном виде одним blob'ом в passwords.vault. Расшифрованные
      данные живут исключительно в оперативной памяти на время текущей
      разблокированной сессии (self._entries в PasswordVault) и обнуляются
      при lock()/закрытии браузера.
    - Отдельный "verifier" (зашифрованная константа) нужен, чтобы проверить
      правильность введённого мастер-пароля БЕЗ попытки распарсить весь
      vault как JSON (что маскировало бы разницу между "неверный пароль" и
      "повреждённый файл").

ВАЖНО (сознательный охват фичи): это ХРАНИЛИЩЕ с ручным вводом/просмотром/
копированием записей, а НЕ автозаполнение форм на страницах и не перехват
логинов с сайтов. Автозаполнение - отдельная, значительно более рискованная
с точки зрения безопасности фича (нужно надёжно распознавать поля логина/
пароля на произвольных сайтах, не путать чужие формы и т.п.) - в этот патч
сознательно не включена, чтобы не поставлять сырую/потенциально опасную
реализацию.

Использование (см. browser_widget.py):

    from browser_passwords import PasswordVault, PasswordManagerDialog

    self.password_vault = PasswordVault(vault_path)
    ...
    dlg = PasswordManagerDialog(self, self.password_vault)
    dlg.exec()
"""

import base64
import json
import os
import secrets
import string

from cryptography.fernet import Fernet, InvalidToken
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QApplication, QDialog, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit, QPushButton,
    QListWidget, QListWidgetItem, QMessageBox, QFormLayout, QWidget,
)

_KDF_ITERATIONS = 390_000
_VERIFIER_PLAINTEXT = b"gor-browser-vault-ok"


def _derive_key(master_password: str, salt: bytes) -> bytes:
    kdf = PBKDF2HMAC(
        algorithm=hashes.SHA256(),
        length=32,
        salt=salt,
        iterations=_KDF_ITERATIONS,
    )
    raw_key = kdf.derive(master_password.encode("utf-8"))
    return base64.urlsafe_b64encode(raw_key)


def generate_strong_password(length=16):
    """Генератор паролей для кнопки "Сгенерировать" в диалоге записи -
    минимум по одному символу каждого класса, остальное - случайный набор,
    затем перемешивается (secrets.SystemRandom - криптографически стойкий)."""
    length = max(8, length)
    alphabet = string.ascii_letters + string.digits + "!@#$%^&*()-_=+"
    rng = secrets.SystemRandom()
    required = [
        rng.choice(string.ascii_uppercase),
        rng.choice(string.ascii_lowercase),
        rng.choice(string.digits),
        rng.choice("!@#$%^&*()-_=+"),
    ]
    rest = [rng.choice(alphabet) for _ in range(length - len(required))]
    chars = required + rest
    rng.shuffle(chars)
    return "".join(chars)


class PasswordVault:
    """Хранилище паролей - один экземпляр на GORBrowser. Не хранит открытый
    мастер-пароль и открытые записи на диске ни при каких обстоятельствах."""

    def __init__(self, path):
        self.path = path
        self._key = None            # Fernet-ключ, только пока разблокировано
        self._entries = []          # [{"id","site","username","password","note"}], только в памяти

    # -- состояние --------------------------------------------------

    def exists(self) -> bool:
        return os.path.exists(self.path)

    def is_unlocked(self) -> bool:
        return self._key is not None

    def lock(self):
        """Забывает ключ и все расшифрованные записи - вызывается при
        закрытии браузера и по явному запросу пользователя."""
        self._key = None
        self._entries = []

    # -- создание / разблокировка -----------------------------------

    def create(self, master_password: str):
        """Создаёт новое пустое хранилище с новым мастер-паролем (перезаписывает
        существующий файл, если он был - вызывающий код должен явно
        подтвердить это действие у пользователя)."""
        salt = secrets.token_bytes(16)
        key = _derive_key(master_password, salt)
        fernet = Fernet(key)
        data = {
            "salt": base64.b64encode(salt).decode("ascii"),
            "verifier": fernet.encrypt(_VERIFIER_PLAINTEXT).decode("ascii"),
            "vault": fernet.encrypt(json.dumps([]).encode("utf-8")).decode("ascii"),
        }
        self._write(data)
        self._key = key
        self._entries = []

    def unlock(self, master_password: str) -> bool:
        """Пытается разблокировать существующее хранилище. Возвращает False
        при неверном пароле или повреждённом файле - НЕ бросает исключение
        наружу, чтобы UI мог просто показать "неверный пароль"."""
        try:
            with open(self.path, "r", encoding="utf-8") as f:
                data = json.load(f)
            salt = base64.b64decode(data["salt"])
            key = _derive_key(master_password, salt)
            fernet = Fernet(key)
            if fernet.decrypt(data["verifier"].encode("ascii")) != _VERIFIER_PLAINTEXT:
                return False
            entries = json.loads(fernet.decrypt(data["vault"].encode("ascii")).decode("utf-8"))
        except (InvalidToken, KeyError, ValueError, json.JSONDecodeError, OSError):
            return False
        self._key = key
        self._entries = entries
        return True

    def change_master_password(self, new_master_password: str):
        """Перешифровывает уже расшифрованные (в памяти) записи новым
        мастер-паролем - вызывается только когда vault уже разблокирован."""
        if not self.is_unlocked():
            raise RuntimeError("Хранилище заблокировано")
        salt = secrets.token_bytes(16)
        key = _derive_key(new_master_password, salt)
        fernet = Fernet(key)
        data = {
            "salt": base64.b64encode(salt).decode("ascii"),
            "verifier": fernet.encrypt(_VERIFIER_PLAINTEXT).decode("ascii"),
            "vault": fernet.encrypt(json.dumps(self._entries).encode("utf-8")).decode("ascii"),
        }
        self._write(data)
        self._key = key

    # -- запись/чтение записей ---------------------------------------

    def list_entries(self):
        return list(self._entries)

    def add_entry(self, site, username, password, note=""):
        entry = {
            "id": secrets.token_hex(8),
            "site": site, "username": username, "password": password, "note": note,
        }
        self._entries.append(entry)
        self._persist()
        return entry

    def update_entry(self, entry_id, **fields):
        for entry in self._entries:
            if entry["id"] == entry_id:
                entry.update(fields)
                self._persist()
                return True
        return False

    def delete_entry(self, entry_id):
        before = len(self._entries)
        self._entries = [e for e in self._entries if e["id"] != entry_id]
        if len(self._entries) != before:
            self._persist()

    # -- внутреннее ----------------------------------------------------

    def _persist(self):
        """Перезаписывает ТОЛЬКО зашифрованный blob "vault" в уже
        существующем файле, сохраняя ту же соль/verifier/ключ сессии."""
        if not self.is_unlocked():
            return
        with open(self.path, "r", encoding="utf-8") as f:
            data = json.load(f)
        fernet = Fernet(self._key)
        data["vault"] = fernet.encrypt(json.dumps(self._entries).encode("utf-8")).decode("ascii")
        self._write(data)

    def _write(self, data):
        tmp_path = self.path + ".tmp"
        with open(tmp_path, "w", encoding="utf-8") as f:
            json.dump(data, f)
        os.replace(tmp_path, self.path)


# ======================================================================
# UI
# ======================================================================

class _UnlockDialog(QDialog):
    """Диалог создания мастер-пароля (первый запуск) или разблокировки
    существующего хранилища."""

    def __init__(self, parent, vault: PasswordVault):
        super().__init__(parent)
        self.vault = vault
        self.setWindowTitle("🔑 Менеджер паролей")
        self.setMinimumWidth(360)
        layout = QVBoxLayout(self)

        creating = not vault.exists()
        title = QLabel(
            "Создайте мастер-пароль для локального хранилища паролей."
            if creating else
            "Введите мастер-пароль, чтобы открыть хранилище."
        )
        title.setWordWrap(True)
        layout.addWidget(title)

        warn = QLabel(
            "⚠️ Мастер-пароль нигде не сохраняется. Если вы его забудете, "
            "восстановить сохранённые пароли будет невозможно."
        )
        warn.setWordWrap(True)
        warn.setStyleSheet("color: #f59f00; font-size: 11px;")
        layout.addWidget(warn)

        self.pw1 = QLineEdit()
        self.pw1.setEchoMode(QLineEdit.EchoMode.Password)
        self.pw1.setPlaceholderText("Мастер-пароль")
        layout.addWidget(self.pw1)

        self.pw2 = None
        if creating:
            self.pw2 = QLineEdit()
            self.pw2.setEchoMode(QLineEdit.EchoMode.Password)
            self.pw2.setPlaceholderText("Повторите мастер-пароль")
            layout.addWidget(self.pw2)

        self.error_label = QLabel("")
        self.error_label.setStyleSheet("color: #ff6b6b;")
        layout.addWidget(self.error_label)

        btn_row = QHBoxLayout()
        btn_ok = QPushButton("Создать" if creating else "Разблокировать")
        btn_ok.clicked.connect(self._on_confirm)
        btn_cancel = QPushButton("Отмена")
        btn_cancel.clicked.connect(self.reject)
        btn_row.addWidget(btn_ok)
        btn_row.addWidget(btn_cancel)
        layout.addLayout(btn_row)

        self._creating = creating
        self.pw1.returnPressed.connect(self._on_confirm)

    def _on_confirm(self):
        pw = self.pw1.text()
        if self._creating:
            if len(pw) < 6:
                self.error_label.setText("Мастер-пароль должен быть не короче 6 символов.")
                return
            if pw != self.pw2.text():
                self.error_label.setText("Пароли не совпадают.")
                return
            self.vault.create(pw)
            self.accept()
        else:
            if not self.vault.unlock(pw):
                self.error_label.setText("Неверный мастер-пароль.")
                self.pw1.clear()
                return
            self.accept()


class _EntryDialog(QDialog):
    """Диалог добавления/редактирования одной записи."""

    def __init__(self, parent, entry=None):
        super().__init__(parent)
        self.setWindowTitle("Запись" if entry else "Новая запись")
        self.setMinimumWidth(360)
        entry = entry or {}
        layout = QFormLayout(self)

        self.site_input = QLineEdit(entry.get("site", ""))
        self.site_input.setPlaceholderText("example.com")
        layout.addRow("Сайт:", self.site_input)

        self.user_input = QLineEdit(entry.get("username", ""))
        layout.addRow("Логин:", self.user_input)

        pw_row = QHBoxLayout()
        self.pw_input = QLineEdit(entry.get("password", ""))
        self.pw_input.setEchoMode(QLineEdit.EchoMode.Password)
        btn_show = QPushButton("👁")
        btn_show.setFixedWidth(32)
        btn_show.setCheckable(True)
        btn_show.toggled.connect(
            lambda on: self.pw_input.setEchoMode(
                QLineEdit.EchoMode.Normal if on else QLineEdit.EchoMode.Password
            )
        )
        btn_gen = QPushButton("🎲")
        btn_gen.setFixedWidth(32)
        btn_gen.setToolTip("Сгенерировать надёжный пароль")
        btn_gen.clicked.connect(lambda: self.pw_input.setText(generate_strong_password()))
        pw_row.addWidget(self.pw_input)
        pw_row.addWidget(btn_show)
        pw_row.addWidget(btn_gen)
        pw_container = QWidget()
        pw_container.setLayout(pw_row)
        layout.addRow("Пароль:", pw_container)

        self.note_input = QLineEdit(entry.get("note", ""))
        layout.addRow("Заметка:", self.note_input)

        btn_row = QHBoxLayout()
        btn_save = QPushButton("Сохранить")
        btn_save.clicked.connect(self._on_save)
        btn_cancel = QPushButton("Отмена")
        btn_cancel.clicked.connect(self.reject)
        btn_row.addWidget(btn_save)
        btn_row.addWidget(btn_cancel)
        layout.addRow(btn_row)

        self.result_data = None

    def _on_save(self):
        if not self.site_input.text().strip():
            QMessageBox.warning(self, "GOR Browser", "Укажите сайт.")
            return
        self.result_data = {
            "site": self.site_input.text().strip(),
            "username": self.user_input.text().strip(),
            "password": self.pw_input.text(),
            "note": self.note_input.text().strip(),
        }
        self.accept()


class PasswordManagerDialog(QDialog):
    """Главное окно менеджера паролей: список записей + добавить/изменить/
    удалить/скопировать. Открывается ТОЛЬКО после успешной разблокировки
    (см. open_password_manager() ниже - удобная точка входа для меню)."""

    def __init__(self, parent, vault: PasswordVault):
        super().__init__(parent)
        self.vault = vault
        self.setWindowTitle("🔑 Менеджер паролей")
        self.setMinimumSize(420, 420)
        layout = QVBoxLayout(self)

        self.list_widget = QListWidget()
        self.list_widget.itemDoubleClicked.connect(self._edit_selected)
        layout.addWidget(self.list_widget)

        btn_row = QHBoxLayout()
        btn_add = QPushButton("➕ Добавить")
        btn_add.clicked.connect(self._add_entry)
        btn_copy = QPushButton("📋 Копировать пароль")
        btn_copy.clicked.connect(self._copy_selected)
        btn_edit = QPushButton("✏️ Изменить")
        btn_edit.clicked.connect(self._edit_selected)
        btn_del = QPushButton("🗑️ Удалить")
        btn_del.clicked.connect(self._delete_selected)
        for b in (btn_add, btn_copy, btn_edit, btn_del):
            btn_row.addWidget(b)
        layout.addLayout(btn_row)

        btn_lock = QPushButton("🔒 Заблокировать и закрыть")
        btn_lock.clicked.connect(self._lock_and_close)
        layout.addWidget(btn_lock)

        self._refresh()

    def _refresh(self):
        self.list_widget.clear()
        for entry in sorted(self.vault.list_entries(), key=lambda e: e.get("site", "").lower()):
            label = f"{entry.get('site', '?')}  —  {entry.get('username', '') or '(без логина)'}"
            item = QListWidgetItem(label)
            item.setData(Qt.ItemDataRole.UserRole, entry["id"])
            self.list_widget.addItem(item)

    def _selected_entry(self):
        item = self.list_widget.currentItem()
        if not item:
            return None
        entry_id = item.data(Qt.ItemDataRole.UserRole)
        return next((e for e in self.vault.list_entries() if e["id"] == entry_id), None)

    def _add_entry(self):
        dlg = _EntryDialog(self)
        if dlg.exec() and dlg.result_data:
            self.vault.add_entry(**dlg.result_data)
            self._refresh()

    def _edit_selected(self):
        entry = self._selected_entry()
        if not entry:
            return
        dlg = _EntryDialog(self, entry)
        if dlg.exec() and dlg.result_data:
            self.vault.update_entry(entry["id"], **dlg.result_data)
            self._refresh()

    def _delete_selected(self):
        entry = self._selected_entry()
        if not entry:
            return
        reply = QMessageBox.question(self, "Удалить запись", f"Удалить запись «{entry.get('site')}»?")
        if reply == QMessageBox.StandardButton.Yes:
            self.vault.delete_entry(entry["id"])
            self._refresh()

    def _copy_selected(self):
        entry = self._selected_entry()
        if not entry:
            return
        QApplication.clipboard().setText(entry.get("password", ""))

    def _lock_and_close(self):
        self.vault.lock()
        self.close()


def open_password_manager(parent_browser, vault: PasswordVault):
    """Единая точка входа для меню/хоткея: если хранилище заблокировано -
    сперва просит создать/ввести мастер-пароль, и только потом открывает
    сам менеджер записей."""
    if not vault.is_unlocked():
        unlock_dlg = _UnlockDialog(parent_browser, vault)
        if unlock_dlg.exec() != QDialog.DialogCode.Accepted:
            return
    dlg = PasswordManagerDialog(parent_browser, vault)
    dlg.exec()
