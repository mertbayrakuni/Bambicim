/* core/static/game/engine.js */
/* jshint esversion: 11, browser: true, devel: true */
/* eslint-env browser */

(function () {
    const SAVE_KEY = "bambiGameSave";

    function qs(s, r) {
        return (r || document).querySelector(s)
    }

    function el(t, a, ...k) {
        const n = document.createElement(t);
        if (a) for (const [x, v] of Object.entries(a)) {
            if (x === "class") n.className = v; else if (x.startsWith("on") && typeof v === "function") n.addEventListener(x.slice(2), v); else n.setAttribute(x, v)
        }
        k.forEach(c => n.append(c));
        return n
    }

    const Store = {
        load() {
            try {
                return JSON.parse(localStorage.getItem(SAVE_KEY)) || {}
            } catch {
                return {}
            }
        }, save(o) {
            localStorage.setItem(SAVE_KEY, JSON.stringify(o || {}))
        }, clear() {
            localStorage.removeItem(SAVE_KEY)
        }
    };

    function renderInventory(inv) {
        const wrap = el("div", {class: "bg-black/5 rounded-xl px-3 py-2 text-sm flex gap-2 flex-wrap"});
        const keys = Object.keys(inv || {}).filter(k => (inv[k] || 0) > 0);
        if (!keys.length) {
            wrap.append(el("span", {class: "opacity-60"}, "Inventory: (empty)"));
            return wrap;
        }
        wrap.append(el("span", {class: "opacity-60"}, "Inventory:"));
        keys.forEach(k => wrap.append(el("span", {class: "px-2 py-1 rounded-lg border border-black/10"}, `${k} × ${inv[k]}`)));
        return wrap;
    }

    function mount(container) {
        container.innerHTML = "";
        const header = el("div", {class: "flex items-center justify-between mb-3"},
            el("div", {class: "text-lg font-semibold"}, "Bambi Game"),
            el("div", {}, el("button", {
                class: "border rounded-lg px-3 py-1", onclick: () => {
                    if (confirm("Reset progress?")) {
                        Store.clear();
                        start();
                    }
                }
            }, "Reset"))
        );
        const invBar = el("div", {class: "mb-3"});
        const card = el("div", {class: "rounded-2xl shadow p-4 bg-white/90 space-y-4"});
        const title = el("h3", {class: "text-xl font-bold"});
        const body = el("div", {class: "whitespace-pre-wrap leading-relaxed"});
        const choices = el("div", {class: "grid gap-2"});
        card.append(title, body, choices);
        container.append(header, invBar, card);

        let scenes = {}, state = {current: null, inv: {}};

        function gainsApply(g) {
            (g || []).forEach(x => {
                const key = (x.item || "").trim();
                if (!key) return;
                const q = Number(x.qty || 1);
                state.inv[key] = (state.inv[key] || 0) + q;
            });
        }

        function render(key) {
            const s = scenes[key];
            if (!s) return;
            state.current = key;
            Store.save(state);
            title.textContent = s.title || "";
            body.textContent = s.text || "";
            invBar.innerHTML = "";
            invBar.append(renderInventory(state.inv));
            choices.innerHTML = "";
            (s.choices || []).forEach(ch => {
                const btn = el("button", {class: "border rounded-xl px-3 py-2 text-left"}, ch.text || "Continue");
                btn.addEventListener("click", () => {
                    gainsApply(ch.gains || []);
                    const t = ch.target;
                    if (t && scenes[t]) render(t); else {
                        invBar.innerHTML = "";
                        invBar.append(renderInventory(state.inv));
                        Store.save(state);
                    }
                });
                choices.append(btn);
            });
        }

        function start() {
            state = Store.load();
            fetch("/game/scenes").then(r => r.json()).then(data => {
                scenes = data.scenes || {};
                const startKey = state.current || data.start;
                if (!state.inv) state.inv = {};
                render(startKey);
            }).catch(err => {
                console.error("Failed to load scenes:", err);
                container.innerHTML = "Bambi couldn’t load the adventure.";
            });
        }

        start();
    }

    document.addEventListener("DOMContentLoaded", () => {
        const root = qs("#game-root");
        if (root) mount(root);
    });
})();
