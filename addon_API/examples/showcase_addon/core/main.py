"""
Витрина API: интерактивная галерея возможностей addon_API.

Каждая демо - обычная функция ниже, помеченная @demo(...). Код, который вы видите
в окне «Код», - это ТОЧНО тот код, что выполняется по кнопке (берётся из этого файла
через inspect). Хотите поэкспериментировать - скопируйте тело демо и меняйте.
"""

import ast
import sys
import json
import math
import time
import inspect
import textwrap
import datetime
import threading
import traceback

from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QGridLayout, QLabel, QPushButton, QListWidget,
    QListWidgetItem, QFrame, QScrollArea, QSplitter, QTabWidget, QPlainTextEdit, QProgressBar,
    QComboBox,
)
from PyQt6.QtGui import QFont

from addon_API import AddonBase, Events

# ===================================================================== #
#  Реестр демо
# ===================================================================== #
SECTIONS = [
    ("design",   "🎨", "Дизайн",              "api.design — цвета, стили, эффекты, анимации, слои поверх окна. Всё откатывается кнопкой «Сбросить всё»."),
    ("games",    "🎮", "Игры",                "api.games — библиотека игр целиком: чтение, изменение, запуск, статистика."),
    ("hooks",    "🪝", "События и перехват",  "Шина событий и перехватчики: слушать лаунчер — и вмешиваться в его действия."),
    ("data",     "💾", "Данные",              "api.db (SQLite), api.cache, api.settings — свои данные у каждого аддона."),
    ("net",      "🌐", "Сеть и система",      "api.http без зависаний интерфейса и api.system: процессы, буфер обмена, запуск программ."),
    ("audio",    "🔊", "Звук",                "api.audio — звук без единого файла: синтез сигналов прямо в коде."),
    ("time",     "⏱", "Клавиши и время",      "api.keys, api.schedule, api.commands (палитра Ctrl+K), связь между аддонами."),
    ("ui",       "🖼", "Интерфейс",           "api.ui — формы, диалоги, окна, таблицы, графики, встроенный браузер, значки."),
    ("canvas",   "🕹", "Холст и игры",        "api.canvas — свой игровой цикл, клавиатура, мышь, частицы. Из лаунчера можно сделать космолёт."),
    ("dev",      "🛠", "Инструменты",         "Инспектор, консоль, скриншоты, документация, перезагрузка аддона на лету."),
]

DEMOS = []
STATE = {}          # состояние демо (включённые перехватчики, окна и т.п.)


def demo(section, title, desc="", kind="run", choices=None):
    """kind: run - кнопка; choice - список + кнопка (fn получает choice); toggle - вкл/выкл (fn получает on)."""
    def deco(fn):
        DEMOS.append({"id": fn.__name__, "section": section, "title": title, "desc": desc,
                      "kind": kind, "choices": choices or [], "fn": fn})
        return fn
    return deco


def body_source(fn):
    """Исходный код тела демо (без def и докстринга) - ровно то, что выполняется."""
    try:
        src = textwrap.dedent(inspect.getsource(fn))
        node = ast.parse(src).body[0]
        first = 1 if ast.get_docstring(node) is not None else 0
        start = node.body[first].lineno - 1 if len(node.body) > first else node.lineno
        code = textwrap.dedent("\n".join(src.splitlines()[start:node.end_lineno]))
        return "# api — AddonAPI этого аддона, log — запись в журнал\n" + code
    except Exception:
        return "# исходный код недоступен"


def short(args, n=90):
    s = ", ".join(repr(a) for a in args)
    return s if len(s) <= n else s[:n] + "…"


def rnd():
    import random
    return random


# ===================================================================== #
#  🎨 ДИЗАЙН
# ===================================================================== #
@demo("design", "Готовый стиль целиком", "Один вызов — весь лаунчер в новом облике. 7 пресетов.",
      kind="choice", choices=["glass", "neon", "minimal", "cyberpunk", "terminal", "soft", "aurora"])
def design_preset(api, log, choice):
    """Готовый стиль"""
    api.design.preset(choice)
    log(f"стиль «{choice}»: {api.design.preset_info(choice)}")


@demo("design", "Палитра из одного цвета", "Выберите любой цвет — api.design построит ВСЮ палитру лаунчера из него.")
def design_palette_pick(api, log):
    """Палитра из цвета"""
    color = api.ui.pick_color("#ff7a18")
    if color:
        api.design.palette(color, "dark")
        log(f"палитра из {color}: {api.design.get_colors()}")


@demo("design", "Тёмная / светлая палитра", "Тот же акцент, но другой режим. Текст сам подстраивается под светлый фон.",
      kind="choice", choices=["dark", "light"])
def design_modes(api, log, choice):
    """Режим палитры"""
    accent = api.design.get_colors()["accent"]
    api.design.palette(accent, choice)
    log(f"режим {choice}, акцент {accent}")


@demo("design", "Палитра из картинки", "Выберите картинку — лаунчер перекрасится под её главный цвет.")
def design_from_image(api, log):
    """Оформление под картинку"""
    path = api.ui.pick_file("Картинка", "Изображения (*.png *.jpg *.jpeg *.webp)")
    if path:
        color = api.design.palette_from_image(path)
        log(f"главный цвет картинки: {color}")


@demo("design", "Радужный акцент", "Акцентный цвет всего лаунчера плавно переливается по кругу.", kind="toggle")
def design_rainbow(api, log, on):
    """Радуга"""
    if on:
        api.design.rainbow(period_ms=7000, fps=4)
    else:
        api.design.stop_color_animation()
        api.design.reset_colors()
    log("радуга: " + ("включена" if on else "выключена"))


@demo("design", "Плавный переход цвета", "Акцент не прыгает, а перетекает к новому значению.",
      kind="choice", choices=["#ff2d95", "#00d4ff", "#7cff6b", "#ffb300"])
def design_transition(api, log, choice):
    """Плавная смена акцента"""
    api.design.transition_colors({"accent": choice}, ms=700)


@demo("design", "Скругления всего лаунчера", "Одним числом меняет радиус везде. Слишком большие радиусы Qt ломает — API ограничивает их сам.",
      kind="choice", choices=["острые", "обычные", "круглее"])
def design_radius(api, log, choice):
    """Радиус скруглений"""
    if choice == "острые":
        api.design.sharp()
    elif choice == "круглее":
        api.design.rounded(1.6)
    else:
        api.design.radius(scale=1.0)


@demo("design", "Стиль кнопок", "8 готовых стилей для ВСЕХ кнопок, включая «Запустить» и шапку.",
      kind="choice", choices=["flat", "solid", "outline", "ghost", "neon", "glass", "gradient", "pill"])
def design_buttons(api, log, choice):
    """Кнопки"""
    api.design.buttons(choice)


