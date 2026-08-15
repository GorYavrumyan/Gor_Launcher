import os
import sys
import json
import shutil
import tempfile
import zipfile
import urllib.request

from PyQt6.QtCore import QThread, pyqtSignal
from PyQt6.QtGui import QIcon
from PyQt6.QtWidgets import (
    QApplication, QDialog, QVBoxLayout, QHBoxLayout,
    QLabel, QPushButton, QProgressBar, QMessageBox
)

from style_loader import apply_global_style
from lang_loader import tr

def _find_favicon_path():
    """Ищет favicon.ico рядом со скриптом, на уровень выше и в рабочей папке.
    Если нигде не найден - возвращает путь рядом со скриптом (по умолчанию)
    и выводит предупреждение в консоль, чтобы было видно, что иконка не найдена."""
    script_dir = os.path.dirname(os.path.abspath(__file__))
    candidates = []
    if getattr(sys, "frozen", False):
        candidates.append(os.path.dirname(sys.executable))
    candidates.append(script_dir)
    candidates.append(os.getcwd())
    candidates.append(os.path.dirname(script_dir))
    for d in candidates:
        p = os.path.join(d, "favicon.ico")
        if os.path.exists(p):
            return p
    print(f"[updater] favicon.ico не найден. Проверенные папки: {candidates}")
    return os.path.join(script_dir, "favicon.ico")

# ---------------------------------------------------------------------------
# Настройки репозитория GitHub, откуда берётся обновление.
# ---------------------------------------------------------------------------
GITHUB_OWNER = "GorYavrumyan"
GITHUB_REPO = "Gor_Launcher"
GITHUB_BRANCH = "main"

# Путь к файлу версии ВНУТРИ репозитория (относительно корня репо).
# Файлы лаунчера лежат прямо в корне репозитория (без вложенных папок),
# поэтому путь - просто имя файла.
VERSION_FILE_PATH = "version.json"

# Ссылка на JSON с версией (raw-файл на GitHub)
VERSION_URL = (
    f"https://raw.githubusercontent.com/{GITHUB_OWNER}/{GITHUB_REPO}/"
    f"{GITHUB_BRANCH}/{VERSION_FILE_PATH}"
)

# Ссылка на zip-архив всей ветки репозитория (полный исходный код)
ARCHIVE_URL = (
    f"https://codeload.github.com/{GITHUB_OWNER}/{GITHUB_REPO}/zip/refs/heads/{GITHUB_BRANCH}"
)

# Файл, который ни при каких обстоятельствах не должен перезаписываться
# при обновлении - пользовательская библиотека игр, история и настройки.
PROTECTED_FILE = "games_data.json"

# Папки, которые НЕ пропускаются при обновлении, а синхронизируются
# рекурсивно (файл за файлом, поверх существующих). Сейчас это только
# папка с переводами - её обновление ничем не грозит пользовательским
# данным.
UPDATABLE_FOLDERS = {"lang"}

# Локальный файл с версией, которая установлена у пользователя прямо сейчас.
# Он же и есть version.json из репозитория - при обновлении он будет
# перезаписан новой версией автоматически, вместе с остальными файлами.
LOCAL_VERSION_FILE = "version.json"


def get_project_root():
    """Корневая директория лаунчера (рядом с запускаемым исполняемым файлом)."""
    return os.path.dirname(os.path.abspath(sys.argv[0]))


def get_local_version():
    path = os.path.join(get_project_root(), LOCAL_VERSION_FILE)
    if not os.path.exists(path):
        return "0.0.0"
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f).get("version", "0.0.0")
    except Exception:
        return "0.0.0"


