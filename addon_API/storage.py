"""
api.db - своя база данных аддона (SQLite, файл data/addon.sqlite3), и api.cache.

    db = api.db
    db.kv.set("last_run", 123);  db.kv.get("last_run", 0)

    sessions = db.collection("sessions")                    # коллекция документов
    sessions.insert({"game": "Hades", "seconds": 300})
    sessions.find({"game": "Hades"})                        # равенство
    sessions.find({"seconds": {"$gt": 60}}, sort="seconds", reverse=True, limit=5)
    sessions.find(lambda d: d["seconds"] > 60)              # или любая функция
    sessions.update({"game": "Hades"}, {"seconds": 0});  sessions.delete({"game": "Hades"})

    db.query("SELECT ...", params)  /  db.execute("CREATE TABLE ...")      # и обычный SQL

Операторы в условиях: $gt $gte $lt $lte $ne $in $nin $contains $startswith.
"""

import os
import re
import json
import time
import sqlite3
import threading

_OPS = {
    "$gt": lambda a, b: a is not None and a > b,
    "$gte": lambda a, b: a is not None and a >= b,
    "$lt": lambda a, b: a is not None and a < b,
    "$lte": lambda a, b: a is not None and a <= b,
    "$ne": lambda a, b: a != b,
    "$in": lambda a, b: a in b,
    "$nin": lambda a, b: a not in b,
    "$contains": lambda a, b: a is not None and b in a,
    "$startswith": lambda a, b: isinstance(a, str) and a.startswith(b),
}


def _matches(doc, where):
    if where is None:
        return True
    if callable(where):
        return bool(where(doc))
    for key, cond in where.items():
        val = doc.get(key)
        if isinstance(cond, dict) and cond and all(k in _OPS for k in cond):
            try:
                if not all(_OPS[op](val, arg) for op, arg in cond.items()):
                    return False
            except TypeError:
                return False   # несравнимые типы (число vs строка и т.п.) - условие не выполнено
        elif val != cond:
            return False
    return True


class KV:
    def __init__(self, db):
        self._db = db
        db.execute("CREATE TABLE IF NOT EXISTS _kv (key TEXT PRIMARY KEY, value TEXT)")

    def get(self, key, default=None):
        rows = self._db.query("SELECT value FROM _kv WHERE key=?", (key,))
        return json.loads(rows[0]["value"]) if rows else default

    def set(self, key, value):
        self._db.execute("INSERT OR REPLACE INTO _kv(key, value) VALUES(?, ?)",
                         (key, json.dumps(value, ensure_ascii=False)))

    def delete(self, key):
        self._db.execute("DELETE FROM _kv WHERE key=?", (key,))

    def keys(self):
        return [r["key"] for r in self._db.query("SELECT key FROM _kv ORDER BY key")]

    def all(self):
        return {r["key"]: json.loads(r["value"]) for r in self._db.query("SELECT key, value FROM _kv")}


class Collection:
    def __init__(self, db, name):
        self._db = db
        self.name = name
        self._table = "col_" + re.sub(r"\W+", "_", name)
        db.execute(f"CREATE TABLE IF NOT EXISTS {self._table} "
                   "(id INTEGER PRIMARY KEY AUTOINCREMENT, data TEXT NOT NULL)")

    def _rows(self):
        out = []
        for r in self._db.query(f"SELECT id, data FROM {self._table} ORDER BY id"):
            d = json.loads(r["data"])
            d["_id"] = r["id"]
            out.append(d)
        return out

    def insert(self, doc):
        data = {k: v for k, v in doc.items() if k != "_id"}
        cur = self._db.execute(f"INSERT INTO {self._table}(data) VALUES(?)",
                               (json.dumps(data, ensure_ascii=False),))
        return cur.lastrowid

    def insert_many(self, docs):
        return [self.insert(d) for d in docs]

    def get(self, doc_id):
        for d in self._rows():
            if d["_id"] == doc_id:
                return d
        return None

    def find(self, where=None, sort=None, reverse=False, limit=None):
        rows = [d for d in self._rows() if _matches(d, where)]
        if sort:
            rows.sort(key=lambda d: (d.get(sort) is None, d.get(sort)), reverse=reverse)
        elif reverse:
            rows.reverse()
        return rows[:limit] if limit else rows

    def first(self, where=None, **kw):
        res = self.find(where, limit=1, **kw)
        return res[0] if res else None

    def count(self, where=None):
        return len(self.find(where))

    def update(self, where, changes):
        n = 0
        for d in self.find(where):
            doc_id = d.pop("_id")
            d.update(changes)
            self._db.execute(f"UPDATE {self._table} SET data=? WHERE id=?",
                             (json.dumps(d, ensure_ascii=False), doc_id))
            n += 1
        return n

    def delete(self, where=None):
        ids = [d["_id"] for d in self.find(where)]
        for i in ids:
            self._db.execute(f"DELETE FROM {self._table} WHERE id=?", (i,))
        return len(ids)

    def clear(self):
        return self.delete(None)

    def sum(self, field, where=None):
        return sum(d.get(field, 0) or 0 for d in self.find(where))


class Database:
    def __init__(self, path):
        os.makedirs(os.path.dirname(path), exist_ok=True)
        self.path = path
        self._lock = threading.RLock()
        self._conn = sqlite3.connect(path, check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        self.kv = KV(self)
        self._collections = {}

    def execute(self, sql, params=()):
        with self._lock:
            cur = self._conn.execute(sql, params)
            self._conn.commit()
            return cur

    def query(self, sql, params=()):
        with self._lock:
            return [dict(r) for r in self._conn.execute(sql, params).fetchall()]

    def collection(self, name):
        if name not in self._collections:
            self._collections[name] = Collection(self, name)
        return self._collections[name]

    def close(self):
        with self._lock:
            try:
                self._conn.close()
            except Exception:
                pass


class Cache:
    """Кэш в памяти с временем жизни: api.cache.set("k", v, ttl=60)."""
    def __init__(self):
        self._d = {}

    def get(self, key, default=None):
        item = self._d.get(key)
        if item is None:
            return default
        value, expires = item
        if expires and expires < time.time():
            del self._d[key]
            return default
        return value

    def set(self, key, value, ttl=None):
        self._d[key] = (value, time.time() + ttl if ttl else None)

    def delete(self, key):
        self._d.pop(key, None)

    def clear(self):
        self._d.clear()

    def remember(self, key, ttl, fn):
        """Вернуть из кэша или вычислить fn() и запомнить."""
        sentinel = object()
        v = self.get(key, sentinel)
        if v is sentinel:
            v = fn()
            self.set(key, v, ttl)
        return v
