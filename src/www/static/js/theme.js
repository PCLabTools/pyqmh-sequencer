(function () {
    const STORAGE_KEY = 'pyqmh-theme';
    const OPTIONS = ['light', 'dark', 'system'];
    const media = window.matchMedia('(prefers-color-scheme: dark)');

    function getStoredMode() {
        const stored = localStorage.getItem(STORAGE_KEY);
        return OPTIONS.includes(stored) ? stored : 'system';
    }

    function resolveTheme(mode) {
        if (mode === 'system') {
            return media.matches ? 'dark' : 'light';
        }
        return mode;
    }

    function applyTheme(mode) {
        const resolved = resolveTheme(mode);
        document.documentElement.setAttribute('data-theme-mode', mode);
        document.documentElement.setAttribute('data-theme', resolved);

        document.querySelectorAll('[data-theme-option]').forEach((button) => {
            const active = button.getAttribute('data-theme-option') === mode;
            button.classList.toggle('active', active);
            button.setAttribute('aria-pressed', active ? 'true' : 'false');
        });
    }

    function setTheme(mode) {
        localStorage.setItem(STORAGE_KEY, mode);
        applyTheme(mode);
    }

    document.addEventListener('DOMContentLoaded', function () {
        const current = getStoredMode();
        applyTheme(current);

        document.querySelectorAll('[data-theme-option]').forEach((button) => {
            button.addEventListener('click', function () {
                setTheme(button.getAttribute('data-theme-option'));
            });
        });
    });

    if (typeof media.addEventListener === 'function') {
        media.addEventListener('change', function () {
            if (getStoredMode() === 'system') {
                applyTheme('system');
            }
        });
    } else if (typeof media.addListener === 'function') {
        media.addListener(function () {
            if (getStoredMode() === 'system') {
                applyTheme('system');
            }
        });
    }
})();
