// Lucky Card XP Shell — taskbar clock, start menu, window management
(function() {
    'use strict';

    // ===== Multi-language support =====
    var _lang = 'en';
    var _t = {
        en: {
            control_panel: 'Control Panel',
            language: 'Language',
            display: 'Display',
            system: 'System',
            about: 'About Lucky Card',
            version: 'Version 16.1145 (Build 2600)',
            registered: 'Registered to: Lucky Card User',
            cpu: 'Intel(R) Pentium(R) 4 CPU 2.40GHz',
            ram: '512 MB RAM',
            lang_en: 'English',
            lang_zh: '中文',
            switch_lang: 'Switch Language',
            current_lang: 'Current: English',
            run_prompt: 'Type the name of a program, folder, document, or Internet resource, and Lucky Card will open it for you.',
            run_open: 'Open:',
            run_cancel: 'Cancel',
            run_browse: 'Browse...',
            run_title: 'Run',
            notepad_title: 'Notepad',
            cp_category_appearance: 'Appearance and Themes',
            cp_category_network: 'Network and Internet Connections',
            cp_category_sounds: 'Sounds, Speech, and Audio Devices',
            cp_category_performance: 'Performance and Maintenance',
            cp_category_printers: 'Printers and Other Hardware',
            cp_category_accounts: 'User Accounts',
            cp_category_date: 'Date, Time, Language, and Regional Options',
            cp_category_accessibility: 'Accessibility Options',
            cp_category_security: 'Security Center',
        },
        zh: {
            control_panel: '控制面板',
            language: '语言',
            display: '显示',
            system: '系统',
            about: '关于 Lucky Card',
            version: '版本 16.1145 (Build 2600)',
            registered: '注册用户: Lucky Card User',
            cpu: 'Intel(R) Pentium(R) 4 CPU 2.40GHz',
            ram: '512 MB 内存',
            lang_en: 'English',
            lang_zh: '中文',
            switch_lang: '切换语言',
            current_lang: '当前: 中文',
            run_prompt: '请键入程序、文件夹、文档或 Internet 资源的名称，Lucky Card 将为您打开它。',
            run_open: '打开:',
            run_cancel: '取消',
            run_browse: '浏览...',
            run_title: '运行',
            notepad_title: '记事本',
            cp_category_appearance: '外观和主题',
            cp_category_network: '网络和 Internet 连接',
            cp_category_sounds: '声音、语音和音频设备',
            cp_category_performance: '性能和维护',
            cp_category_printers: '打印机和其它硬件',
            cp_category_accounts: '用户帐户',
            cp_category_date: '日期、时间、语言和区域选项',
            cp_category_accessibility: '辅助功能选项',
            cp_category_security: '安全中心',
        }
    };

    function t(key) {
        return (_t[_lang] && _t[_lang][key]) || (_t['en'][key]) || key;
    }

    // ===== Audio =====
    var _xpStartup = new Audio('/static/audio/xp-startup.mp3');
    _xpStartup.volume = 0.3;
    _xpStartup.loop = false;
    _xpStartup.muted = true;
    _xpStartup.play().catch(function(){});
    var _startupPlayed = false;

    function playStartupSound() {
        if (_startupPlayed) return;
        _startupPlayed = true;
        _xpStartup.muted = false;
        _xpStartup.currentTime = 0;
        _xpStartup.play().catch(function(){});
    }

    function playShutdownSound() {
        var a = document.getElementById('xpreal-audio');
        if (a) { a.volume = 0.3; a.currentTime = 0; a.play().catch(function(){}); }
    }

    var checkReady = setInterval(function() {
        if (!document.getElementById('bios-screen')) {
            clearInterval(checkReady);
            setTimeout(playStartupSound, 500);
        }
    }, 200);

    // ===== Clock =====
    var clockEl = document.getElementById('xp-clock');
    function tick() {
        var now = new Date();
        var h = now.getHours(), m = now.getMinutes();
        clockEl.textContent = (h < 10 ? '0' : '') + h + ':' + (m < 10 ? '0' : '') + m;
        setTimeout(tick, 1000);
    }
    tick();

    // ===== Start Menu =====
    var startBtn = document.getElementById('xp-start-btn');
    var startMenu = document.getElementById('xp-start-menu');
    var menuOpen = false;

    function toggleStart() {
        menuOpen = !menuOpen;
        if (menuOpen) {
            startMenu.classList.add('show');
            startBtn.classList.add('open');
            document.addEventListener('click', closeStartOnOutside);
        } else {
            startMenu.classList.remove('show');
            startBtn.classList.remove('open');
            document.removeEventListener('click', closeStartOnOutside);
        }
    }

    function closeStartOnOutside(e) {
        if (!startMenu.contains(e.target) && e.target !== startBtn) {
            menuOpen = false;
            startMenu.classList.remove('show');
            startBtn.classList.remove('open');
            document.removeEventListener('click', closeStartOnOutside);
        }
    }

    startBtn.addEventListener('click', function(e) {
        e.stopPropagation();
        toggleStart();
    });

    // ===== Run Dialog =====
    function openRun() {
        var dlg = document.getElementById('xp-run-dlg');
        if (!dlg) return;
        // Position like a window (absolute, not fixed centered)
        dlg.style.display = 'flex';
        dlg.style.position = 'absolute';
        dlg.style.top = '120px';
        dlg.style.left = '200px';
        dlg.style.transform = 'none';
        // Update translated labels
        dlg.querySelector('[data-lang="run_prompt"]').textContent = t('run_prompt');
        dlg.querySelector('[data-lang="run_open"]').textContent = t('run_open') + ':';
        dlg.querySelector('[data-lang="run_cancel"]').textContent = t('run_cancel');
        dlg.querySelector('[data-lang="run_browse"]').textContent = t('run_browse');
        var inp = document.getElementById('xp-run-input');
        if (inp) { inp.value = ''; setTimeout(function() { inp.focus(); }, 100); }
    }

    function closeRun() {
        var dlg = document.getElementById('xp-run-dlg');
        if (dlg) dlg.style.display = 'none';
    }

    function runCommand() {
        var inp = document.getElementById('xp-run-input');
        var cmd = inp ? inp.value.trim().toLowerCase() : '';
        closeRun();
        if (!cmd) return;

        // Command routing
        var routes = {
            'card':       ['create', 'Create Card', '<img src="/static/img/xp-ie6_20.png?v=1" style="width:20px;height:20px;vertical-align:middle">', '/static/forms/card-create.html'],
            'create':     ['create', 'Create Card', '<img src="/static/img/xp-ie6_20.png?v=1" style="width:20px;height:20px;vertical-align:middle">', '/static/forms/card-create.html'],
            'gallery':    ['gallery', 'Gallery', '<img src="/static/img/xp-gallery_20.png?v=1" style="width:20px;height:20px;vertical-align:middle">', '/static/forms/card-gallery.html'],
            'music':      ['music', 'Music', '<img src="/static/img/xp-music_20.png?v=1" style="width:20px;height:20px;vertical-align:middle">', '/static/forms/music-player.html?v=58'],
            'stylize':    ['stylizer', 'AI Stylizer', '<img src="/static/img/xp-paint_20.png?v=1" style="width:20px;height:20px;vertical-align:middle">', '/static/forms/ai-stylizer.html'],
            'stylizer':   ['stylizer', 'AI Stylizer', '<img src="/static/img/xp-paint_20.png?v=1" style="width:20px;height:20px;vertical-align:middle">', '/static/forms/ai-stylizer.html'],
            'mycards':    ['mycards', 'My Cards', '<img src="/static/img/xp-folder_20.png?v=1" style="width:20px;height:20px;vertical-align:middle">', '/static/forms/my-cards.html'],
            'control':    ['control', t('control_panel'), '<img src="/static/img/xp_controlpanel_24.png?v=1" style="width:18px;height:18px;vertical-align:middle">', buildControlPanelHTML()],
            'notepad':    ['notepad', t('notepad_title'), '<img src="/static/img/xp-notepad_20.png?v=1" style="width:20px;height:20px;vertical-align:middle">', buildNotepadHTML()],
            'cmd':        ['cmd', 'Command Prompt', '💻', buildCmdHTML()],
            'help':       ['help', 'Help', '❓', buildHelpHTML()],
            'about':      ['about', t('about'), 'ℹ️', buildAboutHTML()],
            'sysinfo':    ['sysinfo', 'System Information', 'ℹ️', buildSysInfoHTML()],
            'sys':        ['sysinfo', 'System Information', 'ℹ️', buildSysInfoHTML()],
        };

        if (cmd.startsWith('http://') || cmd.startsWith('https://')) {
            window.open(cmd, '_blank');
            return;
        }

        // Handle explorer.exe → restore shell
        if (cmd === 'explorer' || cmd === 'explorer.exe') {
            if (_shellHidden) restoreShell();
            return;
        }

        // Handle taskmgr → open Task Manager
        if (cmd === 'taskmgr' || cmd === 'taskman') {
            openTaskManager();
            return;
        }

        // WinDOS easter egg 🥚 — download via Run dialog
        if (cmd === 'windos' || cmd === 'windos.exe' || cmd === 'win dos') {
            window.open('/dl/windos-build.zip?dl=1');
            XPShell.openWindow('windos-dl', 'WinDOS', '<img src="/static/img/xp-cmd_20.png?v=1" style="width:20px;height:20px;vertical-align:middle">',
                '<div style="text-align:center;padding:2rem;font-family:Tahoma,sans-serif">' +
                '<p style="font-size:3rem;margin-bottom:0.5rem">🖥️💾</p>' +
                '<p style="font-size:1.3rem;font-weight:bold;margin-bottom:0.5rem">Downloading WinDOS…</p>' +
                '<p style="color:#666;font-size:0.9rem">A lightweight Windows-like OS</p>' +
                '<p style="color:#888;margin-top:1rem;font-size:0.85rem">Build 20260621</p>' +
                '</div>');
            return;
        }

        if (routes[cmd]) {
            var r = routes[cmd];
            XPShell.openWindow(r[0], r[1], r[2], r[3]);
        } else {
            XPShell.openWindow('run-result', 'Run', '▶️',
                '<div style="text-align:center;padding:2rem">' +
                '<p style="font-size:2rem">⚠️</p>' +
                '<p style="margin-top:1rem">Cannot find <b>' + escHtml(cmd) + '</b></p>' +
                '<p style="color:#888;margin-top:0.5rem">Try: card, gallery, music, stylizer, control, notepad, cmd, windos</p>' +
                '</div>');
        }
    }

    function escHtml(s) {
        var d = document.createElement('div');
        d.textContent = s;
        return d.innerHTML;
    }

    // ===== Keyboard shortcuts =====
    // Alt+R opens Run dialog (Win+R is reserved by OS)
    document.addEventListener('keydown', function(e) {
        if (e.altKey && (e.key === 'r' || e.key === 'R')) {
            e.preventDefault();
            openRun();
        }
        // Ctrl+Alt+. (simulated Ctrl+Alt+Del) → Task Manager
        if (e.ctrlKey && e.altKey && e.key === '.') {
            e.preventDefault();
            openTaskManager();
        }
    });

    // ===== Control Panel =====
    function buildControlPanelHTML() {
        var cats = [
            { icon: '<img src="/static/img/xp-paint_20.png?v=1" style="width:20px;height:20px;vertical-align:middle">', key: 'cp_category_appearance', action: 'appearance' },
            { icon: '🌐', key: 'cp_category_network', action: 'network' },
            { icon: '🔊', key: 'cp_category_sounds', action: 'sounds' },
            { icon: '⚡', key: 'cp_category_performance', action: 'performance' },
            { icon: '🖨️', key: 'cp_category_printers', action: 'printers' },
            { icon: '👤', key: 'cp_category_accounts', action: 'accounts' },
            { icon: '📅', key: 'cp_category_date', action: 'datetime' },
            { icon: '<img src="/static/img/xp_access_48.png?v=1" style="width:48px;height:48px;">', key: 'cp_category_accessibility', action: 'accessibility' },
            { icon: '<img src="/static/img/xp_shield_48.png?v=1" style="width:48px;height:48px;">', key: 'cp_category_security', action: 'security' },
        ];

        var h = '<div class="cp-container">';
        // Language switcher bar
        h += '<div class="cp-lang-bar">';
        h += '<span>' + t('current_lang') + '</span>';
        h += '<button class="cp-lang-btn' + (_lang === 'en' ? ' active' : '') + '" onclick="XPShell.setLang(\'en\')">' + t('lang_en') + '</button>';
        h += '<button class="cp-lang-btn' + (_lang === 'zh' ? ' active' : '') + '" onclick="XPShell.setLang(\'zh\')">' + t('lang_zh') + '</button>';
        h += '</div>';

        // Category grid
        h += '<div class="cp-grid">';
        for (var i = 0; i < cats.length; i++) {
            h += '<div class="cp-cat" onclick="XPShell.openCPItem(\'' + cats[i].action + '\')">';
            h += '<div class="cp-cat-icon">' + cats[i].icon + '</div>';
            h += '<div class="cp-cat-label">' + t(cats[i].key) + '</div>';
            h += '</div>';
        }
        h += '</div>';

        // System info at bottom
        h += '<div class="cp-sysinfo">';
        h += '<div class="cp-sys-row"><span class="cp-sys-label">' + t('version') + '</span></div>';
        h += '<div class="cp-sys-row"><span class="cp-sys-label">' + t('registered') + '</span></div>';
        h += '<div class="cp-sys-row"><span class="cp-sys-label">' + t('cpu') + '</span></div>';
        h += '<div class="cp-sys-row"><span class="cp-sys-label">' + t('ram') + '</span></div>';
        h += '</div>';

        h += '</div>';
        return h;
    }

    function openCPItem(action) {
        var titles = {
            appearance: 'Appearance',
            network: 'Network',
            sounds: 'Sounds & Audio',
            performance: 'Performance',
            printers: 'Printers & Cards',
            accounts: 'User Accounts',
            datetime: 'Date & Time',
            accessibility: 'Accessibility',
            security: 'Security Center'
        };

        var menu = {
            appearance: function() {
                var c = localStorage.getItem('xp-theme') || 'blue';
                return '<div style="padding:16px;font-family:Tahoma,sans-serif">' +
                    '<h3 style="margin-bottom:12px;color:#003399">' + t('appearance') + ' &amp; Themes</h3>' +
                    '<p style="font-size:12px;color:#666;margin-bottom:12px">Choose a color scheme for your desktop:</p>' +
                    '<div class="theme-options" style="display:flex;gap:10px;flex-wrap:wrap">' +
                    '  <div class="theme-pick' + (c === 'blue' ? ' active' : '') + '" data-theme="blue" onclick="XPShell.setTheme(\'blue\')" style="width:80px;padding:8px;border:2px solid ' + (c === 'blue' ? '#039' : '#ccc') + ';border-radius:6px;text-align:center;cursor:pointer;background:linear-gradient(180deg,#3a6ea5,#2a5a8a)">' +
                    '    <div style="height:40px;border-radius:4px;background:linear-gradient(135deg,#3a6ea5,#1a3a6a)"></div>' +
                    '    <div style="font-size:11px;margin-top:4px;color:#fff">Classic Blue</div>' +
                    '  </div>' +
                    '  <div class="theme-pick' + (c === 'silver' ? ' active' : '') + '" data-theme="silver" onclick="XPShell.setTheme(\'silver\')" style="width:80px;padding:8px;border:2px solid ' + (c === 'silver' ? '#039' : '#ccc') + ';border-radius:6px;text-align:center;cursor:pointer;background:linear-gradient(180deg,#b0b0b0,#8a8a8a)">' +
                    '    <div style="height:40px;border-radius:4px;background:linear-gradient(135deg,#c0c0c0,#999)"></div>' +
                    '    <div style="font-size:11px;margin-top:4px;color:#333">Silver</div>' +
                    '  </div>' +
                    '  <div class="theme-pick' + (c === 'olive' ? ' active' : '') + '" data-theme="olive" onclick="XPShell.setTheme(\'olive\')" style="width:80px;padding:8px;border:2px solid ' + (c === 'olive' ? '#039' : '#ccc') + ';border-radius:6px;text-align:center;cursor:pointer;background:linear-gradient(180deg,#6a8a3a,#4a6a2a)">' +
                    '    <div style="height:40px;border-radius:4px;background:linear-gradient(135deg,#7a9a4a,#5a7a2a)"></div>' +
                    '    <div style="font-size:11px;margin-top:4px;color:#fff">Olive Green</div>' +
                    '  </div>' +
                    '</div></div>';
                return menu.appearance = function(){return menu.appearance._html;}, menu.appearance._html = menu.appearance._html || menu.appearance(), menu.appearance._html;
            },
            network: function() {
                return '<div style="padding:16px;font-family:Tahoma,sans-serif">' +
                    '<h3 style="margin-bottom:12px;color:#003399">Network Connections</h3>' +
                    '<div style="background:#e8f0e8;border:1px solid #8a8;border-radius:4px;padding:12px;margin-bottom:12px">' +
                    '  <div style="font-size:13px;font-weight:bold;color:#060">✅ Connected</div>' +
                    '  <div style="font-size:11px;color:#666;margin-top:4px">hicard.world — Cloudflare protected</div>' +
                    '  <div style="font-size:11px;color:#888;margin-top:2px">Server: Hong Kong / Speed: Fast</div>' +
                    '</div>' +
                    '<div style="font-size:11px;color:#888">' +
                    '  <div>🔒 Connection: HTTPS + TLS 1.3</div>' +
                    '  <div style="margin-top:2px">📡 Proxy: Cloudflare CDN</div>' +
                    '</div></div>';
            },
            sounds: function() {
                return '<div style="padding:16px;font-family:Tahoma,sans-serif">' +
                    '<h3 style="margin-bottom:12px;color:#003399">Sounds &amp; Audio</h3>' +
                    '<p style="font-size:12px;color:#666;margin-bottom:12px">Configure your audio experience</p>' +
                    '<button onclick="XPShell.openWindow(\'music\',\'Music\',\'<img src=\"/static/img/xp-music_20.png?v=1?v=1\" style=\"width:20px;height:20px;vertical-align:middle\">\',\'' + '/static/forms/music-player.html?v=58' + '\')" style="width:100%;padding:8px;font-size:12px;cursor:pointer;border:1px solid #999;background:linear-gradient(180deg,#fff,#ece9d8);border-radius:3px;margin-bottom:8px"><img src="/static/img/xp-music_20.png?v=1?v=1" style="width:20px;height:20px;vertical-align:middle"> Open Music Player</button>' +
                    '<div style="font-size:11px;color:#888;padding:8px;background:#f5f5f0;border:1px solid #ddd;border-radius:3px">' +
                    '  <div>Volume: 🔊 Default</div>' +
                    '  <div style="margin-top:2px">Audio Device: Browser Default</div>' +
                    '</div></div>';
            },
            performance: function() {
                return '<div style="padding:16px;font-family:Tahoma,sans-serif">' +
                    '<h3 style="margin-bottom:12px;color:#003399">Performance Options</h3>' +
                    '<div style="padding:8px;background:#f5f5f0;border:1px solid #ddd;border-radius:3px;margin-bottom:12px">' +
                    '  <div style="font-size:12px;font-weight:bold">Visual effects</div>' +
                    '  <label style="font-size:11px;display:block;margin-top:6px;cursor:pointer">' +
                    '    <input type="radio" name="perf" checked> Adjust for best appearance</label>' +
                    '  <label style="font-size:11px;display:block;margin-top:3px;cursor:pointer">' +
                    '    <input type="radio" name="perf"> Adjust for best performance</label>' +
                    '  <label style="font-size:11px;display:block;margin-top:3px;cursor:pointer">' +
                    '    <input type="radio" name="perf"> Let Lucky Card choose</label>' +
                    '</div>' +
                    '<button onclick="XPShell.openTaskManager()" style="width:100%;padding:8px;font-size:12px;cursor:pointer;border:1px solid #999;background:linear-gradient(180deg,#fff,#ece9d8);border-radius:3px">⚡ Open Task Manager</button></div>';
            },
            printers: function() {
                return '<div style="padding:16px;font-family:Tahoma,sans-serif">' +
                    '<h3 style="margin-bottom:12px;color:#003399">Printers &amp; Cards</h3>' +
                    '<p style="font-size:12px;color:#666;margin-bottom:12px">Create and manage your greeting cards</p>' +
                    '<button onclick="XPShell.openWindow(\'create\',\'Create Card\',\'<img src=\"/static/img/xp-ie6_20.png?v=1?v=1\" style=\"width:20px;height:20px;vertical-align:middle\">\',\'' + '/static/forms/card-create.html' + '\')" style="width:100%;padding:8px;font-size:12px;cursor:pointer;border:1px solid #999;background:linear-gradient(180deg,#fff,#ece9d8);border-radius:3px;margin-bottom:8px"><img src="/static/img/xp-ie6_20.png?v=1?v=1" style="width:20px;height:20px;vertical-align:middle"> Create a New Card</button>' +
                    '<button onclick="XPShell.openWindow(\'gallery\',\'Gallery\',\'<img src=\"/static/img/xp-gallery_20.png?v=1?v=1\" style=\"width:20px;height:20px;vertical-align:middle\">\',\'' + '/static/forms/card-gallery.html' + '\')" style="width:100%;padding:8px;font-size:12px;cursor:pointer;border:1px solid #999;background:linear-gradient(180deg,#fff,#ece9d8);border-radius:3px"><img src="/static/img/xp-gallery_20.png?v=1?v=1" style="width:20px;height:20px;vertical-align:middle"> View Card Gallery</button></div>';
            },
            accounts: function() {
                return '<div style="padding:16px;font-family:Tahoma,sans-serif">' +
                    '<h3 style="margin-bottom:12px;color:#003399">User Accounts</h3>' +
                    '<div style="display:flex;align-items:center;gap:12px;padding:12px;background:#f5f5f0;border:1px solid #ddd;border-radius:6px;margin-bottom:12px">' +
                    '  <div style="font-size:32px">👤</div>' +
                    '  <div>' +
                    '    <div style="font-weight:bold;font-size:13px">Lucky Card</div>' +
                    '    <div style="font-size:11px;color:#888">Administrator</div>' +
                    '    <div style="font-size:11px;color:#aaa">Password protected</div>' +
                    '  </div>' +
                    '</div>' +
                    '<div style="font-size:11px;color:#888">' +
                    '  <div>🟢 Account is active</div>' +
                    '  <div style="margin-top:2px">📅 Created: June 2026</div>' +
                    '</div></div>';
            },
            datetime: function() {
                var now = new Date();
                var days = ['Sunday','Monday','Tuesday','Wednesday','Thursday','Friday','Saturday'];
                var months = ['January','February','March','April','May','June','July','August','September','October','November','December'];
                return '<div style="padding:16px;font-family:Tahoma,sans-serif">' +
                    '<h3 style="margin-bottom:12px;color:#003399">Date &amp; Time</h3>' +
                    '<div style="text-align:center;padding:16px;background:#f5f5f0;border:1px solid #ddd;border-radius:6px;margin-bottom:12px">' +
                    '  <div style="font-size:28px;font-weight:bold;color:#003399">' + now.getHours().toString().padStart(2,'0') + ':' + now.getMinutes().toString().padStart(2,'0') + '</div>' +
                    '  <div style="font-size:13px;color:#666;margin-top:4px">' + days[now.getDay()] + ', ' + months[now.getMonth()] + ' ' + now.getDate() + ', ' + now.getFullYear() + '</div>' +
                    '  <div style="font-size:11px;color:#888;margin-top:4px">Time Zone: ' + Intl.DateTimeFormat().resolvedOptions().timeZone + '</div>' +
                    '</div>' +
                    '<div style="font-size:11px;color:#888;text-align:center">The clock is automatically synced.</div></div>';
            },
            accessibility: function() {
                return '<div style="padding:16px;font-family:Tahoma,sans-serif">' +
                    '<h3 style="margin-bottom:12px;color:#003399">Accessibility Options</h3>' +
                    '<div style="margin-bottom:12px">' +
                    '  <div style="font-size:12px;font-weight:bold;margin-bottom:6px">Language</div>' +
                    '  <div style="display:flex;gap:8px">' +
                    '    <button onclick="XPShell.setLang(\'en\')" style="flex:1;padding:8px;font-size:12px;cursor:pointer;border:1px solid ' + (_lang === 'en' ? '#039' : '#999') + ';background:' + (_lang === 'en' ? '#e0e8f8' : 'linear-gradient(180deg,#fff,#ece9d8)') + ';border-radius:3px;font-weight:' + (_lang === 'en' ? 'bold' : 'normal') + '">🇺🇸 English</button>' +
                    '    <button onclick="XPShell.setLang(\'zh\')" style="flex:1;padding:8px;font-size:12px;cursor:pointer;border:1px solid ' + (_lang === 'zh' ? '#039' : '#999') + ';background:' + (_lang === 'zh' ? '#e0e8f8' : 'linear-gradient(180deg,#fff,#ece9d8)') + ';border-radius:3px;font-weight:' + (_lang === 'zh' ? 'bold' : 'normal') + '">🇨🇳 中文</button>' +
                    '  </div>' +
                    '</div>' +
                    '<div style="font-size:11px;color:#888">' +
                    '  <label style="display:flex;align-items:center;gap:6px;cursor:pointer;margin-bottom:4px"><input type="checkbox"> Use high contrast</label>' +
                    '  <label style="display:flex;align-items:center;gap:6px;cursor:pointer;margin-bottom:4px"><input type="checkbox"> Show tooltips</label>' +
                    '  <label style="display:flex;align-items:center;gap:6px;cursor:pointer"><input type="checkbox"> Enable animations</label>' +
                    '</div></div>';
            },
            security: function() {
                return '<div style="padding:16px;font-family:Tahoma,sans-serif">' +
                    '<h3 style="margin-bottom:12px;color:#003399;display:flex;align-items:center;gap:8px"><img src="/static/img/xp_shield_48.png?v=1" style="width:24px;height:24px">Security Center</h3>' +
                    '<div style="background:#e8f0e8;border:1px solid #8a8;border-radius:4px;padding:12px;margin-bottom:12px">' +
                    '  <div style="font-size:13px;font-weight:bold;color:#060">✅ All secure</div>' +
                    '  <div style="font-size:11px;color:#666;margin-top:4px">Your connection to hicard.world is encrypted.</div>' +
                    '</div>' +
                    '<div style="font-size:11px;color:#888">' +
                    '  <div>🔒 HTTPS — Encrypted connection</div>' +
                    '  <div style="margin-top:2px">🛡️ Cloudflare — DDoS protection</div>' +
                    '  <div style="margin-top:2px">🔐 No passwords stored in browser</div>' +
                    '</div></div>';
            }
        };

        var content = menu[action] ? menu[action]() : '<p>Coming soon...</p>';
        if (typeof content === 'function') content = content();

        // Replace the control panel body with sub-content + back button
        var bodyEl = document.getElementById('xp-win-body-control');
        if (bodyEl) {
            bodyEl.innerHTML =
                '<div style="padding:4px 8px;background:#d6d0c4;border-bottom:1px solid #b7b09e;display:flex;align-items:center;gap:8px;font-size:11px">' +
                '<button onclick="XPShell.backToControlPanel()" style="padding:2px 8px;cursor:pointer;border:1px solid #999;background:linear-gradient(180deg,#fff,#ece9d8);border-radius:3px;font-size:11px">◀ Back</button>' +
                '<span style="color:#666">' + t('control_panel') + ' &gt; </span>' +
                '<span style="font-weight:bold;color:#003399">' + (titles[action] || action) + '</span>' +
                '</div>' +
                content;
            // Update title bar icon
            var titleBar = document.getElementById('xp-title-control');
            if (titleBar) {
                var iconSpan = titleBar.querySelector('.xp-title-icon');
                if (iconSpan) iconSpan.innerHTML = '⚙️';
            }
        }
    }

    function backToControlPanel() {
        var bodyEl = document.getElementById('xp-win-body-control');
        if (bodyEl) {
            bodyEl.innerHTML = buildControlPanelHTML();
        }
    }

    function openControlPanel() {
        XPShell.openWindow('control', t('control_panel'), '<img src="/static/img/xp_controlpanel_24.png?v=1" style="width:18px;height:18px;vertical-align:middle">', buildControlPanelHTML());
    }

    function setLang(lang) {
        _lang = lang;
        // Refresh control panel if open
        var cpBody = document.getElementById('xp-win-body-control');
        if (cpBody) cpBody.innerHTML = buildControlPanelHTML();
        // Refresh run dialog labels if open
        var runDlg = document.getElementById('xp-run-dlg');
        if (runDlg && runDlg.style.display !== 'none') {
            runDlg.querySelector('[data-lang="run_prompt"]').textContent = t('run_prompt');
            runDlg.querySelector('[data-lang="run_cancel"]').textContent = t('run_cancel');
            runDlg.querySelector('[data-lang="run_browse"]').textContent = t('run_browse');
        }
    }

    // ===== Notepad =====
    function buildNotepadHTML() {
        return '<textarea style="width:100%;height:100%;border:none;resize:none;padding:12px;font-family:Consolas,monospace;font-size:14px;background:#fff;outline:none" placeholder="Type here..."></textarea>';
    }

    // ===== Interactive Command Prompt =====
    function buildCmdHTML() {
        var h = '<div style="display:flex;flex-direction:column;height:100%;background:#000;color:#0f0;font-family:Consolas,monospace;font-size:13px">';
        h += '<div id="cmdOutput" style="flex:1;overflow-y:auto;padding:12px;white-space:pre-wrap">';
        h += 'Lucky Card Command Prompt [Version 16.1145.2600]<br>';
        h += '(C) Copyright 2026 Lucky Card Technologies. All rights reserved.<br><br>';
        h += 'C:\\Documents and Settings\\User&gt;<span id="cmdInputLine"></span>';
        h += '</div>';
        h += '<div style="display:flex;padding:0 12px 8px 12px">';
        h += '<span style="color:#0f0;line-height:24px">C:\\&gt;</span>';
        h += '<input id="cmdInput" style="flex:1;background:transparent;border:none;color:#0f0;font-family:Consolas,monospace;font-size:13px;outline:none;margin-left:4px" autofocus autocomplete="off" spellcheck="false">';
