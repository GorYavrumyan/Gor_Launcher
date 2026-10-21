# addon_API — API для аддонов, тем и кастомизации GOR Launcher (300+ функций)

Главный принцип: **api — это удобство, а не ограничение.** Аддон по-прежнему
может получить весь объект лаунчера (`api.launcher`) и делать с ним что угодно.

## Установка
1. Сделайте бэкап проекта.
2. Распакуйте архив **поверх** папки лаунчера (согласитесь на замену 4 файлов:
   `bridge_loader.py`, `shared/style_loader.py`, `core/game_card.py`,
   `core/GorLauncher.py` — правки в них небольшие, 5–34 строки на файл).
3. Запустите как обычно. В шапке появится кнопка **🎨** (Theme Studio).

Старые аддоны ничего менять не должны — `init_addon(launcher)` работает как раньше.
Папка `web/` у аддона теперь необязательна (заглушка создаётся сама).

## Три способа написать аддон

```python
# 1. Классический (как раньше)
def init_addon(launcher):
    launcher.tabs.addTab(MyWidget(), "Мой аддон")

# 2. Классический + api
def init_addon(launcher, api):
    api.ui.add_tab(MyWidget(), "Мой аддон")

# 3. Новый (класс)
from addon_API import AddonBase, Events

class Addon(AddonBase):
    def on_load(self, api):
        api.on(Events.GAME_FINISHED, lambda sec, game: api.toast(game["name"]))
    def on_unload(self):
        pass   # всё созданное через api уберётся само
```

В `config.json` аддона: `name`, `version`, `author`, `description`, `start_file`,
а также необязательные `min_api` (минимальная версия API) и
`settings_defaults` (настройки по умолчанию). Рабочие примеры — в `examples/`.

## Справочник api

| Что | Как |
|---|---|
| Весь лаунчер | `api.launcher` |
| События | `api.on(event, cb, priority=0)`, `api.once`, `api.off(sub)`, `api.emit(event, ...)` |
| Настройки аддона | `api.settings.get(key, default)`, `.set(key, value)`, `.all()`, `.reset(key)` |
| Таймеры | `api.every(ms, fn)`, `api.later(ms, fn)` |
| Фоновая задача | `api.background(fn, on_done, on_error)` — `fn` в потоке, колбэки в интерфейсе |
| Лог (Control Center) | `api.log("текст", "info"/"change"/"request"/"error")` |
| Уведомления | `api.toast("текст")` (плашка в окне), `api.notify("текст")` (трей) |
| Игры | `api.games()`, `api.running_games()`, `api.data`, `api.save()` |
| Файлы | `api.path(...)`, `api.data_dir()` |
| Переводы | `api.add_translations({"ru": {...}, "en": {...}})`, `api.tr("ключ", x=1)` |
| Управление | `api.reload()`, `api.disable()` |

### api.ui — интерфейс
`add_tab(widget, title, index=None)`, `find_tab`, `rename_tab`, `hide_tab`,
`select_tab` — вкладки (в том числе **чужие**: можно переименовать или спрятать
встроенные); `add_header_button(text, cb, tooltip=...)` — кнопка в шапке;
`add_burger_action(text, cb)` — пункт в меню ☰; `add_card_action(text, cb)` —
пункт в контекстном меню карточки игры; `set_window_title`, `set_window_icon`;
`add_style(qss)` — свой QSS для всего лаунчера (работают `{{accent}}`, `{{bg}}`…);
`set_widget_style(widget, qss)`; `find(objectName)`; `insert(контейнер, виджет)`;
`toast(text)`. Всё, что создано через `api.ui`, **откатывается при выгрузке аддона**.

## api.design — кастомизация дизайна (100+ функций)

`api.design` — это «всё про внешний вид»: цвета, готовые стили компонентов, эффекты,
анимации, слои поверх окна, окно, шрифты, курсоры, инспектор. **Всё откатывается** при
выгрузке аддона или вызове `api.design.reset()`.

```python
d = api.design
d.preset("neon")                       # весь лаунчер в новом облике одной строкой
d.accent("#ff2d95")                    # свой акцентный цвет
d.cards(radius=26, glass=True)         # стеклянные карточки игр
d.hover_glow("GameCard")               # свечение карточек при наведении
d.appear("GameCard", "up")             # новые карточки выезжают каскадом
d.particles("fireflies", 40)           # светлячки поверх окна
d.css("QPushButton#RunGameBtn", radius=14, bg="{{accent}}",
      hover={"bg": "{{accent_hover}}"})  # и любой свой стиль
```

