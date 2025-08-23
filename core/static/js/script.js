(function () {
    const KEY = "bambi_theme";
    const root = document.body;

    function apply(theme) {
        root.setAttribute("data-theme", theme);
        try {
            localStorage.setItem(KEY, theme);
        } catch {
        }
    }

    const saved = (function () {
        try {
            return localStorage.getItem(KEY);
        } catch {
            return null;
        }
    })();
    apply(saved || "pink");

    document.addEventListener("click", (e) => {
        const btn = e.target.closest("[data-set-theme]");
        if (!btn) return;
        const theme = btn.getAttribute("data-set-theme");
        apply(theme);
        sparkle(e.clientX, e.clientY);
    });

    function sparkle(x, y) {
        const s = document.createElement("span");
        s.className = "sparkle";
        s.style.left = (x || window.innerWidth / 2) + "px";
        s.style.top = (y || 0) + "px";
        document.body.appendChild(s);
        setTimeout(() => s.remove(), 500);
    }
})();

(function () {
    const css = `
    .sparkle {
      position: fixed; width: 8px; height: 8px; pointer-events: none;
      background: radial-gradient(circle, var(--accent) 0%, transparent 70%);
      filter: blur(1px);
      transform: translate(-50%, -50%);
      animation: sparkle-pop .5s ease-out forwards;
      z-index: 9999;
    }
    @keyframes sparkle-pop {
      0% { opacity: .9; transform: translate(-50%,-50%) scale(.6) }
      80% { opacity: .3 }
      100% { opacity: 0; transform: translate(-50%,-70%) scale(1.4) }
    }`;
    const tag = document.createElement("style");
    tag.textContent = css;
    document.head.appendChild(tag);
})();

(function () {
    const KEY = 'theme';
    const $root = document.body;
    const saved = localStorage.getItem(KEY) || 'dark';
    $root.dataset.theme = saved;

    document.querySelectorAll('.theme-toggle .swatch').forEach(btn => {
        btn.addEventListener('click', () => {
            const t = btn.dataset.theme || 'dark';
            $root.dataset.theme = t;
            localStorage.setItem(KEY, t);
        });
    });
})();
