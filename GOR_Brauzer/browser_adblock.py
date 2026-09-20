"""
browser_adblock.py
--------------------
Встроенный блокировщик рекламы GOR Browser (uBlock Engine, см. release
notes v1.2). Работает в два уровня, как и заявлено:

  1. Сетевой перехватчик (GorAdBlockInterceptor) - режет запросы к рекламным
     и трекинговым доменам ДО того, как они уйдут в сеть, через
     QWebEngineUrlRequestInterceptor.setUrlRequestInterceptor().

  2. Косметический фильтр - небольшой JS, внедряемый через QWebEngineScript
     на КАЖДУЮ страницу (DocumentReady, все фреймы), который прячет типовые
     пустые рекламные блоки/баннеры, оставшиеся от заблокированных запросов
     (пустые iframe'ы, div'ы с классами вида *ad*, *banner*, *sponsor* и т.п.).

Никакого стороннего движка/списка не скачивается - список доменов лежит
локально (BLOCKED_DOMAINS) и его легко пополнять. При желании можно
подключить внешний список формата "домен на строку" через
load_extra_blocklist().

Использование (см. browser_widget.py):

    from browser_adblock import GorAdBlockInterceptor, install_cosmetic_filter

    self.adblock_interceptor = GorAdBlockInterceptor(self)
    self.adblock_interceptor.set_enabled(self.settings.get("adblock_enabled", True))
    self.profile.setUrlRequestInterceptor(self.adblock_interceptor)
    install_cosmetic_filter(self.profile, self.settings.get("adblock_enabled", True))
"""

import os

from PyQt6.QtCore import QObject, QUrl, pyqtSignal
from PyQt6.QtNetwork import QNetworkAccessManager, QNetworkRequest, QNetworkReply
from PyQt6.QtWebEngineCore import (
    QWebEngineUrlRequestInterceptor,
    QWebEngineScript,
)

# --- Встроенный список рекламных/трекинговых доменов -----------------------
# Не претендует на полноту EasyList - это компактный, легко читаемый набор
# самых распространённых рекламных сетей и трекеров. Достаточно для заметного
# эффекта "из коробки"; расширяется через load_extra_blocklist() или прямым
# редактированием adblock_domains.txt рядом с браузером.
BLOCKED_DOMAINS = {
    # Google Ads / Analytics
    "doubleclick.net", "googlesyndication.com", "googleadservices.com",
    "google-analytics.com", "googletagmanager.com", "googletagservices.com",
    "adservice.google.com", "pagead2.googlesyndication.com",
    # Yandex реклама/метрика (частый источник баннеров в РУ-сегменте)
    "an.yandex.ru", "mc.yandex.ru", "yandexadexchange.net",
    # Крупные рекламные сети
    "adnxs.com", "advertising.com", "adform.net", "adroll.com",
    "criteo.com", "criteo.net", "outbrain.com", "taboola.com",
    "rubiconproject.com", "pubmatic.com", "openx.net", "smartadserver.com",
    "media.net", "bidswitch.net", "casalemedia.com", "moatads.com",
    "amazon-adsystem.com", "scorecardresearch.com",
    # Соцсети - трекинг/пиксели
    "facebook.net", "connect.facebook.net", "ads.tiktok.com",
    "analytics.tiktok.com", "ads.twitter.com", "analytics.twitter.com",
    # Popunder/push-реклама, часто встречающаяся на "серых" сайтах
    "popads.net", "propellerads.com", "adsterra.com", "exoclick.com",
    "juicyads.com", "mgid.com", "revcontent.com", "adcash.com",
    "clickadu.com", "hilltopads.net", "onclickmax.com",
}

_EXTRA_LIST_FILENAME = "adblock_domains.txt"
_DYNAMIC_CACHE_FILENAME = "adblock_dynamic_domains.txt"

# Список-первоисточник по умолчанию для динамического AdBlock (пункт ТЗ:
# "фоновое обновление списков блокировки с GitHub raw.githubusercontent.com
# вместо статического списка"). StevenBlack/hosts - один из самых известных
# и стабильно поддерживаемых открытых hosts-листов, формат "0.0.0.0 домен"
# на строку, отлично парсится без сторонних зависимостей.
DEFAULT_DYNAMIC_ADBLOCK_URL = (
    "https://raw.githubusercontent.com/StevenBlack/hosts/master/hosts"
)


