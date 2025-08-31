/* core/static/game/engine.js — Bambi Game (pink, link-aware, CSRF, logs)
   - Works with both shapes:
       { text, target, gains: [{item, qty}], href? }
       { label, next,  gain:  ["slug" | {slug, qty}], href? }
   - Loads /game/scenes first; falls back to /static/game/scenes.json
   - Best-effort POST to /game/choice with CSRF; failure doesn’t block UI
*/

(function () {
    // ---------- tiny helpers ----------
    const SAVE_KEY = "bambiGameSave";
    const SHOW_INV = false; // keep saving to DB but hide inventory on homepage

    const qs = (sel, root) => (root || document).querySelector(sel);
    const el = (tag, attrs, ...kids) => {
        const n = document.createElement(tag);
        if (attrs) for (const [k, v] of Object.entries(attrs)) {
            if (k === "class") n.className = v;
            else n.setAttribute(k, v);
        }
        for (const k of kids) n.append(k);
        return n;
    };

    const Store = {
        load: () => {
            try {
                return JSON.parse(localStorage.getItem(SAVE_KEY)) || {};
            } catch {
                return {};
            }
        },
        save: (o) => localStorage.setItem(SAVE_KEY, JSON.stringify(o || {})),
        clear: () => localStorage.removeItem(SAVE_KEY),
    };

    function getCookie(name) {
        const m = document.cookie.match('(^|;)\\s*' + name + '\\s*=\\s*([^;]+)');
        return m ? decodeURIComponent(m.pop()) : "";
    }

    const log = (...args) => console.debug("[BambiGame]", ...args);

    // ---------- rendering ----------
    const renderInventory = (inv) => {
        const wrap = el("div", {class: "inventory-wrap"});
        const keys = Object.keys(inv || {}).filter(k => (inv[k] || 0) > 0);
        if (!keys.length) {
            wrap.append(el("span", {class: "inventory-empty"}, "Inventory: (empty)"));
            return wrap;
        }
        wrap.append(el("span", {class: "inventory-label"}, "Inventory:"));
        keys.forEach(k => wrap.append(el("span", {class: "inventory-item"}, `${k} × ${inv[k]}`)));
        return wrap;
    };

    // ---------- data normalization ----------
    function normalizeChoice(ch) {
        const label = (ch.text ?? ch.label ?? "Continue").toString();
        const target = (ch.target ?? ch.next ?? null);
        const href = (ch.href ?? null);
        const gainsRaw = (ch.gains ?? ch.gain ?? []);
        const gains = [];

        if (Array.isArray(gainsRaw)) {
            for (const g of gainsRaw) {
                if (typeof g === "string") gains.push({item: g, qty: 1});
                else if (g && typeof g === "object") {
                    const item = (g.item ?? g.slug ?? "").toString().trim();
                    const qty = Number(g.qty ?? 1) || 1;
                    if (item) gains.push({item, qty});
                }
            }
        }
        return {label, target, href, gains};
    }

    function normalizeScenes(payload) {
        const start = payload.start;
        const scenes = {};
        for (const [key, node] of Object.entries(payload.scenes || {})) {
            const title = node.title || "";
            const text = node.text || "";
            const choices = (node.choices || []).map(normalizeChoice);
            scenes[key] = {title, text, choices};
        }
        return {start, scenes};
    }

    // ---------- app ----------
    const mount = (container) => {
        container.classList.add("b-game");

        const invBar = el("div", {class: "inventory-bar"});
        const resetBtn = el("button", {class: "reset-btn"}, "Reset");
        resetBtn.addEventListener("click", () => {
            Store.clear();
            state = {current: null, inv: {}};
            render(startKey);
        });
        invBar.append(resetBtn);

        const card = el("div", {class: "game-card scene"});
        const sceneTitle = el("h3");
        const sceneText = el("p");
        const choicesWrap = el("div", {class: "choices"});
        card.append(sceneTitle, sceneText, choicesWrap);

        if (SHOW_INV) container.append(invBar);
        container.append(card);

        let scenes = {};
        let startKey = null;
        let state = {current: null, inv: {}};

        const applyGains = (gains) => {
            for (const g of gains || []) {
                const k = (g.item || "").trim();
                if (!k) continue;
                const qty = Number(g.qty || 1) || 1;
                state.inv[k] = (state.inv[k] || 0) + qty;
            }
        };

        const safePostChoice = (sceneKey, choice) => {
            try {
                const csrftoken = getCookie("csrftoken");
                fetch("/game/choice", {
                    method: "POST",
                    headers: {
                        "Content-Type": "application/json",
                        "X-CSRFToken": csrftoken,
                        "X-Requested-With": "fetch",
                    },
                    credentials: "same-origin",
                    body: JSON.stringify({
                        scene: sceneKey,
                        label: choice.label,
                        gain: choice.gains, // [{item, qty}]
                    }),
                }).catch(() => {
                });
            } catch { /* ignore */
            }
        };

        const render = (key) => {
            const s = scenes[key];
            if (!s) {
                log("Missing scene:", key);
                return;
            }
            state.current = key;
            Store.save(state);

            sceneTitle.textContent = s.title || "";
            sceneText.textContent = s.text || "";

            if (SHOW_INV) {
                invBar.querySelector(".inventory-wrap")?.remove();
                invBar.append(renderInventory(state.inv));
            }

            choicesWrap.replaceChildren();
            for (const ch of s.choices || []) {
                const btn = el("button", {class: "choice-btn"}, ch.label || "Continue");
                btn.addEventListener("click", () => {
                    log("Click choice:", ch);
                    applyGains(ch.gains);
                    safePostChoice(key, ch);

                    if (ch.href) {
                        const go = ch.href;
                        if (/^https?:\/\//i.test(go)) window.location.href = go;
                        else window.location.assign(go);
                        return;
                    }

                    const next = ch.target;
                    if (!next) return;
                    if (!scenes[next]) {
                        log("Broken target:", next, "from", key);
                        return;
                    }
                    render(next);
                });
                choicesWrap.append(btn);
            }
        };

        async function loadScenes() {
            const tryUrls = ["/game/scenes", "/static/game/scenes.json", "/game/scenes.json"];
            for (const url of tryUrls) {
                try {
                    const r = await fetch(url, {credentials: "same-origin"});
                    if (!r.ok) continue;
                    const data = await r.json();
                    log("Loaded scenes from:", url);
                    return normalizeScenes(data);
                } catch {
                }
            }
            throw new Error("No scenes JSON available");
        }

        async function start() {
            const saved = Store.load();
            if (saved && typeof saved === "object") {
                state = {current: saved.current || null, inv: saved.inv || {}};
            }
            try {
                const loaded = await loadScenes();
                scenes = loaded.scenes;
                startKey = loaded.start;
                const initial = (state.current && scenes[state.current]) ? state.current : startKey;

                // Debug: broken links at boot
                const broken = [];
                for (const [k, s] of Object.entries(scenes)) {
                    (s.choices || []).forEach(c => {
                        const t = c.target;
                        if (t && !scenes[t]) broken.push({from: k, to: t, choice: c.label});
                    });
                }
                if (broken.length) log("Broken links detected:", broken);

                render(initial);
            } catch (err) {
                console.error("Failed to load scenes:", err);
                container.innerHTML = "Bambi couldn’t load the adventure.";
            }
        }

        start();
    };

    document.addEventListener("DOMContentLoaded", () => {
        const root = qs("#game-root");
        if (root) mount(root);
    });
})();