**Шаблоны цвета** работают в любом стиле и следуют за темой:
`{{accent}}` · `{{accent@25}}` (прозрачность 25%) · `{{surface+8}}` (светлее) · `{{bg-5}}` (темнее).
Роли: `bg surface surface_alt surface_hover border text text_muted accent accent_dark
accent_hover danger warning success editor_bg editor_accent`.

### Цвета
| Функция | Что делает |
|---|---|
| `get_colors()` / `set_colors({...})` / `set_color(role, c)` | читать и менять цвета ролей (живые, на диск не пишутся) |
| `accent(c)` | сменить акцент (тёмный и светлый оттенки считаются сами) |
| `palette(accent, "dark"/"light")` | **вся палитра из одного цвета** |
| `palette_from_hue(h)`, `random_palette(seed)` | палитра из оттенка / случайная |
| `dark_mode()`, `light_mode()` | перевести текущий акцент в тёмную/светлую палитру |
| `palette_from_image(path)`, `dominant_color(path)` | подобрать оформление под картинку |
| `transition_colors({...}, ms)` | плавный переход цветов |
| `animate_accent([цвета], period_ms, fps)`, `rainbow()`, `breathe_accent(a, b)` | живой, переливающийся акцент |
| `reset_colors()`, `stop_color_animation()` | вернуть как было |
| `save_as_theme(name)` | сохранить результат как обычную тему в `themes/` |
| `export_qss()` | итоговый QSS целиком |
| `design.color.*` | математика цвета: `lighten darken saturate hue_shift mix alpha invert grayscale contrast_text contrast_ratio is_dark complementary analogous triadic tetradic shades rainbow gradient radial_gradient palette_from_accent` |

### Стили
| Функция | Что делает |
|---|---|
| `css(selector, radius=.., bg=.., hover={..}, pressed={..}, ...)` | правило из Python (`radius=12` → `border-radius: 12px`) |
| `qss(raw)`, `remove(slot)`, `clear_style()` | свой QSS / убрать стиль |
| `widget_style(target, **props)` | стиль конкретных виджетов (и будущих) |
| `radius(scale=1.5)` / `radius(px=0)`, `sharp()`, `rounded()` | скругления **всего** лаунчера |
| `font(family, size, weight, selector)`, `font_scale(1.2)` | шрифт / размер всех шрифтов |
| `global_style(**props)`, `batch()` | свойства для всех виджетов / пересборка стиля один раз |

### Готовые компоненты
`buttons(style)` — `flat solid outline ghost neon glass gradient pill` (охватывает и «Запустить», и кнопки шапки) ·
`play_button` · `inputs(style)` — `filled outline underline glass` · `search_bar` · `combos` ·
`checkboxes` · `lists` · `menus` · `tooltips` · `progress` · `dialogs` · `labels` ·
`tabs(style)` — `pill underline boxed segmented minimal` · `scrollbars(style)` — `rounded thin hidden` ·
`cards` (карточки игр, `glass=True`) · `covers` · `card_text` · `group_headers` · `header` · `search_and_sort`.
Повторный вызов того же компонента **заменяет** прошлый, а не накладывается.

### Эффекты
`shadow` · `glow(pulse_ms=…)` · `hover_glow` · `hover_shadow` · `opacity` · `blur` · `colorize` · `clear_effects`.
Цель — виджет, `"ObjectName"`, `".QPushButton"` (по классу), функция-фильтр или список.
Эффекты, стили и анимации с `each(...)` подхватывают и **новые** виджеты (например, добавленные позже карточки).
На одном виджете одновременно работает один эффект.

### Анимации
`animate(target, prop, from, to, ms, easing, loop, pingpong)` · `fade_in` · `fade_out` · `slide_in` ·
`appear` (каскадное появление новых виджетов) · `pulse` · `shake` · `bounce` ·
`animate_tab_switch` · `stop_animations` · `easings()` (13 кривых).

### Слои поверх окна (мышь проходит сквозь)
`wallpaper(path, opacity, mode)` · `tint` · `vignette` · `scanlines` · `grid` · `noise` ·
`gradient_overlay` · `animated_gradient` · `particles(kind)` — `stars snow rain fireflies bubbles` · `clear_overlay`.

