"""
browser_startpage.py
----------------------
Генерация стартовой страницы GOR Browser (start_page.html): часы, заголовок,
поле поиска и блок личных заметок (заметки хранятся в localStorage самой
страницы, а не в games_data.json).

Вынесено из GORBrowser.create_start_page в отдельную функцию write_start_page,
т.к. это чистая генерация HTML-строки по словарю настроек и не нуждается
в доступе к остальному состоянию браузера.
"""

from browser_constants import START_PAGE_PATH, SEARCH_ENGINES


def write_start_page(settings):
    """Генерирует start_page.html по переданным настройкам браузера
    (см. browser_constants.DEFAULT_SETTINGS за списком используемых ключей)."""
    accent = settings.get("theme_color", "#4c6ef5")
    opacity = 0.9
    font = settings.get("font_family", "Segoe UI")
    engine_name = settings.get("search_engine", "Google")
    search_url = SEARCH_ENGINES.get(engine_name, SEARCH_ENGINES["Google"])

    show_clock = settings.get("show_clock", True)
    show_title = settings.get("show_title", True)
    # Ключ в JSON исторически называется show_todo, хотя блок - "заметки"
    show_notes = settings.get("show_todo", True)

    clock_html = '<div id="clock">00:00</div>' if show_clock else ''
    title_html = '<h1 id="title">GOR CORE</h1>' if show_title else ''

    if show_notes:
        notes_html = """
        <div id="notes-wrapper">
            <div id="notes-container">
                <div class="notes-header">
                    <span>ЛИЧНЫЕ ЗАМЕТКИ</span>
                    <button onclick="addNote()">НОВАЯ ЗАМЕТКА +</button>
                </div>
                <div id="notes-list"></div>
            </div>
        </div>
        """
    else:
        notes_html = ""

    with open(START_PAGE_PATH, "w", encoding="utf-8") as f:
        f.write(f"""<!DOCTYPE html>
        <html>
        <head>
            <meta charset="UTF-8">
            <style>
                * {{ box-sizing: border-box; }}
                html, body {{
                    height: 100%; margin: 0; padding: 0;
                    overflow: hidden; background: #0b0c0d;
                    color: white; font-family: '{font}', sans-serif;
                }}
                body {{ display: flex; flex-direction: column; align-items: center; padding-top: 5vh; }}
                #clock {{ font-size: 110px; font-weight: 100; color: {accent}; margin-bottom: 5px; }}
                #title {{ margin-bottom: 30px; letter-spacing: 8px; font-weight: 300; color: #555; }}
                .search-container {{ width: 600px; margin-bottom: 20px; flex-shrink: 0; }}
                .search-box {{
                    background: rgba(28, 29, 33, {opacity}); 
                    border-radius: 40px; border: 1px solid rgba(255,255,255,0.1); 
                    display: flex; align-items: center; padding: 5px 25px;
                }}
                input {{ flex: 1; background: transparent; border:none; color:white; padding:15px; outline:none; font-size:18px; }}

                /* СТИЛИ ЗАМЕТОК: ШИРИНА 600px, БЕЗ СКРОЛЛА ОКНА */
                #notes-wrapper {{ width: 600px; display: flex; justify-content: center; flex-grow: 1; overflow: hidden; margin-bottom: 60px; }}
                #notes-container {{ width: 100%; background: rgba(20, 21, 24, 0.6); border: 1px solid #333; border-radius: 20px; display: flex; flex-direction: column; max-height: 100%; }}
                .notes-header {{ padding: 15px 20px; border-bottom: 1px solid #333; display: flex; justify-content: space-between; font-size: 10px; letter-spacing: 3px; color: {accent}; font-weight: bold; flex-shrink: 0; }}
                .notes-header button {{ background: transparent; border: 1px solid {accent}; color: {accent}; border-radius: 5px; cursor: pointer; padding: 3px 10px; font-size: 10px; }}

                /* СКРОЛЛ ТОЛЬКО ВНУТРИ СПИСКА */
                #notes-list {{ overflow-y: auto; padding: 15px; display: grid; grid-template-columns: 1fr 1fr; gap: 10px; }}
                #notes-list::-webkit-scrollbar {{ width: 0px; }} /* Скрываем полосу прокрутки */

                .note-item {{ background: #1c1d21; padding: 12px; border-radius: 10px; font-size: 14px; border-left: 4px solid {accent}; cursor: pointer; }}

                #ctx-menu {{ position: fixed; background: #2c2e33; border: 1px solid #444; border-radius: 8px; display: none; z-index: 1000; min-width: 150px; }}
                .ctx-item {{ padding: 12px; cursor: pointer; font-size: 13px; }}
                .ctx-item:hover {{ background: {accent}; }}
                .footer-info {{ position: fixed; bottom: 20px; color: #333; font-size: 12px; letter-spacing: 2px; }}
            </style>
        </head>
        <body>
            {clock_html}
            {title_html}

            <div class="search-container">
                <div class="search-box">
                    <input type="text" id="searchInput" placeholder="Поиск в системе..." onkeypress="handleSearch(event)">
                </div>
            </div>

            {notes_html}

            <div id="ctx-menu">
                <div class="ctx-item" onclick="editNote()">✏️ Редактировать</div>
                <div class="ctx-item" style="color: #ff5555;" onclick="deleteNoteWithConfirm()">🗑️ Удалить</div>
            </div>

            <div class="footer-info">SYSTEM ENGINE v3.0</div>

            <script>
                let notes = JSON.parse(localStorage.getItem('gor_notes') || '[]');
                let selectedNoteIndex = -1;

                function saveNotes() {{
                    localStorage.setItem('gor_notes', JSON.stringify(notes));
                    renderNotes();
                }}

                function addNote() {{
                    const text = prompt("О чем вы думаете?");
                    if (text) {{ notes.push(text); saveNotes(); }}
                }}

                function renderNotes() {{
                    const list = document.getElementById('notes-list');
                    if (!list) return; 
                    list.innerHTML = '';
                    notes.forEach((note, index) => {{
                        const div = document.createElement('div');
                        div.className = 'note-item';
                        div.innerText = note;
                        div.oncontextmenu = (e) => showMenu(e, index);
                        list.appendChild(div);
                    }});
                }}

                function showMenu(e, index) {{
                    e.preventDefault();
                    selectedNoteIndex = index;
                    const menu = document.getElementById('ctx-menu');
                    if (menu) {{
                        menu.style.display = 'block';
                        menu.style.left = e.pageX + 'px';
                        menu.style.top = e.pageY + 'px';
                    }}
                }}

                function deleteNoteWithConfirm() {{
                    if (confirm("Удалить заметку?")) {{ notes.splice(selectedNoteIndex, 1); saveNotes(); }}
                    hideMenu();
                }}

                function editNote() {{
                    const newText = prompt("Изменить:", notes[selectedNoteIndex]);
                    if (newText) {{ notes[selectedNoteIndex] = newText; saveNotes(); }}
                    hideMenu();
                }}

                function hideMenu() {{ 
                    const menu = document.getElementById('ctx-menu');
                    if(menu) menu.style.display = 'none'; 
                }}
                window.onclick = hideMenu;

                function updateTime() {{ 
                    const clockEl = document.getElementById('clock');
                    if (clockEl) {{
                        const now = new Date(); 
                        clockEl.innerText = now.getHours().toString().padStart(2, '0') + ":" + now.getMinutes().toString().padStart(2, '0'); 
                    }}
                }}
                setInterval(updateTime, 1000); updateTime();
                renderNotes();

                function handleSearch(event) {{
                    if (event.key === 'Enter') {{
                        window.location.href = '{search_url}' + encodeURIComponent(event.target.value);
                    }}
                }}
            </script>
        </body></html>""")
