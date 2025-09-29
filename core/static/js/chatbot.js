/* Bambi Copilot — clean modal chat (SSE + uploads + voice + sources)
   Endpoints (adjust API_BASE if needed):
   - POST ${API_BASE}/upload_files   -> multipart/form-data (files[], optional conversation_id)
   - POST ${API_BASE}/chat_sse       -> JSON {message, conversation_id?, client_id?}, Accept: text/event-stream
   - POST ${API_BASE}/search_api     -> JSON {q, k?} (optional helper)
*/
(() => {
    // ====== Config ======
    const API_BASE = "/copilot"; // change to "/api/copilot" if your urls use that prefix
    const ENDPOINTS = {
        upload: `${API_BASE}/upload_files`,
        chat: `${API_BASE}/chat_sse`,
        search: `${API_BASE}/search_api`,
    };

    // ====== Safe markdown fallback ======
    window.marked = window.marked || {
        parse: (s) =>
            String(s || "")
                .replace(/&/g, "&amp;")
                .replace(/</g, "&lt;")
                .replace(/>/g, "&gt;")
                .replace(/\n/g, "<br>"),
    };

    // ====== Debug overlay (F9) ======
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
                window.addEventListener(
                    "keydown",
                    (e) => e.key === "F9" && el.classList.toggle("open")
                );
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

    // ====== Utils ======
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
    const getCSRF = () => {
        try {
            return (
                document.cookie
                    .split(";")
                    .map((c) => c.trim())
                    .find((c) => c.startsWith("csrftoken="))
                    ?.split("=")[1] || ""
            );
        } catch {
            return "";
        }
    };
    const normalizeMd = (s) =>
        (s || "").replace(/\r\n/g, "\n").replace(/\r/g, "\n").replace(/\\n/g, "\n");

    // Turn plain URLs/emails into <a> safely
    function linkifyHTML(html) {
        const root = document.createElement("div");
        root.innerHTML = html;
        const RE =
            /((?:https?:\/\/|www\.)[^\s<>()]+|[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,})/g;
        const isEmail = (s) => /^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(s);
        const isUrl = (s) => /^(?:https?:\/\/|www\.)/i.test(s);

        (function walk(node) {
            if (node.nodeType === 3) {
                const parts = node.nodeValue.split(RE);
                if (parts.length === 1) return;
                const frag = document.createDocumentFragment();
                for (let i = 0; i < parts.length; i++) {
                    let chunk = parts[i];
                    if (!chunk) continue;
                    if (RE.test(chunk)) {
                        RE.lastIndex = 0;
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
        const raw = normalizeMd(text || "");
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

    function addSources(chatEl, items) {
        if (!chatEl || !items?.length) return;
        const wrap = document.createElement("div");
        wrap.className = "bmb-b a bmb-sources";
        const list = document.createElement("ul");
        list.className = "bmb-src-list";
        items.slice(0, 6).forEach((h) => {
            const li = document.createElement("li");
            const a = document.createElement("a");
            a.href = h.url || "#";
            a.textContent = (h.title || h.url || "Kaynak").trim();
            a.target = "_blank";
            a.rel = "noopener noreferrer";
            const sn = document.createElement("div");
            sn.className = "snip";
            sn.textContent = (h.snippet || h.text || "").slice(0, 160);
            li.appendChild(a);
            if (sn.textContent) li.appendChild(sn);
            list.appendChild(li);
        });
        wrap.appendChild(list);
        const ts = document.createElement("div");
        ts.className = "bmb-ts";
        ts.textContent = new Date().toLocaleTimeString();
        wrap.appendChild(ts);
        chatEl.appendChild(wrap);
        chatEl.scrollTop = chatEl.scrollHeight;
    }

    // ===== Image gallery (for user preview only) =====
    function addImagePreview(chatEl, files) {
        const imgs = [...(files || [])].filter((f) => f.type.startsWith("image/"));
        if (!imgs.length) return;
        const urls = imgs.map((f) => URL.createObjectURL(f));
        const w = document.createElement("div");
        w.className = "bmb-b u";
        const grid = document.createElement("div");
        grid.className = "bmb-previews";
        urls.forEach((u) => {
            const im = document.createElement("img");
            im.src = u;
            im.alt = "preview";
            grid.appendChild(im);
        });
        w.appendChild(grid);
        const ts = document.createElement("div");
        ts.className = "bmb-ts";
        ts.textContent = new Date().toLocaleTimeString();
        w.appendChild(ts);
        chatEl.appendChild(w);
        chatEl.scrollTop = chatEl.scrollHeight;
        setTimeout(() => urls.forEach((u) => URL.revokeObjectURL(u)), 30000);
    }

    // ===== Typing indicator =====
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

    // ===== Modal shell =====
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
          <header class="bmb-h"><h2>AI Chatbot</h2><div class="s">Bambicim uzmanınız 💖</div></header>
          <div class="bmb-log" role="log" aria-live="polite"></div>
          <form class="bmb-row" autocomplete="off">
            <button class="bmb-clip" type="button" title="Dosya ekle" aria-label="Dosya ekle">📎</button>
            <input class="bmb-inp" type="text" placeholder="Mesaj yaz..." aria-label="Mesaj yaz">
            <div class="bmb-picks" aria-live="polite"></div>
            <input class="bmb-file" type="file" accept="image/*,.pdf,.txt,.md,.doc,.docx,.ppt,.pptx,.csv" multiple hidden>
            <div class="bmb-waves" aria-hidden="true"></div>
            <button class="bmb-mic" type="button" id="bmbMic" aria-pressed="false" title="Sesle yaz"></button>
            <button class="bmb-btn bmb-send" type="submit" id="bmbSend">Gönder</button>
          </form>
          <div class="bmb-disclaimer">Bambi, Bambicim için hazırlanmış deneysel bir sohbet asistanıdır.</div>
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

    // ===== Mount (SSE + uploads + voice) =====
    function mount(root, opts) {
        if (!root) return {
            destroy() {
            }
        };

        const chat = root.querySelector(".bmb-log");
        const input = root.querySelector(".bmb-inp");
        const form = root.querySelector("form");
        const mic = root.querySelector("#bmbMic");
        const waves = root.querySelector(".bmb-waves");
        const clip = root.querySelector(".bmb-clip");
        const fileInput = root.querySelector(".bmb-file");
        const picks = root.querySelector(".bmb-picks");

        // File chips (selected before sending)
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

        // ==== Voice (Web Speech API) ====
        const SR = window.SpeechRecognition || window.webkitSpeechRecognition;
        let rec = null, listening = false, starting = false;
        let finalBuf = "", interimBuf = "";
        let srKeepAlive = false;
        let mediaStream = null;
        let audioCtx = null, analyser = null, rafId = 0;

        function startWaves(stream) {
            if (!waves) return;
            try {
                let bars = Array.from(waves.querySelectorAll(".bar"));
                if (bars.length === 0) {
                    const frag = document.createDocumentFragment();
                    for (let i = 0; i < 28; i++) {
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
            input.classList.toggle("is-voice", !!on);
            input.placeholder = on ? "Dinliyorum…" : (input.getAttribute("data-oldph") || "Mesaj yaz...");
            input.setAttribute("aria-label", input.placeholder);
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
                mic && (mic.disabled = true);
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
        input?.addEventListener("keydown", () => {
            if (listening) srStop();
        });

        // ===== TTS toggle (optional) =====
        const panelEl = root.closest(".bmb-panel");
        const ttsBtn = panelEl?.querySelector(".bmb-tts");
        const tts = {
            enabled: false, voice: null, chosen: localStorage.getItem("bmb_tts_voice") || null,
            rate: 1.0, pitch: 1.1, volume: 1.0,
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
            let s = 0, n = (v.name || "").toLowerCase(), l = (v.lang || "").toLowerCase();
            if (l.startsWith("tr")) s += 5;
            if (l.includes("tr-tr")) s += 2;
            if (/seda|filiz|yelda|female|kadin/.test(n)) s += 6;
            if (/google|microsoft|online|natural/.test(n)) s += 2;
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

        function updateTtsBtn() {
            if (!ttsBtn) return;
            ttsBtn.classList.toggle("on", tts.enabled);
            ttsBtn.setAttribute("aria-pressed", String(tts.enabled));
            ttsBtn.textContent = tts.enabled ? "🔊" : "🔈";
            if (tts.voice) ttsBtn.title = `Sesi ${tts.enabled ? "kapat" : "aç"} · ${tts.voice.name}`;
        }

        function initVoicesOnce() {
            if (!ttsSupported()) return;
            tts.voice = pickVoice(tts.chosen);
            try {
                speechSynthesis.onvoiceschanged = () => {
                    const prev = tts.voice && tts.voice.name;
                    tts.voice = pickVoice(tts.chosen || prev);
                    updateTtsBtn();
                };
            } catch {
            }
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
            if (!tts.voice) tts.voice = pickVoice(tts.chosen);
            const idx = Math.max(0, list.findIndex((v) => tts.voice && v.name === tts.voice.name));
            const next = list[(idx + 1) % list.length];
            if (next) {
                tts.voice = next;
                tts.chosen = next.name;
                localStorage.setItem("bmb_tts_voice", next.name);
                updateTtsBtn();
            }
        });
        updateTtsBtn();
        if (ttsSupported()) initVoicesOnce();

        // ===== SSE send (with optional upload) =====
        let activeStream = null;

        async function sseSend(txt, files) {
            // cancel previous
            try {
                activeStream?.abort();
            } catch {
            }
            const ctrl = new AbortController();
            activeStream = ctrl;

            let conversation_id = localStorage.getItem("bmb_convo") || "";

            // upload if any
            if (files && files.length) {
                const fd = new FormData();
                [...files].forEach((f) => fd.append("files", f, f.name));
                if (conversation_id) fd.append("conversation_id", conversation_id);
                const up = await fetch(ENDPOINTS.upload, {
                    method: "POST",
                    body: fd,
                    credentials: "same-origin",
                    headers: {"X-CSRFToken": getCSRF()},
                    signal: ctrl.signal,
                }).catch(() => null);
                if (up && up.ok) {
                    const payload = await up.json().catch(() => []);
                    if (payload?.[0]?.conversation_id) {
                        conversation_id = payload[0].conversation_id;
                        localStorage.setItem("bmb_convo", conversation_id);
                    }
                }
            }

            // create assistant bubble for streaming
            const w = document.createElement("div");
            w.className = "bmb-b a";
            chat.appendChild(w);
            chat.scrollTop = chat.scrollHeight;

            // start stream
            const body = JSON.stringify({conversation_id, message: txt, client_id: getSid()});
            const resp = await fetch(ENDPOINTS.chat, {
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
                w.innerHTML = linkifyHTML(window.marked.parse("_Akış başlatılamadı._"));
                return;
            }

            let buffer = "", bucket = "";
            const reader = resp.body.getReader();
            const decoder = new TextDecoder();

            const flush = () => {
                if (!bucket) return;
                w.innerHTML = linkifyHTML(window.marked.parse(bucket));
                chat.scrollTop = chat.scrollHeight;
                // optional TTS
                if (tts.enabled && ttsSupported() && bucket) {
                    try {
                        speechSynthesis.cancel?.();
                        const u = new SpeechSynthesisUtterance(bucket.replace(/\[\d+\]/g, ""));
                        if (tts.voice) u.voice = tts.voice;
                        u.rate = tts.rate;
                        u.pitch = tts.pitch;
                        u.volume = tts.volume;
                        speechSynthesis.speak(u);
                    } catch {
                    }
                }
            };

            try {
                while (true) {
                    const {value, done} = await reader.read();
                    if (done) break;
                    buffer += decoder.decode(value, {stream: true});

                    const events = buffer.split("\n\n");
                    buffer = events.pop(); // keep last partial
                    for (const raw of events) {
                        // parse SSE block
                        let event = "message", data = "";
                        for (const line of raw.split("\n")) {
                            if (line.startsWith("event:")) event = line.slice(6).trim();
                            else if (line.startsWith("data:")) data += line.slice(5).trim();
                        }
                        if (event === "delta") {
                            try {
                                const j = JSON.parse(data);
                                bucket += j.text || "";
                                flush();
                            } catch {
                            }
                        } else if (event === "tool") {
                            try {
                                const j = JSON.parse(data);
                                if (j.name === "retrieve" && j.status === "end" && Array.isArray(j.result)) {
                                    addSources(chat, j.result);
                                }
                            } catch {
                            }
                        } else if (event === "done") {
                            try {
                                const j = JSON.parse(data);
                                if (j.conversation_id) localStorage.setItem("bmb_convo", j.conversation_id);
                            } catch {
                            }
                            flush();
                            const ts = document.createElement("div");
                            ts.className = "bmb-ts";
                            ts.textContent = new Date().toLocaleTimeString();
                            w.appendChild(ts);
                        }
                    }
                }
            } catch (e) {
                if (ctrl.signal.aborted) dlog("SSE aborted");
                else {
                    dlog("SSE error", e);
                    const err = document.createElement("div");
                    err.className = "bmb-b a";
                    err.innerHTML = linkifyHTML(window.marked.parse("_Akış kesildi. Tekrar deneyebilirsiniz._"));
                    chat.appendChild(err);
                }
            } finally {
                if (activeStream === ctrl) activeStream = null;
            }
        }

        // ===== Send handler =====
        function send() {
            const txt = (input?.value || "").trim();
            const files = fileInput?.files || null;
            if (!txt && (!files || files.length === 0)) return;

            if (txt) addBubble(chat, txt, "user");
            if (files && files.length) addImagePreview(chat, files);

            const removeTyping = showTyping(chat);
            sseSend(txt, files).finally(() => {
                try {
                    removeTyping();
                } catch {
                }
            });

            if (input) input.value = "";
            if (fileInput) {
                fileInput.value = "";
                renderPicks();
            }
        }

        // form events
        form?.addEventListener("submit", (e) => {
            e.preventDefault();
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
            if (!document.body.classList.contains("bmb-modal-open")) {
                try {
                    srStop();
                } catch {
                }
            }
        });
        mo.observe(document.body, {attributes: true, attributeFilter: ["class"]});

        // optional first message (non-blocking)
        const first = (opts.initialText || "").trim();
        if (first) {
            addBubble(chat, first, "user");
            sseSend(first, null);
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
