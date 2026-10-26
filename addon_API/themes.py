"""
Движок тем GOR Launcher.

Как это работает
----------------
Базовое оформление - это style.qss в корне проекта (там жёстко прописаны
цвета). Тема НЕ заменяет этот файл, а "перекрашивает" его: у каждой
роли цвета (bg, surface, accent, ...) есть исходное значение в style.qss,
тема просто подставляет вместо него своё - за один проход, без
конфликтов. Потом дописываются шрифт, дополнительный QSS темы и
QSS-вставки аддонов.

Тема - это папка themes/<id>/ с файлом theme.json:

    {
      "name": "Неоновый розовый",
      "author": "Я",
      "version": "1.0",
      "description": "Текст для списка тем",
      "colors": {"accent": "#ff2d95", "bg": "#0d0014"},
      "font":   {"family": "Segoe UI", "size": 13},
      "replace": {"#ffcc00": "#00ffaa"},
      "qss": "theme.qss"
    }

Доступны любые из TOKENS ниже. Не указанные цвета остаются как есть,
а accent_dark и accent_hover вычисляются из accent сами. В theme.qss
работают подстановки {{accent}}, {{bg}} ... и {{theme_dir}}.

Состояние (какая тема активна и личные правки цветов) хранится в
themes/_state.json - поэтому тема применяется ко ВСЕМ окнам лаунчера,
включая редакторы и Control Center (они отдельные процессы и читают
оформление через shared/style_loader.py).

Модуль намеренно не импортирует PyQt при загрузке - его безопасно
вызывать откуда угодно.
"""

import os
import re
import json
import shutil
import colorsys
import contextlib

from . import accounts as _acc

_PKG_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(_PKG_DIR)
THEMES_DIR = os.path.join(PROJECT_ROOT, "themes")
STATE_FILE = os.path.join(THEMES_DIR, "_state.json")

# Роль цвета -> исходное значение в style.qss
TOKENS = {
    "bg":             "#0a0a0a",   # фон окон
    "surface":        "#1a1a1a",   # поля, кнопки, карточки
    "surface_alt":    "#141414",   # панели
    "surface_hover":  "#222",      # наведение / фокус на полях
    "border":         "#333",      # рамки
    "text":           "#f0f0f0",   # основной текст
    "text_muted":     "#888",      # приглушённый текст
    "accent":         "#007acc",   # акцентный цвет
    "accent_dark":    "#005f9e",   # акцент (нажатие)
    "accent_hover":   "#0090ee",   # акцент (наведение)
    "danger":         "#d9534f",   # опасные действия
    "warning":        "#ffcc00",   # предупреждения / избранное
    "success":        "#229954",   # успех
    "editor_bg":      "#1e1e1e",   # фон окон-редакторов
    "editor_accent":  "#0e639c",   # акцент редакторов
}

TOKEN_TITLES = {
    "bg": "Фон окон", "surface": "Поля и кнопки", "surface_alt": "Панели",
    "surface_hover": "Наведение на поля", "border": "Рамки",
    "text": "Основной текст", "text_muted": "Приглушённый текст",
    "accent": "Акцент", "accent_dark": "Акцент (нажатие)",
    "accent_hover": "Акцент (наведение)", "danger": "Опасное",
    "warning": "Предупреждение", "success": "Успех",
    "editor_bg": "Фон редакторов", "editor_accent": "Акцент редакторов",
}

DEFAULT_THEME_ID = "default"
_HEX_RE = re.compile(r"^#(?:[0-9a-fA-F]{3}|[0-9a-fA-F]{6})$")


# --------------------------------------------------------------------- #
# Работа с цветом
# --------------------------------------------------------------------- #
def _hex_to_rgb(c):
    c = c.lstrip("#")
    if len(c) == 3:
        c = "".join(ch * 2 for ch in c)
    return tuple(int(c[i:i + 2], 16) / 255 for i in (0, 2, 4))


