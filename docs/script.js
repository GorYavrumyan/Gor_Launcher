document.addEventListener("DOMContentLoaded", () => {

    // --- ИНИЦИАЛИЗАЦИЯ И ЛОКАЛИЗАЦИЯ ---
    const savedLang = localStorage.getItem("gor_lang") || "ru";
    applyLanguage(savedLang);
    initTheme();
    initLangDropdown();

    // Если мы на странице документации — рендерим её
    if (document.getElementById("docs-container")) {
        renderDocs();
    }

    // --- 1. Эффект частичек (Interactive Particle Network Background) ---
    createParticles();

    function createParticles() {
        const bg = document.querySelector(".glow-bg");
        if (!bg) return;

        const canvas = document.createElement("canvas");
        canvas.id = "particle-canvas";
        canvas.style.position = "fixed";
        canvas.style.top = "0";
        canvas.style.left = "0";
        canvas.style.width = "100%";
        canvas.style.height = "100%";
        canvas.style.pointerEvents = "none";
        canvas.style.zIndex = "-1";
        document.body.appendChild(canvas);

        const ctx = canvas.getContext("2d");
        let particles = [];

        function resize() {
            canvas.width = window.innerWidth;
            canvas.height = window.innerHeight;
        }
        window.addEventListener("resize", resize);
        resize();

        for (let i = 0; i < 40; i++) {
            particles.push({
                x: Math.random() * canvas.width,
                y: Math.random() * canvas.height,
                radius: Math.random() * 2 + 1,
                vx: (Math.random() - 0.5) * 0.6,
                vy: (Math.random() - 0.5) * 0.6,
                alpha: Math.random() * 0.5 + 0.2
            });
        }

        function animate() {
            ctx.clearRect(0, 0, canvas.width, canvas.height);
            particles.forEach(p => {
                p.x += p.vx;
                p.y += p.vy;

                if (p.x < 0 || p.x > canvas.width) p.vx *= -1;
                if (p.y < 0 || p.y > canvas.height) p.vy *= -1;

                ctx.beginPath();
                ctx.arc(p.x, p.y, p.radius, 0, Math.PI * 2);
                ctx.fillStyle = `rgba(168, 85, 247, ${p.alpha})`;
                ctx.fill();
            });
            requestAnimationFrame(animate);
        }
        animate();
    }

    // --- 2. 3D Tilt эффект для карточек возможностей ---
    const cards = document.querySelectorAll(".feature-card, .dl-card, .doc-card");
    cards.forEach(card => {
        card.addEventListener("mousemove", (e) => {
            const rect = card.getBoundingClientRect();
            const x = e.clientX - rect.left;
            const y = e.clientY - rect.top;

            const centerX = rect.width / 2;
            const centerY = rect.height / 2;

            const rotateX = ((y - centerY) / centerY) * -8;
            const rotateY = ((x - centerX) / centerX) * 8;

            card.style.transform = `perspective(1000px) rotateX(${rotateX}deg) rotateY(${rotateY}deg) translateY(-5px)`;
        });

        card.addEventListener("mouseleave", () => {
            card.style.transform = "perspective(1000px) rotateX(0deg) rotateY(0deg) translateY(0px)";
        });
    });

    // --- 3. Анимированный печатающийся текст (Typing Effect) ---
    initTypingEffect();

    // --- 4. Уведомление о скачивании ---
    const dlButtons = document.querySelectorAll(".dl-card, [data-download]");
    dlButtons.forEach(btn => {
        btn.addEventListener("click", () => {
            const currentLang = localStorage.getItem("gor_lang") || "ru";
            const msg = (i18n[currentLang] && i18n[currentLang].toastDownload) || i18n.ru.toastDownload;
            showToast(msg);
        });
    });

    // --- 5. Кнопки копирования в блоках кода ---
    initCopyButtons();

    // --- 6. Пасхалка (Easter Egg - Наберите "GOR") ---
    let keySequence = [];
    const secretCode = ["g", "o", "r"];
    document.addEventListener("keydown", (e) => {
        keySequence.push(e.key.toLowerCase());
        keySequence = keySequence.slice(-3);
        if (keySequence.join("") === secretCode.join("")) {
            triggerEasterEgg();
        }
    });

    function triggerEasterEgg() {
        showToast("🎮 Режим разработчика разблокирован! (GOR Easter Egg)");
        document.body.style.filter = "hue-rotate(90deg)";
        setTimeout(() => {
            document.body.style.filter = "none";
        }, 5000);
    }
});

