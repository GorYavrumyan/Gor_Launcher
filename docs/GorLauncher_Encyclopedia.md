# GorLauncher v1.0.0 — Техническая энциклопедия

> **Проект:** GorLauncher (автор — Gor Yavrumyan) · **Стек:** Python, PyQt6, QtWebEngine (Chromium), Qt Network, `cryptography` · **Лицензия по данным дампа:** MIT
> **Основа документа:** разбор реального исходного кода из загруженного дампа (82 файла, из них 45 модулей `.py`). Каждое утверждение ниже проверено по коду; места, где код расходится с вводным описанием проекта, вынесены в отдельный раздел 1.

---

<a id="toc"></a>
## Оглавление

| № | Раздел |
|---|---|
| 0 | [О документе: источник, метод, границы](#s0) |
| 1 | [Сверка: что заявлено и что реально в коде](#s1) |
| 2 | [Философия и архитектура](#s2) |
| 3 | [Структура проекта и карта 45 модулей](#s3) |
| 4 | [Жизненный цикл: от `launcher_start.py` до окна](#s4) |
| 5 | [Ядро GUI: `core/`](#s5) |
| 6 | [Редакторы: `editors/`](#s6) |
| 7 | [Данные: `games_data.json` и схемы](#s7) |
| 8 | [Встроенный браузер GOR_Brauzer (13 модулей)](#s8) |
| 9 | [Мульти-аккаунты: `account_manager.py`, `account_dialog.py`](#s9) |
| 10 | [Big Picture, геймпады, TV-стриминг (Sunshine/Moonlight)](#s10) |
| 11 | [Аддоны и безопасность: `addons_sys/`](#s11) |
| 12 | [Мультиязычность (i18n)](#s12) |
| 13 | [Темы и QSS](#s13) |
| 14 | [Обновление, экспорт, колесо фортуны, служебные модули](#s14) |
| 15 | [Веб-портал `WEB/`](#s15) |
| 16 | [Справочник API разработчика](#s16) |
| 17 | [Сборка в Windows EXE (PyInstaller) и деплой](#s17) |
| 18 | [Troubleshooting FAQ](#s18) |
| 19 | [Глоссарий](#s19) |
| A | [Приложение A. Полная карта ключей локализации (417 ключей)](#appA) |
| B | [Приложение B. Справочник сигнатур по всем модулям](#appB) |

---

<a id="s0"></a>
## 0. О документе: источник, метод, границы

### 0.1 Что именно было загружено

Загружены два **идентичных** файла `gorlauncher_full_documentation.md` и `gorlauncher_full_documentation_1.md` (одинаковый размер 1 465 693 байта и одинаковая контрольная сумма). Это не архив проекта, а один большой Markdown, внутри которого:

- **раздел 1** — краткое вводное описание «принципов проектирования»;
- **раздел 2** — дерево файлов (заявлено «350+ файлов»);
- **раздел 27** — полные исходные тексты 82 файлов проекта, каждый в блоке «### 27. Файл `путь`».

В оглавлении исходного файла перечислены разделы 3–26 (архитектура, браузер, аддоны и т. д.), но **самих этих разделов в файле нет**: после раздела 2 идёт сразу раздел 27. Поэтому единственным надёжным источником истины являются исходные тексты из раздела 27, и энциклопедия построена на них.

### 0.2 Состав дампа

| Группа | Файлы |
|---|---|
| Python-модули (45) | `launcher_start.py`, `bridge_loader.py`, `_i18n_merge.py`; `core/` (6); `editors/` (2); `extras/` (3); `remote/` (4); `shared/` (9); `addons_sys/` (3); `GOR_Brauzer/` (13); два примера аддона `addons/gor_style*/core/main.py` |
| QSS-стили и темы | `style.qss` (633 строки, 99 блоков), `themes/*/theme.json` (5 тем), `themes/light/theme.qss`, `themes/retro_terminal/theme.qss`, `themes/_state.json` |
| Локализация | `lang/ru.json`, `en.json`, `es.json`, `hy.json` (по 417 листовых ключей) |
| Веб-портал | `WEB/index.html`, `download.html`, `docs.html`, `docs-data.js`, `script.js`, `style.css` |
| Данные и настройки | `games_data.json`, `version.json`, `moonlight_hosts.json`, `GOR_Brauzer/settings.json`, `history.json`, `start_page.html`, `script.js`, `style.css`, `GOR_Profile/user_prefs.json`, резервная копия браузера `gor-browser-backup-….json`, `core/start_page.html`, `core/version.json` |
| Данные аддонов | `addons/gor_style/{config.json, activity.json, core/main.py, web/index.html}` и «копия» той же папки |

### 0.3 Что в дамп не попало

Код **ссылается** на модули, которых в дампе нет. Их поведение в этой энциклопедии описано только по тому, как их вызывает остальной код, и помечено как «вывод по использованию»:

| Отсутствует | Откуда вызывается | Что известно по вызовам |
|---|---|---|
| пакет `addon_API/` (`manager`, `emit_event`, `Events`, `prepare_addon_folder`, `AddonBase`, `allow`, `apply_filter`, `accounts`, `themes`, `design`) | `bridge_loader.py`, `game_card.py`, `GorLauncher.py`, `account_manager.py`, `lang_loader.py`, `style_loader.py`, `big_picture.py` | событийная шина, загрузчик аддонов, API оформления, предпочтения аккаунтов, движок тем |
| `platform_utils.py` (`is_game_process`, `launch_unix`, `kill_process_tree`, `make_dir_link`) | `game_card.py`, `account_manager.py` | кроссплатформенный запуск игры, остановка дерева процессов, создание ссылки на каталог |
| `runtime/` (встроенный Python), `favicon.ico`, `logo.png`, `Gor_Brauzer.ico`, `vot.user.js`, `adblock_domains.txt` | загрузчик, браузер, Sunshine | ресурсы и необязательные файлы |

### 0.4 Замечание о приватности дампа

В дамп попали **личные данные автора**: реальные пути к играм и профилю Windows в `games_data.json`, история посещений и закладки в `history.json` и в резервной копии браузера, IP-адрес в `moonlight_hosts.json`. В энциклопедию эти значения **не переносятся**; описаны только схемы. Если вы публикуете такой дамп, очистите эти файлы заранее.

---

<a id="s1"></a>
## 1. Сверка: что заявлено и что реально в коде

Вводный текст (раздел 1.1 исходного файла) и запрос на энциклопедию содержат формулировки, которые в коде реализованы иначе. Ниже — таблица расхождений. Это важно: энциклопедия, повторяющая неточные утверждения, ввела бы читателя в заблуждение.

| # | Заявлено | Как в коде на самом деле | Источник |
|---|---|---|---|
| 1 | «Двухфазная атомарная запись всей БД через `.tmp` и `.bak` + `os.replace`» | **`safe_json.py` пишет файл «на месте»** (`open(path, "w")`), а не через `.tmp`/`os.replace`. Причина указана в docstring: `games_data.json` в корне — **жёсткая ссылка** на файл аккаунта, и подмена через rename разорвала бы её. Защита: сначала полная сериализация в строку (при ошибке файл не тронут), резервная копия `.bak` не чаще раза в 60 с, при чтении битого файла — откат к `.bak`, иначе копия `…corrupt-<время>`. Схема `.tmp` + `fsync` + `.bak` + `os.replace` реально есть, но **только в хранилище паролей** (`browser_passwords.py`) | `shared/safe_json.py`, `browser_passwords.py::_write` |
| 2 | «NTFS Junctions (`mklink /J`) и POSIX Symlinks для `GOR_Profile`, `games_data.json`, `settings.json`» | Для **каталогов** (`GOR_Brauzer/GOR_Profile`, `addons/`) создаётся ссылка-каталог через `platform_utils.make_dir_link` (файл не в дампе; в `account_manager` есть также неиспользуемый помощник `_run_mklink`, а `_unlink_dir_point` умеет снимать симлинки). Для **файла** `games_data.json` используется **жёсткая ссылка** (`os.link`), с откатом на копирование. `settings.json` не линкуется: настройки браузера лежат внутри `games_data.json` в блоке `browser` | `shared/account_manager.py` |
| 3 | «Отслеживание процессов через `psutil` + `QThread`» | `psutil` **нигде не импортируется**. `ProcessMonitor(QThread)` ждёт `Popen.poll()`, затем опрашивает `tasklist /FO CSV /NH` (Windows) или `ps -e -o comm=` (Linux/macOS) каждые 5 с | `core/process_monitor.py` |
| 4 | «Переключение аккаунта < 50 мс» | Переключение — это **перезапуск процесса** лаунчера с аргументом `--account <имя>` (`restart_launcher`). Сама подмена ссылок быстрая, но «50 мс» в коде нигде не заявлено и не измеряется | `bridge_loader.py` |
| 5 | «Проверка релизов через GitHub Releases API» | Обновлятор читает сырой `version.json` из ветки `main` (`raw.githubusercontent.com`) и скачивает **zip всей ветки** (`codeload.github.com`). Releases API не используется; страница релизов открывается лишь кнопкой «Узнать больше» | `shared/updater.py` |
| 6 | «Карта всех 382 ключей локализации» | В каждом из четырёх языковых файлов **417 листовых ключей** (из них 2 служебных `_meta.*`, т. е. 415 переводимых строк) в 27 разделах. Расхождений между языками нет | `lang/*.json` |
| 7 | «`addon_watchdog.py` — система изоляции вызовов аддонов» | Это **наблюдатель (журналирование), а не песочница**: он подменяет `builtins.open`, `subprocess.Popen.__init__`, `socket.socket.connect`, `QTabWidget.addTab`, чтобы записывать действия аддонов в их `activity.json`. Вызовы он **не блокирует**; сам docstring честно оговаривает, что обход через `ctypes` возможен | `addons_sys/addon_watchdog.py` |
| 8 | «`ControlCenter.py` — разрешения» | Control Center включает/выключает аддоны (список `addons_list` в `games_data.json`) и показывает журнал активности. Системы «разрешений» с выдачей/отзывом прав в коде нет | `addons_sys/ControlCenter.py` |
| 9 | «Геймпады XInput / DirectInput» | Реализованы **XInput** (Windows) и **Linux `/dev/input/js*`**. DirectInput отсутствует | `shared/gamepad.py` |
| 10 | «Редактор игры: EXE, CWD, ENV, ARGS» | Поля редактора: имя, путь к EXE, корневая папка игры, иконка/обложка, группа, аргументы, «избранное». **Полей CWD и ENV нет**: рабочая папка вычисляется как каталог исполняемого файла | `editors/game_editor.py::get_data`, `game_card.py` |
| 11 | Статьи веб-портала (`docs-data.js`): «QWebChannel-мост», `process_manager.py`, `game_scanner.py`, `psutil`, AudioRelay | Описывают **иную архитектуру**, которой нет в исходниках (нет QWebChannel, нет сканера Steam/Epic/GOG, нет `psutil`). Портал рекламного/справочного характера и с кодом не сверен | `WEB/docs-data.js` |
| 12 | «GOR_Brauzer — 13 модулей» | Верно: 13 `.py`-файлов. Но **два из них — самостоятельные старые варианты** браузера (`GOR_Brauzer.py`, `GORbrauzer_desktop.py`), лаунчер их не импортирует; встроенный браузер — это `browser_widget.py::GORBrowser` | `core/GorLauncher.py` (импорт) |
| 13 | «Ctrl+Shift+K — оверлей поиска вики» | Верно: `WikiSearchOverlay`, поиск через Google с `site:<домен вики игры>` либо «`<игра> wiki <запрос>`» | `browser_widget.py` |
| 14 | «Fernet + PBKDF2» | Верно: PBKDF2-HMAC-SHA256, 390 000 итераций, соль 16 байт, Fernet (AES-128-CBC + HMAC-SHA256) | `browser_passwords.py` |

> **Как читать остальной документ.** Везде, где написано «в коде», имеется в виду проверенное чтение исходника. Там, где поведение выведено лишь из вызовов отсутствующих модулей, это оговорено явно.

---

<a id="s2"></a>
## 2. Философия и архитектура

### 2.1 Четыре идеи, на которых держится проект

1. **Один файл данных — одна правда.** Вся пользовательская информация лежит в `games_data.json`: игры, группы, история сессий, список включённых аддонов, язык, а также **весь блок браузера** (`"browser"`: закладки, история, настройки, группы вкладок, сессия, «сейчас играет»). Это упрощает перенос и бэкап, но создаёт задачу: несколько процессов пишут в один файл. Отсюда большая часть «защитного» кода (см. 2.2 и 2.5).
2. **Код читает «обычные» пути, а аккаунт подставляется ссылками.** Все модули открывают `games_data.json`, `GOR_Brauzer/GOR_Profile`, `addons/` по относительным путям. Мульти-аккаунты не переписывают эти модули — `activate_account` на уровне файловой системы направляет эти пути в папку выбранного аккаунта (см. раздел 9).
3. **Всё тяжёлое — в фоне.** Ожидание завершения игры, проверка обновлений, синхронизация со Sunshine, упаковка экспорта, запросы к Sunshine API, сопряжение Moonlight выполняются в `QThread`/отдельных процессах; GUI-поток только получает сигналы.
4. **Расширяемость без правки ядра.** Аддоны подключаются через `addon_API` с событиями и фильтрами (`game_started`, `game_finished`, `before_game_launch`, …), а оформление — через темы и QSS.

### 2.2 Запись данных: что реально гарантируется

Модуль `shared/safe_json.py` (73 строки) — единая точка записи/чтения JSON лаунчера.

**`write_json_inplace(path, data, **dump_kwargs)`**

| Шаг | Действие | Зачем |
|---|---|---|
| 1 | `json.dumps(data, ensure_ascii=False, indent=4)` целиком в строку | Если в данные попал несериализуемый объект — исключение **до** открытия файла, файл остаётся нетронутым |
| 2 | `_backup(path)` — копия в `<файл>.bak`, но не чаще `BACKUP_INTERVAL = 60` секунд | Откат при порче; ограничение частоты не даёт часто перезаписывать `.bak` |
| 3 | `open(path, "w")`, `write`, `flush` | Запись «на месте» **сохраняет inode** — жёсткая ссылка аккаунта остаётся целой |

**`read_json(path, default_factory=dict)`**

```
нет файла                  → default_factory()
файл читается             → данные
файл битый (ValueError)    → пробуем <файл>.bak → при успехе возвращаем его (сообщение в консоль)
.bak тоже не годится       → копируем битый файл в <файл>.corrupt-ГГГГММДД-ЧЧММСС и возвращаем default
OSError при чтении         → default_factory()
```

Побочный эффект, о котором стоит знать: «на месте» означает, что при внезапном отключении питания **в момент самой записи** файл может оказаться усечённым. Страхует именно `.bak` (и логика `read_json`), но не атомарность. Настоящая атомарная схема (`.tmp` → `fsync` → копия `.bak` → `os.replace`) применена только для `passwords.vault`, где потеря файла критична, а жёсткой ссылки нет (раздел 8.6).

### 2.3 Защита от «затирания» чужих данных внутри одного файла

Так как блок `"browser"` пишет сам браузер (напрямую в файл), а остальное — лаунчер, `GORLauncher.save_data()` перед каждой записью **перечитывает с диска блок `browser`** и подставляет его в память. Иначе любое сохранение лаунчера (конец игровой сессии, «избранное») откатывало бы закладки и историю браузера до состояния на момент загрузки. Аналогично `_write_now_playing` читает файл заново прямо перед записью и при невозможности прочитать — **пропускает** запись, а не пишет «почти пустой» файл. Тот же приём — в `lang_loader.set_language` и `ControlCenter._save_active_addons`: «не удалось прочитать → ничего не пишем».

### 2.4 Изоляция аккаунтов ссылками (кратко; подробно — раздел 9)

```
<корень проекта>/
├── games_data.json            ── ЖЁСТКАЯ ССЫЛКА ──▶ accounts/<имя>/games_data.json
├── addons/                    ── ссылка-каталог ──▶ accounts/<имя>/addons/
└── GOR_Brauzer/GOR_Profile/   ── ссылка-каталог ──▶ accounts/<имя>/GOR_Profile/
```

Жёсткая ссылка и junction в NTFS не требуют прав администратора и «Режима разработчика» (docstring `account_manager.py`). Это и объясняет, почему запись JSON сделана «на месте».

### 2.5 Многопоточность и процессы

Лаунчер — не один процесс. Редакторы и утилиты запускаются **отдельными процессами** (`run_editor_process`), а общаются с главным окном файлом данных и двумя локальными сокетами.

| Механизм | Где | Назначение |
|---|---|---|
| `ProcessMonitor(QThread)` | `core/process_monitor.py` | ждёт конец игры, считает длительность сессии |
| `EditorMonitor(QThread)` | там же | ждёт закрытия процесса редактора и сигналом `editor_closed` заставляет лаунчер перечитать данные |
| `UpdateWorker(QThread)` | `shared/updater.py` | проверка и установка обновления |
| `SyncWorker`, `RestartWorker`, `CredsWorker`, `_StatusWorker` | `remote/sunshine_control.py` | синхронизация игр в Sunshine, перезапуск, логин, статус |
| `ApiTask(QThread)` | `remote/tv_setup.py` | запросы Sunshine API без подвисания окна |
| `PairWorker(QThread)` | `remote/moonlight_cantrol.py` | сопряжение Moonlight (до 45 с) |
| `AppListWorker(QThread)` | `extras/big_picture.py` | получение списка приложений хоста |
| `PackerWorker(QThread)` | `extras/exporter_editor.py` | упаковка библиотеки в zip |
| `QLocalServer` «single instance» | `shared/single_instance.py` | один экземпляр лаунчера на папку проекта |
| `QLocalServer` «cover IPC» | `shared/cover_ipc.py` | редактор игры просит главный процесс открыть выбор обложки в браузере |
| `QUdpSocket` | `browser_broadcast.py` | LAN-рассылка вкладок (порт 51888 по умолчанию) |

Правило, соблюдаемое в коде: **ссылки на запущенные `QThread` хранятся** (`_game_monitors`, `_ACTIVE_WORKERS`), иначе сборщик мусора мог бы уничтожить работающий поток. Мониторы поддерживают `requestInterruption()`: сон разбит на кусочки по 0,25 с, чтобы поток можно было остановить при закрытии лаунчера.

### 2.6 Две «шины» между процессами

**Single instance (`shared/single_instance.py`).** Имя сокета: `"GorLauncher-" + md5(абсолютный_путь_проекта.lower())[:12]`. Новый экземпляр пытается подключиться (таймаут 800 мс); успех — посылает строку-команду (`show` или `bigpicture`) и завершается. Для `bigpicture` процесс **ждёт закрытия соединения**: Sunshine считает стрим живым, пока жив запущенный им процесс. Флаг `--new-instance` отключает проверку (его добавляет перезапуск, пока старый процесс ещё не вышел). Сервер повторяет попытку `listen()` до 20 раз с шагом 500 мс.

**Cover IPC (`shared/cover_ipc.py`).** Имя канала `GorLauncherCoverPickerIPC`, формат — JSON-строка на сообщение, разделитель `\n`; `try_decode_line(buffer)` извлекает одно полное сообщение и **пропускает битые и пустые строки**, не обрывая обработку следующих. Клиент ждёт подключения `CONNECT_TIMEOUT_MS = 1500`, при неудаче редактор откатывается на собственное окно `ImagePickerDialog`.

---

<a id="s3"></a>
## 3. Структура проекта и карта 45 модулей

### 3.1 Реальное дерево (по дампу)

Пометка «⛔» — файл/папка, на которые ссылается код, но которых в дампе нет.

```text
GorLauncher/
├── launcher_start.py        # точка входа №1: запускает bridge_loader.py встроенным Python из runtime/
├── bridge_loader.py         # точка входа №2: sys.path, аккаунт, лаунчер, аддоны, кнопки шапки, обновления
├── _i18n_merge.py           # одноразовая утилита слияния переводов (сам файл помечен "run once, then delete")
├── style.qss                # базовая тема оформления (633 строки)
├── version.json             # {"version": "..."} — читается лаунчером и обновлятором
├── games_data.json          # БД пользователя (при мульти-аккаунтах — жёсткая ссылка на accounts/<имя>/)
├── moonlight_hosts.json     # {"hosts": ["ip", ...]} — сохранённые хосты Moonlight
├── core/                    # главное окно и виджеты
│   ├── GorLauncher.py   game_card.py   group_widget.py   history_card.py
│   ├── launcher_utils.py    process_monitor.py    start_page.html   version.json
├── editors/                 # редакторы (запускаются отдельными процессами)
│   ├── game_editor.py   group_editor.py
├── extras/
│   ├── big_picture.py   fortune_wheel.py   exporter_editor.py
├── remote/
│   ├── sunshine_control.py   sunshine_api.py   moonlight_cantrol.py   tv_setup.py
├── shared/
│   ├── safe_json.py   lang_loader.py   style_loader.py   single_instance.py   cover_ipc.py
│   ├── account_manager.py   account_dialog.py   updater.py   gamepad.py
├── addons_sys/
│   ├── ControlCenter.py   addon_watchdog.py   addon_logger.py
├── GOR_Brauzer/             # 13 .py + start_page.html, script.js, style.css, settings.json, history.json
│   └── GOR_Profile/         # профиль Chromium (при мульти-аккаунтах — ссылка-каталог)
├── themes/                  # gorstyle/, neon_pink/, light/, retro_terminal/, forest/, _state.json
├── lang/                    # ru.json, en.json, es.json, hy.json
├── addons/                  # аддоны пользователя (папка на аккаунт)
├── accounts/                # accounts_index.json + <имя>/{games_data.json, GOR_Profile/, addons/, avatar.png, preferences.json}
├── WEB/                     # офлайн-портал: index/download/docs.html, docs-data.js, script.js, style.css
├── addon_API/               # ⛔ библиотека для аддонов и движок тем
├── platform_utils.py        # ⛔ кроссплатформенные помощники (запуск игры, ссылки, kill дерева)
├── runtime/                 # ⛔ встроенный Python (pythonw.exe) для Windows-сборки
└── favicon.ico, logo.png    # ⛔ ресурсы
```

`bridge_loader.py` и многие модули в начале файла добавляют в `sys.path` подпапки `core, shared, editors, remote, addons_sys, extras, GOR_Brauzer` и корень проекта — поэтому в коде используются «плоские» импорты (`from lang_loader import tr`), а не пакетные.

### 3.2 Карта всех 45 Python-модулей

| Модуль | Строк | Роль |
|---|---:|---|
| `launcher_start.py` | 31 | Запуск `bridge_loader.py` встроенным `pythonw.exe` (Windows) или системным/venv Python (Linux/macOS, `start_new_session=True`) |
| `bridge_loader.py` | 531 | Главный загрузчик: пути, выбор аккаунта, создание лаунчера, загрузка аддонов, кнопки шапки, перезапуск, проверка обновлений |
| `_i18n_merge.py` | 226 | Временный помощник слияния словарей переводов |
| `core/GorLauncher.py` | 1348 | Главное окно `GORLauncher(QMainWindow)`: вкладки, поиск, сортировка, трей, сессии, Big Picture, IPC обложек |
| `core/game_card.py` | 421 | `GameCard` — карточка игры: запуск/остановка, таймер, избранное, drag-n-drop |
| `core/group_widget.py` | 108 | `GroupWidget` — сворачиваемая группа, приём перетаскиваемых игр |
| `core/history_card.py` | 83 | `HistoryCard` — запись об игровой сессии |
| `core/launcher_utils.py` | 83 | `NO_GROUP_KEY`, `NO_WINDOW_FLAGS`, `find_favicon_path`, `load_pixmap_cached`, `universal_launch`, `run_editor_process` |
| `core/process_monitor.py` | 108 | `ProcessMonitor`, `EditorMonitor` — фоновые наблюдатели |
| `editors/game_editor.py` | 536 | `GameEditor`, `ImagePickerDialog` — карточка игры, выбор обложки |
| `editors/group_editor.py` | 133 | `GroupEditor` — создание/переименование группы |
| `extras/big_picture.py` | 1233 | `BigPictureWindow` — 10-foot интерфейс, геймпад, запуск стрима |
| `extras/fortune_wheel.py` | 471 | `FortuneWheelDialog`, `WheelWidget` — случайный выбор игры |
| `extras/exporter_editor.py` | 257 | `PackerGUI`, `PackerWorker` — экспорт игр в zip |
| `remote/sunshine_control.py` | 534 | Окно управления Sunshine, синхронизация игр |
| `remote/sunshine_api.py` | 257 | REST-клиент Sunshine |
| `remote/moonlight_cantrol.py` | 763 | `PCStreamManager`, `StreamModuleUI` — Moonlight (имя файла с опечаткой «cantrol» — это реальное имя) |
| `remote/tv_setup.py` | 357 | Вкладка «ТВ»: логин, приложение, PIN-сопряжение |
| `shared/safe_json.py` | 73 | Чтение/запись JSON |
| `shared/lang_loader.py` | 242 | Загрузчик переводов, `tr()` |
| `shared/style_loader.py` | 78 | Загрузка `style.qss` + наложение темы |
| `shared/single_instance.py` | 99 | Защита от двойного запуска |
| `shared/cover_ipc.py` | 59 | Протокол IPC «выбор обложки» |
| `shared/account_manager.py` | 454 | Аккаунты и ссылки |
| `shared/account_dialog.py` | 523 | Окна выбора/создания аккаунта и переключатель |
| `shared/updater.py` | 532 | Обновление из GitHub |
| `shared/gamepad.py` | 347 | XInput / Linux joystick |
| `addons_sys/ControlCenter.py` | 496 | Диспетчер аддонов + мониторинг |
| `addons_sys/addon_watchdog.py` | 175 | Автоматический перехват и логирование действий аддонов |
| `addons_sys/addon_logger.py` | 92 | Запись `activity.json` аддона |
| `GOR_Brauzer/browser_widget.py` | 2221 | **Ядро встроенного браузера** `GORBrowser`, `WikiSearchOverlay` |
| `GOR_Brauzer/browser_dialogs.py` | 893 | Окно настроек браузера (5 вкладок) |
| `GOR_Brauzer/browser_groups.py` | 579 | Группы вкладок, `GroupedTabBar`, `GroupsPanel` |
| `GOR_Brauzer/browser_passwords.py` | 482 | `PasswordVault` и диалоги |
| `GOR_Brauzer/browser_broadcast.py` | 349 | LAN-рассылка по UDP |
| `GOR_Brauzer/browser_adblock.py` | 332 | Блокировщик рекламы |
| `GOR_Brauzer/browser_startpage.py` | 180 | Генерация стартовой страницы |
| `GOR_Brauzer/browser_translate.py` | 160 | Интеграция переводчика VOT |
| `GOR_Brauzer/browser_constants.py` | 156 | Пути, ключи хранения, настройки по умолчанию |
| `GOR_Brauzer/browser_downloads.py` | 129 | Менеджер загрузок |
| `GOR_Brauzer/browser_page.py` | 45 | `GORWebPage` — обработка `createWindow` |
| `GOR_Brauzer/GOR_Brauzer.py` | 981 | *Старый самостоятельный* вариант браузера (не используется лаунчером) |
| `GOR_Brauzer/GORbrauzer_desktop.py` | 830 | *Старый самостоятельный* вариант на `QMainWindow` |
| `addons/gor_style/core/main.py` (+«копия») | 31 | Пример аддона оформления на `AddonBase` |

---

<a id="s4"></a>
## 4. Жизненный цикл: от `launcher_start.py` до окна

### 4.1 Шаг 0 — `launcher_start.py`

`main()` определяет `base_dir` по `sys.argv[0]` и запускает `bridge_loader.py` **отдельным процессом** (`subprocess.Popen(..., cwd=base_dir)`):

| ОС | Какой Python |
|---|---|
| Windows | `runtime/pythonw.exe` (без консоли) → иначе `runtime/python.exe` → иначе `sys.executable` |
| Linux/macOS | `.venv/bin/python3` → `runtime/bin/python3` → `sys.executable`/`python3`; `start_new_session=True` |

### 4.2 Шаг 1 — подготовка окружения в `bridge_loader.py` (на уровне модуля)

1. Добавление подпапок в `sys.path`.
2. **Фиксация рабочей папки**: `sys.argv[0]` делается абсолютным, затем `os.chdir(корень)`. Весь проект использует относительные пути (`"games_data.json"`, `"covers/"`, `"version.json"`), поэтому без этого запуск из другой папки (ярлык без «Рабочей папки», терминал) читал бы/создавал данные не там.
3. Импорт критических модулей (`style_loader`, `updater`, `lang_loader`, `addon_logger`, `addon_watchdog`, `addon_API`, `GorLauncher`); необязательные (`group_editor`, `game_editor`, `sunshine_control`, `exporter_editor`, `ControlCenter`) подключаются через `safe_import` — отсутствие модуля даёт сообщение, а не падение.

### 4.3 Шаг 2 — блок `if __name__ == "__main__"`

```
1. sys.argv += ['--enable-gpu-rasterization', '--enable-zero-copy', '--ignore-gpu-blocklist']
      (до создания QApplication — иначе Chromium эти флаги не прочитает)
2. app = QApplication(sys.argv); apply_global_style(app)           # style.qss + тема
3. Если НЕТ --new-instance:
       команда = "bigpicture" если есть --bigpicture, иначе "show"
       forward_to_running(корень, команда, wait_for_close=(команда == "bigpicture"))
       → True: sys.exit(0)  (команда ушла уже работающему лаунчеру)
4. Выбор аккаунта:
       --account <имя> и аккаунт существует → берём без окна
       иначе AccountDialog().exec(); отказ → sys.exit(0)
5. account_manager.activate_account(имя)        # подмена ссылок, язык, тема
6. launcher = GORLauncher()                     # читает games_data.json, строит UI
7. load_addons(launcher)                        # watchdog.install → цикл по addons/
8. addon_manager.load_builtin(launcher)         # встроенные аддоны (Theme Studio и др.)
9. emit_event(Events.ADDONS_LOADED)
10. add_restart_button, add_account_button, add_tray_button     # кнопки шапки
11. SingleInstanceServer(...).listen(); command → launcher.on_remote_command
12. --bigpicture → QTimer.singleShot(0, launcher.open_big_picture), иначе launcher.show()
13. check_updates_in_background(launcher)       # UpdateWorker(MODE_CHECK)
14. app.exec()
```

### 4.4 Загрузка аддонов `load_addons(launcher)` (подробно — раздел 11)

Для каждой подпапки `addons/` с `config.json` и `core/` создаётся запись; включённость определяется списком `addons_list` из `games_data.json` **с диска** (Control Center — отдельный процесс и пишет прямо в файл). Если ключа `addons_list` в файле нет вовсе (свежая установка) — включены **все** найденные аддоны. После загрузки `addons_list` перезаписывается списком реально загруженных, чтобы отключённые не «воскресали».

### 4.5 Перезапуск `restart_launcher(confirm=True, account=None)`

Поиск запускаемого файла по приоритету: `bridge_loader.exe` → `bridge_loader.py` → `GorLauncher.exe` → `core/GorLauncher.py` → `sys.executable + sys.argv`. К команде добавляются `--account <имя>` (если задан) и **всегда** `--new-instance`. На Windows процесс создаётся с `DETACHED_PROCESS | CREATE_NEW_PROCESS_GROUP | CREATE_BREAKAWAY_FROM_JOB`, затем `QApplication.closeAllWindows(); sys.exit(0)`. Так же работает смена языка (`change_language` → `set_language` → перезапуск без подтверждения).

---

<a id="s5"></a>
## 5. Ядро GUI: `core/`

### 5.1 `GORLauncher` (`core/GorLauncher.py`)

**Состояние экземпляра**

| Атрибут | Тип | Смысл |
|---|---|---|
| `data_file` | `str` | `"games_data.json"` (относительно корня) |
| `games_info` | `dict` | вся БД в памяти: `groups`, `standalone`, `history`, `browser`, … |
| `active_sessions` | `dict` | `id игры → {process, monitor, start_time, card}` — сейчас запущенные игры |
| `_game_monitors` | `set` | живые `ProcessMonitor` (удерживаются от GC) |
| `_child_processes` | `list[Popen]` | запущенные редакторы/утилиты — закрываются вместе с лаунчером |
| `big_picture`, `_bp_waiters` | окно / сокеты | режим Big Picture и ожидающие его закрытия повторные запуски |
| `tray_icon`, `_state_before_tray` | трей | сворачивание на время игры |
| `_tab_view_mode`, `_tab_view_index`, `_detached_windows` | режимы вкладок | обычный / развёрнутый / весь экран / отдельное окно |
| `_cover_ipc_*` | IPC | сервер выбора обложки |

**Вкладки главного окна:** Библиотека, Избранное, История, Браузер (`self.browser_tab = GORBrowser()` — браузер встроен в окно лаунчера как `QWidget`). Вкладку можно развернуть, вывести на весь экран или открепить в отдельное окно (`DetachedTabWindow`; при закрытии содержимое возвращается на прежнее место).

**Шапка:** счётчик «игр / часов», поле поиска (ширина 300, дебаунс 250 мс), сортировка, кнопки «Добавить игру» и «Добавить группу», кнопка аккаунта (слева), «Addon Manager», кнопка обновления (только если есть новая версия), «🔄 Перезапуск», «В трей», бургер-меню.

**Бургер-меню:** Big Picture (**F11**), Колесо фортуны, Sunshine, «ТВ» (Sunshine на вкладке `tv`), Moonlight, Экспорт, выбор языка (текущий отмечен ✅).

**Сортировка** (`sort_combo`, значение хранится в `currentData`): `default`, `name_asc`, `name_desc`, `playtime_desc`, `playtime_asc`, `newest` (разворот списка). Для групп время играния — сумма по играм группы.

**Ключевые методы**

| Метод | Что делает |
|---|---|
| `load_data()` | `read_json` с резервом; гарантирует ключи `history`, `groups`, `standalone`, `browser`; `migrate_ids()` присваивает `uuid4` играм без `id` |
| `save_data()` | подмешивает свежий блок `browser` с диска, затем `write_json_inplace` |
| `refresh_list()` | пересборка библиотеки/избранного/истории с учётом фильтра; в конце `emit_event("library_refreshed")` |
| `track_game_monitor(m)` | подписывает `on_session_finished` на `finished_playing` и хранит поток |
| `on_session_finished(duration, game)` | убирает сессию, вызывает `finalize_history_session`, шлёт событие `game_finished` |
| `finalize_history_session` | `+duration` к `playtime_seconds`, вставка записи в начало `history`, `save_data`, `refresh_list` |
| `on_game_session_changed()` | пока есть активные игры — свернуть в трей; иначе — вернуть окно (в Big Picture не вмешивается) |
| `on_game_started(game)` | пишет `browser.now_playing`; если у игры задан `guide_group_id` — просит браузер открыть группу вкладок |
| `move_game_to_group(id, group)` | перенос игры drag-n-drop |
| `launch_game_from_wheel(game)` | находит карточку **по id** (по имени — только если id нет) и вызывает её `handle_main_button()`; если карточки на экране нет — создаёт скрытую |
| `open_big_picture()` | `BigPictureWindow(self)`, `setQuitOnLastWindowClosed(False)`, окно лаунчера скрывается |
| `closeEvent()` | `emit_event("launcher_closing")`; фиксирует время ещё идущих игр; прерывает мониторы (`wait(1500)`); закрывает дочерние процессы |

### 5.2 `GameCard` (`core/game_card.py`)

Конструктор: `GameCard(game_data, parent_launcher, group_name=None)`.

**Клавиатура на карточке:** `Enter` — запуск/остановка; `Пробел` — избранное; `Delete` — удалить; `E` — редактировать; `F` — открыть папку игры; стрелки — перемещение фокуса. **Мышь:** двойной клик — запуск; перетаскивание (после порога `startDragDistance`) переносит `id` игры в `QMimeData.text`. **Контекстное меню** (для не запущенной игры): избранное, изменить, удалить, «📚 Гайды по игре» (привязка группы вкладок браузера), «Копировать путь»; аддоны могут дополнить меню событием `game_card_menu`.

**Алгоритм `handle_main_button()`**

```
если игра запущена (is_running):
    Windows → taskkill /F /T /PID <pid>   (дерево процессов), иначе kill_process_tree()
    остановить таймер, вернуть кнопку «Запустить», убрать сессию, on_game_session_changed()
    return
иначе:
    addon_API.allow("before_game_launch", game)  → False: запуск отменён аддоном
    если is_game_process(path):                  # исполняемый файл игры
        full_path = abspath(path); cwd = dirname(full_path)
        args = apply_filter("game_launch_args", game["args"], game)   # аддоны могут дописать аргументы
        Windows: Popen(list2cmdline([full_path]) + " " + args, cwd=cwd)
        иначе  : launch_unix(path, args)        # нативные файлы напрямую, .exe/.bat — через Wine/Proton
        старт живого таймера (1 с), кнопка «Остановить» (красная), кнопка паузы таймера
        ProcessMonitor(process, start_t, game) → launcher.track_game_monitor → .start()
        active_sessions[id] = {...}; on_game_started(); on_game_session_changed(); emit "game_started"
    иначе:
        universal_launch(path)                   # открыть как файл/папку средствами ОС
```

Важная деталь для Windows: аргументы **не** разбираются `shlex` (он «съедает» обратные слэши в путях), командная строка собирается строкой с сохранением кавычек пользователя.

### 5.3 `ProcessMonitor` и `EditorMonitor` (`core/process_monitor.py`)

`ProcessMonitor(process, start_time, game_data)` — сигнал `finished_playing(int, dict)`.

```
1. цикл: пока process.poll() is None → ждать 0.5 с (проверяя requestInterruption)
2. last_alive = now;  пауза 2 с
3. target_name = lower(basename(game_data["path"]))
4. пока имя образа есть в списке процессов ОС (проверка каждые 5 с):
       Windows: tasklist /FO CSV /NH → искать строку '"имя.exe",' (ТОЧНОЕ совпадение первого поля)
       иначе   : ps -e -o comm= → имя (или первые 15 символов) во множестве
       last_alive = now при каждом подтверждении
5. duration = max(0, int(last_alive - start_time));  emit finished_playing(duration, game_data)
```

Два нюанса, оговорённых в комментариях: (а) точное сравнение имени введено, потому что подстрока `launcher.exe` находилась внутри `epicgameslauncher.exe` и сессия не заканчивалась; (б) служебные паузы (2 с и опрос) в наигранное время не входят — длительность считается до момента **последнего подтверждённого «игра жива»**. Игры-лаунчеры, перезапускающие себя, учитываются именно благодаря шагу 4.

`EditorMonitor(process)` просто делает `process.wait()` и испускает `editor_closed` — по нему лаунчер перечитывает данные.

### 5.4 `GroupWidget`, `HistoryCard`

`GroupWidget(name, games, parent_launcher, is_favorite=False)`: сетка карточек по **4 в ряд** (`if c > 3`), заголовок сворачивается (▶/▼), контекстное меню «Переименовать / Удалить группу». Принимает drop только если группа не «Избранное»; перенос откладывается через `QTimer.singleShot(0, …)`, потому что он пересоздаёт все карточки, включая перетаскиваемую. Если после фильтра в группе нет видимых игр — группа скрывается.

`HistoryCard(entry, index, parent_launcher)`: одна запись истории; `Delete` или контекстное меню удаляют её (`delete_history_entry(index)`).

### 5.5 `launcher_utils.py`

| Имя | Описание |
|---|---|
| `NO_GROUP_KEY = "Без группы"` | внутренний ключ данных; **не переводится**, чтобы не ломать `games_data.json` |
| `NO_WINDOW_FLAGS` | `CREATE_NO_WINDOW` на Windows, иначе `0` — чтобы `tasklist`/`taskkill` не мигали консолью |
| `find_favicon_path()` | ищет `favicon.ico`: папка exe (frozen) → папка модуля → cwd → уровнем выше |
| `load_pixmap_cached(path)` | `lru_cache(512)` над `QPixmap` |
| `universal_launch(path)` | `os.startfile` / `open` / `xdg-open` |
| `run_editor_process(script_name, args=None, py_subdir=None)` | запуск редактора отдельным процессом: если рядом лежит `<имя>.exe` — он; иначе `python <py_subdir>/<имя>.py`. **`.exe` ищется плоско в корне**, независимо от раскладки исходников |

---

<a id="s6"></a>
## 6. Редакторы: `editors/`

Оба редактора — **отдельные процессы**. Они общаются с лаунчером через файл `games_data.json`, а `EditorMonitor` сообщает лаунчеру о закрытии окна.

### 6.1 `GameEditor`

Аргументы командной строки: `game_editor.py <имя> [<группа>] [<id>]`. Поиск игры: **сначала по `id`** (надёжно при одинаковых названиях), затем по имени; перебираются `standalone` и все `groups`, приоритет — группе из аргумента (раньше из «Избранного» открывалась пустая форма, т. к. такой группы в файле нет).

Поля формы (`get_data()`):

| Поле словаря | Источник в форме | Комментарий |
|---|---|---|
| `id` | `original_id` или новый `uuid4` | |
| `name` | имя | уникальность проверяет `name_exists` |
| `path` | путь к EXE/файлу | |
| `root_path` | корневая папка игры | используется экспортом (`PackerWorker`) |
| `icon` | путь к обложке | файл с диска, картинка из встроенного браузера или вручную |
| `group` | выпадающий список групп | `NO_GROUP_KEY` → `standalone` |
| `args` | аргументы запуска | выделено акцентной рамкой в QSS |
| `favorite` | чекбокс | |
| `playtime_seconds` | **не редактируется**, берётся из существующей записи | |

`save_and_accept()` перечитывает файл заново (лаунчер мог дописать время игры, браузер — свои данные) и при слиянии **сохраняет всё, чего форма не показывает**: `guide_group_id`, `wiki_url`, `forum_url`, `discord_url`, поля аддонов.

**Выбор обложки из браузера** (кнопка «Найти в браузере»): `GameEditor` подключается к `QLocalServer` лаунчера (`GorLauncherCoverPickerIPC`, ожидание 1500 мс). Лаунчер открывает во вкладке «Браузер» служебную вкладку выбора, скачивает выбранное изображение (`QNetworkAccessManager`) и шлёт редактору путь. Если лаунчер не отвечает — запасной вариант `ImagePickerDialog` (собственное окно с `QWebEngineView`; правый клик по картинке — «выбрать»).

### 6.2 `GroupEditor`

`group_editor.py [<имя_группы>]`. Запрещает пустое имя и зарезервированные названия `«без группы»`, `«избранное»` и переведённый заголовок отдельных игр. **Переименование сохраняет порядок групп**: словарь пересобирается с подстановкой нового имени на старое место. Запись — `write_json_inplace`.

---

<a id="s7"></a>
## 7. Данные: `games_data.json` и схемы

### 7.1 Верхний уровень

| Ключ | Тип | Кто пишет | Содержимое |
|---|---|---|---|
| `groups` | `{имя: [игра, …]}` | лаунчер, редакторы | порядок ключей = порядок отображения |
| `standalone` | `[игра, …]` | то же | игры «без группы» |
| `history` | `[запись, …]` | лаунчер | новые записи **в начале** |
| `addons_list` | `[str, …]` | `bridge_loader`, Control Center | имена папок включённых аддонов |
| `language` | `str` | `lang_loader` | `ru`/`en`/`es`/`hy` |
| `browser` | `dict` | **браузер** (и точечно лаунчер) | см. 8.2 |
| `big_picture` | `{last_tab: int}` | Big Picture | последняя открытая вкладка |

### 7.2 Запись игры

| Поле | Тип | Назначение |
|---|---|---|
| `id` | `str` (uuid4) | устойчивый идентификатор; проставляется миграцией, если нет |
| `name` | `str` | название |
| `path` | `str` | исполняемый файл |
| `root_path` | `str` | папка игры (для экспорта) |
| `icon` | `str` | путь к обложке |
| `args` | `str` | аргументы запуска |
| `favorite` | `bool` | «Избранное» |
| `playtime_seconds` | `int` | накопленное время |
| `guide_group_id` | `str` | *(необязательно)* id группы вкладок браузера, открывающейся при запуске |
| `wiki_url`, `forum_url`, `discord_url` | `str` | *(необязательно)* ссылки для оверлея Ctrl+Shift+K и виджета «Сейчас в игре» |

### 7.3 Запись истории

```json
{ "name": "…", "icon": "…", "date": "ДД.ММ.ГГГГ ЧЧ:ММ", "session_time": 3600 }
```

### 7.4 Прочие файлы данных

| Файл | Схема |
|---|---|
| `version.json` | `{"version": "<строка>"}` — сравнивается с удалённым `version.json` **по неравенству строк** (`remote != current`), а не по семантике версий |
| `moonlight_hosts.json` | `{"hosts": ["<ip>", …]}` |
| `themes/_state.json` | `{"active": "<id темы>", "overrides": {}}` — общее (старое) состояние тем; при аккаунтах тема хранится в `preferences.json` аккаунта |
| `accounts/accounts_index.json` | `{"accounts": {имя: {"salt": "...", "password_hash": "..."}}, "last_active": имя}` |
| `addons/<имя>/config.json` | см. 11.2 |
| `addons/<имя>/activity.json` | список `{type, message, time}`, не более 50 записей, новые первыми |
| `GOR_Brauzer/passwords.vault` | JSON `{salt, verifier, vault}` в base64/Fernet (8.6) |
| резервная копия браузера | `{gor_backup_version, exported_at, settings, history, bookmarks, tab_groups, extensions, start_page_raw}` |

---

<a id="s8"></a>
## 8. Встроенный браузер GOR_Brauzer (13 модулей)

### 8.1 Архитектура

Браузер — это `GORBrowser(QWidget)` из `browser_widget.py`. Он **не окно, а виджет** — именно поэтому лаунчер встраивает его как вкладку «Браузер» (`self.tabs.addTab(self.browser_tab, …)`). Движок — Chromium через `QWebEngineView`/`QWebEngineProfile`.

```
GORBrowser (browser_widget.py, 2221 строка)
 ├─ profile            QWebEngineProfile("GOR_Profile") — постоянный: cookies, localStorage, дисковый HTTP-кэш 256 МБ
 ├─ incognito_profile  QWebEngineProfile() без имени — «в памяти», свой экземпляр AdBlock
 ├─ GorAdBlockInterceptor  ×2 (обычный и приватный профиль)  ← browser_adblock.py
 ├─ GorAdBlockUpdater      фоновое обновление списков        ← browser_adblock.py
 ├─ install_vot_translator(profile, …)                         ← browser_translate.py
 ├─ PasswordVault          passwords.vault                      ← browser_passwords.py
 ├─ GorBroadcastService    UDP, порт 51888                      ← browser_broadcast.py
 ├─ tab_groups + GroupsPanel + GroupedTabBar                    ← browser_groups.py
 ├─ DownloadManager                                             ← browser_downloads.py
 ├─ BrowserSettingsWindow (5 разделов)                          ← browser_dialogs.py
 ├─ GORWebPage             перехват createWindow                ← browser_page.py
 ├─ write_start_page()     стартовая страница                   ← browser_startpage.py
 └─ WikiSearchOverlay      Ctrl+Shift+K
```

**Профиль и производительность (из `__init__`).** Включены: постоянные cookies, `LocalStorageEnabled`, `JavascriptCanAccessClipboard`, плавная прокрутка, поддержка полноэкранного режима, JS, автозагрузка изображений, `LocalContentCanAccessRemoteUrls` (чтобы локальная стартовая страница подтягивала иконочные шрифты с CDN). Дисковый HTTP-кэш: `DiskHttpCache`, максимум `256 * 1024 * 1024`. Глобально лаунчер добавляет флаги Chromium `--enable-gpu-rasterization --enable-zero-copy --ignore-gpu-blocklist` (раздел 4.3).

**Порядок инициализации важен:** перехватчик AdBlock ставится на профиль **ровно один раз и до первой вкладки** (требование QtWebEngine); включение/выключение делается через `set_enabled()` без пересоздания.

### 8.2 Хранение: блок `"browser"` внутри `games_data.json`

Браузер не создаёт отдельных файлов для данных. Константы `browser_constants.py` — это **ключи под-блока**, а не имена файлов (исторически они были именами файлов):

| Константа | Ключ в `browser` | Содержимое |
|---|---|---|
| `BOOKMARKS_FILE` | `bookmarks` | закладки |
| `HISTORY_FILE` | `history` | `{title, url, time, favicon}` |
| `PASSWORDS_FILE` | `passwords` | константа объявлена, но в коде **не используется** (реальное хранилище — файл `passwords.vault`) |
| `SETTINGS_FILE` | `settings` | настройки (таблица 8.3) |
| `EXTENSIONS_FILE` | `extensions` | пользовательские JS-скрипты |
| `TAB_GROUPS_FILE` | `tab_groups` | группы вкладок |
| `SESSION_FILE` | `session` | `{active: bool, tabs: [{url, pinned}]}` |
| *(пишет лаунчер)* | `now_playing` | `{name, icon, started, wiki_url, forum_url, discord_url}` |

Методы `load_data(key)` / `save_data(key, value)` читают файл заново и пишут только свой ключ (`_read_full_data(strict=…)`), чтобы не затереть остальную БД.

Корневой каталог данных браузера `BASE_DIR`: при запуске из `.exe` — папка рядом с `exe` (а не временная `_MEIPASS`, иначе настройки терялись бы при каждом запуске). `get_resource_path()` для упакованных ресурсов — `sys._MEIPASS`.

### 8.3 Настройки по умолчанию (`DEFAULT_SETTINGS`)

| Ключ | По умолчанию | Назначение |
|---|---|---|
| `theme_color` | `#4c6ef5` | акцентный цвет |
| `top_bar_color` | `#16171a` | цвет верхней панели |
| `font_family` / `font_size` | `Segoe UI` / `10` | шрифт интерфейса и страниц |
| `search_engine` | `Google` | движок адресной строки (`Google`, `Yandex`, `Bing`, `DuckDuckGo`) |
| `show_clock`, `show_title`, `show_todo` | `True` | блоки стартовой страницы (`show_todo` — на деле «заметки») |
| `ui_opacity` | `0.9` | прозрачность интерфейса стартовой страницы |
| `bg_image`, `bg_data`, `bg_type` (`image`/`html`/`""`), `bg_blur` (px), `bg_interactive` | пусто / 0 / `False` | фон стартовой страницы (картинка или HTML) |
| `brand_text` | `GOR // OS` | надпись в шапке стартовой страницы |
| `custom_engines`, `active_engine_idx` | `[]`, `0` | пользовательские поисковики `{name, url, param}` |
| `adblock_enabled` | `True` | блокировщик рекламы |
| `vot_enabled` | `True` | переводчик видео |
| `broadcast_enabled`, `broadcast_port` | `True`, `51888` | LAN-рассылка |
| `lan_clipboard_enabled`, `lan_bookmark_sync_enabled` | **`False`** | общий буфер и синхронизация закладок — **только по явному согласию** |
| `adblock_dynamic_update_enabled`, `adblock_update_interval_hours`, `adblock_last_update`, `adblock_update_url` | `True`, `24`, `""`, `""` | фоновое обновление списков (пустой URL → StevenBlack/hosts) |
| `tab_suspend_enabled`, `tab_suspend_minutes` | `True`, `15` | автовыгрузка неактивных вкладок |

Дополнительные константы: `TAB_GROUP_COLORS` (8 цветов), `DEFAULT_BROADCAST_PORT = 51888`, `NOT_RESPONDING_TIMEOUT_MS = 15000`, `ZOOM_STEP = 0.1`, `ZOOM_MIN = 0.25`, `ZOOM_MAX = 4.0`.

### 8.4 AdBlock Engine (`browser_adblock.py`)

Двухуровневый:

**Уровень 1 — сетевой перехватчик `GorAdBlockInterceptor(QWebEngineUrlRequestInterceptor)`.**

| Особенность | Деталь |
|---|---|
| Что режет | подзапросы к доменам из `BLOCKED_DOMAINS` (`info.block(True)`), счётчик `blocked_count` |
| Что **не** режет | запросы **главного фрейма** (`ResourceTypeMainFrame`): прямой переход пользователя на рекламный домен — его выбор |
| Алгоритм поиска | `_host_is_blocked(host)` проверяет сам хост и все родительские домены (`a.b.example.com → b.example.com → example.com`) — число проверок равно числу меток. Раньше перебирался весь набор на каждый запрос (сотни тысяч доменов после загрузки динамического списка) |
| Встроенный список | 46 доменов: Google Ads/Analytics, Яндекс (`an.yandex.ru`, `mc.yandex.ru`…), крупные сети (Criteo, Taboola, Outbrain…), соцсети-трекеры, popunder-сети |
| Расширение | файл `adblock_domains.txt` (по домену на строку, `#` — комментарий) — `load_extra_blocklist(base_dir)`; кэш `adblock_dynamic_domains.txt` — `load_dynamic_blocklist_cache` |

**Динамический список `GorAdBlockUpdater`.** По таймеру (проверка раз в час, обновление по `adblock_update_interval_hours`, первый запуск через 5 с после старта) асинхронно (`QNetworkAccessManager`) скачивает `https://raw.githubusercontent.com/StevenBlack/hosts/master/hosts`. `_parse_blocklist_text` понимает формат hosts (`0.0.0.0 домен`, `127.0.0.1 домен`) и «домен на строку», пропуская `localhost`, `broadcasthost` и т. п. Результат подмешивается в `BLOCKED_DOMAINS`, сигнал `update_finished(added, error)`, кэш пишется на диск (отсортированный). Повторный `update_now()` отменяет предыдущий запрос; ответ привязан к своему `reply` в замыкании.

**Уровень 2 — косметический фильтр.** JS `_COSMETIC_JS`, внедряется `install_cosmetic_filter(profile, enabled)` через `QWebEngineScript` (имя `gor-adblock-cosmetic`, `DocumentReady`, `ApplicationWorld`, во всех фреймах). Прячет (`display:none !important`) блоки по селекторам вида `[id*="google_ads"]`, `[class*="advert"]`, `ins.adsbygoogle`, `div[id^="div-gpt-ad"]`, `.ad-slot`… и следит `MutationObserver` за динамически добавляемыми. Повторная установка сначала удаляет старый скрипт (нет дублей).

> Ограничение: это не EasyList — нет ни правил по URL-путям, ни исключений. Блокируются домены целиком.

### 8.5 LAN Broadcast (`browser_broadcast.py`)

**Формат пакета** (JSON UTF-8, один UDP-датаграмм; порт по умолчанию **51888**):

```json
{ "app": "gor-browser", "type": "tab|group|clipboard|bookmark_sync",
  "name": "…", "urls": ["https://…"], "sender": "ПК (PID 1234)",
  "instance_id": "<uuid процесса>", "msg_id": "<uuid сообщения>" }
```

| Метод `GorBroadcastService` | Действие |
|---|---|
| `start_listening()` | `QUdpSocket.bind(AnyIPv4, port, ShareAddress \| ReuseAddressHint)`, буфер приёма 4 МБ; безопасно вызывать повторно |
| `set_port(port)` | сменить порт и перепривязаться |
| `send_tab(url, title)`, `send_group(group)` | отправка вкладки/группы |
| `send_clipboard(text)` | общий буфер обмена (только если включён у обеих сторон) |
| `send_bookmarks(list)` | закладки режутся на части до `_MAX_DATAGRAM_JSON = 8000` байт, части уходят с интервалом `25 мс` |
| сигнал `broadcast_received(dict)` | входящий и **уже очищенный** пакет |

**Как отправка устроена:** каждый пакет уходит и на `255.255.255.255:порт` (Broadcast), и на `127.0.0.1:порт` (loopback-дубль, чтобы два процесса на одном ПК видели друг друга). Получатель отсеивает **своё эхо по `instance_id`** (а не по имени ПК — иначе два браузера на одной машине глушили бы друг друга) и дубли по `msg_id` (очередь `deque(maxlen=128)`).

**Безопасность (пакеты не аутентифицированы и приходят от кого угодно в сети):** `sanitize_payload` оставляет только ссылки `http://`/`https://` длиной ≤ 2048, максимум 100 ссылок, имя ≤ 200 символов, отправитель ≤ 80; пакеты без маркера `"app": "gor-browser"` отбрасываются; пакет без допустимых URL — отбрасывается. Так `javascript:`, `file:`, `data:` и «шторм» из тысяч вкладок отсекаются. Входящие вкладки/группы показываются тостом `BroadcastToast` («Открыть все», «Сохранить в JSON»); буфер обмена и закладки обрабатываются молча.

**Что нужно открыть в сети:** UDP-порт 51888 (входящий) в брандмауэре; широковещание работает только внутри одной подсети.

### 8.6 Менеджер паролей Vault (`browser_passwords.py`)

**Схема шифрования**

```
мастер-пароль (на диск не пишется)
   │  PBKDF2-HMAC-SHA256, 390 000 итераций, соль 16 байт (secrets.token_bytes)
   ▼
32-байтный ключ → base64url → Fernet (AES-128-CBC + HMAC-SHA256)
   ├─ verifier = Fernet.encrypt(b"gor-browser-vault-ok")   ← проверка пароля без парсинга всего vault
   └─ vault    = Fernet.encrypt(JSON-список записей)

файл passwords.vault = {"salt": b64, "verifier": "...", "vault": "..."}
```

| Элемент | Деталь |
|---|---|
| Запись | `{id (hex 8 байт), site, username, password, note}` |
| Расшифрованные данные | **только в ОЗУ** на время разблокировки (`_entries`); `lock()` зануляет ключ и записи (вызывается при штатном закрытии браузера, `mark_session_closed_cleanly`) |
| `unlock(pw)` | возвращает `False` (не исключение) при неверном пароле/повреждении |
| `change_master_password(new)` | перешифровывает записи новой солью |
| Запись файла `_write` | `.tmp` → `flush` + **`os.fsync`** → копия предыдущей версии в `.bak` → `os.replace` (**единственное место проекта с настоящей атомарной записью**) |
| Генератор | `generate_strong_password(length=16)`, минимум 8; по символу каждого класса + `secrets.SystemRandom().shuffle` |
| Мастер-пароль | при создании не короче 6 символов; **восстановить забытый невозможно** |
| Буфер обмена | при копировании пароля через 30 с буфер очищается, если в нём всё ещё этот пароль |

**Сознательное ограничение (из docstring):** это *хранилище* с ручным вводом/копированием, а **не автозаполнение** форм и не перехват логинов.

### 8.7 Группы вкладок и сессии (`browser_groups.py` + `browser_widget.py`)

**Группа вкладок:**

```json
{ "id": "grp_<timestamp_ms>", "name": "Код", "color": "#4c6ef5",
  "emoji": "🗂️", "urls": ["https://…"], "created": "2026-09-17 14:05" }
```

- `GroupedTabBar(QTabBar)` рисует под вкладками группы цветную полосу (как в Firefox/Chrome) и позволяет сворачивать группу (`collapsed_group_ids` — состояние сессии, на диск не пишется).
- `GroupsPanel` (боковая панель): список групп, «Сохранить текущую сессию как группу» (`save_current_session` — все открытые не-инкогнито вкладки без стартовой), правка/удаление, перетаскивание, двойной клик — открыть. Палитра: 8 цветов, быстрые эмодзи (12 штук), `DEFAULT_GROUP_EMOJI = "🗂️"`.
- Функции `new_group_record(name, color, urls, emoji=None)`, `group_emoji`, `group_display_name`.
- Связь с играми: у игры может быть `guide_group_id`; при запуске лаунчер вызывает `GORBrowser.open_group_by_id` — «авто-группа Гайды по игре».
- Рассылка: `broadcast_group_by_id`, `send_current_tab_to_network`.

**Session Restore.** При старте браузер читает `session`. Если `active == True` (прошлый запуск не закрылся штатно) — после открытия предлагает «Восстановить N вкладок?». Сразу пишет `{"active": True, …}`. Список вкладок сохраняется с задержкой 1,5 с (`_schedule_session_save`, debounce); инкогнито и стартовая страница не сохраняются; закреплённые вкладки восстанавливаются закреплёнными. `GORLauncher.closeEvent` вызывает `mark_session_closed_cleanly()` → `active=False` + блокировка Vault.

**Tab Suspender.** Таймер раз в минуту; вкладка выгружается (`QWebEnginePage.LifecycleState.Discarded`, заголовок получает префикс `💤 `), если неактивна дольше `tab_suspend_minutes` (15). **Не выгружаются:** текущая, закреплённые 📌, уже выгруженные, стартовая страница, вкладки со звуком (`recentlyAudible`). Пробуждение при переключении на вкладку (`LifecycleState.Active`).

**Прочее поведение вкладок:** стек закрытых вкладок до 20 (`Ctrl+Shift+T`); закрепление; дублирование; «закрыть остальные / справа»; индикатор «⚠ не отвечает» после 15 с загрузки; индикатор безопасности URL; `GORWebPage.createWindow` — всплывающие окна становятся вкладками, из инкогнито-вкладки — только инкогнито-вкладки, **не более 5 всплывающих окон за 3 с** (антипопандер).

### 8.8 Переводчик видео VOT (`browser_translate.py`)

Движок перевода — внешний userscript `vot.user.js` (проект Voice-Over-Translation), распространяется отдельно. Положите его в `BASE_DIR` браузера. `install_vot_translator(profile, base_dir, enabled)` внедряет его через `QWebEngineScript` (`DocumentReady`, `MainWorld`, подфреймы) на хосты из `VOT_URL_PATTERNS` (YouTube, Twitch, VK, VK Video, TikTok). Так как `QWebEngineScript` не умеет `@match`, исходник оборачивается проверкой `location.hostname`. Если файла нет — внедряется честный *fallback*: кнопка «🌐 Перевести видео» сообщает, что движок не установлен. Возвращает `True`, если подключён настоящий скрипт.

### 8.9 Оверлей поиска по вики (Ctrl+Shift+K)

`WikiSearchOverlay(QDialog)` — полупрозрачное окно по центру. Берёт `now_playing` (игра, запущенная из лаунчера). Если известен `wiki_url` игры — ищет `https://www.google.com/search?q=site:<домен>+<запрос>`, иначе `<игра>+wiki+<запрос>`. Горячая клавиша зарегистрирована с `ApplicationShortcut`, т. е. работает независимо от того, какой виджет (включая веб-страницу) в фокусе.

### 8.10 Горячие клавиши браузера

| Клавиши | Действие |
|---|---|
| `Ctrl+T` / `Ctrl+W` | новая / закрыть вкладку |
| `Ctrl+Shift+T` | вернуть закрытую вкладку (до 20) |
| `Ctrl+1…8` / `Ctrl+9` | вкладка по номеру / последняя |
| `Ctrl+L` | адресная строка |
| `Ctrl+F` | поиск по странице |
| `Ctrl+H` | показать/скрыть боковую панель |
| `Ctrl+=`, `Ctrl++`, `Ctrl+-`, `Ctrl+0` | масштаб (шаг 0,1; 0,25…4,0) / сброс |
| `F12` | DevTools |
| `Esc` | сначала закрывает панель поиска по странице, иначе выходит из полноэкранного видео |
| `Ctrl+Shift+K` | поиск по вики игры |

### 8.11 Окно настроек и стартовая страница

`BrowserSettingsWindow(QDialog)` (минимум 760×600): боковое меню + `QStackedWidget`, общая кнопка «Сохранить и применить». Разделы (классы): `GeneralTab` (поисковая система, виджеты главной — часы/заголовок/заметки, «спящие вкладки»), `AppearanceTab` (цвета интерфейса, шрифт и прозрачность, название системы), `NetworkSecurityTab` (блокировка рекламы и трекеров, автообновление списка с GitHub, кнопка «Перевести видео», приём вкладок/групп по сети), `ExtensionsTab` (пользовательские JS-скрипты), `BackupTab` (экспорт/импорт JSON: `gor_backup_version`, `exported_at`, `settings`, `history`, `bookmarks`, `tab_groups`, `extensions`, `start_page_raw`).

`write_start_page(settings)` генерирует `start_page.html`: часы, заголовок «GOR CORE», поле поиска активного движка, блок «Личные заметки» (**заметки лежат в `localStorage` самой страницы**, а не в `games_data.json`). Лаунчер передаёт на страницу «сейчас в игре» через `push_now_playing` и настройки через `window.gorApplyNativeSettings({…, engines, engine_idx})`.

### 8.12 Менеджер загрузок

`DownloadManager(QDialog)` + `DownloadItem(QWidget)` на каждый `QWebEngineDownloadRequest`: прогресс, открытие папки, «очистить завершённые». Подписан на `profile.downloadRequested`.

### 8.13 Два «старых» файла

`GOR_Brauzer.py` (класс на `QWidget`) и `GORbrauzer_desktop.py` (класс на `QMainWindow`, «десктопный режим») — самодостаточные ранние версии: каждый содержит собственные `CustomizationManager`, `GORWebPage`, `SettingsDialog`, `ExtensionManager`, `DownloadItem`, `DownloadManager`, `GORBrowser`. Лаунчер импортирует **только** `browser_widget.GORBrowser`; эти два файла можно запускать отдельно для проверки движка, но они не получают AdBlock, Vault, LAN Broadcast, групп вкладок и т. д.

---

<a id="s9"></a>
## 9. Мульти-аккаунты: `account_manager.py`, `account_dialog.py`

### 9.1 Модель

У каждого аккаунта своя папка `accounts/<имя>/`:

| Путь внутри аккаунта | Содержимое | Куда «подключается» при активации |
|---|---|---|
| `games_data.json` | игры, группы, история, блок `browser`, `language`, `addons_list` | `<корень>/games_data.json` — **жёсткая ссылка** |
| `GOR_Profile/` | профиль Chromium (cookies, localStorage, кэш) | `<корень>/GOR_Brauzer/GOR_Profile` — ссылка-каталог |
| `addons/` | аддоны этого аккаунта | `<корень>/addons` — ссылка-каталог |
| `avatar.png` | обложка аккаунта | не линкуется |
| `preferences.json` | язык и тема аккаунта (через `addon_API.accounts`) | не линкуется |

Реестр аккаунтов — `accounts/accounts_index.json`: `{"accounts": {имя: {"salt", "password_hash"}}, "last_active": имя}`. Читается через `read_json` (при порче — `.bak`, затем `.corrupt-*`), пишется `write_json_inplace`.

### 9.2 Имя и пароль

`validate_account_name(name)` отклоняет: пустое; символы `\ / : * ? " < > |` и управляющие; `.`/`..` и имена, оканчивающиеся точкой или пробелом; длину > 64; зарезервированные имена Windows (`con, prn, aux, nul, com1–9, lpt1–9`); имя `accounts_index.json`. Дополнительно запрещены дубли **без учёта регистра** (Windows считает `Vova` и `vova` одной папкой). `get_account_dir` проверяет, что папка лежит прямо в `accounts/` (защита от `..` перед `rmtree`).

Пароль аккаунта (необязательный): `salt = sha256(os.urandom(16)).hexdigest()[:16]`, хэш `sha256(salt + password)`. Это **защита входа в лаунчер, а не шифрование данных**: файлы аккаунта лежат на диске открыто, и быстрый SHA-256 без растяжения слабее PBKDF2 хранилища паролей браузера.

### 9.3 API модуля

| Функция | Назначение |
|---|---|
| `create_account(name, password="", language=None)` → `(ok, ошибка)` | создаёт папку, запись в индексе, начальные предпочтения (тема `default`, язык) |
| `delete_account(name)` → `(ok, ошибка)` | нельзя удалить **активный** аккаунт; затем `rmtree` папки |
| `list_accounts()`, `account_exists`, `account_has_password`, `verify_password(name, pw)` | аккаунт без пароля пускает без проверки |
| `get_avatar_path`, `save_avatar_png(name, bytes)`, `remove_avatar` | обложка (обрезку делает UI) |
| `activate_account(name)` | подмена ссылок, `last_active`, `GOR_ACTIVE_ACCOUNT` в окружении, применение предпочтений |
| `get_project_root()` | `dirname(abspath(sys.argv[0]))` |

### 9.4 `activate_account` по шагам

```
1. _link_file(<корень>/games_data.json, accounts/<имя>/games_data.json)
2. _link_dir(<корень>/GOR_Brauzer/GOR_Profile, accounts/<имя>/GOR_Profile)
3. _link_dir(<корень>/addons,                  accounts/<имя>/addons)
4. last_active = имя;  os.environ["GOR_ACTIVE_ACCOUNT"] = имя
5. _apply_account_preferences: язык и тема аккаунта; перечитать переводы
```

**`_link_file`.** Уже та же жёсткая ссылка (`os.path.samefile`) — ничего не делает. Данных аккаунта нет: «усыновляется» файл из корня (если у него `st_nlink <= 1`, т. е. это обычный файл), иначе создаётся пустой `{}`. Данные есть, а в корне лежит *настоящий* файл (ссылка разорвана) — `_preserve_real_file`: если корневой файл новее и непустой, его содержимое переносится в аккаунт (старое → `.bak-<время>`), иначе он откладывается как `.orphan-<время>`. Затем `os.link`; при неудаче — копирование (не живая ссылка!).

**`_link_dir`.** Симлинк снимается; настоящая папка с данными при пустой папке аккаунта **переносится** в неё (первая миграция); если данные есть с обеих сторон — корневая папка переименовывается в `….orphan-<время>`, ничего не теряется. Ссылку создаёт `platform_utils.make_dir_link`; если не вышло (не NTFS и т. п.) — запасной `copytree`.

**Первый запуск поверх старой установки.** Существующие `games_data.json`, `GOR_Profile`, `addons` автоматически достаются тому аккаунту, который создан первым.

### 9.5 Окна

`AccountDialog` — выбор/создание аккаунта при старте (с вводом пароля). `AccountSwitcherDialog(account_name, on_switch_confirmed, parent)` — окно «мой аккаунт» из кнопки-аватара в шапке: большая обложка, список остальных; подтверждённый выбор вызывает `restart_launcher(confirm=False, account=target)`. `circular_avatar(name, size=64)` рисует круглую обложку или заглушку-квадрат.

> **Почему переключение требует перезапуска.** Модули открывают пути один раз, а Chromium держит профиль открытым. Поэтому «переключение» — новый процесс с `--account`, который пропускает окно выбора.

---

<a id="s10"></a>
## 10. Big Picture, геймпады, TV-стриминг

### 10.1 Геймпад (`shared/gamepad.py`)

Без внешних зависимостей (Qt6 убрал QtGamepad). Слои:

| Элемент | Роль |
|---|---|
| `decode_state(buttons, lx, ly, lt, rt)` | сырое состояние XInput → `frozenset` логических кнопок |
| `ButtonRepeater` | нажатие + автоповтор только для `up/down/left/right`: задержка `REPEAT_DELAY = 0.40` с, интервал `REPEAT_INTERVAL = 0.11` с; `swallow(held)` «проглатывает» зажатые кнопки при возобновлении |
| `XInputBackend` | `xinput*.dll` через `ctypes`; пересканирование каждую 1,0 с |
| `LinuxJoystickBackend` | `/dev/input/js*`, структура события `<IhBB`, до 4 слотов, пересканирование 2 с; раскладки Xbox и PlayStation |
| `GamepadReader(QObject)` | опрос по таймеру (по умолчанию 16 мс), сигнал `pressed(str)`; `set_paused`, `resync`, `connected()` |

Логические кнопки: `up down left right a b x y lb rb start back lt rt`. Маски XInput: `0x0001…0x0008` — D-pad, `0x0010` start, `0x0020` back, `0x0100/0x0200` LB/RB, `0x1000/0x2000/0x4000/0x8000` — A/B/X/Y. Левый стик считается нажатием при отклонении > `STICK_THRESHOLD = 16000` (из ±32767), триггеры — > `TRIGGER_THRESHOLD = 128` (из 255). На других ОС (macOS) считыватель неактивен, режим управляется клавиатурой.

### 10.2 Big Picture (`extras/big_picture.py`)

Полноэкранный интерфейс «с дивана». Окно не знает деталей лаунчера — ему нужен объект с интерфейсом `GORLauncher` (`games_info`, `active_sessions`, `launch_game_from_wheel`, `save_data`, `refresh_list`).

**Разделы** (`TABS`): `library`, `favorites`, `recent` (до `RECENT_LIMIT = 20`), `stream`. Переключение — LB/RB.

| Действие | Геймпад | Клавиатура |
|---|---|---|
| навигация | D-pad / левый стик | стрелки |
| выбрать / запустить | A | Enter, Пробел |
| назад / меню выхода | B | Esc, Backspace |
| в избранное | X | F |
| действия с игрой | Y | Y |
| раздел назад/вперёд | LB / RB | Shift+Tab / Tab (PageUp/PageDown) |
| главное меню | Start | M, F10 |

**Тема.** `Theme.load()` берёт палитру активной темы лаунчера (`addon_API.themes.themes.colors()`), объединяет с `_DEFAULT_COLORS`, и **гарантирует контраст**: `ensure_contrast(text, bg, 3.0)` и `ensure_contrast(text_muted, bg, 4.5)` (формула WCAG-яркости, `contrast_ratio`). Обложки масштабируются `CARD_SCALE = 0.78`.

**Игра или стрим** → окно прячется, ввод игнорируется (`_suspend(done_fn, kind)`, `GamepadReader.set_paused`), по завершении интерфейс возвращается сам. Запуск игры идёт через `launcher.launch_game_from_wheel(game)` — тот же путь, что у карточки (учёт времени, события аддонов).

**Параметры стрима:** разрешения `1280x720`, `1920x1080` и др. (`STREAM_RESOLUTIONS`), FPS `30/60/90/120`, битрейт `10000…80000` кбит/с, приложения по умолчанию `Desktop`, `Steam Big Picture`. Список приложений хоста грузит `AppListWorker` (фон).

**Запуск с ТВ.** Sunshine запускает приложение «GorLauncher Big Picture» командой `pythonw bridge_loader.py --bigpicture`. Если лаунчер уже открыт, новый процесс через single-instance передаёт команду `bigpicture` и **остаётся жить, пока Big Picture открыт** (иначе Sunshine завершил бы стрим). Выход: `exited(quit_app)` → `_on_big_picture_exited`.

### 10.3 Sunshine (хост-сторона)

**`sunshine_api.py` — `SunshineAPI(user, password, base_url="https://localhost:47990", timeout=6)`** (без Qt). HTTP Basic, самоподписанный сертификат: проверка TLS отключена и **разрешена только для `localhost/127.0.0.1/::1`** — иной хост даёт ошибку.

| Метод | Эндпоинт | Результат |
|---|---|---|
| `check()` | `GET /api/config` | `'ok'` / `'unauthorized'` / `'down'` |
| `clients()` | `GET /api/clients/list` | `[{name, uuid}]` |
| `pair(pin, name="Android TV")` | `POST /api/pin` | PIN — ровно 4 цифры; на HTTP 400 повтор без поля `name` (старые версии) |
| `unpair(uuid)` | `POST /api/clients/unpair` | |
| `apps()` | `GET /api/apps` | список приложений |
| `ensure_app(entry)` | `POST /api/apps` (`index=-1` — добавить) | `'added'/'updated'/'unchanged'` **без перезапуска Sunshine** |
| `has_app(name)` | | есть ли приложение |

Вспомогательное: `launcher_app_entry(project_root)` — запись `{name: "GorLauncher Big Picture", cmd, working-dir, auto-detach: False, wait-all: True, exit-timeout: 5, image-path?}`; `lan_addresses()`; `save_login/load_login/forget_login` (файл `gorlauncher_api.json` в `Sunshine/config`); `upsert_app_in_file(apps_json, entry)` — запасной путь правкой `apps.json`.

**`sunshine_control.py`** — окно управления. Рабочая папка Sunshine: `<корень>/Sunshine`, обложки — `Sunshine/assets`, `apps.json` — `platform_utils.sunshine_apps_json`.

- `SyncWorker` — «синхронизировать игры»: читает `games_data.json`, конвертирует обложки не-PNG в PNG (Pillow, если установлен) или копирует PNG в `assets`, формирует записи `{name, cmd, working-dir, auto-detach: True, wait-all: True, image-path}`; **сохраняет** системные пункты (`Desktop`, `Steam Big Picture`, всё, что начинается с `gorlauncher`), перезаписывает `apps.json`, затем **убивает и перезапускает Sunshine** (`taskkill /f /im sunshine.exe` / `pkill -x sunshine`) — это обрывает идущий стрим, поэтому для одного приложения лаунчера используется API без перезапуска.
- `CredsWorker` — задать логин/пароль: `sunshine --creds <user> <pwd>`; пароль на время вызова **виден в списке процессов** (ограничение самого Sunshine).
- `RestartWorker`, `_StatusWorker` (опрос запущенности `tasklist /FI "IMAGENAME eq sunshine.exe"`).

**`tv_setup.py` (вкладка «ТВ»)**: 1) вход в Sunshine (кнопка «Авто» создаёт пользователя `gorlauncher` со случайным паролем `secrets.token_urlsafe(9)` и запоминает его); 2) «добавить приложение GorLauncher Big Picture» (через API, при неудаче — правкой файла); 3) сопряжение по PIN; 4) список/отключение устройств. Все обращения — в `ApiTask(QThread)`; индикатор статуса `ok/unauthorized/down`.

### 10.4 Moonlight (клиент-сторона, `moonlight_cantrol.py`)

`PCStreamManager` — движок без GUI:

| Метод | Деталь |
|---|---|
| `find_moonlight_executable()` | порядок: папка `Moonlight/` рядом с лаунчером → `PATH` (`moonlight-qt`, `moonlight`, `Moonlight.exe`…) → типичные каталоги (Program Files `Moonlight Game Streaming`, `/usr/bin`, `/opt/moonlight-qt`, flatpak) |
| `pair_with_host(ip, pin, timeout=45)` | `moonlight pair <ip> --pin <4 цифры>`; один и тот же PIN нужно подтвердить в веб-панели Sunshine (`https://<ip>:47990`) за время таймаута |
| `list_apps(ip, timeout=25)` | `moonlight list <ip>`; вывод разбирается терпимо (служебные строки отбрасываются) |
| `start_stream(ip, app_name, width=1920, height=1080, fps=60, bitrate=20000, windowed=False)` | фоновый запуск, `last_process` |
| `load_hosts/save_hosts/add_host/remove_host` | `moonlight_hosts.json` |

`StreamModuleUI` — виджет (встраиваемый или отдельный), `PairWorker`, `PinDialog` (случайный PIN, `regenerate_pin`).

**Порядок настройки ТВ:** Sunshine на ПК → вкладка «ТВ» (логин) → добавить приложение → на ТВ в Moonlight добавить ПК, ввести показанный PIN в «PIN» → в Big Picture / Moonlight запустить «GorLauncher Big Picture».

---

<a id="s11"></a>
## 11. Аддоны и безопасность: `addons_sys/`

### 11.1 Структура аддона

```
addons/<папка>/
├── config.json        # обязателен
├── core/              # обязателен: код (start_file лежит здесь)
│   └── main.py
├── web/index.html     # карточка для Control Center (если нет — prepare_addon_folder создаёт заглушку)
├── favicon.png        # необязательно (иконка в списке)
├── requirements.txt   # необязательно
└── activity.json      # журнал (создаётся автоматически)
```

`config.json`: `name`, `version`, `author`, `description`, `start_file` (**обязательно**, иначе в журнал пишется ошибка), `min_api`.

### 11.2 Загрузка (`bridge_loader.load_addons`)

1. `addon_watchdog.install(addons_dir)` — **до** загрузки любого аддона.
2. Включённость: список `addons_list` с диска (ключа нет → включены все).
3. `prepare_addon_folder` — для всех аддонов, включая выключенные (иначе Control Center их не покажет).
4. `install_requirements(addon_path)`: SHA-256 от `requirements.txt` сравнивается с маркером `.requirements_installed`; при совпадении установка пропускается; `pip install -r … --quiet --disable-pip-version-check` с таймаутом 60 с, без окна консоли. **Маркер пишется и при неудаче/таймауте** — чтобы запуск не зависал каждый раз без сети. Повторить: удалить маркер вручную.
5. `addon_manager.load(launcher, addon_path, config)` — поддерживает три формы: `init_addon(launcher)`, `init_addon(launcher, api)`, класс `Addon`.
6. `launcher.games_info["addons_list"] = active_addons; save_data()`; если есть хоть один аддон — в шапку добавляется кнопка «Addon Manager».

### 11.3 Пример аддона (`addons/gor_style`)

```python
from addon_API import AddonBase

class Addon(AddonBase):
    def on_load(self, api):
        d = api.design
        with d.batch():                       # пакетное применение
            d.preset('glass', clear=False)
            d.palette('#362bee', 'dark', 0.08)
            d.radius(scale=1.4); d.font('Comic Sans MS', None)
            d.buttons('pill'); d.cards(radius=24, glass=False); d.covers(radius=16)
            d.shadow("GameCard", blur=26, dy=8)
            d.hover_glow("GameCard", "{{accent}}", 24)
            d.glow("RunGameBtn", "{{accent}}", 16, pulse_ms=2400)
            d.noise(0.05); d.vignette(0.5); d.grid(44, "{{accent}}", 0.08); d.scanlines(3, 0.10)
            d.animated_gradient(["{{accent}}", "#7a2dff", "#00d4ff"], 14000, 0.14)
            d.particles("stars", 70)          # также "snow", "fireflies"
    def on_unload(self):
        pass                                   # api.design откатит всё сам
```

Жизненный цикл: `on_load(api)` / `on_unload()`. `{{accent}}`, `{{accent_hover}}` — токены темы. Сам пакет `addon_API` в дамп не входит.

### 11.4 Control Center (`ControlCenter.py`)

Отдельный процесс (`bridge_loader.run_control_center`, регистрируется в `launcher._track_process` и закрывается вместе с лаунчером). `ControlCenter(QDialog)`: слева список (`AddonDelegate` рисует иконку, имя, версию и **квадратный чекбокс вручную через `QPainter`** — `setItemWidget` в Qt/Windows даёт размытый текст), справа — вкладка веб-карточки (`web/index.html` в `QWebEngineView`, при ошибке — `ERROR_PAGE_TEMPLATE`) и вкладка «Мониторинг» (`MonitoringTab`, опрос `activity.json` раз в 1000 мс).

Показываются только аддоны, у которых **есть и `config.json`, и `web/index.html`**. `_save_active_addons()` синхронизирует `addons_list`; записи, которые окно не показывало, **сохраняются** (раньше такие аддоны молча отключались); при нечитаемом файле запись не выполняется.

### 11.5 Логгер (`addon_logger.py`)

Общение между процессами идёт через `activity.json`: аддон пишет, Control Center читает.

| Функция | Применение |
|---|---|
| `log_activity(__file__, msg_type, message)` | из кода аддона (`core/*.py`, корень аддона — на два уровня выше) |
| `log_activity_for_addon(addon_root, msg_type, message)` | когда путь известен (загрузчик, watchdog) |

Типы: `info` (ℹ️), `change` (✏️), `request` (📨), `error` (⚠️). Запись: `{type, message, time: "ЧЧ:ММ:СС"}`, новые **в начало**, не более `MAX_LOG_ENTRIES = 50`, под `threading.Lock`; исключения наружу не пробрасываются.

### 11.6 Watchdog (`addon_watchdog.py`)

`install(addons_dir)` один раз подменяет (monkey-patch):

| Подмена | Что журналируется (тип) |
|---|---|
| `builtins.open` с режимами `w/a/x/+` | «Запись в файл: …» (`change`) |
| `subprocess.Popen.__init__` | «Запуск процесса: …» (`request`) |
| `socket.socket.connect` | «Сетевое подключение: …» (`request`) |
| `QTabWidget.addTab` | «Создана новая вкладка интерфейса» (`change`) |

Источник определяется обходом стека `sys._getframe()/f_back` до файла внутри `addons/<имя>/` (не `inspect.stack()` — тот читает исходники с диска и тормозил запуск). От рекурсии (лог сам вызывает `open`) защищает **поточно-локальный** флаг `_guard.busy`. Ограничения честно названы в docstring: это видимость, а не песочница; обход через `ctypes` возможен. Оригинальные функции вызываются первыми, поведение аддона не меняется.

### 11.7 Хуки лаунчера для аддонов (по вызовам в коде)

| Имя | Вид | Где вызывается | Аргументы |
|---|---|---|---|
| `before_game_launch` | `allow()` — может **отменить** запуск | `GameCard.handle_main_button` | `game_data` |
| `game_launch_args` | `apply_filter()` — менять аргументы | там же | `args, game_data` |
| `game_started` | событие | там же | `game_data` |
| `game_finished` | событие | `on_game_finished` / `on_session_finished` | `duration, game_data` |
| `game_card_menu` | событие | контекстное меню карточки | `menu, game_data, card` |
| `library_refreshed` | событие | `refresh_list` | — |
| `launcher_closing` | событие | `closeEvent` | — |
| `Events.ADDONS_LOADED` | событие | `bridge_loader` после загрузки | — |

---

<a id="s12"></a>
## 12. Мультиязычность (i18n)

### 12.1 Механика (`shared/lang_loader.py`)

| Элемент | Поведение |
|---|---|
| Файлы | `lang/<код>.json`: `ru`, `en`, `es`, `hy` (армянский). Метаданные: `_meta.code`, `_meta.name` (имя языка в меню). Список языков строится сканированием папки (`available_languages`) — **добавить язык = положить новый JSON** |
| Ключи | вложенные: `раздел.имя`, поиск через точку (`_lookup`) |
| `tr(key, **kwargs)` | 1) текущий язык → 2) резервный `ru` (`FALLBACK_LANG`) → 3) если нигде нет — возвращается **сам ключ**. Плейсхолдеры `{имя}` подставляются `str.format`; при ошибке форматирования возвращается строка без подстановки |
| `get_language()` | язык активного аккаунта (`preferences.json`) → поле `language` в `games_data.json` → `ru` |
| `set_language(code)` | пишет язык; при нечитаемом файле **не пишет** (не затирает БД) |
| `reload_language(code=None)` | перечитывает словари; `ensure_loaded()` вызывается лениво из `tr` |
| Ключи, которые **не переводятся** | внутренние значения данных, например `NO_GROUP_KEY = "Без группы"` |

Смена языка в меню лаунчера = `set_language` + перезапуск без подтверждения.

### 12.2 Структура: 27 разделов, 417 ключей на язык

| Раздел | Ключей |
|---|---:|
| `_meta` | 2 |
| `common` | 10 |
| `launcher` | 46 |
| `game_card` | 9 |
| `history_card` | 3 |
| `group` | 4 |
| `game_delete` | 2 |
| `history_clear` | 2 |
| `sunshine_error` | 2 |
| `moonlight_error` | 2 |
| `exporter_error` | 2 |
| `game_editor` | 26 |
| `group_editor` | 7 |
| `exporter` | 16 |
| `control_center` | 32 |
| `sunshine` | 29 |
| `sunshine_log` | 24 |
| `wheel` | 11 |
| `updater` | 27 |
| `browser` | 22 |
| `big_picture` | 48 |
| `tv_setup` | 39 |
| `browser_custom` | 10 |
| `broadcast` | 8 |
| `account_btn` | 1 |
| `style_studio` | 28 |
| `browser_menu` | 5 |

Наборы ключей в четырёх языках **совпадают полностью**. Полный список с русским и английским текстом — **Приложение A**.

### 12.3 Как добавить язык

1. Скопировать `lang/en.json` в `lang/<код>.json`.
2. Заполнить `_meta.code` и `_meta.name`.
3. Перевести значения, **не меняя ключи и `{плейсхолдеры}`**.
4. Перезапустить лаунчер — язык появится в меню автоматически.

---

<a id="s13"></a>
## 13. Темы и QSS

### 13.1 Конвейер (`shared/style_loader.py`)

```
load_stylesheet(): читает style.qss  →  _apply_theme(base_qss): движок тем (addon_API.themes)
                   подставляет токены {{имя}} из палитры активной темы, добавляет theme.qss темы
apply_global_style(app): app.setStyleSheet(...)
```

Если движок тем недоступен, применяется базовый `style.qss` как есть. Файл `style.qss` — 633 строки, ~99 блоков; секции по комментариям: поля ввода, кнопки (в т. ч. красная «опасного действия» и зелёная «запуск»), группы, журналы, списки, чекбоксы, комбобоксы, вкладки, прогресс-бары, меню, прокрутка, строка аддона и индикатор статуса, лог активности, карточка игры/истории (красная рамка запущенной, бейдж «ИГРАЕТ», золотая рамка избранного, заглушка обложки, кнопка «ЗАПУСТИТЬ→ОТКЛЮЧИТЬ»), заголовок «ИЗБРАННОЕ», квадратные кнопки шапки, выделенное поле аргументов. Состояния (`running`, `favorite`) переключаются **динамическими свойствами** Qt (`setProperty` + `polish`).

### 13.2 Схема `themes/<id>/theme.json`

| Поле | Тип | Описание |
|---|---|---|
| `name`, `author`, `version`, `description` | str | метаданные |
| `colors` | dict | токены палитры (таблица 13.3) |
| `font` | `{family, size}` | необязательно (у «Ретро-терминала» — Consolas 13) |
| `qss` | str | необязательно: имя файла с дополнительным QSS (`theme.qss`) |

### 13.3 Токены цвета

`bg`, `surface`, `surface_alt`, `surface_hover`, `border`, `text`, `text_muted`, `accent`, `accent_dark`, `accent_hover`, `success`, `warning`, `danger`, `editor_bg`, `editor_accent`. Отсутствующие токены берутся из значений по умолчанию (поэтому у тем их не все).

### 13.4 Пять встроенных тем

| id | Название | `bg` | `surface` | `text` | `accent` | Особенности |
|---|---|---|---|---|---|---|
| `gorstyle` | GorStyle (создана в Theme Studio, **активна** по `_state.json`) | `#000034` | `#1a168d` | `#5a55f5` | `#5227ff` | единственная с `accent_dark`/`accent_hover` |
| `forest` | Лесная | `#0b110d` | `#14201a` | `#e8f5ec` | `#2ecc71` | спокойные зелёные тона |
| `light` | Светлая | `#f2f3f5` | `#ffffff` | `#1b1f24` | `#0b6fd6` | `theme.qss`: возвращает читаемый цвет тексту (в базовом стиле он белый), у кнопок при наведении — белый |
| `neon_pink` | Неоновый розовый | `#0d0014` | `#1a0a24` | `#fbeaff` | `#ff2d95` | фиолетовый фон |
| `retro_terminal` | Ретро-терминал | `#000000` | `#061406` | `#33ff66` | `#00c040` | Consolas 13, `border-radius: 0` (острые углы), `danger #ff4040`, `warning #e6e600` |

Тема активного аккаунта хранится в его `preferences.json`; `themes/_state.json` (`active`, `overrides`) — общее состояние. Аддон оформления (`api.design`) накладывается **поверх** темы и откатывается при `on_unload`. Редактор тем «Theme Studio» (раздел `style_studio` локализации, 28 ключей) в дамп не входит.

---

<a id="s14"></a>
## 14. Обновление, экспорт, колесо фортуны, служебное

### 14.1 Обновление (`shared/updater.py`)

| Константа/режим | Значение |
|---|---|
| Удалённая версия | `version.json` в ветке `main` на `raw.githubusercontent.com` |
| Архив | zip ветки с `codeload.github.com` |
| `MODE_CHECK` / `MODE_INSTALL` | только проверка / проверка + установка |
| Сравнение | `remote != current` (строки) |

`UpdateWorker(QThread)` скачивает zip, распаковывает во временную папку и копирует файлы через `_safe_copy_files` по **белому списку**: обновляются только папки `UPDATABLE_FOLDERS = {lang, core, shared, editors, remote, addons_sys, extras, addon_api, gor_brauzer}` (сравнение без учёта регистра) и файлы корня. Папка `addons/` **намеренно не входит** в список — это сторонний код пользователя. На любой глубине пропускаются `SYNC_SKIP_NAMES = {__pycache__, gor_profile, _data}` (профиль браузера, кэш). Данные пользователя (`games_data.json`, `accounts/`) лежат вне списка и не затрагиваются. `version.json` обновляется вместе с остальными файлами. Фоновая проверка при запуске: `check_updates_in_background(launcher)` → в шапке появляется кнопка обновления; сетевые ошибки в фоне молчат. Окно `UpdaterDialog`: проверить, обновить, «Узнать больше» (страница релизов).

### 14.2 Экспорт (`extras/exporter_editor.py`)

`PackerGUI` выбирает игры из `games_data.json`, `PackerWorker(QThread)` упаковывает их **корневые папки (`root_path`)** в zip. Поэтому у игры должен быть заполнен `root_path`; игры без него пропускаются.

### 14.3 Колесо фортуны (`extras/fortune_wheel.py`)

`FortuneWheelDialog` собирает плоский список игр из `groups` и `standalone` (дедупликация по `id`) и **перечитывает файл при каждом вращении**. Победитель выбирается заранее (`random.randint`), затем считается угол: 5–8 полных оборотов плюс точный доворот до середины сектора (стрелка сверху), анимация — таймер 16 мс (~60 FPS) с плавным замедлением. `WheelWidget` рисует сектора (`drawPie`) и кэширует обложки. Результат запускается через `launcher.launch_game_from_wheel(game)` — по `id` игры.

### 14.4 `_i18n_merge.py`

Одноразовый скрипт слияния новых ключей в `lang/*.json`; в самом файле помечен «запустить один раз и удалить». В работе лаунчера не участвует.

---

<a id="s15"></a>
## 15. Веб-портал `WEB/`

Статический сайт без сервера: `index.html` (главная), `download.html` (загрузка), `docs.html` + `docs-data.js` (статьи, рендерятся скриптом), `script.js`, `style.css`. Интерфейс сайта локализован в самом `script.js` (RU/EN/HY). Контент документации — массив объектов в `docs-data.js`.

> **Внимание.** Статьи портала описывают архитектуру, которой нет в исходниках (QWebChannel-мост, `process_manager.py`, `game_scanner.py`, `psutil`, AudioRelay). Для разработки ориентируйтесь на эту энциклопедию и исходный код, а не на статьи портала.

---

<a id="s16"></a>
## 16. Справочник API разработчика

Полный автоматический справочник сигнатур — **Приложение B**. Ниже — то, что нужно чаще всего.

### 16.1 Данные и перевод

```python
from safe_json import read_json, write_json_inplace
data = read_json("games_data.json", default_factory=dict)   # битый → .bak → .corrupt-*
write_json_inplace("games_data.json", data)                  # полностью сериализует ДО записи

from lang_loader import tr
tr("game_card.run")                    # строка
tr("history_card.session_time", h=2, m=30)
```

### 16.2 Аккаунты

```python
import account_manager as am
ok, err = am.create_account("Vova", password="", language="ru")
am.activate_account("Vova")
am.verify_password("Vova", "secret")
```

### 16.3 Sunshine

```python
from sunshine_api import SunshineAPI, launcher_app_entry
api = SunshineAPI("gorlauncher", "пароль")           # только localhost
api.check()                                           # 'ok' | 'unauthorized' | 'down'
api.ensure_app(launcher_app_entry(project_root))      # без перезапуска Sunshine
api.pair("1234", name="Android TV")
```

### 16.4 Moonlight

```python
from moonlight_cantrol import PCStreamManager
m = PCStreamManager()
exe = m.find_moonlight_executable()
m.pair_with_host("192.168.0.10", "4821")
m.start_stream("192.168.0.10", "GorLauncher Big Picture", 1920, 1080, 60, 20000)
```

### 16.5 Хранилище паролей

```python
from browser_passwords import PasswordVault, generate_strong_password
v = PasswordVault(path); v.create("мастер-пароль") ; v.unlock("мастер-пароль"); v.lock()
```

### 16.6 Логи аддона

```python
from addon_logger import log_activity
log_activity(__file__, "change", "Изменён цвет акцента")   # info | change | request | error
```

### 16.7 Single-instance и IPC

`forward_to_running(root, command, wait_for_close=False) -> bool`; `SingleInstanceServer(root, on_command)`; `cover_ipc.try_decode_line(buffer)` извлекает одно JSON-сообщение из буфера по `\n`.

---

<a id="s17"></a>
## 17. Сборка в Windows EXE (PyInstaller) и деплой

В дампе **нет** `.spec`-файла и скрипта сборки; ниже — что код требует от упакованной версии, и рекомендуемый рецепт (он не взят из репозитория).

### 17.1 Что код ожидает от `.exe`

| Требование | Где |
|---|---|
| Данные (`games_data.json`, `accounts/`, `lang/`, `themes/`, `style.qss`, `version.json`) лежат **рядом с `.exe`**, а не во временной `_MEIPASS` | `browser_constants.BASE_DIR`, `lang_loader._detect_base_dir`, `style_loader` |
| Только упакованные ресурсы читаются из `sys._MEIPASS` | `get_resource_path()` |
| Редакторы лежат **плоско в корне** как `game_editor.exe`, `group_editor.exe`, `ControlCenter.exe`, `sunshine_control.exe`, `exporter_editor.exe`; иначе запускается `python <подпапка>/<имя>.py` | `run_editor_process` |
| Перезапуск ищет `bridge_loader.exe` → `bridge_loader.py` → `GorLauncher.exe` | `restart_launcher` |
| Рабочая папка = папка проекта (`os.chdir` в начале) | `bridge_loader.py` |

### 17.2 Рекомендуемый рецепт (не из репозитория)

```bat
pip install pyinstaller PyQt6 PyQt6-WebEngine cryptography pillow
pyinstaller --noconfirm --windowed --name bridge_loader --icon favicon.ico ^
  --paths core --paths shared --paths editors --paths remote --paths extras ^
  --paths addons_sys --paths GOR_Brauzer ^
  --hidden-import browser_widget --hidden-import browser_dialogs --hidden-import browser_groups ^
  --hidden-import browser_passwords --hidden-import browser_broadcast --hidden-import browser_adblock ^
  --hidden-import browser_startpage --hidden-import browser_translate --hidden-import browser_constants ^
  --hidden-import browser_downloads --hidden-import browser_page ^
  bridge_loader.py
:: аналогично собрать каждый редактор отдельным exe; затем положить рядом с bridge_loader.exe:
:: lang\ themes\ style.qss version.json favicon.ico addon_API\ (если он внешний)
```

Нюансы: `QtWebEngineProcess` и ресурсы Qt подтягивает хук PyInstaller для PyQt6; `addon_API` и пакет `cryptography` должны попасть в сборку; аддоны с `requirements.txt` ставят зависимости через `pip`, то есть нужен рабочий Python — в Windows-раздаче его обеспечивает папка `runtime/`.

---

<a id="s18"></a>
## 18. Troubleshooting FAQ

| Симптом | Причина (по коду) | Что делать |
|---|---|---|
| Данные «откатились» после сбоя | запись «на месте»; повреждённый файл заменяется копией `.bak` (до 60 с давности) | посмотреть `games_data.json.bak` и `games_data.json.corrupt-*` рядом с файлом |
| Аккаунт видит чужие игры / пустой список | жёсткая ссылка разорвана (ссылку сломал внешний редактор/синхронизатор, заменивший файл) | запустить лаунчер заново: `activate_account` переподключит ссылку, настоящий файл сохранится как `.orphan-*`/`.bak-*` |
| Ссылки не создаются | диск не NTFS или нет прав | модуль падает на копирование — изменения перестанут синхронизироваться; перенесите проект на NTFS |
| Игра запущена, а таймер не останавливается | процесс-«лаунчер» перезапускает себя; монитор ждёт исчезновения образа из `tasklist` | закрыть игру целиком; проверить, что имя `.exe` в карточке совпадает с реальным |
| Время сессии меньше ожидаемого | считается до последнего подтверждённого «игра жива» | это ожидаемо |
| Аддон не грузится | нет `config.json`/`core/`/`start_file`; ошибка в журнале аддона (`activity.json`) | открыть Control Center → «Мониторинг» |
| Зависимости аддона не ставятся повторно | маркер `.requirements_installed` записан даже при неудаче | удалить маркер в папке аддона |
| Аддон выключен, но снова включился | список `addons_list` перезаписывается загруженными; если ключа нет — включены все | включать/выключать через Control Center |
| Sunshine: `unauthorized` | неверный логин/пароль | вкладка «ТВ» → «Авто» создаст пользователя `gorlauncher` |
| Sunshine: стрим обрывается при «Синхронизации» | `SyncWorker` перезапускает Sunshine | не синхронизировать во время стрима; приложение лаунчера добавляется через API без перезапуска |
| Moonlight не найден | не найден ни в `Moonlight/`, ни в `PATH` | положить Moonlight-Qt в папку `Moonlight/` рядом с лаунчером |
| Сопряжение не проходит | PIN нужно подтвердить в веб-панели Sunshine за 45 с | повторить, вводя тот же 4-значный PIN |
| Рассылка вкладок не доходит | брандмауэр, другая подсеть, неверный порт | открыть UDP 51888; одинаковый порт на обоих ПК |
| Реклама не режется на главной странице | главный фрейм намеренно не блокируется | ожидаемо; режутся подзапросы и косметика |
| Забыт мастер-пароль Vault | ключ не хранится | восстановление невозможно; удалить `passwords.vault` и создать заново |
| Лаунчер не запускается второй раз | single instance | второй запуск показывает первое окно; `--new-instance` обходит защиту |
| Окно выбора обложки не открылось | лаунчер не отвечает по IPC за 1,5 с | откроется запасное окно `ImagePickerDialog` |

---

<a id="s19"></a>
## 19. Глоссарий

| Термин | Значение |
|---|---|
| **Hard link (жёсткая ссылка)** | второе имя того же файла на NTFS; запись «на месте» видна по обоим именам |
| **Junction (`mklink /J`)** | ссылка на каталог в NTFS без прав администратора |
| **Fernet** | симметричное шифрование с аутентификацией (AES-128-CBC + HMAC-SHA256) из `cryptography` |
| **PBKDF2** | растяжение пароля в ключ многократным хэшированием (здесь 390 000 раундов) |
| **QThread** | поток Qt; результат возвращается сигналами |
| **QWebEngine** | Chromium внутри Qt |
| **Request interceptor** | перехватчик сетевых запросов профиля (используется AdBlock) |
| **Cosmetic filter** | скрытие рекламных блоков на странице скриптом/CSS |
| **Single instance** | один экземпляр приложения; повторный запуск передаёт команду первому |
| **IPC** | межпроцессное взаимодействие (здесь `QLocalServer`) |
| **Sunshine** | серверная часть игрового стриминга (Moonlight-совместимая) |
| **Moonlight** | клиент стриминга на ТВ/другом ПК |
| **Big Picture / 10-foot UI** | интерфейс для управления с дивана геймпадом |
| **XInput** | API геймпадов Xbox в Windows |
| **Токен темы** | именованный цвет `{accent}`, подставляемый в QSS |
| **QSS** | Qt Style Sheets — аналог CSS для виджетов Qt |
| **Хук / событие / фильтр** | точки расширения для аддонов: `emit_event`, `allow`, `apply_filter` |
| **Watchdog** | перехватчик, пишущий действия аддонов в журнал |
| **Orphan / `.corrupt-*` / `.bak`** | резервные копии, создаваемые при разрыве ссылок и порче файлов |

---

<a id="appA"></a>
## Приложение A. Полная карта ключей локализации

Таблицы сгенерированы программно из `lang/ru.json` и `lang/en.json`. Колонки: ключ → русский текст → английский текст. Плейсхолдеры `{имя}` подставляются через `tr(key, имя=значение)`. Наличие ключей в `es.json` и `hy.json` проверено: наборы ключей во всех четырёх файлах идентичны (417 листовых ключей, расхождений 0).


### A.1. Раздел `_meta` (2)

| Ключ | RU | EN |
|---|---|---|
| `_meta.code` | ru | en |
| `_meta.name` | Русский | English |

### A.2. Раздел `common` (10)

| Ключ | RU | EN |
|---|---|---|
| `common.error` | Ошибка | Error |
| `common.delete` | Удалить | Delete |
| `common.cancel` | ОТМЕНА | CANCEL |
| `common.save` | СОХРАНИТЬ | SAVE |
| `common.browse` | 📁 Обзор | 📁 Browse |
| `common.no_group` | Без группы | No group |
| `common.hours_short` | ч | h |
| `common.minutes_short` | м | m |
| `common.all_files` | Все файлы (*.*) | All files (*.*) |
| `common.images_filter` | Изображения (*.png *.jpg *.jpeg) | Images (*.png *.jpg *.jpeg) |

### A.3. Раздел `launcher` (46)

| Ключ | RU | EN |
|---|---|---|
| `launcher.window_title` | GOR Launcher | GOR Launcher |
| `launcher.app_title` | GOR UNIVERSAL | GOR UNIVERSAL |
| `launcher.search_placeholder` | 🔍 Поиск в библиотеке... | 🔍 Search library... |
| `launcher.menu_wheel` | 🎡 КОЛЕСО ФОРТУНЫ | 🎡 FORTUNE WHEEL |
| `launcher.menu_sunshine` | ⚙️ SUNSHINE | ⚙️ SUNSHINE |
| `launcher.menu_exporter` | 📦 ЭКСПОРТ | 📦 EXPORT |
| `launcher.menu_language` | 🌐 ЯЗЫК | 🌐 LANGUAGE |
| `launcher.tab_library` | 📚 БИБЛИОТЕКА | 📚 LIBRARY |
| `launcher.tab_favorites` | ⭐️ ИЗБРАННОЕ | ⭐️ FAVORITES |
| `launcher.tab_history` | 📜 ИСТОРИЯ | 📜 HISTORY |
| `launcher.tab_browser` | 🌐 БРАУЗЕР | 🌐 BROWSER |
| `launcher.add_game_btn` | ➕ ДОБАВИТЬ ИГРУ | ➕ ADD GAME |
| `launcher.add_group_btn` | 📁 НОВАЯ ГРУППА | 📁 NEW GROUP |
| `launcher.clear_history_btn` | 🗑️ ОЧИСТИТЬ ИСТОРИЮ | 🗑️ CLEAR HISTORY |
| `launcher.stats` | Всего игр: {count} \| Наиграно: {hours}ч | Total games: {count} \| Playtime: {hours}h |
| `launcher.standalone_title` | Отдельные игры / Без группы | Standalone games / No group |
| `launcher.addon_manager_btn` | ⚙️ ADDON MANAGER | ⚙️ ADDON MANAGER |
| `launcher.restart_tooltip` | Полностью перезапустить GOR Launcher | Fully restart GOR Launcher |
| `launcher.restart_confirm_title` | Перезапуск лаунчера | Restart launcher |
| `launcher.restart_confirm_text` | Перезапустить GOR Launcher сейчас?⏎Текущее окно будет закрыто и открыто заново со всеми аддонами и функциями. | Restart GOR Launcher now?⏎The current window will be closed and relaunched with all addons and features. |
| `launcher.restart_error_title` | Ошибка перезапуска | Restart error |
| `launcher.restart_error_text` | Не удалось перезапустить лаунчер:⏎{error} | Failed to restart the launcher:⏎{error} |
| `launcher.update_available_btn` | ⬆️ ДОСТУПНО ОБНОВЛЕНИЕ ({version}) | ⬆️ UPDATE AVAILABLE ({version}) |
| `launcher.language_restart_title` | Язык изменён | Language changed |
| `launcher.language_restart_text` | Язык изменён на «{name}».⏎Для полного применения изменений лаунчер нужно перезапустить.⏎Перезапустить сейчас? | Language changed to "{name}".⏎The launcher needs to restart for the interface to update fully.⏎Restart now? |
| `launcher.sort_label` | Сортировка: | Sort: |
| `launcher.sort_default` | Без сортировки | No sorting |
| `launcher.sort_name_asc` | Имя (А-Я) | Name (A-Z) |
| `launcher.sort_name_desc` | Имя (Я-А) | Name (Z-A) |
| `launcher.sort_playtime_desc` | Наиграно (больше → меньше) | Playtime (high → low) |
| `launcher.sort_playtime_asc` | Наиграно (меньше → больше) | Playtime (low → high) |
| `launcher.sort_newest` | Сначала новые | Newest first |
| `launcher.tab_menu_expand_window` | 🗖 Развернуть вкладку на всё окно | 🗖 Expand tab to fill window |
| `launcher.tab_menu_fullscreen` | ⛶ На весь экран | ⛶ Fullscreen |
| `launcher.tab_menu_detach` | 🗗 Открыть в отдельном окне | 🗗 Open in separate window |
| `launcher.tab_menu_restore` | ↩ Обычный вид | ↩ Normal view |
| `launcher.detached_return_btn` | ↩ Вернуть в GOR Launcher | ↩ Return to GOR Launcher |
| `launcher.detached_window_title` | {title} — GOR Launcher | {title} — GOR Launcher |
| `launcher.tray_open` | 🗖 Открыть GOR Launcher | 🗖 Open GOR Launcher |
| `launcher.tray_quit` | ❌ Выход | ❌ Quit |
| `launcher.tray_title` | GOR Launcher | GOR Launcher |
| `launcher.tray_hidden_text` | Лаунчер свёрнут в трей, пока запущена игра. Значок вернёт окно обратно. | The launcher is minimized to the tray while a game is running. Click the icon to bring it back. |
| `launcher.tray_minimize_tooltip` | Свернуть в трей | Minimize to tray |
| `launcher.menu_moonlight` | 🌙 MOONLIGHT | 🌙 MOONLIGHT |
| `launcher.menu_big_picture` | 📺 Режим Big Picture | 📺 Big Picture mode |
| `launcher.menu_tv` | 📺 ПОДКЛЮЧИТЬ ТВ | 📺 CONNECT TV |

### A.4. Раздел `game_card` (9)

| Ключ | RU | EN |
|---|---|---|
| `game_card.run` | ЗАПУСТИТЬ | LAUNCH |
| `game_card.stop` | ОСТАНОВИТЬ | STOP |
| `game_card.time_static` | ⏱ {h}ч {m}м | ⏱ {h}h {m}m |
| `game_card.remove_favorite` | ❌ Убрать из избранного | ❌ Remove from favorites |
| `game_card.add_favorite` | ⭐️ Добавить в избранное | ⭐️ Add to favorites |
| `game_card.edit` | 📝 Изменить | 📝 Edit |
| `game_card.delete` | 🗑️ Удалить | 🗑️ Delete |
| `game_card.copy_path` | 📋 Скопировать путь | 📋 Copy path |
| `game_card.launch_error` | Не удалось запустить:⏎{error} | Failed to launch:⏎{error} |

### A.5. Раздел `history_card` (3)

| Ключ | RU | EN |
|---|---|---|
| `history_card.delete_entry` | 🗑️ Удалить запись | 🗑️ Delete entry |
| `history_card.session_time` | ⌛ Сессия: {h}ч {m}м | ⌛ Session: {h}h {m}m |
| `history_card.date_prefix` | 📅 {date} | 📅 {date} |

### A.6. Раздел `group` (4)

| Ключ | RU | EN |
|---|---|---|
| `group.rename` | ✏️ Переименовать | ✏️ Rename |
| `group.delete_group` | ❌ Удалить группу | ❌ Delete group |
| `group.delete_confirm_title` | Удаление группы | Delete group |
| `group.delete_confirm_text` | Точно удалить группу «{name}»?⏎Все игры будут перемещены в список без группы. | Are you sure you want to delete the group «{name}»?⏎All games will be moved to the no-group list. |

### A.7. Раздел `game_delete` (2)

| Ключ | RU | EN |
|---|---|---|
| `game_delete.confirm_title` | Удаление игры | Delete game |
| `game_delete.confirm_text` | Точно удалить «{name}»? | Are you sure you want to delete «{name}»? |

### A.8. Раздел `history_clear` (2)

| Ключ | RU | EN |
|---|---|---|
| `history_clear.confirm_title` | Очистка истории | Clear history |
| `history_clear.confirm_text` | Точно полностью очистить историю запусков? | Are you sure you want to completely clear the launch history? |

### A.9. Раздел `sunshine_error` (2)

| Ключ | RU | EN |
|---|---|---|
| `sunshine_error.title` | Ошибка | Error |
| `sunshine_error.text` | Не удалось запустить Sunshine Control:⏎{error} | Failed to start Sunshine Control:⏎{error} |

### A.10. Раздел `moonlight_error` (2)

| Ключ | RU | EN |
|---|---|---|
| `moonlight_error.title` | Ошибка | Error |
| `moonlight_error.text` | Не удалось запустить Moonlight Control:⏎{error} | Failed to launch Moonlight Control:⏎{error} |

### A.11. Раздел `exporter_error` (2)

| Ключ | RU | EN |
|---|---|---|
| `exporter_error.title` | Ошибка | Error |
| `exporter_error.text` | Не удалось запустить Exporter:⏎{error} | Failed to start Exporter:⏎{error} |

### A.12. Раздел `game_editor` (26)

| Ключ | RU | EN |
|---|---|---|
| `game_editor.title` | Настройки игры | Game settings |
| `game_editor.name_label` | Название мода/игры: | Mod/game name: |
| `game_editor.path_label` | Файл запуска (любой тип файла): | Launch file (any file type): |
| `game_editor.root_label` | Корневая папка игры: | Game root folder: |
| `game_editor.root_btn` | 📂 Папка | 📂 Folder |
| `game_editor.args_label` | Аргументы запуска: | Launch arguments: |
| `game_editor.args_placeholder` | -game folder_name | -game folder_name |
| `game_editor.icon_label` | Обложка (PNG/JPG): | Cover (PNG/JPG): |
| `game_editor.icon_btn` | 🖼️ Фото | 🖼️ Photo |
| `game_editor.icon_browser_btn` | 🌐 Найти в браузере | 🌐 Find in browser |
| `game_editor.picker_title` | Выбор обложки из браузера | Pick a cover from the browser |
| `game_editor.picker_hint` | Найди подходящую картинку любым способом (поиск, сайт игры и т.д.), нажми на неё ПРАВОЙ кнопкой мыши и выбери «Использовать как обложку игры». | Find a suitable image any way you like (search, the game's website, etc.), then right-click it and choose “Use as game cover”. |
| `game_editor.picker_switch_hint` | 🌐 Открылась служебная вкладка «🖼️ Обложка» в главном окне лаунчера (вкладка «Браузер») — переключись туда, найди картинку и кликни по ней правой кнопкой мыши. | 🌐 A “🖼️ Cover” tab has opened in the main launcher window (the Browser tab) — switch there, find an image and right-click it. |
| `game_editor.picker_go` | Перейти | Go |
| `game_editor.picker_use_as_cover` | 🖼️ Использовать как обложку игры | 🖼️ Use as game cover |
| `game_editor.picker_downloading` | Скачивание картинки… | Downloading image… |
| `game_editor.picker_download_error` | Не удалось скачать картинку: {error} | Failed to download the image: {error} |
| `game_editor.no_photo` | Нет фото | No photo |
| `game_editor.file_not_found` | Файл не найден | File not found |
| `game_editor.favorite_check` | ⭐️ ДОБАВИТЬ В ИЗБРАННОЕ | ⭐️ ADD TO FAVORITES |
| `game_editor.group_label` | Назначить группу: | Assign to group: |
| `game_editor.name_empty_error` | Название игры не может быть пустым! | Game name cannot be empty! |
| `game_editor.name_exists_error` | Игра с таким названием уже существует! | A game with this name already exists! |
| `game_editor.select_launch_file` | Выберите файл запуска | Select launch file |
| `game_editor.select_root_folder` | Выберите корневую папку игры | Select game root folder |
| `game_editor.select_cover` | Выберите обложку | Select cover |

### A.13. Раздел `group_editor` (7)

| Ключ | RU | EN |
|---|---|---|
| `group_editor.title_edit` | Изменить группу | Edit group |
| `group_editor.title_create` | Создать группу | Create group |
| `group_editor.label` | Введите название группы: | Enter group name: |
| `group_editor.placeholder` | введите название группы | type group name |
| `group_editor.name_empty_error` | Название группы не может быть пустым! | Group name cannot be empty! |
| `group_editor.name_exists_edit_error` | Группа с таким названием уже существует! | A group with this name already exists! |
| `group_editor.name_exists_create_error` | Такая группа уже существует! | This group already exists! |

### A.14. Раздел `exporter` (16)

| Ключ | RU | EN |
|---|---|---|
| `exporter.window_title` | GOR Packer | GOR Packer |
| `exporter.default_name` | MyLibraryExport | MyLibraryExport |
| `exporter.name_label` | Название итогового архива: | Final archive name: |
| `exporter.save_location_label` | Куда сохранить zip: | Where to save the zip: |
| `exporter.select_all_check` | Выбрать все игры | Select all games |
| `exporter.include_json_check` | Включить games_data.json | Include games_data.json |
| `exporter.select_games_label` | Выберите игры для экспорта: | Select games to export: |
| `exporter.start_export_btn` | НАЧАТЬ ЭКСПОРТ | START EXPORT |
| `exporter.select_folder_dialog_title` | Выберите папку для сохранения | Select folder to save |
| `exporter.error_no_games` | Выберите игры или включите экспорт games_data.json! | Select games or enable games_data.json export! |
| `exporter.error_no_folder` | Выберите папку для сохранения! | Select a folder to save to! |
| `exporter.progress_title` | Экспорт... | Exporting... |
| `exporter.total_progress_label` | ОБЩИЙ ПРОГРЕСС: | TOTAL PROGRESS: |
| `exporter.game_label` | Игра: {name} | Game: {name} |
| `exporter.packing_label` | Упаковка {name} | Packing {name} |
| `exporter.assembling_label` | Сборка мастер-архива | Assembling master archive |

### A.15. Раздел `control_center` (32)

| Ключ | RU | EN |
|---|---|---|
| `control_center.window_title` | GOR Control Center - Управление аддонами | GOR Control Center - Addon Management |
| `control_center.empty_page_text` | ⬅️ Выберите аддон слева, чтобы открыть его интерфейс | ⬅️ Select an addon on the left to open its interface |
| `control_center.load_error_title` | Не удалось загрузить аддон | Failed to load addon |
| `control_center.status_card_title` | Статус аддона | Addon status |
| `control_center.status_unknown` | НЕИЗВЕСТНО | UNKNOWN |
| `control_center.status_active` | ● АКТИВЕН | ● ACTIVE |
| `control_center.status_inactive` | ● ОТКЛЮЧЁН | ● DISABLED |
| `control_center.select_addon_hint` | Выберите аддон слева, чтобы увидеть подробности. | Select an addon on the left to see details. |
| `control_center.log_card_title` | Журнал активности / запросы аддона | Activity log / addon requests |
| `control_center.controls_card_title` | Управление аддоном | Addon controls |
| `control_center.approve_btn` | ✅ Одобрить запрос | ✅ Approve request |
| `control_center.restart_addon_btn` | 🔁 Перезапустить аддон | 🔁 Restart addon |
| `control_center.revoke_btn` | ⛔ Отклонить / Отключить | ⛔ Decline / Disable |
| `control_center.no_description` | Описание для этого аддона не указано в config.json. | No description provided for this addon in config.json. |
| `control_center.desc_version` | {desc}⏎Версия: {version} | {desc}⏎Version: {version} |
| `control_center.no_activity` | Для этого аддона нет записей активности. | No activity entries for this addon. |
| `control_center.version_unknown` | версия неизвестна | version unknown |
| `control_center.tab_view` | 🌐 Просмотр | 🌐 View |
| `control_center.tab_monitoring` | 📊 Мониторинг | 📊 Monitoring |
| `control_center.save_error_title` | Ошибка сохранения | Save error |
| `control_center.approve_done_title` | Готово | Done |
| `control_center.approve_done_text` | Запрос аддона «{name}» одобрен. | Addon «{name}» request approved. |
| `control_center.restart_title` | Перезапуск | Restart |
| `control_center.restart_text` | Аддон «{name}» будет перезапущен. | Addon «{name}» will be restarted. |
| `control_center.revoke_confirm_title` | Отключение аддона | Disable addon |
| `control_center.revoke_confirm_text` | Отключить «{name}»? | Disable «{name}»? |
| `control_center.addon_load_failed` | Не удалось загрузить аддон. Проверьте файлы web/index.html. | The addon failed to load. Check the web/index.html files. |
| `control_center.web_not_found` | Файл index.html не найден по пути:<br><code>{path}</code> | index.html file not found at:<br><code>{path}</code> |
| `control_center.sample_request` | Аддон запросил доступ к папке сохранений. | The addon requested access to the save folder. |
| `control_center.sample_change` | Разрешение экрана изменено на 1920x1080. | Screen resolution setting changed to 1920x1080. |
| `control_center.sample_info` | Аддон инициализировался без ошибок. | The addon initialized without errors. |
| `control_center.sample_error` | Не удалось найти файл конфигурации трансляции. | Could not find the streaming configuration file. |

### A.16. Раздел `sunshine` (29)

| Ключ | RU | EN |
|---|---|---|
| `sunshine.window_title` | Sunshine Control | Sunshine Control |
| `sunshine.title` | SUNSHINE CONTROL | SUNSHINE CONTROL |
| `sunshine.status_group` | 📡 Статус | 📡 Status |
| `sunshine.checking` | Проверка... | Checking... |
| `sunshine.running` | Sunshine: Запущен | Sunshine: Running |
| `sunshine.stopped` | Sunshine: Остановлен | Sunshine: Stopped |
| `sunshine.open_web_btn` | 🌐 Открыть веб-панель | 🌐 Open web panel |
| `sunshine.open_web_tooltip` | Открыть {url} в браузере по умолчанию | Open {url} in the default browser |
| `sunshine.control_group` | 🎮 Управление | 🎮 Controls |
| `sunshine.sync_btn` | 🔄 ЗАПУСТИТЬ И СИНХРОНИЗИРОВАТЬ SUNSHINE | 🔄 START & SYNC SUNSHINE |
| `sunshine.sync_tooltip` | Прочитать games_data.json, обновить apps.json и перезапустить Sunshine | Read games_data.json, update apps.json and restart Sunshine |
| `sunshine.stop_btn` | 🛑 ПРИНУДИТЕЛЬНО ОСТАНОВИТЬ SUNSHINE | 🛑 FORCE STOP SUNSHINE |
| `sunshine.stop_tooltip` | Немедленно завершить процесс Sunshine | Immediately terminate the Sunshine process |
| `sunshine.tab_home` | 🎮 Главная | 🎮 Home |
| `sunshine.auth_group` | 🔐 Учётные данные | 🔐 Credentials |
| `sunshine.new_login_label` | Новый логин: | New login: |
| `sunshine.login_placeholder` | Введите логин... | Enter login... |
| `sunshine.new_password_label` | Новый пароль: | New password: |
| `sunshine.password_placeholder` | Введите пароль... | Enter password... |
| `sunshine.save_creds_btn` | СОХРАНИТЬ ДАННЫЕ | SAVE CREDENTIALS |
| `sunshine.save_creds_tooltip` | Применить новый логин/пароль к Sunshine и перезапустить его | Apply the new login/password to Sunshine and restart it |
| `sunshine.tab_auth` | 🔐 Авторизация | 🔐 Authorization |
| `sunshine.log_group` | 📝 Журнал событий | 📝 Event log |
| `sunshine.tab_log` | 📝 Журнал | 📝 Log |
| `sunshine.success_title` | Успешно | Success |
| `sunshine.status_title` | Статус | Status |
| `sunshine.done_title` | Готово | Done |
| `sunshine.process_stopped` | Процесс Sunshine остановлен. | The Sunshine process has been stopped. |
| `sunshine.data_not_found` | games_data.json не найден! | games_data.json not found! |

### A.17. Раздел `sunshine_log` (24)

| Ключ | RU | EN |
|---|---|---|
| `sunshine_log.app_started` | Приложение запущено. | Application started. |
| `sunshine_log.opening_web` | Открытие веб-панели: {url} | Opening web panel: {url} |
| `sunshine_log.sync_start` | Начало синхронизации... | Starting synchronization... |
| `sunshine_log.data_not_found_log` | Ошибка: games_data.json не найден. | Error: games_data.json not found. |
| `sunshine_log.process_stopped` | Процесс Sunshine остановлен. | The Sunshine process has been stopped. |
| `sunshine_log.creds_empty` | Логин или пароль не заполнены. | Login or password not filled in. |
| `sunshine_log.reading_data` | Чтение games_data.json... | Reading games_data.json... |
| `sunshine_log.apps_json_warning` | Предупреждение: ошибка чтения apps.json: {error} | Warning: error reading apps.json: {error} |
| `sunshine_log.games_found` | Найдено игр: {count} | Games found: {count} |
| `sunshine_log.pillow_missing` | Pillow не установлен, конвертация иконки для '{name}' пропущена, используется исходный файл. | Pillow is not installed, icon conversion skipped for '{name}', using the original file. |
| `sunshine_log.icon_convert_error` | Ошибка конвертации иконки '{name}': {error} | Error converting icon '{name}': {error} |
| `sunshine_log.icon_copy_error` | Ошибка копирования иконки '{name}': {error} | Error copying icon '{name}': {error} |
| `sunshine_log.game_added` | Добавлено: {name} | Added: {name} |
| `sunshine_log.apps_saved_restart` | apps.json сохранён. Перезапуск Sunshine... | apps.json saved. Restarting Sunshine... |
| `sunshine_log.sync_success` | Конфигурация обновлена, Sunshine перезапущен! | Configuration updated and Sunshine restarted! |
| `sunshine_log.sync_error` | Ошибка синхронизации: {error} | Synchronization error: {error} |
| `sunshine_log.stopping` | Остановка Sunshine... | Stopping Sunshine... |
| `sunshine_log.starting` | Запуск Sunshine... | Starting Sunshine... |
| `sunshine_log.restarted` | Sunshine перезапущен. | Sunshine restarted. |
| `sunshine_log.restart_error` | Ошибка перезапуска: {error} | Restart error: {error} |
| `sunshine_log.stopping_before_creds` | Остановка Sunshine перед сменой учётных данных... | Stopping Sunshine before changing credentials... |
| `sunshine_log.applying_creds` | Применение новых данных... | Applying new credentials... |
| `sunshine_log.creds_applied` | Учётные данные применены, процесс запущен. | Credentials applied, process started. |
| `sunshine_log.creds_error` | Ошибка применения учётных данных: {error} | Error applying credentials: {error} |

### A.18. Раздел `wheel` (11)

| Ключ | RU | EN |
|---|---|---|
| `wheel.window_title` | Случайная игра — Колесо фортуны | Random Game — Fortune Wheel |
| `wheel.default_title` | Во что сыграем сегодня? | What to play today? |
| `wheel.load_error` | Ошибка загрузки:⏎{error} | Load error:⏎{error} |
| `wheel.file_not_found` | Файл не найден.⏎Проверены пути:⏎{paths} | File not found.⏎Tried:⏎{paths} |
| `wheel.read_error` | {error_type}: {error}⏎Путь: {path} | {error_type}: {error}⏎Path: {path} |
| `wheel.empty_list` | games_data.json загружен, но список игр пуст⏎(нет записей в groups/standalone) | games_data.json loaded, but the game list is empty⏎(no entries in groups/standalone) |
| `wheel.spin_btn` | КРУТИТЬ КОЛЕСО! | SPIN THE WHEEL! |
| `wheel.play_btn` | ИГРАТЬ В ВЫБРАННУЮ ИГРУ | PLAY SELECTED GAME |
| `wheel.nothing_to_spin` | Список игр пуст! Крутить нечего. | The game list is empty! Nothing to spin. |
| `wheel.result` | Выпало: {name}! | Landed on: {name}! |
| `wheel.default_game_name` | Игра | Game |

### A.19. Раздел `updater` (27)

| Ключ | RU | EN |
|---|---|---|
| `updater.window_title` | Обновление GOR Launcher | GOR Launcher Update |
| `updater.status_initial` | Текущая версия: {version}.⏎Нажмите «ПРОВЕРИТЬ ОБНОВЛЕНИЯ». | Current version: {version}.⏎Click «CHECK FOR UPDATES». |
| `updater.check_btn` | ПРОВЕРИТЬ ОБНОВЛЕНИЯ | CHECK FOR UPDATES |
| `updater.install_btn` | УСТАНОВИТЬ ОБНОВЛЕНИЕ | INSTALL UPDATE |
| `updater.learn_more_btn` | УЗНАТЬ БОЛЬШЕ | УЗНАТЬ БОЛЬШЕ |
| `updater.confirm_title` | Подтверждение | Confirmation |
| `updater.confirm_text` | Установить обновление сейчас?⏎Все папки и файл games_data.json затронуты не будут. | Install the update now?⏎All folders and the games_data.json file will not be affected. |
| `updater.check_first_hint` | Сначала нажми «Проверить обновления», чтобы узнать, есть ли новая версия. | Сначала нажми «Проверить обновления», чтобы узнать, есть ли новая версия. |
| `updater.already_latest` | У вас уже установлена последняя версия ({version}). | You already have the latest version ({version}). |
| `updater.update_available` | Доступна новая версия: {remote} (текущая: {current}). | A new version is available: {remote} (current: {current}). |
| `updater.restart_prompt` | {message}⏎⏎Перезапустить лаунчер сейчас? | {message}⏎⏎Restart the launcher now? |
| `updater.cancelling` | Отмена обновления... | Cancelling update... |
| `updater.update_cancelled` | Обновление отменено. | Update cancelled. |
| `updater.checking_status` | Проверка обновлений... | Checking for updates... |
| `updater.version_not_found_error` | Файл version.json не найден в репозитории ({path}). Убедитесь, что он туда добавлен. | version.json not found in the repository ({path}). Make sure it was added there. |
| `updater.network_error` | Ошибка сети: {error} | Network error: {error} |
| `updater.generic_error` | Ошибка: {error} | Error: {error} |
| `updater.downloading` | Загрузка архива с GitHub... | Downloading archive from GitHub... |
| `updater.extracting` | Распаковка архива... | Extracting archive... |
| `updater.source_not_found` | Не удалось найти корневую папку репозитория внутри скачанного архива. | Could not find the repository root folder inside the downloaded archive. |
| `updater.safe_updating` | Безопасное обновление файлов... | Safely updating files... |
| `updater.update_done_status` | Обновление завершено! | Update complete! |
| `updater.update_done_message` | Обновление до версии {version} успешно установлено.⏎Перезапустите лаунчер, чтобы применить изменения. | Update to version {version} installed successfully.⏎Restart the launcher to apply the changes. |
| `updater.skip_folder` | Пропуск папки (не затронута): {name} | Skipping folder (untouched): {name} |
| `updater.skip_protected` | Пропуск защищённого файла: {name} | Skipping protected file: {name} |
| `updater.updating_file` | Обновление файла: {name} | Updating file: {name} |
| `updater.unknown_version` | неизвестна | unknown |

### A.20. Раздел `browser` (22)

| Ключ | RU | EN |
|---|---|---|
| `browser.menu.settings` | ⚙️ Настройки браузера | ⚙️ Browser settings |
| `browser.menu.find_on_page` | 🔎 Найти на странице (Ctrl+F) | 🔎 Find on page (Ctrl+F) |
| `browser.menu.devtools` | 🛠️ Инструменты разработчика (F12) | 🛠️ Developer tools (F12) |
| `browser.menu.restore_tab` | ↩️ Вернуть закрытую вкладку (Ctrl+Shift+T) | ↩️ Reopen closed tab (Ctrl+Shift+T) |
| `browser.menu.save_session_as_group` | 💾 Сохранить текущую сессию как группу | 💾 Save current session as a group |
| `browser.settings.tab_general` | 🔍  Общие | 🔍  General |
| `browser.settings.tab_appearance` | 🎨  Внешний вид | 🎨  Appearance |
| `browser.settings.tab_backup` | 💾  Резервная копия | 💾  Backup |
| `browser.settings.tab_security` | 🛡️  Безопасность | 🛡️  Security |
| `browser.settings.tab_extensions` | 🧩  Расширения | 🧩  Extensions |
| `browser.settings.cancel` | Отмена | Cancel |
| `browser.settings.save` | Сохранить | Save |
| `browser.tab.pin` | 📌 Закрепить вкладку | 📌 Pin tab |
| `browser.tab.unpin` | 📌 Открепить вкладку | 📌 Unpin tab |
| `browser.tab.close` | ✕ Закрыть вкладку | ✕ Close tab |
| `browser.tab.close_others` | Закрыть остальные вкладки | Close other tabs |
| `browser.tab.close_right` | Закрыть вкладки справа | Close tabs to the right |
| `browser.tab.incognito_label` | Инкогнито | Incognito |
| `browser.tab.home_label` | Новая вкладка | New tab |
| `browser.sidebar.bookmarks` | Закладки | Bookmarks |
| `browser.sidebar.history` | История | History |
| `browser.sidebar.groups` | Группы | Groups |

### A.21. Раздел `big_picture` (48)

| Ключ | RU | EN |
|---|---|---|
| `big_picture.tab_library` | Библиотека | Library |
| `big_picture.tab_favorites` | Избранное | Favorites |
| `big_picture.tab_recent` | Недавние | Recent |
| `big_picture.tab_stream` | Стрим | Stream |
| `big_picture.hint_ok` | Выбрать | Select |
| `big_picture.hint_back` | Назад | Back |
| `big_picture.hint_favorite` | Избранное | Favorite |
| `big_picture.hint_actions` | Действия | Actions |
| `big_picture.hint_section` | Раздел | Section |
| `big_picture.hint_menu` | Меню | Menu |
| `big_picture.empty_library` | Библиотека пуста.⏎Добавьте игры в обычном режиме лаунчера. | Your library is empty.⏎Add games in the regular launcher mode. |
| `big_picture.empty_favorites` | В избранном пока ничего нет.⏎Нажмите X на игре, чтобы добавить её. | No favorites yet.⏎Press X on a game to add it. |
| `big_picture.empty_recent` | Вы ещё ничего не запускали. | You haven't launched anything yet. |
| `big_picture.running` | Запущена | Running |
| `big_picture.never_played` | Ещё не запускалась | Never played |
| `big_picture.playtime` | Наиграно: {time} | Played: {time} |
| `big_picture.time_hm` | {h} ч {m} мин | {h} h {m} min |
| `big_picture.time_m` | {m} мин | {m} min |
| `big_picture.time_lt_min` | меньше минуты | under a minute |
| `big_picture.already_running` | Игра уже запущена | The game is already running |
| `big_picture.launch_failed` | Не удалось запустить игру | Could not launch the game |
| `big_picture.gamepad_on` | 🎮 Геймпад подключён | 🎮 Gamepad connected |
| `big_picture.gamepad_off` | 🎮 Геймпад не найден (работает клавиатура) | 🎮 No gamepad found (keyboard works) |
| `big_picture.menu_title` | Меню | Menu |
| `big_picture.menu_resume` | Продолжить | Resume |
| `big_picture.menu_exit` | Выйти в обычный режим | Exit to regular mode |
| `big_picture.menu_quit` | Закрыть лаунчер | Quit launcher |
| `big_picture.actions_title` | Действия | Actions |
| `big_picture.action_play` | Запустить | Play |
| `big_picture.action_fav_add` | Добавить в избранное | Add to favorites |
| `big_picture.action_fav_remove` | Убрать из избранного | Remove from favorites |
| `big_picture.action_cancel` | Отмена | Cancel |
| `big_picture.session_done` | Сессия завершена: {time} | Session finished: {time} |
| `big_picture.stream_hosts` | Хосты (Sunshine) | Hosts (Sunshine) |
| `big_picture.stream_apps` | Приложения на хосте | Apps on host |
| `big_picture.stream_quality` | Качество стрима | Stream quality |
| `big_picture.stream_no_moonlight` | Moonlight не найден.⏎Укажите путь к нему в обычном режиме (меню ☰ → Moonlight). | Moonlight not found.⏎Set its path in regular mode (☰ menu → Moonlight). |
| `big_picture.stream_no_hosts` | Нет сохранённых хостов.⏎Добавьте и сопрягите хост в обычном режиме (меню ☰ → Moonlight). | No saved hosts.⏎Add and pair a host in regular mode (☰ menu → Moonlight). |
| `big_picture.stream_select_host` | Выберите хост, чтобы увидеть его приложения | Select a host to see its apps |
| `big_picture.stream_loading` | Загружаю список приложений… | Loading app list… |
| `big_picture.stream_apps_default` | Не удалось получить список с хоста, показан стандартный: {error} | Could not get the list from the host, showing defaults: {error} |
| `big_picture.stream_starting` | Запускаю стрим: {app} | Starting stream: {app} |
| `big_picture.stream_error` | Ошибка стрима: {error} | Stream error: {error} |
| `big_picture.stream_ended` | Стрим завершён | Stream ended |
| `big_picture.stream_resolution` | Разрешение | Resolution |
| `big_picture.stream_fps` | Кадров/с | Frames/s |
| `big_picture.stream_bitrate` | Битрейт | Bitrate |
| `big_picture.stream_hint_cycle` | A — сменить значение | A — change value |

### A.22. Раздел `tv_setup` (39)

| Ключ | RU | EN |
|---|---|---|
| `tv_setup.tab` | 📺 ТВ | 📺 TV |
| `tv_setup.intro` | Подключение телевизора (Android TV) к этому ПК. Установите на ТВ приложение Moonlight и пройдите шаги ниже: открывать веб-интерфейс Sunshine в браузере не нужно. | Connect your TV (Android TV) to this PC. Install the Moonlight app on the TV and follow the steps below - there is no need to open the Sunshine web UI in a browser. |
| `tv_setup.step1` | 1. Вход в Sunshine | 1. Sign in to Sunshine |
| `tv_setup.step2` | 2. Приложение лаунчера | 2. Launcher app |
| `tv_setup.step3` | 3. Сопряжение телевизора | 3. Pair the TV |
| `tv_setup.step4` | 4. Подключённые устройства | 4. Connected devices |
| `tv_setup.status_down` | Sunshine не запущен или не отвечает | Sunshine is not running or not responding |
| `tv_setup.status_unauthorized` | Sunshine работает, нужен логин и пароль | Sunshine is running, login and password required |
| `tv_setup.status_ok` | Подключено к Sunshine | Connected to Sunshine |
| `tv_setup.login` | Логин | Login |
| `tv_setup.password` | Пароль | Password |
| `tv_setup.remember` | Запомнить (хранится открытым текстом в Sunshine/config) | Remember (stored as plain text in Sunshine/config) |
| `tv_setup.btn_connect` | Войти | Sign in |
| `tv_setup.btn_auto` | Создать логин автоматически | Create login automatically |
| `tv_setup.btn_start` | Запустить Sunshine | Start Sunshine |
| `tv_setup.auto_confirm` | Будет создан новый логин «{user}», прежний логин Sunshine перестанет работать. Продолжить? | A new login "{user}" will be created and the previous Sunshine login will stop working. Continue? |
| `tv_setup.auto_done` | Логин создан и сохранён.⏎⏎Логин: {user}⏎Пароль: {password}⏎⏎Запишите пароль: он понадобится для веб-интерфейса Sunshine. | Login created and saved.⏎⏎Login: {user}⏎Password: {password}⏎⏎Write the password down: you will need it for the Sunshine web UI. |
| `tv_setup.app_present` | ✓ «GorLauncher Big Picture» добавлено в Sunshine | ✓ "GorLauncher Big Picture" is added to Sunshine |
| `tv_setup.app_missing` | Приложения «GorLauncher Big Picture» в Sunshine пока нет | The "GorLauncher Big Picture" app is not in Sunshine yet |
| `tv_setup.btn_add_app` | Добавить / обновить в Sunshine | Add / update in Sunshine |
| `tv_setup.app_added` | Приложение добавлено в Sunshine. Теперь оно видно в Moonlight на ТВ. | The app was added to Sunshine. It is now visible in Moonlight on the TV. |
| `tv_setup.app_updated` | Приложение обновлено. | The app was updated. |
| `tv_setup.app_unchanged` | Приложение уже настроено. | The app is already set up. |
| `tv_setup.app_file_fallback` | Sunshine не принял запрос через API, поэтому запись добавлена в apps.json. Перезапустите Sunshine, чтобы она появилась. | Sunshine did not accept the API request, so the entry was written to apps.json. Restart Sunshine for it to appear. |
| `tv_setup.pair_howto` | На телевизоре откройте Moonlight и выберите этот ПК: появится PIN из 4 цифр. Введите его здесь и нажмите «Сопрячь» (PIN действует недолго). | On the TV open Moonlight and select this PC: a 4-digit PIN appears. Enter it here and press "Pair" (the PIN expires quickly). |
| `tv_setup.addresses` | Адреса этого ПК (если Moonlight не нашёл его сам, добавьте вручную): {ips} | Addresses of this PC (add manually if Moonlight does not find it by itself): {ips} |
| `tv_setup.no_address` | Адрес ПК определить не удалось | Could not determine the PC address |
| `tv_setup.device_name` | Название устройства | Device name |
| `tv_setup.pin` | PIN | PIN |
| `tv_setup.btn_pair` | Сопрячь | Pair |
| `tv_setup.pair_ok` | Устройство «{name}» сопряжено. Теперь в Moonlight на ТВ откройте этот ПК и выберите «GorLauncher Big Picture». | Device "{name}" is paired. Now open this PC in Moonlight on the TV and choose "GorLauncher Big Picture". |
| `tv_setup.pair_fail` | Не удалось сопрячь: {error} | Pairing failed: {error} |
| `tv_setup.pin_invalid` | PIN — это 4 цифры, которые показывает Moonlight на телевизоре | The PIN is the 4 digits shown by Moonlight on the TV |
| `tv_setup.btn_refresh` | Обновить | Refresh |
| `tv_setup.btn_unpair` | Отключить выбранное | Unpair selected |
| `tv_setup.unpair_confirm` | Отключить устройство «{name}»? Чтобы подключить его снова, понадобится новое сопряжение. | Unpair device "{name}"? You will need to pair it again to reconnect. |
| `tv_setup.no_devices` | Сопряжённых устройств пока нет | No paired devices yet |
| `tv_setup.error` | Ошибка: {error} | Error: {error} |
| `tv_setup.start_failed` | Sunshine не найден: {path} | Sunshine not found: {path} |

### A.23. Раздел `browser_custom` (10)

| Ключ | RU | EN |
|---|---|---|
| `browser_custom.window_title` | Кастомизация GOR Browser | GOR Browser Customization |
| `browser_custom.accent_color` | 🎨 Акцентный цвет (кнопки, часы): | 🎨 Accent Color (buttons, clock): |
| `browser_custom.select_accent` | Выбрать акцент | Select Accent |
| `browser_custom.topbar_color` | 📟 Цвет верхней панели (TopBar): | 📟 Top Bar Color: |
| `browser_custom.select_topbar` | Выбрать цвет панели | Select Bar Color |
| `browser_custom.ui_font` | 🔤 Шрифт интерфейса: | 🔤 UI Font: |
| `browser_custom.bg_image` | 🖼️ Фон стартовой страницы: | 🖼️ Start Page Background: |
| `browser_custom.default_dark` | Стандартный темный | Default Dark |
| `browser_custom.select_image` | Выбрать изображение | Select Image |
| `browser_custom.reset_default` | Сбросить в дефолт | Reset to Default |

### A.24. Раздел `broadcast` (8)

| Ключ | RU | EN |
|---|---|---|
| `broadcast.received` | 📡 {sender} прислал(о) {kind} | 📡 {sender} sent {kind} |
| `broadcast.device_default` | Устройство в сети | Network Device |
| `broadcast.links_count` | {count} ссылок(a) | {count} link(s) |
| `broadcast.links_count_host` | {count} ссылок(a): {host} | {count} link(s): {host} |
| `broadcast.open_all` | Открыть все | Open All |
| `broadcast.save_json` | Сохранить в JSON | Save to JSON |
| `broadcast.saved_title` | GOR Browser | GOR Browser |
| `broadcast.saved_msg` | Сохранено. | Saved. |

### A.25. Раздел `account_btn` (1)

| Ключ | RU | EN |
|---|---|---|
| `account_btn.tooltip` | Аккаунт: {name} | Account: {name} |

### A.26. Раздел `style_studio` (28)

| Ключ | RU | EN |
|---|---|---|
| `style_studio.window_title` | Темы и оформление | Themes and Design |
| `style_studio.theme_standard` | Стандартная (GOR) | Standard (GOR) |
| `style_studio.theme_forest` | Лесная | Forest |
| `style_studio.theme_gorstyle` | GorStyle | GorStyle |
| `style_studio.theme_light` | Светлая | Light |
| `style_studio.theme_neon` | Неоновый розовый | Neon Pink |
| `style_studio.theme_retro` | Ретро-терминал | Retro Terminal |
| `style_studio.account_colors` | Аккаунт: {name} — тема и цвета запоминаются за ним | Account: {name} — theme and colors saved per account |
| `style_studio.colors_section` | Цвета (нажмите на цветной квадрат, изменения видны сразу) | Colors (click a colored box to see changes immediately) |
| `style_studio.window_bg` | Фон окон | Window Background |
| `style_studio.fields_buttons` | Поля и кнопки | Fields and Buttons |
| `style_studio.panels` | Панели | Panels |
| `style_studio.field_hover` | Наведение на поля | Field Hover |
| `style_studio.frames` | Рамки | Borders |
| `style_studio.main_text` | Основной текст | Main Text |
| `style_studio.dim_text` | Приглушённый текст | Dim Text |
| `style_studio.accent` | Акцент | Accent Color |
| `style_studio.accent_hover` | Акцент (наведение) | Accent (Hover) |
| `style_studio.danger` | Опасное | Danger |
| `style_studio.warning` | Предупреждение | Warning |
| `style_studio.success` | Успех | Success |
| `style_studio.editors_bg` | Фон редакторов | Editors Background |
| `style_studio.btn_import` | Импорт... | Import... |
| `style_studio.btn_delete` | Удалить | Delete |
| `style_studio.btn_themes_folder` | 📁 Папка тем | 📁 Themes Folder |
| `style_studio.btn_reset` | Сбросить правки | Reset Changes |
| `style_studio.btn_save_theme` | 💾 Сохранить как тему.. | 💾 Save as Theme.. |
| `style_studio.btn_close` | Закрыть | Close |

### A.27. Раздел `browser_menu` (5)

| Ключ | RU | EN |
|---|---|---|
| `browser_menu.settings` | ⚙️ Настройки браузера | ⚙️ Browser Settings |
| `browser_menu.find_page` | 🔍 Найти на странице (Ctrl+F) | 🔍 Find on Page (Ctrl+F) |
| `browser_menu.dev_tools` | 🛠️ Инструменты разработчика (F12) | 🛠️ Developer Tools (F12) |
| `browser_menu.reopen_tab` | ↩️ Вернуть закрытую вкладку (Ctrl+Shift+T) | ↩️ Reopen Closed Tab (Ctrl+Shift+T) |
| `browser_menu.save_session` | 💾 Сохранить текущую сессию как группу | 💾 Save Current Session as Group |

---

<a id="appB"></a>
## Приложение B. Справочник сигнатур по модулям (автогенерация из AST)

Сигнатуры извлечены статическим разбором исходников. Показаны публичные функции и классы верхнего уровня и публичные методы классов (без имён, начинающихся с `_`, кроме `__init__`). Описание — первая строка docstring, если он есть.


### `GOR_Brauzer/GOR_Brauzer.py`

- **`get_resource_path(relative_path)`** — Получает путь к ресурсу, работает для обычного запуска и для .exe
- **class `CustomizationManager(QDialog)`**
    - `__init__(self, parent)`
    - `pick_accent_color(self)`
    - `pick_top_color(self)`
    - `pick_background(self)`
    - `apply_changes(self)`
- **class `GORWebPage(QWebEnginePage)`** — Специальный класс страницы для обработки новых окон GOR-Browser
    - `__init__(self, profile, parent=None)`
    - `createWindow(self, _type)` — Метод вызывается, когда браузер хочет открыть новую вкладку (например, через Target='_blank'). Мы вызываем наш метод создания вкладки, но возвращаем именно ОБЪЕ
- **class `SettingsDialog(QDialog)`**
    - `__init__(self, parent)`
    - `save_settings(self)`
- **class `ExtensionManager(QDialog)`**
    - `__init__(self, parent)`
    - `refresh_list(self)`
    - `show_ext_menu(self, pos)`
    - `add_extension(self)`
    - `delete_ext(self, name)`
- **class `DownloadItem(QWidget)`**
    - `__init__(self, download_item, parent=None)`
    - `update_progress(self)`
    - `open_folder(self)`
    - `handle_state(self, state)`
- **class `DownloadManager(QDialog)`**
    - `__init__(self, parent)`
    - `add_download(self, download_item)`
    - `clear_finished(self)`
- **class `GORBrowser(QWidget)`**
    - `__init__(self, parent=None)`
    - `load_data(self, f)` — Метод безопасной загрузки данных GOR
    - `on_download_requested(self, download)` — Обработка загрузок файлов
    - `save_data(self, f, d)` — Сохранение данных в JSON
    - `reload_start_pages(self)` — Перезагрузка всех открытых стартовых страниц
    - `apply_extensions(self)` — Заглушка системы расширений (функционал вырезан)
    - `update_styles(self)` — Метод для применения стилей интерфейса
    - `init_ui(self)` — Инициализация интерфейса: Сайдбар слева, Контент справа
    - `show_more_menu(self)` — Меню настроек и инструментов (вырезана кастомизация)
    - `toggle_devtools(self)` — Запуск панели разработчика
    - `add_new_tab(self, qurl=None, label='Новая вкладка', incognito=False)` — Создание новой вкладки в движке
    - `update_tab_icon(self, browser, icon)` — Устанавливает favicon сайта на вкладке (реальный источник иконок в GOR)
    - `update_progress(self, p)` — Обновление индикатора загрузки
    - `on_url_changed(self, qurl, browser)` — Событие при смене адреса
    - `add_to_history(self, title, url)` — Добавление записи в историю GOR
    - `update_tab_title(self, browser)` — Обновление текста на вкладке
    - `navigate_to_url(self)` — Переход по введенному адресу или поиск
    - `refresh_sidebar_bookmarks(self)` — Обновление списка закладок в сайдбаре
    - `refresh_sidebar_history(self)` — Обновление списка истории в сайдбаре
    - `show_bookmark_menu(self, pos)` — Контекстное меню закладок
    - `show_history_menu(self, pos)` — Контекстное меню истории
    - `delete_item(self, item, mode)` — Удаление элементов из БД
    - `on_sidebar_item_clicked(self, item)` — Переход по ссылке из сайдбара
    - `add_bookmark_dialog(self)` — Диалог добавления новой закладки
    - `setup_shortcuts(self)` — Настройка горячих клавиш GOR
    - `close_tab(self, i)` — Закрытие активной вкладки
    - `create_start_page(self)` — Генерация быстрой стартовой страницы (БЕЗ AI И КАСТОМИЗАЦИИ)

### `GOR_Brauzer/GORbrauzer_desktop.py`

- **`get_resource_path(relative_path)`** — Получает путь к ресурсу, работает для обычного запуска и для .exe
- **`get_resource_path(relative_path)`**
- **class `CustomizationManager(QDialog)`**
    - `__init__(self, parent)`
    - `pick_accent_color(self)`
    - `pick_top_color(self)`
    - `pick_background(self)`
    - `apply_changes(self)`
- **class `GORWebPage(QWebEnginePage)`** — Специальный класс страницы для обработки новых окон GOR-Browser
    - `__init__(self, profile, parent=None)`
    - `createWindow(self, _type)` — Метод вызывается, когда браузер хочет открыть новую вкладку (например, через Target='_blank'). Мы вызываем наш метод создания вкладки, но возвращаем именно ОБЪЕ
- **class `SettingsDialog(QDialog)`**
    - `__init__(self, parent)`
    - `save_settings(self)`
- **class `ExtensionManager(QDialog)`**
    - `__init__(self, parent)`
    - `refresh_list(self)`
    - `show_ext_menu(self, pos)`
    - `add_extension(self)`
    - `delete_ext(self, name)`
- **class `DownloadItem(QWidget)`**
    - `__init__(self, download_item, parent=None)`
    - `update_progress(self)`
    - `open_folder(self)`
    - `handle_state(self, state)`
- **class `DownloadManager(QDialog)`**
    - `__init__(self, parent)`
    - `add_download(self, download_item)`
    - `clear_finished(self)`
- **class `GORBrowser(QMainWindow)`**
    - `__init__(self)`
    - `load_data(self, f)` — Метод безопасной загрузки данных GOR
    - `on_download_requested(self, download)` — Обработка загрузок файлов
    - `save_data(self, f, d)` — Сохранение данных в JSON
    - `reload_start_pages(self)` — Перезагрузка всех открытых стартовых страниц
    - `apply_extensions(self)` — Заглушка системы расширений (функционал вырезан)
    - `init_ui(self)` — Инициализация главного графического интерфейса
    - `update_styles(self)` — Применение визуального стиля GOR-Dark
    - `show_more_menu(self)` — Меню настроек и инструментов (вырезана кастомизация)
    - `toggle_devtools(self)` — Запуск панели разработчика
    - `add_new_tab(self, qurl=None, label='Новая вкладка', incognito=False)` — Создание новой вкладки в движке
    - `update_progress(self, p)` — Обновление индикатора загрузки
    - `on_url_changed(self, qurl, browser)` — Событие при смене адреса
    - `add_to_history(self, title, url)` — Добавление записи в историю GOR
    - `update_tab_title(self, browser)` — Обновление текста на вкладке
    - `navigate_to_url(self)` — Переход по введенному адресу или поиск
    - `refresh_sidebar_bookmarks(self)` — Обновление списка закладок в сайдбаре
    - `refresh_sidebar_history(self)` — Обновление списка истории в сайдбаре
    - `show_bookmark_menu(self, pos)` — Контекстное меню закладок
    - `show_history_menu(self, pos)` — Контекстное меню истории
    - `delete_item(self, item, mode)` — Удаление элементов из БД
    - `on_sidebar_item_clicked(self, item)` — Переход по ссылке из сайдбара
    - `add_bookmark_dialog(self)` — Диалог добавления новой закладки
    - `setup_shortcuts(self)` — Настройка горячих клавиш GOR
    - `close_tab(self, i)` — Закрытие активной вкладки
    - `create_start_page(self)` — Генерация быстрой стартовой страницы (БЕЗ AI И КАСТОМИЗАЦИИ)

### `GOR_Brauzer/browser_adblock.py`

- **`load_extra_blocklist(base_dir)`** — Подгружает пользовательский список доменов (по одному на строку, "#" - комментарий) из adblock_domains.txt рядом с браузером, если файл
- **`load_dynamic_blocklist_cache(base_dir)`** — Подгружает УЖЕ СКАЧАННЫЙ ранее динамический список (см. GorAdBlockUpdater) из локального кэша - чтобы блокировка работала сразу
- **class `GorAdBlockUpdater(QObject)`** — Динамический AdBlock (пункт ТЗ): в фоне, по таймеру, скачивает актуальный список блокировки с GitHub (raw.githubusercontent.com) и
    - `__init__(self, base_dir, parent=None)`
    - `update_now(self, url=None)` — Запускает асинхронное скачивание списка. Безопасно вызывать, даже если предыдущий запрос ещё не завершился - новый просто
- **class `GorAdBlockInterceptor(QWebEngineUrlRequestInterceptor)`** — Сетевой уровень AdBlock'а. Ставится ОДИН РАЗ на профиль (profile.setUrlRequestInterceptor(...)) - до создания вкладок, как того
    - `__init__(self, parent=None)`
    - `set_enabled(self, enabled)`
    - `is_enabled(self)`
    - `interceptRequest(self, info)`
- **`install_cosmetic_filter(profile, enabled=True)`** — Регистрирует (или снимает) косметический JS-фильтр на уровне профиля. Скрипт живёт под фиксированным именем "gor-adblock-cosmetic", поэтому

### `GOR_Brauzer/browser_broadcast.py`

- **`is_safe_web_url(url)`**
- **`sanitize_payload(data)`** — Приводит входящий пакет к безопасному виду. None - пакет надо отбросить.
- **class `GorBroadcastService(QObject)`** — Обёртка над парой UDP-сокетов (приём + отправка). Один экземпляр на GORBrowser, живёт всё время работы браузера.
    - `__init__(self, port=51888, parent=None)`
    - `start_listening(self)` — Поднимает приёмный сокет. Безопасно вызывать повторно (например, при смене порта в настройках) - предыдущий сокет закрывается.
    - `stop_listening(self)`
    - `set_port(self, port)`
    - `send_tab(self, url, title='')`
    - `send_group(self, group)`
    - `send_clipboard(self, text)` — Общий буфер обмена по LAN (пункт ТЗ) - рассылает текст всем GOR Browser в сети; см. GORBrowser._on_local_clipboard_changed /
    - `send_bookmarks(self, bookmarks)` — Синхронизация закладок по LAN (пункт ТЗ) - рассылает ПОЛНЫЙ текущий список закладок; получатели добавляют себе те, которых у
- **class `BroadcastToast(QWidget)`** — Компактное всплывающее уведомление о принятой вкладке/группе - "Быстрый приём" из release notes: кнопки «Открыть все» и «Сохранить в
    - `__init__(self, parent_browser, payload)`
    - `open_all(self)`
    - `save_json(self)`
- **`Qt_WindowFlags(parent_browser)`** — Небольшой хелпер, чтобы не тянуть Qt.WindowType в импорты модуля напрямую при статическом анализе - тост открывается как обычное дочернее

### `GOR_Brauzer/browser_constants.py`

- **`get_resource_path(relative_path)`** — Путь к ресурсу внутри папки браузера, работает и при обычном запуске, и после сборки PyInstaller (--onefile, sys._MEIPASS).
- **`get_startpage_engines(settings)`** — Возвращает полный список поисковиков стартовой страницы: 4 встроенных + пользовательские, добавленные через CustomizationManager. Единая точка

### `GOR_Brauzer/browser_dialogs.py`

- **class `GeneralTab(QWidget)`** — Поиск по умолчанию + виджеты стартовой страницы (бывший SettingsDialog).
    - `__init__(self, parent_browser)`
    - `apply(self)`
- **class `AppearanceTab(QWidget)`** — Внешний вид: цвета/шрифт/прозрачность + всё, что раньше жило на отдельной вкладке "Стартовая страница" (бренд/фон/блюр/интерактивность) -
    - `__init__(self, parent_browser)`
    - `pick_accent_color(self)`
    - `pick_top_color(self)`
    - `pick_background(self)`
    - `clear_background(self)`
    - `reset_appearance(self)`
    - `apply(self)`
- **class `BackupTab(QWidget)`** — Экспорт/импорт резервной копии стартовой страницы.
    - `__init__(self, parent_browser)`
    - `apply(self)`
- **class `ExtensionsTab(QWidget)`** — Менеджер простых JS-расширений (бывший ExtensionManager).
    - `__init__(self, parent_browser)`
    - `refresh_list(self)`
    - `show_ext_menu(self, pos)`
    - `add_extension(self)`
    - `delete_ext(self, name)`
    - `apply(self)`
- **class `NetworkSecurityTab(QWidget)`** — AdBlock / VOT-переводчик / LAN Broadcast - три новые фичи v1.2. Переключатели дёргают install_*()/service.set_port() сразу в apply(),
    - `__init__(self, parent_browser)`
    - `apply(self)`
- **class `BrowserSettingsWindow(QDialog)`** — Единое красивое окно настроек GOR Browser: боковое меню разделов слева (QListWidget, как в VS Code/Telegram - надёжная и всегда
    - `__init__(self, parent_browser)`
    - `apply_all(self)`

### `GOR_Brauzer/browser_downloads.py`

- **class `DownloadItem(QWidget)`**
    - `__init__(self, download_item, parent=None)`
    - `update_progress(self)`
    - `open_folder(self)` — Открывает папку, где лежит файл (кроссплатформенно).
    - `handle_state(self, state)`
- **class `DownloadManager(QDialog)`**
    - `__init__(self, parent)`
    - `add_download(self, download_item)`
    - `clear_finished(self)` — Удаляем из списка только те элементы, где загрузка не идёт.

### `GOR_Brauzer/browser_groups.py`

- **class `GroupedTabBar(QTabBar)`** — QTabBar главной ленты вкладок браузера с визуальной группировкой в духе Firefox/Chrome: у вкладок одной группы под текстом рисуется цветная
    - `__init__(self, parent_browser)`
    - `tabSizeHint(self, index)`
    - `paintEvent(self, event)`
    - `mousePressEvent(self, event)`
    - `mouseMoveEvent(self, event)`
    - `mouseReleaseEvent(self, event)`
- **`group_emoji(group)`** — Эмодзи группы с фолбэком для записей, сохранённых до появления этого поля (старые JSON без ключа "emoji").
- **`group_display_name(group)`** — "Эмодзи + название" - единая точка форматирования подписи группы, используется и в панели групп, и в заголовках вкладок/групп в ленте.
- **`new_group_record(name, color, urls, emoji=None)`** — Собирает новую запись группы в едином формате (см. докстринг модуля).
- **class `GroupEditDialog(QDialog)`** — Единое окно редактирования группы: название, цвет, список URL (с возможностью удалить отдельную вкладку из группы или добавить
    - `__init__(self, parent_browser, group)`
    - `pick_color(self)`
    - `add_current_tab(self)`
    - `remove_selected_url(self)`
    - `save_and_close(self)`
- **class `GroupsPanel(QWidget)`** — Панель "Группы" для сайдбара GORBrowser (третья вкладка в sidebar_stack, рядом с "Закладки"/"История"). Использует
    - `__init__(self, parent_browser)`
    - `refresh(self)`
    - `on_item_double_clicked(self, item)`
    - `save_current_session(self)` — Собирает URL всех открытых (не инкогнито) вкладок в новую группу - "Broadcast сохранённой группы" из release notes работает
    - `show_group_menu(self, pos)`
    - `edit_group(self, group_id)` — Открывает единое окно редактирования (название + цвет + список вкладок) - см. GroupEditDialog.
    - `delete_group(self, group_id)`

### `GOR_Brauzer/browser_page.py`

- **class `GORWebPage(QWebEnginePage)`** — Специальный класс страницы для обработки новых окон GOR-Browser.
    - `__init__(self, profile, parent=None)`
    - `createWindow(self, _type)` — Вызывается, когда страница хочет открыть новую вкладку (например, через target="_blank"). Вместо стандартного окна Qt мы создаём

### `GOR_Brauzer/browser_passwords.py`

- **`generate_strong_password(length=16)`** — Генератор паролей для кнопки "Сгенерировать" в диалоге записи - минимум по одному символу каждого класса, остальное - случайный набор,
- **class `PasswordVault()`** — Хранилище паролей - один экземпляр на GORBrowser. Не хранит открытый мастер-пароль и открытые записи на диске ни при каких обстоятельствах.
    - `__init__(self, path)`
    - `exists(self)`
    - `is_unlocked(self)`
    - `lock(self)` — Забывает ключ и все расшифрованные записи - вызывается при закрытии браузера и по явному запросу пользователя.
    - `create(self, master_password)` — Создаёт новое пустое хранилище с новым мастер-паролем (перезаписывает существующий файл, если он был - вызывающий код должен явно
    - `unlock(self, master_password)` — Пытается разблокировать существующее хранилище. Возвращает False при неверном пароле или повреждённом файле - НЕ бросает исключение
    - `change_master_password(self, new_master_password)` — Перешифровывает уже расшифрованные (в памяти) записи новым мастер-паролем - вызывается только когда vault уже разблокирован.
    - `list_entries(self)`
    - `add_entry(self, site, username, password, note='')`
    - `update_entry(self, entry_id, **fields)`
    - `delete_entry(self, entry_id)`
- **class `_UnlockDialog(QDialog)`** — Диалог создания мастер-пароля (первый запуск) или разблокировки существующего хранилища.
    - `__init__(self, parent, vault)`
- **class `_EntryDialog(QDialog)`** — Диалог добавления/редактирования одной записи.
    - `__init__(self, parent, entry=None)`
- **class `PasswordManagerDialog(QDialog)`** — Главное окно менеджера паролей: список записей + добавить/изменить/ удалить/скопировать. Открывается ТОЛЬКО после успешной разблокировки
    - `__init__(self, parent, vault)`
- **`open_password_manager(parent_browser, vault)`** — Единая точка входа для меню/хоткея: если хранилище заблокировано - сперва просит создать/ввести мастер-пароль, и только потом открывает

### `GOR_Brauzer/browser_startpage.py`

- **`write_start_page(settings)`** — Генерирует start_page.html по переданным настройкам браузера (см. browser_constants.DEFAULT_SETTINGS за списком используемых ключей).

### `GOR_Brauzer/browser_translate.py`

- **`install_vot_translator(profile, base_dir, enabled=True)`** — Регистрирует (или снимает) VOT-скрипт на уровне профиля. Если рядом с браузером лежит настоящий vot.user.js - внедряется он (полноценный

### `GOR_Brauzer/browser_widget.py`

- **class `WikiSearchOverlay(QDialog)`** — Оверлей «Быстрый поиск по вики» (пункт ТЗ): всплывает по хоткею (см. GORBrowser._setup_shortcuts - Ctrl+Shift+K) поверх окна браузера,
    - `__init__(self, parent_browser)`
    - `showEvent(self, event)`
    - `keyPressEvent(self, event)`
- **class `GORBrowser(QWidget)`**
    - `__init__(self, parent=None)`
    - `load_data(self, key)` — Загружает под-раздел браузера (bookmarks/history/settings/extensions) из общего блока "browser" в games_data.json. Ничего не удаляет и не
    - `save_data(self, key, value)` — Сохраняет под-раздел браузера обратно в общий games_data.json лаунчера, в блок "browser", не затрагивая данные игр/групп/истории
    - `save_tab_groups(self)` — Персистит self.tab_groups в games_data.json (см. save_data).
    - `get_open_tab_urls(self)` — URL всех открытых (не инкогнито, кроме стартовой страницы) вкладок - используется и для сохранения новой группы, и для
    - `find_tab_group(self, group_id)` — Ищет сохранённую группу по id - общая точка входа и для GroupsPanel, и для GroupedTabBar (подсветка в ленте вкладок).
    - `tag_tab_with_group(self, browser_widget, group_id)` — Помечает открытую вкладку как принадлежащую группе - именно это свойство читает GroupedTabBar, чтобы нарисовать цветную полоску под
    - `untag_tab_from_group(self, index)` — Убирает вкладку из визуальной группы (полоска пропадёт), НЕ трогая сам сохранённый список URL группы - это разные вещи: одно
    - `open_group_by_id(self, group_id)` — Открывает все вкладки сохранённой группы одним кликом ("Мгновенный запуск сохраненных групп" из release notes) и сразу
    - `create_group_from_tab(self, index)` — Аналог "Add Tab to New Group" из Firefox/Chrome - создаёт НОВУЮ сохранённую группу прямо из одной открытой вкладки (сразу же
    - `add_tab_to_group(self, index, group_id)` — Добавляет уже открытую вкладку в существующую сохранённую группу - и подсвечивает её в ленте, и дописывает URL в сохранённый
    - `toggle_group_collapse(self, group_id)` — Сворачивает/разворачивает группу в ленте вкладок - как клик по заголовку группы в Firefox. Технически: все вкладки группы, кроме
    - `refresh_groups_panel(self)` — Безопасный вызов GroupsPanel.refresh() - панель создаётся в init_ui() уже ПОСЛЕ первой вкладки, поэтому в моменты между началом
    - `mark_session_closed_cleanly(self)` — Вызывается лаунчером из GORLauncher.closeEvent ПРИ ШТАТНОМ закрытии приложения: немедленно (без debounce) пишет "active": False,
    - `broadcast_group_by_id(self, group_id)` — Отправляет сохранённую группу в локальную сеть (LAN Broadcast).
    - `send_current_tab_to_network(self)` — Отправка активной вкладки в сеть по UDP - "Отправка вкладки в сеть" из release notes.
    - `statusBar_message(self, text, timeout_ms=3000)` — Лёгкое всплывающее сообщение в заголовке окна на пару секунд - в этом виджете нет полноценного statusBar (QWidget, не QMainWindow),
    - `on_broadcast_received(self, payload)` — Пришёл UDP-пакет от другого GOR Browser в сети. Буфер обмена и синхронизация закладок обрабатываются молча (без тоста - см.
    - `on_download_requested(self, download)` — Обработка загрузок файлов.
    - `create_start_page(self)` — Стартовая страница теперь - готовый файл GOR_Brauzer/start_page.html (кастомный дашборд с ярлыками, поиском и своими настройками на
    - `reload_start_pages(self)` — Перезагрузка всех открытых стартовых страниц.
    - `push_now_playing(self, game_data)` — "Сейчас в игре" (пункт ТЗ) - живое обновление виджета на ВСЕХ открытых стартовых страницах прямо сейчас, без ожидания перезагрузки
    - `run_js_on_start_pages(self, js_code)` — Выполняет произвольный JS на всех открытых вкладках стартовой страницы. Используется и для точечного push_native_settings_to_pages,
    - `push_native_settings_to_pages(self)` — Отправляет текущие self.settings во все открытые стартовые страницы без перезагрузки вкладки (в отличие от старого
    - `sync_start_page_settings(self, browser)` — Как push_native_settings_to_pages, но только для одной, только что загрузившейся вкладки - чтобы свежая стартовая страница сразу
    - `get_first_start_page_browser(self)` — Первая открытая вкладка стартовой страницы (нужна как источник для экспорта - JS с данными localStorage должен выполняться внутри
    - `export_backup_to_file(self, dialog_parent)` — Полная резервная копия (пункт 3.3 ТЗ): настройки, история, закладки, группы вкладок, расширения - ВСЁ одним JSON-файлом.
    - `import_backup_from_file(self, dialog_parent)` — Импорт полной резервной копии (обратная операция к export_backup_to_file) - валидирует формат, перезаписывает
    - `clear_cookies(self, dialog_parent=None)` — Приватность (пункт 3.4 ТЗ) - немедленная очистка кук основного профиля, без ожидания перезапуска браузера. Инкогнито-профиль не
    - `clear_http_cache(self, dialog_parent=None)` — Приватность (пункт 3.4 ТЗ) - очистка дискового HTTP-кеша.
    - `apply_extensions(self)` — Внедряет пользовательские JS-расширения на каждую загружаемую страницу через QWebEngineScript (пункт 5 ТЗ: базовый менеджер
    - `update_styles(self)` — Применение стилей интерфейса.
    - `init_ui(self)` — Сайдбар слева, контент справа.
    - `show_more_menu(self)` — Главное меню (⋮) - НАМЕРЕННО короткое (5 пунктов): всё остальное, что раньше было здесь (LAN, AdBlock, Tab Suspender, пароли, вики-
    - `toggle_devtools(self)` — Запуск панели разработчика.
    - `add_new_tab(self, qurl=None, label='Новая вкладка', incognito=False)` — Создание новой вкладки в движке.
    - `update_tab_icon(self, browser, icon)` — Устанавливает иконку вкладки - единая точка правды и для настоящих favicon'ов сайтов, и для значков спецтипов вкладок
    - `update_progress(self, p)` — Обновление индикатора загрузки.
    - `on_url_changed(self, qurl, browser)` — Событие при смене адреса.
    - `update_security_indicator(self, url_str)` — Обновляет иконку слева от адресной строки в зависимости от протокола: 🔒 для HTTPS, ⚠ (жёлтым) для незащищённого HTTP, пусто
    - `add_to_history(self, title, url, icon=None)` — Добавление записи в историю GOR. icon - favicon текущей вкладки (пункт 4 ТЗ) - сохраняется вместе с записью как base64 PNG.
    - `update_tab_title(self, browser)` — Обновление текста на вкладке.
    - `navigate_to_url(self)` — Переход по введенному адресу или поиск.
    - `setup_shortcuts(self)` — Горячие клавиши GOR.
    - `on_escape_pressed(self)` — Esc: сначала закрывает поиск по странице (если открыт), иначе выходит из полноэкранного видео (если оно активно).
    - `open_find_bar(self)`
    - `close_find_bar(self)`
    - `do_find(self, text, backward=False, advance=False)` — Запускает поиск текста на текущей вкладке. advance=True означает, что это переход к след./пред. совпадению (Enter / кнопки ˄˅), а не
    - `zoom_in(self)`
    - `zoom_out(self)`
    - `zoom_reset(self)`
    - `focus_url_bar(self)`
    - `on_reload_stop_clicked(self)`
    - `on_load_started(self, browser)`
    - `on_load_finished_state(self, browser, ok)`
    - `on_tab_changed(self, index)` — При переключении вкладки - обновляем адресную строку и состояние кнопки reload/stop под свежевыбранную вкладку.
    - `focus_tab_by_position(self, position)` — Ctrl+1..Ctrl+9: переключает на вкладку по позиции в ленте (0-based), включая закреплённые - они всегда идут первыми.
    - `open_wiki_search_overlay(self)` — Ctrl+Shift+K - показывает WikiSearchOverlay поверх окна браузера (см. класс выше). Держим ссылку в self, иначе PyQt соберёт диалог
    - `handle_fullscreen_request(self, request)` — QWebEnginePage.fullScreenRequested: сайт (например, плеер YouTube) просит развернуть <video> на весь экран. Разворачиваем
    - `close_tab(self, i)` — Закрытие активной вкладки (с сохранением в стек для Ctrl+Shift+T).
    - `restore_closed_tab(self)` — Ctrl+Shift+T: переоткрывает последнюю закрытую ПУБЛИЧНУЮ вкладку. Стек closed_tabs по построению (см. _push_closed_tab) никогда не
    - `show_tab_context_menu(self, pos)`
    - `duplicate_tab(self, index)`
    - `toggle_pin_tab(self, index)`
    - `close_other_tabs(self, keep_index)`
    - `close_tabs_to_right(self, index)`
    - `refresh_sidebar_bookmarks(self)`
    - `refresh_sidebar_history(self)`
    - `show_bookmark_menu(self, pos)`
    - `edit_bookmark(self, item)` — Редактирование имени и адреса уже существующей закладки (а не только удаление, как раньше).
    - `show_history_menu(self, pos)`
    - `delete_item(self, item, mode)`
    - `on_sidebar_item_clicked(self, item)`
    - `add_bookmark_dialog(self)`

### `addons_sys/ControlCenter.py`

- **`get_project_root()`** — Находит корень проекта (там, где лежат games_data.json и addons/), а НЕ папку, где физически лежит сам ControlCenter.py.
- **class `AddonDelegate(QStyledItemDelegate)`** — Рисует одну строку списка аддонов: иконка + имя + версия слева, чёткий квадратный чекбокс справа. on_toggle(addon_path, enabled)
    - `__init__(self, on_toggle, parent=None)`
    - `paint(self, painter, option, index)`
    - `editorEvent(self, event, model, option, index)`
    - `sizeHint(self, option, index)`
- **class `MonitoringTab(QWidget)`**
    - `__init__(self, parent=None)`
    - `show_empty(self)`
    - `update_for_addon(self, addon_info)` — addon_info: dict с ключами name, path, enabled, config
- **class `ControlCenter(QDialog)`**
    - `__init__(self)`
    - `scan_addons(self)`
    - `on_addon_selected(self, item)`
    - `on_load_finished(self, ok)`
    - `on_toggle_addon(self, addon_path, enabled)`

### `addons_sys/addon_logger.py`

- **`log_activity(caller_file, msg_type, message)`** — То, что вызывает САМ АДДОН из своего core/*.py:
- **`log_activity_for_addon(addon_root, msg_type, message)`** — То же самое, но когда путь к папке аддона уже известен напрямую (используется bridge_loader.py для автоматических системных записей,

### `addons_sys/addon_watchdog.py`

- **`install(addons_dir)`**

### `bridge_loader.py`

- **`safe_import(module_name)`**
- **`install_requirements(addon_path)`**
- **`change_language(lang_code)`** — Устанавливает новый язык и перезапускает интерфейс.
- **`restart_launcher(confirm=True, account=None)`** — Надежный перезапуск GorLauncher с сохранением всех аддонов, обновлений и UI.
- **`run_control_center(launcher=None)`**
- **`load_addons(launcher)`**
- **`add_restart_button(launcher)`** — Добавляет кнопку перезапуска.
- **`add_account_button(launcher, account_name)`** — Кнопка-обложка в шапке лаунчера. Открывает окно переключения аккаунта (большая обложка текущего + список остальных).
- **`add_tray_button(launcher)`** — Переставляет уже созданную кнопку 'В трей' (GORLauncher.tray_btn) вплотную к остальным маленьким квадратным кнопкам в шапке (Restart,
- **`update_widget_style_property(widget, prop_name, prop_value)`** — Вспомогательная функция для обновления динамических свойств QSS.
- **`check_updates_in_background(launcher)`**
- **`show_update_available_button(launcher, remote_version)`**

### `core/GorLauncher.py`

- **class `DetachedTabWindow(QMainWindow)`** — Окно, в которое временно переезжает вкладка лаунчера в режиме 'Отдельное окно'. При закрытии этого окна содержимое автоматически
    - `__init__(self, owner, content_widget, title, icon, original_index)`
    - `closeEvent(self, event)`
- **class `GORLauncher(QMainWindow)`**
    - `__init__(self)`
    - `load_data(self)`
    - `migrate_ids(self)`
    - `save_data(self)`
    - `init_ui(self)`
    - `set_tab_expand_window(self, index, checked)` — Развернуть указанную вкладку на всё окно лаунчера (прячет верхнюю панель поиска/бургер-меню, оставляя саму панель вкладок - чтобы можно
    - `set_tab_fullscreen(self, index, checked)` — Развернуть указанную вкладку на весь экран (полноэкранный режим окна + скрытая верхняя панель).
    - `detach_tab(self, index)` — Открепить вкладку в отдельное окно. После закрытия этого окна вкладка автоматически возвращается обратно в главное окно на своё
    - `minimize_to_tray(self)` — Прячет главное окно лаунчера в системный трей (вызывается при запуске игры).
    - `restore_from_tray(self)` — Возвращает главное окно лаунчера обратно из трея (вызывается, когда все запущенные из лаунчера игры закрыты, или по клику на
    - `track_game_monitor(self, monitor)` — Регистрирует ProcessMonitor запущенной игры. Обработчик конца сессии живёт здесь, в лаунчере, а не в GameCard: карточки
    - `on_session_finished(self, duration, game_data)`
    - `on_game_session_changed(self)` — Вызывается из GameCard при запуске/остановке/завершении игры. Сворачивает лаунчер в трей, пока запущена хотя бы одна игра, и
    - `on_game_started(self, game_data)` — Вызывается GameCard РОВНО В МОМЕНТ успешного запуска игры (до on_game_session_changed) - пункты ТЗ "Сейчас в игре" и "Авто-группа
    - `change_language(self, code, name)`
    - `sort_games_list(self, games)` — Возвращает отсортированную КОПИЮ списка игр согласно self.sort_combo. Сами словари игр не копируются - это те же объекты, что и в self.games_info,
    - `sort_groups(self, groups_dict)` — Возвращает список (имя_группы, игры) из словаря групп, отсортированный тем же режимом, что выбран в self.sort_combo.
    - `update_stats(self)`
    - `refresh_list(self)`
    - `add_game_dialog(self)`
    - `edit_game(self, game_data, group_name)`
    - `on_editor_closed(self)`
    - `add_group(self)`
    - `edit_group(self, group_name)`
    - `delete_group_confirm(self, group_name)`
    - `delete_game_confirm(self, game_data, group_name)`
    - `move_game_to_group(self, game_identifier, target_group)`
    - `open_fortune_wheel(self)`
    - `open_big_picture(self)` — Режим Big Picture: полноэкранный интерфейс для ТВ с управлением геймпадом.
    - `on_remote_command(self, command, sock)`
    - `bring_to_front(self)`
    - `attach_big_picture_waiter(self, sock)` — Повторный запуск с --bigpicture (например, из Sunshine) не создаёт второй лаунчер, а открывает Big Picture здесь и держит соединение, пока режим не закроют.
    - `launch_game_from_wheel(self, game_data)`
    - `run_sunshine(self, tab=None)`
    - `run_moonlight(self)`
    - `open_exporter(self)`
    - `finalize_history_session(self, duration, game_data)`
    - `delete_history_entry(self, index)`
    - `clear_history_confirm(self)`
    - `closeEvent(self, event)`

### `core/game_card.py`

- **class `GameCard(QFrame)`**
    - `__init__(self, game_data, parent_launcher, group_name=None)`
    - `init_ui(self)`
    - `open_game_folder(self)`
    - `show_context_menu(self, pos)`
    - `pick_guide_group(self)` — Привязывает эту игру к сохранённой группе вкладок браузера - при следующем запуске игры лаунчер попросит браузер автоматически
    - `copy_path_to_clipboard(self)`
    - `toggle_favorite(self)`
    - `keyPressEvent(self, e)`
    - `handle_main_button(self)`
    - `update_live_timer(self)`
    - `toggle_timer_pause(self)`
    - `on_game_finished(self, duration, game_data)`
    - `mouseDoubleClickEvent(self, e)`
    - `mousePressEvent(self, e)`
    - `mouseMoveEvent(self, e)`

### `core/group_widget.py`

- **class `GroupWidget(QFrame)`**
    - `__init__(self, name, games, parent_launcher, is_favorite=False)`
    - `init_ui(self)`
    - `dragEnterEvent(self, e)`
    - `dragMoveEvent(self, e)`
    - `dropEvent(self, e)`
    - `refresh_cards(self, filter_text='')`
    - `toggle(self)`
    - `show_group_menu(self, pos)`

### `core/history_card.py`

- **class `HistoryCard(QFrame)`**
    - `__init__(self, entry, index, parent_launcher)`
    - `init_ui(self)`
    - `show_context_menu(self, pos)`
    - `keyPressEvent(self, e)`

### `core/launcher_utils.py`

- **`find_favicon_path()`** — Ищет favicon.ico рядом со скриптом, на уровень выше и в рабочей папке. Если нигде не найден - возвращает путь рядом со скриптом (по умолчанию)
- **`load_pixmap_cached(path)`** — Кэширует QPixmap по пути к файлу, чтобы не читать иконку с диска заново при каждом refresh_list.
- **`universal_launch(path)`** — Открывает файл/папку средствами ОС (аналог двойного клика в проводнике).
- **`run_editor_process(script_name, args=None, py_subdir=None)`** — Запускает редактор (game_editor/group_editor/...) как отдельный процесс - .exe, если он собран, иначе .py тем же интерпретатором.

### `core/process_monitor.py`

- **class `ProcessMonitor(QThread)`** — Ждёт завершения запущенной игры и сообщает итоговую длительность сессии. После того как основной процесс игры завершился, дополнительно
    - `__init__(self, process, start_time, game_data)`
    - `run(self)`
- **class `EditorMonitor(QThread)`** — Ждёт закрытия окна редактора (game_editor/group_editor/...), запущенного отдельным процессом, и сообщает об этом сигналом -
    - `__init__(self, process)`
    - `run(self)`

### `editors/game_editor.py`

- **class `_PickerView(QWebEngineView)`** — WebView в режиме выбора обложки.
    - `__init__(self, on_image_picked, parent=None)`
    - `contextMenuEvent(self, event)`
- **class `ImagePickerDialog(QDialog)`** — Встроенный браузер в 'режиме выбора обложки': пользователь ищет картинку как обычно (поиск, любой сайт), а клик по любому изображению
    - `__init__(self, parent=None, initial_query='')`
- **class `GameEditor(QDialog)`**
    - `__init__(self, parent=None, game_data=None, groups=None, current_group=None)`
    - `load_json(self)`
    - `save_json(self, data)`
    - `init_ui(self)`
    - `name_exists(self, name, exclude_id=None)` — Проверяет, занято ли имя другой игрой (кроме редактируемой).
    - `save_and_accept(self)`
    - `select_path(self)`
    - `select_root_path(self)`
    - `select_icon(self)`
    - `closeEvent(self, event)`
    - `select_icon_from_browser(self)` — Просит ГЛАВНЫЙ процесс лаунчера (если он запущен) переключиться на вкладку "Браузер" и открыть там служебную вкладку выбора
    - `update_preview(self)`
    - `get_data(self)`

### `editors/group_editor.py`

- **class `GroupEditor(QDialog)`**
    - `__init__(self, parent=None, old_name=None)`
    - `save_group(self)`

### `extras/big_picture.py`

- **`contrast_ratio(a, b)`**
- **`ensure_contrast(fg, bg, minimum=4.5)`** — Подтягивает цвет текста к белому/чёрному ровно настолько, чтобы он читался на ТВ. Приглушённые цвета тем (например, тёмно-синий на тёмно-синем) на расстоянии ди
- **`on_color(bg)`** — Читаемый цвет текста ПОВЕРХ заданного фона.
- **class `Theme()`** — Палитра Big Picture = палитра активной темы лаунчера.
    - `__init__(self)`
    - `load(self)`
- **`format_duration(seconds)`**
- **class `Tile(QWidget)`** — Карточка игры собрана из тех же виджетов и с теми же objectName, что GameCard в обычном режиме (GameCard / GameCardImage / GameCardName / GameCardTime / RunGame
    - `__init__(self, title, subtitle='', pixmap=None, unit=1.0, kind='game', value='', running=False, favorite=False, data=None, parent=None)`
    - `selected(self)`
    - `set_selected(self, selected)`
- **class `MirrorOverlay(QWidget)`** — Рисует те же слои оформления, что аддоны добавили в обычное окно лаунчера (api.design.particles / animated_gradient / wallpaper ...). Слои - общие объекты, поэт
    - `__init__(self, host, launcher)`
    - `layers(self)`
    - `refresh(self)`
    - `showEvent(self, event)`
    - `hideEvent(self, event)`
    - `resizeEvent(self, event)`
    - `paintEvent(self, _event)`
- **class `NavPage(QScrollArea)`** — Вертикальный список горизонтальных строк плиток с курсором (строка, столбец).
    - `__init__(self, unit, parent=None)`
    - `set_rows(self, rows, keep_position=True)`
    - `has_rows(self)`
    - `current(self)` — (ключ строки, индекс плитки, плитка) или None.
    - `move(self, dx, dy)`
    - `resizeEvent(self, event)`
- **class `OverlayMenu(QWidget)`**
    - `__init__(self, parent, unit)`
    - `paintEvent(self, _e)`
    - `open(self, title, items)` — items: [(текст, callback)]; callback вызывается после закрытия меню.
    - `close_menu(self)`
    - `handle(self, name)`
- **class `AppListWorker(QThread)`**
    - `__init__(self, manager, ip)`
    - `run(self)`
- **class `BigPictureWindow(QWidget)`**
    - `__init__(self, launcher, gamepad_reader=None, stream_manager=None)`
    - `refresh(self)`
    - `start(self)`
    - `shutdown(self)` — Останавливает таймеры и опрос геймпада; безопасно вызывать повторно.
    - `closeEvent(self, event)`
    - `resizeEvent(self, event)`
    - `keyPressEvent(self, event)`
    - `handle_input(self, name)`

### `extras/exporter_editor.py`

- **class `PackerWorker(QThread)`**
    - `__init__(self, selected_games, output_path, master_name, include_json)`
    - `run(self)`
- **class `PackerGUI(QWidget)`**
    - `__init__(self)`
    - `load_games(self)`
    - `init_ui(self)`
    - `toggle_all(self, state)`
    - `select_folder(self)`
    - `start_export(self)`
- **class `ProgressWindow(QWidget)`**
    - `__init__(self, selected_games, output_path, master_name, include_json)`
    - `update_ui(self, total_p, text, game_idx, game_p)`

### `extras/fortune_wheel.py`

- **class `FortuneWheelDialog(QDialog)`**
    - `__init__(self, parent=None, json_path='games_data.json', qss_path='style.qss', launch_callback=None)`
    - `apply_stylesheet(self)` — Ищет и применяет style.qss - единый файл стилей проекта.
    - `load_games(self)` — Собирает единый список игр из games_data.json.
    - `init_ui(self)`
    - `set_title_text(self, text, error=False)` — Меняет текст заголовка и переключает свойство error=true/false, которое обрабатывается в style.qss (QLabel#WheelTitleLabel[error="true"]).
    - `init_sounds(self)`
    - `start_spinning(self)`
    - `update_wheel_animation(self)`
    - `on_spin_finished(self)`
    - `launch_selected_game(self)`
- **class `WheelWidget(QWidget)`** — Вспомогательный виджет для отрисовки кастомного колеса фортуны
    - `__init__(self, parent=None)`
    - `clear_cache(self)` — Очищает кэш иконок при обновлении списка игр
    - `set_angle(self, angle)`
    - `paintEvent(self, event)`

### `launcher_start.py`

- **`main()`**

### `remote/moonlight_cantrol.py`

- **class `PCStreamManager()`** — Отвечает за:   - автоматический поиск исполняемого файла Moonlight в системе;
    - `__init__(self)`
    - `find_moonlight_executable(self)` — Ищет moonlight-qt в системе:   0) в папке "Moonlight", лежащей РЯДОМ с этим модулем (например,
    - `is_available(self)` — Проверка, найден ли исполняемый файл Moonlight.
    - `load_manual_path(self)` — Загружает вручную указанный путь к Moonlight из конфига, если он там есть.
    - `set_manual_path(self, path)` — Сохраняет путь к moonlight.exe, указанный пользователем вручную (например, через диалог выбора файла в интерфейсе), и делает его
    - `load_hosts(self)` — Загружает список сохранённых хостов из JSON-файла конфигурации.
    - `save_hosts(self)` — Сохраняет текущий список хостов в JSON-файл конфигурации.
    - `add_host(self, ip)` — Добавляет IP-адрес в список сохранённых хостов (без дублей).
    - `remove_host(self, ip)` — Удаляет IP-адрес из списка сохранённых хостов.
    - `pair_with_host(self, ip, pin, timeout=45)` — Выполняет сопряжение с удалённым ПК по IP-адресу и PIN-коду.
    - `list_apps(self, ip, timeout=25)` — Список приложений на хосте через "moonlight list <ip>".
    - `start_stream(self, ip, app_name, width=1920, height=1080, fps=60, bitrate=20000, windowed=False)` — Запускает стрим с удалённого ПК в фоновом режиме (не блокируя интерфейс).
- **class `PairWorker(QThread)`** — Выполняет сопряжение с хостом в отдельном потоке.
    - `__init__(self, manager, ip, pin)`
    - `run(self)`
- **class `PinDialog(QDialog)`** — Диалог сопряжения. Важно понимать реальный механизм пары Moonlight/Sunshine: PIN-код для сопряжения НЕ приходит откуда-то с хоста - его нужно один
    - `__init__(self, parent=None, ip='')`
    - `regenerate_pin(self)` — Генерирует новый случайный PIN, если пользователь хочет его сменить.
    - `try_accept(self)`
    - `get_pin(self)`
- **class `StreamModuleUI(QWidget)`** — Виджет для встраивания в GOR Launcher (например, отдельной вкладкой) либо для самостоятельного запуска. Позволяет пользователю указать
    - `__init__(self, parent=None)`
    - `refresh_availability_status(self)` — Обновляет строку статуса и видимость кнопки ручного выбора Moonlight.
    - `locate_moonlight_manually(self)` — Открывает диалог выбора файла, чтобы пользователь указал путь к Moonlight.exe вручную - полезно, если программа установлена
    - `init_ui(self)`
    - `on_saved_host_selected(self, text)` — Подставляет IP из списка сохранённых хостов в поле ввода.
    - `open_pair_dialog(self)` — Открывает диалог сопряжения и, при подтверждении, запускает pairing.
    - `on_pair_finished(self, success, message)`
    - `launch_stream(self)` — Запускает стрим с текущими параметрами интерфейса.

### `remote/sunshine_api.py`

- **class `SunshineAPIError(Exception)`** — kind: down - Sunshine не отвечает; unauthorized - логин не принят; http - прочая ошибка.
    - `__init__(self, kind, message, status=None)`
- **class `SunshineAPI()`**
    - `__init__(self, user='', password='', base_url=DEFAULT_URL, timeout=6)`
    - `configured(self)`
    - `check(self)` — 'down' | 'unauthorized' | 'ok'.
    - `clients(self)` — [{'name':..., 'uuid':...}] сопряжённых устройств.
    - `pair(self, pin, name='Android TV')` — Сопряжение по PIN, который показал клиент (Moonlight). Бросает SunshineAPIError при отказе.
    - `unpair(self, uuid)`
    - `apps(self)`
    - `ensure_app(self, entry)` — Добавляет или обновляет приложение по имени без перезапуска Sunshine. Возвращает 'added' | 'updated' | 'unchanged'.
    - `has_app(self, name=LAUNCHER_APP_NAME)`
- **`launcher_app_entry(project_root, python_exe=None)`** — Описание приложения Sunshine, запускающего Big Picture лаунчера. Берём pythonw из runtime/ проекта (как launcher_start.py), иначе - текущий интерпретатор.
- **`lan_addresses()`** — IPv4-адреса ПК в локальной сети (первым - адрес основного маршрута), без loopback и link-local.
- **`load_login(sunshine_dir)`**
- **`save_login(sunshine_dir, user, password)`** — Запоминает логин для API рядом с собственными файлами Sunshine (открытым текстом - как и любой клиент API; поэтому лаунчер предлагает это только по явному согла
- **`forget_login(sunshine_dir)`**
- **`upsert_app_in_file(apps_json_path, entry)`** — Запасной путь, когда API недоступно: правим apps.json напрямую (потом нужен перезапуск Sunshine). Остальные приложения не трогаем. Возвращает 'added' | 'updated

### `remote/sunshine_control.py`

- **`kill_sunshine()`** — Кроссплатформенное завершение процесса Sunshine.
- **`is_sunshine_running()`** — Проверяет, запущен ли процесс sunshine.exe / sunshine в системе.
- **class `_StatusWorker(QThread)`** — Проверка "запущен ли Sunshine" вне GUI-потока.
    - `run(self)`
- **class `SyncWorker(QThread)`**
    - `__init__(self, sunshine_dir, assets_dir, apps_json_path, games_data_path)`
    - `run(self)`
- **class `RestartWorker(QThread)`**
    - `__init__(self, sunshine_dir)`
    - `run(self)`
- **class `CredsWorker(QThread)`**
    - `__init__(self, sunshine_dir, user, pwd)`
    - `run(self)`
- **class `SunshineControlApp(QMainWindow)`**
    - `__init__(self)`
    - `init_ui(self)`
    - `append_log(self, message)`
    - `init_status_timer(self)`
    - `refresh_status(self)`
    - `closeEvent(self, event)`
    - `set_controls_enabled(self, enabled)`
    - `open_web_panel(self)`
    - `sync_games(self)`
    - `on_sync_finished(self, success, message)`
    - `stop_sunshine(self)`
    - `apply_creds(self)`
    - `on_creds_finished(self, success, message)`

### `remote/tv_setup.py`

- **class `ApiTask(QThread)`** — Выполняет функцию в фоне. done(ok, результат_или_исключение).
    - `__init__(self, fn, parent=None)`
    - `run(self)`
- **class `TVSetupWidget(QWidget)`**
    - `__init__(self, sunshine_dir, project_root, apps_json_path, log=None, creds_worker_cls=None, parent=None)`
    - `showEvent(self, event)`
    - `closeEvent(self, event)`
    - `refresh_all(self)`
    - `start_sunshine(self)`
    - `connect_clicked(self)`
    - `auto_clicked(self)`
    - `add_app_clicked(self)`
    - `pair_clicked(self)`
    - `unpair_clicked(self)`

### `shared/account_dialog.py`

- **`circular_avatar(name, size=64)`** — Круглая обложка аккаунта `name` нужного размера. Если своя обложка не задана - генерируется цветной кружок с первой буквой имени.
- **class `AccountDialog(QDialog)`**
    - `__init__(self, parent=None)`
- **class `AccountSwitcherDialog(QDialog)`** — `on_switch_confirmed(name)` вызывается, когда пользователь выбрал другой аккаунт и подтвердил перезапуск - им обычно передают функцию,
    - `__init__(self, current_account, on_switch_confirmed, parent=None)`

### `shared/account_manager.py`

- **`get_project_root()`** — Корень проекта — там же, где bridge_loader.py / GOR_Launcher.exe.
- **`get_browser_dir()`** — Папка встроенного браузера (GOR_Brauzer/) - именно там, а не в core/, реально создаётся GOR_Profile: browser_widget.py берёт
- **`get_accounts_dir()`**
- **`get_account_dir(name)`**
- **`validate_account_name(name)`** — Возвращает текст ошибки или None, если имя годится для папки аккаунта.
- **`list_accounts()`** — Список имён аккаунтов, отсортированный по алфавиту.
- **`get_last_active()`**
- **`account_exists(name)`**
- **`account_has_password(name)`**
- **`get_avatar_path(name)`** — Путь к обложке аккаунта, если она задана, иначе None.
- **`save_avatar_png(name, png_bytes)`** — Сохраняет уже готовые PNG-байты (обрезку/масштабирование делает UI-слой, у него есть QPixmap) как обложку аккаунта.
- **`remove_avatar(name)`**
- **`verify_password(name, password)`**
- **`create_account(name, password='', language=None)`** — Создаёт новый аккаунт (папку + запись в индексе). Возвращает (True, None) при успехе или (False, "причина") при ошибке.
- **`delete_account(name)`** — Удаляет аккаунт из индекса и его папку с данными. Нельзя удалить активный (заблокированный ссылками) аккаунт — сначала переключись.
- **`activate_account(name)`** — Переключает лаунчер на аккаунт `name`: подменяет games_data.json, core/GOR_Profile и addons ссылками на accounts/<name>/...

### `shared/cover_ipc.py`

- **`encode_message(data)`** — Сериализует сообщение в байты для отправки через QLocalSocket.
- **`try_decode_line(buffer)`** — Пытается вытащить ОДНО полное сообщение из накопленного буфера байт. Возвращает (dict_или_None, остаток_буфера). Так как TCP/локальные

### `shared/gamepad.py`

- **`decode_state(buttons, lx=0, ly=0, lt=0, rt=0)`** — Сырое состояние одного контроллера -> frozenset логических кнопок.
- **class `ButtonRepeater()`** — Превращает "что зажато сейчас" в события нажатия.
    - `__init__(self)`
    - `update(self, held, now)`
    - `swallow(self, held)` — Считать все сейчас зажатые кнопки уже обработанными: событий не будет, пока их не отпустят (нужно после возврата из игры, где A мог остаться зажатым).
- **class `_XInputGamepad(ctypes.Structure)`**
- **class `_XInputState(ctypes.Structure)`**
- **class `XInputBackend()`** — Опрос до 4 контроллеров. poll() -> список (buttons, lx, ly, lt, rt) подключённых. Пустые слоты XInput опрашивает медленно, поэтому их проверяем редко (раз в сек
    - `__init__(self)`
    - `poll(self)`
- **class `LinuxJoystickBackend()`** — Геймпады на Linux через legacy joystick API (/dev/input/js*), без зависимостей.
    - `__init__(self, dev_dir='/dev/input', max_slots=4)`
    - `poll(self)`
- **`default_backend()`** — XInput на Windows, joystick API на Linux, иначе None (остаётся клавиатура).
- **class `GamepadReader(QObject)`** — Опрашивает геймпад по таймеру и испускает pressed("a") и т.п.
    - `__init__(self, backend='auto', parent=None, interval_ms=16)`
    - `available(self)`
    - `connected(self)`
    - `start(self)`
    - `stop(self)`
    - `set_paused(self, paused)` — На паузе ввод игнорируется (игра/стрим на переднем плане), но состояние кнопок отслеживается - после снятия паузы зажатое не превращается в нажатие.
    - `resync(self)`
    - `poll(self, now=None)`

### `shared/lang_loader.py`

- **`available_languages()`** — Возвращает список языков, найденных в папке lang/.
- **`get_language()`** — Читает текущий выбранный язык: сначала из предпочтений активного аккаунта (accounts/<имя>/preferences.json), затем из games_data.json.
- **`set_language(code)`** — Сохраняет выбранный язык в games_data.json и сразу активирует его.
- **`reload_language(code=None)`** — Перечитывает словарь текущего (или указанного) языка с диска.
- **`current_language()`**
- **`ensure_loaded()`**
- **`tr(key, **kwargs)`** — Возвращает переведённую строку по ключу вида 'раздел.имя'.

### `shared/safe_json.py`

- **`write_json_inplace(path, data, **dump_kwargs)`**
- **`read_json(path, default_factory=dict)`** — Читает JSON. Нет файла -> default. Битый файл -> .bak -> default (с сохранением битого файла рядом, ничего не теряется).

### `shared/single_instance.py`

- **`server_name(project_root)`**
- **`forward_to_running(project_root, command, wait_for_close=False, connect_timeout_ms=800)`** — True - команда передана работающему экземпляру (текущий процесс должен завершиться).
- **class `SingleInstanceServer(QObject)`** — Слушает команды от повторных запусков. command(текст, сокет): сокет закрывает обработчик.
    - `__init__(self, project_root, parent=None)`
    - `listen(self)` — Если имя занято (например, после перезапуска старый процесс ещё не вышел) - пробуем ещё несколько секунд в фоне.
    - `listening(self)`
    - `close(self)`

### `shared/style_loader.py`

- **`load_stylesheet()`** — Читает style.qss из корня проекта и возвращает его содержимое.
- **`apply_global_style(app)`** — Применяет общий style.qss ко всему приложению (QApplication).

### `shared/updater.py`

- **`get_project_root()`** — Корневая директория лаунчера (рядом с запускаемым исполняемым файлом).
- **`get_local_version()`**
- **class `UpdateWorker(QThread)`** — Фоновый поток обновления.
    - `__init__(self, mode, current_version='0.0.0')`
    - `cancel(self)`
    - `run(self)`
- **class `UpdaterDialog(QDialog)`** — Окно обновления GOR Launcher, оформленное в едином стиле проекта (style.qss, селектор #EditorDialog).
    - `__init__(self, parent=None, known_info=None)` — known_info - словарь из version.json, если версия уже была проверена ДО открытия диалога (например фоновой проверкой при
    - `install_update(self)`
    - `cancel_or_close(self)`
    - `closeEvent(self, event)`
