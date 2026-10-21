"""
api.addons - аддоны общаются друг с другом.

    api.expose("get_total", lambda: 42)                 # открыть функцию для других аддонов
    api.call("stats_addon.get_total")                    # вызвать функцию другого аддона
    api.addons.list();  api.addons.info("stats_addon");  api.addons.api_of("stats_addon")
    api.addons.when_loaded("stats_addon", lambda: ...)   # дождаться, пока другой аддон загрузится
    api.addons.reload("stats_addon")
"""

_exposed = {}   # "addon_id.name" -> fn


class AddonsAPI:
    def __init__(self, api):
        self._api = api

    @property
    def _mgr(self):
        from .loader import manager
        return manager

    def list(self, include_builtin=True):
        return [k for k in self._mgr.list() if include_builtin or not k.startswith("builtin_")]

    def is_loaded(self, addon_id):
        return addon_id in self._mgr.loaded

    def get(self, addon_id):
        return self._mgr.get(addon_id)

    def api_of(self, addon_id):
        """AddonAPI другого аддона (или None)."""
        item = self._mgr.get(addon_id)
        return item.api if item else None

    def instance(self, addon_id):
        item = self._mgr.get(addon_id)
        return item.instance if item else None

    def module(self, addon_id):
        item = self._mgr.get(addon_id)
        return item.module if item else None

    def info(self, addon_id):
        item = self._mgr.get(addon_id)
        if not item:
            return None
        c = item.config
        return {"id": addon_id, "name": c.get("name", addon_id), "version": c.get("version"),
                "author": c.get("author"), "description": c.get("description"),
                "style": item.style, "builtin": bool(c.get("builtin")), "path": item.path}

    def reload(self, addon_id):
        return self._mgr.reload(addon_id)

    def unload(self, addon_id):
        return self._mgr.unload(addon_id)

    def when_loaded(self, addon_id, callback):
        """Вызвать callback, когда аддон загружен (сразу, если уже загружен)."""
        if self.is_loaded(addon_id):
            self._api._safe(callback)()
            return
        from .events import Events
        def on_loaded(folder):
            if folder == addon_id:
                self._api._safe(callback)()
        self._api.on(Events.ADDON_LOADED, on_loaded)

    # ---- функции-сервисы ----
    def expose(self, name, fn):
        full = f"{self._api.id}.{name}"
        _exposed[full] = fn
        self._api._resources.add(lambda: _exposed.pop(full, None))
        return full

    def call(self, full_name, *args, **kwargs):
        fn = _exposed.get(full_name)
        if fn is None:
            raise KeyError(f"Сервис '{full_name}' не найден (аддон не загружен или не открыл функцию)")
        return fn(*args, **kwargs)

    def exposed(self):
        return sorted(_exposed)
