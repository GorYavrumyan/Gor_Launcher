"""
api.games - полное управление библиотекой игр.

    g = api.games
    g.all(); g.find("hades"); g.search("half"); g.favorites(); g.most_played(5)
    g.add("Моя игра", r"C:\\Games\\my.exe", group="Инди")
    g.update("Моя игра", favorite=True, args="-windowed")
    g.launch("Hades"); g.stop("Hades"); g.launch_random(favorites_only=True)
    g.move("Hades", "Roguelike"); g.remove("Моя игра")

Игра - это словарь из games_data.json: id, name, path, root_path, icon, args,
favorite, playtime_seconds (+ любые свои поля). Ссылаться на игру можно
словарём, id или названием. Все изменения сохраняются на диск и сразу
отображаются в лаунчере; аддонам приходят события game_added/removed/updated/moved,
group_created/removed/renamed.
"""

import os
import uuid
import random

from .events import emit_event, Events


class GamesAPI:
    def __init__(self, api):
        self._api = api
        self.launcher = api.launcher

    def __call__(self):             # обратная совместимость: api.games() -> список
        return self.all()

    # ---------------------------------------------------------- чтение
    @property
    def _info(self):
        return self.launcher.games_info

    def all(self):
        info = self._info
        out = list(info.get("standalone", []))
        for lst in info.get("groups", {}).values():
            out.extend(lst)
        return out

    def groups(self):
        """{название группы: [игры]}"""
        return self._info.get("groups", {})

    def standalone(self):
        return self._info.get("standalone", [])

    def group_names(self):
        return list(self.groups())

    def count(self):
        return len(self.all())

    def _locate(self, ref):
        """-> (game, group_name | None, list) или (None, None, None)"""
        if isinstance(ref, dict):
            gid, name = ref.get("id"), ref.get("name")
        else:
            gid = name = str(ref)
        lists = [(None, self.standalone())] + list(self.groups().items())
        for key in ("id", "name"):
            for gname, lst in lists:
                for g in lst:
                    if key == "id" and gid and g.get("id") == gid:
                        return g, gname, lst
                    if key == "name" and name and g.get("name", "").lower() == str(name).lower():
                        return g, gname, lst
        return None, None, None

    def find(self, ref, fuzzy=False):
        """Игра по словарю / id / названию. fuzzy=True - ещё и по части названия."""
        g, _, _ = self._locate(ref)
        if g is None and fuzzy and not isinstance(ref, dict):
            low = str(ref).lower()
            for cand in self.all():
                if low in cand.get("name", "").lower():
                    return cand
        return g

    get = find

    def group_of(self, ref):
        return self._locate(ref)[1]

    def search(self, text, in_path=False):
        low = text.lower().strip()
        return [g for g in self.all()
                if low in g.get("name", "").lower() or (in_path and low in g.get("path", "").lower())]

    def favorites(self):
        return [g for g in self.all() if g.get("favorite")]

    def most_played(self, n=10):
        return sorted(self.all(), key=lambda g: g.get("playtime_seconds", 0), reverse=True)[:n]

    def never_played(self):
        return [g for g in self.all() if not g.get("playtime_seconds")]

    def history(self):
        """Записи истории запусков (как в games_data.json)."""
        return list(self._info.get("history", []))

    def recent(self, n=10):
        """Последние запущенные игры (по истории), без повторов."""
        seen, out = set(), []
        for entry in self.history():
            g = self.find(entry.get("name", ""))
            if g and g.get("name") not in seen:
                seen.add(g["name"])
                out.append(g)
            if len(out) >= n:
                break
        return out

    def total_playtime(self):
        return sum(g.get("playtime_seconds", 0) for g in self.all())

    def stats(self):
        games = self.all()
        secs = sum(g.get("playtime_seconds", 0) for g in games)
        return {"count": len(games), "favorites": sum(1 for g in games if g.get("favorite")),
                "groups": len(self.groups()), "playtime_seconds": secs, "hours": round(secs / 3600, 1),
                "running": len(self.running())}

    # ---------------------------------------------------------- запущенные
    def _key(self, game):
        return game.get("id") or game.get("name")

    def running(self):
        sessions = getattr(self.launcher, "active_sessions", {}) or {}
        return [g for g in self.all() if self._key(g) in sessions]

    def is_running(self, ref):
        g = self.find(ref)
        return bool(g) and self._key(g) in (getattr(self.launcher, "active_sessions", {}) or {})

    # ---------------------------------------------------------- изменение
    def _commit(self, refresh=True):
        self.launcher.save_data()
        if refresh and hasattr(self.launcher, "refresh_list"):
            self.launcher.refresh_list()

    def refresh(self):
        """Перерисовать список игр."""
        if hasattr(self.launcher, "refresh_list"):
            self.launcher.refresh_list()

    def save(self):
        self.launcher.save_data()

    def add(self, name, path, group=None, icon="", args="", favorite=False, **extra):
        """Добавить игру. group=None - без группы. Возвращает словарь игры."""
        game = {"id": str(uuid.uuid4()), "name": name, "path": path,
                "root_path": os.path.dirname(path), "icon": icon, "args": args,
                "favorite": bool(favorite), "playtime_seconds": 0}
        game.update(extra)
        if group:
            if group not in self.groups():
                self.groups()[group] = []
                emit_event(Events.GROUP_CREATED, group)
            self.groups()[group].append(game)
        else:
            self.standalone().append(game)
        self._commit()
        emit_event(Events.GAME_ADDED, game)
        return game

    def update(self, ref, **changes):
        """Поменять поля игры: update("Hades", favorite=True, args="-windowed")."""
        g = self.find(ref)
        if g is None:
            return None
        g.update(changes)
        self._commit()
        emit_event(Events.GAME_UPDATED, g, changes)
        return g

    def set_favorite(self, ref, value=True):
        return self.update(ref, favorite=bool(value))

    def add_playtime(self, ref, seconds):
        g = self.find(ref)
        if g is None:
            return None
        return self.update(g, playtime_seconds=int(g.get("playtime_seconds", 0) + seconds))

    def remove(self, ref):
        """Удалить игру из библиотеки (файлы игры не трогаются)."""
        g, _, lst = self._locate(ref)
        if g is None:
            return False
        lst.remove(g)
        self._commit()
        emit_event(Events.GAME_REMOVED, g)
        return True

    def move(self, ref, group):
        """Переместить игру в группу (None - убрать из групп)."""
        g, gname, lst = self._locate(ref)
        if g is None:
            return False
        lst.remove(g)
        if group:
            if group not in self.groups():
                self.groups()[group] = []
                emit_event(Events.GROUP_CREATED, group)
            self.groups()[group].append(g)
        else:
            self.standalone().append(g)
        self._commit()
        emit_event(Events.GAME_MOVED, g, group)
        return True

    def create_group(self, name):
        if name and name not in self.groups():
            self.groups()[name] = []
            self._commit()
            emit_event(Events.GROUP_CREATED, name)
            return True
        return False

    def rename_group(self, old, new):
        groups = self.groups()
        if old not in groups or new in groups or not new:
            return False
        rebuilt = {(new if k == old else k): v for k, v in groups.items()}
        groups.clear()
        groups.update(rebuilt)
        self._commit()
        emit_event(Events.GROUP_RENAMED, old, new)
        return True

    def delete_group(self, name, keep_games=True):
        """keep_games=True - игры переедут в «без группы», False - удалятся вместе с группой."""
        groups = self.groups()
        if name not in groups:
            return False
        games = groups.pop(name)
        if keep_games:
            self.standalone().extend(games)
        self._commit()
        emit_event(Events.GROUP_REMOVED, name)
        return True

    # ---------------------------------------------------------- действия
    def _card_for(self, game):
        from PyQt6.QtWidgets import QApplication
        key = self._key(game)
        best = None
        for w in QApplication.allWidgets():
            if w.objectName() == "GameCard" and hasattr(w, "game_data"):
                gd = w.game_data
                if self._key(gd) == key or gd is game:
                    if getattr(w, "group_name", None) != "Избранное":
                        return w
                    best = best or w
        return best

    def launch(self, ref):
        """Запустить игру (как кнопка «Запустить»; перехватчики before_game_launch работают)."""
        g = self.find(ref)
        if g is None or self.is_running(g):
            return False
        card = self._card_for(g)
        if card is not None:
            card.handle_main_button()
            return True
        if hasattr(self.launcher, "launch_game_from_wheel"):
            self.launcher.launch_game_from_wheel(g)
            return True
        return False

    def stop(self, ref):
        """Остановить запущенную игру."""
        g = self.find(ref)
        if g is None or not self.is_running(g):
            return False
        card = self._card_for(g)
        if card is not None:
            card.handle_main_button()
            return True
        return False

    def toggle(self, ref):
        return self.stop(ref) if self.is_running(ref) else self.launch(ref)

    def launch_random(self, predicate=None, favorites_only=False, unplayed_only=False):
        """Запустить случайную игру (можно ограничить условием). Возвращает игру или None."""
        pool = self.all()
        if favorites_only:
            pool = [g for g in pool if g.get("favorite")]
        if unplayed_only:
            pool = [g for g in pool if not g.get("playtime_seconds")]
        if predicate:
            pool = [g for g in pool if predicate(g)]
        pool = [g for g in pool if not self.is_running(g)]
        if not pool:
            return None
        g = random.choice(pool)
        return g if self.launch(g) else None

    def open_folder(self, ref):
        g = self.find(ref)
        if g is None:
            return False
        folder = g.get("root_path") or os.path.dirname(g.get("path", ""))
        if folder and os.path.isdir(folder):
            from PyQt6.QtGui import QDesktopServices
            from PyQt6.QtCore import QUrl
            QDesktopServices.openUrl(QUrl.fromLocalFile(folder))
            return True
        return False
