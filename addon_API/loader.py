"""
Загрузчик аддонов.

Понимает ДВА стиля аддонов - выбирать можно любой:

1. Классический (как раньше):
       def init_addon(launcher): ...

2. Классический + api:
       def init_addon(launcher, api): ...

3. Новый (класс):
       from addon_API import AddonBase
       class Addon(AddonBase):
           def on_load(self, api): ...
           def on_unload(self): ...

В config.json аддона можно указать "min_api": 1 - минимальную версию API.
Для выгрузки классического аддона можно определить shutdown_addon().
"""

import os
import sys
import html
import inspect
import importlib.util
import json
import traceback

from . import API_VERSION
from .api import AddonAPI
from .events import emit_event, Events

_PKG_DIR = os.path.dirname(os.path.abspath(__file__))


def _log(addon_path, msg_type, message):
    try:
        from addon_logger import log_activity_for_addon
        log_activity_for_addon(addon_path, msg_type, message)
    except Exception:
        print(f"[addon_API] {message}")


class LoadedAddon:
    def __init__(self, folder, path, config, module, instance, api, style):
        self.folder, self.path, self.config = folder, path, config
        self.module, self.instance, self.api, self.style = module, instance, api, style


class AddonManager:
    def __init__(self):
        self.launcher = None
        self.loaded = {}   # folder -> LoadedAddon

    # ------------------------------ загрузка ------------------------------ #
    def load(self, launcher, addon_path, config=None, script=None, folder=None):
        """Загружает один аддон. Возвращает True/False. Никогда не бросает исключений."""
        self.launcher = launcher
        folder = folder or os.path.basename(addon_path)
        if folder in self.loaded:
            return True

        if config is None:
            try:
                with open(os.path.join(addon_path, "config.json"), "r", encoding="utf-8") as f:
                    config = json.load(f)
            except Exception as e:
                _log(addon_path, "error", f"Не удалось прочитать config.json: {e}")
                return False

        min_api = config.get("min_api")
        if isinstance(min_api, int) and min_api > API_VERSION:
            _log(addon_path, "error",
                 f"Аддону нужен API версии {min_api}, а установлен {API_VERSION}")
            return False

        if script is None:
            start = config.get("start_file")
            if not start:
                _log(addon_path, "error", "В config.json не указан start_file")
                return False
            script = os.path.join(addon_path, "core", start)
        if not os.path.exists(script):
            _log(addon_path, "error", f"Файл {os.path.basename(script)} не найден")
            return False

        api = AddonAPI(launcher, addon_path, config, folder)
        try:
            _log(addon_path, "info", f"Загрузка модуля: {os.path.basename(script)}")
            mod_name = f"addon_module_{folder}"
            spec = importlib.util.spec_from_file_location(mod_name, script)
            module = importlib.util.module_from_spec(spec)
            sys.modules[mod_name] = module
            spec.loader.exec_module(module)

            instance, style = self._start(module, launcher, api)
            self.loaded[folder] = LoadedAddon(folder, addon_path, config, module, instance, api, style)
            _log(addon_path, "info", f"Аддон успешно запущен ({style})")
            emit_event(Events.ADDON_LOADED, folder)
            return True
        except (Exception, SystemExit) as e:
            # SystemExit тоже: аддон, вызвавший sys.exit() при старте, не должен
            # закрывать весь лаунчер (метод обещает "никогда не бросает исключений").
            traceback.print_exc()
            _log(addon_path, "error", f"Ошибка запуска: {e}")
            api._cleanup()
            sys.modules.pop(f"addon_module_{folder}", None)
            return False

    @staticmethod
    def _start(module, launcher, api):
        instance = getattr(module, "ADDON", None)
        cls = getattr(module, "Addon", None)
        if instance is None and isinstance(cls, type):
            instance = cls()
        if instance is not None and hasattr(instance, "on_load"):
            instance.api = api
            instance.on_load(api)
            return instance, "класс Addon"

        init = getattr(module, "init_addon", None)
        if init is None:
            raise RuntimeError("В аддоне нет ни класса Addon, ни функции init_addon")
        try:
            params = [p for p in inspect.signature(init).parameters.values()
                      if p.kind in (p.POSITIONAL_ONLY, p.POSITIONAL_OR_KEYWORD)]
            wants_api = len(params) >= 2
        except (TypeError, ValueError):
            wants_api = False
        if wants_api:
            init(launcher, api)
            return None, "init_addon(launcher, api)"
        init(launcher)
        return None, "классический init_addon"

    # ------------------------------ выгрузка ------------------------------ #
    def unload(self, folder):
        item = self.loaded.pop(folder, None)
        if item is None:
            return False
        try:
            if item.instance is not None and hasattr(item.instance, "on_unload"):
                item.instance.on_unload()
            elif hasattr(item.module, "shutdown_addon"):
                item.module.shutdown_addon()
        except Exception as e:
            traceback.print_exc()
            _log(item.path, "error", f"Ошибка при выгрузке: {e}")
        item.api._cleanup()
        sys.modules.pop(f"addon_module_{folder}", None)
        _log(item.path, "info", "Аддон выгружен")
        emit_event(Events.ADDON_UNLOADED, folder)
        return True

    def reload(self, folder):
        item = self.loaded.get(folder)
        if item is None:
            return False
        launcher, path, config = self.launcher, item.path, None
        script = None
        if item.api.root.startswith(_PKG_DIR):          # встроенный аддон
            script = getattr(item.module, "__file__", None)
            config = item.config
        self.unload(folder)
        return self.load(launcher, path, config, script=script, folder=folder)

    def get(self, folder):
        return self.loaded.get(folder)

    def list(self):
        return list(self.loaded)

    # ------------------------------ встроенные ---------------------------- #
    def load_builtin(self, launcher):
        """Встроенные аддоны самого API (например, Theme Studio) - написаны
        через тот же публичный API, что и обычные аддоны."""
        bdir = os.path.join(_PKG_DIR, "builtin")
        if not os.path.isdir(bdir):
            return
        for fname in sorted(os.listdir(bdir)):
            if fname.startswith("_") or not fname.endswith(".py"):
                continue
            stem = fname[:-3]
            data_root = os.path.join(bdir, "_data", stem)
            os.makedirs(data_root, exist_ok=True)
            config = {"name": stem.replace("_", " ").title(), "version": "1.0", "builtin": True}
            self.load(launcher, data_root, config, script=os.path.join(bdir, fname),
                      folder=f"builtin_{stem}")


