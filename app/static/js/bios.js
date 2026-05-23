// Lucky Card Boot Sequence — LuckyBIOS POST → Cursor blink 5x → Logo → Home
(function() {
    var scr = document.createElement('div');
    scr.id = 'bios-screen';
    document.body.prepend(scr);

    scr.innerHTML = `
        <div class="boot-layer bios-layer" id="biosLayer"></div>
        <div class="boot-layer logo-layer" id="logoLayer" style="display:none">
            <img src="/static/img/logo.svg" alt="Lucky Card" class="boot-logo">
            <div class="boot-brand">Lucky Card Professional Edition</div>
            <div class="boot-version" id="bootVer"></div>
        </div>
        <div class="xp-progress-bar" id="xpBar" style="display:none">
            <div class="xp-progress-track">
                <div class="xp-progress-blocks" id="xpBlocks">
                    <span class="b"></span><span class="b"></span><span class="b"></span>
                </div>
            </div>
        </div>
        <div class="wipe-curtain" id="wipeCurtain"></div>
    `;

    var biosLayer = scr.querySelector('#biosLayer');
    var logoLayer = scr.querySelector('#logoLayer');
    var verEl = scr.querySelector('#bootVer');
    var xpBar = scr.querySelector('#xpBar');
    var xpBlocks = scr.querySelector('#xpBlocks');
    var wipeCurtain = scr.querySelector('#wipeCurtain');

    // ===== Fan noise =====
    var fanCtx = null;
    var fanGain = null;
    // ===== Audio autoplay workaround =====
    var _pendingResume = true;
    function _resumeAudio() {
        if (!_pendingResume) return;
        _pendingResume = false;
        if (fanCtx && fanCtx.state === 'suspended') fanCtx.resume();
        document.removeEventListener('click', _resumeAudio);
        document.removeEventListener('keydown', _resumeAudio);
        document.removeEventListener('touchstart', _resumeAudio);
    }
    document.addEventListener('click', _resumeAudio);
    document.addEventListener('keydown', _resumeAudio);
    document.addEventListener('touchstart', _resumeAudio);

    function startFan() {
        try {
            fanCtx = new (window.AudioContext || window.webkitAudioContext)();
            if (fanCtx.state === 'suspended') fanCtx.resume();
            // Brown-ish noise via buffer
            var len = fanCtx.sampleRate * 2;
            var buf = fanCtx.createBuffer(1, len, fanCtx.sampleRate);
            var data = buf.getChannelData(0);
            var last = 0;
            for (var i = 0; i < len; i++) {
                var white = Math.random() * 2 - 1;
                last = (last + 0.02 * white) / 1.02;
                data[i] = last * 3.5;
            }
            var src = fanCtx.createBufferSource();
            src.buffer = buf; src.loop = true;
            var filter = fanCtx.createBiquadFilter();
            filter.type = 'lowpass'; filter.frequency.value = 200;
            fanGain = fanCtx.createGain();
            fanGain.gain.value = 0.04;
            src.connect(filter); filter.connect(fanGain); fanGain.connect(fanCtx.destination);
            src.start();
        } catch(e) {}
    }
    function stopFan() {
        if (fanGain) {
            fanGain.gain.linearRampToValueAtTime(0, fanCtx.currentTime + 0.3);
            setTimeout(function() { if (fanCtx) fanCtx.close(); }, 400);
        }
    }

    var biosLines = [
        { c: 'bios-brand', t: 'LuckyBIOS v1.0, An Energy Star Ally' },
        { c: 'bios-brand', t: 'Copyright (C) 2026, Lucky Card Technologies' },
        { t: '' },
        { c: 'bios-mem', t: 'Main Processor : OpenAI GPT-4o @ 2.8GHz' },
        { t: 'Memory Testing : 65536K OK' },
        { t: '' },
        { t: 'Detecting IDE drives...' },
        { c: 'bios-ok', t: '  Primary Master  : LuckyCard SSD 512GB [OK]' },
        { c: 'bios-ok', t: '  Secondary Master: Music Library 120GB [OK]' },
        { t: '' },
        { t: 'Initializing PCI devices...' },
        { c: 'bios-ok', t: '  [GPU]      NVIDIA Grace Hopper     [OK]' },
        { c: 'bios-ok', t: '  [NIC]      GlobalLink 10Gbps       [OK]' },
        { c: 'bios-ok', t: '  [AUDIO]    Blessing Sound System   [OK]' },
        { c: 'bios-ok', t: '  [CRYPTO]   Fortune Encryption      [OK]' },
        { t: '' },
        { c: 'bios-warn', t: 'WARNING: Luck levels critically high!' },
    ];

    function typeLine(text, cls, cb) {
        var d = document.createElement('div');
        d.className = 'bios-line' + (cls ? ' ' + cls : '');
        biosLayer.appendChild(d);
        var i = 0;
        function tick() {
            if (i < text.length) { d.textContent = text.substring(0, ++i); setTimeout(tick, 2 + Math.random() * 5); }
            else { if (cb) cb(); }
        }
        tick();
    }

    function runSeq(items, done) {
        var i = 0;
        function next() {
            if (i >= items.length) { done(); return; }
            var it = items[i];
            typeLine(it.t || '', it.c || null, function() { i++; setTimeout(next, it.t ? 15 : 5); });
        }
        next();
    }

    // Start fan on first line
    var fanStarted = false;
    var origTypeLine = typeLine;
    typeLine = function(text, cls, cb) {
        if (!fanStarted) { fanStarted = true; startFan(); }
        origTypeLine(text, cls, cb);
    };

    // === BIOS → blink 5x → loading ===
    runSeq(biosLines, function() {
        var d = document.createElement('div');
        d.className = 'bios-line';
        d.innerHTML = 'Starting Lucky Card OS<span class="bios-cursor"></span>';
        biosLayer.appendChild(d);
        setTimeout(act2, 2500);
    });

    // === Loading screen — longer, one hard freeze, two-step wipe ===
    function act2() {
        logoLayer.style.display = 'flex';
        xpBar.style.display = 'block';
        xpBlocks.style.animationDuration = '1.8s';

        var start = Date.now();
        var totalMs = 3500;
        var stallAtMs = 3080;
        var stallLen = 600;
        var stalled = false;

        function tick() {
            var now = Date.now();
            var rawElapsed = now - start;

            if (!stalled && rawElapsed < stallAtMs) {
                updateProgress(rawElapsed / totalMs * 100);
                requestAnimationFrame(tick);
                return;
            }

            if (!stalled && rawElapsed >= stallAtMs) {
                stalled = true;
                xpBlocks.style.animationPlayState = 'paused';
                updateProgress(88);
                requestAnimationFrame(tick);
                return;
            }

            if (stalled && rawElapsed < stallAtMs + stallLen) {
                requestAnimationFrame(tick);
                return;
            }

            if (stalled) {
                stalled = false;
                xpBlocks.style.animationPlayState = 'running';
            }

            var pct = (rawElapsed - stallLen) / totalMs * 100;
            if (pct < 100) {
                updateProgress(pct);
                requestAnimationFrame(tick);
                return;
            }

            // Stop fan
            stopFan();

            // Step 1: black curtain wipes down
            wipeCurtain.classList.add('drop');
            // Step 2: slide whole screen down
            setTimeout(function() {
                scr.classList.add('slide-down');
                setTimeout(function() { scr.remove(); }, 600);
            }, 500);
        }

        function updateProgress(pct) {
            if (pct < 50) verEl.textContent = 'v1.0 — loading...';
            else if (pct < 80) verEl.textContent = 'v1.0 — starting services...';
            else if (pct < 95) verEl.textContent = 'v1.0 — almost there...';
            else verEl.textContent = 'v1.0 — ready.';
        }

        requestAnimationFrame(tick);
    }
})();
