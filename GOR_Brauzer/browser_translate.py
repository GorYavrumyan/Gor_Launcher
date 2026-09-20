"""
browser_translate.py
----------------------
Встроенный закадровый переводчик видео (VOT Engine, см. release notes v1.2).

Как заявлено в release notes - интеграция идёт БЕЗ Tampermonkey/внешних
расширений: сам движок перевода - это userscript "vot.user.js" (проект
Voice-Over-Translation, открытый исходный код, распространяется отдельно
от GOR Browser: https://github.com/ilyhalight/voice-over-translation).

GOR Browser не переизобретает и не встраивает чужой движок перевода "по
памяти" - вместо этого он делает то же, что раньше делал Tampermonkey:
берёт .user.js файл и внедряет его на страницы нужных сайтов через нативный
QWebEngineScript. Это и есть "нативная интеграция без установки внешнего
расширения или движка Tampermonkey" из release notes.

Что нужно от пользователя:
    Положить актуальный файл vot.user.js (скачанный с официального
    репозитория проекта) в BASE_DIR браузера, рядом с settings.json.
    GOR Browser сам найдёт его и внедрит на YouTube/Twitch/etc.

Если файла нет - вместо переводчика подставляется лёгкий fallback-скрипт:
кнопка "Перевести видео" появляется как обычно, но по клику честно
показывает, что движок перевода не установлен, а не имитирует работу.
"""

import os

from PyQt6.QtWebEngineCore import QWebEngineScript

VOT_SCRIPT_FILENAME = "vot.user.js"

# Сайты, на которых имеет смысл держать скрипт активным (доп. фильтрация
# происходит уже внутри самого vot.user.js по его собственным правилам,
# здесь это лишь верхнеуровневое ограничение "где вообще матчить URL").
VOT_URL_PATTERNS = [
    "https://www.youtube.com/*",
    "https://youtube.com/*",
    "https://m.youtube.com/*",
    "https://www.twitch.tv/*",
    "https://twitch.tv/*",
    "https://vk.com/*",
    "https://vkvideo.ru/*",
    "https://www.tiktok.com/*",
]

_FALLBACK_JS = r"""
(function() {
    if (window.__gorVotFallbackInstalled) return;
    window.__gorVotFallbackInstalled = true;

    function addButton(video) {
        if (video.__gorVotButtonAdded) return;
        video.__gorVotButtonAdded = true;

        var btn = document.createElement('button');
        btn.textContent = '🌐 Перевести видео';
        btn.style.cssText = [
            'position:absolute', 'z-index:2147483647', 'top:10px', 'right:10px',
            'padding:6px 12px', 'border-radius:6px', 'border:none',
            'background:#4c6ef5', 'color:#fff', 'font-size:13px',
            'cursor:pointer', 'font-family:Segoe UI,Arial,sans-serif',
            'box-shadow:0 2px 6px rgba(0,0,0,.4)'
        ].join(';');
        btn.addEventListener('click', function(e) {
            e.stopPropagation();
            btn.textContent = 'Движок VOT не установлен';
            btn.style.background = '#f03e3e';
            setTimeout(function() {
                btn.textContent = '🌐 Перевести видео';
                btn.style.background = '#4c6ef5';
            }, 2500);
        });

        var container = video.parentElement;
        if (container && getComputedStyle(container).position === 'static') {
            container.style.position = 'relative';
        }
        (container || document.body).appendChild(btn);
    }

    function scan() {
        document.querySelectorAll('video').forEach(addButton);
    }

    scan();
    try {
        var observer = new MutationObserver(scan);
        observer.observe(document.documentElement || document.body, {
            childList: true, subtree: true
        });
    } catch (e) {}
})();
"""


def _read_vot_script(base_dir):
    path = os.path.join(base_dir, VOT_SCRIPT_FILENAME)
    if not os.path.exists(path):
        return None
    try:
        with open(path, "r", encoding="utf-8") as f:
            return f.read()
    except Exception:
        return None


def install_vot_translator(profile, base_dir, enabled=True):
    """Регистрирует (или снимает) VOT-скрипт на уровне профиля. Если рядом
    с браузером лежит настоящий vot.user.js - внедряется он (полноценный
    движок перевода), иначе - облегчённый fallback, честно сообщающий об
    отсутствии движка вместо того, чтобы притворяться рабочим переводчиком.

    Возвращает True, если внедрён именно настоящий vot.user.js, False - если
    fallback или переводчик выключен."""
    scripts = profile.scripts()
    for name in ("gor-vot-engine", "gor-vot-fallback"):
        existing = scripts.find(name)
        for old_script in existing:
            scripts.remove(old_script)

    if not enabled:
        return False

    real_source = _read_vot_script(base_dir)
    script = QWebEngineScript()
    script.setInjectionPoint(QWebEngineScript.InjectionPoint.DocumentReady)
    script.setWorldId(QWebEngineScript.ScriptWorldId.MainWorld)
    script.setRunsOnSubFrames(True)

    if real_source:
        script.setName("gor-vot-engine")
        script.setSourceCode(real_source)
        scripts.insert(script)
        return True
    else:
        script.setName("gor-vot-fallback")
        script.setSourceCode(_FALLBACK_JS)
        scripts.insert(script)
        return False
