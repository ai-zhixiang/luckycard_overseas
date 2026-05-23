// Lucky Card XP Shell — taskbar clock, start menu, window management
(function() {
    'use strict';

    // ===== XP Startup Sound =====
    function playStartupSound() {
        try {
            var ctx = new (window.AudioContext || window.webkitAudioContext)();
            var notes = [
                { f: 330, d: 0.15, t: 0 },       // E4
                { f: 392, d: 0.12, t: 0.12 },     // G4
                { f: 523, d: 0.12, t: 0.22 },     // C5
                { f: 659, d: 0.10, t: 0.32 },     // E5
                { f: 784, d: 0.10, t: 0.40 },     // G5
                { f: 1047, d: 0.30, t: 0.48 },    // C6 (hold)
                { f: 784, d: 0.20, t: 0.76 },     // G5
                { f: 1047, d: 0.60, t: 0.92 }     // C6 (final)
            ];
            notes.forEach(function(n) {
                var osc = ctx.createOscillator();
                var gain = ctx.createGain();
                osc.type = 'triangle';
                osc.frequency.value = n.f;
                gain.gain.setValueAtTime(0, ctx.currentTime + n.t);
                gain.gain.linearRampToValueAtTime(0.25, ctx.currentTime + n.t + 0.02);
                gain.gain.linearRampToValueAtTime(0.2, ctx.currentTime + n.t + n.d - 0.03);
                gain.gain.linearRampToValueAtTime(0, ctx.currentTime + n.t + n.d);
                // Add harmonic
                var osc2 = ctx.createOscillator();
                var gain2 = ctx.createGain();
                osc2.type = 'sine';
                osc2.frequency.value = n.f * 2;
                gain2.gain.setValueAtTime(0, ctx.currentTime + n.t);
                gain2.gain.linearRampToValueAtTime(0.08, ctx.currentTime + n.t + 0.02);
                gain2.gain.linearRampToValueAtTime(0, ctx.currentTime + n.t + n.d);
                osc.connect(gain); gain.connect(ctx.destination);
                osc2.connect(gain2); gain2.connect(ctx.destination);
                osc.start(ctx.currentTime + n.t);
                osc.stop(ctx.currentTime + n.t + n.d + 0.05);
                osc2.start(ctx.currentTime + n.t);
                osc2.stop(ctx.currentTime + n.t + n.d + 0.05);
            });
            setTimeout(function() { ctx.close(); }, 2300);
        } catch(e) {}
    }

    // Play startup sound after boot (delay to let boot screen finish)
    // Detect when desktop is visible (body no longer has boot screen overlay)
    var checkReady = setInterval(function() {
        if (!document.getElementById('bios-screen')) {
            clearInterval(checkReady);
            setTimeout(playStartupSound, 300);
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
            '<div class="xp-window-body">' + contentHTML + '</div>';

        windowsContainer.appendChild(win);

        var tb = document.createElement('button');
        tb.className = 'xp-task-btn active';
        tb.textContent = title;
        tb.onclick = function() { focusWindow(id); if (windows[id] && windows[id].minimized) restoreWindow(id); };
        taskbarTasks.appendChild(tb);

        windows[id] = { el: win, taskBtn: tb, minimized: false, maximized: false };

        var titleBar = win.querySelector('.xp-titlebar');
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
    }

    window.XPShell = {
        openWindow: openWindow,
        toggleStart: toggleStart,
        focusWindow: focusWindow,
        closeWindow: closeWindow
    };

})();
