"""
browser_downloads.py
---------------------
Всё, что относится к загрузкам файлов в GOR Browser:
  - DownloadItem   - строка с прогрессом одной загрузки;
  - DownloadManager - диалог со списком всех загрузок.
"""

import os
import subprocess
import sys

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QProgressBar,
    QPushButton, QDialog, QListWidget, QListWidgetItem,
)
from PyQt6.QtWebEngineCore import QWebEngineDownloadRequest


class DownloadItem(QWidget):
    def __init__(self, download_item: QWebEngineDownloadRequest, parent=None):
        super().__init__(parent)
        self.download_item = download_item
        layout = QHBoxLayout(self)  # Горизонтальный лейаут для кнопок в ряд

        # Информация о файле и прогресс
        info_layout = QVBoxLayout()
        self.label = QLabel(download_item.downloadFileName())
        self.pbar = QProgressBar()
        self.pbar.setFixedHeight(10)
        info_layout.addWidget(self.label)
        info_layout.addWidget(self.pbar)
        layout.addLayout(info_layout)

        # Кнопка открытия папки
        self.btn_open = QPushButton("📂")
        self.btn_open.setFixedSize(35, 35)
        self.btn_open.setEnabled(False)
        self.btn_open.setToolTip("Открыть папку")
        self.btn_open.clicked.connect(self.open_folder)

        # Кнопка отмены
        self.btn_cancel = QPushButton("❌")
        self.btn_cancel.setFixedSize(35, 35)
        self.btn_cancel.setToolTip("Отменить")
        self.btn_cancel.clicked.connect(lambda: self.download_item.cancel())

        layout.addWidget(self.btn_open)
        layout.addWidget(self.btn_cancel)

        download_item.receivedBytesChanged.connect(self.update_progress)
        download_item.stateChanged.connect(self.handle_state)

    def update_progress(self):
        total = self.download_item.totalBytes()
        received = self.download_item.receivedBytes()

        total_mb = total / (1024 * 1024)
        received_mb = received / (1024 * 1024)

        self.label.setText(f"{self.download_item.downloadFileName()} ({received_mb:.1f} / {total_mb:.1f} MB)")

        if total > 0:
            self.pbar.setValue(int(received / total * 100))

    def open_folder(self):
        """Открывает папку, где лежит файл (кроссплатформенно)."""
        path = self.download_item.downloadDirectory()
        if os.path.exists(path):
            if hasattr(os, "startfile"):
                os.startfile(path)  # Windows
            elif sys.platform == "darwin":
                subprocess.run(["open", path])
            else:
                subprocess.run(["xdg-open", path])

    def handle_state(self, state):
        if state == QWebEngineDownloadRequest.DownloadState.DownloadCompleted:
            self.label.setText(f"✅ {self.download_item.downloadFileName()}")
            self.btn_open.setEnabled(True)
            self.btn_cancel.hide()
        elif state == QWebEngineDownloadRequest.DownloadState.DownloadCancelled:
            self.label.setText(f"❌ Отменено: {self.download_item.downloadFileName()}")
            self.btn_cancel.setEnabled(False)
        elif state == QWebEngineDownloadRequest.DownloadState.DownloadInterrupted:
            self.label.setText(f"⚠️ Ошибка: {self.download_item.downloadFileName()}")


class DownloadManager(QDialog):
    def __init__(self, parent):
        super().__init__(parent)
        self.setWindowTitle("Загрузки GOR")
        self.resize(500, 400)
        self.setStyleSheet("background-color: #1c1d21; color: white;")

        self.layout = QVBoxLayout(self)

        header = QHBoxLayout()
        header.addWidget(QLabel("📦 ТЕКУЩИЕ ЗАГРУЗКИ"))
        btn_clear = QPushButton("Очистить список")
        btn_clear.clicked.connect(self.clear_finished)
        btn_clear.setStyleSheet("background: #2c2e33; padding: 5px; border-radius: 4px;")
        header.addWidget(btn_clear)
        self.layout.addLayout(header)

        self.list_widget = QListWidget()
        self.layout.addWidget(self.list_widget)

    def add_download(self, download_item):
        item = QListWidgetItem(self.list_widget)
        widget = DownloadItem(download_item)
        item.setSizeHint(widget.sizeHint())
        self.list_widget.addItem(item)
        self.list_widget.setItemWidget(item, widget)
        self.show()

    def clear_finished(self):
        """Удаляем из списка только те элементы, где загрузка не идёт."""
        for i in range(self.list_widget.count() - 1, -1, -1):
            item = self.list_widget.item(i)
            widget = self.list_widget.itemWidget(item)
            state = widget.download_item.state()
            if state != QWebEngineDownloadRequest.DownloadState.DownloadInProgress:
                self.list_widget.takeItem(i)