let typingTimer = null;
function initTypingEffect() {
    const typedSpan = document.getElementById("typed-text");
    if (!typedSpan) return;

    if (typingTimer) clearTimeout(typingTimer);

    const currentLang = localStorage.getItem("gor_lang") || "ru";
    const words = (i18n[currentLang] && i18n[currentLang].heroWords) || i18n.ru.heroWords;

    let wordIndex = 0;
    let charIndex = 0;
    let isDeleting = false;

    function type() {
        const currentWord = words[wordIndex] || words[0];
        if (isDeleting) {
            typedSpan.textContent = currentWord.substring(0, charIndex - 1);
            charIndex--;
        } else {
            typedSpan.textContent = currentWord.substring(0, charIndex + 1);
            charIndex++;
        }

        let typeSpeed = isDeleting ? 40 : 80;

        if (!isDeleting && charIndex === currentWord.length) {
            typeSpeed = 2000;
            isDeleting = true;
        } else if (isDeleting && charIndex === 0) {
            isDeleting = false;
            wordIndex = (wordIndex + 1) % words.length;
            typeSpeed = 500;
        }

        typingTimer = setTimeout(type, typeSpeed);
    }
    type();
}

function initCopyButtons() {
    const termWindows = document.querySelectorAll(".terminal-window, .code-block");
    termWindows.forEach(win => {
        if (win.querySelector(".copy-code-btn")) return;
        const copyBtn = document.createElement("button");
        copyBtn.className = "copy-code-btn";
        const currentLang = localStorage.getItem("gor_lang") || "ru";
        const copyText = (i18n[currentLang] && i18n[currentLang].btnCopy) || "Копировать";
        copyBtn.innerHTML = `<i class="fa-regular fa-copy"></i> ${copyText}`;

        win.appendChild(copyBtn);

        copyBtn.addEventListener("click", () => {
            const codeText = win.innerText.replace(copyText, "").replace("Скопировано!", "").replace("Copied!", "").replace("Պատճենվեց!", "").trim();
            navigator.clipboard.writeText(codeText);
            const copiedText = (i18n[currentLang] && i18n[currentLang].btnCopied) || "Скопировано!";
            copyBtn.innerHTML = `<i class="fa-solid fa-check"></i> ${copiedText}`;
            setTimeout(() => {
                copyBtn.innerHTML = `<i class="fa-regular fa-copy"></i> ${copyText}`;
            }, 2000);
            const toastMsg = (i18n[currentLang] && i18n[currentLang].toastCopy) || "Код скопирован в буфер обмена!";
            showToast(toastMsg);
        });
    });
}

// ==========================================
// ЛОКАЛИЗАЦИЯ И СМЕНА ТЕМЫ
// ==========================================

