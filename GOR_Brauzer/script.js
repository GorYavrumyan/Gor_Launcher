const defaultSites = [
    { name: 'Tumo Portal', url: 'https://tumo.org' },
    { name: 'GitHub', url: 'https://github.com' },
    { name: 'YouTube', url: 'https://youtube.com' },
    { name: 'Gemini AI', url: 'https://gemini.google.com' }
];

const defaultEngines = [
    { name: 'Google', url: 'https://www.google.com/search', param: 'q' },
    { name: 'DuckDuckGo', url: 'https://duckduckgo.com/', param: 'q' },
    { name: 'Yandex', url: 'https://yandex.ru/search/', param: 'text' }
];

let shortcuts = JSON.parse(localStorage.getItem('gor_shortcuts')) || defaultSites;
let engines = JSON.parse(localStorage.getItem('gor_custom_engines_list')) || defaultEngines;
let currentEngineIndex = parseInt(localStorage.getItem('gor_search_engine_idx')) || 0;
let currentTargetIndex = null;

const container = document.getElementById('shortcuts-container');
const ctxMenu = document.getElementById('context-menu');
const siteModal = document.getElementById('site-modal');
const iframeBg = document.getElementById('html-bg-container');

const osBrandLogo = document.getElementById('os-brand-logo');
const searchForm = document.getElementById('search-form');
const searchInput = document.getElementById('search-input');

// --- Хелперы для плавных анимаций модалок и меню ---
function showModal(el) {
    el.classList.add('modal-visible');
    requestAnimationFrame(() => {
        requestAnimationFrame(() => el.classList.add('modal-open'));
    });
}

function hideModal(el) {
    el.classList.remove('modal-open');
    setTimeout(() => el.classList.remove('modal-visible'), 260);
}

function showMenu(el) {
    el.classList.add('menu-visible');
    requestAnimationFrame(() => {
        requestAnimationFrame(() => el.classList.add('menu-open'));
    });
}

function hideMenu(el) {
    el.classList.remove('menu-open');
    setTimeout(() => el.classList.remove('menu-visible'), 180);
}

