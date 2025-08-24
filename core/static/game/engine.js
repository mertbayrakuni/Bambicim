// Tiny narrative engine with flags, autosave, back/reset + award sync + link choices
(function () {
    // ===== bootstrap =====
    const root = document.getElementById("game-root");
    if (!root) return;

    // <div id="game-root" data-scenes-url=".../scenes.json">
    const scenesUrl = root.dataset.scenesUrl;

    const $ = (sel, el = document) => el.querySelector(sel);
    const tEl = $("#g-title", root);
    const pEl = $("#g-text", root);
    const cEl = $("#g-choices", root);

    // ===== local save =====
    const SAVE_KEY = "bambi_game_v1";
    let data = {start: "intro", scenes: {}};
    let state = {at: "intro", flags: {}, history: []};

    function loadSave() {
        try {
            const raw = localStorage.getItem(SAVE_KEY);
            if (raw) state = JSON.parse(raw);
        } catch {
        }
    }

    function saveLocal() {
        try {
            localStorage.setItem(SAVE_KEY, JSON.stringify(state));
        } catch {
        }
    }

    // ===== csrf + fetch helpers (Django) =====
    function getCookie(name) {
        const m = document.cookie.match(new RegExp("(^|;)\\s*" + name + "=([^;]+)"));
        return m ? decodeURIComponent(m[2]) : "";
    }

    async function postJSON(url, body) {
        const res = await fetch(url, {
            method: "POST",
            credentials: "same-origin",
            headers: {
                "Content-Type": "application/json",
                "X-Requested-With": "fetch",
                "X-CSRFToken": getCookie("csrftoken"),
            },
            body: JSON.stringify(body || {}),
        });
        if (!res.ok) {
            // keep gameplay flowing even if backend refuses (e.g. anon/403)
            try {
                console.warn("POST", url, res.status, await res.text());
            } catch {
            }
            throw new Error("HTTP " + res.status);
        }
        const ct = (res.headers.get("content-type") || "").toLowerCase();
        if (!ct.includes("application/json")) throw new Error("Non-JSON response");
        return res.json();
    }

    // ===== flags / conditions =====
    function allowed(choice) {
        if (!choice.if) return true;
        // choice.if = {flagName: true/false}
        return Object.entries(choice.if).every(([k, v]) => !!state.flags[k] === !!v);
    }

    function apply(choice) {
        if (choice.set) for (const [k, v] of Object.entries(choice.set)) state.flags[k] = v;
    }

    // ===== scene nav =====
    async function goto(nextId, clicked) {
        // apply local effects first
        if (clicked) apply(clicked);

        // remember navigation
        state.history.push(state.at);
        state.at = nextId || state.at;
        saveLocal();

        // send awards (if any) to backend; tolerate failures
        if (clicked && clicked.gain) {
            const gain = normalizeGain(clicked.gain); // -> [{slug, qty}]
            if (gain.length) {
                try {
                    await postJSON("/game/choice", {
                        scene: state.history[state.history.length - 1], // the scene we clicked in
                        choice: clicked.id || clicked.label || "",
                        gain,
                    });
                } catch (e) {
                    // non-fatal; just log
                    console.warn("award sync failed:", e);
                }
            }
        }

        render();
    }

    function normalizeGain(g) {
        // Accept "pink-skirt" OR {slug:"pink-skirt"} OR {slug:"pink-skirt", qty:2}
        if (!Array.isArray(g)) return [];
        return g
            .map(x => {
                if (!x) return null;
                if (typeof x === "string") return {slug: x, qty: 1};
                const slug = (x.slug || "").trim();
                const qty = Math.max(1, parseInt(x.qty ?? 1, 10) || 1);
                return slug ? {slug, qty} : null;
            })
            .filter(Boolean);
    }

    // ===== UI bits =====
    function makeBtn(label, onClick, disabled = false) {
        const b = document.createElement("button");
        b.className = "cta";
        b.textContent = label;
        if (disabled) b.disabled = true;
        b.onclick = onClick;
        return b;
    }

    function handleChoice(choice) {
        // external actions
        if (choice.href) {
            window.location.href = choice.href;
            return;
        }
        if (choice.id === "profile" || choice.action === "profile") {
            window.location.href = "/accounts/me/";
            return;
        }
        if (choice.id === "reset") {
            state = {at: data.start, flags: {}, history: []};
            saveLocal();
            render();
            return;
        }
        if (choice.id === "back") {
            if (state.history.length) {
                state.at = state.history.pop();
                saveLocal();
                render();
            }
            return;
        }

        // normal transition
        goto(choice.next, choice);
    }

    function render() {
        const s = data.scenes[state.at];
        if (!s) {
            console.warn("Unknown scene:", state.at);
            state.at = data.start;
            return render();
        }

        tEl.textContent = s.title || "";
        pEl.textContent = s.text || "";
        cEl.innerHTML = "";

        // utility: back / reset
        cEl.appendChild(makeBtn("◀ Back", () => handleChoice({id: "back"}), state.history.length === 0));
        cEl.appendChild(makeBtn("⟳ Reset", () => handleChoice({id: "reset"})));

        // primary choices
        (s.choices || []).forEach(ch => {
            if (!allowed(ch)) return;
            cEl.appendChild(makeBtn(ch.label || "…", () => handleChoice(ch)));
        });
    }

    // ===== boot =====
    async function boot() {
        try {
            const res = await fetch(scenesUrl, {cache: "no-store"});
            data = await res.json();
        } catch (e) {
            console.warn("Failed to load scenes.json; using fallback", e);
            data = {start: "intro", scenes: {intro: {title: "Hello", text: "Couldn’t load scenes.", choices: []}}};
        }
        if (!state.history.length) state.at = data.start;
        render();
    }

    loadSave();
    boot();
})();