### Окно, шрифты, курсор
`window_opacity` · `always_on_top` · `window_size` · `min_size` · `center_window` · `fullscreen` ·
`screenshot` · `cursor(shape|картинка)` · `pointer_on_buttons` · `load_font(path)` · `app_font`.

### Инспектор — как узнать селектор нужного элемента
`inspector()` включает режим: **Ctrl+Shift+клик** по любому элементу показывает его класс,
`objectName` и свойства и копирует QSS-селектор в буфер. Ещё: `object_names()`, `dump()`, `find_all(target)`.

### Готовые стили целиком
`preset(name)`: `glass` · `neon` · `minimal` · `cyberpunk` · `terminal` · `soft` · `aurora`.
Пресеты — обычные наборы вызовов `api.design` (см. `design/presets.py`), их удобно копировать и дорабатывать.

## Рычаги: управление лаунчером и «всё что угодно»

Кроме оформления (`api.design`) у аддона есть подсистемы, которые превращают лаунчер в платформу.
Подсистемы загружаются лениво — не используете, не платите.

| Подсистема | Что даёт |
|---|---|
| `api.games` | **полное управление библиотекой**: найти, добавить, изменить, удалить, переместить, группы, запуск и остановка, случайная игра, статистика |
| `api.before / filter` | **перехват действий лаунчера**: отменить запуск игры, дописать аргументы запуска, свои точки через `api.allow` / `api.apply` |
| `api.db`, `api.cache` | своя **SQLite-база** (ключ-значение, коллекции документов, обычный SQL) и кэш с временем жизни |
| `api.http` | сеть без зависаний: `get`, `post`, `get_json`, `download` с прогрессом |
| `api.system` | запуск программ, процессы (`is_running`, `kill`), папки, ссылки, буфер обмена, экраны, простой |
| `api.audio` | звук: файлы и **синтезированные сигналы** (`tone`, `noise`) без файлов |
| `api.keys` | горячие клавиши |
| `api.schedule` | `at("22:30")`, `after`, `every`, `on_idle`, `on_active` |
| `api.commands` | общий реестр команд — их показывает **палитра Ctrl+K** |
| `api.addons`, `api.expose/call` | аддоны вызывают друг друга и ждут друг друга |
| `api.canvas` | **игровой холст**: цикл, клавиатура, мышь, частицы, звёздное небо, рисование |
| `api.account` | аккаунт: имя, язык (свой у каждого), личное хранилище предпочтений |
| `api.ui.*` (расширено) | `form`, `settings_tab`, `confirm/prompt/choose`, `pick_file`, `window`, `table`, `chart` (bar/hbar/line/pie), `web_view`, `badge`, `progress` |

### api.games
```python
g = api.games
g.all(); g.find("hades"); g.search("half"); g.favorites(); g.most_played(5); g.recent(); g.stats()
g.add("Моя игра", r"C:\Games\my.exe", group="Инди", favorite=True)
g.update("Hades", args="-windowed"); g.move("Hades", "Roguelike"); g.remove("Моя игра")
g.create_group("Новая"); g.rename_group("Новая", "Старая"); g.delete_group("Старая", keep_games=True)
g.launch("Hades"); g.stop("Hades"); g.is_running("Hades"); g.launch_random(favorites_only=True)
```
События: `game_added`, `game_removed`, `game_updated`, `game_moved`, `group_created`, `group_removed`,
`group_renamed`, `library_refreshed`. Ссылаться на игру можно словарём, `id` или названием.

### Перехватчики — вмешаться, а не только слушать
```python
api.before("before_game_launch", lambda game: ask_parent(game))       # вернул False - запуск отменён
api.filter("game_launch_args", lambda args, game: args + " -windowed") # изменить аргументы запуска
```
Встроенные точки: `before_game_launch(game)` и `game_launch_args(args, game)`. Свои точки делаются
так же: `if api.allow("my_action", data): ...` и `value = api.apply("my_filter", value)`.

### База данных
```python
sessions = api.db.collection("sessions")
sessions.insert({"game": "Hades", "seconds": 300})
sessions.find({"seconds": {"$gt": 60}}, sort="seconds", reverse=True, limit=5)   # $gt $gte $lt $lte $ne $in $contains ...
sessions.update({"game": "Hades"}, {"seconds": 0}); sessions.sum("seconds")
api.db.kv.set("last_run", 123); api.db.query("SELECT ...")
```

