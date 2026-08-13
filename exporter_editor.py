import sys
import json
import zipfile
import os
import shutil
import time
from PyQt6.QtWidgets import (QApplication, QWidget, QVBoxLayout, QHBoxLayout, 
                             QPushButton, QListWidget, QListWidgetItem, 
                             QLabel, QLineEdit, QProgressBar, QMessageBox, QFileDialog, QScrollArea, QCheckBox)
from PyQt6.QtCore import Qt, QThread, pyqtSignal
from PyQt6.QtGui import QIcon

from style_loader import apply_global_style
from lang_loader import tr

# Оформление приложения теперь берётся из общего style.qss (см. style_loader.py),
# который применяется глобально к QApplication в блоке __main__.

class PackerWorker(QThread):
    progress = pyqtSignal(int, str, int, int)
    finished = pyqtSignal()

    def __init__(self, selected_games, output_path, master_name, include_json):
        super().__init__()
        self.selected_games = selected_games
        self.output_path = output_path
        self.master_name = master_name
        self.include_json = include_json

    def run(self):
        total = len(self.selected_games)
        temp_dir = os.path.join(self.output_path, "temp_game_zips")
        os.makedirs(temp_dir, exist_ok=True)
        game_zips = []
        
        for i, game in enumerate(self.selected_games):
            game_name = game['name']
            game_zip_path = os.path.join(temp_dir, f"{game_name}.zip")
            root_folder = game.get('root_path', '')
            
            files_list = []
            if os.path.exists(root_folder):
                for root, _, files in os.walk(root_folder):
                    for file in files: files_list.append(os.path.join(root, file))
            
            with zipfile.ZipFile(game_zip_path, 'w', zipfile.ZIP_DEFLATED) as zf:
                for idx, f_path in enumerate(files_list):
                    zf.write(f_path, arcname=os.path.join(game_name, os.path.relpath(f_path, root_folder)))
                    p_game = int(((idx + 1) / len(files_list)) * 100) if files_list else 100
                    p_total = int(((i + (idx + 1) / len(files_list)) / (total if total > 0 else 1)) * 50)
                    self.progress.emit(p_total, tr("exporter.packing_label", name=game_name), i, p_game)
                
                icon_path = game.get('icon', '')
                if icon_path and os.path.exists(icon_path):
                    zf.write(icon_path, arcname=f"{game_name}{os.path.splitext(icon_path)[1]}")
            
            game_zips.append(game_zip_path)
            
        master_full_path = os.path.join(self.output_path, f"{self.master_name}.zip")
        with zipfile.ZipFile(master_full_path, 'w', zipfile.ZIP_DEFLATED) as master_zip:
            total_zips = len(game_zips) if game_zips else 1
            for i, zf_path in enumerate(game_zips):
                self.progress.emit(50 + int((i + 1) / total_zips * 50), tr("exporter.assembling_label"), -1, 0)
                master_zip.write(zf_path, arcname=os.path.basename(zf_path))
                os.remove(zf_path)
            
            if self.include_json and os.path.exists("games_data.json"):
                master_zip.write("games_data.json", arcname="games_data.json")
        
        time.sleep(0.5)
        if os.path.exists(temp_dir):
            shutil.rmtree(temp_dir, ignore_errors=True)
            
        self.finished.emit()


with open("version.json", "r", encoding="utf-8") as f:
    version = json.load(f)["version"]


