#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
build_windows_release.py - сборка Windows-дистрибутива GorLauncher.

Что делает:
  1. Проверяет, что на месте все компоненты (Common Core + Windows-компоненты).
  2. Копирует их во временную папку GorLauncher_Windows/, отсекая мусор
     (__pycache__, GOR_Profile, .pyc, .git, .orphan, бэкапы, копии папок).
  3. Пакует папку в GorLauncher-Windows.zip.
  4. Кладёт архив в WEB/, чтобы сайт (WEB/download.html) мог сразу его отдавать.

Безопасность: исходники только ЧИТАЮТСЯ. Пишет скрипт лишь в временную папку
сборки и в WEB/GorLauncher-Windows.zip. games_data.json и accounts/ никогда
не копируются в релиз и не изменяются (в конце это проверяется).

Запуск (из корня проекта, рядом с bridge_loader.py):
    python build_windows_release.py
Справка по параметрам:
    python build_windows_release.py --help

Требуется только стандартная библиотека Python 3.8+.
"""
from __future__ import annotations

import argparse
import fnmatch
import hashlib
import os
import re
import shutil
import sys
import time
import zipfile
from collections import Counter
from dataclasses import dataclass, field
from pathlib import Path

# ════════════════════════════════════════════════════════════════════════════
#  НАСТРОЙКИ
# ════════════════════════════════════════════════════════════════════════════

STAGING_NAME = "GorLauncher_Windows"        # временная папка сборки (и корневая папка внутри ZIP)
ZIP_NAME = "GorLauncher-Windows.zip"        # итоговый архив
WEB_DIRNAME = "WEB"                         # куда публикуется архив
OLD_DOWNLOAD_HREF = "downloads/GOR_Launcher_Win.zip"   # старая ссылка в WEB/download.html


@dataclass(frozen=True)
class Item:
    """Один элемент дистрибутива."""
    name: str                  # имя в корне проекта (и в релизе)
    kind: str                  # "file" | "dir"
    required: bool = True      # без обязательного элемента сборка останавливается
    third_party: bool = False  # True: чужой код (runtime, Sunshine) - мягкие правила очистки
    note: str = ""


# ── Общие файлы (Common Core) - из вашего ТЗ ────────────────────────────────
COMMON_CORE = [
    Item("bridge_loader.py", "file"),
    Item("core", "dir"),
    Item("shared", "dir"),
    Item("lang", "dir"),
    Item("themes", "dir"),
    Item("WEB", "dir"),
    Item("editors", "dir"),
    Item("remote", "dir"),
    Item("extras", "dir"),
    Item("addons_sys", "dir"),
    Item("addons", "dir"),
]

# ── Дополнительно найдено в проекте и нужно для запуска ─────────────────────
# bridge_loader.py делает `from addon_API import ...`, а sys.path включает
# GOR_Brauzer, поэтому без этих двух папок лаунчер не стартует.
COMMON_EXTRA = [
    Item("addon_API", "dir", note="импортируется в bridge_loader.py"),
    Item("GOR_Brauzer", "dir", note="встроенный браузер"),
    Item("style.qss", "file", required=False),
    Item("version.json", "file", required=False, note="версия для апдейтера"),
    Item("launcher_start.py", "file", required=False),
    Item("requirements.txt", "file", required=False),
    Item("logo.png", "file", required=False),
    Item("favicon.ico", "file", required=False),
    Item("README.md", "file", required=False),
]

# ── Windows-компоненты ──────────────────────────────────────────────────────
WINDOWS_COMPONENTS = [
    Item("GOR_Launcher.exe", "file"),
    Item("runtime", "dir", third_party=True, note="embeddable Python"),
    Item("Sunshine", "dir", third_party=True, note="Sunshine (sunshine.exe)"),
]

# ════════════════════════════════════════════════════════════════════════════
#  ПРАВИЛА ОЧИСТКИ
# ════════════════════════════════════════════════════════════════════════════

# Папки-мусор (по имени, на любой глубине)
JUNK_DIRS = {
    "__pycache__": "кэш Python (__pycache__)",
    "GOR_Profile": "профиль браузера (GOR_Profile)",
    ".git": ".git / IDE / venv",
    ".svn": ".git / IDE / venv",
    ".hg": ".git / IDE / venv",
    ".idea": ".git / IDE / venv",
    ".vscode": ".git / IDE / venv",
    ".venv": ".git / IDE / venv",
    ".pytest_cache": ".git / IDE / venv",
    ".mypy_cache": ".git / IDE / venv",
}

# Маски имён (для файлов И папок). Порядок важен: первая подошедшая выигрывает.
# Только для собственных файлов проекта.
PROJECT_GLOBS = [
    ("*.pyc", "файлы .pyc"),
    ("*.pyo", "файлы .pyc"),
    ("*.orphan*", "файлы .orphan"),
    ("*.bak", "бэкапы"),
    ("*.backup", "бэкапы"),
    ("*.old", "бэкапы"),
    ("*.orig", "бэкапы"),
    ("*.tmp", "временные файлы"),
    ("*.swp", "временные файлы"),
    ("*~", "временные файлы"),
    ("Thumbs.db", "служебные файлы ОС"),
    ("desktop.ini", "служебные файлы ОС"),
    (".DS_Store", "служебные файлы ОС"),
    (".gitignore", ".git / IDE / venv"),
    (".gitattributes", ".git / IDE / venv"),
]

# Для чужих папок (runtime, Sunshine) - только безопасный минимум.
# .pyc здесь НЕ трогаем: в site-packages бывают пакеты без исходников.
THIRD_PARTY_GLOBS = [
    ("*.orphan*", "файлы .orphan"),
    ("Thumbs.db", "служебные файлы ОС"),
    (".DS_Store", "служебные файлы ОС"),
]

# Личные данные и секреты разработчика в папке Sunshine (ключи, пароль, логи)
THIRD_PARTY_SECRETS = [
    ("sunshine_state.json", "секреты Sunshine (пароль/сертификаты)"),
    ("credentials", "секреты Sunshine (пароль/сертификаты)"),
    ("*.log", "логи"),
]

# Папки-копии: «gor_style — копия», «addon (copy)», «addon_backup» и т.п.
COPY_DIR_RE = re.compile(r"(?i)(копия|[\s_-]copy(\s*\(\d+\))?|[\s_-]backup|_bak)$")

# Пользовательские данные: НИКОГДА не попадают в релиз и не изменяются.
PROTECTED_FILE_GLOBS = ["games_data.json*"]       # игры, группы, настройки (+ .bak, .orphan-*)
PROTECTED_ROOT_DIRS = {"accounts"}                # аккаунты (только в корне проекта)
PROTECTED_REL_PATHS = {"GOR_Brauzer/history.json"}  # личная история браузера
USER_DATA_REASON = "пользовательские данные"

# Архивы внутри WEB/ не копируем: иначе при повторной сборке старый ZIP
# окажется внутри нового.
WEB_ARCHIVE_EXTS = (".zip", ".7z", ".rar", ".tar", ".tar.gz", ".tgz")
WEB_ARCHIVE_REASON = "архивы релизов в WEB/"


class Rules:
    """Решает, нужно ли пропустить файл/папку при копировании."""

    def __init__(self, third_party: bool):
        self.third_party = third_party

    def check(self, rel: str, name: str, is_dir: bool) -> str | None:
        """rel - путь внутри релиза в формате a/b/c. Возвращает причину пропуска или None."""
        # 1. Пользовательские данные - всегда, для любых компонентов
        if rel in PROTECTED_REL_PATHS:
            return USER_DATA_REASON
        if rel.split("/", 1)[0] in PROTECTED_ROOT_DIRS and not self.third_party:
            return USER_DATA_REASON
        if not is_dir and any(fnmatch.fnmatch(name, g) for g in PROTECTED_FILE_GLOBS):
            return USER_DATA_REASON

        # 2. Папки-мусор
        if is_dir and name in JUNK_DIRS:
            return JUNK_DIRS[name]

        # 3. Маски имён
        globs = THIRD_PARTY_GLOBS if self.third_party else PROJECT_GLOBS
        for pattern, reason in globs:
            if fnmatch.fnmatch(name, pattern):
                return reason

        if self.third_party:
            for pattern, reason in THIRD_PARTY_SECRETS:
                if fnmatch.fnmatch(name, pattern):
                    return reason
            return None

        # 4. Папки-копии (только свои)
        if is_dir and COPY_DIR_RE.search(name):
            return "бэкапы и копии папок"

        # 5. Архивы в WEB/
        if not is_dir and rel.startswith(WEB_DIRNAME + "/") and name.lower().endswith(WEB_ARCHIVE_EXTS):
            return WEB_ARCHIVE_REASON
        return None


# ════════════════════════════════════════════════════════════════════════════
#  ВЫВОД В КОНСОЛЬ
# ════════════════════════════════════════════════════════════════════════════

def _setup_console() -> bool:
    """UTF-8 и ANSI-цвета (в т.ч. в cmd/PowerShell). Возвращает True, если цвета включены."""
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8", errors="replace")
        except Exception:
            pass
    if os.name == "nt":
        os.system("")  # включает обработку ANSI-последовательностей в консоли Windows
    return sys.stdout.isatty() and "NO_COLOR" not in os.environ


COLOR = _setup_console()


def _c(code: str, text: str) -> str:
    return f"\033[{code}m{text}\033[0m" if COLOR else text


def ok(msg: str) -> None:
    print(f"  {_c('32', '✓')} {msg}")


def warn(msg: str) -> None:
    print(f"  {_c('33', '!')} {_c('33', msg)}")


def fail(msg: str) -> None:
    print(f"  {_c('31', '✗')} {_c('31', msg)}")


def info(msg: str) -> None:
    print(f"    {_c('90', msg)}")


def section(num: int, title: str) -> None:
    print()
    print(_c("1;36", f"━━ {num}. {title} " + "━" * max(3, 60 - len(title))))


def human(n: float) -> str:
    for unit in ("Б", "КБ", "МБ", "ГБ"):
        if n < 1024 or unit == "ГБ":
            return f"{n:.0f} {unit}" if unit == "Б" else f"{n:.1f} {unit}"
        n /= 1024
    return f"{n:.1f} ГБ"


# ════════════════════════════════════════════════════════════════════════════
#  КОПИРОВАНИЕ
# ════════════════════════════════════════════════════════════════════════════

@dataclass
class Stats:
    files: int = 0
    size: int = 0
    skipped: Counter = field(default_factory=Counter)
    skipped_paths: list = field(default_factory=list)

    def add(self, other: "Stats") -> None:
        self.files += other.files
        self.size += other.size
        self.skipped.update(other.skipped)
        self.skipped_paths.extend(other.skipped_paths)


def copy_tree(src: Path, dst: Path, rel: str, rules: Rules, stats: Stats, ancestors: frozenset = frozenset()) -> None:
    """Рекурсивно копирует src в dst, применяя rules. Исходники не изменяются."""
    real = os.path.realpath(src)
    if real in ancestors:  # петля из ссылок/junction
        stats.skipped["циклические ссылки"] += 1
        stats.skipped_paths.append(rel)
        return
    ancestors = ancestors | {real}

    dst.mkdir(parents=True, exist_ok=True)
    with os.scandir(src) as it:
        entries = sorted(it, key=lambda e: e.name.lower())

    for entry in entries:
        child_rel = f"{rel}/{entry.name}"
        try:
            is_dir = entry.is_dir()  # следует за junction/symlink (аккаунты используют junction)
        except OSError:
            is_dir = False

        reason = rules.check(child_rel, entry.name, is_dir)
        if reason is None and not os.path.exists(entry.path):
            reason = "битые ссылки"
        if reason:
            stats.skipped[reason] += 1
            stats.skipped_paths.append(f"{child_rel}  <- {reason}")
            continue

        if is_dir:
            copy_tree(Path(entry.path), dst / entry.name, child_rel, rules, stats, ancestors)
        else:
            target = dst / entry.name
            shutil.copy2(entry.path, target)
            stats.files += 1
            stats.size += target.stat().st_size


def copy_item(item: Item, src: Path, staging: Path) -> Stats:
    stats = Stats()
    rules = Rules(third_party=item.third_party)
    if item.kind == "dir":
        copy_tree(src, staging / item.name, item.name, rules, stats)
    else:
        shutil.copy2(src, staging / item.name)
        stats.files = 1
        stats.size = (staging / item.name).stat().st_size
    return stats


# ════════════════════════════════════════════════════════════════════════════
#  ПРОВЕРКИ
# ════════════════════════════════════════════════════════════════════════════

def is_inside(child: Path, parent: Path) -> bool:
    try:
        child.resolve().relative_to(parent.resolve())
        return True
    except ValueError:
        return False


def fingerprint_user_data(root: Path) -> dict:
    """Отпечаток games_data.json* и accounts/ (размер, mtime) - чтобы доказать, что сборка их не трогала."""
    fp: dict = {}
    for p in sorted(root.glob("games_data.json*")):
        if p.is_file():
            st = p.stat()
            fp[p.name] = (st.st_size, st.st_mtime_ns)
    acc = root / "accounts"
    if acc.is_dir():
        count = total = newest = 0
        for dirpath, _dirs, files in os.walk(acc):
            for f in files:
                try:
                    st = os.stat(os.path.join(dirpath, f))
                except OSError:
                    continue
                count += 1
                total += st.st_size
                newest = max(newest, st.st_mtime_ns)
        fp["accounts/"] = (count, total, newest)
    return fp


def validate_windows_parts(runtime: Path, sunshine: Path, warnings: list) -> None:
    """Мягкие проверки содержимого runtime/ и Sunshine/ (только предупреждения)."""
    if runtime.is_dir():
        if not ((runtime / "pythonw.exe").is_file() or (runtime / "python.exe").is_file()):
            warnings.append("runtime/: нет python.exe / pythonw.exe - launcher_start.py не сможет запустить лаунчер")
        site_dirs = [runtime / "Lib" / "site-packages", runtime / "site-packages", runtime]
        for pkg in ("PyQt6", "psutil"):
            if not any((d / pkg).is_dir() for d in site_dirs):
                warnings.append(f"runtime/: не найден пакет {pkg} (нужен по requirements.txt)")
    if sunshine.is_dir() and not (sunshine / "sunshine.exe").is_file():
        warnings.append("Sunshine/: нет sunshine.exe")


# ════════════════════════════════════════════════════════════════════════════
#  ZIP
# ════════════════════════════════════════════════════════════════════════════

def make_zip(staging: Path, zip_path: Path) -> int:
    """Пакует staging в zip (корневая папка внутри архива = имя staging). Запись атомарная."""
    tmp = zip_path.with_name(zip_path.name + ".tmp")
    count = 0
    try:
        with zipfile.ZipFile(tmp, "w", zipfile.ZIP_DEFLATED, compresslevel=6) as zf:
            for dirpath, dirnames, filenames in os.walk(staging):
                dirnames.sort(key=str.lower)
                rel_dir = Path(dirpath).relative_to(staging.parent)
                if not dirnames and not filenames:  # сохраняем пустые папки
                    zf.write(dirpath, rel_dir.as_posix() + "/")
                for fname in sorted(filenames, key=str.lower):
                    full = Path(dirpath) / fname
                    zf.write(full, (rel_dir / fname).as_posix())
                    count += 1
        os.replace(tmp, zip_path)  # атомарно подменяем старый архив новым
    finally:
        if tmp.exists():
            tmp.unlink()
    return count


def verify_zip(zip_path: Path, missing_ok: bool) -> list:
    """Проверяет целостность архива и отсутствие пользовательских данных. Возвращает список проблем."""
    problems = []
    with zipfile.ZipFile(zip_path) as zf:
        bad = zf.testzip()
        if bad:
            problems.append(f"повреждён файл в архиве: {bad}")
        names = zf.namelist()
    prefix = STAGING_NAME + "/"
    for n in names:
        rel = n[len(prefix):] if n.startswith(prefix) else n
        parts = rel.rstrip("/").split("/")
        if fnmatch.fnmatch(parts[-1], "games_data.json*") or parts[0] in PROTECTED_ROOT_DIRS:
            problems.append(f"в архив попали пользовательские данные: {n}")
        is_pyc = parts[-1].endswith(".pyc") and parts[0] not in ("runtime", "Sunshine")
        if "__pycache__" in parts[:-1] and parts[0] not in ("runtime", "Sunshine") or "GOR_Profile" in parts or is_pyc:
            problems.append(f"в архив попал мусор: {n}")
    must_have = [prefix + "bridge_loader.py"]
    if not missing_ok:
        must_have.append(prefix + "GOR_Launcher.exe")
    for m in must_have:
        if m not in names:
            problems.append(f"в архиве нет {m}")
    return problems


def sha256_of(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


# ════════════════════════════════════════════════════════════════════════════
#  ОСНОВНАЯ ЛОГИКА
# ════════════════════════════════════════════════════════════════════════════

def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(
        description="Сборка Windows-дистрибутива GorLauncher (GorLauncher-Windows.zip -> WEB/).",
    )
    p.add_argument("--root", type=Path, default=Path(__file__).resolve().parent,
                   help="корень проекта (по умолчанию - папка со скриптом)")
    p.add_argument("--exe", type=Path, help="путь к GOR_Launcher.exe, если он лежит не в корне")
    p.add_argument("--runtime", type=Path, help="путь к папке embeddable Python, если она не <root>/runtime")
    p.add_argument("--sunshine", type=Path, help="путь к папке Sunshine, если она не <root>/Sunshine")
    p.add_argument("--build-dir", type=Path, help="где создавать GorLauncher_Windows/ (по умолчанию - корень проекта)")
    p.add_argument("--allow-missing", action="store_true",
                   help="не останавливаться, если нет GOR_Launcher.exe / runtime / Sunshine (релиз будет неполным!)")
    p.add_argument("--keep-staging", action="store_true", help="не удалять папку GorLauncher_Windows/ после сборки")
    p.add_argument("--no-publish", action="store_true", help="не класть ZIP в WEB/, оставить в папке сборки")
    p.add_argument("--patch-download-html", action="store_true",
                   help=f"заменить в WEB/download.html ссылку {OLD_DOWNLOAD_HREF} на {ZIP_NAME} (с резервной копией)")
    p.add_argument("-v", "--verbose", action="store_true", help="печатать каждый пропущенный файл")
    return p.parse_args()


def main() -> int:
    args = parse_args()
    t0 = time.time()
    root: Path = args.root.resolve()
    build_dir: Path = (args.build_dir or root).resolve()
    staging = build_dir / STAGING_NAME
    web_dir = root / WEB_DIRNAME

    print(_c("1;35", "\n  GorLauncher · сборка Windows-релиза"))
    info(f"проект: {root}")

    if not (root / "bridge_loader.py").is_file():
        fail("В корне проекта нет bridge_loader.py. Запустите скрипт из корня проекта или укажите --root.")
        return 2

    # ── 1. Инвентаризация ────────────────────────────────────────────────
    section(1, "Проверка компонентов")
    overrides = {"GOR_Launcher.exe": args.exe, "runtime": args.runtime, "Sunshine": args.sunshine}
    plan: list = []          # (группа, Item, путь-источник)
    missing_required: list = []
    missing_optional: list = []

    for group, items in (("Common Core", COMMON_CORE + COMMON_EXTRA), ("Windows", WINDOWS_COMPONENTS)):
        print(f"  {_c('1', group)}")
        for item in items:
            src = (overrides.get(item.name) or (root / item.name)).resolve()
            exists = src.is_dir() if item.kind == "dir" else src.is_file()
            label = item.name + ("/" if item.kind == "dir" else "")
            note = f"  ({item.note})" if item.note else ""
            if exists:
                ok(f"{label}{note}")
                plan.append((group, item, src))
            elif item.required:
                fail(f"{label} - НЕ НАЙДЕН{note}")
                missing_required.append(item)
            else:
                warn(f"{label} - не найден, пропускаю (необязательный)")
                missing_optional.append(item)

    part_warnings: list = []
    validate_windows_parts(
        (args.runtime or root / "runtime").resolve(),
        (args.sunshine or root / "Sunshine").resolve(),
        part_warnings,
    )
    for w in part_warnings:
        warn(w)

    missing_windows = [i for i in missing_required if i in WINDOWS_COMPONENTS]
    missing_common = [i for i in missing_required if i not in WINDOWS_COMPONENTS]
    if missing_common:
        fail("Не хватает обязательных общих файлов - собирать нечего. Сборка остановлена.")
        return 2
    if missing_windows and not args.allow_missing:
        fail("Не хватает Windows-компонентов: " + ", ".join(i.name for i in missing_windows))
        info("Положите их в корень проекта, укажите --exe / --runtime / --sunshine,")
        info("или запустите с --allow-missing, чтобы собрать НЕПОЛНЫЙ релиз (для теста).")
        return 2
    if missing_windows:
        warn("Режим --allow-missing: релиз будет НЕПОЛНЫМ и не подходит для публикации!")
        warn("В WEB/ он не попадёт (чтобы не затереть рабочий архив) - ZIP останется в папке сборки.")
        args.no_publish = True

    # ── Защита пользовательских данных: проверки до любых изменений ─────
    if staging == root or is_inside(root, staging):
        fail(f"Папка сборки {staging} совпадает с проектом или содержит его.")
        return 2
    for _g, item, src in plan:
        if item.kind == "dir" and is_inside(staging, src):
            fail(f"Папка сборки лежит внутри {item.name}/ - она скопировала бы сама себя. Укажите другой --build-dir.")
            return 2
    if staging.exists():
        # В распакованном релизе пользователь мог начать работу: тогда там его games_data.json / accounts/.
        for pattern in PROTECTED_FILE_GLOBS:
            if any(staging.glob(pattern)) or any((staging / d).exists() for d in PROTECTED_ROOT_DIRS):
                fail(f"В {staging} найдены games_data.json или accounts/ - похоже, это рабочая установка.")
                info("Сборка остановлена, чтобы не удалить ваши данные. Перенесите их или удалите папку вручную.")
                return 2

    before = fingerprint_user_data(root)

    # ── 2. (необязательно) ссылка на сайте ───────────────────────────────
    download_html = web_dir / "download.html"
    if args.patch_download_html and download_html.is_file():
        section(2, "Ссылка в WEB/download.html")
        raw = download_html.read_bytes()
        if OLD_DOWNLOAD_HREF.encode() in raw:
            shutil.copy2(download_html, download_html.with_name("download.html.bak"))
            download_html.write_bytes(raw.replace(OLD_DOWNLOAD_HREF.encode(), ZIP_NAME.encode()))
            ok(f"{OLD_DOWNLOAD_HREF} -> {ZIP_NAME} (копия: download.html.bak)")
        elif ZIP_NAME.encode() in raw:
            ok("ссылка уже указывает на " + ZIP_NAME)
        else:
            warn(f"в download.html не найдена ссылка {OLD_DOWNLOAD_HREF} - поправьте вручную")

    # ── 3. Копирование ───────────────────────────────────────────────────
    section(3, f"Копирование в {STAGING_NAME}/")
    if staging.exists():
        shutil.rmtree(staging)
        info("старая временная папка удалена")
    staging.mkdir(parents=True)

    totals = {"Common Core": Stats(), "Windows": Stats()}
    for group, item, src in plan:
        s = copy_item(item, src, staging)
        totals[group].add(s)
        skipped_n = sum(s.skipped.values())
        extra = f", пропущено {skipped_n}" if skipped_n else ""
        info(f"{item.name + ('/' if item.kind == 'dir' else ''):<20} {s.files:>6} файлов  {human(s.size):>10}{extra}")

    print()
    for group, s in totals.items():
        ok(f"{group}: {s.files} файлов, {human(s.size)}")
    skipped_all = Counter()
    skipped_paths: list = []
    for s in totals.values():
        skipped_all.update(s.skipped)
        skipped_paths.extend(s.skipped_paths)
    if skipped_all:
        print(f"  {_c('1', 'Отсеяно как мусор / личные данные:')}")
        for reason, n in skipped_all.most_common():
            info(f"{reason}: {n}")
        if args.verbose:
            for sp in skipped_paths:
                info("  - " + sp)

    # ── 4. ZIP ───────────────────────────────────────────────────────────
    section(4, "Упаковка")
    zip_dir = build_dir if args.no_publish else web_dir
    zip_dir.mkdir(parents=True, exist_ok=True)
    zip_path = zip_dir / ZIP_NAME
    n_files = make_zip(staging, zip_path)
    ok(f"{zip_path.name}: {n_files} файлов, {human(zip_path.stat().st_size)}")
    info(f"sha256: {sha256_of(zip_path)}")

    # ── 5. Проверка результата ───────────────────────────────────────────
    section(5, "Проверка результата")
    problems = verify_zip(zip_path, missing_ok=bool(missing_windows))
    if problems:
        for pr in problems:
            fail(pr)
    else:
        ok("архив читается, пользовательских данных и мусора в нём нет")

    after = fingerprint_user_data(root)
    if before == after:
        ok("games_data.json и accounts/ не изменены")
    else:
        warn("games_data.json / accounts/ изменились за время сборки - скрипт их не трогал, "
             "вероятно, в это время работал лаунчер")

    if not args.keep_staging:
        shutil.rmtree(staging, ignore_errors=True)
        info("временная папка удалена (оставить: --keep-staging)")

    # ── Итог ─────────────────────────────────────────────────────────────
    print()
    status = "ГОТОВО" if not problems and not missing_windows else "ГОТОВО С ЗАМЕЧАНИЯМИ"
    print(_c("1;32" if status == "ГОТОВО" else "1;33", f"  {status} за {time.time() - t0:.1f} c"))
    info(f"архив: {zip_path}")
    if not args.no_publish and download_html.is_file() and ZIP_NAME.encode() not in download_html.read_bytes():
        warn(f"WEB/download.html не ссылается на {ZIP_NAME} - запустите с --patch-download-html или поправьте ссылку.")
    print()
    return 1 if problems else 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        print("\nПрервано пользователем.")
        sys.exit(130)