const i18n = {
    ru: {
        langCode: "RU",
        titleIndex: "GOR Launcher — Игровой Центр Нового Поколения",
        titleDownload: "Скачать GOR Launcher — Windows & Linux",
        titleDocs: "Документация — GOR Launcher",
        navHome: "Главная",
        navDownload: "Загрузить",
        navDocs: "Документация",
        langTitle: "Язык",
        themeTitle: "Сменить тему",
        badge: "V1.0.0 Стабильная — Windows и Linux",
        heroPre: "ЭКОСИСТЕМА ДЛЯ",
        heroWords: ["ИГР И ВЕБ-СЕРФИНГА", "МОДДИНГА И АДДОНОВ", "СТРИМИНГА И ЛАУНЧЕРА"],
        heroDesc: "Управляй библиотекой игр, пользуйся встроенным браузером QtWebEngine и запускай кастомные аддоны в одном месте.",
        btnDownloadPage: "Перейти к скачиванию",
        btnDocsPage: "Инструкция",
        featuresTitle: `КЛЮЧЕВЫЕ <span class="gradient-text">ВОЗМОЖНОСТИ</span>`,
        f1Title: "Управление Библиотекой Игр",
        f1Desc: "Организация по группам и папкам, гибкие аргументы запуска, мониторинг процесса ProcessMonitor и удобные сортировки.",
        f2Title: "Встроенный Браузер GOR_Brauzer",
        f2Desc: "Chromium QWebEngine с вкладками, группами, AdBlock, оверлеем гайдов (Ctrl+Shift+K) и LAN UDP-рассылкой.",
        f3Title: "Мульти-Аккаунты и Изоляция",
        f3Desc: "Мгновенная смена профилей с изоляцией игр, сохранений и браузера через системные ссылки (NTFS/Symlinks).",
        f4Title: "Кастомизация и Студия Дизайна",
        f4Desc: "Встроенные QSS-темы, Theme Studio, кастомные цвета, фреймворк аддонов (калькулятор, монитор ресурсов, эффекты).",
        f5Title: "TV-Стриминг и Big Picture",
        f5Desc: "Полноэкранный режим Big Picture (F11) под геймпад и встроенный стриминг на ТВ через Sunshine + Moonlight.",
        f6Title: "Полная Мультиязычность",
        f6Desc: "Поддержка 4 языков из коробки: Русский, English, Español, Հայերեն (Armenian) с мгновенным переключением.",
        f7Title: "Авто-Обновлятор и Защита Данных",
        f7Desc: "Защищенная атомарная запись JSON с бэкапами (.bak), автообновление с GitHub и локальная офлайн-документация WEB/.",
        dlTitle: `ВЫБЕРИТЕ <span class="gradient-text">ВАШУ ПЛАТФОРМУ</span>`,
        dlWinTitle: "Скачать для Windows",
        dlWinSub: "64-bit | ZIP-архив с Python Runtime",
        dlLinuxTitle: "Скачать для Linux",
        dlLinuxSub: "TAR.GZ | Требует Python 3 + PyQt6",
        sysReqTitle: "СИСТЕМНЫЕ ТРЕБОВАНИЯ",
        docsTitle: `ПОЛНАЯ ДОКУМЕНТАЦИЯ И <span class="gradient-text">API РУКОВОДСТВО</span>`,
        docsSearchPh: "Поиск по документации (QWebChannel, Sunshine, PyQt6, JSON)...",
        docsSidebar: "Разделы",
        footer: "Работает на Python и PyQt6.",
        toastDownload: "🚀 Загрузка началась! Спасибо за скачивание GOR Launcher.",
        toastCopy: "Код скопирован в буфер обмена!",
        btnCopy: "Копировать",
        btnCopied: "Скопировано!"
    },
    en: {
        langCode: "EN",
        titleIndex: "GOR Launcher — Next-Gen Gaming Hub",
        titleDownload: "Download GOR Launcher — Windows & Linux",
        titleDocs: "Documentation — GOR Launcher",
        navHome: "Home",
        navDownload: "Get Started",
        navDocs: "Docs",
        langTitle: "Language",
        themeTitle: "Toggle theme",
        badge: "V1.0.0 Stable — Windows & Linux",
        heroPre: "ECOSYSTEM FOR",
        heroWords: ["GAMING & WEB SURFING", "MODDING & ADD-ONS", "STREAMING & LAUNCHER"],
        heroDesc: "Manage your game library, use the built-in QtWebEngine browser, and run custom add-ons all in one place.",
        btnDownloadPage: "Go to Downloads",
        btnDocsPage: "Documentation",
        featuresTitle: `KEY <span class="gradient-text">FEATURES</span>`,
        f1Title: "Game Library Management",
        f1Desc: "Group & folder organization, launch arguments, ProcessMonitor tracking, and smart sorting options.",
        f2Title: "Built-in GOR_Brauzer Engine",
        f2Desc: "Chromium QWebEngine with tab groups, AdBlock, guide overlay (Ctrl+Shift+K), and UDP LAN broadcasting.",
        f3Title: "Multi-Accounts & Isolation",
        f3Desc: "Instant profile switching isolating games, saves, and browser data via system links (NTFS/Symlinks).",
        f4Title: "Customization & Theme Studio",
        f4Desc: "Built-in QSS themes, Theme Studio, custom colors, and add-on framework (calculator, hardware monitor, particles).",
        f5Title: "TV Streaming & Big Picture",
        f5Desc: "Fullscreen Big Picture mode (F11) with gamepad support and TV streaming via Sunshine + Moonlight.",
        f6Title: "Complete Multilingual Engine",
        f6Desc: "Native support for 4 languages out of the box: Russian, English, Español, Հայերեն (Armenian).",
        f7Title: "Auto-Updater & Data Protection",
        f7Desc: "Safe atomic JSON writes with .bak backups, GitHub background updates, and local offline WEB/ documentation.",
        dlTitle: `CHOOSE <span class="gradient-text">YOUR PLATFORM</span>`,
        dlWinTitle: "Download for Windows",
        dlWinSub: "64-bit | ZIP archive with Python Runtime",
        dlLinuxTitle: "Download for Linux",
        dlLinuxSub: "TAR.GZ | Requires Python 3 + PyQt6",
        sysReqTitle: "SYSTEM REQUIREMENTS",
        docsTitle: `FULL DOCUMENTATION & <span class="gradient-text">API GUIDE</span>`,
        docsSearchPh: "Search documentation (QWebChannel, Sunshine, PyQt6, JSON)...",
        docsSidebar: "Sections",
        footer: "Powered by Python & PyQt6.",
        toastDownload: "🚀 Download started! Thank you for downloading GOR Launcher.",
        toastCopy: "Code copied to clipboard!",
        btnCopy: "Copy",
        btnCopied: "Copied!"
    },
    am: {
        langCode: "AM",
        titleIndex: "GOR Launcher — Նոր Սերնդի Խաղային Կենտրոն",
        titleDownload: "Ներբեռնել GOR Launcher — Windows & Linux",
        titleDocs: "Փաստաթղթեր — GOR Launcher",
        navHome: "Գլխավոր",
        navDownload: "Ներբեռնել",
        navDocs: "Փաստաթղթեր",
        langTitle: "Լեզու",
        themeTitle: "Փոխել թեման",
        badge: "V1.0.0 Կայուն — Windows և Linux",
        heroPre: "ԷԿՈՀԱՄԱԿԱՐԳ",
        heroWords: ["ԽԱՂԵՐԻ ԵՎ ՎԵԲԻ ՀԱՄԱՐ", "ՄՈԴԻՆԳԻ ԵՎ ՀԱՎԵԼՈՒՄՆԵՐԻ", "ՍՏՐԻՄԻՆԳԻ ԵՎ ԼԱՈՒՆՉԵՐԻ"],
        heroDesc: "Կառավարեք խաղերի գրադարանը, օգտագործեք ներկառուցված QtWebEngine զննարկիչը և գործարկեք հավելումները:",
        btnDownloadPage: "Անցնել ներբեռնմանը",
        btnDocsPage: "Ուղեցույց",
        featuresTitle: `ՀԻՄՆԱԿԱՆ <span class="gradient-text">ՀՆԱՐԱՎՈՐՈՒԹՅՈՒՆՆԵՐԸ</span>`,
        f1Title: "Խաղերի Գրադարանի Կառավարում",
        f1Desc: "Խմբավորում, գործարկման պարամետրեր, ProcessMonitor մոնիտորինգ և հարմար դասավորում:",
        f2Title: "Ներկառուցված GOR_Brauzer",
        f2Desc: "Chromium QWebEngine ներդիրների խմբերով, AdBlock-ով, Ctrl+Shift+K օվերլեյով և UDP LAN հեռարձակումով:",
        f3Title: "Բազմակի Հաշիվներ և Իզոլացում",
        f3Desc: "Պրոֆիլների ակնթարթային փոխում` խաղերի, պահպանումների և զննարկիչի իզոլացումով (NTFS/Symlinks):",
        f4Title: "Ձևավորում և Theme Studio",
        f4Desc: "Ներկառուցված QSS թեմաներ, Theme Studio, անհատական գույներ և հավելումների ֆրեյմվորք (հաշվիչ, մոնիտորինգ):",
        f5Title: "TV-Ստրիմինգ և Big Picture",
        f5Desc: "Լիաէկրան Big Picture ռեժիմ (F11) գեյմպադով և հեռարձակում TV-ին Sunshine + Moonlight-ի միջոցով:",
        f6Title: "Ամբողջական Բազմալեզվություն",
        f6Desc: "4 լեզուների աջակցություն՝ Ռուսերեն, English, Español, Հայերեն՝ ակնթարթային փոխումով:",
        f7Title: "Ավտո-Թարմացում և Տվյալների Պաշտպանություն",
        f7Desc: "Անվտանգ JSON պահպանում .bak պահուստային պատճեններով, GitHub թարմացումներ և օֆլայն WEB/ փաստաթղթեր:",
        dlTitle: `ԸՆՏՐԵՔ <span class="gradient-text">ՁԵՐ ՀԱՐԹԱԿԸ</span>`,
        dlWinTitle: "Ներբեռնել Windows-ի համար",
        dlWinSub: "64-bit | ZIP արխիվ Python-ով",
        dlLinuxTitle: "Ներբեռնել Linux-ի համար",
        dlLinuxSub: "TAR.GZ | Պահանջում է Python 3 + PyQt6",
        sysReqTitle: "ՀԱՄԱԿԱՐԳԱՅԻՆ ՊԱՀԱՆՋՆԵՐ",
        docsTitle: `ԱՄԲՈՂՋԱԿԱՆ ՓԱՍՏԱԹՂԹԵՐ ԵՎ <span class="gradient-text">API ՈՒՂԵՑՈՒՑ</span>`,
        docsSearchPh: "Փնտրել փաստաթղթերում (QWebChannel, Sunshine, PyQt6, JSON)...",
        docsSidebar: "Բաժիններ",
        footer: "Աշխատում է Python և PyQt6-ով:",
        toastDownload: "🚀 Ներբեռնումը սկսվեց: Շնորհակալություն GOR Launcher-ը ներբեռնելու համար:",
        toastCopy: "Կոդը պատճենվեց:",
        btnCopy: "Պատճենել",
        btnCopied: "Պատճենվեց!"
    }
};