manager = AddonManager()


# --------------------------------------------------------------------- #
# Заглушка web/index.html, чтобы аддон без веб-страницы был виден в
# Control Center (он показывает только аддоны, у которых есть web/index.html)
# --------------------------------------------------------------------- #
_STUB = """<!DOCTYPE html>
<html lang="ru"><head><meta charset="utf-8"><title>{name}</title>
<style>
body{{margin:0;padding:32px;background:#0a0a0a;color:#f0f0f0;font-family:Segoe UI,Arial,sans-serif}}
h1{{margin:0 0 4px;font-size:26px}} .meta{{color:#888;margin-bottom:20px}}
.card{{background:#1a1a1a;border:1px solid #333;border-radius:12px;padding:18px;line-height:1.5}}
</style></head><body>
<h1>{name}</h1>
<div class="meta">{meta}</div>
<div class="card">{desc}</div>
</body></html>
"""


def prepare_addon_folder(addon_path, config):
    """Создаёт web/index.html, если его нет. Вызывается для ВСЕХ аддонов
    (в том числе выключенных), чтобы их можно было включить в Control Center."""
    web_dir = os.path.join(addon_path, "web")
    index = os.path.join(web_dir, "index.html")
    if os.path.exists(index):
        return
    try:
        os.makedirs(web_dir, exist_ok=True)
        meta = " · ".join(x for x in (
            f"v{config['version']}" if config.get("version") else "",
            config.get("author", "")) if x)
        with open(index, "w", encoding="utf-8") as f:
            f.write(_STUB.format(
                name=html.escape(str(config.get("name", os.path.basename(addon_path)))),
                meta=html.escape(meta),
                desc=html.escape(str(config.get("description", "Описание не указано.")))))
    except Exception as e:
        print(f"[addon_API] Не удалось создать web/index.html: {e}")
