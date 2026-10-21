"""
api.design - кастомизация внешнего вида лаунчера из аддона.

Группы возможностей (всё откатывается при выгрузке аддона или design.reset()):

  ЦВЕТА        get_colors set_colors set_color accent palette palette_from_hue
               random_palette dark_mode light_mode palette_from_image dominant_color
               reset_colors transition_colors animate_accent rainbow breathe_accent
               save_as_theme export_qss                      + design.color.* (математика цвета)
  СТИЛИ        css qss remove widget_style clear_style radius sharp rounded font
               font_scale global_style batch
  КОМПОНЕНТЫ   buttons play_button inputs search_bar combos checkboxes lists menus
               tooltips progress dialogs labels tabs scrollbars cards covers card_text
               group_headers header search_and_sort
  ЭФФЕКТЫ      shadow glow hover_glow hover_shadow opacity blur colorize clear_effects
  АНИМАЦИИ     animate fade_in fade_out slide_in appear pulse shake bounce
               animate_tab_switch stop_animations
  СЛОИ         wallpaper tint vignette scanlines grid noise gradient_overlay
               animated_gradient particles clear_overlay
  ОКНО         window_opacity always_on_top window_size min_size center_window
               fullscreen screenshot cursor pointer_on_buttons load_font app_font
  ПОИСК        find_all each object_names describe selector_for dump inspector
  ПРЕСЕТЫ      presets preset_info preset reset
"""

from . import colors
from .qss import StyleMixin
from .effects import EffectsMixin
from .anim import AnimMixin
from .overlay import OverlayMixin
from .window import ColorsMixin, WindowMixin, InspectMixin
from .presets import PresetMixin
from ._util import safe


class DesignAPI(StyleMixin, ColorsMixin, EffectsMixin, AnimMixin, OverlayMixin,
                WindowMixin, InspectMixin, PresetMixin):

    color = colors            # design.color.lighten("#007acc", 10) и т.д.

    def __init__(self, api):
        from ..resources import Resources
        self._api = api
        self.launcher = api.launcher
        self._res = Resources()
        self._slots = {}          # имя слота -> QSS-вставка
        self._counter = 0
        self._anims = []
        self._polish = None
        self._overlay = None
        self._inspector = None
        self._color_timer = None
        api._resources.add(self.reset)

    def batch(self):
        """with design.batch(): ... - стиль пересоберётся один раз в конце блока."""
        from ..themes import themes
        return themes.batch()

    def reset(self):
        """Откатить ВСЁ, что этот аддон сделал через api.design."""
        from ..themes import themes
        with themes.batch():
            self.stop_color_animation()
            self.stop_animations()
            self._res.cleanup()
            for slot in list(self._slots):
                self.remove(slot)
            themes.clear_runtime_of(self._api.root)
