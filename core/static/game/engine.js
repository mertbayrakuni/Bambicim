/* core/static/game/engine.js */
/* jshint esversion: 11, browser: true, devel: true */
/* eslint-env browser */

(function () {
    const SAVE_KEY = "bambiGameSave";

    // A simple query selector helper.
    function qs(sel, root) {
        return (root || document).querySelector(sel);
    }

    // A helper function to create new DOM elements with attributes and children.
    function el(tag, attrs, ...kids) {
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
    }

    // Handles saving and loading game state to localStorage.
    const Store = {
        load() {
            try {
                return JSON.parse(localStorage.getItem(SAVE_KEY)) || {};
            } catch {
                return {};
            }
        },
        save(o) {
            localStorage.setItem(SAVE_KEY, JSON.stringify(o || {}));
        },
        clear() {
            localStorage.removeItem(SAVE_KEY);
        }
    };

    // Renders the player's inventory.
    function renderInventory(inv) {
        // Use your custom CSS classes for styling
        const wrap = el("div", {class: "inventory-wrap"});
        const keys = Object.keys(inv || {}).filter(k => (inv[k] || 0) > 0);
        if (!keys.length) {
            wrap.append(el("span", {class: "inventory-empty"}, "Inventory: (empty)"));
            return wrap;
        }
        wrap.append(el("span", {class: "inventory-label"}, "Inventory:"));
        keys.forEach(k => wrap.append(
            el("span", {class: "inventory-item"}, `${k} × ${inv[k]}`)
        ));
        return wrap;
    }

    // The main function that initializes and mounts the game.
    function mount(container) {
        container.innerHTML = "";
        container.classList.add("bambi-game");

        // Create the game's header
        const header = el("div", {class: "game-header"},
            el("div", {class: "game-title"}, "Bambi Game"),
            el("div", {},
                el("button", {
                    class: "reset-btn",
                    onclick: () => {
                        if (confirm("Reset progress?")) {
                            Store.clear();
                            start();
                        }
                    }
                }, "Reset")
            )
        );

        // Create the main game card and its sections.
        const invBar = el("div", {class: "game-inv-bar"});
        const card = el("div", {class: "game-card"});
        const title = el("h3", {class: "scene-title"});
        const body = el("div", {class: "scene-text"});
        const choicesWrap = el("div", {class: "choices"});

        card.append(title, body, choicesWrap);
        container.append(header, invBar, card);

        let scenes = {};
        let state = {current: null, inv: {}};

        // Adds or removes items from the inventory.
        function applyGains(gains) {
            (gains || []).forEach(g => {
                const key = (g.item || "").trim();
                if (!key) return;
                const qty = Number(g.qty || 1);
                state.inv[key] = (state.inv[key] || 0) + qty;
            });
        }

        // Renders a specific scene based on its key.
        function render(key) {
            const s = scenes[key];
            if (!s) return;

            state.current = key;
            Store.save(state);

            title.textContent = s.title || "";
            body.textContent = s.text || "";

            invBar.innerHTML = "";
            invBar.append(renderInventory(state.inv));

            choicesWrap.innerHTML = "";
            (s.choices || []).forEach(ch => {
                const btn = el(
                    "button",
                    {class: "choice-btn"},
                    ch.text || "Continue"
                );
                btn.addEventListener("click", () => {
                    applyGains(ch.gains || []);
                    const tgt = ch.target;
                    if (tgt && scenes[tgt]) {
                        render(tgt);
                    } else {
                        invBar.innerHTML = "";
                        invBar.append(renderInventory(state.inv));
                        Store.save(state);
                    }
                });
                choicesWrap.append(btn);
            });
        }

        // Initializes the game, loading state and scenes.
        function start() {
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
        }

        start();
    }

    document.addEventListener("DOMContentLoaded", () => {
        const root = qs("#game-root");
        if (root) mount(root);
    });
})();