def _rgb_to_hex(r, g, b):
    return "#%02x%02x%02x" % (round(r * 255), round(g * 255), round(b * 255))


def shade(color, lightness_delta):
    """Осветлить (>0) или затемнить (<0) цвет. lightness_delta: -1..1"""
    h, l, s = colorsys.rgb_to_hls(*_hex_to_rgb(color))
    l = max(0.0, min(1.0, l + lightness_delta))
    return _rgb_to_hex(*colorsys.hls_to_rgb(h, l, s))


def is_valid_color(c):
    return isinstance(c, str) and bool(_HEX_RE.match(c))


# --------------------------------------------------------------------- #
# Чтение тем с диска
# --------------------------------------------------------------------- #
def _read_json(path, default):
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return default


def _scan_dir(base, scope, found):
    if not base or not os.path.isdir(base):
        return
    for entry in sorted(os.listdir(base)):
        if entry.startswith("_"):
            continue
        full = os.path.join(base, entry)
        if os.path.isdir(full):
            data = _read_json(os.path.join(full, "theme.json"), None)
            tdir, tid = full, entry
        elif entry.endswith(".json"):
            data = _read_json(full, None)
            tdir, tid = base, entry[:-5]
        else:
            continue
        if not isinstance(data, dict):
            continue
        data = dict(data)
        data["id"] = data.get("id", tid)
        data.setdefault("name", tid)
        data["_dir"] = tdir
        data["scope"] = scope            # "shared" - общая тема, "account" - тема этого аккаунта
        found[data["id"]] = data


def _scan_themes():
    """{id: theme_dict}. Тема = <папка>/<id>/theme.json или <папка>/<id>.json.
    Видны общие темы (themes/) и собственные темы активного аккаунта (accounts/<имя>/themes/);
    при совпадении id тема аккаунта главнее."""
    found = {DEFAULT_THEME_ID: {
        "id": DEFAULT_THEME_ID, "name": "Стандартная (GOR)", "author": "GOR",
        "version": "1.0", "description": "Оригинальное оформление лаунчера",
        "colors": {}, "_dir": None, "scope": "shared",
    }}
    _scan_dir(THEMES_DIR, "shared", found)
    _scan_dir(_acc.themes_dir(), "account", found)
    return found


def _normalize_state(st):
    if not isinstance(st, dict):
        st = {}
    st = dict(st)
    st.setdefault("active", DEFAULT_THEME_ID)
    st.setdefault("overrides", {})
    return st


def _read_state():
    """Состояние темы: у каждого аккаунта своё (preferences.json -> theme).
    Без системы аккаунтов - старый общий файл themes/_state.json."""
    name = _acc.active_name()
    if name:
        st = _acc.pref("theme", None, name)
        if isinstance(st, dict):
            return _normalize_state(st)
        # у аккаунта ещё нет своей темы: до первого выбора показываем стандартную
        # (старый общий выбор «усыновляет» account_manager при первом входе в старый аккаунт)
        return _normalize_state({})
    return _normalize_state(_read_json(STATE_FILE, {}))


def _write_state(st):
    name = _acc.active_name()
    if name:
        _acc.set_pref("theme", st, name)
        return
    os.makedirs(THEMES_DIR, exist_ok=True)
    text = json.dumps(st, ensure_ascii=False, indent=2)   # до открытия файла: не обрезаем его при ошибке
    with open(STATE_FILE, "w", encoding="utf-8") as f:
        f.write(text)


def _own_themes_dir():
    """Куда сохранять НОВЫЕ темы: в папку активного аккаунта (или в общую, если аккаунтов нет)."""
    return _acc.themes_dir() or THEMES_DIR


