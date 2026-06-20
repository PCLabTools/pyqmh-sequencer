(function () {
    const STORAGE_KEY = 'pyqmh-theme';
    const OPTIONS = ['light', 'dark', 'system'];
    const media = window.matchMedia('(prefers-color-scheme: dark)');
    const isEmbedded = window.self !== window.top;

    function getParentMode() {
        if (!isEmbedded) {
            return null;
        }

        try {
            const mode = window.parent.document.documentElement.getAttribute('data-theme-mode');
            return OPTIONS.includes(mode) ? mode : null;
        } catch (_) {
            return null;
        }
    }

    function getStoredMode() {
        const parentMode = getParentMode();
        if (parentMode) {
            return parentMode;
        }

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
        const normalized = OPTIONS.includes(mode) ? mode : 'system';
        localStorage.setItem(STORAGE_KEY, normalized);
        applyTheme(normalized);

        // Keep parent and iframe aligned when this module is embedded.
        if (isEmbedded) {
            try {
                window.parent.document.documentElement.setAttribute('data-theme-mode', normalized);
                window.parent.document.documentElement.setAttribute('data-theme', resolveTheme(normalized));
            } catch (_) {
                // Ignore cross-origin or unavailable parent access.
            }
        }
    }

    function syncFromParent() {
        const parentMode = getParentMode();
        if (parentMode) {
            applyTheme(parentMode);
        }
    }

    document.addEventListener('DOMContentLoaded', function () {
        const current = getStoredMode();
        applyTheme(current);

        document.querySelectorAll('[data-theme-option]').forEach((button) => {
            button.addEventListener('click', function () {
                setTheme(button.getAttribute('data-theme-option'));
            });
        });

        if (isEmbedded) {
            try {
                const observer = new MutationObserver(function () {
                    syncFromParent();
                });
                observer.observe(window.parent.document.documentElement, {
                    attributes: true,
                    attributeFilter: ['data-theme-mode', 'data-theme'],
                });
            } catch (_) {
                // Ignore cross-origin or unavailable parent access.
            }
        }
    });

    window.addEventListener('storage', function (event) {
        if (event.key === STORAGE_KEY) {
            applyTheme(getStoredMode());
        }
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
