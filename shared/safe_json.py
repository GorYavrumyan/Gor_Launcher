"""
Безопасное чтение/запись JSON для данных лаунчера.

Почему не os.replace(tmp, path): games_data.json в корне проекта - это
жёсткая ссылка (hardlink) на accounts/<имя>/games_data.json
(см. account_manager.py). Подмена файла через rename разорвала бы ссылку,
и данные аккаунта разошлись бы с рабочим файлом. Поэтому пишем "на месте",
но:
  1) сначала полностью сериализуем данные в строку - если это не удалось
     (в данные попал неподдерживаемый объект), файл вообще не трогаем;
  2) не чаще раза в BACKUP_INTERVAL секунд кладём рядом копию <файл>.bak;
  3) при чтении битого файла пробуем .bak, а если и он не подошёл - откладываем
     битый файл в <файл>.corrupt-<время>, а не затираем его.
"""
import json
import os
import shutil
import time

BACKUP_INTERVAL = 60  # сек
_last_backup = {}


def _backup(path):
    try:
        if not os.path.exists(path) or os.path.getsize(path) == 0:
            return
        now = time.time()
        if now - _last_backup.get(path, 0) < BACKUP_INTERVAL:
            return
        shutil.copyfile(path, path + ".bak")
        _last_backup[path] = now
    except OSError:
        pass


def write_json_inplace(path, data, **dump_kwargs):
    dump_kwargs.setdefault("ensure_ascii", False)
    dump_kwargs.setdefault("indent", 4)
    text = json.dumps(data, **dump_kwargs)  # может бросить TypeError ДО изменения файла
    _backup(path)
    with open(path, "w", encoding="utf-8") as f:
        f.write(text)
        f.flush()


def read_json(path, default_factory=dict):
    """Читает JSON. Нет файла -> default. Битый файл -> .bak -> default
    (с сохранением битого файла рядом, ничего не теряется)."""
    if not os.path.exists(path):
        return default_factory()
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except (ValueError, UnicodeDecodeError):
        pass
    except OSError:
        return default_factory()
    bak = path + ".bak"
    try:
        with open(bak, "r", encoding="utf-8") as f:
            data = json.load(f)
        print(f"[safe_json] {path} повреждён, восстановлено из {bak}")
        return data
    except Exception:
        pass
    try:
        shutil.copyfile(path, f"{path}.corrupt-{time.strftime('%Y%m%d-%H%M%S')}")
        print(f"[safe_json] {path} повреждён, копия сохранена как .corrupt-*")
    except OSError:
        pass
    return default_factory()