### Игровой холст (из лаунчера можно сделать космолёт)
```python
c = api.canvas.create(fps=60)
@c.on_update
def update(dt): ...                 # логика; c.is_down("left", "a") - клавиши (и в русской раскладке)
@c.on_draw
def draw(p, w, h): api.canvas.Draw.glow_circle(p, 100, 100, 12, "#00e5ff")
api.ui.add_tab(c, "🎮 Игра")       # цикл сам засыпает, когда вкладка скрыта
```
Есть `Entity`, `Particles`, `Starfield`, `Draw.*`, `clamp/lerp/wrap/dist/circles_hit`.
Готовый пример — `examples/spaceship_addon` («Космолёт»: инерция, астероиды, частицы, звук, рекорд).

### Встроенные аддоны
* **Палитра команд — `Ctrl+K`**: нечёткий поиск по играм, темам, стилям, вкладкам и командам любых аддонов.
* **Консоль разработчика — ``Ctrl+` ``**: живой Python внутри лаунчера (`launcher`, `api`, `d`, `games`, `themes`, `A(id)`).
* **Theme Studio — кнопка 🎨**.
* **Студия дизайна — меню ☰ или Ctrl+K → «Студия дизайна»**: настройка лаунчера мышью (палитра из акцента, пресеты,
  скругления, кнопки, вкладки, карточки, шрифты, эффекты, слои, прозрачность окна). Внизу — живой код `api.design`,
  который и применяется; экспорт: **тема**, **готовый аддон** (в `addons/`), код в буфер, рецепт `.json`. Кнопка 🎲 — случайный стиль.

### Примеры (`examples/`)
`classic_addon` · `modern_addon` · `theme_addon` · `design_addon` ·
**`spaceship_addon`** (игра на `api.canvas`) · **`playtime_guard_addon`** (`api.before`, `api.db`, `api.ui.chart`, `api.ui.form`, `api.schedule`, `api.expose`) ·
**`showcase_addon`** — **Витрина API**: 70 живых демо по ВСЕМ подсистемам, у каждой рядом показан настоящий исполняемый код,
счётчик «опробовано X из 70» (хранится в `api.db`) и **🎬 Автотур**, который сам показывает возможности по очереди.

Чтобы подключить пример: скопируйте его папку из `addon_API/examples/` в `addons/`, включите аддон в Control Center и перезапустите лаунчер.

## Аккаунты: язык и темы у каждого свои

У каждого аккаунта лаунчера теперь **своё** оформление и **свой** язык интерфейса. Всё лежит в
`accounts/<имя>/preferences.json`:

```json
{ "language": "en",
  "theme": {"active": "forest", "overrides": {"accent": "#ff2d95"}},
  "addons": {"my_addon": {"любой ключ": "значение"}} }
