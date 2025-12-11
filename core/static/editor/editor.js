(() => {
    // ------- helpers -------
    const $ = (s) => document.querySelector(s);
    const $$ = (s) => document.querySelectorAll(s);
    const dpr = Math.max(1, window.devicePixelRatio || 1);
    const isAuth = (window.BMB_AUTH === true || window.BMB_AUTH === 'true');

    // ------- DOM -------
    const fileInput = $('#fileInput');
    const resetBtn = $('#resetBtn');
    const rotL = $('#rotL'), rotR = $('#rotR'), flipH = $('#flipH'), flipV = $('#flipV');
    const cropModeBtn = $('#cropMode'), applyCropBtn = $('#applyCrop'), cancelCropBtn = $('#cancelCrop');
    const aspectSel = $('#aspect');
    const fmtSel = $('#fmt'), qRange = $('#quality'), qVal = $('#qv'), dlBtn = $('#downloadBtn');
    const pBW = $('#p_bw'), pWarm = $('#p_warm'), pCool = $('#p_cool'), pVivid = $('#p_vivid');
    const undoBtn = $('#undoBtn'), redoBtn = $('#redoBtn');

    const toolMove = $('#toolMove'), toolText = $('#toolText');
    const txtSize = $('#txtSize'), txtWeight = $('#txtWeight'), txtColor = $('#txtColor');
    const gridToggle = $('#gridToggle'), zoomReadout = $('#zoomReadout'), fitBtn = $('#fitBtn'), oneBtn = $('#oneBtn');

    const layerList = $('#layerList');
    const layerUpBtn = $('#layerUp');
    const layerDownBtn = $('#layerDown');
    const layerDeleteBtn = $('#layerDelete');

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

    // persistence DOM (kept but hidden in template, safe to ignore)
    const saveBtn = $('#saveBtn');
    const openBtn = $('#openBtn');
    const saveTitle = $('#saveTitle');

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

    // layers = text elements (for now)
    const elements = []; // {type:'text', x,y, text, size, weight, color, visible, name}
    let tool = 'move';   // 'move' | 'text'
    let activeIndex = -1;
    let dragDX = 0, dragDY = 0;

    // view transform
    let zoom = 1;
    let panX = 0, panY = 0;
    let showGrid = false;

    // ------- gating -------
    function enableEditing(on) {
        [
            resetBtn, rotL, rotR, flipH, flipV,
            cropModeBtn, aspectSel, fmtSel, qRange, dlBtn,
            pBW, pWarm, pCool, pVivid, applyCropBtn, cancelCropBtn,
            toolMove, toolText, txtSize, txtWeight, txtColor,
            gridToggle, fitBtn, oneBtn,
            layerUpBtn, layerDownBtn, layerDeleteBtn
        ].forEach(el => el && (el.disabled = !on));
        updateHistoryUI();
    }

    function enablePersistence(on) {
        const allow = on && isAuth;
        if (saveBtn) saveBtn.disabled = !allow;
        if (openBtn) openBtn.disabled = !allow;
        if (saveTitle && allow && !saveTitle.value) saveTitle.value = "Untitled";
    }

    // ------- sizing & fit -------
    function setCanvasSize() {
        const r = stage.getBoundingClientRect();
        const w = Math.max(1, Math.floor(r.width));
        const h = Math.max(1, Math.floor(r.height));
        canvas.style.width = `${w}px`;
        canvas.style.height = `${h}px`;
        canvas.width = Math.floor(w * dpr);
        canvas.height = Math.floor(h * dpr);
        stageW = w;
        stageH = h;
        updateZoomReadout();
    }

    function baseFit() {
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
            src: canvas.toDataURL('image/png'),
            filters: {...filters},
            elements: JSON.parse(JSON.stringify(elements)),
            transform: {zoom, panX, panY}
        });
        if (history.length > MAX_STEPS) history.shift();
        future.length = 0;
        updateHistoryUI();
    }

    function restore(state) {
        Object.assign(filters, state.filters || {});
        elements.splice(0, elements.length, ...((state.elements || [])));
        zoom = (state.transform && state.transform.zoom) || 1;
        panX = (state.transform && state.transform.panX) || 0;
        panY = (state.transform && state.transform.panY) || 0;

        if (sliders.bri) sliders.bri.value = filters.bri, vals.bri.textContent = `${filters.bri}%`;
        if (sliders.con) sliders.con.value = filters.con, vals.con.textContent = `${filters.con}%`;
        if (sliders.sat) sliders.sat.value = filters.sat, vals.sat.textContent = `${filters.sat}%`;
        if (sliders.hue) sliders.hue.value = filters.hue, vals.hue.textContent = `${filters.hue}°`;
        if (sliders.sep) sliders.sep.value = filters.sep, vals.sep.textContent = `${filters.sep}%`;
        if (sliders.gra) sliders.gra.value = filters.gra, vals.gra.textContent = `${filters.gra}%`;
        if (sliders.blur) sliders.blur.value = filters.blur, vals.blur.textContent = `${filters.blur}px`;

        refreshLayersUI();
        updateZoomReadout();
        draw();
    }

    // ------- Layers UI -------
    function refreshLayersUI() {
        if (!layerList) return;
        layerList.innerHTML = '';
        if (!elements.length) {
            const li = document.createElement('li');
            li.className = 'layer-item';
            li.textContent = 'Henüz metin katmanı yok';
            layerList.appendChild(li);
            layerUpBtn && (layerUpBtn.disabled = true);
            layerDownBtn && (layerDownBtn.disabled = true);
            layerDeleteBtn && (layerDeleteBtn.disabled = true);
            return;
        }

        // top layer en üstte görünsün (Photopea gibi)
        for (let idx = elements.length - 1; idx >= 0; idx--) {
            const el = elements[idx];
            const li = document.createElement('li');
            li.className = 'layer-item' + (idx === activeIndex ? ' is-active' : '');
            li.dataset.index = String(idx);

            const eye = document.createElement('button');
            eye.type = 'button';
            eye.className = 'layer-eye';
            eye.textContent = el.visible === false ? '🚫' : '👁';
            eye.addEventListener('click', (e) => {
                e.stopPropagation();
                el.visible = !(el.visible === false);
                refreshLayersUI();
                draw();
            });

            const label = document.createElement('span');
            label.textContent = el.name || `Metin ${idx + 1}`;

            li.appendChild(eye);
            li.appendChild(label);
            li.addEventListener('click', () => {
                activeIndex = idx;
                syncTextControls();
                refreshLayersUI();
            });

            layerList.appendChild(li);
        }

        const anyActive = activeIndex >= 0 && activeIndex < elements.length;
        layerUpBtn && (layerUpBtn.disabled = !anyActive);
        layerDownBtn && (layerDownBtn.disabled = !anyActive);
        layerDeleteBtn && (layerDeleteBtn.disabled = !anyActive);
    }

    function moveLayer(delta) {
        if (activeIndex === -1) return;
        const j = activeIndex + delta;
        if (j < 0 || j >= elements.length) return;
        const tmp = elements[activeIndex];
        elements[activeIndex] = elements[j];
        elements[j] = tmp;
        activeIndex = j;
        snapshot();
        refreshLayersUI();
        draw();
    }

    function deleteLayer() {
        if (activeIndex === -1) return;
        elements.splice(activeIndex, 1);
        if (elements.length === 0) {
            activeIndex = -1;
        } else if (activeIndex >= elements.length) {
            activeIndex = elements.length - 1;
        }
        snapshot();
        refreshLayersUI();
        draw();
    }

    layerUpBtn?.addEventListener('click', () => moveLayer(1));   // dizide ileri = üstte görünür
    layerDownBtn?.addEventListener('click', () => moveLayer(-1));
    layerDeleteBtn?.addEventListener('click', deleteLayer);

    // ------- draw pipeline -------
    function draw() {
        ctx.setTransform(1, 0, 0, 1, 0, 0);
        ctx.clearRect(0, 0, canvas.width, canvas.height);
        if (!loaded) return;

        const {s, ox, oy} = baseFit();

        ctx.save();
        ctx.scale(dpr, dpr);
        ctx.translate(ox + panX, oy + panY);
        ctx.scale(zoom, zoom);

        ctx.filter = cssFilter();
        ctx.drawImage(img, 0, 0, img.naturalWidth * s, img.naturalHeight * s);
        ctx.filter = 'none';

        // elements (layers)
        for (let i = 0; i < elements.length; i++) {
            const el = elements[i];
            if (el.visible === false) continue;
            if (el.type === 'text') {
                ctx.save();
                ctx.font = `${el.weight} ${el.size}px Inter, system-ui, sans-serif`;
                ctx.fillStyle = el.color;
                ctx.textBaseline = 'top';
                ctx.fillText(el.text, el.x, el.y);
                ctx.restore();
            }
        }

        ctx.restore();

        // grid overlay DOM (sticky over stage)
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

    function toDoc(x, y) {
        const {s, ox, oy} = baseFit();
        const dx = (x - ox - panX);
        const dy = (y - oy - panY);
        return {x: dx / zoom, y: dy / zoom, baseScale: s};
    }

    // ------- load/reset -------
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
            activeIndex = -1;
            tool = 'move';
            zoom = 1;
            panX = 0;
            panY = 0;
            resetFilters(false);
            snapshot();
            fitToScreen();
            draw();
            enableEditing(true);
            enablePersistence(true); // UI yok ama fonksiyon zarar vermez
            refreshLayersUI();
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
            activeIndex = -1;
            tool = 'move';
            resetFilters(false);
            fitToScreen();
            snapshot();
            draw();
            refreshLayersUI();
        };
        imgNew.src = originalURL;
    }

    function resetFilters(alsoDraw = true) {
        Object.assign(filters, {bri: 100, con: 100, sat: 100, hue: 0, sep: 0, gra: 0, blur: 0});
        if (sliders.bri) sliders.bri.value = 100, vals.bri.textContent = '100%';
        if (sliders.con) sliders.con.value = 100, vals.con.textContent = '100%';
        if (sliders.sat) sliders.sat.value = 100, vals.sat.textContent = '100%';
        if (sliders.hue) sliders.hue.value = 0, vals.hue.textContent = '0°';
        if (sliders.sep) sliders.sep.value = 0, vals.sep.textContent = '0%';
        if (sliders.gra) sliders.gra.value = 0, vals.gra.textContent = '0%';
        if (sliders.blur) sliders.blur.value = 0, vals.blur.textContent = '0px';
        if (alsoDraw) draw();
    }

    // ------- transforms -------
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
        elements.length = 0;
        activeIndex = -1;
        fitToScreen();
        refreshLayersUI();
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

    // ------- events: file, drag/drop -------
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

    // crop drag & pan
    stage.addEventListener('mousedown', (e) => {
        if (tool === 'move' && (e.button === 1 || e.buttons === 4 || e.code === 'Space')) {
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
        if (dragging && tool === 'move' && !cropMode) stage.style.cursor = '';
        dragging = false;
    });

    stage.addEventListener('wheel', (e) => {
        if (!loaded) return;
        e.preventDefault();
        const r = stage.getBoundingClientRect();
        const factor = e.deltaY < 0 ? 1.1 : 0.9;
        setZoom(zoom * factor, e.clientX - r.left, e.clientY - r.top);
    }, {passive: false});

    // history hotkeys
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
        if (e.code === 'Space') {
            stage.style.cursor = 'grab';
        }
    });
    window.addEventListener('keyup', (e) => {
        if (e.code === 'Space') stage.style.cursor = '';
    });

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

    // sliders
    function label(key, v, unit) {
        vals[key].textContent = unit === 'deg' ? `${v}°` : unit === 'px' ? `${v}px` : `${v}%`;
    }

    function bindRange(key, unit) {
        sliders[key]?.addEventListener('input', (e) => {
            const v = Number(e.target.value);
            filters[key] = v;
            label(key, v, unit);
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
        const off = document.createElement('canvas');
        off.width = img.naturalWidth;
        off.height = img.naturalHeight;
        const c = off.getContext('2d');

        c.filter = cssFilter();
        c.drawImage(img, 0, 0);
        c.filter = 'none';

        const {s} = baseFit();
        c.save();
        c.scale(1 / s, 1 / s);
        elements.forEach(el => {
            if (el.visible === false) return;
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

    // tools & text
    function setTool(t) {
        tool = t;
        toolMove && toolMove.classList.toggle('btn-primary', t === 'move');
        toolText && toolText.classList.toggle('btn-primary', t === 'text');
    }

    toolMove?.addEventListener('click', () => setTool('move'));
    toolText?.addEventListener('click', () => setTool('text'));

    function syncTextControls() {
        if (activeIndex === -1 || activeIndex >= elements.length) return;
        const el = elements[activeIndex];
        if (txtSize) txtSize.value = el.size;
        if (txtWeight) txtWeight.value = el.weight;
        if (txtColor) txtColor.value = el.color;
    }

    txtSize?.addEventListener('change', () => {
        if (activeIndex === -1) return;
        const v = Number(txtSize.value || 32);
        elements[activeIndex].size = v;
        snapshot();
        draw();
    });
    txtWeight?.addEventListener('change', () => {
        if (activeIndex === -1) return;
        elements[activeIndex].weight = String(txtWeight.value || '600');
        snapshot();
        draw();
    });
    txtColor?.addEventListener('change', () => {
        if (activeIndex === -1) return;
        elements[activeIndex].color = String(txtColor.value || '#ffffff');
        snapshot();
        draw();
    });

    gridToggle?.addEventListener('click', () => {
        showGrid = !showGrid;
        gridToggle.classList.toggle('btn-primary', showGrid);
        draw();
    });
    fitBtn?.addEventListener('click', () => fitToScreen());
    oneBtn?.addEventListener('click', () => setZoom(1, stageW / 2, stageH / 2));

    // text placement & dragging
    stage.addEventListener('click', (e) => {
        if (!loaded || cropMode || tool !== 'text') return;
        const r = stage.getBoundingClientRect();
        const {x, y} = toDoc(e.clientX - r.left, e.clientY - r.top);
        const el = {
            type: 'text',
            x,
            y,
            text: 'Metin',
            size: Number(txtSize?.value || 32),
            weight: String(txtWeight?.value || '600'),
            color: String(txtColor?.value || '#ffffff'),
            visible: true,
            name: `Metin ${elements.length + 1}`
        };
        elements.push(el);
        activeIndex = elements.length - 1;
        syncTextControls();
        snapshot();
        refreshLayersUI();
        draw();
    });

    stage.addEventListener('mousedown', (e) => {
        if (!loaded || cropMode) return;
        if (tool === 'text' && activeIndex !== -1) {
            dragDX = e.clientX;
            dragDY = e.clientY;
            dragging = true;
        }
    });

    stage.addEventListener('mousemove', (e) => {
        if (!loaded || cropMode) return;
        if (tool === 'text' && dragging && activeIndex !== -1) {
            elements[activeIndex].x += (e.clientX - dragDX) / zoom;
            elements[activeIndex].y += (e.clientY - dragDY) / zoom;
            dragDX = e.clientX;
            dragDY = e.clientY;
            draw();
        }
    });

    window.addEventListener('mouseup', () => {
        if (dragging && tool === 'text') snapshot();
        dragging = false;
    });

    // ---- (optional) backend integration kept but unused ----
    let currentEditId = null;
    let currentSourceId = null;

    function getCSRF() {
        const name = 'csrftoken';
        const m = document.cookie.match(new RegExp('(^| )' + name + '=([^;]+)'));
        return m ? m[2] : '';
    }

    function collectState() {
        const state = {filters, elements, transform: {zoom, panX, panY}};
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

    // (asset upload & save/open event handlers remain here if you re-enable UI later)

    // init
    enableEditing(false);
    enablePersistence(false);
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

    refreshLayersUI();
})();
