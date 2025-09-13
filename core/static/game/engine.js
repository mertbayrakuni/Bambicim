/* core/static/game/engine.js — Bambi Game (no refresh, ensure-all-on-boot)
   - Calls /art/ensure-all once on boot to generate all scene images
   - No per-scene ensure calls on render/click
   - Buttons are type="button" + preventDefault (no page reloads)
   - Caches loaded image URLs to avoid re-requests
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
        const m = document.cookie.match("(^|;)\\s*" + name + "\\s*=\\s*([^;]+)");
        return m ? decodeURIComponent(m.pop()) : "";
    }

    const log = (...args) => console.debug("[BambiGame]", ...args);

    // pixel art cache: key -> image URL ("" means not ready yet, don't hammer)
    const ArtCache = new Map();

    // ---------- rendering helpers ----------
    const renderInventory = (inv) => {
        const wrap = el("div", {class: "inventory-wrap"});
        const keys = Object.keys(inv || {}).filter((k) => (inv[k] || 0) > 0);
        if (!keys.length) {
            wrap.append(el("span", {class: "inventory-empty"}, "Inventory: (empty)"));
            return wrap;
        }
        wrap.append(el("span", {class: "inventory-label"}, "Inventory:"));
        keys.forEach((k) => wrap.append(el("span", {class: "inventory-item"}, `${k} × ${inv[k]}`)));
        return wrap;
    };

    // ---------- data normalization ----------
    function normalizeChoice(ch) {
        const label = (ch.text ?? ch.label ?? "Continue").toString();
        const target = ch.target ?? ch.next ?? null;
        const href = ch.href ?? null;
        const gainsRaw = ch.gains ?? ch.gain ?? [];
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

    // ---------- art helpers ----------
    async function loadArtUrl(key) {
        if (ArtCache.has(key)) return ArtCache.get(key);

        const baseUrl = `/art/scene/${encodeURIComponent(key)}.webp`;
        // Try up to 3 quick loads; if 404, cache "" to avoid hammering.
        let tries = 0, maxTries = 3;
        const urlTry = () =>
            new Promise((resolve) => {
                const img = new Image();
                img.onload = () => resolve(baseUrl);
                img.onerror = () => resolve("");
                img.src = baseUrl + "?t=" + Date.now();
            });

        let url = "";
        while (tries++ < maxTries) {
            // eslint-disable-next-line no-await-in-loop
            url = await urlTry();
            if (url) break;
            // eslint-disable-next-line no-await-in-loop
            await new Promise((r) => setTimeout(r, 800));
        }
        ArtCache.set(key, url);
        return url;
    }

    function prewarmArt(keys, count = 3) {
        keys.slice(0, count).forEach((k) => {
            loadArtUrl(k).catch(() => {
            });
        });
    }

    // ---------- app ----------
    const mount = (container) => {
        container.classList.add("b-game");

        const invBar = el("div", {class: "inventory-bar"});
        const resetBtn = el("button", {class: "reset-btn", type: "button"}, "Reset");
        resetBtn.addEventListener("click", (e) => {
            e.preventDefault();
            e.stopPropagation();
            Store.clear();
            state = {current: null, inv: {}};
            render(startKey);
        });
        invBar.append(resetBtn);

        const card = el("div", {class: "game-card scene"});
        const sceneArtPh = el("div", {class: "scene-pixel ph"});
        const sceneArt = el("img", {class: "scene-pixel", alt: ""});
        const sceneTitle = el("h3");
        const sceneText = el("p");
        const choicesWrap = el("div", {class: "choices"});
        card.append(sceneArtPh, sceneArt, sceneTitle, sceneText, choicesWrap);

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

        const safePostChoice = async (sceneKey, choice) => {
            try {
                const csrftoken = getCookie("csrftoken");
                const r = await fetch("/game/choice", {
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
                        gain: choice.gains,
                    }),
                });
                if (r.ok) {
                    const resp = await r.json().catch(() => null);
                    if (resp && window.ttwAchv && typeof window.ttwAchv.onChoiceResponse === "function") {
                        window.ttwAchv.onChoiceResponse(resp);
                    }
                }
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

            // text
            sceneTitle.textContent = s.title || "";
            sceneText.textContent = s.text || "";

            // pixel art (cached + placeholder)
            sceneArt.removeAttribute("src");
            sceneArt.setAttribute("alt", s.title || key);
            sceneArt.style.display = "none";
            sceneArtPh.style.display = "";

            loadArtUrl(key).then((url) => {
                if (url) {
                    sceneArt.src = url;
                    sceneArt.style.display = "";
                    sceneArtPh.style.display = "none";
                } // else keep placeholder until generator finishes (no extra ensures here)
            });

            // inventory (optional)
            if (SHOW_INV) {
                invBar.querySelector(".inventory-wrap")?.remove();
                invBar.append(renderInventory(state.inv));
            }

            // choices
            choicesWrap.replaceChildren();
            for (const ch of s.choices || []) {
                const btn = el("button", {class: "choice-btn", type: "button"}, ch.label || "Continue");
                btn.addEventListener("click", (e) => {
                    e.preventDefault();
                    e.stopPropagation();
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
                const initial = state.current && scenes[state.current] ? state.current : startKey;

                // NEW: kick server to generate ALL scene images once (background)
                fetch("/art/ensure-all", {credentials: "include"}).catch(() => {
                });
                // Light prewarm so first few scenes pop instantly
                prewarmArt(Object.keys(scenes), 3);

                // debug: broken links
                const broken = [];
                for (const [k, s] of Object.entries(scenes)) {
                    (s.choices || []).forEach((c) => {
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