@demo("design", "Стиль вкладок", "Пять вариантов вкладок. Посмотрите на ряд вкладок лаунчера сверху.",
      kind="choice", choices=["pill", "underline", "boxed", "segmented", "minimal"])
def design_tabs(api, log, choice):
    """Вкладки"""
    api.design.tabs(choice)


@demo("design", "Стеклянные карточки игр", "Полупрозрачные карточки + свечение при наведении. Откройте вкладку с играми.")
def design_cards(api, log):
    """Карточки"""
    api.design.cards(radius=24, glass=True)
    api.design.covers(radius=16)
    api.design.hover_glow("GameCard", "{{accent}}", 26)
    api.design.scrollbars(style="thin")


@demo("design", "Свой стиль из Python", "css() превращает аргументы в QSS. {{accent@25}} — акцент с прозрачностью 25%, следует за темой.")
def design_css(api, log):
    """Правило из кода"""
    api.design.css("QPushButton#RunGameBtn", radius=14, bg="{{accent}}", color="#ffffff",
                   hover={"bg": "{{accent_hover}}"}, pressed={"bg": "{{accent_dark}}"})
    api.design.css("QFrame#GameCard", bg="{{surface_alt}}", border=(2, "{{accent@35}}"))


@demo("design", "Эффекты на виджетах", "Тени, свечение, пульсация. Работают и на карточках, которые появятся позже.",
      kind="choice", choices=["тень", "свечение", "свечение при наведении", "пульс кнопок", "окрасить обложки"])
def design_effects(api, log, choice):
    """Эффекты"""
    d = api.design
    if choice == "тень":
        d.shadow("GameCard", blur=30, dy=8)
    elif choice == "свечение":
        d.glow("GameCard", "{{accent}}", 22, pulse_ms=2600)
    elif choice == "свечение при наведении":
        d.hover_glow("GameCard", "{{accent}}", 28)
    elif choice == "пульс кнопок":
        d.pulse("RunGameBtn")
    else:
        d.colorize("GameCardImage", "{{accent}}", 0.4)


@demo("design", "Слои поверх окна", "Частицы, виньетка, сканлайны, сетка, шум, движущийся градиент. Мышь проходит сквозь них.",
      kind="choice", choices=["звёзды", "снег", "дождь", "светлячки", "пузыри", "виньетка", "сканлайны ЭЛТ",
                              "сетка", "зерно", "плывущий градиент"])
def design_overlay(api, log, choice):
    """Слои"""
    d = api.design
    kinds = {"звёзды": "stars", "снег": "snow", "дождь": "rain", "светлячки": "fireflies", "пузыри": "bubbles"}
    if choice in kinds:
        d.particles(kinds[choice], 70)
    elif choice == "виньетка":
        d.vignette(0.6)
    elif choice == "сканлайны ЭЛТ":
        d.scanlines(3, 0.12)
    elif choice == "сетка":
        d.grid(44, "{{accent}}", 0.10)
    elif choice == "зерно":
        d.noise(0.06)
    else:
        d.animated_gradient(["{{accent}}", "#7a2dff", "#00d4ff"], 12000, 0.16)


@demo("design", "Обои из картинки", "Картинка поверх интерфейса с прозрачностью — как лёгкие обои.")
def design_wallpaper(api, log):
    """Обои"""
    path = api.ui.pick_file("Картинка", "Изображения (*.png *.jpg *.jpeg *.webp)")
    if path:
        api.design.wallpaper(path, opacity=0.22, mode="cover")


@demo("design", "Шрифт интерфейса", "Любой установленный шрифт — одной строкой.", kind="choice",
      choices=["Consolas", "Segoe UI", "Georgia", "Courier New", "Comic Sans MS"])
def design_font(api, log, choice):
    """Шрифт"""
    api.design.font(choice, 13)


@demo("design", "Размер всех шрифтов", "Масштаб ВСЕХ размеров текста в стилях лаунчера.", kind="choice", choices=["0.9", "1.0", "1.15", "1.3"])
def design_font_scale(api, log, choice):
    """Масштаб шрифта"""
    api.design.font_scale(float(choice))


@demo("design", "Анимации виджетов", "Выезд, тряска, подпрыгивание, появление новых карточек каскадом.",
      kind="choice", choices=["тряска поиска", "подпрыгивание кнопок", "появление карточек", "анимация вкладок"])
def design_animate(api, log, choice):
    """Анимации"""
    d = api.design
    if choice == "тряска поиска":
        d.shake("SearchBar")
    elif choice == "подпрыгивание кнопок":
        d.bounce("RunGameBtn")
    elif choice == "появление карточек":
        d.appear("GameCard", "up", stagger=60)
        api.games.refresh()                 # карточки пересоздаются — и выезжают каскадом
    else:
        d.animate_tab_switch("left")
        log("переключайте вкладки лаунчера — содержимое выезжает")


@demo("design", "Прозрачность окна", "Окно лаунчера становится полупрозрачным.", kind="toggle")
def design_opacity(api, log, on):
    """Прозрачность окна"""
    api.design.window_opacity(0.82 if on else 1.0)


@demo("design", "Сохранить как тему", "Всё, что вы настроили выше, сохраняется как обычная тема (появится в Theme Studio).")
def design_save_theme(api, log):
    """Экспорт в тему"""
    theme_id = api.design.save_as_theme("Из витрины API", author="Витрина")
    log(f"тема сохранена: themes/{theme_id}/theme.json — выберите её в Theme Studio (🎨)")


@demo("design", "♻ Сбросить весь дизайн", "Откатывает ВСЁ, что витрина изменила через api.design.")
def design_reset(api, log):
    """Откат"""
    api.design.reset()
    log("дизайн сброшен")


# ===================================================================== #
#  🎮 ИГРЫ
# ===================================================================== #
@demo("games", "Статистика библиотеки", "Количество игр, групп, избранных и общее время — одним вызовом.")
def games_stats(api, log):
    """Статистика"""
    st = api.games.stats()
    log(json.dumps(st, ensure_ascii=False))
    api.toast(f"🎮 {st['count']} игр · {st['hours']} ч · {st['groups']} групп")


@demo("games", "Топ по времени игры", "Самые играемые игры из вашей библиотеки.")
def games_top(api, log):
    """Топ игр"""
    for g in api.games.most_played(5):
        log(f"{g['name']:30} {g.get('playtime_seconds', 0) // 3600} ч")


@demo("games", "Поиск игры", "Поиск по названию (и по части названия).")
def games_search(api, log):
    """Поиск"""
    q = api.ui.prompt("Часть названия игры:", "a")
    if q:
        found = api.games.search(q)
        log(f"найдено {len(found)}: " + ", ".join(g["name"] for g in found[:8]))


