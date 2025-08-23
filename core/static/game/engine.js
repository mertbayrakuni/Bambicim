// Tiny narrative engine with flags, autosave, back/reset + award sync + link choices
(function () {
  const root = document.getElementById("game-root");
  if (!root) return;

  // scenes are provided by template: <div id="game-root" data-scenes-url="{% static 'game/scenes.json' %}">
  const scenesUrl = root.dataset.scenesUrl;

  const $ = (sel, el = document) => el.querySelector(sel);
  const tEl = $("#g-title", root), pEl = $("#g-text", root), cEl = $("#g-choices", root);

  // local save key
  const SAVE_KEY = "bambi_game_v1";

  // game data + state
  let data = { start: "intro", scenes: {} };
  let state = { at: "intro", flags: {}, history: [] };

  // ---- CSRF for Django session auth ----
  function getCookie(name) {
    const m = document.cookie.match("(^|;)\\s*" + name + "\\s*=\\s*([^;]+)");
    return m ? m.pop() : "";
  }
  const CSRF = getCookie("csrftoken");

  async function postJSON(url, payload) {
    try {
      const res = await fetch(url, {
        method: "POST",
        credentials: "same-origin",
        headers: {
          "Content-Type": "application/json",
          "X-Requested-With": "fetch",
          "X-CSRFToken": CSRF
        },
        body: JSON.stringify(payload || {})
      });
      if (!res.ok) return null;             // keep gameplay even if backend says no
      return await res.json();
    } catch {
      return null;
    }
  }

  // ---- save/load (local only; server optional) ----
  function loadSave() {
    try { state = JSON.parse(localStorage.getItem(SAVE_KEY) || "null") || state; } catch {}
  }
  function saveLocal() {
    try { localStorage.setItem(SAVE_KEY, JSON.stringify(state)); } catch {}
  }

  // ---- helpers for flags/conditions ----
  function allowed(choice) {
    if (!choice.if) return true;
    return Object.entries(choice.if).every(([k, v]) => Boolean(state.flags[k]) === Boolean(v));
  }
  function apply(choice) {
    if (choice.set) for (const [k, v] of Object.entries(choice.set)) state.flags[k] = v;
  }

  // ---- navigation ----
  async function go(nextKey, clicked) {
    state.history.push(state.at);
    state.at = nextKey || state.at;

    if (clicked) {
      // local effects
      apply(clicked);
      saveLocal();

      // normalize gains to list of slugs (backend can upsert items by slug)
      const gains = Array.isArray(clicked.gain)
        ? clicked.gain.map(g => (typeof g === "string" ? g : g?.slug).trim()).filter(Boolean)
        : [];

      // best-effort award sync (ok for anonymous too)
      postJSON("/game/choice", {
        scene: state.history.at(-1),          // the scene we just left
        label: clicked.label || "",
        gain: gains
      });
    }

    render();
  }

  function uiBtn(label, onClick, disabled = false) {
    const b = document.createElement("button");
    b.className = "choice-btn";
    b.textContent = label;
    if (disabled) b.setAttribute("disabled", "disabled");
    b.addEventListener("click", onClick);
    return b;
  }

  function handleChoice(choice) {
    // external navigation: either explicit href or special action
    if (choice.href) {
      window.location.href = choice.href;
      return;
    }
    if (choice.action === "profile") {
      window.location.href = "/accounts/me/";
      return;
    }
    // normal scene jump
    go(choice.next, choice);
  }

  function render() {
    const s = data.scenes[state.at];
    if (!s) {
      console.warn("Missing scene:", state.at);
      state.at = data.start;
      return render();
    }

    tEl.textContent = s.title || "";
    pEl.textContent = s.text || "";
    cEl.innerHTML = "";

    // back & reset utilities
    cEl.appendChild(uiBtn("◀ Back", () => {
      if (state.history.length) {
        state.at = state.history.pop();
        saveLocal();
        render();
      }
    }, state.history.length === 0));

    cEl.appendChild(uiBtn("⟳ Reset", () => {
      state = { at: data.start, flags: {}, history: [] };
      saveLocal();
      render();
    }));

    // primary choices
    (s.choices || []).forEach(choice => {
      if (!allowed(choice)) return;
      cEl.appendChild(uiBtn(choice.label, () => handleChoice(choice)));
    });
  }

  // ---- boot ----
  async function boot() {
    try {
      const res = await fetch(scenesUrl, { cache: "no-store" });
      data = await res.json();
    } catch (e) {
      console.warn("Failed to fetch scenes.json; using tiny fallback.", e);
      data = { start: "intro", scenes: { intro: { title: "First step", text: "…", choices: [] } } };
    }
    if (!state.history.length) state.at = data.start;
    render();
  }

  loadSave();
  boot();
})();
