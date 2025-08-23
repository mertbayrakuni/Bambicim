// Tiny narrative engine with flags, autosave, back/reset
(function(){
  const root = document.getElementById("game-root");
  if(!root) return;

  const scenesUrl = root.dataset.scenesUrl; // set from template
  const $ = (sel, el=document) => el.querySelector(sel);
  const tEl = $("#g-title", root), pEl = $("#g-text", root), cEl = $("#g-choices", root);
  const KEY = "bambi_game_save_v2";

  let data = { start:"intro", scenes:{} };
  let state = { at: "intro", flags: {}, history: [] };

  function loadSave(){
    try { const s = JSON.parse(localStorage.getItem(KEY)||"null"); if(s) state=s; } catch {}
  }
  function save(){ try { localStorage.setItem(KEY, JSON.stringify(state)); } catch {} }

  async function boot(){
    try{
      const r = await fetch(scenesUrl, {cache:"no-store"});
      data = await r.json();
    }catch(e){
      console.warn("Game scenes fetch failed, falling back to minimal set.", e);
      data = { start:"intro", scenes:{
        intro:{ title:"First step", text:"A quiet evening…", choices:[{label:"Open docs", next:"docs"},{label:"Open the mirror", next:"mirror"}]},
        docs:{ title:"Variables & voice", text:"let and const…", choices:[{label:"Practice a loop", next:"loop"},{label:"Back", next:"intro"}]},
        mirror:{ title:"Glimmer", text:"You smile…", choices:[{label:"Back", next:"intro"}]},
        loop:{ title:"Tiny triumphs", text:"for…of, while…", choices:[{label:"Ship it", next:"ship"},{label:"Back", next:"docs"}]},
        ship:{ title:"Ship it", text:"Small but honest.", choices:[{label:"Play again", next:"intro"}]}
      }};
    }
    if(!state.history.length){ state.at = data.start; }
    render();
  }

  function allowed(choice){
    if(!choice.if) return true;
    return Object.entries(choice.if).every(([k,v]) => Boolean(state.flags[k]) === Boolean(v));
  }

  function apply(choice){
    if(choice.set){
      for(const [k,v] of Object.entries(choice.set)) state.flags[k]=v;
    }
  }

  function render(){
    const s = data.scenes[state.at];
    if(!s){ console.warn("Missing scene:", state.at); state.at=data.start; return render(); }
    tEl.textContent = s.title || "";
    pEl.textContent = s.text || "";
    cEl.innerHTML = "";

    // utility buttons
    cEl.appendChild(uiBtn("◀ Back", () => { if(state.history.length){ state.at = state.history.pop(); save(); render(); } }, state.history.length===0));
    cEl.appendChild(uiBtn("⟳ Reset", () => { state={at:data.start, flags:{}, history:[]}; save(); render(); }));

    (s.choices||[]).forEach(ch=>{
      if(!allowed(ch)) return;
      const btn = uiBtn(ch.label, ()=>{
        state.history.push(state.at);
        state.at = ch.next || state.at;
        apply(ch);
        save();
        render();
      });
      cEl.appendChild(btn);
    });
  }

  function uiBtn(label, onClick, disabled=false){
    const b = document.createElement("button");
    b.className = "choice-btn";
    b.textContent = label;
    if(disabled) b.setAttribute("disabled","disabled");
    b.addEventListener("click", onClick);
    return b;
  }

  loadSave();
  boot();
})();
