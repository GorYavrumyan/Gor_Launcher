"""
browser_page.py
----------------
GORWebPage - обёртка над QWebEnginePage, которая перехватывает открытие
новых окон/вкладок (target="_blank", window.open() и т.п.) и создаёт для
них полноценную вкладку внутри GORBrowser вместо системного окна Qt.
"""

from PyQt6.QtWebEngineCore import QWebEnginePage


class GORWebPage(QWebEnginePage):
    """Специальный класс страницы для обработки новых окон GOR-Browser."""

    def __init__(self, profile, parent=None):
        super().__init__(profile, parent)
        self.ins_browser = None  # Устанавливается в GORBrowser.add_new_tab

    def createWindow(self, _type):
        """
        Вызывается, когда страница хочет открыть новую вкладку (например,
        через target="_blank"). Вместо стандартного окна Qt мы создаём
        вкладку в нашем GORBrowser и возвращаем именно ОБЪЕКТ СТРАНИЦЫ.
        """
        # Если ссылка открывается ИЗ вкладки инкогнито, новая вкладка тоже
        # должна быть инкогнито - иначе это дыра в приватности (данные
        # "утекли" бы в обычный профиль через window.open()/target=_blank).
        is_incognito = self.profile() == self.ins_browser.incognito_profile
        new_tab_widget = self.ins_browser.add_new_tab(incognito=is_incognito)

        # КРИТИЧЕСКОЕ ИСПРАВЛЕНИЕ: возвращаем .page(), а не сам виджет.
        # Это предотвращает вылеты при открытии ссылок в новых окнах.
        return new_tab_widget.page()
