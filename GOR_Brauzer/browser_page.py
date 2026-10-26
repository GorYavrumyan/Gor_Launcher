"""
browser_page.py
----------------
GORWebPage - обёртка над QWebEnginePage, которая перехватывает открытие
новых окон/вкладок (target="_blank", window.open() и т.п.) и создаёт для
них полноценную вкладку внутри GORBrowser вместо системного окна Qt.
"""

import time

from PyQt6.QtWebEngineCore import QWebEnginePage


class GORWebPage(QWebEnginePage):
    """Специальный класс страницы для обработки новых окон GOR-Browser."""

    def __init__(self, profile, parent=None):
        super().__init__(profile, parent)
        self.ins_browser = None  # Устанавливается в GORBrowser.add_new_tab
        self._popup_times = []   # времена последних открытий окон (защита от спама)

    def createWindow(self, _type):
        """
        Вызывается, когда страница хочет открыть новую вкладку (например,
        через target="_blank"). Вместо стандартного окна Qt мы создаём
        вкладку в нашем GORBrowser и возвращаем именно ОБЪЕКТ СТРАНИЦЫ.
        """
        # Если ссылка открывается ИЗ вкладки инкогнито, новая вкладка тоже
        # должна быть инкогнито - иначе это дыра в приватности (данные
        # "утекли" бы в обычный профиль через window.open()/target=_blank).
        # Защита от "попандеров": страница, которая в цикле вызывает window.open(),
        # раньше открывала неограниченное число вкладок. Не больше 5 окон за 3 секунды.
        now = time.monotonic()
        self._popup_times = [t for t in self._popup_times if now - t < 3.0]
        if len(self._popup_times) >= 5:
            return None
        self._popup_times.append(now)

        is_incognito = self.profile() == self.ins_browser.incognito_profile
        new_tab_widget = self.ins_browser.add_new_tab(incognito=is_incognito)

        # КРИТИЧЕСКОЕ ИСПРАВЛЕНИЕ: возвращаем .page(), а не сам виджет.
        # Это предотвращает вылеты при открытии ссылок в новых окнах.
        return new_tab_widget.page()