@demo("games", "Добавить демо-игру в библиотеку", "Игра появляется в лаунчере прямо сейчас, в новой группе «API Demo».")
def games_add(api, log):
    """Добавление игры"""
    g = api.games.add("Демо-игра (API)", r"C:\demo\fake.exe", group="API Demo", favorite=True, demo_api=True)
    log(f"добавлена: {g['name']} (id {g['id'][:8]}…) — загляните в библиотеку")


@demo("games", "Удалить демо-игру", "Убирает игру из библиотеки и пустую группу (файлы на диске не трогаются).")
def games_remove(api, log):
    """Удаление"""
    for g in [x for x in api.games.all() if x.get("demo_api")]:
        api.games.remove(g)
    if "API Demo" in api.games.group_names() and not api.games.groups()["API Demo"]:
        api.games.delete_group("API Demo")
    log("демо-игра удалена")


@demo("games", "Запустить случайную игру", "launch_random() запускает настоящую игру из вашей библиотеки — поэтому спросим.")
def games_random(api, log):
    """Случайная игра"""
    if api.ui.confirm("Запустить случайную игру из вашей библиотеки?"):
        g = api.games.launch_random()
        log("запущена: " + (g["name"] if g else "ничего не подошло"))


# ===================================================================== #
#  🪝 СОБЫТИЯ И ПЕРЕХВАТ
# ===================================================================== #
@demo("hooks", "Слушать ВСЕ события лаунчера", "Включите — и журнал начнёт показывать каждое событие (смена темы, обновление списка, запуск игр…).", kind="toggle")
def hooks_all_events(api, log, on):
    """Шина событий"""
    if on:
        STATE["ev"] = api.on("*", lambda name, *a: log(f"событие: {name}  {short(a, 60)}"))
    elif "ev" in STATE:
        api.off(STATE.pop("ev"))


@demo("hooks", "Защитник запуска игр", "Перехватчик before_game_launch: перед КАЖДЫМ запуском игры спрашивает подтверждение. «Нет» — игра не запустится.", kind="toggle")
def hooks_guard(api, log, on):
    """Перехват: отмена запуска"""
    if on:
        def ask(game):
            ok = api.ui.confirm(f"Витрина API перехватила запуск «{game['name']}».\nЗапускать?")
            log(f"запуск «{game['name']}»: " + ("разрешён" if ok else "ОТМЕНЁН перехватчиком"))
            return ok
        STATE["guard"] = api.before("before_game_launch", ask)
    elif "guard" in STATE:
        api.off(STATE.pop("guard"))


@demo("hooks", "Фильтр аргументов запуска", "game_launch_args: к аргументам каждой игры добавляется «-api_demo» (смотрите журнал при запуске).", kind="toggle")
def hooks_args(api, log, on):
    """Перехват: изменение аргументов"""
    if on:
        def add_flag(args, game):
            new = (args + " -api_demo").strip()
            log(f"аргументы «{game['name']}»: «{args}» → «{new}»")
            return new
        STATE["args"] = api.filter("game_launch_args", add_flag)
    elif "args" in STATE:
        api.off(STATE.pop("args"))


@demo("hooks", "Своё событие", "Аддоны могут выбрасывать свои события — их услышат другие аддоны.")
def hooks_custom(api, log):
    """Своё событие"""
    api.once("showcase.ping", lambda text: log(f"получено событие showcase.ping: {text}"))
    api.emit("showcase.ping", "привет через шину событий")


# ===================================================================== #
#  💾 ДАННЫЕ
# ===================================================================== #
@demo("data", "Ключ-значение (kv)", "Простое хранилище внутри SQLite-файла аддона.")
def data_kv(api, log):
    """kv"""
    api.db.kv.set("последний_визит", datetime.datetime.now().isoformat(timespec="seconds"))
    log("записано и прочитано: " + str(api.db.kv.get("последний_визит")))


@demo("data", "Коллекция документов", "Вставка, поиск с операторами ($gt), сортировка, сумма — как в мини-MongoDB.")
def data_collection(api, log):
    """Коллекция"""
    col = api.db.collection("demo_scores")
    col.clear()
    for name in ("Аня", "Борис", "Вика", "Глеб", "Дарья"):
        col.insert({"name": name, "score": rnd().randint(10, 99)})
    top = col.find({"score": {"$gt": 50}}, sort="score", reverse=True, limit=3)
    log("топ (>50): " + ", ".join(f"{d['name']}={d['score']}" for d in top))
    log(f"сумма очков: {col.sum('score')}, документов: {col.count()}")


@demo("data", "Обычный SQL", "Если нужно — под рукой настоящий SQLite.")
def data_sql(api, log):
    """SQL"""
    api.db.execute("CREATE TABLE IF NOT EXISTS visits(ts TEXT)")
    api.db.execute("INSERT INTO visits VALUES (?)", (time.strftime("%H:%M:%S"),))
    rows = api.db.query("SELECT COUNT(*) AS n FROM visits")
    log(f"строк в таблице visits: {rows[0]['n']}")


@demo("data", "Кэш с временем жизни", "remember(): посчитать один раз, дальше брать из кэша 10 секунд.")
def data_cache(api, log):
    """Кэш"""
    t0 = time.time()
    value = api.cache.remember("медленно", 10, lambda: (time.sleep(0.4), "результат")[1])
    log(f"значение «{value}» получено за {time.time() - t0:.2f} с (повторите — будет мгновенно)")


@demo("data", "Настройки аддона", "api.settings хранит значения в settings.json аддона.")
def data_settings(api, log):
    """Настройки"""
    n = api.settings.get("runs", 0) + 1
    api.settings.set("runs", n)
    log(f"эта демо запущена {n} раз(а) за всё время")


# ===================================================================== #
#  🌐 СЕТЬ И СИСТЕМА
# ===================================================================== #
def _local_server():
    """Крошечный HTTP-сервер на 127.0.0.1, чтобы демо сети работало даже без интернета."""
    if "srv" in STATE:
        return STATE["srv"]
    import http.server
    import socketserver

    class Handler(http.server.BaseHTTPRequestHandler):
        def log_message(self, *a):
            pass

        def do_GET(self):
            body = json.dumps({"привет": "из локального сервера", "время": time.strftime("%H:%M:%S")},
                              ensure_ascii=False).encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

    srv = socketserver.TCPServer(("127.0.0.1", 0), Handler)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    STATE["srv"] = srv
    return srv


@demo("net", "HTTP-запрос (локальный сервер)", "api.http.get_json не вешает интерфейс: запрос идёт в фоне, ответ приходит в колбэк. Демо поднимает свой мини-сервер, интернет не нужен.")
def net_local(api, log):
    """HTTP без зависаний"""
    port = _local_server().server_address[1]
    api.http.get_json(f"http://127.0.0.1:{port}/", lambda data: log(f"ответ: {data}"),
                      lambda err: log(f"ошибка: {err}"))
    log("запрос отправлен — интерфейс не завис")


