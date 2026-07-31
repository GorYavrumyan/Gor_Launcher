import sys
import subprocess
from PyQt6.QtWidgets import QApplication, QWidget, QVBoxLayout, QPushButton, QLabel
from PyQt6.QtCore import Qt

class GOROverlay(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowFlags(Qt.WindowType.WindowStaysOnTopHint | Qt.WindowType.FramelessWindowHint | Qt.WindowType.Tool)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setStyleSheet("""
            QWidget { background-color: rgba(20, 20, 20, 200); border: 1px solid #007acc; border-radius: 10px; }
            QPushButton { color: white; background: #333; border: none; padding: 5px; border-radius: 5px; }
            QPushButton:hover { background: #007acc; }
            QLabel { color: #007acc; font-weight: bold; }
        """)
        
        layout = QVBoxLayout(self)
        layout.addWidget(QLabel("GOR-OVERLAY"))
        
        btn_editor = QPushButton("🚀 GOR-Editor")
        btn_editor.clicked.connect(lambda: subprocess.Popen([sys.executable, "GOR-Editor.py"]))
        
        btn_close = QPushButton("❌ Close")
        btn_close.clicked.connect(self.close)
        
        layout.addWidget(btn_editor)
        layout.addWidget(btn_close)
        
        self.setGeometry(100, 100, 150, 150)

if __name__ == "__main__":
    app = QApplication(sys.argv)
    overlay = GOROverlay()
    overlay.show()
    sys.exit(app.exec())