class UpdateWorker(QThread):
    """Фоновый поток обновления.

    Режимы (self.mode):
      - MODE_CHECK   - только проверить версию version.json в репозитории;
      - MODE_INSTALL - скачать zip-архив ветки репозитория, распаковать во
                       временную папку и безопасно скопировать файлы в проект.

    Ключевая защита (см. _safe_copy_files):
      1. Любая ПАПКА в корне архива - пропускается (не создаётся, не
         удаляется, не перезаписывается), КРОМЕ папок из UPDATABLE_FOLDERS
         (сейчас это "lang") - они синхронизируются рекурсивно.
      2. Файл games_data.json - пропускается всегда, даже внутри
         синхронизируемых папок.
      3. Все остальные одиночные файлы - перезаписывают файлы в корне проекта
         (включая сам version.json - так текущая версия обновляется
         автоматически вместе с остальными файлами).
    """

    status_signal = pyqtSignal(str)
    progress_signal = pyqtSignal(int)
    check_result_signal = pyqtSignal(dict)
    finished_signal = pyqtSignal(bool, str)

    MODE_CHECK = "check"
    MODE_INSTALL = "install"

    def __init__(self, mode, current_version="0.0.0"):
        super().__init__()
        self.mode = mode
        self.current_version = current_version
        self._cancelled = False

    def cancel(self):
        self._cancelled = True

    def run(self):
        try:
            if self.mode == self.MODE_CHECK:
                self._check_updates()
            elif self.mode == self.MODE_INSTALL:
                self._install_update()
        except urllib.error.HTTPError as e:
            if e.code == 404:
                self.finished_signal.emit(
                    False,
                    tr("updater.version_not_found_error", path=VERSION_FILE_PATH),
                )
            else:
                self.finished_signal.emit(False, tr("updater.network_error", error=e))
        except Exception as e:
            self.finished_signal.emit(False, tr("updater.generic_error", error=e))

    # ------------------------------------------------------------------ #
    # Проверка обновлений
    # ------------------------------------------------------------------ #
    def _fetch_remote_version(self):
        self.status_signal.emit(tr("updater.checking_status"))
        req = urllib.request.Request(
            VERSION_URL, headers={"User-Agent": "GOR-Launcher-Updater"}
        )
        with urllib.request.urlopen(req, timeout=10) as response:
            return json.loads(response.read().decode("utf-8"))

    def _check_updates(self):
        info = self._fetch_remote_version()
        self.check_result_signal.emit(info)

    # ------------------------------------------------------------------ #
    # Установка обновления
    # ------------------------------------------------------------------ #
    def _install_update(self):
        info = self._fetch_remote_version()
        remote_version = info.get("version", tr("updater.unknown_version"))

        with tempfile.TemporaryDirectory(prefix="gor_update_") as tmp_dir:
            if self._cancelled:
                self.finished_signal.emit(False, tr("updater.update_cancelled"))
                return

            archive_path = os.path.join(tmp_dir, "update_package.zip")

            # 1. Скачивание архива ветки репозитория во временную папку СИСТЕМЫ
            self.status_signal.emit(tr("updater.downloading"))
            self._download(ARCHIVE_URL, archive_path)
            if self._cancelled:
                self.finished_signal.emit(False, tr("updater.update_cancelled"))
                return

            # 2. Распаковка во временную папку
            self.status_signal.emit(tr("updater.extracting"))
            extract_dir = os.path.join(tmp_dir, "extracted")
            os.makedirs(extract_dir, exist_ok=True)
            with zipfile.ZipFile(archive_path, "r") as zf:
                zf.extractall(extract_dir)
            if self._cancelled:
                self.finished_signal.emit(False, tr("updater.update_cancelled"))
                return

            # GitHub всегда оборачивает содержимое ветки в единственную папку
            # верхнего уровня вида "Gor_Launcher-main" - файлы лаунчера лежат
            # прямо внутри неё (в корне репозитория), без вложенных папок.
            source_root = self._locate_project_source(extract_dir)
            if source_root is None:
                self.finished_signal.emit(
                    False,
                    tr("updater.source_not_found"),
                )
                return

            # 3. Безопасное точечное копирование файлов в проект
            self.status_signal.emit(tr("updater.safe_updating"))
            self._safe_copy_files(source_root, get_project_root())
            if self._cancelled:
                self.finished_signal.emit(False, tr("updater.update_cancelled"))
                return

        # tmp_dir удаляется автоматически при выходе из контекстного менеджера
        self.status_signal.emit(tr("updater.update_done_status"))
        self.finished_signal.emit(
            True,
            tr("updater.update_done_message", version=remote_version),
        )

    def _locate_project_source(self, extract_dir):
        """Находит корневую папку репозитория внутри распакованного архива.
        GitHub всегда кладёт всё содержимое ветки в единственную папку
        верхнего уровня вида "<repo>-<branch>" - файлы лаунчера лежат
        прямо внутри неё."""
        top_entries = [
            e for e in os.listdir(extract_dir)
            if os.path.isdir(os.path.join(extract_dir, e))
        ]
        for top in top_entries:
            candidate = os.path.join(extract_dir, top)
            if os.path.exists(os.path.join(candidate, "GorLauncher.py")):
                return candidate
        # Резервный вариант: если по какой-то причине GorLauncher.py не
        # нашёлся, но папка верхнего уровня всё равно ровно одна - берём её.
        if len(top_entries) == 1:
            return os.path.join(extract_dir, top_entries[0])
        return None

    def _download(self, url, dest_path):
        req = urllib.request.Request(
            url, headers={"User-Agent": "GOR-Launcher-Updater"}
        )
        with urllib.request.urlopen(req, timeout=30) as response:
            total_size = int(response.info().get("Content-Length", 0))
            downloaded = 0
            with open(dest_path, "wb") as f:
                while True:
                    if self._cancelled:
                        return
                    chunk = response.read(8192)
                    if not chunk:
                        break
                    f.write(chunk)
                    downloaded += len(chunk)
                    if total_size > 0:
                        self.progress_signal.emit(int(downloaded * 100 / total_size))

    def _safe_copy_files(self, source_root, project_root):
        """Копирует отдельные файлы из КОРНЯ source_root (папка Launcher
        внутри архива) в корень проекта.

        Папки пропускаются полностью, КРОМЕ тех, что перечислены в
        UPDATABLE_FOLDERS (сейчас - "lang") - их содержимое синхронизируется
        рекурсивно поверх уже существующей папки в проекте."""

        entries = sorted(os.listdir(source_root))
        total = len(entries) if entries else 1

        for idx, entry in enumerate(entries):
            if self._cancelled:
                return

            src_path = os.path.join(source_root, entry)

            if os.path.isdir(src_path):
                if entry in UPDATABLE_FOLDERS:
                    # Папка из белого списка - синхронизируем её содержимое
                    self.status_signal.emit(tr("updater.updating_file", name=entry))
                    self._sync_folder(src_path, os.path.join(project_root, entry))
                else:
                    # Правило 1: любая другая папка - полностью пропускается
                    self.status_signal.emit(tr("updater.skip_folder", name=entry))
                self.progress_signal.emit(int((idx + 1) / total * 100))
                continue

            # Правило 2: пользовательская база данных неприкосновенна
            if entry == PROTECTED_FILE:
                self.status_signal.emit(tr("updater.skip_protected", name=entry))
                self.progress_signal.emit(int((idx + 1) / total * 100))
                continue

            # Правило 3: остальные одиночные файлы обновляем поверх старых
            dest_path = os.path.join(project_root, entry)
            self.status_signal.emit(tr("updater.updating_file", name=entry))
            shutil.copy2(src_path, dest_path)
            self.progress_signal.emit(int((idx + 1) / total * 100))

    def _sync_folder(self, src_dir, dest_dir):
        """Рекурсивно копирует содержимое папки (например "lang") поверх
        уже существующей в проекте, создавая недостающие подпапки и файлы.
        PROTECTED_FILE пропускается даже здесь - на всякий случай, если он
        вдруг окажется внутри такой папки."""
        os.makedirs(dest_dir, exist_ok=True)
        for entry in sorted(os.listdir(src_dir)):
            if self._cancelled:
                return
            src_path = os.path.join(src_dir, entry)
            dest_path = os.path.join(dest_dir, entry)
            if os.path.isdir(src_path):
                self._sync_folder(src_path, dest_path)
            else:
                if entry == PROTECTED_FILE:
                    continue
                shutil.copy2(src_path, dest_path)