@demo("net", "HTTP-запрос в интернет", "Настоящий запрос к api.github.com. Если сети нет — вызовется on_error.")
def net_internet(api, log):
    """Интернет"""
    api.http.get("https://api.github.com/zen", lambda r: log(f"GitHub ответил ({r.status}): {r.text}"),
                 lambda e: log(f"нет сети или запрос заблокирован: {e}"), timeout=8)


@demo("net", "Сведения о системе и экранах", "api.system.info() и screens().")
def sys_info(api, log):
    """Система"""
    log(json.dumps(api.system.info(), ensure_ascii=False))
    for s in api.system.screens():
        log(f"экран {s['name']}: {s['width']}×{s['height']}, масштаб {s['scale']}")


@demo("net", "Список процессов", "processes(), is_running(), kill() — управление процессами.")
def sys_processes(api, log):
    """Процессы"""
    procs = api.system.processes()
    names = sorted({p["name"] for p in procs})
    log(f"процессов: {len(procs)}, уникальных имён: {len(names)}; примеры: {', '.join(names[:6])}")


@demo("net", "Буфер обмена", "Запишет в буфер обмена строку и прочитает её обратно (ваш буфер будет перезаписан!).")
def sys_clipboard(api, log):
    """Буфер обмена"""
    api.system.clipboard_set("Привет из Витрины API 🌌")
    log("в буфере: " + api.system.clipboard_get())


@demo("net", "Запуск команды в фоне", "api.system.run(..., on_done=...) — программа запускается, интерфейс не ждёт.")
def sys_run(api, log):
    """Запуск программы"""
    api.system.run([sys.executable, "--version"], on_done=lambda r: log("python: " + (r.stdout or r.stderr).strip()))


@demo("net", "Открыть папку аддона", "api.system.open_folder() — открывает папку в проводнике.")
def sys_open(api, log):
    """Папка в проводнике"""
    api.system.open_folder(api.root)


# ===================================================================== #
#  🔊 ЗВУК
# ===================================================================== #
@demo("audio", "Мелодия из кода", "Ни одного звукового файла: ноты синтезируются на лету.")
def audio_melody(api, log):
    """Синтез мелодии"""
    notes = [262, 330, 392, 523, 392, 330, 262]
    for i, hz in enumerate(notes):
        api.later(i * 150, lambda hz=hz: api.audio.tone(hz, 130, 0.3, "triangle"))
    log("играет арпеджио до-мажор")


@demo("audio", "Звуковые эффекты", "Лазер, взрыв, сирена — тон с «скольжением» и шум.", kind="choice",
      choices=["лазер", "взрыв", "сирена", "монетка"])
def audio_sfx(api, log, choice):
    """Эффекты"""
    a = api.audio
    if choice == "лазер":
        a.tone(900, 160, 0.3, "square", slide=-650)
    elif choice == "взрыв":
        a.noise(420, 0.45)
    elif choice == "сирена":
        a.tone(500, 600, 0.3, "saw", slide=500)
    else:
        a.tone(988, 70, 0.3, "square")
        api.later(80, lambda: a.tone(1319, 220, 0.3, "square"))


# ===================================================================== #
#  ⏱ КЛАВИШИ, ВРЕМЯ, КОМАНДЫ, АДДОНЫ
# ===================================================================== #
@demo("time", "Горячая клавиша Ctrl+Alt+S", "Включите и нажмите Ctrl+Alt+S в окне лаунчера.", kind="toggle")
def time_hotkey(api, log, on):
    """Горячая клавиша"""
    if on:
        STATE["hk"] = api.keys.bind("Ctrl+Alt+S", lambda: api.toast("⌨ Сработала горячая клавиша!"),
                                    context="application")
    elif "hk" in STATE:
        api.keys.unbind(STATE.pop("hk"))


@demo("time", "Отложенный вызов", "api.schedule.after(): сделать что-то через N секунд.")
def time_after(api, log):
    """Через 3 секунды"""
    api.schedule.after(3, lambda: api.toast("⏰ Прошло 3 секунды"))
    log("таймер запущен на 3 секунды")


@demo("time", "Повторяющийся таймер", "api.schedule.every(): 5 тиков раз в секунду, потом остановка.")
def time_every(api, log):
    """Таймер"""
    ticks = [0]

    def tick():
        ticks[0] += 1
        log(f"тик {ticks[0]}")
        if ticks[0] >= 5:
            timer.stop()
    timer = api.schedule.every(1, tick)


@demo("time", "Команда в палитре Ctrl+K", "Регистрирует команду «Привет из Витрины API». Откройте палитру и найдите её.")
def time_command(api, log):
    """Своя команда"""
    api.commands.register("hello", "Привет из Витрины API", lambda: api.toast("👋 Вы нашли команду в палитре!"),
                          keywords="демо витрина привет", icon="👋", group="Витрина API")
    log("команда зарегистрирована — нажмите Ctrl+K и введите «привет»")


@demo("time", "Открыть палитру команд", "Один аддон управляет другим: открываем встроенную палитру через api.addons.")
def time_palette(api, log):
    """Управление другим аддоном"""
    palette = api.addons.instance("builtin_command_palette")
    if palette:
        palette.open()
    else:
        log("палитра команд не загружена")


@demo("time", "Сервис между аддонами", "api.expose() открывает функцию, api.call() вызывает её — даже из другого аддона.")
def time_services(api, log):
    """expose / call"""
    api.expose("hello", lambda name="мир": f"Привет, {name}!")
    log(api.call("showcase_addon.hello", "аддон"))
    if api.addons.is_loaded("playtime_guard_addon"):
        log(f"из Стража времени: сегодня {api.call('playtime_guard_addon.today_minutes')} мин")


@demo("time", "Какие аддоны загружены", "api.addons.list() / info() — узнать про соседей.")
def time_addons(api, log):
    """Соседи"""
    for a in api.addons.list():
        info = api.addons.info(a)
        log(f"{info['name']}  v{info['version']}  [{info['style']}]")


# ===================================================================== #
#  🖼 ИНТЕРФЕЙС
# ===================================================================== #
@demo("ui", "Форма из описания", "Десять типов полей описываются списком — форма и сбор значений строятся сами.")
def ui_form(api, log):
    """Форма"""
    res = api.ui.form("Пример формы", [
        {"key": "name", "label": "Имя", "type": "text", "default": "Игрок"},
        {"key": "level", "label": "Уровень", "type": "int", "default": 5, "min": 1, "max": 99},
        {"key": "mode", "label": "Режим", "type": "choice", "choices": ["лёгкий", "обычный", "сложный"], "default": "обычный"},
        {"key": "sound", "label": "Со звуком", "type": "bool", "default": True},
        {"key": "color", "label": "Цвет", "type": "color", "default": "#ff7a18"},
        {"key": "notes", "label": "Заметки", "type": "multiline"},
    ])
    log("результат формы: " + (json.dumps(res, ensure_ascii=False) if res else "отмена"))


