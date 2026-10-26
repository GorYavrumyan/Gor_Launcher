"""
api.http - сеть без зависаний интерфейса. Колбэки вызываются в потоке интерфейса.

    api.http.get("https://api.github.com", on_done=lambda r: print(r.status, r.json()))
    api.http.post(url, json={"a": 1}, on_done=..., on_error=...)
    api.http.download(url, "file.zip", on_done=..., on_progress=lambda done, total: ...)
    r = api.http.request_sync("GET", url)       # блокирующий вариант - только внутри api.background()
"""

import os
import json as _json
import urllib.parse
import urllib.request
import urllib.error

_UA = "GORLauncher-Addon/1.0"


class Response:
    def __init__(self, status, headers, body, url):
        self.status, self.headers, self.body, self.url = status, headers, body, url

    @property
    def ok(self):
        return 200 <= self.status < 300

    @property
    def text(self):
        charset = "utf-8"
        ct = self.headers.get("Content-Type", "") if self.headers else ""
        if "charset=" in ct:
            charset = ct.split("charset=")[-1].split(";")[0].strip()
        return self.body.decode(charset, errors="replace")

    def json(self):
        return _json.loads(self.body.decode("utf-8", errors="replace"))

    def __repr__(self):
        return f"<Response {self.status} {len(self.body)} байт>"


class HttpAPI:
    def __init__(self, api):
        self._api = api

    def request_sync(self, method, url, data=None, json=None, headers=None, timeout=15):
        hdrs = {"User-Agent": _UA}
        hdrs.update(headers or {})
        body = None
        if json is not None:
            body = _json.dumps(json).encode("utf-8")
            hdrs.setdefault("Content-Type", "application/json")
        elif isinstance(data, str):
            body = data.encode("utf-8")
        elif isinstance(data, bytes):
            body = data
        elif isinstance(data, dict):
            body = urllib.parse.urlencode(data).encode("utf-8")
            hdrs.setdefault("Content-Type", "application/x-www-form-urlencoded")
        req = urllib.request.Request(url, data=body, headers=hdrs, method=method.upper())
        try:
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                return Response(resp.status, dict(resp.headers), resp.read(), resp.geturl())
        except urllib.error.HTTPError as e:
            return Response(e.code, dict(e.headers or {}), e.read(), url)

    def _async(self, method, url, on_done, on_error, **kw):
        self._api.background(lambda: self.request_sync(method, url, **kw), on_done, on_error)

    def get(self, url, on_done=None, on_error=None, **kw):
        self._async("GET", url, on_done, on_error, **kw)

    def post(self, url, on_done=None, on_error=None, **kw):
        self._async("POST", url, on_done, on_error, **kw)

    def get_json(self, url, on_done=None, on_error=None, **kw):
        """GET и сразу разобранный JSON в on_done(data)."""
        self._api.background(lambda: self.request_sync("GET", url, **kw).json(), on_done, on_error)

    def download(self, url, dest, on_done=None, on_error=None, on_progress=None, timeout=30):
        """Скачать файл. on_progress(скачано, всего) вызывается в потоке интерфейса."""
        state = {"done": 0, "total": 0, "finished": False}

        def work():
            req = urllib.request.Request(url, headers={"User-Agent": _UA})
            os.makedirs(os.path.dirname(os.path.abspath(dest)), exist_ok=True)
            try:
                with urllib.request.urlopen(req, timeout=timeout) as resp, open(dest + ".part", "wb") as f:
                    state["total"] = int(resp.headers.get("Content-Length") or 0)
                    while True:
                        chunk = resp.read(64 * 1024)
                        if not chunk:
                            break
                        f.write(chunk)
                        state["done"] += len(chunk)
                os.replace(dest + ".part", dest)
            except BaseException:
                # не оставляем недокачанный .part на диске при обрыве/ошибке
                try:
                    os.remove(dest + ".part")
                except OSError:
                    pass
                raise
            return dest

        timer = None
        if on_progress:
            timer = self._api.every(150, lambda: on_progress(state["done"], state["total"]))

        def stop_timer():
            if timer is not None:
                timer.stop()

        def done(path):
            stop_timer()
            if on_progress:
                on_progress(state["done"], state["total"])
            if on_done:
                on_done(path)

        def fail(err):
            stop_timer()
            if on_error:
                on_error(err)
        self._api.background(work, done, fail)