```

* **Язык.** Выбирается при создании аккаунта (в форме появился список языков) и меняется как раньше из меню ☰.
  После входа под аккаунтом включается именно его язык. Выбор больше не «откатывается» (раньше `change_language`
  забывал обновить данные в памяти, и следующее сохранение затирало новый язык).
* **Тема.** Активная тема и личные правки цветов у каждого аккаунта свои. Новые темы (Студия дизайна, Theme Studio,
  `api.design.save_as_theme`) сохраняются **в папку аккаунта** `accounts/<имя>/themes/` и видны только ему (в списке
  у них значок 👤). Общие темы из `themes/` видят все, но из аккаунта их удалить нельзя.
* **Другие окна** (редакторы, Control Center) берут тему и язык того же аккаунта: они наследуют переменную
  окружения `GOR_ACTIVE_ACCOUNT`, а если её нет — «последний активный» из `accounts_index.json`.
* **Старые аккаунты** (созданные до этой системы) при первом входе «усыновляют» то, что раньше было общим:
  язык из своего `games_data.json` и тему из общего `themes/_state.json`, а дальше живут со своими.
  **Новые** аккаунты стартуют со стандартной темой.
* Без системы аккаунтов (нет папки `accounts/`) всё работает по-старому, глобально.
* Настройки `api.settings`, база `api.db` и сами аддоны и так «по аккаунтам»: папка `addons/` у каждого своя.

Для аддонов — `api.account`:
```python
api.account.name                       # "Vova"
api.account.language()                 # "en"
api.account.languages()                # [{"code": "ru", "name": "Русский"}, ...]
api.account.set_language("es")         # запомнится за аккаунтом (restart=True — сразу перезапустить)
api.account.prefs.set("score", 42)     # личное хранилище аддона у ЭТОГО аккаунта
api.themes.account_name()              # чьи темы сейчас действуют
```
Ограничение: окно выбора аккаунта показывается ДО входа, поэтому оно на языке последнего активного аккаунта.

## События (`from addon_API import Events`)
| Событие | Аргументы |
|---|---|
| `GAME_STARTED` | `(game_data)` |
| `GAME_FINISHED` | `(duration_sec, game_data)` |
| `GAME_CARD_MENU` | `(menu, game_data, card)` — добавьте свои пункты в `menu` |
| `LAUNCHER_CLOSING` | `()` |
| `ADDONS_LOADED` | `()` |
| `THEME_CHANGED` | `(theme_id)` |
| `ADDON_LOADED` / `ADDON_UNLOADED` | `(folder)` |
| `LIBRARY_REFRESHED` | `()` |
| `GAME_ADDED` / `GAME_REMOVED` | `(game)` |
| `GAME_UPDATED` | `(game, changes)` |
| `GAME_MOVED` | `(game, group)` |
| `GROUP_CREATED` / `GROUP_REMOVED` | `(name)` |
| `GROUP_RENAMED` | `(old, new)` |
| `"*"` | любое событие: `(имя_события, ...)` |

Ошибка в обработчике не роняет лаунчер: пишется в лог аддона, а после 5 ошибок
подряд обработчик отключается.

## Темы
Тема — это папка `themes/<id>/` с `theme.json` (и, по желанию, `theme.qss`):

```json
{
  "name": "Моя тема", "author": "Я", "version": "1.0",
  "colors": {"accent": "#ff2d95", "bg": "#0d0014"},
  "font": {"family": "Segoe UI", "size": 13},
  "replace": {"#ffcc00": "#00ffaa"},
  "qss": "theme.qss"
}
```
Роли цветов: `bg, surface, surface_alt, surface_hover, border, text, text_muted,
accent, accent_dark, accent_hover, danger, warning, success, editor_bg, editor_accent`.
Не указанные остаются прежними; `accent_dark` и `accent_hover` считаются от `accent`.
В `theme.qss` работают `{{accent}}`, `{{bg}}`… и `{{theme_dir}}` (для картинок).

Тема перекрашивает ваш `style.qss` и работает во **всех** окнах лаунчера
(редакторы, Control Center), потому что подключена через `style_loader`.

Из аддона: `api.themes.apply(id)`, `.set_color("accent", "#fff")`, `.colors()`,
`.list()`, `.install(id, dict)`, `.save_current_as(name)`, `.import_file(path)`.
Готовые темы: Лесная, Светлая, Неоновый розовый, Ретро-терминал.

## Честные ограничения
* **Квадратные углы:** Qt рисует их, если `border-radius` больше половины высоты элемента.
  Поэтому у кнопок, полей и вкладок радиус ограничивается автоматически (≈15–18 px).
* **Обои и слои** рисуются поверх интерфейса полупрозрачно (интерфейс лаунчера непрозрачный),
  поэтому для обоев нужна небольшая `opacity`.
* Светлая палитра: в `style.qss` у ряда элементов жёстко прописан белый текст — `api.design`
  сам подправляет текст при светлом фоне; окна-редакторы (`#2d2d2d` в `style.qss`) остаются тёмными.
* **Горячие клавиши** работают только пока лаунчер в фокусе; системные (глобальные) Qt не поддерживает.
* **Консоль** даёт полный доступ к лаунчеру и ОС: не вставляйте в неё чужой код.
* **Перехватчики** есть в двух встроенных точках (`before_game_launch`, `game_launch_args`); новые точки
  добавляются так же — вызовом `addon_API.allow(...)` / `apply_filter(...)` в нужном месте кода лаунчера.
* `api.http` построен на стандартной библиотеке (urllib); `api.ui.web_view` требует QtWebEngine; звук — звуковое устройство.
* `animate_accent`/`rainbow` пересобирают стиль каждый кадр — держите fps небольшим (4–8).
* Темы перекрашивают `style.qss`. Цвета, зашитые прямо в Python-коде через
  `setStyleSheet(...)` (например, красная кнопка «Стоп»), темой не меняются.
* `api.ui.add_style` действует только в окне лаунчера; темы — везде.
* Это не песочница: watchdog **наблюдает** за аддонами, но не запрещает им ничего.
* Включение/выключение в Control Center по-прежнему применяется после
  перезапуска; горячая выгрузка доступна из кода (`api.disable()`, `manager.unload`).