function initLangDropdown() {
    const selector = document.querySelector(".lang-selector");
    const langBtn = document.getElementById("lang-btn");
    const dropdownBtns = document.querySelectorAll(".lang-dropdown button[data-lang]");

    if (selector && langBtn) {
        langBtn.addEventListener("click", (event) => {
            event.stopPropagation();
            selector.classList.toggle("open");
        });

        document.addEventListener("click", (event) => {
            if (!selector.contains(event.target)) selector.classList.remove("open");
        });

        document.addEventListener("keydown", (event) => {
            if (event.key === "Escape") selector.classList.remove("open");
        });
    }
    dropdownBtns.forEach(btn => {
        btn.addEventListener("click", () => {
            const lang = btn.getAttribute("data-lang");
            setLanguage(lang);
        });
    });
}

function setLanguage(lang) {
    if (!i18n[lang]) return;
    localStorage.setItem("gor_lang", lang);
    applyLanguage(lang);
    initTypingEffect();
    const selector = document.querySelector(".lang-selector");
    if (selector) selector.classList.remove("open");
}

function applyLanguage(lang) {
    const data = i18n[lang] || i18n.ru;
    document.documentElement.lang = lang === "am" ? "hy" : lang;

    const currentLangSpan = document.getElementById("current-lang");
    if (currentLangSpan) currentLangSpan.innerText = data.langCode;

    document.querySelectorAll(".lang-dropdown button[data-lang]").forEach(b => {
        if (b.getAttribute("data-lang") === lang) {
            b.classList.add("active");
        } else {
            b.classList.remove("active");
        }
    });

    if (document.querySelector("title[data-i18n=\"titleIndex\"]")) document.title = data.titleIndex;
    if (document.querySelector("title[data-i18n=\"titleDownload\"]")) document.title = data.titleDownload;
    if (document.querySelector("title[data-i18n=\"titleDocs\"]")) document.title = data.titleDocs;

    document.querySelectorAll("[data-i18n]").forEach(el => {
        const key = el.getAttribute("data-i18n");
        if (data[key] !== undefined) {
            el.innerHTML = data[key];
        }
    });

    document.querySelectorAll("[data-i18n-placeholder]").forEach(el => {
        const key = el.getAttribute("data-i18n-placeholder");
        if (data[key] !== undefined) {
            el.placeholder = data[key];
        }
    });

    document.querySelectorAll("[data-i18n-title]").forEach(el => {
        const key = el.getAttribute("data-i18n-title");
        if (data[key] !== undefined) {
            el.title = data[key];
        }
    });
}