function getCleanDomain(url) {
    try {
        let cleanUrl = url.trim();
        if (!/^https?:\/\//i.test(cleanUrl)) cleanUrl = 'https://' + cleanUrl;
        return new URL(cleanUrl).hostname;
    } catch (e) { return ''; }
}

function renderShortcuts() {
    container.innerHTML = '';
    shortcuts.forEach((site, index) => {
        const card = document.createElement('a');
        card.className = 'shortcut-card';
        card.href = site.url;
        card.dataset.index = index;
        card.style.animationDelay = `${index * 45}ms`;

        const domain = getCleanDomain(site.url);
        const firstLetter = site.name ? site.name.charAt(0) : '?';

        if (domain) {
            const faviconUrl = `https://www.google.com/s2/favicons?sz=64&domain=${domain}`;
            card.innerHTML = `
                        <img class="shortcut-icon" src="${faviconUrl}" alt="" onerror="handleImgError(this, '${firstLetter}')">
                        <div class="shortcut-name">${site.name}</div>
                    `;
        } else {
            card.innerHTML = `
                        <div class="shortcut-letter-icon">${firstLetter}</div>
                        <div class="shortcut-name">${site.name}</div>
                    `;
        }

        card.addEventListener('contextmenu', (e) => {
            e.preventDefault();
            e.stopPropagation();
            currentTargetIndex = index;
            ctxMenu.style.top = `${e.pageY}px`;
            ctxMenu.style.left = `${e.pageX}px`;
            showMenu(ctxMenu);
        });

        container.appendChild(card);
    });

    const addCard = document.createElement('div');
    addCard.className = 'shortcut-card add-btn';
    addCard.innerHTML = '+';
    addCard.style.animationDelay = `${shortcuts.length * 45}ms`;
    addCard.addEventListener('click', () => openSiteModal(null));
    container.appendChild(addCard);
}

function handleImgError(img, letter) {
    const parent = img.parentNode;
    const letterDiv = document.createElement('div');
    letterDiv.className = 'shortcut-letter-icon';
    letterDiv.textContent = letter;
    parent.replaceChild(letterDiv, img);
}

function saveShortcuts() {
    localStorage.setItem('gor_shortcuts', JSON.stringify(shortcuts));
    renderShortcuts();
}

function openSiteModal(index) {
    hideMenu(ctxMenu);
    if (index !== null) {
        document.getElementById('modal-title').textContent = 'Редактировать ярлык';
        document.getElementById('site-name').value = shortcuts[index].name;
        document.getElementById('site-url').value = shortcuts[index].url;
        currentTargetIndex = index;
    } else {
        document.getElementById('modal-title').textContent = 'Добавить ярлык';
        document.getElementById('site-name').value = '';
        document.getElementById('site-url').value = '';
        currentTargetIndex = null;
    }
    showModal(siteModal);
}

document.getElementById('modal-save').addEventListener('click', () => {
    let name = document.getElementById('site-name').value.trim();
    let url = document.getElementById('site-url').value.trim();

    if (!name || !url) return alert('Заполните все поля!');
    if (!/^https?:\/\//i.test(url)) url = 'https://' + url;

    if (currentTargetIndex !== null) {
        shortcuts[currentTargetIndex] = { name, url };
    } else {
        shortcuts.push({ name, url });
    }
    saveShortcuts();
    hideModal(siteModal);
});

document.getElementById('modal-cancel').addEventListener('click', () => hideModal(siteModal));
document.getElementById('ctx-edit').addEventListener('click', () => openSiteModal(currentTargetIndex));
document.getElementById('ctx-delete').addEventListener('click', () => {
    hideMenu(ctxMenu);
    if (confirm(`Удалить ${shortcuts[currentTargetIndex].name}?`)) {
        shortcuts.splice(currentTargetIndex, 1);
        saveShortcuts();
    }
});

document.addEventListener('click', () => hideMenu(ctxMenu));

// --- Акцентный цвет (применение; редактирование теперь в Python) ---
function setSystemAccentColor(hexColor) {
    localStorage.setItem('gor_accent_color', hexColor);
    document.documentElement.style.setProperty('--accent-color', hexColor);

    // Превращаем HEX в RGBA для красивого мягкого свечения и прозрачных рамок
    const r = parseInt(hexColor.slice(1, 3), 16);
    const g = parseInt(hexColor.slice(3, 5), 16);
    const b = parseInt(hexColor.slice(5, 7), 16);

    document.documentElement.style.setProperty('--accent-glow', `rgba(${r}, ${g}, ${b}, 0.6)`);
    document.documentElement.style.setProperty('--accent-glow-muted', `rgba(${r}, ${g}, ${b}, 0.25)`);
    document.documentElement.style.setProperty('--accent-border', `rgba(${r}, ${g}, ${b}, 0.2)`);
}

function loadAccentColor() {
    const savedColor = localStorage.getItem('gor_accent_color') || '#4c6ef5';
    setSystemAccentColor(savedColor);
}

// --- Активная поисковая система (применение; редактирование теперь в Python) ---
function applySearchEngine() {
    if (currentEngineIndex >= engines.length) currentEngineIndex = 0;
    const currentEngine = engines[currentEngineIndex];
    searchForm.action = currentEngine.url;
    searchInput.name = currentEngine.param;
    searchInput.placeholder = `Поиск в ${currentEngine.name} или URL...`;
    localStorage.setItem('gor_search_engine_idx', currentEngineIndex);
}

searchForm.addEventListener('submit', (e) => {
    let value = searchInput.value.trim();
    if (!value) { e.preventDefault(); return; }
    const isUrl = /^(https?:\/\/)?([\w\d-]+\.)+\w{2,}(\/.*)?$/i.test(value);
    if (isUrl) {
        e.preventDefault();
        if (!/^https?:\/\//i.test(value)) value = 'https://' + value;
        window.location.href = value;
    }
});

// --- Название системы (применение; редактирование теперь в Python) ---
function applyBrandText() {
    const savedBrandText = localStorage.getItem('gor_brand_text') || 'GOR // OS';
    osBrandLogo.textContent = savedBrandText;
}

// --- Фон, блюр и кликабельность (применение; редактирование теперь в Python) ---
function updateBlurEffect() {
    const blurValue = localStorage.getItem('gor_bg_blur') || '0px';
    iframeBg.style.filter = `blur(${blurValue})`;
    if (localStorage.getItem('gor_custom_bg_type') !== 'html') {
        document.body.style.backdropFilter = `blur(${blurValue})`;
    } else {
        document.body.style.backdropFilter = 'none';
    }
}

function updateInteractivity() {
    const isInteractive = localStorage.getItem('gor_bg_interactive') === 'true';
    if (isInteractive && localStorage.getItem('gor_custom_bg_type') === 'html') {
        iframeBg.classList.add('interactive-backend');
    } else {
        iframeBg.classList.remove('interactive-backend');
    }
}

function applyBackground(bgData, type) {
    if (!bgData) return;
    if (type === 'html') {
        document.body.style.backgroundImage = 'none';
        iframeBg.style.display = 'block';
        if (iframeBg.src !== bgData) iframeBg.src = bgData;
    } else {
        iframeBg.style.display = 'none';
        iframeBg.src = '';
        document.body.style.backgroundImage = `url('${bgData}')`;
    }
    updateBlurEffect();
    updateInteractivity();
}

function updateClock() {
    const now = new Date();
    document.getElementById('clock').textContent = now.toTimeString().split(' ')[0];
    const days = ['Воскресенье', 'Понедельник', 'Вторник', 'Среда', 'Четверг', 'Пятница', 'Суббота'];
    const months = ['января', 'февраля', 'марта', 'апреля', 'мая', 'июня', 'июля', 'августа', 'сентября', 'октября', 'ноября', 'декабря'];
    document.getElementById('date').textContent = `${days[now.getDay()]}, ${now.getDate()} ${months[now.getMonth()]} ${now.getFullYear()}`;
}

// ------------------------------------------------------------------
// API ДЛЯ ПРИЁМА НАСТРОЕК ИЗ PYTHON (GOR_Brauzer/browser_widget.py)
// ------------------------------------------------------------------
// Шестерёнка "⚙ Настройки оформления" и модалка "bg-modal" (Система/Цвет/
// Фон/Поиск/Данные) убраны со страницы. Всё это теперь настраивается в
// нативном диалоге "Кастомизация" GOR Browser (⋮ -> Настройки браузера),
// а страница только ПРИМЕНЯЕТ то, что ей передают через
// page().runJavaScript("gorApplyNativeSettings(...)"). Логика применения
// (setSystemAccentColor/applyBackground/...) не потеряна - она просто
// больше не завязана на клики по кнопкам на странице.
window.gorApplyNativeSettings = function (s) {
    if (!s || typeof s !== 'object') return;

    if (typeof s.accent === 'string' && s.accent) {
        setSystemAccentColor(s.accent);
    }
    if (typeof s.brand === 'string') {
        const brand = s.brand || 'GOR // OS';
        localStorage.setItem('gor_brand_text', brand);
        osBrandLogo.textContent = brand;
    }
    if (Array.isArray(s.engines) && s.engines.length) {
        engines = s.engines;
        localStorage.setItem('gor_custom_engines_list', JSON.stringify(engines));
    }
    if (typeof s.engine_idx === 'number') {
        currentEngineIndex = s.engine_idx;
        applySearchEngine();
    }
    if (typeof s.bg_data === 'string') {
        localStorage.setItem('gor_custom_bg', s.bg_data);
        localStorage.setItem('gor_custom_bg_type', s.bg_type || 'image');
        applyBackground(s.bg_data, s.bg_type || 'image');
    }
    if (typeof s.bg_blur === 'number') {
        const val = s.bg_blur + 'px';
        localStorage.setItem('gor_bg_blur', val);
        updateBlurEffect();
    }
    if (typeof s.bg_interactive === 'boolean') {
        localStorage.setItem('gor_bg_interactive', s.bg_interactive);
        updateInteractivity();
    }
    if ('now_playing' in s) {
        applyNowPlaying(s.now_playing);
    }
    // "Виджеты на главной" (GeneralTab в browser_dialogs.py) - единая точка
    // истины для часов/заголовка/заметок. Для todo-widget синхронизируем
    // ТУ ЖЕ карту видимости (gor_widget_visibility), которой управляет и
    // чекбокс "🧩 Виджеты" прямо на странице - чтобы два способа включения
    // не конфликтовали и не перетирали друг друга.
    if (typeof s.show_clock === 'boolean') {
        const el = document.getElementById('clock-container');
        if (el) el.style.display = s.show_clock ? '' : 'none';
    }
    if (typeof s.show_title === 'boolean') {
        if (osBrandLogo) osBrandLogo.style.display = s.show_title ? '' : 'none';
    }
    if (typeof s.show_todo === 'boolean') {
        const vis = loadWidgetVisibility();
        vis['todo-widget'] = s.show_todo;
        saveWidgetVisibility(vis);
        applyWidgetVisibility();
        syncVisibilityCheckboxes();
    }
};

// "Сейчас в игре" (пункт ТЗ) - принимает {name, icon, wiki_url, forum_url,
// discord_url} из Python (GorLauncher → GORBrowser.load_data("now_playing"),
// см. browser_widget.py → _build_startpage_payload). null/undefined - игру
// ещё ни разу не запускали, блок просто остаётся скрытым.
function applyNowPlaying(data) {
    const card = document.getElementById('now-playing-card');
    if (!card) return;
    if (!data || !data.name) {
        card.style.display = 'none';
        return;
    }

    const icon = document.getElementById('now-playing-icon');
    const name = document.getElementById('now-playing-name');
    const links = document.getElementById('now-playing-links');

    icon.src = data.icon || '';
    icon.style.visibility = data.icon ? 'visible' : 'hidden';
    name.textContent = data.name;

    const q = encodeURIComponent(data.name);
    const linkDefs = [
        { emoji: '📖', title: 'Вики', url: data.wiki_url || `https://www.google.com/search?q=${q}+wiki` },
        { emoji: '💬', title: 'Форум', url: data.forum_url || `https://www.google.com/search?q=${q}+форум` },
        { emoji: '🎮', title: 'Discord', url: data.discord_url || `https://www.google.com/search?q=${q}+discord+server` },
    ];
    links.innerHTML = '';
    linkDefs.forEach(function (def) {
        if (!def.url) return;
        const a = document.createElement('a');
        a.href = def.url;
        a.title = def.title;
        a.textContent = def.emoji;
        links.appendChild(a);
    });

    card.style.display = 'flex';
}

// Полный сброс (вызывается из Python, кнопка "Сбросить всё" в CustomizationManager)
window.gorResetAll = function () {
    localStorage.clear();

    shortcuts = [...defaultSites];
    engines = [...defaultEngines];
    currentEngineIndex = 0;

    document.body.style.backgroundImage = 'none';
    iframeBg.style.display = 'none';
    iframeBg.src = '';

    setSystemAccentColor('#4c6ef5');
    applyBrandText();
    applySearchEngine();
    renderShortcuts();
    updateBlurEffect();
    updateInteractivity();

    todos = [];
    renderTodos();
    notesTextarea.value = '';
    initWeather();
};

// --- Резервная копия (вызывается из Python: "Данные" в CustomizationManager) ---
// GOR_STORAGE_KEYS перечисляет ВСЕ данные страницы, которые есть смысл
// сохранять/переносить: ярлыки, поисковики, оформление, виджеты, дела,
// заметки. Экспорт/импорт теперь идут через нативные диалоги "Сохранить
// файл"/"Открыть файл" в Python, а не через скачивание Blob на странице.
const GOR_STORAGE_KEYS = [
    'gor_shortcuts',
    'gor_custom_engines_list',
    'gor_search_engine_idx',
    'gor_accent_color',
    'gor_brand_text',
    'gor_custom_bg_type',
    'gor_custom_bg',
    'gor_bg_blur',
    'gor_bg_interactive',
    'gor_widget_visibility',
    'gor_custom_widgets',
    'gor_last_coords',
    'gor_todos',
    'gor_notes'
];

window.gorNativeExportBackup = function () {
    const data = {};
    GOR_STORAGE_KEYS.forEach(key => {
        const val = localStorage.getItem(key);
        if (val !== null) data[key] = val;
    });
    return JSON.stringify({ app: 'gor-os', version: 1, exportedAt: new Date().toISOString(), data });
};

window.gorNativeImportBackup = function (jsonStr) {
    let payload;
    try {
        payload = JSON.parse(jsonStr);
    } catch (e) {
        return 'bad-json';
    }
    if (!payload || payload.app !== 'gor-os' || !payload.data) {
        return 'bad-format';
    }
    GOR_STORAGE_KEYS.forEach(key => {
        if (payload.data[key] !== undefined) {
            localStorage.setItem(key, payload.data[key]);
        } else {
            localStorage.removeItem(key);
        }
    });
    location.reload();
    return 'ok';
};

// --- Вкладки в модалках (используется модалкой настройки виджетов) ---
document.querySelectorAll('.modal-tab').forEach(tabBtn => {
    tabBtn.addEventListener('click', () => {
        const scope = tabBtn.closest('.modal-content-tabbed');
        scope.querySelectorAll('.modal-tab').forEach(t => t.classList.remove('active'));
        scope.querySelectorAll('.tab-panel').forEach(p => p.classList.remove('active'));

        tabBtn.classList.add('active');
        document.getElementById(tabBtn.dataset.tab).classList.add('active');
    });
});


// --- Модалка управления виджетами (видимость + свои виджеты) ---
const widgetSettingsModal = document.getElementById('widget-settings-modal');
document.getElementById('widget-settings-btn').addEventListener('click', () => {
    syncVisibilityCheckboxes();
    renderCustomWidgetManageList();
    showModal(widgetSettingsModal);
});
document.getElementById('widget-settings-close').addEventListener('click', () => {
    hideModal(widgetSettingsModal);
});

// --- Видимость встроенных виджетов ---
function loadWidgetVisibility() {
    return JSON.parse(localStorage.getItem('gor_widget_visibility')) || {};
}

function saveWidgetVisibility(vis) {
    localStorage.setItem('gor_widget_visibility', JSON.stringify(vis));
}

function applyWidgetVisibility() {
    const vis = loadWidgetVisibility();
    document.querySelectorAll('.widget-vis-toggle').forEach(cb => {
        const widgetId = cb.dataset.widgetId;
        const isHidden = vis[widgetId] === false;
        const el = document.getElementById(widgetId);
        if (el) el.style.display = isHidden ? 'none' : '';
    });
}

function syncVisibilityCheckboxes() {
    const vis = loadWidgetVisibility();
    document.querySelectorAll('.widget-vis-toggle').forEach(cb => {
        cb.checked = vis[cb.dataset.widgetId] !== false;
    });
}

document.querySelectorAll('.widget-vis-toggle').forEach(cb => {
    cb.addEventListener('change', () => {
        const vis = loadWidgetVisibility();
        vis[cb.dataset.widgetId] = cb.checked;
        saveWidgetVisibility(vis);
        applyWidgetVisibility();
    });
});

// --- Свои виджеты (HTML/CSS/JS, рендерятся в изолированном iframe) ---
let customWidgets = JSON.parse(localStorage.getItem('gor_custom_widgets')) || [];
const customWidgetsContainer = document.getElementById('custom-widgets-container');
const customWidgetManageList = document.getElementById('custom-widgets-manage-list');

function saveCustomWidgets() {
    localStorage.setItem('gor_custom_widgets', JSON.stringify(customWidgets));
}

function renderCustomWidgetsInPanel() {
    customWidgetsContainer.innerHTML = '';
    customWidgets.forEach(widget => {
        const card = document.createElement('div');
        card.className = 'widget-card custom-widget-card';
        card.id = 'custom-' + widget.id;
        card.style.display = widget.visible === false ? 'none' : '';

        const header = document.createElement('div');
        header.className = 'widget-header';
        const isFileType = widget.type === 'file';
        const openLinkHtml = isFileType
            ? ''
            : `<a class="widget-refresh cw-open-link" href="${escapeHtml(widget.url || '')}" target="_blank" rel="noopener noreferrer" title="Открыть в новой вкладке">⤢</a>`;
        header.innerHTML = `
            <span class="widget-title">${escapeHtml(widget.name)}</span>
            ${openLinkHtml}
        `;

        const body = document.createElement('div');
        body.className = 'widget-body custom-widget-body';
        body.style.height = (widget.height || 260) + 'px';

        const isValidUrl = typeof widget.url === 'string' && /^https?:\/\/.+/i.test(widget.url);
        const hasFileContent = isFileType && typeof widget.content === 'string' && widget.content.length > 0;

        if (hasFileContent) {
            const iframe = document.createElement('iframe');
            iframe.className = 'custom-widget-frame';
            iframe.setAttribute('sandbox', 'allow-scripts allow-forms allow-modals allow-popups');
            iframe.srcdoc = widget.content;
            body.appendChild(iframe);
        } else if (!isFileType && isValidUrl) {
            const iframe = document.createElement('iframe');
            iframe.className = 'custom-widget-frame';
            iframe.src = widget.url;
            iframe.loading = 'lazy';
            iframe.referrerPolicy = 'no-referrer';
            body.appendChild(iframe);
        } else {
            const warning = document.createElement('div');
            warning.className = 'cw-broken-url';
            warning.innerHTML = `⚠️ ${isFileType ? 'Файл не загружен.' : 'Ссылка не указана или некорректна.'}<br>Открой ⚙ виджетов → «Видимость» → ✎ у «${escapeHtml(widget.name)}», чтобы её исправить.`;
            body.appendChild(warning);
        }

        card.appendChild(header);
        card.appendChild(body);
        customWidgetsContainer.appendChild(card);

        if ((hasFileContent || isValidUrl) && typeof ResizeObserver !== 'undefined') {
            let resizeSaveTimeout = null;
            const observer = new ResizeObserver(entries => {
                const newHeight = Math.round(entries[0].contentRect.height);
                if (Math.abs(newHeight - (widget.height || 260)) < 2) return;
                clearTimeout(resizeSaveTimeout);
                resizeSaveTimeout = setTimeout(() => {
                    widget.height = newHeight;
                    saveCustomWidgets();
                }, 400);
            });
            observer.observe(body);
        }
    });
}

function renderCustomWidgetManageList() {
    customWidgetManageList.innerHTML = '';
    if (customWidgets.length === 0) {
        customWidgetManageList.innerHTML = '<div class="widget-empty-hint">Пока нет своих виджетов</div>';
        return;
    }
    customWidgets.forEach(widget => {
        const row = document.createElement('div');
        row.className = 'custom-widget-manage-item';

        const name = document.createElement('span');
        name.className = 'cw-name';
        name.textContent = widget.name;
        name.title = widget.type === 'file' ? `Файл: ${widget.fileName || 'без имени'}` : (widget.url || '');

        const actions = document.createElement('div');
        actions.className = 'cw-actions';

        const visToggle = document.createElement('input');
        visToggle.type = 'checkbox';
        visToggle.className = 'widget-vis-toggle';
        visToggle.checked = widget.visible !== false;
        visToggle.title = 'Показывать виджет';
        visToggle.addEventListener('change', () => {
            widget.visible = visToggle.checked;
            saveCustomWidgets();
            renderCustomWidgetsInPanel();
        });

        const editBtn = document.createElement('button');
        editBtn.className = 'cw-delete-btn';
        editBtn.textContent = '✎';
        editBtn.title = 'Редактировать виджет';
        editBtn.addEventListener('click', () => startEditingCustomWidget(widget.id));

        const delBtn = document.createElement('button');
        delBtn.className = 'cw-delete-btn';
        delBtn.textContent = '✕';
        delBtn.title = 'Удалить виджет';
        delBtn.addEventListener('click', () => {
            if (confirm(`Удалить виджет "${widget.name}"?`)) {
                customWidgets = customWidgets.filter(w => w.id !== widget.id);
                saveCustomWidgets();
                renderCustomWidgetsInPanel();
                renderCustomWidgetManageList();
                if (editingCustomWidgetId === widget.id) cancelEditingCustomWidget();
            }
        });

        actions.appendChild(visToggle);
        actions.appendChild(editBtn);
        actions.appendChild(delBtn);
        row.appendChild(name);
        row.appendChild(actions);
        customWidgetManageList.appendChild(row);
    });
}

function escapeHtml(str) {
    const div = document.createElement('div');
    div.textContent = str;
    return div.innerHTML;
}

let editingCustomWidgetId = null;
let pendingFileContent = null;
let pendingFileName = null;
const cwNameInput = document.getElementById('custom-widget-name');
const cwUrlInput = document.getElementById('custom-widget-url');
const cwAddBtn = document.getElementById('custom-widget-add-btn');
const cwCancelEditBtn = document.getElementById('custom-widget-cancel-edit-btn');
const cwFileBtn = document.getElementById('custom-widget-file-btn');
const cwFileInput = document.getElementById('custom-widget-file-input');
const cwFileNameLabel = document.getElementById('custom-widget-file-name');

cwFileBtn.addEventListener('click', () => cwFileInput.click());
cwFileInput.addEventListener('change', () => {
    const file = cwFileInput.files[0];
    if (!file) return;
    const reader = new FileReader();
    reader.onload = () => {
        pendingFileContent = reader.result;
        pendingFileName = file.name;
        cwFileNameLabel.textContent = `✓ ${file.name}`;
    };
    reader.onerror = () => {
        alert('Не удалось прочитать файл.');
    };
    reader.readAsText(file);
});

function startEditingCustomWidget(id) {
    const widget = customWidgets.find(w => w.id === id);
    if (!widget) return;
    editingCustomWidgetId = id;
    cwNameInput.value = widget.name;
    cwUrlInput.value = widget.type === 'file' ? '' : (widget.url || '');
    pendingFileContent = null;
    pendingFileName = null;
    cwFileInput.value = '';
    cwFileNameLabel.textContent = widget.type === 'file' ? `Текущий файл: ${widget.fileName || 'без имени'} (выбери новый, чтобы заменить)` : '';
    cwAddBtn.textContent = '💾 Сохранить изменения';
    cwCancelEditBtn.style.display = '';

    document.querySelectorAll('.modal-tab').forEach(t => t.classList.remove('active'));
    document.querySelectorAll('.tab-panel').forEach(p => p.classList.remove('active'));
    document.querySelector('[data-tab="wtab-create"]').classList.add('active');
    document.getElementById('wtab-create').classList.add('active');
    cwNameInput.focus();
}

function cancelEditingCustomWidget() {
    editingCustomWidgetId = null;
    cwNameInput.value = '';
    cwUrlInput.value = '';
    pendingFileContent = null;
    pendingFileName = null;
    cwFileInput.value = '';
    cwFileNameLabel.textContent = '';
    cwAddBtn.textContent = '+ Добавить виджет';
    cwCancelEditBtn.style.display = 'none';
}

cwCancelEditBtn.addEventListener('click', cancelEditingCustomWidget);

document.getElementById('custom-widget-add-btn').addEventListener('click', () => {
    const nameInput = cwNameInput;
    const urlInput = cwUrlInput;

    const name = nameInput.value.trim();
    if (!name) return alert('Введите название виджета!');

    let url = urlInput.value.trim();
    const usingFile = !!pendingFileContent;

    if (!usingFile) {
        if (!url) return alert('Введите URL сайта или выберите HTML-файл!');
        if (!/^https?:\/\//i.test(url)) url = 'https://' + url;
        if (!/^https?:\/\/[^\s/$.?#].[^\s]*$/i.test(url)) {
            return alert('Похоже, это не настоящий адрес сайта. Введите, например: https://example.com');
        }
    }

    if (editingCustomWidgetId) {
        const widget = customWidgets.find(w => w.id === editingCustomWidgetId);
        if (widget) {
            widget.name = name;
            if (usingFile) {
                widget.type = 'file';
                widget.content = pendingFileContent;
                widget.fileName = pendingFileName;
                delete widget.url;
            } else if (url) {
                widget.type = 'url';
                widget.url = url;
                delete widget.content;
                delete widget.fileName;
            }
        }
    } else {
        customWidgets.push(usingFile ? {
            id: 'w' + Date.now(),
            name,
            type: 'file',
            content: pendingFileContent,
            fileName: pendingFileName,
            height: 260,
            visible: true
        } : {
            id: 'w' + Date.now(),
            name,
            type: 'url',
            url,
            height: 260,
            visible: true
        });
    }
    saveCustomWidgets();
    renderCustomWidgetsInPanel();
    renderCustomWidgetManageList();
    cancelEditingCustomWidget();
});

// ============ ВИДЖЕТЫ ============

// --- Открытие/закрытие панели ---
const widgetsPanel = document.getElementById('widgets-panel');
document.getElementById('open-widgets-panel').addEventListener('click', () => {
    widgetsPanel.classList.add('open');
});
document.getElementById('widgets-close').addEventListener('click', () => {
    widgetsPanel.classList.remove('open');
});

// --- Погода (Open-Meteo, без ключа API) ---
const weatherBody = document.getElementById('weather-body');

const weatherCodeMap = {
    0: ['☀️', 'Ясно'],
    1: ['🌤️', 'Преимущественно ясно'],
    2: ['⛅', 'Переменная облачность'],
    3: ['☁️', 'Пасмурно'],
    45: ['🌫️', 'Туман'],
    48: ['🌫️', 'Изморозь'],
    51: ['🌦️', 'Лёгкая морось'],
    53: ['🌦️', 'Морось'],
    55: ['🌧️', 'Сильная морось'],
    61: ['🌧️', 'Небольшой дождь'],
    63: ['🌧️', 'Дождь'],
    65: ['🌧️', 'Сильный дождь'],
    71: ['🌨️', 'Небольшой снег'],
    73: ['🌨️', 'Снег'],
    75: ['❄️', 'Сильный снег'],
    77: ['❄️', 'Снежная крупа'],
    80: ['🌦️', 'Ливень'],
    81: ['🌧️', 'Сильный ливень'],
    82: ['⛈️', 'Очень сильный ливень'],
    85: ['🌨️', 'Снегопад'],
    86: ['❄️', 'Сильный снегопад'],
    95: ['⛈️', 'Гроза'],
    96: ['⛈️', 'Гроза с градом'],
    99: ['⛈️', 'Сильная гроза с градом']
};

function renderWeatherError(msg) {
    weatherBody.innerHTML = `<div class="weather-status">${msg}</div>`;
}

async function fetchWeather(lat, lon) {
    weatherBody.innerHTML = `<div class="weather-status">Загружаем погоду…</div>`;
    try {
        const url = `https://api.open-meteo.com/v1/forecast?latitude=${lat}&longitude=${lon}&current=temperature_2m,weather_code,relative_humidity_2m,wind_speed_10m&timezone=auto`;
        const res = await fetch(url);
        if (!res.ok) throw new Error('bad response');
        const data = await res.json();
        const cur = data.current;
        const [icon, desc] = weatherCodeMap[cur.weather_code] || ['🌡️', 'Неизвестно'];
        const temp = Math.round(cur.temperature_2m);

        weatherBody.innerHTML = `
            <div class="weather-main">
                <div class="weather-icon">${icon}</div>
                <div>
                    <div class="weather-temp">${temp}°C</div>
                    <div class="weather-desc">${desc}</div>
                </div>
            </div>
            <div class="weather-meta">Влажность: ${cur.relative_humidity_2m}% · Ветер: ${Math.round(cur.wind_speed_10m)} км/ч</div>
        `;
        localStorage.setItem('gor_last_coords', JSON.stringify({ lat, lon }));
    } catch (err) {
        renderWeatherError('Не удалось загрузить погоду. Попробуйте обновить.');
    }
}

function initWeather() {
    if (!navigator.geolocation) {
        renderWeatherError('Геолокация недоступна в этом браузере.');
        return;
    }
    navigator.geolocation.getCurrentPosition(
        (pos) => fetchWeather(pos.coords.latitude, pos.coords.longitude),
        () => {
            const cached = localStorage.getItem('gor_last_coords');
            if (cached) {
                const { lat, lon } = JSON.parse(cached);
                fetchWeather(lat, lon);
            } else {
                renderWeatherError('Доступ к геолокации не разрешён. Разрешите доступ, чтобы видеть погоду.');
            }
        },
        { timeout: 8000 }
    );
}

document.getElementById('weather-refresh').addEventListener('click', initWeather);

// --- Калькулятор ---
const calcDisplay = document.getElementById('calc-display');
let calcCurrent = '0';
let calcPrevious = null;
let calcOperator = null;
let calcResetOnNextInput = false;

function calcUpdateDisplay() {
    calcDisplay.textContent = calcCurrent.replace('.', ',');
}

function calcInputNumber(num) {
    if (calcResetOnNextInput) {
        calcCurrent = '0';
        calcResetOnNextInput = false;
    }
    if (calcCurrent === '0' && num !== '.') {
        calcCurrent = num;
    } else {
        if (calcCurrent.length >= 14) return;
        calcCurrent += num;
    }
    calcUpdateDisplay();
}

function calcInputDecimal() {
    if (calcResetOnNextInput) {
        calcCurrent = '0';
        calcResetOnNextInput = false;
    }
    if (!calcCurrent.includes('.')) {
        calcCurrent += '.';
        calcUpdateDisplay();
    }
}

function calcCompute(a, b, op) {
    switch (op) {
        case '+': return a + b;
        case '-': return a - b;
        case '*': return a * b;
        case '/': return b === 0 ? NaN : a / b;
        default: return b;
    }
}

function calcFormatResult(num) {
    if (isNaN(num)) return 'Ошибка';
    let str = String(Math.round(num * 1e10) / 1e10);
    if (str.length > 14) str = num.toExponential(6);
    return str;
}

function calcHandleOperator(op) {
    const inputValue = parseFloat(calcCurrent);
    if (calcOperator && !calcResetOnNextInput) {
        const result = calcCompute(calcPrevious, inputValue, calcOperator);
        calcCurrent = calcFormatResult(result);
        calcPrevious = parseFloat(calcCurrent);
        calcUpdateDisplay();
    } else {
        calcPrevious = inputValue;
    }
    calcOperator = op;
    calcResetOnNextInput = true;
}

function calcHandleEquals() {
    if (calcOperator === null || calcPrevious === null) return;
    const inputValue = parseFloat(calcCurrent);
    const result = calcCompute(calcPrevious, inputValue, calcOperator);
    calcCurrent = calcFormatResult(result);
    calcOperator = null;
    calcPrevious = null;
    calcResetOnNextInput = true;
    calcUpdateDisplay();
}

function calcClearAll() {
    calcCurrent = '0';
    calcPrevious = null;
    calcOperator = null;
    calcResetOnNextInput = false;
    calcUpdateDisplay();
}

function calcToggleSign() {
    if (calcCurrent === '0') return;
    calcCurrent = calcCurrent.startsWith('-') ? calcCurrent.slice(1) : '-' + calcCurrent;
    calcUpdateDisplay();
}

function calcPercent() {
    calcCurrent = calcFormatResult(parseFloat(calcCurrent) / 100);
    calcUpdateDisplay();
}

document.querySelectorAll('#calculator-widget .calc-btn').forEach(btn => {
    btn.addEventListener('click', () => {
        if (btn.dataset.num !== undefined) {
            calcInputNumber(btn.dataset.num);
        } else if (btn.dataset.op) {
            calcHandleOperator(btn.dataset.op);
        } else if (btn.dataset.action === 'decimal') {
            calcInputDecimal();
        } else if (btn.dataset.action === 'clear') {
            calcClearAll();
        } else if (btn.dataset.action === 'sign') {
            calcToggleSign();
        } else if (btn.dataset.action === 'percent') {
            calcPercent();
        } else if (btn.dataset.action === 'equals') {
            calcHandleEquals();
        }
    });
});

document.getElementById('calc-clear-all').addEventListener('click', calcClearAll);

// --- Виджет "Система" ---
const systemInfoGrid = document.getElementById('system-info-grid');
const pageLoadTimestamp = Date.now();
let cachedBatteryManager = null;

function detectOS() {
    const ua = navigator.userAgent;
    if (/Windows/i.test(ua)) return 'Windows';
    if (/Mac OS X/i.test(ua)) return 'macOS';
    if (/Android/i.test(ua)) return 'Android';
    if (/iPhone|iPad|iPod/i.test(ua)) return 'iOS';
    if (/Linux/i.test(ua)) return 'Linux';
    return 'Неизвестно';
}

function detectBrowser() {
    const ua = navigator.userAgent;
    if (/Firefox\//i.test(ua)) return 'Firefox';
    if (/Edg\//i.test(ua)) return 'Edge';
    if (/OPR\/|Opera/i.test(ua)) return 'Opera';
    if (/Chrome\//i.test(ua)) return 'Chrome';
    if (/Safari\//i.test(ua)) return 'Safari';
    return 'Неизвестно';
}

function formatUptime(ms) {
    const totalSec = Math.floor(ms / 1000);
    const h = String(Math.floor(totalSec / 3600)).padStart(2, '0');
    const m = String(Math.floor((totalSec % 3600) / 60)).padStart(2, '0');
    const s = String(totalSec % 60).padStart(2, '0');
    return `${h}:${m}:${s}`;
}

function siRow(label, value, extraHtml) {
    return `<div class="system-info-row">
                <span class="si-label">${label}</span>
                <span class="si-value">${value}${extraHtml || ''}</span>
            </div>`;
}

function renderSystemWidget() {
    const uptime = formatUptime(Date.now() - pageLoadTimestamp);
    const resolution = `${screen.width}×${screen.height}`;
    const os = detectOS();
    const browser = detectBrowser();

    let batteryHtml = siRow('🔋 Батарея', 'Недоступно');
    if (cachedBatteryManager) {
        const pct = Math.round(cachedBatteryManager.level * 100);
        const chargingIcon = cachedBatteryManager.charging ? ' ⚡' : '';
        batteryHtml = `<div class="system-info-row">
                <span class="si-label">🔋 Батарея</span>
                <span class="si-value">${pct}%${chargingIcon}
                    <div class="si-bar-wrap"><div class="si-bar" style="width:${pct}%;"></div></div>
                </span>
            </div>`;
    }

    let memoryHtml = siRow('🧠 Память вкладки', 'Недоступно');
    if (performance.memory) {
        const usedMb = Math.round(performance.memory.usedJSHeapSize / 1048576);
        const limitMb = Math.round(performance.memory.jsHeapSizeLimit / 1048576);
        const pct = Math.min(100, Math.round((usedMb / limitMb) * 100));
        memoryHtml = `<div class="system-info-row">
                <span class="si-label">🧠 Память вкладки</span>
                <span class="si-value">${usedMb} МБ
                    <div class="si-bar-wrap"><div class="si-bar" style="width:${pct}%;"></div></div>
                </span>
            </div>`;
    }

    systemInfoGrid.innerHTML =
        siRow('💻 ОС', os) +
        siRow('🌐 Браузер', browser) +
        siRow('🖥️ Экран', resolution) +
        batteryHtml +
        memoryHtml +
        siRow('⏱️ Аптайм страницы', uptime) +
        siRow('📶 Сеть', navigator.onLine ? 'Онлайн' : 'Офлайн');
}

function initSystemWidget() {
    if (navigator.getBattery) {
        navigator.getBattery().then(battery => {
            cachedBatteryManager = battery;
            renderSystemWidget();
            battery.addEventListener('levelchange', renderSystemWidget);
            battery.addEventListener('chargingchange', renderSystemWidget);
        }).catch(() => renderSystemWidget());
    } else {
        renderSystemWidget();
    }
    setInterval(renderSystemWidget, 1000);
}

document.getElementById('system-refresh').addEventListener('click', renderSystemWidget);
window.addEventListener('online', renderSystemWidget);
window.addEventListener('offline', renderSystemWidget);

initSystemWidget();

// --- Дела (Todo) ---
let todos = JSON.parse(localStorage.getItem('gor_todos')) || [];
const todoList = document.getElementById('todo-list');
const todoForm = document.getElementById('todo-form');
const todoInput = document.getElementById('todo-input');

function saveTodos() {
    localStorage.setItem('gor_todos', JSON.stringify(todos));
}

function renderTodos() {
    todoList.innerHTML = '';
    if (todos.length === 0) {
        todoList.innerHTML = '<div class="todo-empty">Пока нет задач</div>';
        return;
    }
    todos.forEach((todo, index) => {
        const item = document.createElement('div');
        item.className = 'todo-item' + (todo.done ? ' done' : '');
        item.style.animationDelay = `${index * 30}ms`;

        const checkbox = document.createElement('input');
        checkbox.type = 'checkbox';
        checkbox.checked = todo.done;
        checkbox.addEventListener('change', () => {
            todos[index].done = checkbox.checked;
            saveTodos();
            renderTodos();
        });

        const text = document.createElement('span');
        text.className = 'todo-text';
        text.textContent = todo.text;
        text.addEventListener('click', () => {
            checkbox.checked = !checkbox.checked;
            todos[index].done = checkbox.checked;
            saveTodos();
            renderTodos();
        });

        const delBtn = document.createElement('button');
        delBtn.className = 'todo-delete';
        delBtn.textContent = '✕';
        delBtn.addEventListener('click', () => {
            item.classList.add('todo-removing');
            setTimeout(() => {
                todos.splice(index, 1);
                saveTodos();
                renderTodos();
            }, 180);
        });

        item.appendChild(checkbox);
        item.appendChild(text);
        item.appendChild(delBtn);
        todoList.appendChild(item);
    });
}

todoForm.addEventListener('submit', (e) => {
    e.preventDefault();
    const val = todoInput.value.trim();
    if (!val) return;
    todos.push({ text: val, done: false });
    saveTodos();
    renderTodos();
    todoInput.value = '';
});

// --- Заметки (автосохранение) ---
const notesTextarea = document.getElementById('notes-textarea');
const notesSaveHint = document.getElementById('notes-save-hint');
let notesSaveTimeout = null;

notesTextarea.value = localStorage.getItem('gor_notes') || '';

notesTextarea.addEventListener('input', () => {
    clearTimeout(notesSaveTimeout);
    notesSaveTimeout = setTimeout(() => {
        localStorage.setItem('gor_notes', notesTextarea.value);
        notesSaveHint.textContent = 'Сохранено';
        notesSaveHint.classList.add('show');
        setTimeout(() => notesSaveHint.classList.remove('show'), 1200);
    }, 500);
});

// Инициализация виджетов
renderTodos();
initWeather();
applyWidgetVisibility();
renderCustomWidgetsInPanel();

// Запуск
setInterval(updateClock, 1000);
updateClock();
renderShortcuts();
applySearchEngine();
applyBrandText();
loadAccentColor();
updateBlurEffect();
applyBackground(localStorage.getItem('gor_custom_bg'), localStorage.getItem('gor_custom_bg_type'));