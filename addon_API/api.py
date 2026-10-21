"""
AddonAPI - объект, который получает каждый аддон.

Главное правило: api - это УДОБСТВО, а не ограничение. api.launcher - это
сам объект лаунчера, с полным доступом ко всему.
"""

import os
import threading
import traceback

from .events import bus
from .resources import Resources
from .settings import AddonSettings
from .themes import themes
from .ui import UIAPI
from .design import DesignAPI
from .hooks import hooks


class AddonAPI:
    def __init__(self, launcher, addon_root, config=None, folder=None):
        self.launcher = launcher                  # ПОЛНЫЙ доступ ко всему лаунчеру
        self.root = addon_root                    # папка аддона
        self.config = config or {}
        self.id = folder or os.path.basename(addon_root)
        self.name = self.config.get("name", self.id)
        self.version = self.config.get("version")
        self._resources = Resources()
        self._translations = {}
        self._bridge = None
        self._lazy = {}

        self.settings = AddonSettings(addon_root, self.config.get("settings_defaults"))
        self.themes = themes                      # движок тем (см. themes.py)
        self.ui = UIAPI(self)                     # кастомизация интерфейса (см. ui.py)
        self.design = DesignAPI(self)             # кастомизация ДИЗАЙНА (см. design/)

    # ------------------------------- события ------------------------------ #
    def on(self, event, callback, priority=0):
        """Подписаться на событие. Возвращает подписку для api.off()."""
        sub = bus.subscribe(event, callback, owner=self.root, priority=priority)
        self._resources.add(lambda: bus.unsubscribe(sub))
        return sub

    def once(self, event, callback):
        sub = bus.subscribe(event, callback, owner=self.root, once=True)
        self._resources.add(lambda: bus.unsubscribe(sub))
        return sub

    def off(self, subscription):
        """Снять подписку на событие или перехватчик/фильтр (то, что вернули on/before/filter)."""
        from .hooks import _Hook
        if isinstance(subscription, _Hook):
            hooks.remove(subscription)
        else:
            bus.unsubscribe(subscription)

    def emit(self, event, *args, **kwargs):
        """Выбросить своё событие (его услышат другие аддоны)."""
        bus.emit(event, *args, **kwargs)

    # ------------------------------- таймеры ------------------------------ #
    def _safe(self, fn):
        def run():
            try:
                fn()
            except Exception as e:
                traceback.print_exc()
                self.log(f"Ошибка в таймере: {e}", "error")
        return run

    def every(self, ms, fn):
        """Вызывать fn каждые ms миллисекунд. Возвращает QTimer."""
        from PyQt6.QtCore import QTimer
        t = QTimer(self.launcher)
        t.timeout.connect(self._safe(fn))
        t.start(ms)
        self._resources.add(lambda: (t.stop(), t.deleteLater()))
        return t

    def later(self, ms, fn):
        """Вызвать fn один раз через ms миллисекунд."""
        from PyQt6.QtCore import QTimer
        t = QTimer(self.launcher)
        t.setSingleShot(True)
        t.timeout.connect(self._safe(fn))
        t.start(ms)
        self._resources.add(lambda: (t.stop(), t.deleteLater()))
        return t

    def background(self, fn, on_done=None, on_error=None):
        """Выполнить fn() в отдельном потоке, не вешая интерфейс.
        on_done(результат) и on_error(исключение) вызываются в потоке интерфейса."""
        from PyQt6.QtCore import QObject, pyqtSignal

        if self._bridge is None:
            class _Bridge(QObject):
                finished = pyqtSignal(object, object, object, object)

                def __init__(self):
                    super().__init__()
                    self.finished.connect(self._deliver)

                def _deliver(self, ok_cb, err_cb, result, err):
                    try:
                        if err is not None:
                            (err_cb or (lambda e: traceback.print_exception(e)))(err)
                        elif ok_cb:
                            ok_cb(result)
                    except Exception:
                        traceback.print_exc()
            self._bridge = _Bridge()

        bridge = self._bridge

        def worker():
            try:
                res, err = fn(), None
            except Exception as e:
                res, err = None, e
            bridge.finished.emit(on_done, on_error, res, err)

        threading.Thread(target=worker, daemon=True).start()

    # --------------------------------- лог -------------------------------- #
    def log(self, message, msg_type="info"):
        """Запись в лог аддона (Control Center -> Мониторинг).
        msg_type: info | change | request | error"""
        try:
            from addon_logger import log_activity_for_addon
            log_activity_for_addon(self.root, msg_type, message)
        except Exception:
            print(f"[{self.name}] {message}")

    # ------------------------------ уведомления --------------------------- #
    def toast(self, text, ms=3000):
        return self.ui.toast(text, ms)

    def notify(self, text, title=None):
        """Системное уведомление из трея (если трей доступен)."""
        tray = getattr(self.launcher, "tray_icon", None)
        if tray is not None and tray.supportsMessages():
            from PyQt6.QtWidgets import QSystemTrayIcon
            tray.showMessage(title or self.name, text,
                             QSystemTrayIcon.MessageIcon.Information, 3000)
        else:
            self.toast(text)

    # ---------------------- «рычаги»: ленивые подсистемы ---------------------- #
    def _get(self, name, factory):
        if name not in self._lazy:
            self._lazy[name] = factory()
        return self._lazy[name]

    @property
    def games(self):
        """Управление библиотекой игр (см. games.py). api.games() тоже работает - список игр."""
        from .games import GamesAPI
        return self._get("games", lambda: GamesAPI(self))

    @property
    def db(self):
        """Своя SQLite-база аддона: kv, коллекции документов, обычный SQL (см. storage.py)."""
        def make():
            from .storage import Database
            d = Database(os.path.join(self.data_dir(), "addon.sqlite3"))
            self._resources.add(d.close)
            return d
        return self._get("db", make)

    @property
    def cache(self):
        from .storage import Cache
        return self._get("cache", Cache)

    @property
    def http(self):
        """Сеть без зависаний интерфейса (см. netio.py)."""
        from .netio import HttpAPI
        return self._get("http", lambda: HttpAPI(self))

    @property
    def system(self):
        """ОС: запуск программ, процессы, буфер обмена, экраны (см. system.py)."""
        from .system import SystemAPI
        return self._get("system", lambda: SystemAPI(self))

    @property
    def audio(self):
        """Звук: файлы и синтезированные сигналы (см. audio.py)."""
        from .audio import AudioAPI
        return self._get("audio", lambda: AudioAPI(self))

    @property
    def keys(self):
        """Горячие клавиши (см. keys.py)."""
        from .keys import KeysAPI
        return self._get("keys", lambda: KeysAPI(self))

    @property
    def schedule(self):
        """Расписание и простой (см. schedule.py)."""
        from .schedule import ScheduleAPI
        return self._get("schedule", lambda: ScheduleAPI(self))

    @property
    def commands(self):
        """Реестр команд / палитра Ctrl+K (см. commands.py)."""
        from .commands import CommandsAPI
        return self._get("commands", lambda: CommandsAPI(self))

    @property
    def addons(self):
        """Другие аддоны: список, связь, сервисы (см. services.py)."""
        from .services import AddonsAPI
        return self._get("addons", lambda: AddonsAPI(self))

    @property
    def account(self):
        """Аккаунт лаунчера: язык, предпочтения, список (см. account_api.py)."""
        from .account_api import AccountAPI
        return self._get("account", lambda: AccountAPI(self))

    @property
    def canvas(self):
        """Игровой холст: цикл, ввод, рисование (см. canvas.py)."""
        from .canvas import CanvasAPI
        return self._get("canvas", lambda: CanvasAPI(self))

    # ---- перехватчики: вмешательство в действия лаунчера ----
    def before(self, name, fn, priority=0):
        """Перехватчик действия: fn(...) вернул False - действие отменяется.
        Встроенное: "before_game_launch" (fn(game))."""
        h = hooks.before(name, fn, self.root, priority)
        self._resources.add(lambda: hooks.remove(h))
        return h

    def filter(self, name, fn, priority=0):
        """Фильтр значения: fn(value, ...) -> новое значение.
        Встроенное: "game_launch_args" (fn(args, game))."""
        h = hooks.filter(name, fn, self.root, priority)
        self._resources.add(lambda: hooks.remove(h))
        return h

    def allow(self, name, *args, **kwargs):
        """Спросить у перехватчиков, можно ли действие (для СВОИХ точек)."""
        return hooks.allow(name, *args, **kwargs)

    def apply(self, name, value, *args, **kwargs):
        """Пропустить значение через фильтры (для СВОИХ точек)."""
        return hooks.apply(name, value, *args, **kwargs)

    # ---- сервисы между аддонами ----
    def expose(self, name, fn):
        """Открыть функцию для других аддонов: они вызовут api.call("<id_аддона>.<name>")."""
        return self.addons.expose(name, fn)

    def call(self, full_name, *args, **kwargs):
        return self.addons.call(full_name, *args, **kwargs)

    # --------------------------------- игры ------------------------------- #
    def running_games(self):
        """Сейчас запущенные игры: {id_или_имя: сведения о сессии}."""
        return dict(getattr(self.launcher, "active_sessions", {}) or {})

    @property
    def data(self):
        """Данные лаунчера (games_data.json в памяти)."""
        return self.launcher.games_info

    def save(self):
        """Сохранить данные лаунчера на диск."""
        self.launcher.save_data()

    # --------------------------- файлы и переводы ------------------------- #
    def path(self, *parts):
        """Путь внутри папки аддона."""
        return os.path.join(self.root, *parts)

    def data_dir(self):
        """Папка data/ внутри аддона для его файлов (создаётся сама)."""
        d = os.path.join(self.root, "data")
        os.makedirs(d, exist_ok=True)
        return d

    def add_translations(self, mapping):
        """api.add_translations({"ru": {"hello": "Привет"}, "en": {"hello": "Hi"}})
        потом: api.tr("hello"). Язык берётся из настроек лаунчера."""
        for code, d in mapping.items():
            self._translations.setdefault(code, {}).update(d)

    def tr(self, key, **kwargs):
        """Перевод строки аддона. Порядок поиска: текущий язык лаунчера,
        английский, русский, любой другой. Нет перевода - вернёт key."""
        try:
            import lang_loader
            current = lang_loader.current_language()
        except Exception:
            current = None
        for code in (current, "en", "ru", *self._translations):
            value = self._translations.get(code, {}).get(key)
            if value is not None:
                if kwargs:
                    try:
                        return value.format(**kwargs)
                    except Exception:
                        return value
                return value
        return key

    # ------------------------------ управление ---------------------------- #
    def reload(self):
        """Перезагрузить этот аддон (удобно при разработке)."""
        from .loader import manager
        self.later(0, lambda: manager.reload(self.id))

    def disable(self):
        """Выгрузить этот аддон до перезапуска лаунчера."""
        from .loader import manager
        self.later(0, lambda: manager.unload(self.id))

    def _cleanup(self):
        bus.unsubscribe_owner(self.root)
        self._resources.cleanup()
        themes.remove_snippets_of(self.root)
        themes.clear_runtime_of(self.root)
        hooks.remove_owner(self.root)