function renderDocs() {
    if (typeof docsData === "undefined") return;

    const container = document.getElementById("docs-container");
    const menu = document.getElementById("sidebar-menu");

    if (!container || !menu) return;

    container.innerHTML = "";
    menu.innerHTML = "";

    docsData.forEach(item => {
        const menuItem = document.createElement("li");
        menuItem.innerHTML = `<a href="#${item.id}"><i class="fa-solid ${item.icon}" style="color: ${item.color}; margin-right: 8px;"></i> ${item.title}</a>`;
        menu.appendChild(menuItem);

        const card = document.createElement("div");
        card.className = "doc-card search-item";
        card.id = item.id;

        let content = `<h2 class="doc-title" style="color: ${item.color};"><i class="fa-solid ${item.icon}"></i> ${item.title}</h2>`;
        content += `<p class="doc-desc">${item.desc}</p>`;

        if (item.code) {
            content += `<div class="code-block">${escapeHtml(item.code)}</div>`;
        }

        if (item.table) {
            content += `<table class="param-table"><thead><tr>`;
            item.table.headers.forEach(h => content += `<th>${h}</th>`);
            content += `</tr></thead><tbody>`;
            item.table.rows.forEach(r => {
                content += `<tr><td><code>${r[0]}</code></td><td>${r[1]}</td><td>${r[2]}</td></tr>`;
            });
            content += `</tbody></table>`;
        }

        if (item.faq) {
            item.faq.forEach(f => {
                content += `
                    <div class="faq-item">
                        <h4 class="faq-q" onclick="toggleFaq(this)">
                            <span>${f.q}</span> <i class="fa-solid fa-chevron-down"></i>
                        </h4>
                        <p class="faq-ans">${f.a}</p>
                    </div>`;
            });
        }

        card.innerHTML = content;
        container.appendChild(card);
    });

    initCopyButtons();
}

