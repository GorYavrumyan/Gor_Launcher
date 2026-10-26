# GOR Launcher: Windows + Linux

Патч накладывается поверх проекта: распакуй архив в корень лаунчера с заменой файлов.

## Запуск
- **Windows**: как раньше (`GOR_Launcher.exe` или `launcher_start.py`). Ничего менять не нужно.
- **Linux**: `./run_linux.sh` (при первом запуске сам создаст `.venv` и поставит PyQt6, PyQt6-WebEngine, psutil).
  Нужен Python 3.10+ и пакет `python3-venv`. Режим Big Picture: `./run_linux.sh --bigpicture`.

## Что изменено
| Файл | Что |
|---|---|
| `shared/platform_utils.py` (новый) | все различия ОС в одном месте |
| `shared/account_manager.py` | на Linux вместо `mklink /J` - симлинки (раньше данные копировались и расходились) |
| `core/game_card.py` | запуск/остановка игр: Linux - нативные файлы напрямую, `.exe/.bat` через Wine; остановка вместе с дочерними процессами |
| `shared/gamepad.py` | геймпад на Linux (`/dev/input/js*`, Xbox и PlayStation) |
| `launcher_start.py`, `run_linux.sh`, `requirements.txt` | запуск без `runtime/pythonw.exe` на Linux |
| `remote/sunshine_control.py`, `remote/tv_setup.py` | `sunshine` вместо `sunshine.exe`, `apps.json` в `~/.config/sunshine` |
| `GOR_Brauzer/GORbrauzer_desktop.py` | `os.startfile` без проверки платформы |
| `addon_API/system.py` | время простоя на Linux через `xprintidle` |

## Windows-игры на Linux
Игры `.exe` / `.bat` (и пути вида `C:\Games\x.exe`) запускаются через `wine`.
Другой запуск (например Proton): `export GOR_WINE=umu-run`.
Нативные игры: `.sh`, AppImage, ELF-бинарники (должны быть исполняемыми: `chmod +x`).

## Важно
- Пути к играм в `games_data.json` на Linux нужно указать заново (или оставить `C:\...`, если Wine-префикс их видит).
- Если в корне уже лежат настоящие папки `addons/` и т.п., а у аккаунта есть свои, лаунчер откладывает корневые в `*.orphan-<время>` (ничего не удаляется).
