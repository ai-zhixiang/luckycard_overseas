// Lucky Card XP Shell — taskbar clock, start menu, window management
(function() {
    'use strict';

    // ===== Multi-language support =====
    var _lang = (navigator.language || 'en').startsWith('zh') ? 'zh' : 'en';
    var _t = {
        en: {
            control_panel: 'Control Panel',
            language: 'Language',
            display: 'Display',
            system: 'System',
            about: 'About Lucky Card',
            version: 'Version 1.0 (Build 2600)',
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
            version: '版本 1.0 (Build 2600)',
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
    _xpStartup.volume = 0.7;
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
        if (a) { a.volume = 0.9; a.currentTime = 0; a.play().catch(function(){}); }
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
        dlg.style.display = 'flex';
        // Update translated labels
        dlg.querySelector('[data-lang="run_prompt"]').textContent = t('run_prompt');
        dlg.querySelector('[data-lang="run_open"]').textContent = t('run_open') + ' ';
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
            'card':       ['create', 'Create Card', '🃏', '/static/forms/card-create.html'],
            'create':     ['create', 'Create Card', '🃏', '/static/forms/card-create.html'],
            'gallery':    ['gallery', 'Gallery', '🖼️', '/static/forms/card-gallery.html'],
            'music':      ['music', 'Music', '🎵', '/static/forms/music-player.html'],
            'mycards':    ['mycards', 'My Cards', '📁', '/static/forms/my-cards.html'],
            'control':    ['control', t('control_panel'), '⚙️', buildControlPanelHTML()],
            'notepad':    ['notepad', t('notepad_title'), '📝', buildNotepadHTML()],
            'cmd':        ['cmd', 'Command Prompt', '💻', buildCmdHTML()],
            'help':       ['help', 'Help', '❓', buildHelpHTML()],
            'about':      ['about', t('about'), 'ℹ️', buildAboutHTML()],
        };

        if (cmd.startsWith('http://') || cmd.startsWith('https://')) {
            window.open(cmd, '_blank');
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
                '<p style="color:#888;margin-top:0.5rem">Try: card, gallery, music, control, notepad, cmd</p>' +
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
    });

    // ===== Control Panel =====
    function buildControlPanelHTML() {
        var cats = [
            { icon: '🎨', key: 'cp_category_appearance' },
            { icon: '🌐', key: 'cp_category_network' },
            { icon: '🔊', key: 'cp_category_sounds' },
            { icon: '⚡', key: 'cp_category_performance' },
            { icon: '🖨️', key: 'cp_category_printers' },
            { icon: '👤', key: 'cp_category_accounts' },
            { icon: '📅', key: 'cp_category_date' },
            { icon: '♿', key: 'cp_category_accessibility' },
            { icon: '🛡️', key: 'cp_category_security' },
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
            h += '<div class="cp-cat">';
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

    function openControlPanel() {
        XPShell.openWindow('control', t('control_panel'), '⚙️', buildControlPanelHTML());
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

    // ===== Command Prompt =====
    function buildCmdHTML() {
        return '<div style="background:#000;color:#0f0;height:100%;padding:12px;font-family:Consolas,monospace;font-size:13px;overflow-y:auto">' +
               '<div>Microsoft Windows XP [Version 5.1.2600]</div>' +
               '<div>(C) Copyright 1985-2001 Microsoft Corp.</div>' +
               '<div style="margin-top:8px">C:\\Documents and Settings\\User&gt;</div>' +
               '<div style="color:#888">Type "help" for available commands.</div>' +
               '</div>';
    }

    // ===== Help =====
    function buildHelpHTML() {
        return '<div style="padding:20px;font-family:Segoe UI,sans-serif">' +
               '<h2 style="color:#003399;margin-bottom:12px">' + t('about') + '</h2>' +
               '<p>Commands: <b>card, gallery, music, mycards, control, notepad, cmd</b></p>' +
               '<p style="margin-top:8px">Run dialog: Start → Run... or <b>Alt+R</b></p>' +
               '<p style="margin-top:8px">' + t('version') + '</p>' +
               '</div>';
    }

    // ===== About =====
    function buildAboutHTML() {
        return '<div style="text-align:center;padding:2rem;font-family:Segoe UI,sans-serif">' +
               '<img src="/static/img/logo.svg" style="width:64px;height:64px;margin-bottom:12px;">' +
               '<h2 style="color:#003399">Lucky Card</h2>' +
               '<p style="margin-top:8px">' + t('version') + '</p>' +
               '<p style="margin-top:4px;color:#888">' + t('registered') + '</p>' +
               '<p style="margin-top:16px;color:#888">Physical memory available to Windows: 523,760 KB</p>' +
               '</div>';
    }

    // ===== Windows =====
    var windowsContainer = document.getElementById('xp-windows');
    var taskbarTasks = document.getElementById('xp-taskbar-tasks');
    var windows = {};
    var zIndex = 10;
    var activeWindow = null;

    function openWindow(id, title, icon, contentHTML) {
        if (windows[id]) {
            focusWindow(id);
            if (windows[id].minimized) restoreWindow(id);
            return;
        }

        if (contentHTML && (contentHTML.startsWith('/') || contentHTML.startsWith('http'))) {
            var url = contentHTML;
            _doOpen(id, title, icon, '<p style="text-align:center;padding:2rem;color:#888">Loading...</p>');
            fetch(url).then(function(r) { return r.text(); }).then(function(html) {
                var bodyEl = document.getElementById('xp-win-body-' + id);
                if (bodyEl) {
                    bodyEl.innerHTML = html;
                    var scripts = bodyEl.querySelectorAll('script');
                    scripts.forEach(function(oldScript) {
                        var newScript = document.createElement('script');
                        if (oldScript.src) {
                            newScript.src = oldScript.src;
                        } else {
                            newScript.textContent = oldScript.textContent;
                        }
                        oldScript.parentNode.replaceChild(newScript, oldScript);
                    });
                }
            }).catch(function() {
                var bodyEl = document.getElementById('xp-win-body-' + id);
                if (bodyEl) bodyEl.innerHTML = '<p style="text-align:center;padding:2rem;color:#c33">Failed to load.</p>';
            });
            return;
        }

        _doOpen(id, title, icon, contentHTML);
    }

    function _doOpen(id, title, icon, contentHTML) {
        var win = document.createElement('div');
        win.className = 'xp-window';
        win.id = 'xp-win-' + id;
        var isMobile = window.innerWidth < 768;
        if (isMobile) {
            win.style.cssText = 'top:0;left:0;right:0;bottom:40px;z-index:' + (++zIndex) + ';';
        } else {
            win.style.cssText = 'top:60px;left:100px;width:600px;height:440px;z-index:' + (++zIndex) + ';';
        }
        win.innerHTML =
            '<div class="xp-titlebar" id="xp-title-' + id + '">' +
                '<span class="xp-title-icon">' + icon + '</span>' +
                '<span class="xp-title-text">' + title + '</span>' +
                '<div class="xp-title-btns">' +
                    '<button class="xp-btn-min" title="Minimize">─</button>' +
                    '<button class="xp-btn-max" title="Maximize">□</button>' +
                    '<button class="xp-btn-close" title="Close">✕</button>' +
                '</div>' +
            '</div>' +
            '<div class="xp-window-body" id="xp-win-body-' + id + '">' + contentHTML + '</div>';

        windowsContainer.appendChild(win);

        var tb = document.createElement('button');
        tb.className = 'xp-task-btn active';
        tb.textContent = title;
        tb.onclick = function() { focusWindow(id); if (windows[id] && windows[id].minimized) restoreWindow(id); };
        taskbarTasks.appendChild(tb);
        taskbarTasks.classList.add('has-windows');

        windows[id] = { el: win, taskBtn: tb, minimized: false, maximized: false };

        var titleBar = win.querySelector('.xp-titlebar');
        var isDragging = false, dragX = 0, dragY = 0;
        titleBar.addEventListener('mousedown', function(e) {
            if (e.target.tagName === 'BUTTON') return;
            if (win.classList.contains('maximized')) return;
            isDragging = true;
            dragX = e.clientX - win.offsetLeft;
            dragY = e.clientY - win.offsetTop;
            win.style.cursor = 'move';
            document.body.style.userSelect = 'none';
            e.preventDefault();
        });
        document.addEventListener('mousemove', function(e) {
            if (!isDragging) return;
            var newLeft = e.clientX - dragX;
            var newTop = e.clientY - dragY;
            newLeft = Math.max(-100, Math.min(newLeft, window.innerWidth - 200));
            newTop = Math.max(0, Math.min(newTop, window.innerHeight - 80));
            win.style.left = newLeft + 'px';
            win.style.top = newTop + 'px';
            win.style.right = 'auto';
            win.style.bottom = 'auto';
        });
        document.addEventListener('mouseup', function() {
            if (isDragging) {
                isDragging = false;
                win.style.cursor = '';
                document.body.style.userSelect = '';
            }
        });

        var btns = titleBar.querySelectorAll('button');
        btns[0].onclick = function(e) { e.stopPropagation(); minimizeWindow(id); };
        btns[1].onclick = function(e) { e.stopPropagation(); toggleMaximize(id); };
        btns[2].onclick = function(e) { e.stopPropagation(); closeWindow(id); };

        win.addEventListener('mousedown', function() { focusWindow(id); });

        focusWindow(id);
    }

    function focusWindow(id) {
        if (!windows[id]) return;
        var win = windows[id];
        if (activeWindow && activeWindow !== id && windows[activeWindow]) {
            windows[activeWindow].taskBtn.classList.remove('active');
            var prevTitle = document.getElementById('xp-title-' + activeWindow);
            if (prevTitle) prevTitle.classList.add('inactive');
        }
        activeWindow = id;
        win.el.style.zIndex = ++zIndex;
        win.taskBtn.classList.add('active');
        var titleBar = document.getElementById('xp-title-' + id);
        if (titleBar) titleBar.classList.remove('inactive');
    }

    function minimizeWindow(id) {
        if (!windows[id]) return;
        windows[id].el.classList.add('minimized');
        windows[id].minimized = true;
        windows[id].taskBtn.classList.remove('active');
        if (activeWindow === id) activeWindow = null;
    }

    function restoreWindow(id) {
        if (!windows[id]) return;
        windows[id].el.classList.remove('minimized');
        windows[id].minimized = false;
        focusWindow(id);
    }

    function toggleMaximize(id) {
        if (!windows[id]) return;
        var win = windows[id];
        if (win.maximized) {
            win.el.classList.remove('maximized');
            win.el.style.cssText = 'top:60px;left:100px;width:600px;height:440px;z-index:' + (++zIndex) + ';';
            win.maximized = false;
        } else {
            win.el.classList.add('maximized');
            win.maximized = true;
        }
        focusWindow(id);
    }

    function closeWindow(id) {
        if (!windows[id]) return;
        windows[id].el.remove();
        windows[id].taskBtn.remove();
        if (activeWindow === id) activeWindow = null;
        delete windows[id];
        if (Object.keys(windows).length === 0) {
            taskbarTasks.classList.remove('has-windows');
        }
    }

    function logOff() {
        toggleStart();
        playShutdownSound();
        var overlay = document.createElement('div');
        overlay.id = 'xp-logoff';
        overlay.style.cssText = 'position:fixed;inset:0;z-index:99999;background:#1a3a6b;display:flex;flex-direction:column;align-items:center;justify-content:center;color:#fff;font-family:"Segoe UI",sans-serif;transition:opacity 0.3s';
        overlay.innerHTML = '<div style="font-size:2rem;margin-bottom:2rem;font-weight:300;letter-spacing:1px;font-style:italic">Logging off…</div>';
        document.body.appendChild(overlay);
        setTimeout(function() {
            overlay.innerHTML = '<div style="font-size:2rem;font-weight:300;letter-spacing:1px;font-style:italic">Welcome back!</div>';
            setTimeout(function() {
                overlay.style.opacity = '0';
                setTimeout(function() { overlay.remove(); }, 300);
            }, 1500);
        }, 2000);
    }

    function powerOff() {
        toggleStart();
        playShutdownSound();
        var overlay = document.createElement('div');
        overlay.id = 'xp-poweroff';
        overlay.style.cssText = 'position:fixed;inset:0;z-index:99999;display:flex;flex-direction:column;color:#fff;font-family:"Segoe UI",sans-serif';
        overlay.innerHTML = '<div style="height:100px;background:#1a3a6b;flex-shrink:0"></div><div id="xp-po-msg" style="flex:1;background:#3b6fb6;display:flex;align-items:center;justify-content:center;font-size:2rem;font-weight:300;letter-spacing:1px;font-style:italic">Logging off…</div><div style="height:100px;background:#1a3a6b;flex-shrink:0"></div>';
        document.body.appendChild(overlay);
        setTimeout(function() {
            document.getElementById('xp-po-msg').textContent = 'LuckyCard OS is shutting down…';
            setTimeout(function() {
                overlay.style.background = '#000';
                overlay.innerHTML = '';
                setTimeout(function() { location.reload(); }, 5000);
            }, 3000);
        }, 2500);
    }

    window.XPShell = {
        openWindow: openWindow,
        toggleStart: toggleStart,
        focusWindow: focusWindow,
        closeWindow: closeWindow,
        logOff: logOff,
        shutDown: powerOff,
        openRun: openRun,
        closeRun: closeRun,
        runCommand: runCommand,
        openControlPanel: openControlPanel,
        setLang: setLang,
    };

})();
