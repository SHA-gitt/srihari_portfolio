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
    // Check for saved theme preference, defaulting to light mode
    const currentTheme = localStorage.getItem('theme') || 'light';
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
    
    // ── Welcome Screen & Tutorial ────────────────────────
    // Changed key to trigger tutorial again for the user
    const hasVisited = localStorage.getItem('portfolioVisited_v2');
    const welcomeScreen = document.getElementById('welcome-screen');
    const tutorialOverlay = document.getElementById('tutorial-overlay');
    const tutorialTooltip = document.getElementById('tutorial-tooltip');
    const tutorialCloseBtn = document.getElementById('tutorial-close-btn');
    
    // Find the first menu card to highlight
    const firstMenuCard = document.querySelector('.menu-card');

    if (!hasVisited) {
        // First visit
        if (welcomeScreen) {
            // After animation ends, hide welcome screen and show tutorial
            setTimeout(() => {
                welcomeScreen.classList.add('hidden');
                
                // Remove welcome screen from DOM after transition
                setTimeout(() => {
                    welcomeScreen.remove();
                    
                    // Show tutorial
                    if (firstMenuCard && tutorialOverlay && tutorialTooltip) {
                        // Scroll slightly so the card is visible
                        firstMenuCard.scrollIntoView({ behavior: 'smooth', block: 'center' });
                        
                        setTimeout(() => {
                            firstMenuCard.classList.add('tutorial-highlight');
                            tutorialOverlay.classList.add('active');
                            tutorialTooltip.classList.add('active');
                        }, 800);
                    }
                }, 800);
            }, 2500); // 2.5s for the animation
        }

        const closeTutorial = () => {
            if (firstMenuCard) firstMenuCard.classList.remove('tutorial-highlight');
            if (tutorialOverlay) tutorialOverlay.classList.remove('active');
            if (tutorialTooltip) tutorialTooltip.classList.remove('active');
            localStorage.setItem('portfolioVisited_v2', 'true');
        };

        if (tutorialCloseBtn) tutorialCloseBtn.addEventListener('click', closeTutorial);
        if (tutorialOverlay) tutorialOverlay.addEventListener('click', closeTutorial);

    } else {
        // Not first visit, instantly hide welcome and tutorial
        if (welcomeScreen) welcomeScreen.style.display = 'none';
        if (tutorialOverlay) tutorialOverlay.style.display = 'none';
        if (tutorialTooltip) tutorialTooltip.style.display = 'none';
    }

});

// ── Project Toggle Logic ──────────────────────────────
window.showProject = function (projectId) {
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

window.showMainMenu = function () {
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

// ── Private Visitor Tracking (Google Sheets) ─────────────────────────
// This function silently collects basic visitor details (Location, Browser, Page)
// and sends them to your private Google Sheet.
// It runs in the background and does not affect page performance.
function trackVisitor() {
    // Avoid spamming by only tracking once per session
    if (sessionStorage.getItem('visitor_tracked')) return;

    // 🔴 IMPORTANT: Replace this with your Google Apps Script Web App URL!
    const SCRIPT_URL = 'https://script.google.com/macros/s/AKfycbxCfSfiONttve2PwBHv5-TirEzlWyeIV82WJIP3NIPVLfEJLiyw_UKrDMDQNytZHgo2Cw/exec';

    if (SCRIPT_URL === 'YOUR_GOOGLE_SCRIPT_URL_HERE') {
        return; // Setup is incomplete, silent return.
    }

    // Fetch basic IP-based location data (Free tier)
    fetch('https://ipapi.co/json/')
        .then(response => response.json())
        .then(data => {
            let page = window.location.pathname.split('/').pop();
            if (!page || page === '') page = 'Home (index.html)';

            const city = data.city || 'Unknown';
            const region = data.region || 'Unknown';
            const country = data.country_name || 'Unknown';
            const ip = data.ip || 'Unknown';
            const browser = navigator.userAgent;
            const time = new Date().toLocaleString();

            // Prepare data for Google Sheets
            const formData = new FormData();
            formData.append('Time', time);
            formData.append('Page', page);
            formData.append('Location', `${city}, ${region}, ${country}`);
            formData.append('IP', ip);
            formData.append('Browser', browser);

            // Send silently to Google Sheets
            fetch(SCRIPT_URL, {
                method: 'POST',
                body: formData,
                mode: 'no-cors' // Required to prevent CORS errors on static sites
            })
                .then(() => {
                    sessionStorage.setItem('visitor_tracked', 'true');
                }).catch(err => {
                    // Fail silently
                });
        })
        .catch(err => {
            // Fail silently so user experience is never disturbed
        });
}

// Run tracker after a slight delay so it doesn't block critical rendering
setTimeout(trackVisitor, 3000);

