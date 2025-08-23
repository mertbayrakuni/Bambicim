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
  const fine = window.matchMedia('(pointer:fine)').matches;
  const reduced = window.matchMedia('(prefers-reduced-motion: reduce)').matches;
  const b = document.getElementById('bfly');
  if (!b || !fine || reduced) return;

  b.style.display = 'block';
  document.body.classList.add('hide-system-cursor');

  let x = innerWidth / 2, y = innerHeight / 2;
  let tx = x, ty = y;

  addEventListener('mousemove', (e) => { tx = e.clientX; ty = e.clientY; });

  document.addEventListener('mouseover', (e) => {
    const interactive = e.target.closest('input, textarea, select, [contenteditable="true"]');
    const showButterfly = !interactive;
    b.style.visibility = showButterfly ? 'visible' : 'hidden';
    document.body.classList.toggle('hide-system-cursor', showButterfly);
  });

  function loop() {
    const dx = tx - x, dy = ty - y;
    x += dx * 0.18; // easing
    y += dy * 0.18;
    const angle = Math.atan2(dy, dx) * 180 / Math.PI;

    b.style.left = x + 'px';
    b.style.top  = y + 'px';
    b.style.rotate = angle + 'deg';

    requestAnimationFrame(loop);
  }
  loop();

  addEventListener('blur', () => { b.style.visibility = 'hidden'; });
  addEventListener('focus', () => { b.style.visibility = 'visible'; });
})();
