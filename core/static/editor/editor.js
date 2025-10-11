(() => {
    // tiny helpers
    const $ = (s) => document.querySelector(s);
    const $$ = (s) => document.querySelectorAll(s);
    const dpr = Math.max(1, window.devicePixelRatio || 1);

    // DOM
    const fileInput = $('#fileInput');
    const resetBtn = $('#resetBtn');
    const rotL = $('#rotL'), rotR = $('#rotR'), flipH = $('#flipH'), flipV = $('#flipV');
    const cropModeBtn = $('#cropMode'), applyCropBtn = $('#applyCrop'), cancelCropBtn = $('#cancelCrop');
    const aspectSel = $('#aspect');
    const fmtSel = $('#fmt'), qRange = $('#quality'), qVal = $('#qv'), dlBtn = $('#downloadBtn');
    const pBW = $('#p_bw'), pWarm = $('#p_warm'), pCool = $('#p_cool'), pVivid = $('#p_vivid');
    const undoBtn = $('#undoBtn'), redoBtn = $('#redoBtn');

    const sliders = {
        bri: $('#s_bri'), con: $('#s_con'), sat: $('#s_sat'),
        hue: $('#s_hue'), sep: $('#s_sep'), gra: $('#s_gra'), blur: $('#s_blur')
    };
    const vals = {
        bri: $('#v_bri'), con: $('#v_con'), sat: $('#v_sat'),
        hue: $('#v_hue'), sep: $('#v_sep'), gra: $('#v_gra'), blur: $('#v_blur')
    };

    const stage = $('.ed-stage');
    const canvas = $('#preview');
    const ctx = canvas.getContext('2d');
    const hint = $('#hint');

    // ------- STATE -------
    let originalURL = null;
    let img = new Image();      // current baked image
    let loaded = false;

    // fixed stage size cache (CSS px) — only updated by ResizeObserver/window resize
    let stageW = 0, stageH = 0;

    // filters (applied in preview & on export)
    const filters = {bri: 100, con: 100, sat: 100, hue: 0, sep: 0, gra: 0, blur: 0};

    // crop UI
    let cropMode = false;
    let sel = null;          // {x,y,w,h} in CSS px (preview coords)
    let dragging = false;
    let aspect = 'free';

    // history (Undo/Redo)
    const MAX_STEPS = 10;
    const history = [];   // stack of {src, filters}
    const future = [];

    // ------- UTIL -------
    function enableEditing(on) {
        [
            resetBtn, rotL, rotR, flipH, flipV, cropModeBtn, aspectSel,
            fmtSel, qRange, dlBtn, pBW, pWarm, pCool, pVivid,
            applyCropBtn, cancelCropBtn
        ].forEach(el => el && (el.disabled = !on));
        Object.values(sliders).forEach(el => el && (el.disabled = !on));
        updateHistoryUI();
    }

    function setCanvasSize() {
        const r = stage.getBoundingClientRect();
        const w = Math.max(1, Math.floor(r.width));
        const h = Math.max(1, Math.floor(r.height));
        if (w === stageW && h === stageH) return; // idempotent: no thrash
        stageW = w;
        stageH = h;
        canvas.style.width = `${stageW}px`;
        canvas.style.height = `${stageH}px`;
        canvas.width = Math.floor(stageW * dpr);
        canvas.height = Math.floor(stageH * dpr);
    }

    function computeFit() {
        // use canvas’s CSS size (stable between draws) rather than re-reading layout every frame
        const W = stageW, H = stageH;
        const iw = img.naturalWidth || 1, ih = img.naturalHeight || 1;
        const scale = Math.min(W / iw, H / ih);
        const vw = iw * scale, vh = ih * scale;
        const ox = (W - vw) / 2;
        const oy = (H - vh) / 2;
        return {scale, vw, vh, ox, oy};
    }

    function cssFilter() {
        return `brightness(${filters.bri}%) contrast(${filters.con}%) saturate(${filters.sat}%) hue-rotate(${filters.hue}deg) sepia(${filters.sep}%) grayscale(${filters.gra}%) blur(${filters.blur}px)`;
    }

    function updateHistoryUI() {
        if (undoBtn) undoBtn.disabled = history.length === 0;
        if (redoBtn) redoBtn.disabled = future.length === 0;
    }

    function snapshot() {
        if (!loaded) return;
        history.push({src: img.src, filters: {...filters}});
        if (history.length > MAX_STEPS) history.shift();
        future.length = 0; // clear redo stack
        updateHistoryUI();
    }

    function restore(state) {
        const tmp = new Image();
        tmp.onload = () => {
            img = tmp;
            Object.assign(filters, state.filters);
            // reflect sliders/labels
            sliders.bri.value = filters.bri;
            vals.bri.textContent = `${filters.bri}%`;
            sliders.con.value = filters.con;
            vals.con.textContent = `${filters.con}%`;
            sliders.sat.value = filters.sat;
            vals.sat.textContent = `${filters.sat}%`;
            sliders.hue.value = filters.hue;
            vals.hue.textContent = `${filters.hue}°`;
            sliders.sep.value = filters.sep;
            vals.sep.textContent = `${filters.sep}%`;
            sliders.gra.value = filters.gra;
            vals.gra.textContent = `${filters.gra}%`;
            sliders.blur.value = filters.blur;
            vals.blur.textContent = `${filters.blur}px`;
            draw();
        };
        tmp.src = state.src;
    }

    function doUndo() {
        if (history.length === 0) return;
        const curr = {src: img.src, filters: {...filters}};
        const prev = history.pop();
        future.push(curr);
        restore(prev);
        updateHistoryUI();
    }

    function doRedo() {
        if (future.length === 0) return;
        const curr = {src: img.src, filters: {...filters}};
        const next = future.pop();
        history.push(curr);
        restore(next);
        updateHistoryUI();
    }

    // ------- DRAW -------
    function draw() {
        // clear
        ctx.setTransform(1, 0, 0, 1, 0, 0);
        ctx.clearRect(0, 0, canvas.width, canvas.height);

        if (!loaded) return;

        const {ox, oy, vw, vh} = computeFit();

        // draw image with filters
        ctx.save();
        ctx.scale(dpr, dpr);
        ctx.filter = cssFilter();
        ctx.drawImage(img, ox, oy, vw, vh);
        ctx.restore();

        // crop overlay
        if (cropMode && sel) {
            ctx.save();
            ctx.scale(dpr, dpr);
            // darken full
            ctx.fillStyle = 'rgba(0,0,0,0.35)';
            ctx.fillRect(0, 0, stageW, stageH);
            // punch hole
            ctx.globalCompositeOperation = 'destination-out';
            ctx.fillStyle = '#000';
            ctx.fillRect(sel.x, sel.y, sel.w, sel.h);
            ctx.globalCompositeOperation = 'source-over';
            // border
            ctx.strokeStyle = '#ff5fb8';
            ctx.lineWidth = 2;
            ctx.strokeRect(sel.x, sel.y, sel.w, sel.h);
            ctx.restore();
        }
    }

    // ------- LOAD / RESET -------
    function loadFromFile(file) {
        const url = URL.createObjectURL(file);
        originalURL = url;
        const imgNew = new Image();
        imgNew.onload = () => {
            img = imgNew;
            loaded = true;
            enableEditing(true);
            hint && (hint.style.display = 'none');
            resetFilters(false);   // don’t draw yet
            cropMode = false;
            sel = null;
            snapshot();            // initial snapshot
            draw();
        };
        imgNew.src = url;
    }

    function resetAll() {
        if (!originalURL) return;
        // snapshot current before resetting
        snapshot();
        const imgNew = new Image();
        imgNew.onload = () => {
            img = imgNew;
            loaded = true;
            cropMode = false;
            sel = null;
            resetFilters(false);
            snapshot(); // baseline after reset
            draw();
        };
        imgNew.src = originalURL;
    }

    function resetFilters(alsoDraw = true) {
        Object.assign(filters, {bri: 100, con: 100, sat: 100, hue: 0, sep: 0, gra: 0, blur: 0});
        sliders.bri.value = 100;
        vals.bri.textContent = '100%';
        sliders.con.value = 100;
        vals.con.textContent = '100%';
        sliders.sat.value = 100;
        vals.sat.textContent = '100%';
        sliders.hue.value = 0;
        vals.hue.textContent = '0°';
        sliders.sep.value = 0;
        vals.sep.textContent = '0%';
        sliders.gra.value = 0;
        vals.gra.textContent = '0%';
        sliders.blur.value = 0;
        vals.blur.textContent = '0px';
        if (alsoDraw) draw();
    }

    // ------- TRANSFORMS (baked) -------
    function bakeTransform(drawFn, newW, newH) {
        const off = document.createElement('canvas');
        off.width = newW;
        off.height = newH;
        const c = off.getContext('2d');
        drawFn(c, off);
        const next = new Image();
        next.onload = () => {
            img = next;
            draw();
        };
        next.src = off.toDataURL('image/png');
    }

    function rotate(deg) {
        if (!loaded) return;
        const w = img.naturalWidth, h = img.naturalHeight;
        snapshot();
        if (deg === 90) {
            bakeTransform((c) => {
                c.translate(h, 0);
                c.rotate(Math.PI / 2);
                c.drawImage(img, 0, 0);
            }, h, w);
        } else if (deg === -90) {
            bakeTransform((c) => {
                c.translate(0, w);
                c.rotate(-Math.PI / 2);
                c.drawImage(img, 0, 0);
            }, h, w);
        }
    }

    function flip(horizontal) {
        if (!loaded) return;
        const w = img.naturalWidth, h = img.naturalHeight;
        snapshot();
        bakeTransform((c) => {
            if (horizontal) {
                c.translate(w, 0);
                c.scale(-1, 1);
            } else {
                c.translate(0, h);
                c.scale(1, -1);
            }
            c.drawImage(img, 0, 0);
        }, w, h);
    }

    // map preview CSS px -> image px
    function applyCrop() {
        if (!sel || !loaded) return;
        const {scale, ox, oy} = computeFit();
        const ix = Math.max(0, Math.round((sel.x - ox) / scale));
        const iy = Math.max(0, Math.round((sel.y - oy) / scale));
        const iw = Math.max(1, Math.round(sel.w / scale));
        const ih = Math.max(1, Math.round(sel.h / scale));

        const w = img.naturalWidth, h = img.naturalHeight;
        const x = Math.min(w - 1, Math.max(0, ix));
        const y = Math.min(h - 1, Math.max(0, iy));
        const cw = Math.min(w - x, iw);
        const ch = Math.min(h - y, ih);

        snapshot();
        bakeTransform((c) => {
            c.drawImage(img, x, y, cw, ch, 0, 0, cw, ch);
        }, cw, ch);

        cropMode = false;
        sel = null;
    }

    function startCrop() {
        cropMode = true;
        sel = null;
        draw();
    }

    // ------- EVENTS -------
    fileInput?.addEventListener('change', (e) => {
        const f = e.target.files?.[0];
        if (f) loadFromFile(f);
    });

    stage.addEventListener('dragover', e => e.preventDefault());
    stage.addEventListener('drop', e => {
        e.preventDefault();
        const f = e.dataTransfer.files?.[0];
        if (f) loadFromFile(f);
    });

    resetBtn?.addEventListener('click', resetAll);
    rotL?.addEventListener('click', () => rotate(-90));
    rotR?.addEventListener('click', () => rotate(90));
    flipH?.addEventListener('click', () => flip(true));
    flipV?.addEventListener('click', () => flip(false));

    cropModeBtn?.addEventListener('click', startCrop);
    cancelCropBtn?.addEventListener('click', () => {
        cropMode = false;
        sel = null;
        draw();
    });
    applyCropBtn?.addEventListener('click', applyCrop);
    aspectSel?.addEventListener('change', (e) => {
        aspect = e.target.value;
    });

    // crop mouse handling
    stage.addEventListener('mousedown', (e) => {
        if (!cropMode || !loaded) return;
        const r = stage.getBoundingClientRect();
        const sx = e.clientX - r.left, sy = e.clientY - r.top;
        sel = {x: sx, y: sy, w: 0, h: 0};
        dragging = true;
        draw();
    });
    stage.addEventListener('mousemove', (e) => {
        if (!cropMode || !dragging || !sel) return;
        const r = stage.getBoundingClientRect();
        let w = (e.clientX - r.left) - sel.x;
        let h = (e.clientY - r.top) - sel.y;

        if (aspect !== 'free') {
            const [aw, ah] = aspect.split(':').map(Number);
            const ratio = aw / ah;
            if (Math.abs(w) / Math.abs(h || 1) > ratio) h = Math.sign(h || 1) * Math.abs(w) / ratio;
            else w = Math.sign(w || 1) * Math.abs(h) * ratio;
        }
        // normalize to positive
        if (w < 0) {
            sel.x += w;
            w = -w;
        }
        if (h < 0) {
            sel.y += h;
            h = -h;
        }
        sel.w = w;
        sel.h = h;
        draw();
    });
    window.addEventListener('mouseup', () => {
        dragging = false;
    });

    // sliders
    function setValLabel(key, v, unit) {
        vals[key].textContent = unit === 'deg' ? `${v}°` : unit === 'px' ? `${v}px` : `${v}%`;
    }

    function bindRange(key, unit) {
        sliders[key].addEventListener('input', (e) => {
            const v = Number(e.target.value);
            filters[key] = v;
            setValLabel(key, v, unit);
            draw();
        });
        // push a single history step when user releases the thumb
        sliders[key].addEventListener('change', () => snapshot());
    }

    bindRange('bri');
    bindRange('con');
    bindRange('sat');
    bindRange('hue', 'deg');
    bindRange('sep');
    bindRange('gra');
    bindRange('blur', 'px');

    // presets
    function applyPreset(name) {
        snapshot();
        if (name === 'bw') {
            sliders.gra.value = 100;
            sliders.sep.value = 0;
            sliders.sat.value = 0;
        } else if (name === 'warm') {
            sliders.hue.value = -10;
            sliders.sep.value = 10;
            sliders.bri.value = 105;
        } else if (name === 'cool') {
            sliders.hue.value = 12;
            sliders.sep.value = 5;
            sliders.bri.value = 102;
        } else if (name === 'vivid') {
            sliders.con.value = 115;
            sliders.sat.value = 140;
            sliders.bri.value = 102;
        }
        // trigger inputs to sync filters + labels
        ['gra', 'sep', 'sat', 'hue', 'bri', 'con'].forEach(k => sliders[k].dispatchEvent(new Event('input')));
    }

    [pBW, pWarm, pCool, pVivid].forEach(btn => btn?.addEventListener('click', () => applyPreset(btn.dataset.preset)));

    // export
    qRange?.addEventListener('input', e => {
        qVal.textContent = e.target.value;
    });
    dlBtn?.addEventListener('click', () => {
        if (!loaded) return;
        const off = document.createElement('canvas');
        off.width = img.naturalWidth;
        off.height = img.naturalHeight;
        const c = off.getContext('2d');
        c.filter = cssFilter();
        c.drawImage(img, 0, 0);
        const mime = fmtSel.value;
        const q = Number(qRange.value) / 100;
        const url = off.toDataURL(mime, q);
        const a = document.createElement('a');
        a.href = url;
        a.download = mime === 'image/png' ? 'bambicim-edit.png' : 'bambicim-edit.jpg';
        a.click();
    });

    // history buttons + shortcuts
    undoBtn?.addEventListener('click', doUndo);
    redoBtn?.addEventListener('click', doRedo);
    window.addEventListener('keydown', (e) => {
        const z = (e.key === 'z' || e.key === 'Z');
        if ((e.metaKey || e.ctrlKey) && z && !e.shiftKey) {
            e.preventDefault();
            doUndo();
        }
        if ((e.metaKey || e.ctrlKey) && z && e.shiftKey) {
            e.preventDefault();
            doRedo();
        }
    });

    // ------- INIT -------
    enableEditing(false);
    setCanvasSize();
    // resize only when the stage actually changes size → no more creeping preview
    const ro = new ResizeObserver(() => {
        setCanvasSize();
        draw();
    });
    ro.observe(stage);
    window.addEventListener('resize', () => {
        setCanvasSize();
        draw();
    });

})();
