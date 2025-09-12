// Minimal, drop-in achievements HUD + toast
(function () {
  const bar = document.getElementById("achv-bar");
  const toast = document.getElementById("toast");
  if (!bar) return;

  const unlocked = new Set();

  function renderBar(items) {
    bar.innerHTML = "";
    if (!items || !items.length) {
      bar.classList.add("is-empty");
      bar.textContent = "No achievements yet — keep playing!";
      return;
    }
    bar.classList.remove("is-empty");
    const frag = document.createDocumentFragment();
    items.forEach((a) => {
      unlocked.add(a.slug);
      const b = document.createElement("div");
      b.className = "achv-badge";
      b.title = a.name;
      b.innerHTML = `<span class="emo">${a.emoji}</span><span class="nm">${a.name}</span>`;
      frag.appendChild(b);
    });
    bar.appendChild(frag);
  }

  function showToast(list) {
    if (!list || !list.length) return;
    toast.classList.remove("show");
    toast.innerHTML = list
      .map((a) => `<div class="achv-toast-row"><span class="emo">${a.emoji}</span> ${a.name}</div>`)
      .join("");
    // force reflow
    void toast.offsetWidth;
    toast.classList.add("show");
    setTimeout(() => toast.classList.remove("show"), 2600);
  }

  async function refresh() {
    try {
      const r = await fetch("/game/achievements", { credentials: "include" });
      if (!r.ok) return;
      const data = await r.json();
      renderBar(data.items || []);
    } catch (_) {}
  }

  // Hook into your existing engine: whenever a choice is made successfully,
  // we expect the server to return { achievements: [...] }
  // Patch the global function if present, else expose a helper.
  window.ttwAchv = {
    onChoiceResponse(resp) {
      if (!resp || !resp.achievements) return;
      const newly = resp.achievements.filter((a) => !unlocked.has(a.slug));
      if (newly.length) {
        newly.forEach((a) => unlocked.add(a.slug));
        showToast(newly);
        refresh();
      }
    },
  };

  // Initial fetch
  refresh();
})();
