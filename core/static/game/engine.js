/* core/static/game/engine.js (patched, backward‑compatible)
   - Accepts scenes using either:
     * {choices:[{text:"..", target:"..", gains:[{item,qty}]}]}
     * {choices:[{label:"..", next:"..", gain:["slug" or {slug,qty}]}]}
   - Gracefully falls back between /game/scenes and static file /static/game/scenes.json
   - Works without login; choice POST is best‑effort only.
*/
(function () {
    const SAVE_KEY = "bambiGameSave";

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

    const renderInventory = (inv) => {
        const wrap = el("div", {class: "inventory-wrap"});
        const keys = Object.keys(inv || {}).filter(k => (inv[k] || 0) > 0);
        if (!keys.length) {
            wrap.append(el("span", {class: "inventory-empty"}, "Inventory: (empty)"));
            return wrap;
        }
        wrap.append(el("span", {class: "inventory-label"}, "Inventory:"));
        keys.forEach(k => {
            wrap.append(el("span", {class: "inventory-item"}, `${k} × ${inv[k]}`));
        });
        return wrap;
    };

    function normalizeChoice(ch) {
        // Support both shapes
        const label = (ch.text ?? ch.label ?? "Continue").toString();
        const target = (ch.target ?? ch.next ?? null);
        const gains = (ch.gains ?? ch.gain ?? []);
        // Normalize gains into [{item, qty}] with non‑empty item
        const normGains = [];
        if (Array.isArray(gains)) {
            for (const g of gains) {
                if (typeof g === "string") normGains.push({item: g, qty: 1});
                else if (g && typeof g === "object") {
                    const item = (g.item ?? g.slug ?? "").toString().trim();
                    const qty = Number(g.qty ?? 1) || 1;
                    if (item) normGains.push({item, qty});
                }
            }
        }
        return {label, target, gains: normGains};
    }

    function normalizeScenes(payload) {
        // Accept {start, scenes:{id:{title,text,choices}}}
        // and keep as is (only normalize choices)
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

    const mount = (container) => {
        container.classList.add("b-game");

        const invBar = el("div", {class: "inventory"});
        const resetBtn = el("button", {class: "reset-btn"}, "Reset");
        resetBtn.addEventListener("click", () => {
            Store.clear();
            state = {current: null, inv: {}};
            render(state.current || startKey);
        });
        invBar.append(resetBtn);

        const card = el("div", {class: "game-card scene"});
        const sceneTitle = el("h3");
        const sceneText = el("p");
        const choicesWrap = el("div", {class: "choices"});
        card.append(sceneTitle, sceneText, choicesWrap);

        container.append(invBar, card);

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

        const render = (key) => {
            const s = scenes[key];
            if (!s) return;
            state.current = key;
            Store.save(state);

            sceneTitle.textContent = s.title || "";
            sceneText.textContent = s.text || "";
            // inventory
            invBar.querySelector(".inventory-wrap")?.remove();
            invBar.append(renderInventory(state.inv));

            // choices
            choicesWrap.replaceChildren();
            for (const ch of s.choices || []) {
                const btn = el("button", {class: "choice-btn"}, ch.label || "Continue");
                btn.addEventListener("click", () => {
                    applyGains(ch.gains);
                    // best‑effort log (ignore failures / login redirects)
                    try {
                        fetch("/game/choice", {
                            method: "POST",
                            headers: {"Content-Type": "application/json", "X-Requested-With": "fetch"},
                            body: JSON.stringify({scene: key, label: ch.label, gain: ch.gains}),
                            credentials: "same-origin",
                        }).catch(() => {
                        });
                    } catch {
                    }
                    const next = ch.target;
                    if (next && scenes[next]) render(next);
                });
                choicesWrap.append(btn);
            }
        };

        async function loadScenes() {
            // Try server JSON first, then static file
            const tryUrls = ["/game/scenes", "/static/game/scenes.json", "/game/scenes.json", "{STATIC_URL}game/scenes.json"];
            let payload = null;
            for (const url of tryUrls) {
                try {
                    const r = await fetch(url, {credentials: "same-origin"});
                    if (!r.ok) continue;
                    const data = await r.json();
                    payload = data;
                    break;
                } catch {
                }
            }
            if (!payload) throw new Error("no-scenes");
            return normalizeScenes(payload);
        }

        async function start() {
            // restore saved inventory / position
            const saved = Store.load();
            if (saved && typeof saved === "object") state = {current: saved.current || null, inv: saved.inv || {}};

            try {
                const loaded = await loadScenes();
                scenes = loaded.scenes;
                startKey = loaded.start;
                render(state.current || startKey);
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