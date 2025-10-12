(() => {
    // short-hands
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

    // new controls
    const toolMove = $('#toolMove'), toolText = $('#toolText');
    const txtSize = $('#txtSize'), txtWeight = $('#txtWeight'), txtColor = $('#txtColor');
    const gridToggle = $('#gridToggle'), zoomReadout = $('#zoomReadout'), fitBtn = $('#fitBtn'), oneBtn = $('#oneBtn');

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

    // persistence UI
    const saveBtn = document.querySelector('#saveBtn');
    const openBtn = document.querySelector('#openBtn');
    const saveTitle = document.querySelector('#saveTitle');


    // -------- STATE --------
    let originalURL = null;
    let img = new Image();
    let loaded = false;

    let stageW = 0, stageH = 0;

    const filters = {bri: 100, con: 100, sat: 100, hue: 0, sep: 0, gra: 0, blur: 0};

    // crop ui
    let cropMode = false;
    let sel = null;
    let dragging = false;
    let aspect = 'free';

    // history
    const MAX_STEPS = 20;
    const history = [];  // {src, filters, elements, transform:{zoom, panX, panY}}
    const future = [];

    // text/elements & tools
    const elements = []; // {type:'text', x,y, text, size, weight, color}
    let tool = 'move';   // 'move' | 'text'
    let hoverIndex = -1, activeIndex = -1;
    let dragDX = 0, dragDY = 0;

    // view transform
    let zoom = 1;      // 1 = fit will compute later; this is applied AFTER fit scale
    let panX = 0, panY = 0;
    let showGrid = false;

    // ------- helpers -------
    function enableEditing(on) {
        [
            resetBtn, rotL, rotR, flipH, flipV, cropModeBtn, aspectSel, fmtSel, qRange, dlBtn,
            pBW, pWarm, pCool, pVivid, applyCropBtn, cancelCropBtn
        ].forEach(el => el && (el.disabled = !on));
        Object.values(sliders).forEach(el => el && (el.disabled = !on));

        // text & nav
        [toolMove, toolText, txtSize, txtWeight, txtColor, gridToggle, fitBtn, oneBtn].forEach(el => el && (el.disabled = !on));
        updateHistoryUI();
    }

    function enablePersistence(on) {
        if (saveBtn) saveBtn.disabled = !on;
        if (openBtn) openBtn.disabled = !on;
        if (saveTitle && on && !saveTitle.value) saveTitle.value = "Untitled";
    }


    function setCanvasSize() {
        const r = stage.getBoundingClientRect();
        const w = Math.max(1, Math.floor(r.width));
        const h = Math.max(1, Math.floor(r.height));
        if (w === stageW && h === stageH) return;
        stageW = w;
        stageH = h;
        canvas.style.width = `${stageW}px`;
        canvas.style.height = `${stageH}px`;
        canvas.width = Math.floor(stageW * dpr);
        canvas.height = Math.floor(stageH * dpr);
        updateZoomReadout();
    }

    function baseFit() {
        // fit image into stage (CSS px)
        const W = stageW, H = stageH;
        const iw = img.naturalWidth || 1, ih = img.naturalHeight || 1;
        const s = Math.min(W / iw, H / ih);
        const vw = iw * s, vh = ih * s;
        const ox = (W - vw) / 2, oy = (H - vh) / 2;
        return {s, vw, vh, ox, oy};
    }

    function updateZoomReadout() {
        if (!zoomReadout) return;
        const pct = Math.round(zoom * 100);
        zoomReadout.textContent = `${pct}%`;
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
        history.push({
            src: canvas.toDataURL('image/png'), // snapshot of current composed view
            filters: {...filters},
            elements: JSON.parse(JSON.stringify(elements)),
            transform: {zoom, panX, panY}
        });
        if (history.length > MAX_STEPS) history.shift();
        future.length = 0;
        updateHistoryUI();
    }

    function restore(state) {
        // Reconstruct from state; we keep original image unchanged and just restore UI state
        Object.assign(filters, state.filters);
        elements.splice(0, elements.length, ...state.elements);
        zoom = state.transform.zoom;
        panX = state.transform.panX;
        panY = state.transform.panY;

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
        updateZoomReadout();
        draw();
    }

    function doUndo() {
        if (history.length === 0) return;
        const curr = {
            src: canvas.toDataURL('image/png'),
            filters: {...filters},
            elements: JSON.parse(JSON.stringify(elements)),
            transform: {zoom, panX, panY}
        };
        const prev = history.pop();
        future.push(curr);
        restore(prev);
    }

    function doRedo() {
        if (future.length === 0) return;
        const curr = {
            src: canvas.toDataURL('image/png'),
            filters: {...filters},
            elements: JSON.parse(JSON.stringify(elements)),
            transform: {zoom, panX, panY}
        };
        const next = future.pop();
        history.push(curr);
        restore(next);
    }

    // ------- draw pipeline -------
    function draw() {
        ctx.setTransform(1, 0, 0, 1, 0, 0);
        ctx.clearRect(0, 0, canvas.width, canvas.height);
        if (!loaded) return;

        const {s, ox, oy, vw, vh} = baseFit();

        // world transform (device pixels)
        ctx.save();
        ctx.scale(dpr, dpr);

        // translate to fit origin, then apply pan & zoom
        ctx.translate(ox + panX, oy + panY);
        ctx.scale(zoom, zoom);

        // draw image with filters at base scale s
        ctx.filter = cssFilter();
        ctx.drawImage(img, 0, 0, img.naturalWidth * s, img.naturalHeight * s);
        ctx.filter = 'none';

        // draw elements
        for (let i = 0; i < elements.length; i++) {
            const el = elements[i];
            if (el.type === 'text') {
                ctx.save();
                ctx.font = `${el.weight} ${el.size}px Inter, system-ui, sans-serif`;
                ctx.fillStyle = el.color;
                ctx.textBaseline = 'top';
                ctx.fillText(el.text, el.x, el.y);
                if (i === activeIndex) {
                    // selection box
                    const m = ctx.measureText(el.text);
                    const w = m.width, h = el.size * 1.2;
                    ctx.strokeStyle = '#ff5fb8';
                    ctx.lineWidth = 1 / zoom; // scale-aware
                    ctx.strokeRect(el.x - 2, el.y - 2, w + 4, h + 4);
                }
                ctx.restore();
            }
        }

        ctx.restore();

        // (optional) grid overlay
        if (showGrid) {
            if (!$('.grid-overlay')) {
                const div = document.createElement('div');
                div.className = 'grid-overlay';
                stage.appendChild(div);
            }
        } else {
            $('.grid-overlay')?.remove();
        }
    }

    // convert stage coords -> document coords under fit+transform
    function toDoc(x, y) {
        const {s, ox, oy} = baseFit();
        const dx = (x - ox - panX);
        const dy = (y - oy - panY);
        return {x: dx / zoom, y: dy / zoom, baseScale: s};
    }

    // ------- loading/reset -------
    function loadFromFile(file) {
        const url = URL.createObjectURL(file);
        originalURL = url;
        const imgNew = new Image();
        imgNew.onload = () => {
            img = imgNew;
            loaded = true;
            hint && (hint.style.display = 'none');
            cropMode = false;
            sel = null;
            elements.length = 0;
            tool = 'move';
            zoom = 1;
            panX = 0;
            panY = 0;
            resetFilters(false);
            snapshot();
            fitToScreen();
            draw();
            enableEditing(true);
            enablePersistence(true);
        };
        imgNew.src = url;
    }

    function resetAll() {
        if (!originalURL) return;
        snapshot();
        const imgNew = new Image();
        imgNew.onload = () => {
            img = imgNew;
            loaded = true;
            cropMode = false;
            sel = null;
            elements.length = 0;
            tool = 'move';
            resetFilters(false);
            fitToScreen();
            snapshot();
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

    // ------- transforms (baked) -------
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

    // ------- crop -------
    function applyCrop() {
        if (!sel || !loaded) return;
        const {s, ox, oy} = baseFit();
        // convert CSS px selection → image pixels through fit scale (not zoom/pan because we draw crop over stage)
        const ix = Math.max(0, Math.round((sel.x - ox) / s));
        const iy = Math.max(0, Math.round((sel.y - oy) / s));
        const iw = Math.max(1, Math.round(sel.w / s));
        const ih = Math.max(1, Math.round(sel.h / s));

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
        elements.length = 0; // elements are invalid after crop (simplify v1)
        fitToScreen();
    }

    function startCrop() {
        cropMode = true;
        sel = null;
        draw();
    }

    // ------- zoom/pan -------
    function fitToScreen() {
        zoom = 1;
        panX = panY = 0;
        updateZoomReadout();
        draw();
    }

    function setZoom(newZ, cx, cy) {
        newZ = Math.max(0.1, Math.min(8, newZ));
        const {s, ox, oy} = baseFit();
        const oldZ = zoom;
        const worldX = (cx - ox - panX) / oldZ;
        const worldY = (cy - oy - panY) / oldZ;
        zoom = newZ;
        panX = cx - ox - worldX * newZ;
        panY = cy - oy - worldY * newZ;
        updateZoomReadout();
        draw();
    }


    // ------- events -------
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

    // crop drag
    stage.addEventListener('mousedown', (e) => {
        if (tool === 'move' && (e.button === 1 || e.buttons === 4)) {
            // middle-mouse pans like hand
            dragging = true;
            dragDX = e.clientX;
            dragDY = e.clientY;
            stage.style.cursor = 'grabbing';
            return;
        }
        if (!cropMode || !loaded) return;
        const r = stage.getBoundingClientRect();
        const sx = e.clientX - r.left, sy = e.clientY - r.top;
        sel = {x: sx, y: sy, w: 0, h: 0};
        dragging = true;
        draw();
    });
    stage.addEventListener('mousemove', (e) => {
        if (dragging && tool === 'move' && !cropMode) {
            panX += (e.clientX - dragDX);
            panY += (e.clientY - dragDY);
            dragDX = e.clientX;
            dragDY = e.clientY;
            draw();
            return;
        }
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
        // normalize
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
        if (dragging && tool === 'move' && !cropMode) {
            stage.style.cursor = '';
        }
        dragging = false;
    });

    // wheel zoom (cmd/ctrl+wheel also works on most OS; we’ll keep simple)
    stage.addEventListener('wheel', (e) => {
        if (!loaded) return;
        e.preventDefault();
        const factor = e.deltaY < 0 ? 1.1 : 0.9;
        setZoom(zoom * factor, e.clientX - r.left, e.clientY - r.top);
    }, {passive: false});

    // space = temporary hand tool
    let spaceHeld = false;
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
        if (e.code === 'Space' && !spaceHeld) {
            spaceHeld = true;
            tool = 'move';
            stage.style.cursor = 'grab';
        }
    });
    window.addEventListener('keyup', (e) => {
        if (e.code === 'Space') {
            spaceHeld = false;
            stage.style.cursor = '';
        }
    });

    // sliders
    function setValLabel(key, v, unit) {
        vals[key].textContent = unit === 'deg' ? `${v}°` : unit === 'px' ? `${v}px` : `${v}%`;
    }

    function bindRange(key, unit) {
        sliders[key]?.addEventListener('input', (e) => {
            const v = Number(e.target.value);
            filters[key] = v;
            setValLabel(key, v, unit);
            draw();
        });
        sliders[key]?.addEventListener('change', () => snapshot());
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
        ['gra', 'sep', 'sat', 'hue', 'bri', 'con'].forEach(k => sliders[k].dispatchEvent(new Event('input')));
    }

    [pBW, pWarm, pCool, pVivid].forEach(btn => btn?.addEventListener('click', () => applyPreset(btn.dataset.preset)));

    // export
    qRange?.addEventListener('input', e => {
        qVal.textContent = e.target.value;
    });
    dlBtn?.addEventListener('click', () => {
        if (!loaded) return;
        // re-render at image resolution with filters & elements
        const off = document.createElement('canvas');
        off.width = img.naturalWidth;
        off.height = img.naturalHeight;
        const c = off.getContext('2d');

        c.filter = cssFilter();
        c.drawImage(img, 0, 0);
        c.filter = 'none';

        // paint elements in image pixel space: scale positions from baseFit.s
        const {s} = baseFit();
        c.save();
        c.scale(1 / s, 1 / s); // invert base scaling to map our screen coords back to image px
        elements.forEach(el => {
            if (el.type === 'text') {
                c.font = `${el.weight} ${el.size}px Inter, system-ui, sans-serif`;
                c.fillStyle = el.color;
                c.textBaseline = 'top';
                c.fillText(el.text, el.x, el.y);
            }
        });
        c.restore();

        const mime = fmtSel.value;
        const q = Number(qRange.value) / 100;
        const url = off.toDataURL(mime, q);
        const a = document.createElement('a');
        a.href = url;
        a.download = mime === 'image/png' ? 'bambicim-edit.png' : 'bambicim-edit.jpg';
        a.click();
    });

    // tools
    toolMove?.addEventListener('click', () => {
        tool = 'move';
    });
    toolText?.addEventListener('click', () => {
        tool = 'text';
    });

    gridToggle?.addEventListener('click', () => {
        showGrid = !showGrid;
        draw();
    });
    fitBtn?.addEventListener('click', () => {
        fitToScreen();
    });
    oneBtn?.addEventListener('click', () => {
        setZoom(1, stageW / 2, stageH / 2);
    });

    // placing & dragging text
    stage.addEventListener('click', (e) => {
        if (!loaded) return;
        if (cropMode) return;
        if (tool !== 'text') return;

        const r = stage.getBoundingClientRect();
        const {x, y} = toDoc(e.clientX - r.left + 0, e.clientY - r.top + 0);
        const el = {
            type: 'text',
            x, y,
            text: 'Your text',
            size: Number(txtSize.value || 32),
            weight: String(txtWeight.value || '600'),
            color: String(txtColor.value || '#ffffff')
        };
        elements.push(el);
        activeIndex = elements.length - 1;
        snapshot();
        draw();
    });

    stage.addEventListener('mousedown', (e) => {
        if (!loaded || cropMode) return;
        if (tool === 'text') {
            // begin dragging active text if clicked inside
            const hit = hitTestText(e);
            if (hit.index !== -1) {
                activeIndex = hit.index;
                dragging = true;
                dragDX = e.clientX;
                dragDY = e.clientY;
            }
        }
    });
    stage.addEventListener('mousemove', (e) => {
        if (!loaded || cropMode) return;
        if (tool === 'text' && dragging && activeIndex !== -1) {
            const dx = (e.clientX - dragDX) / (zoom); // scale-aware
            const dy = (e.clientY - dragDY) / (zoom);
            elements[activeIndex].x += dx;
            elements[activeIndex].y += dy;
            dragDX = e.clientX;
            dragDY = e.clientY;
            draw();
        }
    });
    window.addEventListener('mouseup', () => {
        if (dragging && tool === 'text') {
            snapshot();
        }
        dragging = false;
    });

    // double-click to edit text
    stage.addEventListener('dblclick', (e) => {
        if (!loaded || cropMode) return;
        const hit = hitTestText(e);
        if (hit.index === -1) return;
        const el = elements[hit.index];
        const text = prompt('Edit text:', el.text);
        if (text != null) {
            el.text = text;
            snapshot();
            draw();
        }
    });

    function hitTestText(e) {
        const r = stage.getBoundingClientRect();
        const pt = toDoc(e.clientX - r.left, e.clientY - r.top);
        const {s} = baseFit();
        // we measure in current canvas transform; approximate bounding boxes
        for (let i = elements.length - 1; i >= 0; i--) {
            const el = elements[i];
            if (el.type !== 'text') continue;
            // measure using an offscreen 2d context at 1:1
            ctx.save();
            ctx.font = `${el.weight} ${el.size}px Inter, system-ui, sans-serif`;
            const w = ctx.measureText(el.text).width;
            ctx.restore();
            const h = el.size * 1.2;
            const within = (pt.x >= el.x && pt.x <= el.x + w) && (pt.y >= el.y && pt.y <= el.y + h);
            if (within) return {index: i};
        }
        return {index: -1};
    }

    // init
    enableEditing(false);
    setCanvasSize();
    const ro = new ResizeObserver(() => {
        setCanvasSize();
        draw();
    });
    ro.observe(stage);
    window.addEventListener('resize', () => {
        setCanvasSize();
        draw();
    });

    // ---- Server integration (minimal v1) ----
    let currentEditId = null;
    let currentSourceId = null;

    function getCSRF() {
        const name = 'csrftoken';
        const m = document.cookie.match(new RegExp('(^| )' + name + '=([^;]+)'));
        return m ? m[2] : '';
    }

    function collectState() {
        const state = {
            filters,
            elements,
            transform: {zoom, panX, panY},
        };
        return {
            title: (saveTitle && saveTitle.value) || "Untitled",
            state,
            width: (img && img.naturalWidth) || 0,
            height: (img && img.naturalHeight) || 0,
            format: (fmtSel && fmtSel.value) || 'image/png',
            quality: (qRange && Number(qRange.value)) || 92,
            source_id: currentSourceId || undefined,
            id: currentEditId || undefined,
        };
    }

    document.querySelector('#fileInput')?.addEventListener('change', async (e) => {
        const f = e.target.files && e.target.files[0];
        if (!f) return;
        try {
            const form = new FormData();
            form.append('file', f);
            const res = await fetch('/editor/api/upload', {
                method: 'POST',
                body: form,
                headers: {'X-CSRFToken': getCSRF()},
                credentials: 'same-origin'
            });
            if (res.ok) {
                const j = await res.json();
                currentSourceId = j.id;
            }
        } catch (_) {
        }
    }, {once: false});

    saveBtn?.addEventListener('click', async () => {
        const payload = collectState();
        const res = await fetch('/editor/api/save', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'X-CSRFToken': getCSRF()
            },
            body: JSON.stringify(payload),
            credentials: 'same-origin'
        });
        if (!res.ok) return alert('Save failed');
        const j = await res.json();
        currentEditId = j.id;
        alert('Saved ✓');
    });

    openBtn?.addEventListener('click', async () => {
        const res = await fetch('/editor/api/list', {credentials: 'same-origin'});
        if (!res.ok) return alert('Open failed');
        const j = await res.json();
        if (!j.items?.length) return alert('No edits yet');
        const choice = prompt('Open which id?\n' + j.items.map(i => `${i.id}: ${i.title}`).join('\n'));
        if (!choice) return;
        const picked = j.items.find(i => String(i.id) === String(choice));
        if (!picked) return alert('Not found');
        alert('For v1 this is meta-only; add /editor/api/get?id=… to restore full state.');
    });

    (async () => {
        try {
            const res = await fetch('/editor/api/presets');
            if (res.ok) {
                const j = await res.json();
                window.BAMBICIM_PRESETS = j.presets || [];
            }
        } catch (_) {
        }
    })();

})();