class PackerGUI(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle(tr("exporter.window_title") + "   " + version)
        self.setFixedSize(500, 700)
        self.games = self.load_games()
        self.selected_folder = ""
        self.init_ui()

    def load_games(self):
        if not os.path.exists("games_data.json"): return []
        with open("games_data.json", 'r', encoding='utf-8') as f:
            data = json.load(f)
            all_g = data.get("standalone", [])
            for grp in data.get("groups", {}).values(): all_g.extend(grp)
            return all_g

    def init_ui(self):
        layout = QVBoxLayout(self)
        layout.addWidget(QLabel(tr("exporter.name_label")))
        self.name_edit = QLineEdit(tr("exporter.default_name"))
        layout.addWidget(self.name_edit)
        
        layout.addWidget(QLabel(tr("exporter.save_location_label")))
        folder_layout = QHBoxLayout()
        self.folder_edit = QLineEdit()
        self.folder_edit.setReadOnly(True)
        self.folder_btn = QPushButton(tr("common.browse"))
        self.folder_btn.clicked.connect(self.select_folder)
        folder_layout.addWidget(self.folder_edit)
        folder_layout.addWidget(self.folder_btn)
        layout.addLayout(folder_layout)

        check_layout = QHBoxLayout()
        self.all_check = QCheckBox(tr("exporter.select_all_check"))
        self.all_check.stateChanged.connect(self.toggle_all)
        self.json_check = QCheckBox(tr("exporter.include_json_check"))
        check_layout.addWidget(self.all_check)
        check_layout.addWidget(self.json_check)
        layout.addLayout(check_layout)

        layout.addWidget(QLabel(tr("exporter.select_games_label")))
        self.list_widget = QListWidget()
        for game in self.games:
            item = QListWidgetItem(game['name'])
            item.setFlags(item.flags() | Qt.ItemFlag.ItemIsUserCheckable)
            item.setCheckState(Qt.CheckState.Unchecked)
            self.list_widget.addItem(item)
        layout.addWidget(self.list_widget)
        
        self.ok_btn = QPushButton(tr("exporter.start_export_btn"))
        self.ok_btn.setObjectName("ExportBtn")
        self.ok_btn.clicked.connect(self.start_export)
        layout.addWidget(self.ok_btn)

    def toggle_all(self, state):
        for i in range(self.list_widget.count()):
            self.list_widget.item(i).setCheckState(Qt.CheckState.Checked if state == 2 else Qt.CheckState.Unchecked)

    def select_folder(self):
        folder = QFileDialog.getExistingDirectory(self, tr("exporter.select_folder_dialog_title"))
        if folder:
            self.selected_folder = folder
            self.folder_edit.setText(folder)

    def start_export(self):
        selected = [g for i, g in enumerate(self.games) if self.list_widget.item(i).checkState() == Qt.CheckState.Checked]
        if not selected and not self.json_check.isChecked():
            QMessageBox.warning(self, tr("common.error"), tr("exporter.error_no_games"))
            return
        if not self.selected_folder:
            QMessageBox.warning(self, tr("common.error"), tr("exporter.error_no_folder"))
            return
        self.hide()
        self.progress_win = ProgressWindow(selected, self.selected_folder, self.name_edit.text(), self.json_check.isChecked())
        self.progress_win.show()

class ProgressWindow(QWidget):
    def __init__(self, selected_games, output_path, master_name, include_json):
        super().__init__()
        self.setWindowTitle(tr("exporter.progress_title"))
        self.setFixedSize(450, 400)
        layout = QVBoxLayout(self)
        self.master_bar = QProgressBar()
        layout.addWidget(QLabel(tr("exporter.total_progress_label")))
        layout.addWidget(self.master_bar)
        self.scroll = QScrollArea()
        self.scroll.setObjectName("ExportScrollArea")
        self.scroll.setWidgetResizable(True)
        self.scroll_content = QWidget()
        self.scroll_layout = QVBoxLayout(self.scroll_content)
        self.game_bars = {}
        for game in selected_games:
            g_layout = QVBoxLayout()
            g_layout.addWidget(QLabel(tr("exporter.game_label", name=game['name'])))
            bar = QProgressBar()
            g_layout.addWidget(bar)
            self.scroll_layout.addLayout(g_layout)
            self.game_bars[game['name']] = bar
        self.scroll_layout.addStretch()
        self.scroll.setWidget(self.scroll_content)
        layout.addWidget(self.scroll)
        self.worker = PackerWorker(selected_games, output_path, master_name, include_json)
        self.worker.progress.connect(self.update_ui)
        self.worker.finished.connect(self.close)
        self.worker.start()

    def update_ui(self, total_p, text, game_idx, game_p):
        self.master_bar.setValue(total_p)
        if game_idx >= 0:
            name = list(self.game_bars.keys())[game_idx]
            self.game_bars[name].setValue(game_p)

if __name__ == "__main__":
    app = QApplication(sys.argv)
    app.setWindowIcon(QIcon(os.path.join(os.path.dirname(os.path.abspath(__file__)), "favicon.ico")))
    apply_global_style(app)
    window = PackerGUI()
    window.show()
    sys.exit(app.exec())