@demo("ui", "Диалоги", "confirm / prompt / choose — готовые окна вопросов.")
def ui_dialogs(api, log):
    """Диалоги"""
    if api.ui.confirm("Вам нравится API?", default=True):
        name = api.ui.prompt("Как вас зовут?", "Игрок")
        pick = api.ui.choose("Любимый жанр?", ["RPG", "Шутер", "Стратегия", "Платформер"])
        log(f"{name}: жанр {pick}")


@demo("ui", "Графики по вашей библиотеке", "bar / hbar / line / pie из ваших реальных данных о времени игры.")
def ui_charts(api, log):
    """Графики"""
    games = sorted(api.games.all(), key=lambda g: g.get("playtime_seconds", 0), reverse=True)[:7]
    top = [(g["name"][:10], round(g.get("playtime_seconds", 0) / 3600, 1)) for g in games] or \
          [("Пример А", 12), ("Пример Б", 7), ("Пример В", 3)]
    per_group = [(name, round(sum(g.get("playtime_seconds", 0) for g in lst) / 3600, 1))
                 for name, lst in api.games.groups().items()] or [("Группа 1", 5), ("Группа 2", 9)]
    w = QWidget()
    grid = QGridLayout(w)
    grid.addWidget(api.ui.chart("bar", top, "Часы по играм", unit="ч"), 0, 0)
    grid.addWidget(api.ui.chart("hbar", top, "То же, горизонтально", unit="ч"), 0, 1)
    grid.addWidget(api.ui.chart("line", top, "Линия", unit="ч"), 1, 0)
    grid.addWidget(api.ui.chart("pie", per_group, "По группам", unit="ч"), 1, 1)
    api.ui.window("📊 Графики", w, size=(860, 560))


@demo("ui", "Таблица игр", "api.ui.table(): клик по строке вызывает функцию.")
def ui_table(api, log):
    """Таблица"""
    rows = [[g["name"], api.games.group_of(g) or "—", g.get("playtime_seconds", 0) // 3600,
             "⭐" if g.get("favorite") else ""] for g in api.games.all()]
    table = api.ui.table(["Игра", "Группа", "Часы", "★"], rows,
                         on_row_click=lambda r: api.toast("Выбрано: " + rows[r][0]))
    api.ui.window("📋 Библиотека", table, size=(620, 420))


@demo("ui", "Значки NEW на карточках", "api.ui.badge() вешает метку на угол виджетов (и на новые тоже).", kind="toggle")
def ui_badges(api, log, on):
    """Значки"""
    if on:
        api.ui.badge("GameCard", "NEW", color="{{danger}}", corner="tr")
    else:
        api.design.reset()           # значки живут в тех же ресурсах и откатываются вместе с дизайном
        log("значки убраны (заодно сброшен дизайн)")


@demo("ui", "Встроенный браузер", "api.ui.web_view(): страница на HTML+JS внутри лаунчера. Цвета берутся из вашей темы.")
def ui_web(api, log):
    """Веб-страница"""
    c = api.design.get_colors()
    html = ("<body style='margin:0;background:@bg@;color:@text@;font-family:Segoe UI,sans-serif;"
            "display:flex;flex-direction:column;align-items:center;justify-content:center;height:100vh'>"
            "<h1 style='color:@accent@;font-size:42px;margin:0'>Привет из HTML!</h1>"
            "<p style='opacity:.7'>Эта страница красится в цвета вашей темы</p>"
            "<div id=t style='font-size:56px;font-weight:bold'></div>"
            "<script>setInterval(()=>t.textContent=new Date().toLocaleTimeString(),250)</script></body>")
    for k in ("bg", "text", "accent"):
        html = html.replace(f"@{k}@", c[k])
    view = api.ui.web_view(html=html)
    if view is None:
        log("QtWebEngine недоступен")
    else:
        api.ui.window("🌐 Веб-страница", view, size=(560, 380))


@demo("ui", "Окно прогресса", "api.ui.progress() + таймер — для долгих операций.")
def ui_progress(api, log):
    """Прогресс"""
    p = api.ui.progress("Имитация загрузки…")
    p.setValue(0)
    n = [0]

    def step():
        n[0] += 4
        p.setValue(min(100, n[0]))
        if n[0] >= 100:
            timer.stop()
            p.close()
            api.toast("✅ Готово")
    timer = api.every(50, step)


@demo("ui", "Всплывающие плашки", "api.toast() — быстрое уведомление поверх окна.")
def ui_toast(api, log):
    """Toast"""
    api.toast("✨ Это toast: появляется поверх окна и исчезает сам")


# ===================================================================== #
#  🕹 ХОЛСТ И ИГРЫ
# ===================================================================== #
@demo("canvas", "Фейерверк", "Холст + частицы + синтезированный звук. Кликайте по холсту — запускайте салют.")
def canvas_fireworks(api, log):
    """Салют"""
    cv = api.canvas
    c = cv.create(fps=60, bg="#05050f", min_size=(560, 360))
    parts, rockets = cv.Particles(), []
    colors = ["#ff4d6d", "#ffd166", "#06d6a0", "#4cc9f0", "#c77dff"]
    clock = [0.0]

    def launch(x, y):
        r = cv.Entity(c.width() / 2 + cv.random.uniform(-60, 60), c.height(), r=3)
        a = cv.angle_to(r.x, r.y, x, y)
        r.vx, r.vy, r.tx, r.ty = math.cos(a) * 520, math.sin(a) * 520, x, y
        rockets.append(r)

    @c.on_mouse
    def click(kind, x, y, button):
        if kind == "press":
            launch(x, y)

    @c.on_update
    def update(dt):
        clock[0] += dt
        if clock[0] > 0.9:
            clock[0] = 0
            launch(cv.random.uniform(80, c.width() - 80), cv.random.uniform(40, c.height() * 0.5))
        for r in rockets:
            r.move(dt)
            if cv.dist(r.x, r.y, r.tx, r.ty) < 14 or r.y < 0:
                r.alive = False
                parts.emit(r.x, r.y, 70, 230, 1.4, cv.random.choice(colors), 3.0, drag=0.94)
                api.audio.noise(110, 0.18)
        rockets[:] = [r for r in rockets if r.alive]
        for p in parts.items:
            p["vy"] += 200 * dt
        parts.update(dt)

    @c.on_draw
    def draw(p, w, h):
        for r in rockets:
            cv.Draw.glow_circle(p, r.x, r.y, 3, "#ffe066", 3)
        parts.draw(p)
        cv.Draw.text(p, w / 2, h - 28, "кликайте — салют", 13, "rgba(255,255,255,0.5)", align="center")
    api.ui.window("🎆 Фейерверк", c, size=(700, 460), on_close=c.stop)