# --------------------------------------------------------------------- #
# Сборка итогового стиля
# --------------------------------------------------------------------- #
def effective_colors(theme=None, overrides=None):
    """Итоговые значения всех TOKENS с учётом темы и личных правок."""
    colors = dict(TOKENS)
    given = {}
    if theme:
        given.update({k: v for k, v in (theme.get("colors") or {}).items() if k in TOKENS})
    if overrides:
        given.update({k: v for k, v in overrides.items() if k in TOKENS})
    given = {k: v for k, v in given.items() if is_valid_color(v)}
    colors.update(given)
    # производные оттенки акцента, если их не задали явно
    if "accent" in given:
        if "accent_dark" not in given:
            colors["accent_dark"] = shade(given["accent"], -0.12)
        if "accent_hover" not in given:
            colors["accent_hover"] = shade(given["accent"], 0.08)
    return colors


def _recolor(qss, colors, extra_replace=None):
    """Один проход: исходные цвета style.qss -> цвета темы."""
    mapping = {}
    for token, base in TOKENS.items():
        if colors[token].lower() != base.lower():
            mapping[base.lower()] = colors[token]
    for old, new in (extra_replace or {}).items():
        if is_valid_color(old) and is_valid_color(new):
            mapping[old.lower()] = new
    if not mapping:
        return qss
    keys = sorted(mapping, key=len, reverse=True)
    pattern = re.compile("(" + "|".join(re.escape(k) for k in keys) + r")(?![0-9a-fA-F])",
                         re.IGNORECASE)
    return pattern.sub(lambda m: mapping[m.group(1).lower()], qss)


def _fill_template(text, colors, theme_dir):
    """Подстановки в QSS:
        {{accent}}      - цвет роли
        {{accent@25}}   - тот же цвет с прозрачностью 25%  -> rgba(...)
        {{accent+10}}   - светлее на 10 пунктов
        {{accent-10}}   - темнее на 10 пунктов
        {{theme_dir}}   - папка темы (для картинок)"""
    def repl(m):
        key, op, num = m.group(1), m.group(2), m.group(3)
        if key == "theme_dir":
            return (theme_dir or "").replace("\\", "/")
        base = colors.get(key)
        if base is None:
            return m.group(0)
        if not op:
            return base
        n = float(num)
        if op == "@":
            r, g, b = _hex_to_rgb(base)
            return "rgba(%d,%d,%d,%.2f)" % (round(r * 255), round(g * 255),
                                            round(b * 255), max(0.0, min(1.0, n / 100)))
        return shade(base, n / 100 if op == "+" else -n / 100)
    return re.sub(r"\{\{\s*(\w+)\s*(?:([@+\-])\s*(\d+(?:\.\d+)?))?\s*\}\}", repl, text)


def read_base_qss():
    path = os.path.join(PROJECT_ROOT, "style.qss")
    try:
        with open(path, "r", encoding="utf-8") as f:
            return f.read()
    except Exception:
        return ""


def build_stylesheet(base_qss, snippets=None):
    """Главная функция: базовый style.qss + активная тема + правки + вставки аддонов."""
    try:
        state = _read_state()
        theme = _scan_themes().get(state["active"]) or _scan_themes()[DEFAULT_THEME_ID]
        merged = dict(state["overrides"])
        merged.update(_runtime.merged_colors())
        colors = effective_colors(theme, merged)
        out = _recolor(base_qss, colors, theme.get("replace"))

        rule = _runtime.radius_rule()
        if rule:
            out = _apply_radius_rule(out, *rule)
        fscale = _runtime.font_scale()
        if fscale:
            out = _scale_numbers(out, "font-size", lambda r: r * fscale)

        font = theme.get("font") or {}
        if font.get("family") or font.get("size"):
            rules = []
            if font.get("family"):
                rules.append('font-family: "%s";' % str(font["family"]).replace('"', ""))
            if font.get("size"):
                rules.append("font-size: %spx;" % int(font["size"]))
            out += "\n\n/* [theme font] */\nQWidget { %s }\n" % " ".join(rules)

        tdir = theme.get("_dir")
        qss_name = theme.get("qss")
        if qss_name and tdir:
            try:
                with open(os.path.join(tdir, qss_name), "r", encoding="utf-8") as f:
                    out += "\n\n/* [theme qss: %s] */\n%s\n" % (
                        theme["id"], _fill_template(f.read(), colors, tdir))
            except Exception as e:
                print(f"[themes] Не удалось прочитать qss темы {theme['id']}: {e}")

        for owner, qss in (snippets if snippets is not None else _snippets.items_flat()):
            out += "\n\n/* [addon: %s] */\n%s\n" % (os.path.basename(str(owner)),
                                                    _fill_template(qss, colors, None))
        return out
    except Exception as e:
        print(f"[themes] Ошибка сборки стиля, использую базовый: {e}")
        return base_qss


