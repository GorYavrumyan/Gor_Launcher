const docsData = [
    {
        id: "arch-sec",
        icon: "fa-sitemap",
        color: "#a855f7",
        title: "1. Глубокая Архитектура Ядра (PyQt6 & QtWebEngine)",
        desc: "GOR Launcher базируется на асинхронной гибридной архитектуре, сочетающей легковесную графическую оболочку Chromium DOM и изолированное Python-ядро. Оболочка реализует концепцию сплит-процессов: графический интерфейс отрисовывается через аппаратно-ускоренный рендерер PyQt6.QtWebEngineCore, в то время как системные операции (управление фоновыми процессами, низкоуровневая работа с реестром, сетевой мониторинг и управление файловыми потоками) исполняются в отдельной среде Python 3.11+. Данная структура полностью исключает зависание пользовательского интерфейса (UI Freeze) при тяжелых дисковых или сетевых операциях.",
        code: `GOR_Launcher/
├── main.py                          # Точка входа: инициализация QApplication, разбор аргументов CLI
├── core/
│   ├── __init__.py                  # Пакет инициализации системных сервисов
│   ├── browser_engine.py            # Менеджер окон QWebEnginePage, настройки профиля QWebEngineProfile
│   ├── bridge.py                    # Двунаправленный IPC-мост QWebChannel (Python <-> JS Engine)
│   ├── process_manager.py           # Модуль изоляции процессов, контроля поддеревьев PID и лимитов RAM
│   ├── game_scanner.py              # Автоматический парсер библиотек Steam, Epic Games, GOG и кастомных директорий
│   ├── network_manager.py           # Менеджер асинхронной загрузки дистрибутивов и обновлений
│   └── GOR_Profile/                 # Сессионные данные Chromium
│       ├── Local Storage/           # Кэш пользовательских настроек и состояний интерфейса
│       ├── Cookies/                 # Зашифрованные сессионные куки авторизации
│       └── GPUCache/                # Шейдерный кэш для ускорения отрисовки DOM
├── addons/                          # Модульная система расширений
│   ├── __init__.py                  # Динамический загрузчик аддонов (Plugin Loader)
│   ├── calculator/                  # Аддон CalculatorTab (PyQt6 QWidget с интеграцией NumPy)
│   │   ├── __init__.py
│   │   └── calc_tab.py              # Реализация интерфейса и математического движка
│   └── sys_monitor/                 # Аддон мониторинга аппаратных ресурсов CPU/GPU/RAM/NVMe
│       ├── __init__.py
│       └── monitor_widget.py        # Графики ресурсов в реальном времени
└── config/
    ├── launcher_config.json         # Глобальные конфигурации окна, движка WebEngine и флагов GPU
    ├── games_database.json          # База данных установленных игр, путей запуска и аргументов CLI
    └── streaming_hosts.json         # Сопряженные Sunshine / Moonlight узлы и токены авторизации`
    },
    {
        id: "ipc-sec",
        icon: "fa-network-wired",
        color: "#6366f1",
        title: "2. Межпроцессное Взаимодействие и IPC Движок (QWebChannel)",
        desc: "Передача сигналов между JS-интерфейсом (Chromium) и Python-бэкендом осуществляется через высокоскоростной протокол QWebChannel. Все методы Python, доступные для вызова из JavaScript, должны быть помечены декоратором @pyqtSlot с явным указанием типов аргументов и возвращаемого значения. Передача данных оптимизирована: вместо тяжелой серии асинхронных HTTP-запросов используется прямой бинарный WebSocket/IPC канал, что снижает задержку отклика до sub-millisecond значений.",
        code: `// ==========================================
// БЭКЕНД НА PYTHON (core/bridge.py)
// ==========================================
import sys
import psutil
from PyQt6.QtCore import QObject, pyqtSlot, pyqtSignal

class LauncherBridge(QObject):
    # Сигналы для асинхронного информирования фронтенда
    gameStatusChanged = pyqtSignal(str, str) # (game_id, status)
    resourceUpdate = pyqtSignal(dict)        # ({cpu: 12.5, ram: 45.2})

    def __init__(self, process_mgr):
        super().__init__()
        self.proc_mgr = process_mgr

    @pyqtSlot(str, result=str)
    def launch_game(self, game_id):
        """ Запуск игры по ID с передачей статуса в JS """
        try:
            pid = self.proc_mgr.start_game(game_id)
            self.gameStatusChanged.emit(game_id, "RUNNING")
            return f"{{\\"status\\": \\"SUCCESS\\", \\"pid\\": {pid}}}"
        except Exception as e:
            return f"{{\\"status\\": \\"ERROR\\", \\"message\\": \\"{str(e)}\\"}}"

    @pyqtSlot(result=str)
    def get_system_stats(self):
        """ Получение показателей загрузки системы """
        stats = {
            "cpu_usage": psutil.cpu_percent(interval=None),
            "ram_usage": psutil.virtual_memory().percent
        }
        return str(stats)

// ==========================================
// ФРОНТЕНД НА JAVASCRIPT (assets/js/app.js)
// ==========================================
document.addEventListener("DOMContentLoaded", () => {
    new QWebChannel(qt.webChannelTransport, function(channel) {
        window.bridge = channel.objects.bridge;

        // Подписка на событие изменения статуса игры
        window.bridge.gameStatusChanged.connect((gameId, status) => {
            console.log(\`[GOR IPC] Игра \${gameId} изменила статус на: \${status}\`);
            updateGameUI(gameId, status);
        });

        // Запуск игры по клику
        const launchBtn = document.getElementById("btn-launch-portal");
        if (launchBtn) {
            launchBtn.addEventListener("click", () => {
                window.bridge.launch_game("portal_2", function(response) {
                    const res = JSON.parse(response);
                    if (res.status === "SUCCESS") {
                        showToast(\`Игра запущена! PID: \${res.pid}\`);
                    } else {
                        showToast(\`Ошибка запуска: \${res.message}\`, "error");
                    }
                });
            });
        }
    });
});`
    },
    {
        id: "install-sec",
        icon: "fa-terminal",
        color: "#ec4899",
        title: "3. Развертывание, Виртуальное Окружение и Сборка",
        desc: "Для работы GOR Launcher требуется изолированное виртуальное окружение. Это предотвращает конфликты системных библиотек C++ (Qt6) и обеспечивают портативность лаунчера. Поддерживается прямая сборка в бинарные дистрибутивы через PyInstaller или Nuitka для систем Windows 10/11 и различных дистрибутивов Linux (Debian, Ubuntu, Arch Linux, Fedora).",
        code: `# ==========================================
# РАЗВЕРТЫВАНИЕ НА LINUX (Debian / Ubuntu / Arch)
# ==========================================
# 1. Установка системных зависимостей Qt6 и системных графических библиотек
sudo apt update && sudo apt install -y \\
    python3-full python3-pip python3-venv \\
    libxcb-cursor0 libxcb-xinerama0 libqt6webenginecore6 \\
    libgl1-mesa-glx libegl1-mesa

# 2. Создание и активация виртуального окружения
python3 -m venv venv
source venv/bin/activate

# 3. Обновление pip и установка Python-пакетов
pip install --upgrade pip
pip install PyQt6 PyQt6-WebEngine psutil pyyaml requests

# 4. Тестовый запуск
python3 main.py

# ==========================================
# РАЗВЕРТЫВАНИЕ НА WINDOWS (PowerShell)
# ==========================================
# 1. Создание виртуального окружения
python -m venv venv
.\\venv\\Scripts\\Activate.ps1

# 2. Установка зависимостей
python -m pip install --upgrade pip
pip install PyQt6 PyQt6-WebEngine psutil pywin32 requests

# 3. Сборка автономного .EXE файла через PyInstaller
pip install pyinstaller
pyinstaller --noconfirm --onedir --windowed \\
    --add-data "config;config" \\
    --add-data "addons;addons" \\
    --name "GOR_Launcher" main.py`
    },
    {
        id: "addons-sec",
        icon: "fa-puzzle-piece",
        color: "#3b82f6",
        title: "4. Полное Справочное Руководство API Аддонов",
        desc: "Архитектура GOR Launcher поддерживает горячую подгрузку модулей через встроенный загрузчик. Каждый аддон представляет собой изолят, работающий в собственном пространстве имён. Модули могут добавлять пользовательские графические панели (PyQt6 QWidget), регистрировать JS-методы или запускать демоны фонового мониторинга.",
        table: {
            headers: ["Метод / Event", "Возвращаемый тип", "Описание метода и правила вызова"],
            rows: [
                ["init_addon(core_engine)", "<span class='badge badge-green'>bool</span>", "Главный инициализатор аддона. Принимает ссылку на экземпляр ядра. Возвращает True при успешной загрузке."],
                ["get_tab_name()", "<span class='badge'>str</span>", "Возвращает отображаемое имя вкладки в главном навигационном меню лаунчера."],
                ["get_tab_icon()", "<span class='badge'>str</span>", "Возвращает FontAwesome класс иконки (например: 'fa-calculator')."],
                ["get_widget()", "<span class='badge badge-yellow'>QWidget</span>", "Возвращает скомпилированный экземпляр QWidget для встраивания в центральную стек-панель лаунчера."],
                ["register_js_bridge()", "<span class='badge'>dict</span>", "Позволяет аддону пробросить собственные Python-объекты в глобальный контекст window JavaScript."],
                ["on_unload()", "<span class='badge'>None</span>", "Деструктор аддона. Вызывается при закрытии лаунчера для корректного освобождения ресурсов GPU/CPU и остановки потоков."]
            ]
        }
    },
    {
        id: "addons-gui-sec",
        icon: "fa-window-restore",
        color: "#14b8a6",
        title: "5. Разработка Встраиваемого Аддона (CalculatorTab)",
        desc: "Ниже представлен полноценный исходный код плагина-калькулятора, интегрируемого напрямую в пользовательский интерфейс GOR Launcher как родной компонент PyQt6.",
        code: `# ==========================================
# ИСХОДНЫЙ КОД: addons/calculator/calc_tab.py
# ==========================================
import math
from PyQt6.QtWidgets import (QWidget, QVBoxLayout, QGridLayout, 
                             QLineEdit, QPushButton, QSizePolicy)
from PyQt6.QtCore import Qt

class CalculatorTab(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("CalculatorTab")
        self.init_ui()

    def init_ui(self):
        # Основной вертикальный макет
        self.main_layout = QVBoxLayout(self)
        self.main_layout.setContentsMargins(15, 15, 15, 15)
        self.main_layout.setSpacing(10)

        # Поле ввода/вывода результатов
        self.display = QLineEdit()
        self.display.setFixedHeight(50)
        self.display.setAlignment(Qt.AlignmentFlag.AlignRight)
        self.display.setReadOnly(True)
        self.display.setStyleSheet("""
            QLineEdit {
                background-color: #0d0e12;
                color: #a855f7;
                font-family: 'JetBrains Mono', monospace;
                font-size: 22px;
                border: 1px solid rgba(255, 255, 255, 0.1);
                border-radius: 8px;
                padding: 5px 10px;
            }
        """)
        self.main_layout.addWidget(self.display)

        # Сетка кнопок
        grid_layout = QGridLayout()
        grid_layout.setSpacing(8)

        buttons = [
            ('7', 0, 0), ('8', 0, 1), ('9', 0, 2), ('/', 0, 3),
            ('4', 1, 0), ('5', 1, 1), ('6', 1, 2), ('*', 1, 3),
            ('1', 2, 0), ('2', 2, 1), ('3', 2, 2), ('-', 2, 3),
            ('0', 3, 0), ('.', 3, 1), ('C', 3, 2), ('+', 3, 3),
            ('=', 4, 0, 1, 4)
        ]

        for btn_info in buttons:
            text = btn_info[0]
            row = btn_info[1]
            col = btn_info[2]
            row_span = btn_info[3] if len(btn_info) > 3 else 1
            col_span = btn_info[4] if len(btn_info) > 4 else 1

            btn = QPushButton(text)
            btn.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
            btn.setStyleSheet("""
                QPushButton {
                    background-color: #161820;
                    color: #f1f5f9;
                    font-size: 16px;
                    font-weight: bold;
                    border: 1px solid rgba(255, 255, 255, 0.05);
                    border-radius: 6px;
                    min-height: 45px;
                }
                QPushButton:hover {
                    background-color: #a855f7;
                    color: #ffffff;
                }
            """)
            btn.clicked.connect(lambda checked, t=text: self.on_button_click(t))
            grid_layout.addWidget(btn, row, col, row_span, col_span)

        self.main_layout.addLayout(grid_layout)

    def on_button_click(self, char):
        if char == 'C':
            self.display.clear()
        elif char == '=':
            try:
                expression = self.display.text()
                result = str(eval(expression, {"__builtins__": None}, {"math": math}))
                self.display.setText(result)
            except Exception:
                self.display.setText("Ошибка")
        else:
            self.display.setText(self.display.text() + char)

    def get_tab_name(self):
        return "Калькулятор"

    def get_tab_icon(self):
        return "fa-calculator"`
    },
    {
        id: "game-launch-sec",
        icon: "fa-rocket",
        color: "#f59e0b",
        title: "6. Запуск Игр, Изоляция и Управление Процессами (psutil)",
        desc: "Подсистема управления процессами отвечает за запуск приложений, перехват их вывода, управление приоритетами CPU/GPU, а также за контроль дочерних деревьев процессов. Для исключения зомби-процессов используется интеграция с библиотекой psutil, а потоки ввода-вывода направляются в изолированный лог-файл.",
        code: `# ==========================================
# ИСХОДНЫЙ КОД: core/process_manager.py
# ==========================================
import os
import subprocess
import psutil
import time
from PyQt6.QtCore import QThread, pyqtSignal

class ProcessWatcherThread(QThread):
    processFinished = pyqtSignal(str, int) # (game_id, return_code)

    def __init__(self, game_id, pid):
        super().__init__()
        self.game_id = game_id
        self.pid = pid

    def run(self):
        try:
            proc = psutil.Process(self.pid)
            # Ожидание завершения процесса и всех его дочерних потоков
            while proc.is_running() and proc.status() != psutil.STATUS_ZOMBIE:
                time.sleep(1)
            self.processFinished.emit(self.game_id, 0)
        except psutil.NoSuchProcess:
            self.processFinished.emit(self.game_id, -1)

class ProcessManager:
    def __init__(self, log_dir="logs"):
        self.log_dir = log_dir
        self.active_games = {}
        self.watchers = {}
        if not os.path.exists(log_dir):
            os.makedirs(log_dir)

    def start_game(self, game_id, exec_path, args=[], cwd=None):
        """ Запуск игрового процесса с изоляцией логов и мониторингом """
        if game_id in self.active_games:
            raise RuntimeError(f"Игра {game_id} уже запущена!")

        log_file_path = os.path.join(self.log_dir, f"{game_id}.log")
        log_file = open(log_file_path, "w", encoding="utf-8")

        # Настройка окружения
        env = os.environ.copy()
        env["GOR_LAUNCHER_ACTIVE"] = "1"

        # Непосредственный запуск через subprocess
        process = subprocess.Popen(
            [exec_path] + args,
            stdout=log_file,
            stderr=subprocess.STDOUT,
            cwd=cwd or os.path.dirname(exec_path),
            env=env,
            creationflags=subprocess.CREATE_NEW_PROCESS_GROUP if os.name == 'nt' else 0
        )

        self.active_games[game_id] = {
            "pid": process.pid,
            "process": process,
            "log_file": log_file
        }

        # Запуск потока отслеживания завершения
        watcher = ProcessWatcherThread(game_id, process.pid)
        watcher.processFinished.connect(self._on_game_finished)
        watcher.start()
        self.watchers[game_id] = watcher

        return process.pid

    def _on_game_finished(self, game_id, return_code):
        print(f"[ProcessManager] Игра {game_id} завершена с кодом {return_code}")
        if game_id in self.active_games:
            self.active_games[game_id]["log_file"].close()
            del self.active_games[game_id]
            del self.watchers[game_id]

    def terminate_game(self, game_id):
        """ Принудительное завершение дерева процессов """
        if game_id in self.active_games:
            pid = self.active_games[game_id]["pid"]
            try:
                parent = psutil.Process(pid)
                for child in parent.children(recursive=True):
                    child.kill()
                parent.kill()
            except psutil.NoSuchProcess:
                pass`
    },
    {
        id: "config-sec",
        icon: "fa-gear",
        color: "#06b6d4",
        title: "7. Справочник Конфигураций и Структура Настроек (JSON)",
        desc: "Все глобальные параметры лаунчера хранятся в JSON-формате в файле config/launcher_config.json. Схема конфигурации включает в себя графические параметры QtWebEngine, конфигурацию аудиомаршрутизации, порты удаленной отладки, а также списки узлов стриминга.",
        code: `{
  "application": {
    "name": "GOR Launcher Pro",
    "version": "2.5.0",
    "environment": "production",
    "theme": "dark_modern",
    "language": "ru_RU",
    "check_updates_on_startup": true,
    "close_to_tray": true
  },
  "window": {
    "width": 1280,
    "height": 800,
    "min_width": 1024,
    "min_height": 720,
    "frameless": true,
    "start_maximized": false
  },
  "webengine": {
    "gpu_acceleration": true,
    "enable_webgl": true,
    "remote_debugging_port": 9222,
    "disk_cache_size_mb": 512,
    "user_agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) GORLauncher/2.5.0 Chrome/120.0.0.0 Safari/537.36",
    "flags": [
      "--disable-gpu-compositing",
      "--enable-accelerated-2d-canvas",
      "--ignore-gpu-blocklist"
    ]
  },
  "paths": {
    "games_directory": "C:\\\\Games",
    "screenshots_directory": "C:\\\\Users\\\\Public\\\\Pictures\\\\GOR_Screenshots",
    "logs_directory": "./logs"
  },
  "network": {
    "connection_timeout_ms": 5000,
    "max_concurrent_downloads": 4
  }
}`
    },
    {
        id: "streaming-sec",
        icon: "fa-wifi",
        color: "#10b981",
        title: "8. Remote Streaming (Sunshine & Moonlight)",
        desc: "GOR Launcher интегрирован с экосистемой удаленного стриминга с минимальной задержкой. Серверная часть работает на базе Sunshine (с поддержкой NVENC/VAAPI), а клиентские сессии запускаются через встроенную сборку Moonlight CLI. Это позволяет транслировать игры и рабочие столы с основного ПК на другие устройства в локальной сети или через VPN.",
        code: `# ==========================================
# 1. КОМАНДЫ СОПРЯЖЕНИЯ И ПОДКЛЮЧЕНИЯ (CLI)
# ==========================================

# Сопряжение клиента Moonlight с хостом Sunshine по IP-адресу
# При выполнении команды на экране появится PIN-код для ввода в веб-панели Sunshine
moonlight pair 192.168.1.100

# Отображение списка доступных приложений и игр на хосте
moonlight list 192.168.1.100

# Запуск прямого стриминга игры "GOR Launcher" в режиме 1080p 60fps с битрейтом 25 Mbps
moonlight stream 192.168.1.100 -app "GOR Launcher" -1080 -fps 60 -bitrate 25000

# Запуск стриминга в 4K разрешении с HDR (потребуется поддержка монитором и GPU)
moonlight stream 192.168.1.100 -app "Portal 2" -2160 -fps 60 -bitrate 50000 -hdr

# ==========================================
# 2. ПРИМЕР PYTHON-МОДУЛЯ ИНТЕГРАЦИИ (core/streaming.py)
# ==========================================
import subprocess

class StreamingController:
    def __init__(self, host_ip):
        self.host_ip = host_ip

    def start_stream(self, app_name, resolution="1080", fps="60", bitrate=25000):
        cmd = [
            "moonlight", "stream", self.host_ip,
            "-app", app_name,
            f"-{resolution}",
            "-fps", str(fps),
            "-bitrate", str(bitrate)
        ]
        return subprocess.Popen(cmd)`
    },
    {
        id: "audio-sec",
        icon: "fa-headphones",
        color: "#8b5cf6",
        title: "9. AudioRelay Маршрутизация Аудио и Виртуальные Кабели",
        desc: "Подсистема маршрутизации звука позволяет перенаправлять звуковой поток из выбранных игр и аддонов на внешние мобильные устройства (смартфоны, планшеты) или виртуальные аудиокабели с использованием протоколов AudioRelay и PulseAudio/PipeWire.",
        code: `# ==========================================
# НАСТРОЙКА ВИРТУАЛЬНЫХ АУДИОКАБЕЛЕЙ LINUX (PulseAudio/PipeWire)
# ==========================================

# 1. Создание виртуального изолированного устройства вывода (Null Sink)
pactl load-module module-null-sink sink_name=AudioRelay_Sink sink_properties=device.description="AudioRelay_Virtual_Audio"

# 2. Перенаправление аудиовыхода конкретного процесса (по PID) на виртуальный кабель
# (Используется интерфейс PulseAudio CLI)
pacmd move-sink-input <SINK_INPUT_ID> AudioRelay_Sink

# 3. Запуск сервера трансляции AudioRelay для передачи звука на Android/iOS устройство
audiorelay-headless --server --source=AudioRelay_Sink.monitor --port=59100`
    },
    {
        id: "trouble-sec",
        icon: "fa-bug",
        color: "#ef4444",
        title: "10. Полное Руководство по Диагностике и GPU Ошибкам",
        desc: "Часто при запуске QtWebEngine на устаревших или специфических видеокартах (например, серии NVIDIA GeForce GTX 600/700) возникают проблемы с аппаратно-ускоренным композитингом, сбоями OpenGL контекста или конфликтами системных DLL. Ниже приведены проверенные флаги запуска для решения графических аномалий.",
        code: `# ==========================================
# 1. ЗАПУСК С ФЛАГАМИ ОБХОДА GPU АНОМАЛИЙ
# ==========================================

# Полное отключение GPU-композитинга при черном экране или вылетах Chromium
python main.py --disable-gpu-compositing --disable-gpu-rasterization

# Запуск в режиме программного рендеринга (Software Rendering)
python main.py --disable-gpu --use-gl=swiftshader

# Принудительный запуск через ANGLE DirectX 11 (для Windows)
python main.py --use-angle=d3d11

# ==========================================
# 2. РЕШЕНИЕ КОНФЛИКТОВ С СИСТЕМНЫМИ DLL (Windows)
# ==========================================
# Если лаунчер выдает ошибку "ImportError: DLL load failed while importing QtWebEngineCore":
# 1. Убедитесь, что установлены компоненты Visual C++ Redistributable 2015-2022.
# 2. Сбросьте кэш зарегистрированных DLL через командную строку:
# set PATH=%CD%\\venv\\Lib\\site-packages\\PyQt6\\Qt6\\bin;%PATH%`
    },
    {
        id: "faq-sec",
        icon: "fa-circle-question",
        color: "#eab308",
        title: "11. Полный Базовый FAQ и Ответы на Технические Вопросы",
        desc: "В данном разделе собраны наиболее частые технические вопросы и подробные ответы по настройке, расширению и эксплуатации GOR Launcher.",
        faq: [
            {
                q: "Как открыть отладчик Chromium DevTools в интерфейсе лаунчера?",
                a: "Для активации встроенного отладчика укажите порт удаленной отладки в файле config/launcher_config.json ('remote_debugging_port': 9222). После запуска лаунчера откройте любой внешний браузер (Google Chrome / Brave) и перейдите по адресу http://localhost:9222. Вы получите доступ к полной консоли JavaScript, отладке DOM, просмотру сетевых запросов Network и инспектированию CSS."
            },
            {
                q: "Где хранятся пользовательские сессии, файлы cookie и кэш авторизаций?",
                a: "Все сессионные данные сохраняются локально в директории core/GOR_Profile/. Внутри используются стандартизированные базы данных Chromium LevelDB. Чтобы сбросить авторизацию или очистить кэш полностью, достаточно удалить содержимое этой папки при закрытом лаунчере."
            },
            {
                q: "Как добавить новую игру в каталог лаунчера вручную?",
                a: "Информация об играх считывается из файла config/games_database.json. Добавьте новый объект с уникальным ключом, именем, путем к исполняемому файлу (.exe или бинарнику Linux) и параметрами запуска. Пример:\n{\n  \"portal_2\": {\n    \"title\": \"Portal 2\",\n    \"exec_path\": \"C:\\\\Games\\\\Portal 2\\\\portal2.exe\",\n    \"args\": [\"-novid\", \"-high\"],\n    \"icon\": \"portal2.png\"\n  }\n}"
            },
            {
                q: "Почему главное окно лаунчера застывает (UI Freeze) при запуске тяжелой игры?",
                a: "Это происходит, если процесс запуска выполняется в основном потоке интерфейса (Main UI Thread). В GOR Launcher запуск всех внешних приложений реализован асинхронно с использованием класса QThread и модуля subprocess.Popen, что позволяет GUI сохранять плавнось 60 FPS независимо от нагрузки системы."
            },
            {
                q: "Поддерживает ли лаунчер кастомные темы оформления и CSS-стили?",
                a: "Да, графическая оболочка на 100% кастомизируема. Вы можете изменять стили через CSS3, добавлять свои анимации и переключать темы оформления на лету путем подмены подключенных стилей в HTML-файле."
            },
            {
                q: "Как ограничить выделение оперативной памяти для браузерного движка лаунчера?",
                a: "В файле config/launcher_config.json в блоке 'webengine' настройте параметр 'disk_cache_size_mb' и добавьте флаг '--js-flags=--max_old_space_size=256', что ограничит максимальный размер V8-кэша памяти JavaScript."
            }
        ]
    }
];