@demo("canvas", "Звёздный полёт", "Псевдо-3D: звёзды летят на вас. Двигайте мышь вправо-влево — меняется скорость.")
def canvas_warp(api, log):
    """Гиперпрыжок"""
    cv = api.canvas
    c = cv.create(fps=60, bg="#02020a", min_size=(560, 360))
    r = cv.random
    stars = [[r.uniform(-1, 1), r.uniform(-1, 1), r.uniform(0.05, 1.0)] for _ in range(320)]
    speed = [0.2]

    @c.on_update
    def update(dt):
        speed[0] = 0.15 + abs(c.mouse[0] - c.width() / 2) / max(1, c.width()) * 2.2
        for s in stars:
            s[2] -= speed[0] * dt
            if s[2] <= 0.02:
                s[0], s[1], s[2] = r.uniform(-1, 1), r.uniform(-1, 1), 1.0

    @c.on_draw
    def draw(p, w, h):
        for x, y, z in stars:
            sx, sy = x / z * w / 2 + w / 2, y / z * h / 2 + h / 2
            ex, ey = (sx - w / 2) * (1 - speed[0] * 0.18) + w / 2, (sy - h / 2) * (1 - speed[0] * 0.18) + h / 2
            cv.Draw.line(p, sx, sy, ex, ey, f"rgba(255,255,255,{max(0.1, 1 - z):.2f})", 1 + (1 - z) * 2)
    api.ui.window("🚀 Звёздный полёт", c, size=(700, 460), on_close=c.stop)


@demo("canvas", "Рисовалка", "Рисуйте мышью — цвет переливается. Клавиша C — очистить.")
def canvas_paint(api, log):
    """Рисование мышью"""
    cv = api.canvas
    c = cv.create(fps=60, bg="#0b0b14", min_size=(560, 360))
    strokes, held = [], [False]

    @c.on_mouse
    def mouse(kind, x, y, button):
        if kind == "press":
            held[0] = True
            strokes.append([(x, y)])
        elif kind == "release":
            held[0] = False
        elif kind == "move" and held[0] and strokes:
            strokes[-1].append((x, y))

    c.on_key_down(lambda k: k == "c" and strokes.clear())

    @c.on_draw
    def draw(p, w, h):
        for si, stroke in enumerate(strokes):
            for i in range(1, len(stroke)):
                col = cv.qcolor(api.design.color.rainbow((si * 0.13 + i * 0.01) % 1.0)).name()
                cv.Draw.line(p, *stroke[i - 1], *stroke[i], col, 4)
        cv.Draw.text(p, 14, h - 26, "зажмите мышь и рисуйте · C — очистить", 12, "rgba(255,255,255,0.45)")
    api.ui.window("🖌 Рисовалка", c, size=(700, 460), on_close=c.stop)


@demo("canvas", "🚀 Космолёт (отдельный аддон)", "Полноценная аркада на api.canvas. Если аддон «Космолёт» загружен — переключаемся на него.")
def canvas_spaceship(api, log):
    """Игра на холсте"""
    if api.addons.is_loaded("spaceship_addon"):
        api.commands.run("spaceship_addon.play")
    else:
        log("аддон «Космолёт» не загружен: скопируйте addon_API/examples/spaceship_addon в папку addons/")


# ===================================================================== #
#  🛠 ИНСТРУМЕНТЫ
# ===================================================================== #
@demo("dev", "Инспектор элементов", "Ctrl+Shift+клик по любому элементу лаунчера покажет его селектор (и скопирует в буфер).", kind="toggle")
def dev_inspector(api, log, on):
    """Инспектор"""
    api.design.inspector(on)


@demo("dev", "Дерево виджетов лаунчера", "api.design.dump() — как устроен интерфейс (для поиска селекторов).")
def dev_dump(api, log):
    """Дерево"""
    for line in api.design.dump(depth=3).splitlines()[:25]:
        log(line)


@demo("dev", "Все objectName интерфейса", "По этим именам можно стилизовать: design.css(\"QFrame#GameCard\", ...).")
def dev_names(api, log):
    """Имена"""
    log(", ".join(f"{k} ({v})" for k, v in api.design.object_names().items()))


@demo("dev", "Скриншот лаунчера", "Сохраняет PNG окна лаунчера в папку data/ аддона.")
def dev_shot(api, log):
    """Скриншот"""
    path = api.design.screenshot()
    log("сохранено: " + path)


@demo("dev", "Консоль разработчика", "Живой Python внутри лаунчера (встроенный аддон). Там уже есть launcher, api, d, games…")
def dev_console(api, log):
    """Консоль"""
    con = api.addons.instance("builtin_dev_console")
    if con:
        con.open_console()
    else:
        log("консоль не загружена")


@demo("dev", "Открыть документацию API", "README со всеми функциями.")
def dev_docs(api, log):
    """Документация"""
    import addon_API
    import os
    api.system.open(os.path.join(os.path.dirname(addon_API.__file__), "README.md"))


@demo("dev", "Перезагрузить этот аддон", "api.reload(): аддон выгружается и загружается заново без перезапуска лаунчера.")
def dev_reload(api, log):
    """Горячая перезагрузка"""
    api.reload()


# ===================================================================== #
#  ИНТЕРФЕЙС ВИТРИНЫ
# ===================================================================== #
QSS = """
QFrame#DemoCard { background: {{surface_alt}}; border: 1px solid {{border}}; border-radius: 14px; }
QFrame#DemoCard:hover { border: 1px solid {{accent}}; }
QLabel#DemoTitle { font-size: 15px; font-weight: bold; }
QLabel#DemoDesc { color: {{text_muted}}; }
QLabel#DemoDone { color: {{success}}; font-weight: bold; }
QLabel#ShowcaseHead { font-size: 24px; font-weight: bold; color: {{accent_hover}}; }
QLabel#ShowcaseSub { color: {{text_muted}}; }
QLabel#ShowcaseSection { font-size: 13px; color: {{text_muted}}; }
QLabel#TourBanner { background: {{accent}}; color: #ffffff; border-radius: 14px; padding: 14px 22px;
                    font-size: 18px; font-weight: bold; }
QPlainTextEdit#ShowcaseCode, QPlainTextEdit#ShowcaseLog { font-family: Consolas, "DejaVu Sans Mono", monospace; font-size: 12px; }
"""


