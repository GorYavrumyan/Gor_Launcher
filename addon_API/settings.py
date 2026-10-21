"""Настройки аддона: JSON-файл settings.json в папке аддона."""

import os
import json


class AddonSettings:
    def __init__(self, addon_root, defaults=None):
        self._path = os.path.join(addon_root, "settings.json")
        self._defaults = dict(defaults or {})
        self._data = None

    def _load(self):
        if self._data is None:
            try:
                with open(self._path, "r", encoding="utf-8") as f:
                    self._data = json.load(f)
            except Exception:
                self._data = {}
        return self._data

    def _save(self):
        with open(self._path, "w", encoding="utf-8") as f:
            json.dump(self._data, f, ensure_ascii=False, indent=2)

    def get(self, key, default=None):
        data = self._load()
        if key in data:
            return data[key]
        return self._defaults.get(key, default)

    def set(self, key, value):
        self._load()[key] = value
        self._save()

    def all(self):
        merged = dict(self._defaults)
        merged.update(self._load())
        return merged

    def reset(self, key=None):
        """Сбросить одну настройку (key) или все."""
        if key is None:
            self._data = {}
        else:
            self._load().pop(key, None)
        self._save()
