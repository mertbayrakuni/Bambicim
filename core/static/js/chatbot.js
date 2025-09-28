/* Bambi Copilot – modal chat (SSE + uploads + voice + gallery) */
/* Safe markdown fallback */
window.marked = window.marked || {
    parse: (s) =>
        String(s || "")
            .replace(/&/g, "&amp;")
            .replace(/</g, "&lt;")
            .replace(/>/g, "&gt;")
            .replace(/\n/g, "<br>"),
};

(() => {
    // ===== debug overlay (F9) =====
    const DBG = {box: null, body: null, lines: []};
    const dlog = (...a) => {
        try {
            if (!DBG.box) {
                const el = document.createElement("div");
                el.className = "bmb-debug";
                el.innerHTML = '<div class="hd">Bambi Debug (F9)</div><div class="bd"></div>';
                document.body.appendChild(el);
                DBG.box = el;
                DBG.body = el.querySelector(".bd");
                window.addEventListener("keydown", (e) => e.key === "F9" && el.classList.toggle("open"));
            }
            const line =
                `[${new Date().toLocaleTimeString()}] ` +
                a
                    .map((x) => {
                        try {
                            return typeof x === "string" ? x : JSON.stringify(x);
                        } catch {
                            return String(x);
                        }
                    })
                    .join(" ");
            DBG.lines.push(line);
            if (DBG.lines.length > 400) DBG.lines.shift();
            DBG.body.textContent = DBG.lines.join("\n");
            DBG.body.scrollTop = DBG.body.scrollHeight;
        } catch {
        }
    };

    // ===== utils =====
    const getSid = () => {
        try {
            let sid = localStorage.getItem("bmb_sid");
            if (!sid) {
                sid = crypto?.randomUUID?.() || Math.random().toString(36).slice(2);
                localStorage.setItem("bmb_sid", sid);
            }
            return sid;
        } catch {
            return Math.random().toString(36).slice(2);
        }
    };

    const normalizeMd = (s) =>
        (s || "").replace(/\r\n/g, "\n").replace(/\r/g, "\n").replace(/\\n/g, "\n");

    const getCSRF = () => {
        try {
            return document.cookie
                .split(";")
                .map((c) => c.trim())
                .find((c) => c.startsWith("csrftoken="))
                ?.split("=")[1] || "";
        } catch {
            return "";
        }
    };

    // Turn plain URLs/emails into <a> (DOM safe)
    function linkifyHTML(html) {
        const root = document.createElement("div");
        root.innerHTML = html;

        const LINK_RE_G =
            /((?:https?:\/\/|www\.)[^\s<>()]+|[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,})/g;
        const isEmail = (s) => /^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(s);
        const isUrl = (s) => /^(?:https?:\/\/|www\.)/i.test(s);

        (function walk(node) {
            if (node.nodeType === 3) {
                const parts = node.nodeValue.split(LINK_RE_G);
                if (parts.length === 1) return;
                const frag = document.createDocumentFragment();
                for (let i = 0; i < parts.length; i++) {
                    let chunk = parts[i];
                    if (!chunk) continue;
                    if (LINK_RE_G.test(chunk)) {
                        LINK_RE_G.lastIndex = 0;
                        const m = chunk.match(/[),.;!?]+$/);
                        const trail = m ? m[0] : "";
                        if (trail) chunk = chunk.slice(0, -trail.length);
                        const a = document.createElement("a");
                        if (isEmail(chunk)) {
                            a.href = `mailto:${chunk}`;
                            a.textContent = chunk;
                        } else if (isUrl(chunk)) {
                            a.href = chunk.startsWith("www.") ? `https://${chunk}` : chunk;
                            a.textContent = chunk;
                        } else {
                            frag.appendChild(document.createTextNode(parts[i]));
                            continue;
                        }
                        a.target = "_blank";
                        a.rel = "noopener noreferrer";
                        frag.appendChild(a);
                        if (trail) frag.appendChild(document.createTextNode(trail));
                    } else frag.appendChild(document.createTextNode(chunk));
                }
                node.parentNode.replaceChild(frag, node);
                return;
            }
            if (
                node.nodeType === 1 &&
                node.nodeName !== "A" &&
                node.nodeName !== "SCRIPT" &&
                node.nodeName !== "STYLE"
            ) {
                for (let c = node.firstChild; c;) {
                    const n = c.nextSibling;
                    walk(c);
                    c = n;
                }
            }
        })(root);

        return root.innerHTML;
    }

    function addBubble(chatEl, text, who) {
        if (!chatEl) return;
        const w = document.createElement("div");
        w.className = "bmb-b " + (who === "user" ? "u" : "a");
        const raw = (text || "").replace(/\r\n/g, "\n").replace(/\r/g, "\n").replace(/\\n/g, "\n");
        const html =
            window.marked && window.marked.parse
                ? window.marked.parse(raw)
                : raw
                    .replace(/&/g, "&amp;")
                    .replace(/</g, "&lt;")
                    .replace(/>/g, "&gt;")
                    .replace(/\n/g, "<br>");
        w.innerHTML = linkifyHTML(html);
        const ts = document.createElement("div");
        ts.className = "bmb-ts";
        ts.textContent = new Date().toLocaleTimeString();
        w.appendChild(ts);
        chatEl.appendChild(w);
        chatEl.scrollTop = chatEl.scrollHeight;
    }

    // assistant file list (non-images)
    function addFileList(chatEl, files) {
        if (!chatEl || !files?.length) return;
        const wrap = document.createElement("div");
        wrap.className = "bmb-b a";
        const box = document.createElement("div");
        box.className = "bmb-files";
        files.forEach((f) => {
            const row = document.createElement("div");
            row.className = "bmb-file-row";
            const ico = document.createElement("div");
            ico.className = "ico";
            ico.textContent = "📄";
            const a = document.createElement("a");
            a.href = f.url;
            a.target = "_blank";
            a.rel = "noopener";
            a.textContent = f.name || f.url;
            const meta = document.createElement("small");
            const kb = Math.round((f.size || 0) / 1024);
            meta.textContent = (f.content_type || "").split(";")[0] + (kb ? ` · ${kb} KB` : "");
            row.append(ico, a, meta);
            box.appendChild(row);
        });
        wrap.appendChild(box);
        const ts = document.createElement("div");
        ts.className = "bmb-ts";
        ts.textContent = new Date().toLocaleTimeString();
        wrap.appendChild(ts);
        chatEl.appendChild(wrap);
        chatEl.scrollTop = chatEl.scrollHeight;
    }

    function showTyping(chatEl) {
        const b = document.createElement("div");
        b.className = "bmb-b a bmb-typing";
        b.innerHTML =
            '<span class="dots"><span class="dot"></span><span class="dot"></span><span class="dot"></span></span>';
        chatEl.appendChild(b);
        chatEl.scrollTop = chatEl.scrollHeight;
        return () => {
            try {
                b.remove();
            } catch {
            }
        };
    }

    function splitSteps(text) {
        const norm = normalizeMd(text || "").replace(/\n{3,}/g, "\n\n").trim();
        if (!norm) return [];
        const blocks = norm.split(/\n\s*\n/);
        dlog("MD ▶", blocks.map((b) => (b.slice(0, 80) + "…").replace(/\n/g, "⏎")));
        return blocks.slice(0, 12);
    }

    // ===== gallery =====
    function resolveUrl(u) {
        if (!u) return null;
        if (/^https?:\/\//i.test(u)) return u;
        if (u.startsWith("//")) return location.protocol + u;
        if (u.startsWith("/")) return location.origin + u;
        return location.origin + "/" + u.replace(/^\.?\//, "");
    }

    function hardClampCaptions(scope) {
        const doClamp = () => {
            const caps = (scope || document).querySelectorAll(".bmb-gallery .cap");
            caps.forEach((el) => {
                const cs = getComputedStyle(el);
                let lh = parseFloat(cs.lineHeight);
                if (!isFinite(lh)) {
                    const fs = parseFloat(cs.fontSize) || 12;
                    lh = fs * 1.3;
                }
                const maxH = Math.round(lh * 2);
                if (el.scrollHeight > maxH + 1) {
                    const full = (el.getAttribute("data-full") || el.textContent || "")
                        .trim()
                        .replace(/\s+/g, " ");
                    let lo = 0,
                        hi = full.length,
                        best = "";
                    while (lo <= hi) {
                        const mid = (lo + hi) >> 1;
                        el.textContent = full.slice(0, mid).trim() + "…";
                        if (el.scrollHeight <= maxH + 1) {
                            best = el.textContent;
                            lo = mid + 1;
                        } else hi = mid - 1;
                    }
                    el.textContent = best || full.slice(0, 2) + "…";
                    if (!el.title) el.title = full;
                }
            });
        };
        requestAnimationFrame(() => requestAnimationFrame(doClamp));
    }

    function addImageGallery(chatEl, items) {
        if (!chatEl || !items?.length) return;
        const wrap = document.createElement("div");
        wrap.className = "bmb-b a has-gallery";
        const grid = document.createElement("div");
        grid.className = "bmb-gallery";
        items.slice(0, 12).forEach((it) => {
            const obj = typeof it === "string" ? {image: it, adres: it} : it || {};
            const imgSrc = resolveUrl(obj.image || obj.adres);
            const href = resolveUrl(obj.adres || obj.image);
            if (!imgSrc) return;
            const tile = document.createElement("a");
            tile.className = "tile";
            tile.href = href || imgSrc;
            tile.target = "_blank";
            tile.rel = "noopener noreferrer";
            const imgWrap = document.createElement("div");
            imgWrap.className = "img-wrap";
            const img = document.createElement("img");
            img.src = imgSrc;
            img.alt = obj.title || "görsel";
            img.loading = "lazy";
            imgWrap.appendChild(img);
            tile.appendChild(imgWrap);
            const cap = document.createElement("div");
            cap.className = "cap";
            const title = (obj.title || "").trim();
            cap.textContent = title;
            cap.title = title;
            cap.setAttribute("data-full", title);
            tile.appendChild(cap);
            grid.appendChild(tile);
        });
        wrap.appendChild(grid);
        const ts = document.createElement("div");
        ts.className = "bmb-ts";
        ts.textContent = new Date().toLocaleTimeString();
        wrap.appendChild(ts);
        chatEl.appendChild(wrap);
        chatEl.scrollTop = chatEl.scrollHeight;
        hardClampCaptions(wrap);
    }

    // ===== modal shell =====
    const pageRect = (el) => {
        const r = el.getBoundingClientRect();
        return {left: r.left + scrollX, top: r.top + scrollY, width: r.width, height: r.height};
    };

    function openModal(opts) {
        const overlay = document.createElement("div");
        overlay.className = "bmb-overlay";
        const panel = document.createElement("div");
        panel.className = "bmb-panel";
        panel.innerHTML = `
      <div class="bmb-head">
        Bambi · Canlı Sohbet
        <button class="bmb-tts" type="button" title="Sesi aç/kapat" aria-pressed="false">🔈</button>
        <button class="bmb-close" type="button">×</button>
      </div>
      <div class="bmb-body">
        <div class="bmb-chat" data-bmb-chat data-autoinit="1">
          <header class="bmb-h"><h2>AI Chatbot</h2><div class="s">Size yardımcı olmak için buradayım</div></header>
          <div class="bmb-log" role="log" aria-live="polite"></div>
          <form class="bmb-row" autocomplete="off">
            <button class="bmb-clip" type="button" title="Dosya ekle" aria-label="Dosya ekle">📎</button>
            <input class="bmb-inp" type="text" placeholder="Mesajınızı yazın..." aria-label="Mesajınızı yazın">
            <div class="bmb-picks" aria-live="polite"></div>
            <input class="bmb-file" type="file" accept="image/*,.pdf,.txt,.md,.doc,.docx,.ppt,.pptx,.csv" multiple hidden>
            <div class="bmb-waves" aria-hidden="true"></div>
            <button class="bmb-mic" type="button" id="bmbMic" aria-pressed="false" title="Sesle yaz"></button>
            <button class="bmb-btn bmb-send" type="button" id="bmbSend">Gönder</button>
            <button class="bmb-btn bmb-ok" type="button" id="bmbOk" style="display:none">OK</button>
            <button class="bmb-btn bmb-cancel" type="button" id="bmbCancel" style="display:none">İptal</button>
          </form>
          <div class="bmb-disclaimer">Bambi, Bambicim için hazırlanmış deneysel bir sohbet asistanıdır</div>
        </div>
      </div>`;
        document.body.append(overlay, panel);
        document.body.classList.add("bmb-modal-open");

        panel.querySelector(".bmb-close").onclick = (e) => {
            e.preventDefault();
            close();
        };
        overlay.onclick = (e) => e.target === overlay && close();

        const originEl =
            typeof opts?.animateFrom === "string"
                ? document.querySelector(opts.animateFrom)
                : opts?.animateFrom || null;
        const doGrow =
            originEl &&
            originEl.getBoundingClientRect().width > 0 &&
            originEl.getBoundingClientRect().height > 0;

        function setFromOrigin() {
            const t = panel.getBoundingClientRect(),
                p = pageRect(panel),
                o = pageRect(originEl);
            const sx = Math.max(0.01, o.width / t.width),
                sy = Math.max(0.01, o.height / t.height);
            const dx = o.left - p.left,
                dy = o.top - p.top;
            panel.style.transformOrigin = "top left";
            panel.style.transform = `translate(${dx}px,${dy}px) scale(${sx},${sy})`;
            panel.style.opacity = "0.001";
        }

        requestAnimationFrame(() => {
            if (doGrow) setFromOrigin();
            requestAnimationFrame(() => {
                overlay.classList.add("open");
                panel.style.transform = "none";
                panel.style.opacity = "1";
            });
        });

        const controller = mount(panel.querySelector("[data-bmb-chat]"), opts || {});

        function close() {
            if (doGrow) {
                setFromOrigin();
                overlay.classList.remove("open");
                const done = () => {
                    panel.removeEventListener("transitionend", done);
                    cleanup();
                };
                panel.addEventListener("transitionend", done);
            } else cleanup();
        }

        function cleanup() {
            try {
                controller?.destroy?.();
            } catch {
            }
            try {
                overlay.remove();
            } catch {
            }
            try {
                panel.remove();
            } catch {
            }
            document.body.classList.remove("bmb-modal-open");
        }
    }

    // ===== Mount (HTTP+SSE) =====
    function mount(root, opts) {
        if (!root)
            return {
                destroy() {
                },
            };

        const chat = root.querySelector(".bmb-log");
        const input = root.querySelector(".bmb-inp");
        const sendB = root.querySelector(".bmb-send");
        const form = root.querySelector("form");
        const mic = root.querySelector("#bmbMic");
        const waves = root.querySelector(".bmb-waves");
        const okB = root.querySelector("#bmbOk");
        const cancelB = root.querySelector("#bmbCancel");
        const clip = root.querySelector(".bmb-clip");
        const fileInput = root.querySelector(".bmb-file");
        const picks = root.querySelector(".bmb-picks");

        // file chips
        function renderPicks() {
            picks.innerHTML = "";
            const files = fileInput?.files ? [...fileInput.files] : [];
            if (!files.length) return;
            const frag = document.createDocumentFragment();
            files.forEach((f, idx) => {
                const chip = document.createElement("span");
                chip.className = "bmb-pick";
                const ico = document.createElement("span");
                ico.className = "ico";
                ico.textContent =
                    /^image\//.test(f.type) ? "🖼️" :
                        /\.pdf$/i.test(f.name) ? "📕" :
                            /\.(docx?|odt)$/i.test(f.name) ? "📘" :
                                /\.(pptx?|odp)$/i.test(f.name) ? "📙" :
                                    /\.(csv|xlsx?|tsv)$/i.test(f.name) ? "📗" :
                                        /\.(md|txt)$/i.test(f.name) ? "📝" : "📄";
                const nm = document.createElement("span");
                nm.textContent = f.name;
                const rm = document.createElement("button");
                rm.className = "rm";
                rm.type = "button";
                rm.textContent = "×";
                rm.onclick = () => {
                    const dt = new DataTransfer();
                    [...fileInput.files].forEach((ff, j) => j !== idx && dt.items.add(ff));
                    fileInput.files = dt.files;
                    renderPicks();
                };
                chip.append(ico, nm, rm);
                frag.appendChild(chip);
            });
            picks.appendChild(frag);
        }

        clip?.addEventListener("click", () => fileInput?.click());
        fileInput?.addEventListener("change", renderPicks);

        // === Voice (SR + waves)
        const SR = window.SpeechRecognition || window.webkitSpeechRecognition;
        let rec = null,
            listening = false,
            starting = false;
        let finalBuf = "",
            interimBuf = "";
        let srKeepAlive = false;
        let mediaStream = null;

        let audioCtx = null,
            analyser = null,
            rafId = 0;

        function startWaves(stream) {
            if (!waves) return;
            try {
                let bars = Array.from(waves.querySelectorAll(".bar"));
                if (bars.length === 0) {
                    const target = 28,
                        frag = document.createDocumentFragment();
                    for (let i = 0; i < target; i++) {
                        const b = document.createElement("span");
                        b.className = "bar";
                        frag.appendChild(b);
                    }
                    waves.appendChild(frag);
                    bars = Array.from(waves.querySelectorAll(".bar"));
                }
                if (!audioCtx) audioCtx = new (window.AudioContext || window.webkitAudioContext)();
                const src = audioCtx.createMediaStreamSource(stream);
                analyser = audioCtx.createAnalyser();
                analyser.fftSize = 1024;
                analyser.smoothingTimeConstant = 0.75;
                const freq = new Uint8Array(analyser.frequencyBinCount);
                const step = Math.floor(freq.length / bars.length);
                const gain = 1.8;
                const draw = () => {
                    analyser.getByteFrequencyData(freq);
                    for (let i = 0; i < bars.length; i++) {
                        let sum = 0;
                        for (let j = i * step; j < (i + 1) * step; j++) sum += freq[j];
                        const v = sum / step / 255;
                        const s = Math.max(0.12, Math.min(1.25, v * gain));
                        bars[i].style.transform = `scaleY(${s})`;
                    }
                    rafId = requestAnimationFrame(draw);
                };
                waves.classList.add("on");
                src.connect(analyser);
                draw();
            } catch (e) {
                dlog("waves init failed", e);
            }
        }

        function stopWaves() {
            try {
                cancelAnimationFrame(rafId);
            } catch {
            }
            rafId = 0;
            waves?.classList.remove("on");
        }

        function toggleRecordUI(on) {
            const oldph = input.getAttribute("data-oldph") || input.placeholder || "";
            if (!input.getAttribute("data-oldph")) input.setAttribute("data-oldph", oldph);
            root.querySelector(".bmb-row")?.classList.toggle("rec", !!on);
            mic?.classList.toggle("rec", !!on);
            waves?.classList.toggle("on", !!on);
            if (sendB) sendB.style.display = on ? "none" : "inline-block";
            if (okB) okB.style.display = on ? "inline-block" : "none";
            if (cancelB) cancelB.style.display = on ? "inline-block" : "none";
            if (on) {
                input.classList.add("is-voice");
                input.placeholder = "Dinliyorum…";
                input.setAttribute("aria-label", "Dinliyorum…");
            } else {
                input.classList.remove("is-voice");
                input.placeholder = input.getAttribute("data-oldph") || "Mesajınızı yazın...";
                input.setAttribute("aria-label", "Mesajınızı yazın");
            }
        }

        const srSupported = () => !!SR;

        function srStop() {
            srKeepAlive = false;
            try {
                rec && rec.stop();
            } catch {
            }
            listening = false;
            toggleRecordUI(false);
            stopWaves();
            try {
                mediaStream?.getTracks()?.forEach((t) => t.stop());
            } catch {
            }
            mediaStream = null;
        }

        async function srStart() {
            if (starting || listening) return;
            if (!srSupported()) {
                dlog("SpeechRecognition not supported");
                if (mic) mic.disabled = true;
                return;
            }
            starting = true;
            srKeepAlive = true;
            toggleRecordUI(true);
            try {
                mediaStream = mediaStream || (await navigator.mediaDevices.getUserMedia({audio: true}));
                startWaves(mediaStream);
            } catch (err) {
                dlog("Mic permission error", err);
            }
            rec = new SR();
            rec.lang = "tr-TR";
            rec.interimResults = true;
            rec.continuous = true;
            rec.onstart = () => {
                starting = false;
                listening = true;
            };
            rec.onresult = (e) => {
                interimBuf = "";
                for (let i = e.resultIndex; i < e.results.length; i++) {
                    const chunk = e.results[i][0].transcript;
                    if (e.results[i].isFinal) finalBuf += chunk + " ";
                    else interimBuf += chunk;
                }
                input.value = (finalBuf + " " + interimBuf).replace(/\s+/g, " ").trim();
            };
            rec.onerror = () => {
            };
            rec.onend = () => {
                if (srKeepAlive) {
                    try {
                        rec.start();
                    } catch {
                        setTimeout(() => {
                            try {
                                rec.start();
                            } catch {
                            }
                        }, 200);
                    }
                }
            };
            try {
                rec.start();
            } catch (err) {
                starting = false;
                dlog("SR start fail", err);
            }
        }

        mic?.addEventListener("click", () => {
            !listening && !starting ? srStart() : srStop();
        });
        cancelB?.addEventListener("click", () => {
            srStop();
            input.value = (input.value || "").trim();
            input.focus();
        });
        okB?.addEventListener("click", () => {
            srStop();
            input.focus();
        });
        input?.addEventListener("keydown", () => {
            if (listening) srStop();
        });

        // ===== TTS (optional, toggled from header)
        const panelEl = root.closest(".bmb-panel");
        const ttsBtn = panelEl?.querySelector(".bmb-tts");
        const tts = {
            enabled: false,
            voice: null,
            rate: 1.0,
            pitch: 1.1,
            volume: 1.0,
            chosenName: localStorage.getItem("bmb_tts_voice") || null,
            audio: null,
            lastUrl: null,
        };
        const ttsSupported = () => "speechSynthesis" in window && "SpeechSynthesisUtterance" in window;
        const listVoicesSafe = () => {
            try {
                return speechSynthesis.getVoices() || [];
            } catch {
                return [];
            }
        };
        const rankVoice = (v) => {
            let s = 0;
            const n = (v.name || "").toLowerCase(),
                l = (v.lang || "").toLowerCase();
            if (l.startsWith("tr")) s += 5;
            if (l.includes("tr-tr")) s += 2;
            if (/seda|filiz|yelda|female|kadin/.test(n)) s += 6;
            if (/google|microsoft|online|natural/.test(n)) s += 2;
            if (!l.startsWith("tr") && /samantha|serena|victoria|aria|jenny|zira|emma|amy|joanna/.test(n))
                s += 1;
            return s;
        };
        const pickVoice = (pref) => {
            const vs = listVoicesSafe();
            if (!vs.length) return null;
            if (pref) {
                const f = vs.find((v) => v.name === pref);
                if (f) return f;
            }
            const ranked = [...vs].sort((a, b) => rankVoice(b) - rankVoice(a));
            return ranked.find((v) => (v.lang || "").toLowerCase().startsWith("tr")) || ranked[0] || null;
        };

        function initVoicesOnce() {
            if (!ttsSupported()) return;
            tts.voice = pickVoice(tts.chosenName);
            try {
                speechSynthesis.onvoiceschanged = () => {
                    const prev = tts.voice && tts.voice.name;
                    tts.voice = pickVoice(tts.chosenName || prev);
                    updateTtsBtn();
                };
            } catch {
            }
        }

        function updateTtsBtn() {
            if (!ttsBtn) return;
            ttsBtn.classList.toggle("on", tts.enabled);
            ttsBtn.setAttribute("aria-pressed", String(tts.enabled));
            ttsBtn.textContent = tts.enabled ? "🔊" : "🔈";
            if (tts.voice) ttsBtn.title = `Sesi ${tts.enabled ? "kapat" : "aç"} · ${tts.voice.name}`;
        }

        ttsBtn?.addEventListener("click", (ev) => {
            if (ev.altKey) return;
            tts.enabled = !tts.enabled;
            if (tts.enabled && ttsSupported()) initVoicesOnce();
            if (!tts.enabled) {
                try {
                    speechSynthesis.cancel?.();
                } catch {
                }
                try {
                    if (tts.audio) {
                        tts.audio.pause();
                        tts.audio.src = "";
                        tts.audio = null;
                    }
                    if (tts.lastUrl) {
                        URL.revokeObjectURL(tts.lastUrl);
                        tts.lastUrl = null;
                    }
                } catch {
                }
            }
            updateTtsBtn();
        });
        ttsBtn?.addEventListener("click", (ev) => {
            if (!ev.altKey) return;
            ev.preventDefault();
            if (!ttsSupported()) return;
            const vs = listVoicesSafe();
            if (!vs.length) return;
            const pool = vs.filter((v) => (v.lang || "").toLowerCase().startsWith("tr"));
            const list = pool.length ? pool : vs;
            if (!tts.voice) tts.voice = pickVoice(tts.chosenName);
            const idx = Math.max(0, list.findIndex((v) => tts.voice && v.name === tts.voice.name));
            const next = list[(idx + 1) % list.length];
            if (next) {
                tts.voice = next;
                tts.chosenName = next.name;
                localStorage.setItem("bmb_tts_voice", next.name);
                updateTtsBtn();
            }
        });
        updateTtsBtn();
        if (ttsSupported()) initVoicesOnce();

        // ===== Fallback: plain HTTP responder (still used by initialText)
        async function httpSend(txt, files) {
            try {
                let res;
                if (files && files.length) {
                    const fd = new FormData();
                    fd.append("q", txt || "");
                    fd.append("client_id", getSid());
                    [...files].forEach((f) => fd.append("files", f, f.name));
                    res = await fetch("/api/chat", {
                        method: "POST",
                        body: fd,
                        credentials: "same-origin",
                        headers: {"X-CSRFToken": getCSRF()},
                    });
                } else {
                    res = await fetch("/api/chat", {
                        method: "POST",
                        headers: {
                            "Content-Type": "application/json",
                            "X-CSRFToken": getCSRF(),
                        },
                        credentials: "same-origin",
                        body: JSON.stringify({q: txt, client_id: getSid()}),
                    });
                }

                let data = null,
                    textBlob = "";
                try {
                    data = await res.clone().json();
                } catch {
                    textBlob = await res.text().catch(() => "");
                }
                if (!res.ok) {
                    let human = `Sunucu ${res.status} döndürdü.`;
                    if (data && (data.error || data.detail)) {
                        const bits = [data.error, data.detail].filter(Boolean).join(" · ");
                        human += " " + bits;
                    }
                    if (res.status === 403 && /csrf/i.test(textBlob)) {
                        human = "Güvenlik (CSRF) engeli. Çözüm: /api/chat CSRF muaf olmalı veya token gönderilmeli.";
                    }
                    await renderAssistantReply(chat, "Hata: " + human);
                    dlog("HTTP error", res.status, textBlob.slice(0, 400));
                    return;
                }
                const reply = data && typeof data.reply === "string" ? data.reply : "";
                await renderAssistantReply(chat, reply || "Üzgünüm, bir aksaklık oldu. Birazdan tekrar dener misin?");

                // images
                const urls = Array.isArray(data?.urls) ? data.urls : [];
                if (urls.length) addImageGallery(chat, urls);

                // non-images
                const filesMeta = Array.isArray(data?.files) ? data.files : [];
                const nonImages = filesMeta.filter((f) => !(f.content_type || "").startsWith("image/"));
                if (nonImages.length) addFileList(chat, nonImages);
            } catch (err) {
                await renderAssistantReply(chat, "Üzgünüm, bir sorun oluştu. Lütfen tekrar dener misiniz?");
                dlog("HTTP error", err);
            }
        }

        // ===== SSE (Copilot)
        let activeStream = null;

        async function sseSend(txt, fileInput, chatEl, onStart, onDone) {
            // cancel previous stream
            try {
                activeStream?.abort();
            } catch {
            }
            const ctrl = new AbortController();
            activeStream = ctrl;

            // upload files (optional)
            let conversation_id = localStorage.getItem("bmb_convo") || "";
            if (fileInput && fileInput.files && fileInput.files.length) {
                const fd = new FormData();
                [...fileInput.files].forEach((f) => fd.append("files", f, f.name));
                if (conversation_id) fd.append("conversation_id", conversation_id);
                const up = await fetch("/api/copilot/upload", {
                    method: "POST",
                    body: fd,
                    credentials: "same-origin",
                    headers: {"X-CSRFToken": getCSRF()},
                    signal: ctrl.signal,
                }).catch(() => null);

                if (up && up.ok) {
                    const files = await up.json().catch(() => []);
                    if (files?.[0]?.conversation_id) {
                        conversation_id = files[0].conversation_id;
                        localStorage.setItem("bmb_convo", conversation_id);
                    }
                }
            }

            // start stream
            const body = JSON.stringify({conversation_id, message: txt, client_id: getSid()});
            const resp = await fetch("/api/copilot/chat", {
                method: "POST",
                headers: {
                    "Content-Type": "application/json",
                    "Accept": "text/event-stream",
                    "X-CSRFToken": getCSRF(),
                },
                credentials: "same-origin",
                body,
                signal: ctrl.signal,
            }).catch(() => null);

            if (!resp || !resp.ok || !resp.body) {
                await renderAssistantReply(chatEl, "Üzgünüm, akışı başlatamadım.");
                onDone?.();
                return;
            }

            onStart?.();

            const reader = resp.body.getReader();
            const decoder = new TextDecoder();
            let buffer = "",
                bucket = "";

            // target assistant bubble
            const w = document.createElement("div");
            w.className = "bmb-b a";
            chatEl.appendChild(w);

            function flushBucket() {
                if (!bucket) return;
                w.innerHTML = linkifyHTML(window.marked.parse(bucket));
                chatEl.scrollTop = chatEl.scrollHeight;
            }

            try {
                while (true) {
                    const {value, done} = await reader.read();
                    if (done) break;
                    buffer += decoder.decode(value, {stream: true});

                    const parts = buffer.split("\n\n");
                    buffer = parts.pop();
                    for (const raw of parts) {
                        const lines = raw.split("\n");
                        let event = "message",
                            data = "";
                        for (const ln of lines) {
                            if (ln.startsWith("event:")) event = ln.slice(6).trim();
                            if (ln.startsWith("data:")) data += ln.slice(5).trim();
                        }
                        if (event === "delta") {
                            try {
                                const j = JSON.parse(data);
                                bucket += j.text || "";
                                flushBucket();
                            } catch {
                            }
                        } else if (event === "done") {
                            try {
                                const j = JSON.parse(data);
                                if (j.conversation_id) localStorage.setItem("bmb_convo", j.conversation_id);
                            } catch {
                            }
                            flushBucket();
                            const ts = document.createElement("div");
                            ts.className = "bmb-ts";
                            ts.textContent = new Date().toLocaleTimeString();
                            w.appendChild(ts);
                            onDone?.();
                        }
                    }
                }
            } catch (e) {
                if (ctrl.signal.aborted) {
                    dlog("SSE aborted");
                } else {
                    dlog("SSE error", e);
                    await renderAssistantReply(chatEl, "\n\n_(Akış kesildi. Tekrar deneyebilirsiniz.)_");
                }
            } finally {
                if (activeStream === ctrl) activeStream = null;
            }
        }

        // ===== typewriter used by HTTP fallback
        function typeWriter(el, text, msPerChar = 16) {
            return new Promise((res) => {
                const full = normalizeMd(text || "");
                let i = 0,
                    len = full.length;
                const id = setInterval(() => {
                    i++;
                    el.innerHTML = window.marked.parse(full.slice(0, i));
                    if (i >= len) {
                        clearInterval(id);
                        el.innerHTML = linkifyHTML(el.innerHTML);
                        res();
                    }
                }, msPerChar);
            });
        }

        const renderAssistantReply = async (chatEl, fullText) => {
            const steps = splitSteps(fullText).slice(0, 8);
            for (const step of steps) {
                const remove = showTyping(chatEl);
                const w = document.createElement("div");
                w.className = "bmb-b a";
                chatEl.appendChild(w);
                chatEl.scrollTop = chatEl.scrollHeight;
                remove();
                let msPerChar = 16;
                await typeWriter(w, step, msPerChar);
                const ts = document.createElement("div");
                ts.className = "bmb-ts";
                ts.textContent = new Date().toLocaleTimeString();
                w.appendChild(ts);
            }
        };

        // ===== send
        function send() {
            const txt = (input?.value || "").trim();
            const files = fileInput?.files || null;
            if (!txt && (!files || files.length === 0)) return;

            // user's bubble
            if (txt) addBubble(chat, txt, "user");

            // quick previews (images)
            if (files && files.length) {
                const imgUrls = [...files]
                    .filter((f) => f.type.startsWith("image/"))
                    .map((f) => URL.createObjectURL(f));
                if (imgUrls.length) {
                    const pre = document.createElement("div");
                    pre.className = "bmb-previews";
                    imgUrls.forEach((u) => {
                        const im = document.createElement("img");
                        im.src = u;
                        pre.appendChild(im);
                    });
                    const w = document.createElement("div");
                    w.className = "bmb-b u";
                    w.appendChild(pre);
                    const ts = document.createElement("div");
                    ts.className = "bmb-ts";
                    ts.textContent = new Date().toLocaleTimeString();
                    w.appendChild(ts);
                    chat.appendChild(w);
                    chat.scrollTop = chat.scrollHeight;
                    setTimeout(() => imgUrls.forEach((u) => URL.revokeObjectURL(u)), 30000);
                }
            }

            const removeTyping = showTyping(chat);
            sseSend(
                txt,
                fileInput,
                chat,
                () => {
                },
                () => {
                    try {
                        removeTyping();
                    } catch {
                    }
                }
            );

            if (input) input.value = "";
            if (fileInput) {
                fileInput.value = "";
                renderPicks();
            }
        }

        form?.addEventListener("submit", (e) => {
            e.preventDefault();
            e.stopPropagation();
        });
        sendB?.addEventListener("click", (e) => {
            e.preventDefault();
            e.stopPropagation();
            send();
        });
        input?.addEventListener("keydown", (e) => {
            if (e.key === "Enter" && !e.shiftKey) {
                e.preventDefault();
                send();
            }
        });

        // stop voice when modal closes
        const mo = new MutationObserver(() => {
            if (!document.body.classList.contains("bmb-modal-open")) srStop();
        });
        mo.observe(document.body, {attributes: true, attributeFilter: ["class"]});

        const first = (opts.initialText || "").trim();
        if (first) {
            addBubble(chat, first, "user");
            httpSend(first);
        }

        return {
            destroy() {
                try {
                    srStop();
                } catch {
                }
                try {
                    mo.disconnect();
                } catch {
                }
                try {
                    activeStream?.abort();
                } catch {
                }
            },
        };
    }

    // expose for launcher
    window.TTWChatbot = {openModal, mount};
    try {
        window.dispatchEvent(new Event("bmb-ready"));
    } catch {
    }
})();
