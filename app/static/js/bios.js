// Lucky Card Boot Sequence — LuckyBIOS POST → Cursor blink → Logo → Desktop
// All BIOS settings editable — wrong settings → real consequences
(function() {
    var scr = document.createElement('div');
    scr.id = 'bios-screen';
    document.body.prepend(scr);

    var _isMobile = ('ontouchstart' in window) || (navigator.maxTouchPoints > 0);

    // === ALL BIOS SETTINGS ===
    var _settings = {
        bootDevice: 0,        // 0=SSD, 1=PXE, 2=USB, 3=CD/DVD
        cpuConfig: 0,         // 0=Auto, 1=Manual
        hyperThreading: 1,    // 0=Disabled, 1=Enabled
        virtualization: 1,    // 0=Disabled, 1=Enabled
        gpuAccel: 1,          // 0=Disabled, 1=Enabled
        audioDevice: 1,       // 0=Disabled(Auto), 1=Enabled
        audioModel: 0,        // 0=Blessing Sound, 1=AC'97, 2=SB16
        networkStack: 1,      // 0=Disabled, 1=Enabled
        fortuneEncryption: 1, // 0=Disabled, 1=Enabled
        luckShield: 1,        // 0=Inactive, 1=Active
        quietBoot: 0,         // 0=Disabled, 1=Enabled
        fastBoot: 1,          // 0=Disabled, 1=Enabled
        numLock: 1,           // 0=Off, 1=On
    };

    var BOOT_DEVICES = ['LuckyCard SSD', 'Network: GlobalLink PXE', 'USB: LuckyKey', 'CD/DVD'];
    var AUDIO_MODELS = ['Blessing Sound System', 'AC\'97 Audio', 'Sound Blaster 16'];
    var _bootMode = null;  // null=normal, 'safemode', 'safemode-net', 'safemode-cmd', 'lastknown' 

    function toggle(name) {
        var keys = Object.keys(_settings);
        var opts = TOGGLE_OPTIONS[name];
        var cur = _settings[name];
        _settings[name] = (cur + 1) % opts.length;
    }

    var TOGGLE_OPTIONS = {
        cpuConfig: ['Auto', 'Manual'],
        hyperThreading: ['Disabled', 'Enabled'],
        virtualization: ['Disabled', 'Enabled'],
        gpuAccel: ['Disabled', 'Enabled'],
        audioDevice: ['Disabled', 'Enabled'],
        audioModel: AUDIO_MODELS,
        networkStack: ['Disabled', 'Enabled'],
        fortuneEncryption: ['Disabled', 'Enabled'],
        luckShield: ['Inactive', 'Active'],
        quietBoot: ['Disabled', 'Enabled'],
        fastBoot: ['Disabled', 'Enabled'],
        numLock: ['Off', 'On'],
    };

    function val(name) { return TOGGLE_OPTIONS[name][_settings[name]]; }
    function valColor(name) {
        var cur = _settings[name];
        var defVal = _DEFAULTS[name];
        if (cur === defVal) return '#0f0';
        return '#ff0';
    }
    var _DEFAULTS = JSON.parse(JSON.stringify(_settings));

    // === Cookie persistence ===
    var COOKIE_KEY = 'luckybios_cfg';
    function loadSettings() {
        try {
            var raw = document.cookie.split('; ').find(function(r) { return r.startsWith(COOKIE_KEY+'='); });
            if (raw) {
                var saved = JSON.parse(decodeURIComponent(raw.split('=')[1]));
                for (var k in saved) { if (_settings.hasOwnProperty(k)) _settings[k] = saved[k]; }
            }
        } catch(e) {}
    }
    function saveSettings() {
        var d = new Date(); d.setFullYear(d.getFullYear()+1);
        document.cookie = COOKIE_KEY+'='+encodeURIComponent(JSON.stringify(_settings))+';expires='+d.toUTCString()+';path=/;SameSite=Lax';
    }
    function clearSettings() {
        document.cookie = COOKIE_KEY+'=;expires=Thu,01 Jan 1970 00:00:00 GMT;path=/';
    }
    loadSettings();

    // ===== HTML =====
    scr.innerHTML = `
        <div class="boot-layer bios-layer" id="biosLayer"></div>
        <div class="boot-layer logo-layer" id="logoLayer" style="display:none">
            <img src="/static/img/logo.svg" alt="Lucky Card" class="boot-logo">
            <div class="boot-brand">Lucky Card Professional</div>
            <div class="boot-version" id="bootVer"></div>
        </div>
        <div class="boot-layer setup-layer" id="setupLayer" style="display:none"></div>
        <div class="boot-layer error-layer" id="errorLayer" style="display:none"></div>
        <div class="boot-layer f8-layer" id="f8Layer" style="display:none"></div>
        <div class="xp-progress-bar" id="xpBar" style="display:none">
            <div class="xp-progress-track"><div class="xp-progress-blocks" id="xpBlocks">
                <span class="b"></span><span class="b"></span><span class="b"></span>
            </div></div>
        </div>
        <div class="wipe-curtain" id="wipeCurtain"></div>
    `;

    var biosLayer = scr.querySelector('#biosLayer');
    var logoLayer = scr.querySelector('#logoLayer');
    var setupLayer = scr.querySelector('#setupLayer');
    var errorLayer = scr.querySelector('#errorLayer');
    var f8Layer = scr.querySelector('#f8Layer');
    var verEl = scr.querySelector('#bootVer');
    var xpBar = scr.querySelector('#xpBar');
    var xpBlocks = scr.querySelector('#xpBlocks');
    var wipeCurtain = scr.querySelector('#wipeCurtain');

    // ===== Fan =====
    var _fanAudio = new Audio('/static/audio/fan-noise.mp3');
    _fanAudio.volume = 0.02; _fanAudio.muted = true; _fanAudio.loop = true;
    _fanAudio.play().catch(function(){});
    function startFan() { _fanAudio.muted = false; _fanAudio.currentTime = 0; _fanAudio.play().catch(function(){}); }
    function stopFan() {
        var f=10, iv=80, sv=_fanAudio.volume, s=0;
        var fo = setInterval(function(){
            s++; _fanAudio.volume = Math.max(0, sv*(1-s/f));
            if (s>=f) { clearInterval(fo); _fanAudio.pause(); _fanAudio.muted = true; }
        }, iv);
    }

    // ===== SETUP =====
    var setupScreen = false, setupPhase = false, bootAfterSetup = false;
    var _activeTab = 0;  // Track which BIOS tab is active
    var SETUP_KEY_TIMEOUT = 3500;

    function openSetup() {
        if (setupScreen) return;
        setupScreen = true; bootAfterSetup = true;
        biosLayer.style.display = 'none';
        logoLayer.style.display = 'none';
        if (xpBar) xpBar.style.display = 'none';
        stopFan();
        setupLayer.style.display = 'block';
        renderSetupMain();
    }

    function settingRow(label, name, desc) {
        var v = val(name), c = valColor(name);
        return '<tr class="setup-clickable" data-setting="'+name+'" style="cursor:pointer">' +
            '<td style="padding:3px 8px;color:#aaa;width:220px">'+label+'</td>' +
            '<td style="padding:3px 8px;color:'+c+'">['+v+']</td>' +
            '<td style="padding:3px 8px;color:#666;font-size:11px">'+desc+'</td></tr>';
    }

    function bootPriorityRows() {
        var rows = '';
        for (var i=0; i<BOOT_DEVICES.length; i++) {
            var c = (i===0) ? (_settings.bootDevice===i ? '#0f0' : '#ff0') : '#aaa';
            var tag = (i===0) ? (_settings.bootDevice===i ? ' ← BOOT' : ' ← click to change') : '';
            rows += '<tr class="setup-clickable" data-setting="bootDevice" data-val="'+i+'" style="cursor:pointer">' +
                '<td style="padding:3px 8px;color:'+c+';width:30px">'+(i+1)+'</td>' +
                '<td style="padding:3px 8px;color:'+c+'">['+BOOT_DEVICES[i]+']</td>' +
                '<td style="padding:3px 8px;color:#0f0;font-size:10px">'+tag+'</td></tr>';
        }
        return rows;
    }

    function renderSetupMain(tab) {
        if (tab === undefined) tab = 0;
        _activeTab = tab;  // Track for keyboard shortcuts
        var tabs = ['Main', 'Advanced', 'Boot', 'Exit'];
        var content = '';

        if (tab === 0) {
            content =
                '<div style="padding:8px 0"><span style="color:#fff">System Information</span></div>' +
                '<table style="width:100%;color:#fff;font-size:13px;border-collapse:collapse">' +
                '<tr><td style="padding:3px 8px;color:#aaa;width:200px">BIOS Version</td><td style="padding:3px 8px">LuckyBIOS v1.0</td></tr>' +
                '<tr><td style="padding:3px 8px;color:#aaa">BIOS Date</td><td style="padding:3px 8px">05/23/2026</td></tr>' +
                '<tr><td style="padding:3px 8px;color:#aaa">Processor</td><td style="padding:3px 8px">CPU: Open(R) AI(TM) GPT v1.0</td></tr>' +
                '<tr><td style="padding:3px 8px;color:#aaa">System Memory</td><td style="padding:3px 8px">65536 KB</td></tr>' +
                '<tr><td style="padding:3px 8px;color:#aaa">System Time</td><td style="padding:3px 8px" id="setupTime"></td></tr>' +
                '<tr><td style="padding:3px 8px;color:#aaa">System Date</td><td style="padding:3px 8px" id="setupDate"></td></tr>' +
                '</table>' +
                '<div style="margin-top:12px;color:#fff"><span style="color:#aaa">IDE Configuration</span></div>' +
                '<table style="width:100%;color:#fff;font-size:13px;border-collapse:collapse">' +
                '<tr><td style="padding:3px 8px;color:#aaa;width:200px">Primary Master</td><td style="padding:3px 8px">[LuckyCard SSD 512GB]</td></tr>' +
                '<tr><td style="padding:3px 8px;color:#aaa">Secondary Master</td><td style="padding:3px 8px">[Music Library 120GB]</td></tr>' +
                '</table>';
        } else if (tab === 1) {
            content =
                '<div style="padding:8px 0"><span style="color:#fff">Advanced Settings</span></div>' +
                '<div style="margin:4px 0;color:#888;font-size:11px">Click any value to change — yellow = non-default</div>' +
                '<table style="width:100%;color:#fff;font-size:13px;border-collapse:collapse">' +
                settingRow('CPU Configuration', 'cpuConfig', 'Manual may cause instability') +
                settingRow('Hyper-Threading', 'hyperThreading', 'Disable for single-core mode') +
                settingRow('Virtualization', 'virtualization', 'Required for VM sandbox') +
                settingRow('GPU Acceleration', 'gpuAccel', 'Disabling = no display output') +
                '</table>' +
                '<div style="margin-top:12px;color:#fff"><span style="color:#aaa">Peripheral Configuration</span></div>' +
                '<table style="width:100%;color:#fff;font-size:13px;border-collapse:collapse">' +
                settingRow('Audio Device', 'audioDevice', 'Onboard sound controller') +
                settingRow('Audio Model', 'audioModel', 'Sound card emulation') +
                settingRow('Network Stack', 'networkStack', 'GlobalLink 10Gbps NIC') +
                '</table>' +
                '<div style="margin-top:12px;color:#fff"><span style="color:#aaa">Security</span></div>' +
                '<table style="width:100%;color:#fff;font-size:13px;border-collapse:collapse">' +
                settingRow('Fortune Encryption', 'fortuneEncryption', 'Encrypt luck data at rest') +
                settingRow('Luck Shield', 'luckShield', 'Active protection against bad vibes') +
                '</table>';
        } else if (tab === 2) {
            content =
                '<div style="padding:8px 0"><span style="color:#fff">Boot Settings</span></div>' +
                '<div style="margin:4px 0;color:#888;font-size:11px">Click a device to promote to 1st boot — or press +/- to cycle</div>' +
                '<table style="width:100%;color:#fff;font-size:13px;border-collapse:collapse" id="bootPriorityTable">' +
                bootPriorityRows() +
                '</table>' +
                '<div style="margin-top:12px">' +
                '<table style="width:100%;color:#fff;font-size:13px;border-collapse:collapse">' +
                settingRow('Quiet Boot', 'quietBoot', 'Show logo instead of POST text') +
                settingRow('Fast Boot', 'fastBoot', 'Skip memory test on boot') +
                settingRow('Bootup NumLock', 'numLock', 'NumLock state at startup') +
                '</table></div>';
        } else if (tab === 3) {
            var changed = false;
            for (var k in _settings) { if (_settings[k] !== _DEFAULTS[k]) { changed = true; break; } }
            var sColor = (_settings.bootDevice===0 && _settings.gpuAccel===1 && _settings.luckShield===1) ? '#0f0' : '#ff0';
            content =
                '<div style="padding:8px 0"><span style="color:#fff">Exit Options</span></div>' +
                (changed ? '<div style="color:#ff0;font-size:11px;margin-bottom:8px">⚠ Settings have been changed from defaults</div>' : '') +
                '<table style="width:100%;color:#fff;font-size:13px;border-collapse:collapse">' +
                '<tr id="exitSave" class="setup-clickable" style="cursor:pointer"><td style="padding:5px 8px;color:'+sColor+'">▶ Save & Exit Setup</td><td style="padding:3px 8px;color:#aaa">Write changes to CMOS and boot</td></tr>' +
                '<tr id="exitDiscard" class="setup-clickable" style="cursor:pointer"><td style="padding:5px 8px;color:#aaa">▶ Exit Without Saving</td><td style="padding:3px 8px;color:#888">Discard changes and boot</td></tr>' +
                '<tr id="exitDefaults" class="setup-clickable" style="cursor:pointer"><td style="padding:5px 8px;color:#aaa">▶ Load Optimized Defaults</td><td style="padding:3px 8px;color:#888">Restore factory settings</td></tr>' +
                '</table>' +
                '<div style="margin-top:16px;color:#0f0;font-size:12px">► Press Enter to Save &amp; Exit</div>';
        }

        var h = '<div class="setup-container">';
        h += '<div class="setup-header">LuckyBIOS Setup Utility — v1.0</div>';
        h += '<div class="setup-tabs">';
        for (var i=0; i<tabs.length; i++) {
            h += '<div class="setup-tab'+(i===tab?' active':'')+'" data-tab="'+i+'">'+tabs[i]+'</div>';
        }
        h += '</div>';
        h += '<div class="setup-body">'+content+'</div>';
        h += '<div class="setup-footer">';
        if (_isMobile) {
            h += '<span>◀ Swipe ▶</span><span class="setup-boot-btn" id="setupBootBtn">🟢 BOOT</span>';
        } else {
            h += '<span>← → Tab</span><span>Click to Change</span><span>+/- Boot Order</span><span>Enter Boot</span><span>ESC Exit</span>';
        }
        h += '</div></div>';
        setupLayer.innerHTML = h;

        // Tab clicks
        setupLayer.querySelectorAll('.setup-tab').forEach(function(el) {
            el.onclick = function() { renderSetupMain(parseInt(this.getAttribute('data-tab'))); };
        });

        // Event delegation on setup body — catches all clickable rows
        var body = setupLayer.querySelector('.setup-body');
        body.onclick = function(e) {
            var row = e.target.closest('.setup-clickable');
            if (!row) return;
            var name = row.getAttribute('data-setting');
            if (name === 'bootDevice') {
                _settings.bootDevice = parseInt(row.getAttribute('data-val'));
                renderSetupMain(tab);
            } else if (TOGGLE_OPTIONS[name]) {
                _settings[name] = (_settings[name] + 1) % TOGGLE_OPTIONS[name].length;
                renderSetupMain(tab);
            }
        };

        // Exit options
        var saveBtn = document.getElementById('exitSave');
        var discardBtn = document.getElementById('exitDiscard');
        var defaultsBtn = document.getElementById('exitDefaults');
        if (saveBtn) saveBtn.onclick = function() { exitSetupAndBoot(true); };
        if (discardBtn) discardBtn.onclick = function() {
            _settings = JSON.parse(JSON.stringify(_DEFAULTS));
            clearSettings();
            exitSetupAndBoot(false);
        };
        if (defaultsBtn) defaultsBtn.onclick = function() {
            _settings = JSON.parse(JSON.stringify(_DEFAULTS));
            clearSettings();
            renderSetupMain(3);
        };

        var bootBtn = document.getElementById('setupBootBtn');
        if (bootBtn) bootBtn.onclick = function() { exitSetupAndBoot(true); };

        // Mobile swipe
        if (_isMobile) {
            var tsx=0, tsy=0;
            body.addEventListener('touchstart', function(e) { tsx=e.touches[0].clientX; tsy=e.touches[0].clientY; }, {passive:true});
            body.addEventListener('touchend', function(e) {
                var dx=e.changedTouches[0].clientX-tsx, dy=e.changedTouches[0].clientY-tsy;
                if (Math.abs(dx)>Math.abs(dy) && Math.abs(dx)>40) {
                    var nt = tab + (dx<0?1:-1);
                    nt = ((nt%tabs.length)+tabs.length)%tabs.length;
                    renderSetupMain(nt);
                }
            });
        }

        updateSetupClock();
        setInterval(updateSetupClock, 1000);
    }

    function updateSetupClock() {
        var n = new Date();
        var te = document.getElementById('setupTime');
        var de = document.getElementById('setupDate');
        if (te) te.textContent = n.toLocaleTimeString('en-US', {hour12: false});
        if (de) de.textContent = n.toLocaleDateString('en-US', {month:'2-digit',day:'2-digit',year:'numeric'});
    }

    // ===== Exit & Boot — check all settings =====
    function exitSetupAndBoot(save) {
        setupLayer.style.display = 'none';

        if (save) {
            saveSettings();
            // Check for fatal misconfigurations
            if (_settings.bootDevice !== 0) {
                var bootErrors = {
                    1: { title: 'PXE-E61: Media test failure',
                         msg: 'PXE-E61: Media test failure, check cable\nPXE-M0F: Exiting PXE ROM.\n\nReboot and Select proper Boot device\nor Insert Boot Media in selected Boot device\nand press a key' },
                    2: { title: 'Reboot and Select proper Boot device',
                         msg: 'Reboot and Select proper Boot device\nor Insert Boot Media in selected Boot device\nand press a key' },
                    3: { title: 'Boot from CD/DVD :',
                         msg: 'Boot from CD/DVD :\nDISK BOOT FAILURE, INSERT SYSTEM DISK\nAND PRESS ENTER' }
                };
                var be = bootErrors[_settings.bootDevice] || bootErrors[2];
                showError(be.title, be.msg);
                return;
            }
            if (_settings.gpuAccel === 0) {
                showError('No display device detected',
                    'GPU acceleration is disabled.\nCannot initialize video output.');
                return;
            }
            if (_settings.luckShield === 0) {
                showError('SYSTEM HALTED',
                    'Luck Shield is INACTIVE.\nCritical luck levels detected.\nSystem halted for your protection.');
                return;
            }
            if (_settings.hyperThreading === 0 || _settings.cpuConfig === 1) {
                // Non-fatal but show warning, then boot
                showWarningThenBoot('CPU Configuration Warning',
                    'Non-default CPU settings detected.\nSystem may be unstable.\n\nBooting anyway...');
                return;
            }
        }

        // Normal boot
        if (_bootMode) {
            applySafeMode();
            safeModeBoot();
        } else {
            logoLayer.style.display = 'flex';
            xpBar.style.display = 'block';
            xpBlocks.style.animationDuration = '1.8s';
            runLoadingScreen();
        }
    }

    function showError(title, msg) {
        errorLayer.style.display = 'block';
        errorLayer.innerHTML =
            '<div style="position:absolute;inset:0;background:#000;color:#fff;font-family:\'Courier New\',monospace;display:flex;flex-direction:column;align-items:center;justify-content:center">' +
            '<div style="font-size:20px;font-weight:bold;margin-bottom:16px;letter-spacing:1px">'+escHtml2(title)+'</div>' +
            '<div style="font-size:14px;color:#aaa;text-align:center;line-height:1.8;white-space:pre-line">'+escHtml2(msg)+'</div>' +
            '<div style="margin-top:24px"><span class="error-cursor"></span></div>' +
            '</div>' +
            '<div class="error-restart" style="position:absolute;bottom:60px;left:50%;transform:translateX(-50%);color:#888;font-family:\'Courier New\',monospace;font-size:12px;animation:blink 1s step-end infinite">' +
            'Press any key to restart</div>';
        bindErrorRestart();
    }

    function showWarningThenBoot(title, msg) {
        errorLayer.style.display = 'block';
        errorLayer.innerHTML =
            '<div style="position:absolute;inset:0;background:#000;color:#ff0;font-family:\'Courier New\',monospace;display:flex;flex-direction:column;align-items:center;justify-content:center">' +
            '<div style="font-size:18px;font-weight:bold;margin-bottom:12px">'+escHtml2(title)+'</div>' +
            '<div style="font-size:13px;color:#aaa;text-align:center;line-height:1.8;white-space:pre-line">'+escHtml2(msg)+'</div>' +
            '</div>';
        setTimeout(function() {
            errorLayer.style.display = 'none';
            logoLayer.style.display = 'flex';
            xpBar.style.display = 'block';
            runLoadingScreen();
        }, 2500);
    }

    function escHtml2(s) {
        var d = document.createElement('div'); d.textContent = s; return d.innerHTML;
    }

    function bindErrorRestart() {
        function rk(e) { e.preventDefault(); document.removeEventListener('keydown',rk); errorLayer.removeEventListener('touchend',rk); location.reload(); }
        document.addEventListener('keydown', rk);
        errorLayer.addEventListener('touchend', rk);
    }

    // ===== BIOS POST =====
    var biosLines = [
        { c:'bios-brand', t:'LuckyBIOS v1.0, An Energy Star Ally' },
        { c:'bios-brand', t:'Copyright (C) 2026, Lucky Card Technologies' },
        { t:'' },
        { c:'bios-mem', t:'CPU: Open(R) AI(TM) GPT v1.0' },
        { t:'Memory Testing : 65536K OK' },
        { t:'' },
        { t:'Detecting IDE drives...' },
        { c:'bios-ok', t:'  Primary Master  : LuckyCard SSD 512GB [OK]' },
        { c:'bios-ok', t:'  Secondary Master: Music Library 120GB [OK]' },
        { t:'' },
        { t:'Initializing PCI devices...' },
        { c:'bios-ok', t:'  [GPU]      NVIDIA Grace Hopper     [OK]' },
        { c:'bios-ok', t:'  [NIC]      GlobalLink 10Gbps       [OK]' },
        { c:'bios-ok', t:'  [AUDIO]    Blessing Sound System   [OK]' },
        { c:'bios-ok', t:'  [CRYPTO]   Fortune Encryption      [OK]' },
        { t:'' },
        { c:'bios-warn', t:'WARNING: Luck levels critically high!' },
    ];

    function typeLine(text, cls, cb) {
        var d = document.createElement('div');
        d.className = 'bios-line'+(cls?' '+cls:'');
        biosLayer.appendChild(d);
        var i=0;
        function tick() {
            if (i<text.length) { d.textContent=text.substring(0,++i); setTimeout(tick,2+Math.random()*5); }
            else { if(cb) cb(); }
        }
        tick();
    }
    function runSeq(items, done) {
        var i=0;
        function next() {
            if (i>=items.length) { done(); return; }
            var it=items[i];
            typeLine(it.t||'', it.c||null, function(){ i++; setTimeout(next, it.t?15:5); });
        }
        next();
    }

    var fanStarted = false;
    var origTypeLine = typeLine;
    typeLine = function(text, cls, cb) {
        if (!fanStarted) { fanStarted=true; startFan(); }
        origTypeLine(text, cls, cb);
    };

    var _setupTimeout = null, _blinkInterval = null;

    function stopPromptAndBoot() {
        if (_blinkInterval) clearInterval(_blinkInterval);
        if (_setupTimeout) clearTimeout(_setupTimeout);
        setupPhase = false;
        document.removeEventListener('keydown', onSetupKey);
        scr.removeEventListener('touchstart', onTouchStart);
        scr.removeEventListener('touchend', onTouchEnd);
        var bl = document.createElement('div');
        bl.className = 'bios-line';
        bl.innerHTML = 'Starting Lucky Card OS<span class="bios-cursor"></span>';
        biosLayer.appendChild(bl);
        setTimeout(function(){ act2(); }, 600);
    }

    function clearPrompt() {
        if (_blinkInterval) clearInterval(_blinkInterval);
        if (_setupTimeout) clearTimeout(_setupTimeout);
        setupPhase = false;
        document.removeEventListener('keydown', onSetupKey);
        scr.removeEventListener('touchstart', onTouchStart);
        scr.removeEventListener('touchend', onTouchEnd);
    }

    function onSetupKey(e) {
        if (e.key==='F8') {
            e.preventDefault();
            if (setupPhase && !setupScreen) { clearPrompt(); showF8Menu(); }
        } else if (e.key==='Delete'||e.key==='Del'||e.key==='Escape'||e.key==='Esc') {
            e.preventDefault();
            if (setupScreen) { exitSetupAndBoot(true); }
            else if (setupPhase) { clearPrompt(); openSetup(); }
        } else if (setupScreen && e.key==='Enter') { e.preventDefault(); exitSetupAndBoot(true); }
        else if (setupScreen && (e.key==='ArrowLeft'||e.key==='ArrowRight')) {
            e.preventDefault();
            var tabs = setupLayer.querySelectorAll('.setup-tab');
            var ai = 3;
            for (var ti=0; ti<tabs.length; ti++) {
                if (tabs[ti].classList.contains('active')) { ai=ti; break; }
            }
            ai = (e.key==='ArrowLeft') ? (ai-1+tabs.length)%tabs.length : (ai+1)%tabs.length;
            renderSetupMain(ai);
        } else if (setupScreen && _activeTab === 2 && (e.key==='+' || e.key==='=')) {
            e.preventDefault();
            _settings.bootDevice = (_settings.bootDevice + 1) % BOOT_DEVICES.length;
            renderSetupMain(2);
        } else if (setupScreen && _activeTab === 2 && e.key==='-') {
            e.preventDefault();
            _settings.bootDevice = (_settings.bootDevice - 1 + BOOT_DEVICES.length) % BOOT_DEVICES.length;
            renderSetupMain(2);
        }
    }
    document.addEventListener('keydown', onSetupKey);

    var _touchStartTime = 0, _longPressTimer = null;
    function onTouchStart(e) {
        if (setupScreen||!setupPhase) return;
        _touchStartTime = Date.now();
        _longPressTimer = setTimeout(function() {
            // Long press detected (> 1.5s) — enter F8 boot menu
            clearPrompt();
            showF8Menu();
        }, 1500);
    }
    function onTouchEnd(e) {
        if (_longPressTimer) clearTimeout(_longPressTimer);
        if (setupScreen||!setupPhase) return;
        var duration = Date.now() - _touchStartTime;
        if (duration < 1500) {
            // Short tap — enter SETUP
            e.preventDefault();
            clearPrompt();
            openSetup();
        }
    }

    // ===== F8 Boot Menu =====
    var F8_OPTIONS = [
        { key: '1', label: 'Safe Mode', desc: 'Minimal drivers and services. No GPU acceleration.' },
        { key: '2', label: 'Safe Mode with Networking', desc: 'Safe Mode + GlobalLink 10Gbps NIC enabled.' },
        { key: '3', label: 'Safe Mode with Command Prompt', desc: 'Boot to CMD.EXE. No desktop shell.' },
        { key: '4', label: 'Last Known Good Configuration', desc: 'Restore last working registry snapshot.' },
        { key: '5', label: 'Start LuckyCard OS Normally', desc: 'Default boot — all drivers loaded.' },
    ];
    var F8_MENU_TIMEOUT = 30000;
    var _f8Timeout = null;

    function showF8Menu() {
            biosLayer.style.display = 'none';
            f8Layer.style.display = 'block';
            var h = '<div style="background:#000;color:#fff;font-family:"Courier New",monospace;font-size:14px;padding:40px;height:100%;box-sizing:border-box;display:flex;flex-direction:column;justify-content:center">';
            h += '<div style="font-size:20px;font-weight:bold;margin-bottom:4px;letter-spacing:1px">Windows Advanced Options Menu</div>';
            h += '<div style="color:#aaa;margin-bottom:24px;font-size:12px">Please select an option:</div>';
            for (var i=0; i<F8_OPTIONS.length; i++) {
                var opt = F8_OPTIONS[i];
                var hl = (i===4) ? 'color:#ff0;' : '';
                h += '<div style="padding:4px 0;'+hl+'"><span style="color:#aaa;margin-right:12px">['+opt.key+']</span>' + opt.label + '</div>';
                h += '<div style="color:#666;font-size:11px;padding-left:30px;margin-bottom:6px">' + opt.desc + '</div>';
            }
            h += '<div style="margin-top:20px;color:#aaa;font-size:12px">Use ↑ and ↓ to highlight. Enter to choose. Auto starts in ' + (F8_MENU_TIMEOUT/1000) + 's...</div>';
            h += '</div>';
            f8Layer.innerHTML = h;

            var _f8Sel = 4;  // Default: Start Normally
            function renderF8() {
                var lines = f8Layer.querySelectorAll('div[style]');
                var idx = 0;
                for (var i=0; i<lines.length; i++) {
                    if (lines[i].textContent && lines[i].textContent.match(/^\[/)) {
                        var bg = (idx === _f8Sel) ? '#3168D5' : 'transparent';
                        lines[i].style.background = bg;
                        idx++;
                    }
                }
            }
            renderF8();

            // Mobile: tap to select
            if (_isMobile) {
                var items = f8Layer.querySelectorAll('div');
                var optIdx = 0;
                for (var i = 0; i < items.length; i++) {
                    if (items[i].textContent && items[i].textContent.match(/^\[/)) {
                        (function(idx) {
                            items[i].style.cursor = 'pointer';
                            items[i].onclick = function() { selectF8(idx); };
                        })(optIdx);
                        optIdx++;
                    }
                }
            }

            function f8Key(e) {
                if (e.key >= '1' && e.key <= '5') {
                    e.preventDefault();
                    _f8Sel = parseInt(e.key) - 1;
                    selectF8(_f8Sel);
                } else if (e.key === 'ArrowUp') {
                    e.preventDefault();
                    _f8Sel = (_f8Sel - 1 + F8_OPTIONS.length) % F8_OPTIONS.length;
                    renderF8();
                } else if (e.key === 'ArrowDown') {
                    e.preventDefault();
                    _f8Sel = (_f8Sel + 1) % F8_OPTIONS.length;
                    renderF8();
                } else if (e.key === 'Enter') {
                    e.preventDefault();
                    selectF8(_f8Sel);
                }
            }
            document.addEventListener('keydown', f8Key);

            function selectF8(idx) {
                document.removeEventListener('keydown', f8Key);
                if (_f8Timeout) clearTimeout(_f8Timeout);
                if (idx === 4) {
                    // Start Normally
                    _bootMode = null;
                } else if (idx === 0) {
                    _bootMode = 'safemode';
                } else if (idx === 1) {
                    _bootMode = 'safemode-net';
                } else if (idx === 2) {
                    _bootMode = 'safemode-cmd';
                } else if (idx === 3) {
                    _bootMode = 'lastknown';
                }
                if (_bootMode) {
                    document.cookie = 'luckybios_bootmode=' + _bootMode + ';path=/;SameSite=Lax';
                }
                f8Boot();
            }

            _f8Timeout = setTimeout(function() { selectF8(4); }, F8_MENU_TIMEOUT);

            function f8Boot() {
                f8Layer.style.display = 'none';
                biosLayer.style.display = 'block';
                var bl = document.createElement('div');
                bl.className = 'bios-line';
                bl.innerHTML = 'Starting Lucky Card OS<span class="bios-cursor"></span>';
                biosLayer.appendChild(bl);
                setTimeout(function(){ act2(); }, 600);
            }
    }

    // === BIOS POST complete ===
    runSeq(biosLines, function() {
        setupPhase = true;

        var sp = document.createElement('div');
        sp.className = 'bios-line bios-setup-prompt';
        if (_isMobile) {
            sp.textContent = 'Tap = SETUP  |  Hold = Boot Menu';
            sp.style.cursor = 'pointer'; sp.style.fontSize = '14px'; sp.style.padding = '8px 0';
            scr.addEventListener('touchstart', onTouchStart);
            scr.addEventListener('touchend', onTouchEnd);
        } else {
            sp.textContent = 'Press DEL or ESC to enter SETUP';
        }
        biosLayer.appendChild(sp);

        var f8p = document.createElement('div');
        f8p.className = 'bios-line';
        f8p.textContent = 'Press F8 to choose Operating System.';
        biosLayer.appendChild(f8p);

        _setupTimeout = setTimeout(function(){ stopPromptAndBoot(); }, SETUP_KEY_TIMEOUT);
    });

    function act2() {
        if (bootAfterSetup) return;
        if (_bootMode) {
            // Safe mode — show text driver loading
            applySafeMode();
            safeModeBoot();
        } else {
            logoLayer.style.display = 'flex'; xpBar.style.display = 'block';
            xpBlocks.style.animationDuration = '1.8s';
            runLoadingScreen();
        }
    }

    // ===== BSOD (Blue Screen of Death) =====
    function showBSOD() {
        errorLayer.style.display = 'block';
        var codes = [
            { name:'LUCK_OVERFLOW_ERROR', code:'0x0000007E', desc:'Luck levels exceeded safe threshold.\nThe Luck Shield was unable to contain the overflow.' },
            { name:'IRQL_NOT_LESS_OR_EQUAL', code:'0x0000000A', desc:'A kernel-mode process attempted to access\nmemory at an invalid IRQL level.' },
            { name:'PAGE_FAULT_IN_NONPAGED_AREA', code:'0x00000050', desc:'The system attempted to access pageable memory\nat a process IRQL that was too high.' },
            { name:'KERNEL_MODE_EXCEPTION_NOT_HANDLED', code:'0x0000008E', desc:'An unhandled exception occurred in the\nLucky Card kernel mode driver.' },
            { name:'NTFS_FILE_SYSTEM', code:'0x00000024', desc:'A problem occurred in ntfs.sys.\nCannot read boot sector of LuckyCard SSD.' },
            { name:'FORTUNE_CORRUPTION', code:'0x000000C4', desc:'Fortune Encryption driver detected\ncorrupted luck data in the registry.' },
            { name:'DRIVER_IRQL_NOT_LESS_OR_EQUAL', code:'0x000000D1', desc:'luckycard.sys attempted to access pageable\nmemory at DISPATCH_LEVEL or above.' },
            { name:'UNMOUNTABLE_BOOT_VOLUME', code:'0x000000ED', desc:'The Lucky Card boot volume could not be\nmounted. Luck partition may be corrupted.' }
        ];
        var bsod = codes[Math.floor(Math.random() * codes.length)];

        var h = '<div style="position:absolute;inset:0;background:#0000aa;color:#fff;font-family:\'Courier New\',monospace;font-size:13px;padding:40px 60px;overflow:hidden">';
        h += '<div style="background:#aaa;color:#0000aa;text-align:center;padding:4px 0;font-size:16px;font-weight:bold;margin-bottom:20px;letter-spacing:2px">Lucky Card</div>';
        h += '<div style="margin-bottom:16px">';
        h += '<p style="margin:0 0 8px 0">A problem has been detected and Lucky Card has been shut down to prevent damage to your computer.</p>';
        h += '<p style="margin:0 0 16px 0">'+bsod.desc+'</p>';
        h += '<p style="margin:0 0 4px 0">If this is the first time you\'ve seen this Stop error screen, restart your computer. If this screen appears again, follow these steps:</p>';
        h += '<p style="margin:0 0 4px 0">Check to make sure any new hardware or software is properly installed. If this is a new installation, ask your hardware or software manufacturer for any Lucky Card updates you might need.</p>';
        h += '<p style="margin:0 0 4px 0">If problems continue, disable or remove any newly installed hardware or software. Disable BIOS memory options such as caching or shadowing. If you need to use Safe Mode to remove or disable components, restart your computer, press F8 to select Advanced Startup Options, and then select Safe Mode.</p>';
        h += '</div>';
        h += '<div style="margin-bottom:12px">';
        h += '<p style="margin:0 0 4px 0">Technical information:</p>';
        h += '<p style="margin:0 0 4px 0;font-size:15px;font-weight:bold">*** STOP: '+bsod.code+' (0xFFFFFA80, 0x00000000, 0x'+Math.random().toString(16).substr(2,8).toUpperCase()+', 0x'+Math.random().toString(16).substr(2,8).toUpperCase()+')</p>';
        h += '<p style="margin:0 0 4px 0">*** '+bsod.name+' — Address 0x'+Math.random().toString(16).substr(2,8).toUpperCase()+' base at 0x'+Math.random().toString(16).substr(2,8).toUpperCase()+', DateStamp 0x4a5b'+Math.random().toString(16).substr(2,6).toUpperCase()+'</p>';
        h += '</div>';
        h += '<div id="bsodDump" style="margin-top:4px">';
        h += '<p style="margin:0">Beginning dump of physical memory</p>';
        h += '<p style="margin:0">Physical memory dump complete.</p>';
        h += '<p style="margin:0">Contact your system administrator or technical support group for further assistance.</p>';
        h += '</div>';
        h += '</div>';

        errorLayer.innerHTML = h;

        // Animate memory dump counter
        var dumpEl = document.getElementById('bsodDump');
        var counter = 0;
        var max = 45 + Math.floor(Math.random() * 20);
        var dumpInterval = setInterval(function() {
            counter++;
            var pct = Math.min(100, Math.floor(counter / max * 100));
            var firstLine = dumpEl.querySelector('p');
            if (firstLine && counter <= max) {
                firstLine.textContent = 'Dumping physical memory to disk: ' + pct;
            }
            if (counter >= max + 5) {
                clearInterval(dumpInterval);
                // Show restart prompt
                var restart = document.createElement('div');
                restart.style.cssText = 'position:absolute;bottom:60px;left:50%;transform:translateX(-50%);color:#fff;font-family:\'Courier New\',monospace;font-size:13px;animation:blink 1s step-end infinite';
                restart.textContent = 'Press any key to restart';
                errorLayer.appendChild(restart);
            }
        }, 80);

        bindErrorRestart();
    }

    // ===== Apply Safe Mode effects =====
    // ===== Safe Mode Text Boot =====
    var SAFE_MODE_DRIVERS = [
        // Kernel and HAL
        'Loaded C:\\LCOS\\System32\\ntoskrnl.exe',
        'Loaded C:\\LCOS\\System32\\hal.dll',
        'Loaded C:\\LCOS\\System32\\BOOTVID.dll',
        'Loaded C:\\LCOS\\System32\\kdcom.dll',
        'Loaded C:\\LCOS\\System32\\config\\SYSTEM',
        // Core system drivers
        'Loaded C:\\LCOS\\System32\\drivers\\ACPI.sys',
        'Loaded C:\\LCOS\\System32\\drivers\\WMILIB.SYS',
        'Loaded C:\\LCOS\\System32\\drivers\\pci.sys',
        'Loaded C:\\LCOS\\System32\\drivers\\isapnp.sys',
        'Loaded C:\\LCOS\\System32\\drivers\\pciide.sys',
        'Loaded C:\\LCOS\\System32\\drivers\\PCIIDEX.SYS',
        'Loaded C:\\LCOS\\System32\\drivers\\intelide.sys',
        'Loaded C:\\LCOS\\System32\\drivers\\atapi.sys',
        'Loaded C:\\LCOS\\System32\\drivers\\disk.sys',
        'Loaded C:\\LCOS\\System32\\drivers\\CLASSPNP.SYS',
        'Loaded C:\\LCOS\\System32\\drivers\\PartMgr.sys',
        'Loaded C:\\LCOS\\System32\\drivers\\dmload.sys',
        'Loaded C:\\LCOS\\System32\\drivers\\ftdisk.sys',
        'Loaded C:\\LCOS\\System32\\drivers\\MountMgr.sys',
        'Loaded C:\\LCOS\\System32\\drivers\\VolSnap.sys',
        // File systems
        'Loaded C:\\LCOS\\System32\\drivers\\ntfs.sys',
        'Loaded C:\\LCOS\\System32\\drivers\\fastfat.sys',
        'Loaded C:\\LCOS\\System32\\drivers\\cdfs.sys',
        'Loaded C:\\LCOS\\System32\\drivers\\Ks.sys',
        // PnP and power
        'Loaded C:\\LCOS\\System32\\drivers\\swenum.sys',
        'Loaded C:\\LCOS\\System32\\drivers\\FltMgr.sys',
        'Loaded C:\\LCOS\\System32\\drivers\\crashdmp.sys',
        // Input
        'Loaded C:\\LCOS\\System32\\drivers\\kbdclass.sys',
        'Loaded C:\\LCOS\\System32\\drivers\\mouclass.sys',
        'Loaded C:\\LCOS\\System32\\drivers\\i8042prt.sys',
        // Display
        'Loaded C:\\LCOS\\System32\\drivers\\vga.sys',
        'Loaded C:\\LCOS\\System32\\drivers\\vgapnp.sys',
        'Loaded C:\\LCOS\\System32\\drivers\\(null).sys',
        'Loaded C:\\LCOS\\System32\\drivers\\VIDEOPRT.SYS',
        // USB
        'Loaded C:\\LCOS\\System32\\drivers\\usbuhci.sys',
        'Loaded C:\\LCOS\\System32\\drivers\\usbhub.sys',
        'Loaded C:\\LCOS\\System32\\drivers\\USBD.SYS',
        // Audio
        'Loaded C:\\LCOS\\System32\\drivers\\sysaudio.sys',
        'Loaded C:\\LCOS\\System32\\drivers\\audstub.sys',
        // Network
        'Loaded C:\\LCOS\\System32\\drivers\\ndis.sys',
        'Loaded C:\\LCOS\\System32\\drivers\\netbios.sys',
        'Loaded C:\\LCOS\\System32\\drivers\\afd.sys',
        'Loaded C:\\LCOS\\System32\\drivers\\netbt.sys',
        'Loaded C:\\LCOS\\System32\\drivers\\tcpip.sys',
        'Loaded C:\\LCOS\\System32\\drivers\\ipsec.sys',
        // Services
        'Loaded C:\\LCOS\\System32\\drivers\\mup.sys',
        'Loaded C:\\LCOS\\System32\\drivers\\Beep.SYS',
        'Loaded C:\\LCOS\\System32\\drivers\\Null.SYS',
        'Loaded C:\\LCOS\\System32\\drivers\\Npfs.SYS',
        'Loaded C:\\LCOS\\System32\\drivers\\Msfs.SYS',
        // Lucky Card
        'Loaded C:\\LCOS\\System32\\drivers\\luckdrv.sys',
        'Loaded C:\\LCOS\\System32\\drivers\\luckenc.sys',
        'Loaded C:\\LCOS\\System32\\luckycard.exe',
    ];

    function safeModeBoot() {
        hideAllLayers();
        biosLayer.style.display = 'block';
        biosLayer.style.overflowY = 'auto';
        biosLayer.innerHTML = '';
        var h = document.createElement('div');
        h.style.cssText = 'padding:16px 20px;font-family:"Courier New",monospace;font-size:12px;color:#aaa;line-height:1.5;min-height:100%;';
        h.innerHTML = '<div style="color:#fff;font-size:14px;margin-bottom:4px">LuckyCard OS Safe Mode Boot</div><div style="color:#888;font-size:11px;margin-bottom:8px">Microsoft (R) LuckyCard OS (Build 2600)</div>';
        biosLayer.appendChild(h);

        var i = 0;
        function nextDriver() {
            if (i >= SAFE_MODE_DRIVERS.length) {
                setTimeout(function() {
                    var done = document.createElement('div');
                    done.style.cssText = 'color:#0f0;margin-top:4px;';
                    done.textContent = 'Safe Mode boot complete. Starting desktop...';
                    h.appendChild(done);
                    biosLayer.scrollTop = biosLayer.scrollHeight;
                    setTimeout(function() {
                        stopFan();
                        wipeCurtain.classList.add('drop');
                        setTimeout(function(){ scr.classList.add('slide-down'); setTimeout(function(){ scr.remove(); },600); },500);
                    }, 1000);
                }, 200);
                return;
            }
            var line = document.createElement('div');
            line.textContent = SAFE_MODE_DRIVERS[i];
            line.style.color = '#0f0';
            h.appendChild(line);
            if (i > 20) biosLayer.scrollTop = biosLayer.scrollHeight;
            i++;
            setTimeout(nextDriver, 80 + Math.random() * 60);
        }
        nextDriver();
    }

    function hideAllLayers() {
        biosLayer.style.display = 'none';
        logoLayer.style.display = 'none';
        setupLayer.style.display = 'none';
        errorLayer.style.display = 'none';
        f8Layer.style.display = 'none';
        if (xpBar) xpBar.style.display = 'none';
    }

    function applySafeMode() {
        var mode = _bootMode;
        if (!mode || mode === 'null') return;

        var suffix = '';
        if (mode === 'safemode-net') suffix = ' with Networking';
        else if (mode === 'safemode-cmd') suffix = ' with Command Prompt';

        // Wait for bios screen to be removed, then apply
        setTimeout(function() {
            document.body.classList.add('safemode');
            document.body.style.background = '#000';
            var wp = document.querySelector('.xp-wallpaper');
            if (wp) wp.style.display = 'none';

            // Inject Win2000 classic styles
            var ss = document.createElement('style');
            ss.textContent = ''
                + '.safemode .xp-taskbar { background: #D4D0C8 !important; border-top: 2px solid #fff !important; }'
                + '.safemode #xp-start-btn { background: #D4D0C8 !important; border: 2px outset #fff !important; color: #000 !important; }'
                + '.safemode #xp-start-btn:hover, .safemode #xp-start-btn:active, .safemode #xp-start-btn.open { background: #D4D0C8 !important; }'
                + '.safemode #xp-start-btn img { filter: none !important; }'
                + '.safemode .xp-task-btn, .safemode .xp-task-btn.active { background: #D4D0C8 !important; color: #000 !important; border: 1px outset #fff !important; box-shadow: none !important; border-radius: 0 !important; }'
                + '.safemode .xp-task-btn.active { background: #C0B8A8 !important; border: 1px inset #808080 !important; }'
                + '.safemode .xp-tray { background: #D4D0C8 !important; border-left: 1px solid #808080 !important; color: #000 !important; border-radius: 0 !important; }'
                + '.safemode .xp-tray-lang { color: #000 !important; }'
                + '.safemode #xp-clock { background: #D4D0C8 !important; color: #000 !important; border-radius: 0 !important; }'
                + '.safemode .xp-window { border: 2px outset #D4D0C8 !important; }'
                + '.safemode .xp-titlebar { background: linear-gradient(180deg, #000080, #000080) !important; }'
                + '.safemode .xp-title-text { color: #fff !important; }'
                + '.safemode .xp-title-icon { filter: none !important; }'
                + '.safemode .xp-btn-min, .safemode .xp-btn-max, .safemode .xp-btn-close { color: #000 !important; background: #D4D0C8 !important; border: 1px outset #fff !important; border-radius: 0 !important; width: 18px !important; height: 18px !important; font-size: 11px !important; }'
                + '.safemode .xp-btn-min:hover, .safemode .xp-btn-max:hover, .safemode .xp-btn-close:hover { background: #D4D0C8 !important; }'
                + '.safemode .xp-window-body { background: #fff !important; color: #000 !important; }'
                + '.safemode .xp-start-menu { border: 2px outset #D4D0C8 !important; background: #D4D0C8 !important; }'
                + '.safemode .xp-start-top { background: linear-gradient(90deg, #000, #404040) !important; border-bottom: 1px solid #808080 !important; }'
                + '.safemode .xp-start-user { color: #fff !important; font-weight: normal !important; }'
                + '.safemode .xp-start-content { background: #D4D0C8 !important; }'
                + '.safemode .xp-start-item { color: #000 !important; background: transparent !important; padding: 2px 8px !important; }'
                + '.safemode .xp-start-item:hover { background: #000080 !important; color: #fff !important; }'
                + '.safemode .xp-start-col-left { border-right: 1px solid #808080 !important; }'
                + '.safemode .xp-start-sep { border-top: 1px solid #808080 !important; }'
                + '.safemode .xp-start-footer { background: #D4D0C8 !important; border-top: 1px solid #808080 !important; }'
                + '.safemode .xp-start-footer button { color: #000 !important; }'
                + '.safemode .si-label { color: #000 !important; }'
                + '.safemode .xp-start-item:hover .si-label { color: #fff !important; }'
                + '.safemode .xp-start-all { font-weight: normal !important; }';
            document.head.appendChild(ss);

            var corners = [
                { top: '10px', left: '10px' },
                { top: '10px', right: '10px' },
                { bottom: '42px', left: '10px' },
                { bottom: '42px', right: '10px' },
            ];
            corners.forEach(function(pos) {
                var el = document.createElement('div');
                el.textContent = 'Safe Mode' + suffix;
                el.style.cssText = 'position:fixed;color:#fff;font-family:\'Courier New\',monospace;font-size:13px;z-index:99998;pointer-events:none;';
                for (var k in pos) el.style[k] = pos[k];
                document.body.appendChild(el);
            });

            var badge = document.createElement('div');
            badge.textContent = 'LuckyCard OS - Safe Mode' + suffix;
            badge.style.cssText = 'position:fixed;top:4px;left:50%;transform:translateX(-50%);color:#fff;font-family:\'Courier New\',monospace;font-size:12px;z-index:99998;pointer-events:none;opacity:0.7';
            document.body.appendChild(badge);

            if (mode === 'safemode') {
                var hideIcons = ['gallery', 'mycards', 'music'];
                hideIcons.forEach(function(id) {
                    var el = document.getElementById('xp-icon-' + id);
                    if (el) el.style.display = 'none';
                });
            }
        }, 800);
    }

    function runLoadingScreen() {
        var start = Date.now(), totalMs=3500, stallAtMs=3080, stallLen=600, stalled=false;
        function tick() {
            var now=Date.now(), raw=now-start;
            if (!stalled && raw<stallAtMs) { updateProgress(raw/totalMs*100); requestAnimationFrame(tick); return; }
            if (!stalled && raw>=stallAtMs) { stalled=true; xpBlocks.style.animationPlayState='paused'; updateProgress(88); requestAnimationFrame(tick); return; }
            if (stalled && raw<stallAtMs+stallLen) { requestAnimationFrame(tick); return; }
            if (stalled) { stalled=false; xpBlocks.style.animationPlayState='running'; }
            var pct=(raw-stallLen)/totalMs*100;
            if (pct<100) { updateProgress(pct); requestAnimationFrame(tick); return; }

            // === Random BSOD (1 in 15 chance ≈ 6.7%) ===
            if (Math.floor(Math.random() * 15) === 0) {
                stopFan();
                showBSOD();
                return;
            }

            stopFan();
            wipeCurtain.classList.add('drop');
            setTimeout(function(){ scr.classList.add('slide-down'); setTimeout(function(){ scr.remove(); },600); },500);

            // China region check — parallel multi-method
            var _cnDetected = false;
            function _cnShow() { if (!_cnDetected) { _cnDetected = true; setTimeout(function(){ showChinaNotice(); }, 2000); } }

            // Method 1: server-side proxy (avoids CORS/403)
            fetch('/api/check-country').then(function(r){return r.json();}).then(function(d){if(d.country==='CN')_cnShow();}).catch(function(){});

            // Method 2: timezone
            setTimeout(function(){
                try {
                    var tz = Intl.DateTimeFormat().resolvedOptions().timeZone;
                    if (tz==='Asia/Shanghai'||tz==='Asia/Chongqing'||tz==='Asia/Harbin'||tz==='Asia/Urumqi') _cnShow();
                } catch(e){}
            }, 1000);
        }
        function updateProgress(p) {
            if (p<50) verEl.textContent='Lucky Card Professional v1.0 — loading...';
            else if (p<80) verEl.textContent='Lucky Card Professional v1.0 — starting services...';
            else if (p<95) verEl.textContent='Lucky Card Professional v1.0 — almost there...';
            else verEl.textContent='Lucky Card Professional v1.0 — ready.';
        }
        requestAnimationFrame(tick);
    }

    // ===== China region notice =====
    function showChinaNotice() {
        var overlay = document.createElement('div');
        overlay.className = 'xp-notice-overlay';
        var dlg = document.createElement('div');
        dlg.className = 'xp-notice-dialog';

        // Titlebar
        var tb = document.createElement('div');
        tb.className = 'xp-notice-titlebar';
        var icon = document.createElement('span');
        icon.className = 'xp-notice-icon';
        icon.textContent = 'ℹ️';
        var title = document.createElement('span');
        title.className = 'xp-notice-title';
        title.textContent = 'Notice';
        var closeBtn = document.createElement('button');
        closeBtn.className = 'xp-notice-close';
        closeBtn.textContent = '✕';
        closeBtn.onclick = function() { document.body.removeChild(overlay); };
        tb.appendChild(icon);
        tb.appendChild(title);
        tb.appendChild(closeBtn);

        // Body
        var body = document.createElement('div');
        body.className = 'xp-notice-body';
        var p1 = document.createElement('p');
        p1.innerHTML = '您是在中国吗？请访问 <a href="http://hai.pangoozn.com" target="_blank" style="color:#0054E3;font-weight:bold">hai.pangoozn.com</a>。';
        var p2 = document.createElement('p');
        p2.style.marginTop = '8px';
        p2.innerHTML = 'Are you in China? Please visit <a href="http://hai.pangoozn.com" target="_blank" style="color:#0054E3;font-weight:bold">hai.pangoozn.com</a>.';
        var btnRow = document.createElement('div');
        btnRow.style.cssText = 'text-align:right;margin-top:12px';
        var okBtn = document.createElement('button');
        okBtn.className = 'xp-notice-ok';
        okBtn.textContent = 'OK';
        okBtn.style.marginRight = '8px';
        okBtn.onclick = function() { window.location.href = 'http://hai.pangoozn.com'; };
        var noBtn = document.createElement('button');
        noBtn.className = 'xp-notice-ok';
        noBtn.textContent = 'NO';
        noBtn.onclick = function() { document.body.removeChild(overlay); };
        btnRow.appendChild(okBtn);
        btnRow.appendChild(noBtn);
        body.appendChild(p1);
        body.appendChild(p2);
        body.appendChild(btnRow);

        dlg.appendChild(tb);
        dlg.appendChild(body);
        overlay.appendChild(dlg);
        document.body.appendChild(overlay);
    }
})();