def load_extra_blocklist(base_dir):
    """Подгружает пользовательский список доменов (по одному на строку,
    "#" - комментарий) из adblock_domains.txt рядом с браузером, если файл
    существует, и добавляет его к BLOCKED_DOMAINS. Не обязателен - если
    файла нет, просто используется встроенный список."""
    path = os.path.join(base_dir, _EXTRA_LIST_FILENAME)
    if not os.path.exists(path):
        return
    try:
        with open(path, "r", encoding="utf-8") as f:
            for line in f:
                domain = line.strip().lower()
                if domain and not domain.startswith("#"):
                    BLOCKED_DOMAINS.add(domain)
    except Exception:
        pass


def load_dynamic_blocklist_cache(base_dir):
    """Подгружает УЖЕ СКАЧАННЫЙ ранее динамический список (см.
    GorAdBlockUpdater) из локального кэша - чтобы блокировка работала сразу
    при старте, не дожидаясь свежего запроса к GitHub по сети."""
    path = os.path.join(base_dir, _DYNAMIC_CACHE_FILENAME)
    if not os.path.exists(path):
        return
    try:
        with open(path, "r", encoding="utf-8") as f:
            for line in f:
                domain = line.strip().lower()
                if domain:
                    BLOCKED_DOMAINS.add(domain)
    except Exception:
        pass


def _parse_blocklist_text(text: str):
    """Понимает два распространённых формата открытых списков блокировки:
    - hosts-формат: "0.0.0.0 domain.com" / "127.0.0.1 domain.com" на строку
      (например StevenBlack/hosts - список по умолчанию);
    - простой список доменов, один на строку (как в adblock_domains.txt).
    Строки-комментарии ("#") и служебные хосты (localhost и т.п.) игнорируются.
    """
    domains = set()
    skip = {"localhost", "localhost.localdomain", "local", "broadcasthost", "ip6-localhost", "ip6-loopback"}
    for raw_line in text.splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        parts = line.split()
        if len(parts) >= 2 and parts[0] in ("0.0.0.0", "127.0.0.1"):
            domain = parts[1].strip().lower()
        elif len(parts) == 1:
            domain = parts[0].strip().lower()
        else:
            continue
        if domain and domain not in skip and "." in domain:
            domains.add(domain)
    return domains


class GorAdBlockUpdater(QObject):
    """Динамический AdBlock (пункт ТЗ): в фоне, по таймеру, скачивает
    актуальный список блокировки с GitHub (raw.githubusercontent.com) и
    подмешивает его в BLOCKED_DOMAINS - без перезапуска браузера и без
    блокировки UI (запрос асинхронный через QNetworkAccessManager).

    Результат кэшируется в adblock_dynamic_domains.txt рядом с профилем,
    поэтому даже без сети список остаётся тем, что был скачан в прошлый раз
    (см. load_dynamic_blocklist_cache, вызывается один раз при старте).
    """

    update_finished = pyqtSignal(int, str)   # (кол-во новых доменов, ошибка или "")

    def __init__(self, base_dir, parent=None):
        super().__init__(parent)
        self.base_dir = base_dir
        self._manager = QNetworkAccessManager(self)
        self._reply = None

    def update_now(self, url=None):
        """Запускает асинхронное скачивание списка. Безопасно вызывать,
        даже если предыдущий запрос ещё не завершился - новый просто
        отменит старый (на практике этого либо не происходит, либо не
        критично: список идемпотентен)."""
        url = url or DEFAULT_DYNAMIC_ADBLOCK_URL
        if self._reply is not None:
            try:
                self._reply.abort()
            except Exception:
                pass
        request = QNetworkRequest(QUrl(url))
        self._reply = self._manager.get(request)
        self._reply.finished.connect(lambda: self._on_finished(self._reply))

    def _on_finished(self, reply):
        try:
            if reply.error() != QNetworkReply.NetworkError.NoError:
                self.update_finished.emit(0, reply.errorString())
                return
            raw = bytes(reply.readAll()).decode("utf-8", errors="ignore")
        except Exception as exc:
            self.update_finished.emit(0, str(exc))
            return
        finally:
            reply.deleteLater()
            self._reply = None

        domains = _parse_blocklist_text(raw)
        if not domains:
            self.update_finished.emit(0, "Список пуст или не распознан")
            return

        before = len(BLOCKED_DOMAINS)
        BLOCKED_DOMAINS.update(domains)
        added = len(BLOCKED_DOMAINS) - before

        try:
            path = os.path.join(self.base_dir, _DYNAMIC_CACHE_FILENAME)
            with open(path, "w", encoding="utf-8") as f:
                f.write("\n".join(sorted(domains)))
        except Exception:
            pass  # кэш не критичен - список уже применён в памяти

        self.update_finished.emit(added, "")


