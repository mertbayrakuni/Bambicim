// ---------- safe markdown fallback ----------
window.marked = window.marked || {
    parse: (s) =>
        String(s || "")
            .replace(/&/g, "&amp;")
            .replace(/</g, "&lt;")
            .replace(/>/g, "&gt;")
            .replace(/\n/g, "<br>"),
};

(() => {
    // ========= lightweight debug to on-screen panel (F9) =========
    const DBG = {box: null, body: null, lines: []};
    const dlog = (...a) => {
        try {
            if (!DBG.box) {
                const el = document.createElement("div");
                el.className = "bmb-debug";
                el.innerHTML =
                    '<div class="hd">Bambi Debug (F9)</div><div class="bd"></div>';
                document.body.appendChild(el);
                DBG.box = el;
                DBG.body = el.querySelector(".bd");
                window.addEventListener("keydown", (e) => {
                    if (e.key === "F9") el.classList.toggle("open");
                });
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

    // ========= utils =========
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

    // Turn plain URLs & emails inside an HTML string into <a> tags (safe, DOM based)
    function linkifyHTML(html) {
        const root = document.createElement("div");
        root.innerHTML = html;

        const LINK_RE_G = /((?:https?:\/\/|www\.)[^\s<>()]+|[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,})/g;
        const isEmail = s => /^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(s);
        const isUrl = s => /^(?:https?:\/\/|www\.)/i.test(s);

        function process(node) {
            // only touch text nodes (and skip inside existing links/scripts/styles)
            if (node.nodeType === 3) {
                const text = node.nodeValue;
                const parts = text.split(LINK_RE_G);
                if (parts.length === 1) return;

                const frag = document.createDocumentFragment();
                for (let i = 0; i < parts.length; i++) {
                    let chunk = parts[i];
                    if (!chunk) continue;

                    // if this piece is a link/email candidate, wrap it
                    if (LINK_RE_G.test(chunk)) {
                        LINK_RE_G.lastIndex = 0; // reset global regex
                        // strip trailing punctuation (common in prose)
                        const m = chunk.match(/[),.;!?]+$/);
                        const trail = m ? m[0] : "";
                        if (trail) chunk = chunk.slice(0, -trail.length);

                        const a = document.createElement("a");
                        if (isEmail(chunk)) {
                            a.href = `mailto:${chunk}`;
                            a.textContent = chunk;
                        } else if (isUrl(chunk)) {
                            const href = chunk.startsWith("www.") ? `https://${chunk}` : chunk;
                            a.href = href;
                            a.textContent = chunk;
                        } else {
                            frag.appendChild(document.createTextNode(parts[i]));
                            continue;
                        }
                        a.target = "_blank";
                        a.rel = "noopener noreferrer";
                        frag.appendChild(a);
                        if (trail) frag.appendChild(document.createTextNode(trail));
                    } else {
                        frag.appendChild(document.createTextNode(chunk));
                    }
                }
                node.parentNode.replaceChild(frag, node);
                return;
            }

            if (node.nodeType === 1 && node.nodeName !== "A" && node.nodeName !== "SCRIPT" && node.nodeName !== "STYLE") {
                for (let c = node.firstChild; c;) {
                    const n = c.nextSibling;
                    process(c);
                    c = n;
                }
            }
        }

        process(root);
        return root.innerHTML;
    }

    // ========= bubbles & typing =========
    function addBubble(chatEl, text, who) {
        if (!chatEl) return;
        const w = document.createElement("div");
        w.className = "bmb-b " + (who === "user" ? "u" : "a");

        const raw = normalizeMd(text || "");
        const html = window.marked.parse(raw);
        w.innerHTML = linkifyHTML(html);

        const ts = document.createElement("div");
        ts.className = "bmb-ts";
        ts.textContent = new Date().toLocaleTimeString();
        w.appendChild(ts);

        chatEl.appendChild(w);
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

    // ========= gallery (optional) =========
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

    // ========= modal shell (grow-from-origin) =========
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
            <input class="bmb-inp" type="text" placeholder="Mesajınızı yazın..." aria-label="Mesajınızı yazın">
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

        const micBtn = panel.querySelector("#bmbMic");
        if (micBtn) {
            micBtn.innerHTML = `<svg width="18" height="18" viewBox="0 0 24 24" aria-hidden="true">
        <path d="M12 14a3 3 0 0 0 3-3V6a3 3 0 0 0-6 0v5a3 3 0 0 0 3 3zm5-3a5 5 0 0 1-10 0H5a7 7 0 0 0 14 0h-2zM11 19h2v3h-2v-3z"/></svg>`;
        }

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

        panel.querySelector(".bmb-close").onclick = (e) => {
            e.preventDefault();
            close();
        };
        overlay.onclick = (e) => {
            if (e.target === overlay) close();
        };
    }

    // ========= Mount core (HTTP only) =========
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

        // ===== Voice (SR) + animated waves =====
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
                if (!audioCtx)
                    audioCtx = new (window.AudioContext || window.webkitAudioContext)();
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
                mediaStream =
                    mediaStream || (await navigator.mediaDevices.getUserMedia({audio: true}));
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

        // ===== TTS hooks (disabled unless you add /tts) =====
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

        const ttsSupported = () =>
            "speechSynthesis" in window && "SpeechSynthesisUtterance" in window;

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
            return (
                ranked.find((v) => (v.lang || "").toLowerCase().startsWith("tr")) ||
                ranked[0] ||
                null
            );
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

        function cleanForTTS(s) {
            return (s || "")
                .replace(/!\[[^\]]*\]\([^)]+\)/g, "$1")
                .replace(/\[([^\]]+)\]\([^)]+\)/g, "$1")
                .replace(/https?:\/\/\S+|www\.\S+|\S+@\S+/g, " ")
                .replace(/[=+\-/*<>|\\^~`_%$€£¥©®™°\[\]{}()@#:;]/g, " ")
                .replace(/[`*_#>{}<~^]+/g, " ")
                .replace(/[!?]{2,}/g, "!")
                .replace(/\.{3,}/g, ".")
                .replace(/\s+/g, " ")
                .trim();
        }

        function ttsStop() {
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

        function updateTtsBtn() {
            if (!ttsBtn) return;
            ttsBtn.classList.toggle("on", tts.enabled);
            ttsBtn.setAttribute("aria-pressed", String(tts.enabled));
            ttsBtn.textContent = tts.enabled ? "🔊" : "🔈";
            if (tts.voice)
                ttsBtn.title = `Sesi ${tts.enabled ? "kapat" : "aç"} · ${tts.voice.name}`;
        }

        ttsBtn?.addEventListener("click", (ev) => {
            if (ev.altKey) return;
            tts.enabled = !tts.enabled;
            if (tts.enabled && ttsSupported()) initVoicesOnce();
            if (!tts.enabled) ttsStop();
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
        const ttsEndpoint = location.origin + "/tts";

        async function speakAndGetDuration(text) {
            if (!tts.enabled)
                return {
                    play: async () => {
                    }, durationMs: 0
                };
            const clean = cleanForTTS(text || "");
            if (!clean) return {
                play: async () => {
                }, durationMs: 0
            };
            try {
                const res = await fetch(ttsEndpoint, {
                    method: "POST",
                    headers: {"Content-Type": "application/json"},
                    body: JSON.stringify({text: clean, provider: "polly", voice: "Burcu"}),
                });
                if (!res.ok) return {
                    play: async () => {
                    }, durationMs: 0
                };
                const blob = await res.blob();
                const url = URL.createObjectURL(blob);
                const probe = new Audio();
                const durationMs = await new Promise((r) => {
                    probe.preload = "metadata";
                    probe.src = url;
                    probe.onloadedmetadata = () => r(Math.max(0, (probe.duration || 0) * 1000));
                    probe.onerror = () => r(0);
                });
                const play = () =>
                    new Promise((resolve) => {
                        try {
                            if (tts.audio) tts.audio.pause();
                        } catch {
                        }
                        const a = new Audio(url);
                        a.onended = () => {
                            try {
                                URL.revokeObjectURL(url);
                            } catch {
                            }
                            resolve();
                        };
                        a.play().catch(() => resolve());
                        tts.audio = a;
                    });
                return {play, durationMs: durationMs || Math.max(1200, clean.length * 55)};
            } catch {
                return {
                    play: async () => {
                    }, durationMs: 0
                };
            }
        }

        // ===== typewriter (synced with optional audio) =====
        function typeWriter(el, text, msPerChar = 16) {
            return new Promise(res => {
                const full = normalizeMd(text || "");
                let i = 0, len = full.length;
                const id = setInterval(() => {
                    i++;
                    el.innerHTML = window.marked.parse(full.slice(0, i));
                    if (i >= len) {
                        clearInterval(id);
                        // turn plain URLs/emails into anchors after final render
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
                let playAudio = async () => {
                };
                try {
                    const {play, durationMs} = await speakAndGetDuration(step);
                    playAudio = play;
                    if (durationMs && step.length) {
                        msPerChar = Math.min(Math.max(Math.ceil(durationMs / step.length), 8), 64);
                    }
                } catch {
                }
                await Promise.all([typeWriter(w, step, msPerChar), playAudio()]);
                const ts = document.createElement("div");
                ts.className = "bmb-ts";
                ts.textContent = new Date().toLocaleTimeString();
                w.appendChild(ts);
            }
        };

        // ===== HTTP transport only =====
        async function httpSend(txt) {
            try {
                const res = await fetch("/api/chat", {
                    method: "POST",
                    headers: {"Content-Type": "application/json"},
                    body: JSON.stringify({q: txt, client_id: getSid()}),
                });
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
                        human = "Güvenlik (CSRF) engeli. Çözüm: /api/chat CSRF muaf olmalı.";
                    }
                    await renderAssistantReply(chat, "Hata: " + human);
                    dlog("HTTP error", res.status, textBlob.slice(0, 400));
                    return;
                }
                const reply = data && typeof data.reply === "string" ? data.reply : "";
                const urls = Array.isArray(data?.urls) ? data.urls : [];
                await renderAssistantReply(
                    chat,
                    reply || "Üzgünüm, bir aksaklık oldu. Birazdan tekrar dener misin?"
                );
                if (urls.length) addImageGallery(chat, urls);
            } catch (err) {
                await renderAssistantReply(
                    chat,
                    "Üzgünüm, bir sorun oluştu. Lütfen tekrar dener misiniz?"
                );
                dlog("HTTP error", err);
            }
        }

        function send() {
            const txt = (input?.value || "").trim();
            if (!txt) return;
            addBubble(chat, txt, "user");
            const removeTyping = showTyping(chat);
            httpSend(txt).finally(() => {
                try {
                    removeTyping();
                } catch {
                }
            });
            if (input) input.value = "";
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
            },
        };
    }

    // expose (kept name so your launcher keeps working)
    window.TTWChatbot = {openModal, mount};
    try {
        window.dispatchEvent(new Event("bmb-ready"));
    } catch {
    }
})();