function escapeHtml(text) {
    return text
        .replace(/&/g, "&amp;")
        .replace(/</g, "&lt;")
        .replace(/>/g, "&gt;");
}

function toggleFaq(el) {
    const parent = el.parentElement;
    const ans = el.nextElementSibling;
    if (ans) {
        const isShow = ans.classList.contains("show-faq");
        ans.classList.toggle("show-faq");
        if (parent) parent.classList.toggle("open", !isShow);
    }
}

function filterDocs() {
    let input = document.getElementById("docs-search").value.toLowerCase();
    let items = document.getElementsByClassName("search-item");

    for (let i = 0; i < items.length; i++) {
        let text = items[i].innerText.toLowerCase();
        items[i].style.display = text.includes(input) ? "block" : "none";
    }
}

function initTheme() {
    const themeBtn = document.getElementById("theme-toggle");
    const themeIcon = document.getElementById("theme-icon");

    const savedTheme = localStorage.getItem("gor_theme") || "dark";
    if (savedTheme === "light") {
        document.body.classList.add("light-mode");
        if (themeIcon) themeIcon.className = "fa-solid fa-moon";
    } else {
        document.body.classList.remove("light-mode");
        if (themeIcon) themeIcon.className = "fa-solid fa-sun";
    }

    if (themeBtn) {
        themeBtn.addEventListener("click", () => {
            document.body.classList.toggle("light-mode");
            const isLight = document.body.classList.contains("light-mode");
            localStorage.setItem("gor_theme", isLight ? "light" : "dark");

            if (themeIcon) {
                themeIcon.className = isLight ? "fa-solid fa-moon" : "fa-solid fa-sun";
            }
        });
    }
}

function showToast(msg) {
    let toast = document.querySelector(".toast-notification");
    if (!toast) {
        toast = document.createElement("div");
        toast.className = "toast-notification";
        document.body.appendChild(toast);
    }
    toast.innerText = msg;
    toast.classList.add("show");
    setTimeout(() => toast.classList.remove("show"), 3000);
}




var logo = document.getElementById("logo")
logo.addEventListener("click", function () {
    window.location.href = "index.html";
})