class DemoCard(QFrame):
    def __init__(self, owner, d):
        super().__init__()
        self.setObjectName("DemoCard")
        self.owner, self.d = owner, d
        lay = QVBoxLayout(self)
        lay.setContentsMargins(16, 12, 16, 12)
        top = QHBoxLayout()
        title = QLabel(d["title"])
        title.setObjectName("DemoTitle")
        self.done = QLabel("")
        self.done.setObjectName("DemoDone")
        top.addWidget(title, 1)
        top.addWidget(self.done)
        lay.addLayout(top)
        desc = QLabel(d["desc"])
        desc.setObjectName("DemoDesc")
        desc.setWordWrap(True)
        lay.addWidget(desc)
        row = QHBoxLayout()
        self.combo = None
        kind = d["kind"]
        if kind == "choice":
            self.combo = QComboBox()
            ch = d["choices"]() if callable(d["choices"]) else d["choices"]
            self.combo.addItems([str(c) for c in ch])
            row.addWidget(self.combo, 1)
        row.addStretch(1) if kind != "choice" else None
        code_btn = QPushButton("</> Код")
        code_btn.clicked.connect(lambda: owner.show_code(d))
        row.addWidget(code_btn)
        if kind == "toggle":
            self.btn = QPushButton("Выключено")
            self.btn.setCheckable(True)
            self.btn.toggled.connect(self._toggled)
        else:
            self.btn = QPushButton("▶ Запустить" if kind == "run" else "▶ Применить")
            self.btn.clicked.connect(self._clicked)
        row.addWidget(self.btn)
        lay.addLayout(row)
        self.mark(d["id"] in owner.tried)

    def _clicked(self):
        self.owner.run(self.d, self.combo.currentText() if self.combo else None)

    def _toggled(self, on):
        self.btn.setText("Включено ✔" if on else "Выключено")
        self.owner.run(self.d, on)

    def mark(self, tried):
        self.done.setText("✓ опробовано" if tried else "")