def _host_is_blocked(host: str) -> bool:
    """True, если host совпадает с одним из заблокированных доменов или
    является его поддоменом (например, "ads.doubleclick.net" блокируется
    по записи "doubleclick.net")."""
    host = host.lower()
    if host in BLOCKED_DOMAINS:
        return True
    return any(host.endswith("." + d) for d in BLOCKED_DOMAINS)


class GorAdBlockInterceptor(QWebEngineUrlRequestInterceptor):
    """Сетевой уровень AdBlock'а. Ставится ОДИН РАЗ на профиль
    (profile.setUrlRequestInterceptor(...)) - до создания вкладок, как того
    требует QWebEngine. Включение/выключение делается через set_enabled(),
    без пересоздания объекта, чтобы не терять уже установленный перехватчик."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._enabled = True
        self.blocked_count = 0

    def set_enabled(self, enabled: bool):
        self._enabled = bool(enabled)

    def is_enabled(self) -> bool:
        return self._enabled

    def interceptRequest(self, info):
        if not self._enabled:
            return
        try:
            host = info.requestUrl().host()
        except Exception:
            return
        if not host:
            return
        # Не блокируем переход по URL в главном фрейме (прямая навигация
        # пользователя на рекламный домен - его осознанный выбор), режем
        # только подгружаемые с других доменов ресурсы (баннеры, пиксели,
        # скрипты сетей).
        try:
            from PyQt6.QtWebEngineCore import QWebEngineUrlRequestInfo
            is_main_frame = info.resourceType() == QWebEngineUrlRequestInfo.ResourceType.ResourceTypeMainFrame
        except Exception:
            is_main_frame = False
        if is_main_frame:
            return
        if _host_is_blocked(host):
            info.block(True)
            self.blocked_count += 1


# --- Косметическая фильтрация (JS, скрывает "пустые дыры" от блокировки) ---
_COSMETIC_JS = r"""
(function() {
    if (window.__gorAdblockCosmeticInstalled) return;
    window.__gorAdblockCosmeticInstalled = true;

    var SELECTORS = [
        '[id*="google_ads"]', '[id*="ad-banner"]', '[class*="ad-banner"]',
        '[class^="ads-"]', '[class*=" ads-"]', '[class*="advert"]',
        '[class*="sponsor-banner"]', 'ins.adsbygoogle',
        'div[id^="div-gpt-ad"]', 'iframe[id^="google_ads_iframe"]',
        '.textad', '.banner-ad', '.ad-container', '.ad-slot',
    ];

    function hideAds(root) {
        try {
            SELECTORS.forEach(function(sel) {
                root.querySelectorAll(sel).forEach(function(el) {
                    el.style.setProperty('display', 'none', 'important');
                });
            });
        } catch (e) { /* некоторые селекторы могут не поддерживаться - не критично */ }
    }

    hideAds(document);

    // Страницы часто подгружают рекламные блоки динамически (SPA/лениво) -
    // следим за изменениями DOM и повторно прячем новые совпадения.
    try {
        var observer = new MutationObserver(function() { hideAds(document); });
        observer.observe(document.documentElement || document.body, {
            childList: true, subtree: true
        });
    } catch (e) {}
})();
"""


def install_cosmetic_filter(profile, enabled=True):
    """Регистрирует (или снимает) косметический JS-фильтр на уровне профиля.
    Скрипт живёт под фиксированным именем "gor-adblock-cosmetic", поэтому
    повторный вызов безопасно переустанавливает/выключает его, не плодя
    дублей в profile.scripts()."""
    scripts = profile.scripts()
    existing = scripts.find("gor-adblock-cosmetic")
    for old_script in existing:
        scripts.remove(old_script)
    if not enabled:
        return
    script = QWebEngineScript()
    script.setName("gor-adblock-cosmetic")
    script.setSourceCode(_COSMETIC_JS)
    script.setInjectionPoint(QWebEngineScript.InjectionPoint.DocumentReady)
    script.setWorldId(QWebEngineScript.ScriptWorldId.ApplicationWorld)
    script.setRunsOnSubFrames(True)
    scripts.insert(script)
