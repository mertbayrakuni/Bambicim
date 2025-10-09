(() => {
    const $ = (sel) => document.querySelector(sel);
    const $$ = (sel) => document.querySelectorAll(sel);
    const dpr = Math.max(1, window.devicePixelRatio || 1);

    // DOM
    const fileInput = $('#fileInput');
    const resetBtn = $('#resetBtn');
    const rotL = $('#rotL'), rotR = $('#rotR'), flipH = $('#flipH'), flipV = $('#flipV');
    const cropModeBtn = $('#cropMode'), applyCropBtn = $('#applyCrop'), cancelCropBtn = $('#cancelCrop');
    const aspectSel = $('#aspect');
    const fmtSel = $('#fmt'), qRange = $('#quality'), qVal = $('#qv'), dlBtn = $('#downloadBtn');
    const pBW = $('#p_bw'), pWarm = $('#p_warm'), pCool = $('#p_cool'), pVivid = $('#p_vivid');

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

    // STATE
    let originalURL = null;
    let img = new Image(); // current baked image
    let loaded = false;

    // filters preview (baked only on export)
    const filters = {bri: 100, con: 100, sat: 100, hue: 0, sep: 0, gra: 0, blur: 0};

    // crop UI
    let cropMode = false;
    let sel = null; // {x,y,w,h} in preview CSS pixels
    let dragging = false;
    let aspect = 'free';

    function enableEditing(on) {
        [resetBtn, rotL, rotR, flipH, flipV, cropModeBtn, aspectSel, fmtSel, qRange, dlBtn,
            pBW, pWarm, pCool, pVivid, applyCropBtn, cancelCropBtn].forEach(el => el.disabled = !on);
        Object.values(sliders).forEach(el => el.disabled = !on);
    }

    function setCanvasSize() {
        // Fit image into stage while preserving aspect ratio
        const rect = stage.getBoundingClientRect();
        // CSS size
        canvas.style.width = `${rect.width}px`;
        canvas.style.height = `${rect.height}px`;
        // Actual pixels
        canvas.width = Math.floor(rect.width * dpr);
        canvas.height = Math.floor(rect.height * dpr);
    }

    function computeFit() {
        const rect = stage.getBoundingClientRect();
        const W = rect.width, H = rect.height;
        const iw = img.naturalWidth, ih = img.naturalHeight;
        const scale = Math.min(W / iw, H / ih);
        const vw = iw * scale, vh = ih * scale;
        const ox = (W - vw) / 2;
        const oy = (H - vh) / 2;
        return {scale, vw, vh, ox, oy};
    }

    function cssFilter() {
        return `brightness(${filters.bri}%) contrast(${filters.con}%) saturate(${filters.sat}%) hue-rotate(${filters.hue}deg) sepia(${filters.sep}%) grayscale(${filters.gra}%) blur(${filters.blur}px)`;
    }

    function draw() {
        setCanvasSize();
        const {ox, oy, vw, vh, scale} = computeFit();

        // clear
        ctx.setTransform(1, 0, 0, 1, 0, 0);
        ctx.clearRect(0, 0, canvas.width, canvas.height);

        if (!loaded) return;

        // draw image with filters
        ctx.save();
        ctx.scale(dpr, dpr);
        ctx.filter = cssFilter();
        ctx.drawImage(img, ox, oy, vw, vh);
        ctx.restore();

        // draw crop overlay when in crop mode
        if (cropMode && sel) {
            ctx.save();
            ctx.scale(dpr, dpr);
            // darken
            ctx.fillStyle = 'rgba(0,0,0,0.35)';
            ctx.fillRect(0, 0, canvas.width / dpr, canvas.height / dpr);
            // hole
            ctx.globalCompositeOperation = 'destination-out';
            ctx.fillStyle = 'rgba(0,0,0,1)';
            ctx.fillRect(sel.x, sel.y, sel.w, sel.h);
            ctx.globalCompositeOperation = 'source-over';
            // border
            ctx.strokeStyle = '#ff5fb8';
            ctx.lineWidth = 2;
            ctx.strokeRect(sel.x, sel.y, sel.w, sel.h);
            ctx.restore();
        }
    }

    function loadFromFile(file) {
        const url = URL.createObjectURL(file);
        originalURL = url;
        img = new Image();
        img.onload = () => {
            loaded = true;
            enableEditing(true);
            hint.style.display = 'none';
            resetFilters();
            cropMode = false;
            sel = null;
            draw();
        };
        img.src = url;
    }

    function resetAll() {
        if (!originalURL) return;
        img = new Image();
        img.onload = () => {
            loaded = true;
            cropMode = false;
            sel = null;
            resetFilters();
            draw();
        };
        img.src = originalURL;
    }

    function resetFilters() {
        filters.bri = 100;
        filters.con = 100;
        filters.sat = 100;
        filters.hue = 0;
        filters.sep = 0;
        filters.gra = 0;
        filters.blur = 0;
        sliders.bri.value = 100;
        sliders.con.value = 100;
        sliders.sat.value = 100;
        sliders.hue.value = 0;
        sliders.sep.value = 0;
        sliders.gra.value = 0;
        sliders.blur.value = 0;
        vals.bri.textContent = '100%';
        vals.con.textContent = '100%';
        vals.sat.textContent = '100%';
        vals.hue.textContent = '0°';
        vals.sep.textContent = '0%';
        vals.gra.textContent = '0%';
        vals.blur.textContent = '0px';
    }

    function bakeTransform(drawFn, newW, newH) {
        const off = document.createElement('canvas');
        off.width = newW;
        off.height = newH;
        const c = off.getContext('2d');
        drawFn(c, off);
        img = new Image();
        img.onload = () => {
            draw();
        };
        img.src = off.toDataURL('image/png');
    }

    function rotate(deg) {
        if (!loaded) return;
        const w = img.naturalWidth, h = img.naturalHeight;
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

    function toImageCoords(px, py) {
        const {scale, ox, oy} = computeFit();
        const x = (px - ox) / scale;
        const y = (py - oy) / scale;
        return {
            x: Math.max(0, Math.min(img.naturalWidth, x)),
            y: Math.max(0, Math.min(img.naturalHeight, y))
        };
    }

    function applyCrop() {
        if (!sel || !loaded) return;
        // map selection (preview CSS px) -> image px
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

    // EVENTS
    fileInput.addEventListener('change', (e) => {
        const f = e.target.files?.[0];
        if (f) loadFromFile(f);
    });
    stage.addEventListener('dragover', e => {
        e.preventDefault();
    });
    stage.addEventListener('drop', e => {
        e.preventDefault();
        const f = e.dataTransfer.files?.[0];
        if (f) loadFromFile(f);
    });

    resetBtn.onclick = resetAll;
    rotL.onclick = () => rotate(-90);
    rotR.onclick = () => rotate(90);
    flipH.onclick = () => flip(true);
    flipV.onclick = () => flip(false);

    cropModeBtn.onclick = () => startCrop();
    cancelCropBtn.onclick = () => {
        cropMode = false;
        sel = null;
        draw();
    };
    applyCropBtn.onclick = applyCrop;
    aspectSel.onchange = (e) => {
        aspect = e.target.value;
    };

    // crop mouse handling on the canvas area
    stage.addEventListener('mousedown', (e) => {
        if (!cropMode || !loaded) return;
        const rect = stage.getBoundingClientRect();
        const sx = e.clientX - rect.left;
        const sy = e.clientY - rect.top;
        sel = {x: sx, y: sy, w: 0, h: 0};
        dragging = true;
    });
    stage.addEventListener('mousemove', (e) => {
        if (!cropMode || !dragging || !sel) return;
        const rect = stage.getBoundingClientRect();
        const cx = e.clientX - rect.left;
        const cy = e.clientY - rect.top;
        let w = cx - sel.x, h = cy - sel.y;

        if (aspect !== 'free') {
            const [aw, ah] = aspect.split(':').map(Number);
            const r = aw / ah;
            if (Math.abs(w) / Math.abs(h || 1) > r) {
                h = Math.sign(h || 1) * Math.abs(w) / r;
            } else {
                w = Math.sign(w || 1) * Math.abs(h) * r;
            }
        }
        sel.w = w;
        sel.h = h;
        // normalize to positive dims
        if (sel.w < 0) {
            sel.x += sel.w;
            sel.w *= -1;
        }
        if (sel.h < 0) {
            sel.y += sel.h;
            sel.h *= -1;
        }

        draw();
    });
    window.addEventListener('mouseup', () => {
        dragging = false;
    });

    // sliders
    function bindRange(key, unit, post = v => v) {
        sliders[key].addEventListener('input', e => {
            const v = Number(e.target.value);
            filters[key] = v;
            vals[key].textContent = unit === 'deg' ? `${v}°` : unit === 'px' ? `${v}px` : `${v}%`;
            draw();
        });
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
        // trigger inputs to update filters + labels
        ['gra', 'sep', 'sat', 'hue', 'bri', 'con'].forEach(k => sliders[k].dispatchEvent(new Event('input')));
    }

    [pBW, pWarm, pCool, pVivid].forEach(btn => {
        btn?.addEventListener('click', () => applyPreset(btn.dataset.preset));
    });

    // export
    qRange.addEventListener('input', e => {
        qVal.textContent = e.target.value;
    });
    dlBtn.addEventListener('click', () => {
        if (!loaded) return;
        // render at image resolution with filters
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

    // init
    enableEditing(false);
    setCanvasSize();
    window.addEventListener('resize', draw);
})();
