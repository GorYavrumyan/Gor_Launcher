import json
import math
import random
from PyQt6.QtCore import QPointF, QRectF, Qt, QTimer, QUrl
from PyQt6.QtGui import QBrush, QColor, QPainter, QPen, QPixmap, QFont
from PyQt6.QtWidgets import (
    QApplication,
    QDialog,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

# QSoundEffect живёт в отдельном модуле QtMultimedia, который не всегда
# установлен вместе с PyQt6. Импортируем его безопасно, чтобы отсутствие
# пакета PyQt6-Qt6/multimedia-плагинов не роняло всё приложение.
try:
    from PyQt6.QtMultimedia import QSoundEffect
    HAS_SOUND = True
except ImportError:
    QSoundEffect = None
    HAS_SOUND = False


class FortuneWheelDialog(QDialog):

    def __init__(self, parent=None, json_path="games_data.json", launch_callback=None):
        super().__init__(parent)
        self.setWindowTitle("Случайная игра — Колесо Фортуны")
        self.resize(600, 650)
        self.setMinimumSize(420, 500)
        self.setStyleSheet(
            "background-color: #1e1e1e; color: white; font-family: Arial;"
        )

        self.json_path = json_path
        self.launch_callback = launch_callback  # Ссылка на функцию запуска игры из вашего лаунчера
        self.load_error = None
        
        # Сразу загружаем игры при инициализации
        self.games = self.load_games()

        self.current_angle = 0.0
        self.target_angle = 0.0
        self.spinning = False
        self.speed = 0.0

        self.init_ui()
        self.init_sounds()

    def load_games(self):
        """Собирает единый список игр из games_data.json.

        Реальная структура файла:
            {
                "groups": {"1": [game, ...], "2": [game, ...], ...},
                "standalone": [game, ...],
                "history": [...],
                "addons_list": [...]
            }
        Для колеса фортуны берём все игры из groups (все подсписки)
        и из standalone, объединяя их в один плоский список.
        Дедуплицируем по "id", если он есть, чтобы одна и та же игра
        не попала в колесо дважды (например если её id повторяется).
        """
        import os

        candidate_paths = [self.json_path]
        if not os.path.isabs(self.json_path):
            # Если относительный путь не найден от текущей рабочей директории
            # (частый случай при запуске из отладчика/лаунчера с другим cwd),
            # пробуем найти файл рядом с этим скриптом.
            script_dir = os.path.dirname(os.path.abspath(__file__))
            candidate_paths.append(os.path.join(script_dir, self.json_path))

        actual_path = None
        for p in candidate_paths:
            if os.path.isfile(p):
                actual_path = p
                break

        if actual_path is None:
            self.load_error = (
                f"Файл не найден.\nПробовал:\n" + "\n".join(candidate_paths)
            )
            print(f"Ошибка загрузки игр: {self.load_error}")
            return []

        try:
            with open(actual_path, "r", encoding="utf-8") as f:
                data = json.load(f)
        except Exception as e:
            self.load_error = f"{type(e).__name__}: {e}\nПуть: {actual_path}"
            print(f"Ошибка загрузки игр: {self.load_error}")
            return []

        # Поддержка старого формата (просто список) — на всякий случай
        if isinstance(data, list):
            return data

        all_games = []
        seen_ids = set()

        def add_game(game):
            if not isinstance(game, dict):
                return
            game_id = game.get("id")
            if game_id is not None:
                if game_id in seen_ids:
                    return
                seen_ids.add(game_id)
            all_games.append(game)

        groups = data.get("groups", {})
        if isinstance(groups, dict):
            for group_games in groups.values():
                if isinstance(group_games, list):
                    for game in group_games:
                        add_game(game)

        standalone = data.get("standalone", [])
        if isinstance(standalone, list):
            for game in standalone:
                add_game(game)

        return all_games

    def init_ui(self):
        layout = QVBoxLayout(self)

        # Заголовок
        self.title_label = QLabel("Во что сыграть сегодня?")
        self.title_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.title_label.setStyleSheet("font-size: 22px; font-weight: bold; margin: 10px;")
        layout.addWidget(self.title_label)

        # Иконка выбранной игры (появляется после остановки колеса)
        self.result_icon_label = QLabel(self)
        self.result_icon_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.result_icon_label.setFixedHeight(64)
        layout.addWidget(self.result_icon_label)

        # Область для колеса — растягивается вместе с окном
        self.wheel_widget = WheelWidget(self)
        self.wheel_widget.setMinimumSize(300, 300)
        self.wheel_widget.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding
        )
        layout.addWidget(self.wheel_widget, 1)

        # Кнопка вращения
        self.spin_btn = QPushButton("КРУТИТЬ КОЛЕСО!", self)
        self.spin_btn.setStyleSheet("""
            QPushButton {
                background-color: #ffaa00; color: #1e1e1e; font-size: 16px; 
                font-weight: bold; border-radius: 10px; padding: 12px;
            }
            QPushButton:hover { background-color: #ffbb33; }
            QPushButton:pressed { background-color: #cc8800; }
        """)
        self.spin_btn.clicked.connect(self.start_spinning)
        layout.addWidget(self.spin_btn)

        # Кнопка «Играть» (скрыта до остановки колеса)
        self.play_btn = QPushButton("ИГРАТЬ В ВЫБРАННУЮ ИГРУ", self)
        self.play_btn.setStyleSheet("""
            QPushButton {
                background-color: #2ecc71; color: white; font-size: 16px; 
                font-weight: bold; border-radius: 10px; padding: 12px;
            }
            QPushButton:hover { background-color: #27ae60; }
        """)
        self.play_btn.hide()
        self.play_btn.clicked.connect(self.launch_selected_game)
        layout.addWidget(self.play_btn)

        self.selected_game = None

        if not self.games:
            if self.load_error:
                self.title_label.setText(f"Ошибка загрузки:\n{self.load_error}")
            else:
                self.title_label.setText(
                    "games_data.json загружен, но список игр пуст\n"
                    "(нет ни одной записи в groups/standalone)"
                )
            self.title_label.setStyleSheet("font-size: 14px; font-weight: bold; margin: 10px; color: #ff6666;")
            self.spin_btn.setEnabled(False)

    def init_sounds(self):
        # Опционально: звук тиков при вращении и победный звук.
        # Если QtMultimedia недоступен, просто отключаем звук.
        if HAS_SOUND:
            self.tick_sound = QSoundEffect()
            # self.tick_sound.setSource(QUrl.fromLocalFile("tick.wav"))
        else:
            self.tick_sound = None

    def start_spinning(self):
        # Каждый раз заново перечитываем файл с диска, чтобы подхватить актуальный список игр
        self.games = self.load_games()
        if self.wheel_widget:
            self.wheel_widget.clear_cache()
            self.wheel_widget.update()

        if self.spinning or not self.games:
            if not self.games:
                self.title_label.setText("Список игр пуст! Нечего крутить.")
                self.title_label.setStyleSheet("font-size: 14px; font-weight: bold; margin: 10px; color: #ff6666;")
            return

        self.play_btn.hide()
        self.result_icon_label.clear()
        self.title_label.setText("Во что сыграть сегодня?")
        self.title_label.setStyleSheet("font-size: 22px; font-weight: bold; margin: 10px;")
        
        self.spinning = True
        self.spin_btn.setEnabled(False)

        # Выбираем случайную победную игру заранее
        self.winning_index = random.randint(0, len(self.games) - 1)

        # Расчет углов: делаем от 5 до 8 полных оборотов + точный доворот до сектора
        num_segments = len(self.games)
        segment_angle = 360 / num_segments

        # Угол центра выигрышного сегмента
        target_segment_middle = self.winning_index * segment_angle + (segment_angle / 2)

        # Итоговый угол поворота (стрелка сверху, на 270 градусов по математическому кругу)
        extra_spins = random.randint(5, 8) * 360
        self.target_angle = (
            self.current_angle
            + extra_spins
            + (270 - target_segment_middle - self.current_angle) % 360
        )

        self.speed = 25.0  # начальная скорость анимации

        # Таймер анимации кадра (~60 FPS)
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.update_wheel_animation)
        self.timer.start(16)

    def update_wheel_animation(self):
        # Плавное замедление (эйзинг)
        diff = self.target_angle - self.current_angle
        if diff < 0.5:
            self.current_angle = self.target_angle
            self.wheel_widget.set_angle(self.current_angle)
            self.timer.stop()
            self.spinning = False
            self.spin_btn.setEnabled(True)
            self.on_spin_finished()
            return

        self.speed = max(0.5, diff * 0.08)
        self.current_angle += self.speed
        self.wheel_widget.set_angle(self.current_angle)

    def on_spin_finished(self):
        self.selected_game = self.games[self.winning_index]
        self.title_label.setText(f"Выпало: {self.selected_game.get('name', 'Игра')}!")

        icon_path = self.selected_game.get("icon")
        pixmap = QPixmap(icon_path) if icon_path else QPixmap()
        if not pixmap.isNull():
            scaled = pixmap.scaled(
                64, 64,
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation,
            )
            self.result_icon_label.setPixmap(scaled)
        else:
            self.result_icon_label.clear()

        self.play_btn.show()

    def launch_selected_game(self):
        if self.selected_game and self.launch_callback:
            # Вызываем штатный метод запуска лаунчера, передавая всю информацию об игре
            self.launch_callback(self.selected_game)
            self.close()


