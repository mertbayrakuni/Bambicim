/* core/static/game/engine.js */
/* jshint esversion: 11, browser: true, devel: true */
/* eslint-env browser */

(function () {
    const SAVE_KEY = "bambiGameSave";

    // Helper to query for an element.
    const qs = (sel, root) => (root || document).querySelector(sel);

    // Helper to create a new element.
    const el = (tag, attrs, ...kids) => {
        const n = document.createElement(tag);
        if (attrs) {
            for (const [k, v] of Object.entries(attrs)) {
                if (k === "class") n.className = v;
                else if (k.startsWith("on") && typeof v === "function") n.addEventListener(k.slice(2), v);
                else n.setAttribute(k, v);
            }
        }
        kids.forEach(c => n.append(c));
        return n;
    };

    // Game state management using localStorage.
    const Store = {
        load: () => {
            try {
                return JSON.parse(localStorage.getItem(SAVE_KEY)) || {};
            } catch {
                return {};
            }
        },
        save: (o) => localStorage.setItem(SAVE_KEY, JSON.stringify(o || {})),
        clear: () => localStorage.removeItem(SAVE_KEY)
    };

    // Renders the player's inventory list.
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

    // Initializes and mounts the game.
    const mount = (container) => {
        container.innerHTML = "";
        container.classList.add("b-game");

        const invBar = el("div", {class: "game-inv-bar"});
        const card = el("div", {class: "game-card"});
        const sceneTitle = el("h3");
        const sceneText = el("p");
        const choicesWrap = el("div", {class: "choices"});

        card.append(sceneTitle, sceneText, choicesWrap);
        container.append(invBar, card);

        let scenes = {};
        let state = {current: null, inv: {}};

        // Adds or removes items from the inventory.
        const applyGains = (gains) => {
            (gains || []).forEach(g => {
                const key = (g.item || "").trim();
                if (!key) return;
                const qty = Number(g.qty || 1);
                state.inv[key] = (state.inv[key] || 0) + qty;
            });
        };

        // Renders a specific scene.
        const render = (key) => {
            const s = scenes[key];
            if (!s) return;

            state.current = key;
            Store.save(state);

            sceneTitle.textContent = s.title || "";
            sceneText.textContent = s.text || "";

            invBar.innerHTML = "";
            invBar.append(renderInventory(state.inv));

            choicesWrap.innerHTML = "";
            (s.choices || []).forEach(ch => {
                const btn = el(
                    "button",
                    {
                        class: "choice-btn",
                        onclick: () => {
                            applyGains(ch.gains || []);
                            const tgt = ch.target;
                            if (tgt && scenes[tgt]) {
                                render(tgt);
                            } else {
                                invBar.innerHTML = "";
                                invBar.append(renderInventory(state.inv));
                                Store.save(state);
                            }
                        }
                    },
                    ch.text || "Continue"
                );
                choicesWrap.append(btn);
            });
        };

        // Initializes the game, loading state and scenes.
        const start = () => {
            state = Store.load();
            fetch("/game/scenes")
                .then(r => r.json())
                .then(data => {
                    scenes = data.scenes || {};
                    const startKey = state.current || data.start;
                    if (!state.inv) state.inv = {};
                    render(startKey);
                })
                .catch(err => {
                    console.error("Failed to load scenes:", err);
                    container.innerHTML = "Bambi couldn’t load the adventure.";
                });
        };

        start();
    };

    // Mount the game when the page loads.
    document.addEventListener("DOMContentLoaded", () => {
        const root = qs("#game-root");
        if (root) mount(root);
    });
})();