class UpdaterDialog(QDialog):
    """Окно обновления GOR Launcher, оформленное в едином стиле проекта
    (style.qss, селектор #EditorDialog)."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.current_version = get_local_version()
        self.worker = None
        self.latest_info = None

        self.setObjectName("EditorDialog")
        self.setWindowTitle(tr("updater.window_title"))
        self.setWindowIcon(QIcon(_find_favicon_path()))
        self.setFixedWidth(550)

        self._init_ui()

    def _init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(15)

        title = QLabel(tr("updater.window_title"))
        layout.addWidget(title)

        self.status_label = QLabel(
            tr("updater.status_initial", version=self.current_version)
        )
        self.status_label.setWordWrap(True)
        layout.addWidget(self.status_label)

        self.progress_bar = QProgressBar()
        self.progress_bar.setValue(0)
        # Полоса прогресса скрыта, пока реально не началась установка
        # обновления (появляется только в install_update, а не во время
        # обычной проверки версии).
        self.progress_bar.setVisible(False)
        layout.addWidget(self.progress_bar)

        btn_layout = QHBoxLayout()

        self.check_btn = QPushButton(tr("updater.check_btn"))
        self.check_btn.clicked.connect(self.check_updates)

        self.install_btn = QPushButton(tr("updater.install_btn"))
        self.install_btn.clicked.connect(self.install_update)
        self.install_btn.setEnabled(False)

        self.cancel_btn = QPushButton(tr("common.cancel"))
        self.cancel_btn.setObjectName("CancelBtn")
        self.cancel_btn.clicked.connect(self.cancel_or_close)

        btn_layout.addWidget(self.check_btn)
        btn_layout.addWidget(self.install_btn)
        btn_layout.addWidget(self.cancel_btn)
        layout.addLayout(btn_layout)

    # ------------------------------------------------------------------ #
    def _start_worker(self, mode):
        self.worker = UpdateWorker(mode, self.current_version)
        self.worker.status_signal.connect(self.status_label.setText)
        self.worker.progress_signal.connect(self.progress_bar.setValue)
        self.worker.check_result_signal.connect(self._on_check_result)
        self.worker.finished_signal.connect(self._on_finished)
        self._set_buttons_busy(True)
        self.worker.start()

    def _set_buttons_busy(self, busy):
        self.check_btn.setEnabled(not busy)
        self.install_btn.setEnabled(not busy and self.latest_info is not None)

    def check_updates(self):
        # Во время простой проверки версии полоса прогресса не нужна
        self.progress_bar.setVisible(False)
        self.progress_bar.setValue(0)
        self._start_worker(UpdateWorker.MODE_CHECK)

    def install_update(self):
        if self.latest_info is None:
            return
        reply = QMessageBox.question(
            self, tr("updater.confirm_title"),
            tr("updater.confirm_text"),
        )
        if reply != QMessageBox.StandardButton.Yes:
            return
        self.progress_bar.setValue(0)
        # Показываем полосу прогресса только сейчас - обновление лаунчера
        # действительно началось.
        self.progress_bar.setVisible(True)
        self._start_worker(UpdateWorker.MODE_INSTALL)

    def _on_check_result(self, info):
        self.latest_info = info
        remote_version = info.get("version", tr("updater.unknown_version"))
        if remote_version == self.current_version:
            self.status_label.setText(
                tr("updater.already_latest", version=self.current_version)
            )
            self.install_btn.setEnabled(False)
        else:
            self.status_label.setText(
                tr("updater.update_available", remote=remote_version, current=self.current_version)
            )
            self.install_btn.setEnabled(True)

    def _on_finished(self, success, message):
        self._set_buttons_busy(False)
        self.status_label.setText(message)
        if success:
            self.current_version = get_local_version()
            reply = QMessageBox.question(
                self, tr("updater.window_title"),
                tr("updater.restart_prompt", message=message)
            )
            if reply == QMessageBox.StandardButton.Yes:
                # Ленивый импорт - чтобы не создавать циклическую зависимость
                # bridge_loader <-> updater (bridge_loader сам импортирует updater).
                from bridge_loader import restart_launcher
                restart_launcher(confirm=False)
        elif "отменено" not in message.lower() and "cancel" not in message.lower():
            QMessageBox.warning(self, tr("updater.window_title"), message)

    def cancel_or_close(self):
        if self.worker and self.worker.isRunning():
            self.worker.cancel()
            self.status_label.setText(tr("updater.cancelling"))
        else:
            self.reject()

    def closeEvent(self, event):
        if self.worker and self.worker.isRunning():
            self.worker.cancel()
            self.worker.wait(2000)
        event.accept()


if __name__ == "__main__":
    app = QApplication(sys.argv)
    app.setWindowIcon(QIcon(_find_favicon_path()))
    apply_global_style(app)
    dialog = UpdaterDialog()
    dialog.show()
    sys.exit(app.exec())