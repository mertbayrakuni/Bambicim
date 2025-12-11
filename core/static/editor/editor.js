(() => {
    // ------- helpers -------
    const $ = (s) => document.querySelector(s);
    const dpr = Math.max(1, window.devicePixelRatio || 1);

    // ------- DOM -------
    const stage = $('.ed-stage');
    const canvas = $('#preview');
    const ctx = canvas.getContext('2d');
    const hint = $('#hint');
    const txtContent = $('#txtContent');

    const fileInput = $('#fileInput');
    const resetBtn = $('#resetBtn');

    const rotL = $('#rotL');
    const rotR = $('#rotR');
    const flipH = $('#flipH');
    const flipV = $('#flipV');

    const cropModeBtn = $('#cropMode');
    const applyCropBtn = $('#applyCrop');
    const cancelCropBtn = $('#cancelCrop');
    const aspectSel = $('#aspect');

    const fmtSel = $('#fmt');
    const qRange = $('#quality');
    const qVal = $('#qv');
    const dlBtn = $('#downloadBtn');

    const undoBtn = $('#undoBtn');
    const redoBtn = $('#redoBtn');

    const gridToggle = $('#gridToggle');
    const zoomReadout = $('#zoomReadout');
    const fitBtn = $('#fitBtn');
    const oneBtn = $('#oneBtn');

    const toolMove = $('#toolMove');
    const toolText = $('#toolText');
    const txtSize = $('#txtSize');
    const txtWeight = $('#txtWeight');
    const txtColor = $('#txtColor');

    const layerList = $('#layerList');
    const layerUpBtn = $('#layerUp');
    const layerDownBtn = $('#layerDown');
    const layerDeleteBtn = $('#layerDelete');

    const sliders = {
        bri: $('#s_bri'),
        con: $('#s_con'),
        sat: $('#s_sat'),
        hue: $('#s_hue'),
        sep: $('#s_sep'),
        gra: $('#s_gra'),
        blur: $('#s_blur')
    };
    const vals = {
        bri: $('#v_bri'),
        con: $('#v_con'),
        sat: $('#v_sat'),
        hue: $('#v_hue'),
        sep: $('#v_sep'),
        gra: $('#v_gra'),
        blur: $('#v_blur')
    };

    const pBW = $('#p_bw');
    const pWarm = $('#p_warm');
    const pCool = $('#p_cool');
    const pVivid = $('#p_vivid');

    // ------- STATE -------
    let stageW = 1;
    let stageH = 1;

    let img = new Image();
    let imgUrl = null;
    let loaded = false;

    const filters = {
        bri: 100,
        con: 100,
        sat: 100,
        hue: 0,
        sep: 0,
        gra: 0,
        blur: 0
    };

    // zoom / pan
    let zoom = 1;
    let panX = 0;
    let panY = 0;
    let showGrid = false;

    // crop
    let cropMode = false;
    let cropRect = null;     // sahne koordinatlarında {sx,sy,sw,sh}
    let dragKind = null;     // 'pan' | 'crop' | 'text'
    let dragSX = 0, dragSY = 0;

    // elements (layers) in IMAGE coordinates
    // {type:'text', x, y, text, size, weight, color, visible, name}
    const elements = [];
    let activeIndex = -1;
    let tool = 'move';       // 'move' | 'text'

    // history (for undo/redo)
    const MAX_STEPS = 20;
    const history = [];
    const future = [];

    // offscreen canvas for text measurement
    const offCanvas = document.createElement('canvas');
    const offCtx = offCanvas.getContext('2d');

    // ------- layout / canvas size -------
    function setNavH() {
        const h = document.querySelector('.site-header');
        if (h) document.documentElement.style.setProperty('--nav-h', (h.offsetHeight || 88) + 'px');
    }

    function setCanvasSize() {
        const r = stage.getBoundingClientRect();
        const w = Math.max(1, Math.floor(r.width));
        const h = Math.max(1, Math.floor(r.height));
        stageW = w;
        stageH = h;
        canvas.style.width = w + 'px';
        canvas.style.height = h + 'px';
        canvas.width = Math.floor(w * dpr);
        canvas.height = Math.floor(h * dpr);
        updateZoomReadout();
        draw();
    }

    function baseFit() {
        const W = stageW, H = stageH;
        const iw = img.naturalWidth || 1;
        const ih = img.naturalHeight || 1;
        const s = Math.min(W / iw, H / ih);
        const vw = iw * s;
        const vh = ih * s;
        const ox = (W - vw) / 2;
        const oy = (H - vh) / 2;
        return {s, ox, oy};
    }

    // stage (screen) -> image pixel coordinates
    function stageToImage(sx, sy) {
        const {s, ox, oy} = baseFit();
        const dx = (sx - ox - panX) / zoom;
        const dy = (sy - oy - panY) / zoom;
        const ix = dx / s;
        const iy = dy / s;
        return {ix, iy, s};
    }

    function updateZoomReadout() {
        if (!zoomReadout) return;
        zoomReadout.textContent = `${Math.round(zoom * 100)}%`;
    }

    // ------- filters -------
    function cssFilter() {
        return `brightness(${filters.bri}%) contrast(${filters.con}%) saturate(${filters.sat}%) `
            + `hue-rotate(${filters.hue}deg) sepia(${filters.sep}%) `
            + `grayscale(${filters.gra}%) blur(${filters.blur}px)`;
    }

    function resetFilters(drawNow = true) {
        filters.bri = 100;
        filters.con = 100;
        filters.sat = 100;
        filters.hue = 0;
        filters.sep = 0;
        filters.gra = 0;
        filters.blur = 0;

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

        if (drawNow) draw();
    }

    // ------- history -------
    function updateHistoryUI() {
        if (undoBtn) undoBtn.disabled = history.length === 0;
        if (redoBtn) redoBtn.disabled = future.length === 0;
    }

    function snapshot() {
        if (!loaded) return;
        const state = {
            src: canvas.toDataURL('image/png'),
            filters: {...filters},
            elements: JSON.parse(JSON.stringify(elements)),
            transform: {zoom, panX, panY}
        };
        history.push(state);
        if (history.length > MAX_STEPS) history.shift();
        future.length = 0;
        updateHistoryUI();
    }

    function restore(state) {
        const imgNew = new Image();
        imgNew.onload = () => {
            img = imgNew;
            Object.assign(filters, state.filters || {});
            elements.splice(0, elements.length, ...(state.elements || []));
            zoom = (state.transform && state.transform.zoom) || 1;
            panX = (state.transform && state.transform.panX) || 0;
            panY = (state.transform && state.transform.panY) || 0;
            cropMode = false;
            cropRect = null;
            activeIndex = -1;
            syncFilterUI();
            refreshLayersUI();
            updateZoomReadout();
            draw();
        };
        imgNew.src = state.src;
    }

    function syncFilterUI() {
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
        updateHistoryUI();
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
        updateHistoryUI();
    }

    // ------- layers UI -------
    function refreshLayersUI() {
        if (!layerList) return;
        layerList.innerHTML = '';

        if (!elements.length) {
            const li = document.createElement('li');
            li.className = 'layer-item';
            li.textContent = 'Henüz metin katmanı yok';
            layerList.appendChild(li);
            layerUpBtn.disabled = layerDownBtn.disabled = layerDeleteBtn.disabled = true;
            return;
        }

        // son eklenen en üstte
        for (let i = elements.length - 1; i >= 0; i--) {
            const el = elements[i];
            const li = document.createElement('li');
            li.className = 'layer-item' + (i === activeIndex ? ' is-active' : '');
            li.dataset.index = String(i);

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
            label.textContent = el.name || `Metin ${i + 1}`;

            li.appendChild(eye);
            li.appendChild(label);
            li.addEventListener('click', () => {
                activeIndex = i;
                syncTextControls();
                refreshLayersUI();
            });

            layerList.appendChild(li);
        }

        const hasActive = activeIndex >= 0 && activeIndex < elements.length;
        layerUpBtn.disabled = !hasActive;
        layerDownBtn.disabled = !hasActive;
        layerDeleteBtn.disabled = !hasActive;
    }

    function moveLayer(delta) {
        if (activeIndex < 0 || activeIndex >= elements.length) return;
        const j = activeIndex + delta;
        if (j < 0 || j >= elements.length) return;
        snapshot();
        const tmp = elements[activeIndex];
        elements[activeIndex] = elements[j];
        elements[j] = tmp;
        activeIndex = j;
        refreshLayersUI();
        draw();
    }

    function deleteLayer() {
        if (activeIndex < 0 || activeIndex >= elements.length) return;
        snapshot();
        elements.splice(activeIndex, 1);
        if (!elements.length) activeIndex = -1;
        else if (activeIndex >= elements.length) activeIndex = elements.length - 1;
        refreshLayersUI();
        draw();
    }

    layerUpBtn?.addEventListener('click', () => moveLayer(1));   // listede aşağı ama görüntüde yukarı
    layerDownBtn?.addEventListener('click', () => moveLayer(-1));
    layerDeleteBtn?.addEventListener('click', deleteLayer);

    // ------- draw -------
    function draw() {
        ctx.setTransform(1, 0, 0, 1, 0, 0);
        ctx.clearRect(0, 0, canvas.width, canvas.height);
        if (!loaded) return;

        const {s, ox, oy} = baseFit();

        ctx.save();
        ctx.scale(dpr, dpr);
        ctx.translate(ox + panX, oy + panY);
        ctx.scale(zoom, zoom);
        ctx.scale(s, s);

        // image
        ctx.filter = cssFilter();
        ctx.drawImage(img, 0, 0);
        ctx.filter = 'none';

        // text layers
        elements.forEach((el) => {
            if (el.visible === false) return;
            if (el.type === 'text') {
                ctx.save();
                ctx.font = `${el.weight} ${el.size}px Inter, system-ui, sans-serif`;
                ctx.fillStyle = el.color;
                ctx.textBaseline = 'top';
                ctx.fillText(el.text, el.x, el.y);
                ctx.restore();
            }
        });

        ctx.restore();

        // grid overlay via DOM
        if (showGrid) {
            if (!stage.querySelector('.grid-overlay')) {
                const div = document.createElement('div');
                div.className = 'grid-overlay';
                stage.appendChild(div);
            }
        } else {
            stage.querySelector('.grid-overlay')?.remove();
        }

        // crop overlay via DOM
        stage.querySelector('.crop-rect')?.remove();
        if (cropMode && cropRect) {
            const div = document.createElement('div');
            div.className = 'crop-rect';
            div.style.left = `${cropRect.sx}px`;
            div.style.top = `${cropRect.sy}px`;
            div.style.width = `${cropRect.sw}px`;
            div.style.height = `${cropRect.sh}px`;
            stage.appendChild(div);
        }
    }

    // ------- enable / disable -------
    function enableEditing(on) {
        [
            resetBtn, rotL, rotR, flipH, flipV,
            cropModeBtn, applyCropBtn, cancelCropBtn, aspectSel,
            fmtSel, qRange, dlBtn,
            gridToggle, fitBtn, oneBtn,
            undoBtn, redoBtn,
            toolMove, toolText,
            txtSize, txtWeight, txtColor,
            layerUpBtn, layerDownBtn, layerDeleteBtn,
            pBW, pWarm, pCool, pVivid
        ].forEach(el => el && (el.disabled = !on));
        updateHistoryUI();
    }

    function setTool(newTool) {
        tool = newTool;
        toolMove.classList.toggle('btn-primary', tool === 'move');
        toolText.classList.toggle('btn-primary', tool === 'text');
    }

    // ------- file load / reset -------
    function loadFromFile(file) {
        const url = URL.createObjectURL(file);
        imgUrl = url;
        const imgNew = new Image();
        imgNew.onload = () => {
            img = imgNew;
            loaded = true;
            hint && (hint.style.display = 'none');
            zoom = 1;
            panX = panY = 0;
            cropMode = false;
            cropRect = null;
            elements.length = 0;
            activeIndex = -1;
            resetFilters(false);
            setTool('move');
            enableEditing(true);
            snapshot();
            draw();
            refreshLayersUI();
        };
        imgNew.src = url;
    }

    function resetAll() {
        if (!imgUrl) return;
        const imgNew = new Image();
        imgNew.onload = () => {
            snapshot();
            img = imgNew;
            zoom = 1;
            panX = panY = 0;
            cropMode = false;
            cropRect = null;
            elements.length = 0;
            activeIndex = -1;
            resetFilters(false);
            setTool('move');
            refreshLayersUI();
            draw();
        };
        imgNew.src = imgUrl;
    }

    // ------- transforms (rotate / flip) -------
    function bakeImage(drawFn, newW, newH) {
        const off = document.createElement('canvas');
        off.width = newW;
        off.height = newH;
        const c = off.getContext('2d');
        drawFn(c);
        const next = new Image();
        next.onload = () => {
            img = next;
            draw();
        };
        next.src = off.toDataURL('image/png');
    }

    function rotate(deg) {
        if (!loaded) return;
        snapshot();
        const w = img.naturalWidth;
        const h = img.naturalHeight;
        if (deg === 90) {
            bakeImage((c) => {
                c.translate(h, 0);
                c.rotate(Math.PI / 2);
                c.drawImage(img, 0, 0);
            }, h, w);
        } else if (deg === -90) {
            bakeImage((c) => {
                c.translate(0, w);
                c.rotate(-Math.PI / 2);
                c.drawImage(img, 0, 0);
            }, h, w);
        }
    }

    function flip(horizontal) {
        if (!loaded) return;
        snapshot();
        const w = img.naturalWidth;
        const h = img.naturalHeight;
        bakeImage((c) => {
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
    function startCrop() {
        if (!loaded) return;
        cropMode = true;
        cropRect = null;
        draw();
    }

    function applyCrop() {
        if (!loaded || !cropRect) return;
        snapshot();

        const {sx, sy, sw, sh} = cropRect;
        const {ix: x1, iy: y1} = stageToImage(sx, sy);
        const {ix: x2, iy: y2} = stageToImage(sx + sw, sy + sh);

        const ix = Math.max(0, Math.min(x1, x2));
        const iy = Math.max(0, Math.min(y1, y2));
        const iw = Math.max(1, Math.min(img.naturalWidth - ix, Math.abs(x2 - x1)));
        const ih = Math.max(1, Math.min(img.naturalHeight - iy, Math.abs(y2 - y1)));

        bakeImage((c) => {
            c.drawImage(img, ix, iy, iw, ih, 0, 0, iw, ih);
        }, iw, ih);

        cropMode = false;
        cropRect = null;
        elements.length = 0;
        activeIndex = -1;
        refreshLayersUI();
    }

    function cancelCrop() {
        cropMode = false;
        cropRect = null;
        draw();
    }

    // ------- zoom / pan -------
    function fitToScreen() {
        zoom = 1;
        panX = panY = 0;
        updateZoomReadout();
        draw();
    }

    function setZoom(newZ, anchorX, anchorY) {
        newZ = Math.max(0.1, Math.min(8, newZ));
        const {s, ox, oy} = baseFit();
        const oldZ = zoom;
        const worldX = (anchorX - ox - panX) / oldZ;
        const worldY = (anchorY - oy - panY) / oldZ;
        zoom = newZ;
        panX = anchorX - ox - worldX * newZ;
        panY = anchorY - oy - worldY * newZ;
        updateZoomReadout();
        draw();
    }

    // ------- sliders / presets -------
    function bindRange(key, unit) {
        const sl = sliders[key];
        sl.addEventListener('input', (e) => {
            const v = Number(e.target.value);
            filters[key] = v;
            if (unit === '%') vals[key].textContent = `${v}%`;
            else if (unit === 'deg') vals[key].textContent = `${v}°`;
            else vals[key].textContent = `${v}px`;
            draw();
        });
        sl.addEventListener('change', () => snapshot());
    }

    bindRange('bri', '%');
    bindRange('con', '%');
    bindRange('sat', '%');
    bindRange('hue', 'deg');
    bindRange('sep', '%');
    bindRange('gra', '%');
    bindRange('blur', 'px');

    function applyPreset(name) {
        snapshot();
        if (name === 'bw') {
            filters.gra = 100;
            filters.sep = 0;
            filters.sat = 0;
        } else if (name === 'warm') {
            filters.hue = -10;
            filters.sep = 10;
            filters.bri = 105;
        } else if (name === 'cool') {
            filters.hue = 12;
            filters.sep = 5;
            filters.bri = 102;
        } else if (name === 'vivid') {
            filters.con = 115;
            filters.sat = 140;
            filters.bri = 102;
        }
        syncFilterUI();
        draw();
    }

    pBW?.addEventListener('click', () => applyPreset('bw'));
    pWarm?.addEventListener('click', () => applyPreset('warm'));
    pCool?.addEventListener('click', () => applyPreset('cool'));
    pVivid?.addEventListener('click', () => applyPreset('vivid'));

    // ------- export -------
    qRange?.addEventListener('input', (e) => {
        qVal.textContent = e.target.value;
    });

    dlBtn?.addEventListener('click', () => {
        if (!loaded) return;

        const w = img.naturalWidth;
        const h = img.naturalHeight;
        const off = document.createElement('canvas');
        off.width = w;
        off.height = h;
        const c = off.getContext('2d');

        c.filter = cssFilter();
        c.drawImage(img, 0, 0);
        c.filter = 'none';

        elements.forEach(el => {
            if (el.visible === false) return;
            if (el.type === 'text') {
                c.font = `${el.weight} ${el.size}px Inter, system-ui, sans-serif`;
                c.fillStyle = el.color;
                c.textBaseline = 'top';
                c.fillText(el.text, el.x, el.y);
            }
        });

        const mime = fmtSel.value;
        const q = Number(qRange.value) / 100;
        const url = off.toDataURL(mime, q);
        const a = document.createElement('a');
        a.href = url;
        a.download = mime === 'image/png' ? 'bambicim-edit.png' : 'bambicim-edit.jpg';
        a.click();
    });

    // ------- tools / text helpers -------
    function syncTextControls() {
        if (activeIndex === -1 || activeIndex >= elements.length) return;
        const el = elements[activeIndex];
        if (txtContent) txtContent.value = el.text || '';
        if (txtSize) txtSize.value = el.size;
        if (txtWeight) txtWeight.value = el.weight;
        if (txtColor) txtColor.value = el.color;
        if (txtContent) {
            txtContent.addEventListener('input', () => {
                if (activeIndex < 0 || activeIndex >= elements.length) return;
                elements[activeIndex].text = txtContent.value;
                draw();
            });
            txtContent.addEventListener('blur', () => {
                if (activeIndex < 0 || activeIndex >= elements.length) return;
                snapshot();
            });
        }

    }


    txtSize?.addEventListener('change', () => {
        if (activeIndex < 0 || activeIndex >= elements.length) return;
        snapshot();
        elements[activeIndex].size = Number(txtSize.value || 32);
        draw();
    });

    txtWeight?.addEventListener('change', () => {
        if (activeIndex < 0 || activeIndex >= elements.length) return;
        snapshot();
        elements[activeIndex].weight = String(txtWeight.value || '600');
        draw();
    });

    txtColor?.addEventListener('change', () => {
        if (activeIndex < 0 || activeIndex >= elements.length) return;
        snapshot();
        elements[activeIndex].color = String(txtColor.value || '#ffffff');
        draw();
    });

    toolMove?.addEventListener('click', () => setTool('move'));
    toolText?.addEventListener('click', () => setTool('text'));

    gridToggle?.addEventListener('click', () => {
        showGrid = !showGrid;
        gridToggle.classList.toggle('btn-primary', showGrid);
        draw();
    });

    fitBtn?.addEventListener('click', () => fitToScreen());
    oneBtn?.addEventListener('click', () => setZoom(1, stageW / 2, stageH / 2));

    // text measurement helper for hit-test
    function measureText(el) {
        offCtx.font = `${el.weight} ${el.size}px Inter, system-ui, sans-serif`;
        const m = offCtx.measureText(el.text || '');
        const w = m.width;
        const h = el.size * 1.2;
        return {w, h};
    }

    function hitTextLayer(sx, sy) {
        if (!elements.length) return -1;
        const {ix, iy, s} = stageToImage(sx, sy);
        // üstteki önce
        for (let i = elements.length - 1; i >= 0; i--) {
            const el = elements[i];
            if (el.visible === false || el.type !== 'text') continue;
            const {w, h} = measureText(el);
            const x1 = el.x;
            const y1 = el.y;
            const x2 = x1 + w;
            const y2 = y1 + h;
            if (ix >= x1 && ix <= x2 && iy >= y1 && iy <= y2) return i;
        }
        return -1;
    }

    // ------- mouse events: pan / crop / text -------
    stage.addEventListener('mousedown', (e) => {
        if (!loaded) return;
        const rect = stage.getBoundingClientRect();
        const sx = e.clientX - rect.left;
        const sy = e.clientY - rect.top;

        dragSX = sx;
        dragSY = sy;

        if (cropMode) {
            dragKind = 'crop';
            cropRect = {sx, sy, sw: 0, sh: 0};
            draw();
            return;
        }

        if (tool === 'move') {
            const hit = hitTextLayer(sx, sy);
            if (hit !== -1) {
                activeIndex = hit;
                dragKind = 'text';
                refreshLayersUI();
                syncTextControls();
            } else {
                dragKind = 'pan';
            }
            return;
        }

        if (tool === 'text') {
            // yeni metin ekle
            const {ix} = stageToImage(sx, sy); // sadece s için çağırıyoruz aslında
            const {ix: tx, iy: ty} = stageToImage(sx, sy);
            snapshot();
            const el = {
                type: 'text',
                x: tx,
                y: ty,
                text: 'Metin',
                size: Number(txtSize.value || 32),
                weight: String(txtWeight.value || '600'),
                color: String(txtColor.value || '#ffffff'),
                visible: true,
                name: `Metin ${elements.length + 1}`
            };
            elements.push(el);
            activeIndex = elements.length - 1;
            refreshLayersUI();
            syncTextControls();
            draw();
            // text ekledikten sonra taşıma moduna geç
            setTool('move');
            dragKind = null;
        }
    });

    stage.addEventListener('mousemove', (e) => {
        if (!loaded || !dragKind) return;
        const rect = stage.getBoundingClientRect();
        const sx = e.clientX - rect.left;
        const sy = e.clientY - rect.top;

        const dx = sx - dragSX;
        const dy = sy - dragSY;

        if (dragKind === 'pan') {
            panX += dx;
            panY += dy;
            dragSX = sx;
            dragSY = sy;
            draw();
        } else if (dragKind === 'crop' && cropRect) {
            let sw = sx - cropRect.sx;
            let sh = sy - cropRect.sy;
            // aspect oranı
            const asp = aspectSel.value;
            if (asp !== 'free') {
                const [aw, ah] = asp.split(':').map(Number);
                const ratio = aw / ah;
                if (Math.abs(sw) / Math.abs(sh || 1) > ratio) {
                    sh = Math.sign(sh || 1) * Math.abs(sw) / ratio;
                } else {
                    sw = Math.sign(sw || 1) * Math.abs(sh) * ratio;
                }
            }
            cropRect.sw = sw;
            cropRect.sh = sh;
            draw();
        } else if (dragKind === 'text' && activeIndex >= 0) {
            const {s} = baseFit();
            const deltaImgX = dx / (zoom * s);
            const deltaImgY = dy / (zoom * s);
            elements[activeIndex].x += deltaImgX;
            elements[activeIndex].y += deltaImgY;
            dragSX = sx;
            dragSY = sy;
            draw();
        }
    });

    window.addEventListener('mouseup', () => {
        if (dragKind === 'text' && activeIndex >= 0) snapshot();
        dragKind = null;
    });

    stage.addEventListener('wheel', (e) => {
        if (!loaded) return;
        e.preventDefault();
        const rect = stage.getBoundingClientRect();
        const sx = e.clientX - rect.left;
        const sy = e.clientY - rect.top;
        const factor = e.deltaY < 0 ? 1.1 : 0.9;
        setZoom(zoom * factor, sx, sy);
    }, {passive: false});

    // ------- file input / drag & drop -------
    fileInput?.addEventListener('change', (e) => {
        const f = e.target.files?.[0];
        if (f) loadFromFile(f);
    });

    resetBtn?.addEventListener('click', resetAll);

    stage.addEventListener('dragover', (e) => {
        e.preventDefault();
    });
    stage.addEventListener('drop', (e) => {
        e.preventDefault();
        const f = e.dataTransfer.files?.[0];
        if (f) loadFromFile(f);
    });

    // ------- crop buttons -------
    cropModeBtn?.addEventListener('click', startCrop);
    applyCropBtn?.addEventListener('click', applyCrop);
    cancelCropBtn?.addEventListener('click', cancelCrop);

    // ------- rotate / flip buttons -------
    rotL?.addEventListener('click', () => rotate(-90));
    rotR?.addEventListener('click', () => rotate(90));
    flipH?.addEventListener('click', () => flip(true));
    flipV?.addEventListener('click', () => flip(false));

    // ------- undo / redo hotkeys + buttons -------
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

    // ------- init -------
    function init() {
        setNavH();
        setCanvasSize();
        resetFilters(false);
        enableEditing(false);
        refreshLayersUI();
    }

    document.addEventListener('DOMContentLoaded', () => {
        setNavH();
        init();
    });
    window.addEventListener('resize', () => {
        setNavH();
        setCanvasSize();
    });
})();
