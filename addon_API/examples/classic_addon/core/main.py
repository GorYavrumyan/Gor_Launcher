from PyQt6.QtWidgets import QWidget, QVBoxLayout, QLabel


def init_addon(launcher):
    """Классический стиль: получаем весь лаунчер и делаем с ним что хотим."""
    page = QWidget()
    lay = QVBoxLayout(page)
    lay.addWidget(QLabel("Классический аддон работает!\nИгр в библиотеке: %d"
                         % len(launcher.games_info.get("standalone", []))))
    launcher.tabs.addTab(page, "Классика")
