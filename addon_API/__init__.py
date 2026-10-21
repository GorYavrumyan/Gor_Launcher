"""
addon_API - единый API для аддонов, тем и кастомизации GOR Launcher.

    from addon_API import AddonBase, Events

Пакет загружается лениво: модули, которым нужен PyQt, подгружаются только
когда к ним обратились (так style_loader может безопасно брать темы из
любого процесса лаунчера).
"""

__version__ = "1.0.0"
API_VERSION = 1   # меняется только при несовместимых изменениях API

_LAZY = {
    "emit_event": ("events", "emit_event"),
    "Events": ("events", "Events"),
    "bus": ("events", "bus"),
    "theme_manager": ("themes", "themes"),
    "build_stylesheet": ("themes", "build_stylesheet"),
    "AddonAPI": ("api", "AddonAPI"),
    "AddonBase": ("base", "AddonBase"),
    "allow": ("hooks", "allow"),
    "apply_filter": ("hooks", "apply_filter"),
    "manager": ("loader", "manager"),
    "AddonManager": ("loader", "AddonManager"),
    "prepare_addon_folder": ("loader", "prepare_addon_folder"),
}


def __getattr__(name):
    if name in _LAZY:
        import importlib
        mod, attr = _LAZY[name]
        return getattr(importlib.import_module(f".{mod}", __name__), attr)
    raise AttributeError(f"module 'addon_API' has no attribute '{name}'")
