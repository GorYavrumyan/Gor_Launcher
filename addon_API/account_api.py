"""
api.account - аккаунт, под которым открыт лаунчер: язык, предпочтения, список аккаунтов.

    api.account.name                    # "Vova" (None - если системы аккаунтов нет)
    api.account.language()              # "en"
    api.account.languages()             # [{"code": "ru", "name": "Русский"}, ...]
    api.account.set_language("es")      # запоминается за аккаунтом; restart=True - сразу перезапустить лаунчер
    api.account.prefs.set("любой ключ", значение)    # личное хранилище аддона у ЭТОГО аккаунта
    api.account.prefs.get("любой ключ", по_умолчанию)

Темы тоже у каждого аккаунта свои: api.themes.apply(...) меняет тему только текущего аккаунта,
api.themes.account_name() говорит, чей это выбор, а новые темы (api.themes.install, save_as_theme)
сохраняются в accounts/<имя>/themes/. Настройки api.settings и данные api.db тоже уже «по аккаунтам»:
папка addons/ у каждого аккаунта своя.
"""

from . import accounts


class AccountPrefs:
    """Личное хранилище аддона внутри предпочтений аккаунта (preferences.json -> addons -> <id аддона>)."""
    def __init__(self, addon_id):
        self._ns = addon_id

    def get(self, key, default=None):
        return accounts.ns_get(self._ns, key, default)

    def set(self, key, value):
        return accounts.ns_set(self._ns, key, value)

    def all(self):
        return accounts.ns_all(self._ns)


class AccountAPI:
    def __init__(self, api):
        self._api = api
        self.prefs = AccountPrefs(api.id)

    @property
    def name(self):
        return accounts.active_name()

    @property
    def dir(self):
        return accounts.account_dir()

    def list(self):
        return accounts.list_accounts()

    def language(self):
        try:
            import lang_loader
            return lang_loader.get_language()
        except Exception:
            return accounts.pref("language", "ru")

    def languages(self):
        try:
            import lang_loader
            return lang_loader.available_languages()
        except Exception:
            return []

    def set_language(self, code, restart=False):
        """Сменить язык интерфейса ЭТОГО аккаунта. Строки, уже нарисованные в окне,
        обновятся после перезапуска (restart=True перезапустит лаунчер сразу)."""
        import lang_loader
        lang_loader.set_language(code)
        info = getattr(self._api.launcher, "games_info", None)
        if isinstance(info, dict):
            info["language"] = code            # чтобы следующий save_data() не затёр выбор
        if restart:
            try:
                from bridge_loader import restart_launcher
                restart_launcher(confirm=False)
            except Exception as e:
                self._api.log(f"Не удалось перезапустить лаунчер: {e}", "error")
        return code

    def theme(self):
        """id активной темы этого аккаунта."""
        from .themes import themes
        return themes.current_id()