class _Runtime:
    """Временные настройки от аддонов (живут только в процессе лаунчера,
    не сохраняются на диск и откатываются при выгрузке аддона)."""
    def __init__(self):
        self.colors = {}   # owner -> {token: color}
        self.radius = {}   # owner -> ("scale"|"px", число)
        self.fonts = {}    # owner -> множитель размера шрифта

    def merged_colors(self):
        out = {}
        for d in self.colors.values():
            out.update(d)
        return out

    def radius_rule(self):
        return list(self.radius.values())[-1] if self.radius else None

    def font_scale(self):
        return list(self.fonts.values())[-1] if self.fonts else None


_runtime = _Runtime()


def _scale_numbers(qss, prop, fn):
    pattern = re.compile(r"(%s\s*:\s*)(\d+)(px)" % re.escape(prop))
    return pattern.sub(lambda m: "%s%d%s" % (m.group(1), max(0, round(fn(int(m.group(2))))), m.group(3)), qss)


# Qt рисует КВАДРАТНЫЕ углы, если border-radius больше половины высоты элемента.
# Для небольших элементов ограничиваем радиус, чтобы глобальное скругление не ломало их.
_SMALL_CONTROLS = (("QProgressBar", 5), ("QCheckBox", 6), ("QLineEdit", 15), ("QComboBox", 15),
                   ("QSpinBox", 15), ("QPushButton", 17), ("QTabBar", 16))


def _radius_cap(selector):
    caps = [cap for key, cap in _SMALL_CONTROLS if key in selector]
    return min(caps) if caps else None


def _apply_radius_rule(qss, mode, val):
    rule_re = re.compile(r"([^{}]+)\{([^{}]*)\}")
    rad_re = re.compile(r"((?<![-\w])border-radius\s*:\s*)(\d+)(px)")

    def fix_rule(m):
        sel, body = m.group(1), m.group(2)
        cap = _radius_cap(sel)

        def fix_val(mm):
            r = int(mm.group(2))
            new = round(r * val) if mode == "scale" else (val if r > 0 else 0)
            if cap is not None:
                new = min(new, cap)
            return "%s%d%s" % (mm.group(1), max(0, new), mm.group(3))
        return "%s{%s}" % (sel, rad_re.sub(fix_val, body))
    return rule_re.sub(fix_rule, qss)


class _Snippets:
    """QSS-вставки аддонов (живут только в процессе лаунчера)."""
    def __init__(self):
        self._data = []   # [(owner, qss)]

    def add(self, owner, qss, front=False):
        item = (owner, qss)
        if front:
            self._data.insert(0, item)   # низкий приоритет: любые другие стили перекроют
        else:
            self._data.append(item)
        return item

    def remove(self, item):
        if item in self._data:
            self._data.remove(item)

    def remove_owner(self, owner):
        self._data = [i for i in self._data if i[0] != owner]

    def items_flat(self):
        return list(self._data)


_snippets = _Snippets()


