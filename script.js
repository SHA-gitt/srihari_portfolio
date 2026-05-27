// ═══════════════════════════════════════════════════════════
// Scroll-triggered reveal with staggered children
// ═══════════════════════════════════════════════════════════

document.addEventListener('DOMContentLoaded', () => {

    // Initialize Lucide icons
    if (typeof lucide !== 'undefined') lucide.createIcons();

    // ── Intersection Observer ──────────────────────────────
    const observer = new IntersectionObserver((entries) => {
        entries.forEach(entry => {
            if (entry.isIntersecting) {
                entry.target.classList.add('visible');
            }
        });
    }, {
        threshold: 0.1,
        rootMargin: '0px 0px -40px 0px'
    });

    document.querySelectorAll('.reveal').forEach(el => observer.observe(el));

    // ── Smooth scroll for nav links ───────────────────────
    document.querySelectorAll('a[href^="#"]').forEach(link => {
        link.addEventListener('click', e => {
            const id = link.getAttribute('href');
            const target = document.querySelector(id);
            if (target) {
                e.preventDefault();
                target.scrollIntoView({ behavior: 'smooth', block: 'start' });
            }
        });
    });

    // ── Navbar background on scroll ───────────────────────
    const nav = document.querySelector('.nav');
    if (nav) {
        window.addEventListener('scroll', () => {
            if (window.scrollY > 80) {
                nav.style.background = 'var(--nav-bg-scrolled)';
            } else {
                nav.style.background = 'var(--nav-bg)';
            }
        }, { passive: true });
    }

    // ── Flowchart node interactive pulse on hover ─────────
    document.querySelectorAll('.flow-node').forEach(node => {
        node.addEventListener('mouseenter', () => {
            node.style.transition = 'transform 0.25s ease, box-shadow 0.25s ease';
        });
    });

    // ── Theme Toggle ──────────────────────────────────────
    const themeToggleBtn = document.getElementById('theme-toggle');
    const prefersDarkScheme = window.matchMedia('(prefers-color-scheme: dark)');
    
    // Check for saved theme preference or use system preference
    const currentTheme = localStorage.getItem('theme') || (prefersDarkScheme.matches ? 'dark' : 'light');
    if (currentTheme === 'dark') {
        document.documentElement.setAttribute('data-theme', 'dark');
    }

    if (themeToggleBtn) {
        // Set initial icon
        themeToggleBtn.innerHTML = currentTheme === 'dark' ? '<i data-lucide="sun"></i>' : '<i data-lucide="moon"></i>';
        if (typeof lucide !== 'undefined') lucide.createIcons();
        
        themeToggleBtn.addEventListener('click', () => {
            const isDark = document.documentElement.getAttribute('data-theme') === 'dark';
            const newTheme = isDark ? 'light' : 'dark';
            document.documentElement.setAttribute('data-theme', newTheme);
            localStorage.setItem('theme', newTheme);
            
            themeToggleBtn.innerHTML = newTheme === 'dark' ? '<i data-lucide="sun"></i>' : '<i data-lucide="moon"></i>';
            if (typeof lucide !== 'undefined') lucide.createIcons();
        });
    }

    // ── Realtime Clock ────────────────────────────────────
    const clockEl = document.getElementById('realtime-clock');
    if (clockEl) {
        const updateClock = () => {
            const now = new Date();
            const dateStr = now.toLocaleDateString('en-US', { weekday: 'short', month: 'short', day: 'numeric' });
            const timeStr = now.toLocaleTimeString('en-US', { hour: '2-digit', minute: '2-digit', second: '2-digit' });
            clockEl.textContent = `${dateStr} • ${timeStr}`;
        };
        updateClock();
        setInterval(updateClock, 1000);
    }


});

// ── Project Toggle Logic ──────────────────────────────
window.showProject = function(projectId) {
    const mainMenu = document.getElementById('main-projects-menu');
    if (mainMenu) mainMenu.style.display = 'none';

    const projects = document.querySelectorAll('.project');
    projects.forEach(p => {
        p.style.display = 'none';
        p.classList.remove('visible'); // Reset reveal state
    });
    
    const target = document.getElementById(projectId);
    if (target) {
        target.style.display = 'block';
        // Allow a small delay before adding visible to trigger CSS transition
        setTimeout(() => target.classList.add('visible'), 50);
        const workSection = document.getElementById('work');
        if (workSection) {
            workSection.scrollIntoView({ behavior: 'smooth', block: 'start' });
        }
    }
};

window.showMainMenu = function() {
    const projects = document.querySelectorAll('.project');
    projects.forEach(p => {
        p.style.display = 'none';
    });

    const mainMenu = document.getElementById('main-projects-menu');
    if (mainMenu) {
        mainMenu.style.display = 'block';
        const workSection = document.getElementById('work');
        if (workSection) {
            workSection.scrollIntoView({ behavior: 'smooth', block: 'start' });
        }
    }
};
