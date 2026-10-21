document.addEventListener('DOMContentLoaded', () => {

    // --- ИНИЦИАЛИЗАЦИЯ И ЛОКАЛИЗАЦИЯ ---
    const savedLang = localStorage.getItem('gor_lang') || 'ru';
    applyLanguage(savedLang);
    initTheme();

    // Если мы на странице документации — рендерим её
    if (document.getElementById('docs-container')) {
        renderDocs();
    }

    // --- 1. Эффект частичек (Interactive Particle Network Background) ---
    createParticles();

    function createParticles() {
        const bg = document.querySelector('.glow-bg');
        if (!bg) return;

        const canvas = document.createElement('canvas');
        canvas.id = 'particle-canvas';
        canvas.style.position = 'fixed';
        canvas.style.top = '0';
        canvas.style.left = '0';
        canvas.style.width = '100%';
        canvas.style.height = '100%';
        canvas.style.pointerEvents = 'none';
        canvas.style.zIndex = '-1';
        document.body.appendChild(canvas);

        const ctx = canvas.getContext('2d');
        let particles = [];

        function resize() {
            canvas.width = window.innerWidth;
            canvas.height = window.innerHeight;
        }
        window.addEventListener('resize', resize);
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
    const cards = document.querySelectorAll('.feature-card, .dl-card, .doc-card');
    cards.forEach(card => {
        card.addEventListener('mousemove', (e) => {
            const rect = card.getBoundingClientRect();
            const x = e.clientX - rect.left;
            const y = e.clientY - rect.top;

            const centerX = rect.width / 2;
            const centerY = rect.height / 2;

            const rotateX = ((y - centerY) / centerY) * -8;
            const rotateY = ((x - centerX) / centerX) * 8;

            card.style.transform = `perspective(1000px) rotateX(${rotateX}deg) rotateY(${rotateY}deg) translateY(-5px)`;
        });

        card.addEventListener('mouseleave', () => {
            card.style.transform = 'perspective(1000px) rotateX(0deg) rotateY(0deg) translateY(0px)';
        });
    });

    // --- 3. Анимированный печатающийся текст (Typing Effect) ---
    const heroTitle = document.querySelector('.hero h1');
    if (heroTitle && !heroTitle.dataset.typed) {
        heroTitle.dataset.typed = "true";
        const words = ["ИГР И ВЕБ-СЕРФИНГА", "МОДДИНГА И АДДОНОВ", "СТРИМИНГА И ЛАУНЧЕРА"];
        let wordIndex = 0;
        let charIndex = 0;
        let isDeleting = false;

        const gradientSpan = heroTitle.querySelector('.gradient-text');
        if (gradientSpan) {
            function type() {
                const currentWord = words[wordIndex];
                if (isDeleting) {
                    gradientSpan.textContent = currentWord.substring(0, charIndex - 1);
                    charIndex--;
                } else {
                    gradientSpan.textContent = currentWord.substring(0, charIndex + 1);
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

                setTimeout(type, typeSpeed);
            }
            type();
        }
    }

    // --- 4. Уведомление о скачивании ---
    const dlButtons = document.querySelectorAll('.dl-card');
    dlButtons.forEach(btn => {
        btn.addEventListener('click', () => {
            showToast('🚀 Загрузка началась! Спасибо за скачивание GOR Launcher.');
        });
    });

    // --- 5. Кнопки копирования в блоках кода ---
    const termWindows = document.querySelectorAll('.terminal-window, .code-block');
    termWindows.forEach(win => {
        const copyBtn = document.createElement('button');
        copyBtn.className = 'copy-code-btn';
        copyBtn.innerHTML = '<i class="fa-regular fa-copy"></i> Копировать';
        copyBtn.style.position = 'absolute';
        copyBtn.style.right = '12px';
        copyBtn.style.top = '10px';
        copyBtn.style.background = 'rgba(255,255,255,0.08)';
        copyBtn.style.border = '1px solid rgba(255,255,255,0.1)';
        copyBtn.style.borderRadius = '6px';
        copyBtn.style.color = '#cbd5e1';
        copyBtn.style.fontSize = '12px';
        copyBtn.style.padding = '4px 10px';
        copyBtn.style.cursor = 'pointer';
        copyBtn.style.transition = '0.2s';

        win.style.position = 'relative';
        win.appendChild(copyBtn);

        copyBtn.addEventListener('click', () => {
            const codeText = win.innerText.replace('Копировать', '').trim();
            navigator.clipboard.writeText(codeText);
            copyBtn.innerHTML = '<i class="fa-solid fa-check"></i> Скопировано!';
            setTimeout(() => {
                copyBtn.innerHTML = '<i class="fa-regular fa-copy"></i> Копировать';
            }, 2000);
            showToast('Код скопирован в буфер обмена!');
        });
    });

    // --- 6. Пасхалка (Easter Egg - Наберите "GOR") ---
    let keySequence = [];
    const secretCode = ['g', 'o', 'r'];
    document.addEventListener('keydown', (e) => {
        keySequence.push(e.key.toLowerCase());
        keySequence = keySequence.slice(-3);
        if (keySequence.join('') === secretCode.join('')) {
            triggerEasterEgg();
        }
    });

    function triggerEasterEgg() {
        showToast('🎮 Режим разработчика разблокирован! (GOR Easter Egg)');
        document.body.style.filter = 'hue-rotate(90deg)';
        setTimeout(() => {
            document.body.style.filter = 'none';
        }, 5000);
    }
});

// ==========================================
// ЛОКАЛИЗАЦИЯ И СМЕНА ТЕМЫ
// ==========================================

const i18n = {
    ru: {
        langCode: "RU",
        navHome: "Главная",
        navDownload: "Скачать",
        navDocs: "Документация",
        navGet: "Загрузить",
        heroTitle: "ЭКОСИСТЕМА ДЛЯ <br><span class=\"gradient-text\">ИГР И ВЕБ-СЕРФИНГА</span>",
        heroDesc: "Управляй библиотекой игр, пользуйся встроенным браузером QtWebEngine и запускай кастомные аддоны в одном месте.",
        btnDownloadPage: "Перейти к скачиванию",
        btnDocsPage: "Инструкция",
        featuresTitle: "КЛЮЧЕВЫЕ <span class=\"gradient-text\">ВОЗМОЖНОСТИ</span>"
    },
    en: {
        langCode: "EN",
        navHome: "Home",
        navDownload: "Download",
        navDocs: "Docs",
        navGet: "Get Started",
        heroTitle: "ECOSYSTEM FOR <br><span class=\"gradient-text\">GAMING & WEB SURFING</span>",
        heroDesc: "Manage your game library, use the built-in QtWebEngine browser, and run custom add-ons all in one place.",
        btnDownloadPage: "Go to Downloads",
        btnDocsPage: "Documentation",
        featuresTitle: "KEY <span class=\"gradient-text\">FEATURES</span>"
    },
    am: {
        langCode: "AM",
        navHome: "Գլխավոր",
        navDownload: "Ներբեռնել",
        navDocs: "Փաստաթղթեր",
        navGet: "Սկսել",
        heroTitle: "ԷԿՈՀԱՄԱԿԱՐԳ <br><span class=\"gradient-text\">ԽԱՂԵՐԻ ԵՎ ՎԵԲԻ ՀԱՄԱՐ</span>",
        heroDesc: "Կառավարեք խաղերի գրադարանը, օգտագործեք ներկառուցված QtWebEngine կրծքավանդակը և գործարկեք հավելումները:",
        btnDownloadPage: "Անցնել ներբեռնմանը",
        btnDocsPage: "Ուղեցույց",
        featuresTitle: "ՀԻՄՆԱԿАՆ <span class=\"gradient-text\">ՀՆԱՐԱՎՈՐՈՒԹՅՈՒՆՆԵՐԸ</span>"
    }
};

function setLanguage(lang) {
    if (!i18n[lang]) return;
    localStorage.setItem('gor_lang', lang);
    applyLanguage(lang);
}

function applyLanguage(lang) {
    const data = i18n[lang];
    const currentLangSpan = document.getElementById('current-lang');
    if (currentLangSpan) currentLangSpan.innerText = data.langCode;

    const navLinks = document.querySelectorAll('.navbar nav a');
    if (navLinks.length >= 4) {
        navLinks[0].innerText = data.navHome;
        navLinks[1].innerText = data.navDownload;
        navLinks[2].innerText = data.navDocs;
        navLinks[3].innerText = data.navGet;
    }

    const heroH1 = document.querySelector('.hero h1');
    if (heroH1) heroH1.innerHTML = data.heroTitle;

    const heroDesc = document.querySelector('.hero-desc');
    if (heroDesc) heroDesc.innerText = data.heroDesc;

    const featuresTitle = document.querySelector('.section-title');
    if (featuresTitle && featuresTitle.innerHTML.includes('ВОЗМОЖНОСТИ')) {
        featuresTitle.innerHTML = data.featuresTitle;
    }
}

// Динамический рендеринг документации
function renderDocs() {
    if (typeof docsData === 'undefined') return;

    const container = document.getElementById('docs-container');
    const menu = document.getElementById('sidebar-menu');

    if (!container || !menu) return;

    container.innerHTML = '';
    menu.innerHTML = '';

    docsData.forEach(item => {
        // Меню
        const menuItem = document.createElement('li');
        menuItem.innerHTML = `<a href="#${item.id}" style="color: #cbd5e1; text-decoration: none; font-size: 13px;"><i class="fa-solid ${item.icon}" style="color: ${item.color}; margin-right: 8px;"></i> ${item.title}</a>`;
        menu.appendChild(menuItem);

        // Карточка
        const card = document.createElement('div');
        card.className = 'doc-card search-item';
        card.id = item.id;

        let content = `<h2 style="color: ${item.color}; font-size: 20px;"><i class="fa-solid ${item.icon}"></i> ${item.title}</h2>`;
        content += `<p style="color: #94a3b8; font-size: 14px; margin-top: 10px;">${item.desc}</p>`;

        if (item.code) {
            content += `<div class="code-block">${item.code}</div>`;
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
                    <div class="faq-item" style="border-top: 1px solid rgba(255,255,255,0.05); padding: 15px 0;">
                        <h4 style="color: #f8fafc; cursor: pointer; display: flex; justify-content: space-between;" onclick="toggleFaq(this)">
                            ${f.q} <i class="fa-solid fa-chevron-down" style="font-size: 12px; color: #64748b;"></i>
                        </h4>
                        <p style="color: #94a3b8; font-size: 13px; margin-top: 10px; display: none;" class="faq-ans">${f.a}</p>
                    </div>`;
            });
        }

        card.innerHTML = content;
        container.appendChild(card);
    });
}

// Переключение видимости ответа в FAQ
function toggleFaq(el) {
    const ans = el.nextElementSibling;
    if (ans) {
        ans.style.display = ans.style.display === 'none' ? 'block' : 'none';
    }
}

// Поиск по элементам документации
function filterDocs() {
    let input = document.getElementById('docs-search').value.toLowerCase();
    let items = document.getElementsByClassName('search-item');

    for (let i = 0; i < items.length; i++) {
        let text = items[i].innerText.toLowerCase();
        items[i].style.display = text.includes(input) ? "block" : "none";
    }
}

// Переключение темы
function initTheme() {
    const themeBtn = document.getElementById('theme-toggle');
    const themeIcon = document.getElementById('theme-icon');

    const savedTheme = localStorage.getItem('gor_theme') || 'dark';
    if (savedTheme === 'light') {
        document.body.classList.add('light-mode');
        if (themeIcon) themeIcon.className = 'fa-solid fa-moon';
    }

    if (themeBtn) {
        themeBtn.addEventListener('click', () => {
            document.body.classList.toggle('light-mode');
            const isLight = document.body.classList.contains('light-mode');
            localStorage.setItem('gor_theme', isLight ? 'light' : 'dark');

            if (themeIcon) {
                themeIcon.className = isLight ? 'fa-solid fa-moon' : 'fa-solid fa-sun';
            }
        });
    }
}

// Утилита Toast Уведомлений
function showToast(msg) {
    let toast = document.querySelector('.toast-notification');
    if (!toast) {
        toast = document.createElement('div');
        toast.className = 'toast-notification';
        document.body.appendChild(toast);
    }
    toast.innerText = msg;
    toast.classList.add('show');
    setTimeout(() => toast.classList.remove('show'), 3000);
}