class Showcase(QWidget):
    def __init__(self, api):
        super().__init__()
        self.api = api
        self.tried = set(api.db.kv.get("tried", []))
        self.cards = {}                 # id -> DemoCard
        self.tour_timer, self.tour_i, self.tour_banner, self.tour_on = None, 0, None, False
        self._build()
        self.show_section(SECTIONS[0][0])
        self.log("Добро пожаловать! Выберите раздел слева и нажимайте кнопки — код каждой демо виден внизу.")

    # ------------------------------------------------------------ сборка
    def _build(self):
        api = self.api
        root = QVBoxLayout(self)
        head = QHBoxLayout()
        left = QVBoxLayout()
        h = QLabel("🌌 Витрина API")
        h.setObjectName("ShowcaseHead")
        s = QLabel(f"{len(DEMOS)} живых демо · рядом с каждой — настоящий код, который выполняется")
        s.setObjectName("ShowcaseSub")
        left.addWidget(h)
        left.addWidget(s)
        head.addLayout(left, 1)
        self.progress = QProgressBar()
        self.progress.setMaximum(len(DEMOS))
        self.progress.setFormat("опробовано %v из %m")
        self.progress.setMinimumWidth(230)
        head.addWidget(self.progress)
        self.tour_btn = QPushButton("🎬 Автотур")
        self.tour_btn.clicked.connect(self.toggle_tour)
        reset = QPushButton("♻ Сбросить всё")
        reset.clicked.connect(self.reset_all)
        head.addWidget(self.tour_btn)
        head.addWidget(reset)
        root.addLayout(head)

        body = QSplitter(Qt.Orientation.Horizontal)
        self.nav = QListWidget()
        self.nav.setObjectName("ShowcaseNav")
        self.nav.setFixedWidth(230)
        for key, icon, title, _ in SECTIONS:
            it = QListWidgetItem()
            it.setData(Qt.ItemDataRole.UserRole, key)
            self.nav.addItem(it)
        self.nav.currentRowChanged.connect(lambda i: self.show_section(SECTIONS[i][0]) if i >= 0 else None)
        body.addWidget(self.nav)

        right = QSplitter(Qt.Orientation.Vertical)
        self.scroll = QScrollArea()
        self.scroll.setWidgetResizable(True)
        self.holder = QWidget()
        self.cards_lay = QVBoxLayout(self.holder)
        self.section_label = QLabel()
        self.section_label.setObjectName("ShowcaseSection")
        self.section_label.setWordWrap(True)
        self.scroll.setWidget(self.holder)
        right.addWidget(self.scroll)

        bottom = QSplitter(Qt.Orientation.Horizontal)
        self.code_view = QPlainTextEdit()
        self.code_view.setObjectName("ShowcaseCode")
        self.code_view.setReadOnly(True)
        self.code_view.setPlaceholderText("Здесь появится код демо — нажмите «</> Код» или «Запустить»")
        self.log_view = QPlainTextEdit()
        self.log_view.setObjectName("ShowcaseLog")
        self.log_view.setReadOnly(True)
        self.log_view.setPlaceholderText("Журнал результатов")
        bottom.addWidget(self.code_view)
        bottom.addWidget(self.log_view)
        right.addWidget(bottom)
        right.setSizes([380, 220])
        body.addWidget(right)
        body.setSizes([230, 900])
        root.addWidget(body, 1)
        self.refresh_progress()

    # ------------------------------------------------------------ разделы
    def refresh_progress(self):
        self.progress.setValue(len(self.tried))
        for i, (key, icon, title, _) in enumerate(SECTIONS):
            ids = [d["id"] for d in DEMOS if d["section"] == key]
            done = sum(1 for x in ids if x in self.tried)
            self.nav.item(i).setText(f"{icon}  {title}   {done}/{len(ids)}")

    def show_section(self, key):
        i = [s[0] for s in SECTIONS].index(key)
        if self.nav.currentRow() != i:
            self.nav.blockSignals(True)
            self.nav.setCurrentRow(i)
            self.nav.blockSignals(False)
        while self.cards_lay.count():
            it = self.cards_lay.takeAt(0)
            if it.widget():
                it.widget().setParent(None)
                it.widget().deleteLater()
        self.cards = {}
        self.section_label.setText(SECTIONS[i][3])
        self.cards_lay.addWidget(self.section_label)
        for d in [x for x in DEMOS if x["section"] == key]:
            card = DemoCard(self, d)
            self.cards[d["id"]] = card
            self.cards_lay.addWidget(card)
            if d["kind"] == "toggle" and STATE.get("on:" + d["id"]):
                card.btn.blockSignals(True)
                card.btn.setChecked(True)
                card.btn.setText("Включено ✔")
                card.btn.blockSignals(False)
        self.cards_lay.addStretch(1)
        self.refresh_progress()

    # ------------------------------------------------------------ выполнение
    def log(self, text):
        if not isinstance(text, str):
            text = json.dumps(text, ensure_ascii=False, default=str)
        self.log_view.appendPlainText(f"[{time.strftime('%H:%M:%S')}] {text}")

    def show_code(self, d):
        self.code_view.setPlainText(f"# {d['title']}\n" + body_source(d["fn"]))

    def run(self, d, arg=None):
        self.show_code(d)
        try:
            if d["kind"] == "run":
                d["fn"](self.api, self.log)
            else:
                d["fn"](self.api, self.log, arg)
                if d["kind"] == "toggle":
                    STATE["on:" + d["id"]] = bool(arg)
        except Exception as e:
            traceback.print_exc()
            self.log(f"⚠ ошибка в демо: {e!r}")
            return False
        if d["id"] not in self.tried:
            self.tried.add(d["id"])
            self.api.db.kv.set("tried", sorted(self.tried))
            if d["id"] in self.cards:
                self.cards[d["id"]].mark(True)
            self.refresh_progress()
        return True

    def reset_all(self):
        """Выключить все переключатели, убрать демо-игру, откатить дизайн, остановить звук и тур."""
        self.stop_tour(silent=True)
        for d in DEMOS:
            if d["kind"] == "toggle" and STATE.get("on:" + d["id"]):
                try:
                    d["fn"](self.api, self.log, False)
                except Exception:
                    traceback.print_exc()
                STATE["on:" + d["id"]] = False
        games_remove(self.api, lambda *_: None)
        self.api.design.reset()
        self.api.audio.stop_all()
        self.close_demo_windows()
        self.show_section([s[0] for s in SECTIONS][max(0, self.nav.currentRow())])
        self.log("♻ всё сброшено")

    def close_demo_windows(self):
        from PyQt6.QtWidgets import QDialog
        for w in self.api.launcher.findChildren(QDialog):
            if w.windowTitle().split(" ")[0] in ("📊", "📋", "🌐", "🎆", "🚀", "🖌") and w.isVisible():
                w.close()

    # ------------------------------------------------------------ автотур
    def _tour_steps(self):
        api = self.api
        L = lambda fn, *a: (lambda: fn(api, self.log, *a))
        return [
            (3.4, "👋 Автотур: малая часть API — обычными вызовами кода", lambda: self.reset_quiet()),
            (3.4, "🎨 api.design.preset('glass') — весь лаунчер одной строкой", L(design_preset, "glass")),
            (3.4, "…а так выглядит 'neon': контуры и свечение", L(design_preset, "neon")),
            (3.4, "✨ Слои поверх окна: светлячки", L(design_overlay, "светлячки")),
            (4.0, "🌈 Акцент переливается — api.design.rainbow()", L(design_rainbow, True)),
            (3.2, "🎮 api.games.add() — игра появилась в библиотеке", L(games_add)),
            (2.6, "…и так же легко убирается", L(games_remove)),
            (3.4, "🔊 Звук синтезируется кодом, без файлов", L(audio_melody)),
            (4.2, "📊 Графики из ваших реальных данных", L(ui_charts)),
            (6.0, "🎆 api.canvas: частицы, физика и звук — салют!", lambda: (self.close_demo_windows(), canvas_fireworks(api, self.log))),
            (3.6, "⚡ И уже совсем другое настроение: cyberpunk", lambda: (self.close_demo_windows(), design_rainbow(api, self.log, False),
                                                                  STATE.__setitem__("on:design_rainbow", False), design_preset(api, self.log, "cyberpunk"))),
            (4.2, "🪝 Аддон может ПЕРЕХВАТЫВАТЬ запуск игр, хранить данные в SQLite, ходить в сеть, ловить клавиши…", lambda: None),
            (5.0, "🌌 Это лишь малая часть. Дальше — сами: 71 демо слева!", lambda: None),
        ]

    def reset_quiet(self):
        for d in DEMOS:
            if d["kind"] == "toggle" and STATE.get("on:" + d["id"]):
                d["fn"](self.api, self.log, False)
                STATE["on:" + d["id"]] = False
        self.api.design.reset()

    def toggle_tour(self):
        self.stop_tour() if self.tour_on else self.start_tour()

    def start_tour(self):
        self.reset_all()
        self.tour_on, self.tour_i = True, 0
        self.tour_btn.setText("⏹ Остановить тур")
        self.steps = self._tour_steps()
        self._tour_step()

    def _banner(self, text):
        L = self.api.launcher
        if self.tour_banner is None:
            from PyQt6.QtWidgets import QLabel as _L
            self.tour_banner = _L(L)
            self.tour_banner.setObjectName("TourBanner")
            self.tour_banner.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        b = self.tour_banner
        b.setText(text)
        b.adjustSize()
        b.move(max(10, (L.width() - b.width()) // 2), 14)
        b.show()
        b.raise_()

    def _tour_step(self):
        if not self.tour_on:
            return
        if self.tour_i >= len(self.steps):
            self.stop_tour()
            return
        secs, text, fn = self.steps[self.tour_i]
        self.tour_i += 1
        self._banner(text)
        self.log("🎬 " + text)
        try:
            fn()
        except Exception as e:
            traceback.print_exc()
            self.log(f"⚠ шаг тура: {e!r}")
        self.tour_timer = QTimer(self)
        self.tour_timer.setSingleShot(True)
        self.tour_timer.timeout.connect(self._tour_step)
        self.tour_timer.start(int(secs * 1000))

    def stop_tour(self, silent=False):
        was = self.tour_on
        self.tour_on = False
        if self.tour_timer is not None:
            self.tour_timer.stop()
            self.tour_timer = None
        if self.tour_banner is not None:
            self.tour_banner.hide()
            self.tour_banner.deleteLater()
            self.tour_banner = None
        self.tour_btn.setText("🎬 Автотур")
        if was and not silent:
            self.close_demo_windows()
            self.reset_quiet()
            self.api.toast("🌌 Тур окончен — всё возвращено как было")


# ===================================================================== #
#  АДДОН
# ===================================================================== #
class Addon(AddonBase):
    def on_load(self, api):
        self.api = api
        STATE.clear()
        api.settings.set("runs", api.settings.get("runs", 0) + 1)
        api.ui.add_style(QSS)
        self.view = Showcase(api)
        api.ui.add_tab(self.view, "🌌 Витрина API")
        goto = lambda: api.ui.select_tab("🌌 Витрина API")
        api.ui.add_burger_action("🌌 Витрина API", goto)
        api.commands.register("open", "Открыть Витрину API", goto, icon="🌌", group="Витрина API",
                              keywords="демо галерея возможности api")
        api.commands.register("tour", "Автотур по возможностям API", lambda: (goto(), self.view.start_tour()),
                              icon="🎬", group="Витрина API", keywords="демо показ экскурсия")

    def on_unload(self):
        self.view.stop_tour(silent=True)
        srv = STATE.get("srv")
        if srv is not None:
            threading.Thread(target=srv.shutdown, daemon=True).start()
            srv.server_close()
        STATE.clear()