class WheelWidget(QWidget):
    """Вспомогательный виджет для отрисовки кастомного колеса фортуны"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.angle = 0.0
        self._icon_cache = {}  # (путь, размер) -> QPixmap | None, чтобы не грузить файл на каждый кадр

    def clear_cache(self):
        """Очищает кэш иконок при обновлении списка игр"""
        self._icon_cache.clear()

    def _load_icon(self, path, size):
        """Загружает и масштабирует иконку игры, с кэшированием по (путь, размер)."""
        if not path:
            return None
        key = (path, size)
        if key in self._icon_cache:
            return self._icon_cache[key]

        pixmap = QPixmap(path)
        if pixmap.isNull():
            self._icon_cache[key] = None
            return None

        scaled = pixmap.scaled(
            size, size,
            Qt.AspectRatioMode.KeepAspectRatio,
            Qt.TransformationMode.SmoothTransformation,
        )
        self._icon_cache[key] = scaled
        return scaled

    def set_angle(self, angle):
        self.angle = angle
        self.update()

    def paintEvent(self, event):
        parent = self.parent()
        games = getattr(parent, "games", [])
        if not games:
            return

        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setRenderHint(QPainter.RenderHint.TextAntialiasing)

        width = self.width()
        height = self.height()
        side = min(width, height) - 40

        # Центр колеса
        center = QPointF(width / 2.0, height / 2.0)
        rect = QRectF(center.x() - side / 2, center.y() - side / 2, side, side)

        num_segments = len(games)
        angle_step = 360.0 / num_segments

        colors = [
            QColor("#e74c3c"), QColor("#3498db"), QColor("#2ecc71"),
            QColor("#f1c40f"), QColor("#9b59b6"), QColor("#e67e22")
        ]

        radius = side / 2.0

        # Увеличенный размер иконки и сдвиг к самому краю колеса
        icon_size = int(max(40, min(140, radius * 0.7, angle_step * 4.0)))
        icon_radius = radius * 0.72  # смещено ближе к краю колеса

        # --- Шаг 1: Поворачиваем холст и рисуем секторы колеса ---
        painter.save()
        painter.translate(center)
        painter.rotate(self.angle)
        painter.translate(-center)

        for i in range(num_segments):
            brush = QBrush(colors[i % len(colors)])
            painter.setBrush(brush)
            painter.setPen(QPen(QColor("#1e1e1e"), 2))

            # Сам сектор рисуется через startAngle/spanAngle
            painter.drawPie(rect, int(i * angle_step * 16), int(angle_step * 16))

        painter.restore()

        # --- Шаг 2: Рисуем только иконки по краям колеса без вращения и без названий ---
        for i in range(num_segments):
            current_segment_angle = self.angle + (i + 0.5) * angle_step
            rad = math.radians(current_segment_angle)

            # Вычисляем текущие экранные координаты центра иконки у края колеса
            pos_x = center.x() + icon_radius * math.cos(rad)
            pos_y = center.y() + icon_radius * math.sin(rad)

            icon_path = games[i].get("icon")
            icon_pixmap = self._load_icon(icon_path, icon_size)

            if icon_pixmap is not None:
                # Отрисовка крупной иконки без поворота самого изображения (всегда вертикально)
                painter.drawPixmap(
                    int(pos_x - icon_pixmap.width() / 2),
                    int(pos_y - icon_pixmap.height() / 2),
                    icon_pixmap,
                )

        # Рисуем указатель (стрелочку сверху) — рисуется уже без поворота холста,
        # он всегда должен смотреть строго вверх
        painter.setBrush(QBrush(QColor("#ffffff")))
        painter.setPen(QPen(QColor("#000000"), 1))
        pointer = [
            QPointF(center.x() - 10, rect.top() - 15),
            QPointF(center.x() + 10, rect.top() - 15),
            QPointF(center.x(), rect.top() + 5)
        ]
        painter.drawPolygon(pointer)


if __name__ == "__main__":
    import sys

    app = QApplication(sys.argv)
    dlg = FortuneWheelDialog()
    dlg.show()
    sys.exit(app.exec())