# --------------------------------------------------------------------- #
# Менеджер тем (то, что видит аддон через api.themes)
# --------------------------------------------------------------------- #
class ThemeManager:
    _defer = 0
    _dirty = False

    @contextlib.contextmanager
    def batch(self):
        """Внутри блока стиль пересобирается один раз - на выходе:
            with themes.batch():
                themes.set_color(...); themes.set_color(...)"""
        self._defer += 1
        try:
            yield
        finally:
            self._defer -= 1
            if self._defer == 0 and self._dirty:
                self._dirty = False
                self.refresh()

    def list(self):
        """[{id, name, author, version, description, colors}]"""
        return [
            {k: v for k, v in t.items() if not k.startswith("_")}
            for t in _scan_themes().values()
        ]

    def account_name(self):
        """Имя аккаунта, чьи темы и выбор сейчас действуют (None - системы аккаунтов нет)."""
        return _acc.active_name()

    def current_id(self):
        return _read_state()["active"]

    def colors(self):
        """Итоговые цвета прямо сейчас (с учётом темы и личных правок)."""
        st = _read_state()
        theme = _scan_themes().get(st["active"])
        merged = dict(st["overrides"])
        merged.update(_runtime.merged_colors())      # + живые цвета аддонов
        return effective_colors(theme, merged)

    def overrides(self):
        return dict(_read_state()["overrides"])

    def apply(self, theme_id, reset_overrides=True):
        """Применить тему ко всему лаунчеру и запомнить выбор."""
        if theme_id not in _scan_themes():
            raise KeyError(f"Тема '{theme_id}' не найдена")
        st = _read_state()
        st["active"] = theme_id
        if reset_overrides:
            st["overrides"] = {}
        _write_state(st)
        self.refresh()
        _emit_theme_changed(theme_id)

    def set_color(self, token, color, persist=True):
        """Поменять один цвет (личная правка поверх темы)."""
        if token not in TOKENS:
            raise KeyError(f"Неизвестная роль цвета: {token}")
        if not is_valid_color(color):
            raise ValueError(f"Некорректный цвет: {color}")
        st = _read_state()
        st["overrides"][token] = color
        if persist:
            _write_state(st)
        self.refresh()

    def set_colors(self, mapping):
        for k, v in mapping.items():
            if k in TOKENS and is_valid_color(v):
                st = _read_state()
                st["overrides"][k] = v
                _write_state(st)
        self.refresh()

    def reset_overrides(self):
        st = _read_state()
        st["overrides"] = {}
        _write_state(st)
        self.refresh()

    def refresh(self, app=None):
        """Пересобрать стиль и применить к QApplication."""
        if self._defer:
            self._dirty = True
            return
        try:
            if app is None:
                from PyQt6.QtWidgets import QApplication
                app = QApplication.instance()
            if app is not None:
                app.setStyleSheet(build_stylesheet(read_base_qss()))
        except Exception as e:
            print(f"[themes] refresh: {e}")

    def install(self, theme_id, data, qss_text=None):
        """Сохранить тему на диск: в папку темы ТЕКУЩЕГО аккаунта (accounts/<имя>/themes/<id>/),
        а без системы аккаунтов - в общую themes/. Возвращает id."""
        theme_id = re.sub(r"[^\w\-]+", "_", theme_id.strip().lower()) or "my_theme"
        folder = os.path.join(_own_themes_dir(), theme_id)
        os.makedirs(folder, exist_ok=True)
        clean = {k: v for k, v in data.items() if not k.startswith("_") and k != "id"}
        if qss_text:
            with open(os.path.join(folder, "theme.qss"), "w", encoding="utf-8") as f:
                f.write(qss_text)
            clean["qss"] = "theme.qss"
        with open(os.path.join(folder, "theme.json"), "w", encoding="utf-8") as f:
            json.dump(clean, f, ensure_ascii=False, indent=2)
        return theme_id

    def save_current_as(self, name, author=""):
        """Сохранить текущие цвета (тема + правки) как новую тему."""
        st = _read_state()
        theme = _scan_themes().get(st["active"]) or {}
        colors = {k: v for k, v in self.colors().items() if v.lower() != TOKENS[k].lower()}
        data = {"name": name, "author": author, "version": "1.0",
                "description": "Создана в Theme Studio", "colors": colors}
        for key in ("font", "replace"):
            if theme.get(key):
                data[key] = theme[key]
        qss_text = None
        if theme.get("qss") and theme.get("_dir"):
            try:
                with open(os.path.join(theme["_dir"], theme["qss"]), "r", encoding="utf-8") as f:
                    qss_text = f.read().replace(theme["_dir"].replace("\\", "/"), "{{theme_dir}}")
            except Exception:
                pass
        return self.install(name, data, qss_text)

    def import_file(self, path):
        """Импорт темы из .json файла или папки с theme.json. Возвращает id."""
        base = _own_themes_dir()
        os.makedirs(base, exist_ok=True)
        if os.path.isdir(path):
            tid = os.path.basename(path.rstrip("/\\"))
            if not tid or tid in (".", ".."):
                raise ValueError(f"Не удалось определить имя темы по пути: {path!r}")
            dst = os.path.join(base, tid)
            if os.path.abspath(dst) == os.path.abspath(path):
                return tid   # импорт папки из самой себя: rmtree удалил бы источник
            if os.path.exists(dst):
                shutil.rmtree(dst)
            shutil.copytree(path, dst)
            return tid
        tid = os.path.splitext(os.path.basename(path))[0]
        shutil.copy2(path, os.path.join(base, tid + ".json"))
        return tid

    def delete(self, theme_id):
        """Удалить тему. Свои темы аккаунта удаляются свободно; общие (themes/) защищены от удаления
        из-под аккаунта - они нужны остальным (без системы аккаунтов удаляются как раньше)."""
        if theme_id == DEFAULT_THEME_ID:
            return False
        # id приходит и от аддонов: "../что-то" привело бы к rmtree за пределами папки тем
        if not theme_id or theme_id in (".", "..") or os.path.basename(theme_id) != theme_id \
                or "/" in theme_id or "\\" in theme_id:
            return False
        bases = [_acc.themes_dir()] if _acc.active_name() else [THEMES_DIR]
        removed = False
        for base in bases:
            if not base:
                continue
            folder = os.path.join(base, theme_id)
            if os.path.isdir(folder):
                shutil.rmtree(folder)
                removed = True
            elif os.path.exists(folder + ".json"):
                os.remove(folder + ".json")
                removed = True
        if removed and _read_state()["active"] == theme_id:
            self.apply(DEFAULT_THEME_ID)
        return removed

    # --- живой слой аддонов (api.design) ---
    def set_runtime_colors(self, owner, mapping):
        valid = {k: v for k, v in mapping.items() if k in TOKENS and is_valid_color(v)}
        self_cur = _runtime.colors.setdefault(owner, {})
        self_cur.update(valid)
        self.refresh()

    def clear_runtime_colors(self, owner):
        _runtime.colors.pop(owner, None)
        self.refresh()

    def set_radius(self, owner, mode, value):
        """mode: "scale" (множитель всех скруглений) или "px" (все = value px)."""
        _runtime.radius[owner] = (mode, value)
        self.refresh()

    def set_font_scale(self, owner, factor):
        _runtime.fonts[owner] = factor
        self.refresh()

    def clear_runtime_of(self, owner):
        changed = any(owner in d for d in (_runtime.colors, _runtime.radius, _runtime.fonts))
        _runtime.colors.pop(owner, None)
        _runtime.radius.pop(owner, None)
        _runtime.fonts.pop(owner, None)
        if changed:
            self.refresh()

    def stylesheet(self):
        """Итоговый QSS, как он применён сейчас (для отладки/экспорта)."""
        return build_stylesheet(read_base_qss())

    # --- QSS-вставки аддонов (используются через api.ui.add_style) ---
    def add_snippet(self, owner, qss, front=False):
        item = _snippets.add(owner, qss, front)
        self.refresh()
        return item

    def remove_snippet(self, item):
        _snippets.remove(item)
        self.refresh()

    def remove_snippets_of(self, owner):
        _snippets.remove_owner(owner)
        self.refresh()


themes = ThemeManager()


def _emit_theme_changed(theme_id):
    try:
        from .events import emit_event, Events
        emit_event(Events.THEME_CHANGED, theme_id)
    except Exception:
        pass
