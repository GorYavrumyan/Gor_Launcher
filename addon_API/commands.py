"""
api.commands - общий реестр команд лаунчера (его показывает палитра команд Ctrl+K).

    api.commands.register("my.hello", "Сказать привет", lambda: api.toast("Привет!"),
                          hotkey="Ctrl+Alt+H", keywords="приветствие hello", group="Мои команды")

    # динамический список (например, игры): вызывается при каждом вводе в палитре
    api.commands.provider(lambda query: [{"title": f"▶ {g['name']}", "fn": lambda g=g: api.games.launch(g),
                                          "group": "Игры"} for g in api.games.search(query)][:8])

Команды других аддонов видны всем: api.commands.search("тема"), api.commands.run("my.hello").
"""

_commands = {}      # id -> dict
_providers = []     # (owner, fn)


def fuzzy_score(query, text):
    """Нечёткий поиск: буквы запроса должны идти по порядку. Больше - лучше, 0 - не подходит."""
    q, t = (query or "").lower().strip(), (text or "").lower()
    if not q:
        return 1
    if q in t:
        return 1000 - t.index(q) * 5 - len(t)
    pos, score, prev = 0, 0, -2
    for ch in q:
        i = t.find(ch, pos)
        if i == -1:
            return 0
        score += 10 + (15 if i == prev + 1 else 0) + (8 if i == 0 or t[i - 1] in " _-.:/" else 0)
        prev, pos = i, i + 1
    return max(1, score - len(t) // 4)


class CommandsAPI:
    def __init__(self, api):
        self._api = api

    def register(self, id, title, fn, hotkey=None, keywords="", group="", icon=""):
        full = id if "." in id else f"{self._api.id}.{id}"
        _commands[full] = {"id": full, "title": title, "fn": fn, "keywords": keywords,
                           "group": group or self._api.name, "icon": icon,
                           "hotkey": hotkey, "owner": self._api.root}
        if hotkey:
            self._api.keys.bind(hotkey, lambda: self.run(full), context="application")
        self._api._resources.add(lambda: _commands.pop(full, None))
        return full

    def unregister(self, id):
        full = id if "." in id else f"{self._api.id}.{id}"
        _commands.pop(full, None)

    def provider(self, fn):
        """fn(query) -> список {'title', 'fn', 'group'?, 'icon'?}."""
        item = (self._api.root, fn)
        _providers.append(item)
        self._api._resources.add(lambda: item in _providers and _providers.remove(item))

    def run(self, id):
        cmd = _commands.get(id)
        if cmd is None:
            return False
        self._api._safe(cmd["fn"])()
        return True

    def all(self):
        return list(_commands.values())

    def search(self, query="", limit=40):
        """Найти команды (зарегистрированные + от провайдеров), лучшие сверху."""
        scored = []
        for c in _commands.values():
            s = max(fuzzy_score(query, c["title"]), fuzzy_score(query, c["keywords"]) // 2,
                    fuzzy_score(query, c["group"]) // 3)
            if s:
                scored.append((s, c))
        for owner, fn in list(_providers):
            try:
                for c in fn(query) or []:
                    c = dict(c)
                    c.setdefault("group", "")
                    c.setdefault("icon", "")
                    c.setdefault("id", None)
                    scored.append((fuzzy_score(query, c["title"]) or 1, c))
            except Exception as e:
                self._api.log(f"Ошибка провайдера команд: {e}", "error")
        scored.sort(key=lambda x: -x[0])
        return [c for _, c in scored[:limit]]
