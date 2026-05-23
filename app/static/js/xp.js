// Lucky Card XP Shell — taskbar clock, start menu, window management
(function() {
    'use strict';

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
    var windows = {};  // id -> { el, taskBtn, minimized, maximized }
    var zIndex = 10;
    var activeWindow = null;

    function openWindow(id, title, icon, contentHTML) {
        // If already open, focus it
        if (windows[id]) {
            focusWindow(id);
            if (windows[id].minimized) restoreWindow(id);
            return;
        }

        // Create window element
        var win = document.createElement('div');
        win.className = 'xp-window';
        win.id = 'xp-win-' + id;
        win.style.cssText = 'top:60px;left:100px;width:600px;height:440px;z-index:' + (++zIndex) + ';';
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

        // Taskbar button
        var tb = document.createElement('button');
        tb.className = 'xp-task-btn active';
        tb.textContent = title;
        tb.onclick = function() { focusWindow(id); if (windows[id] && windows[id].minimized) restoreWindow(id); };
        taskbarTasks.appendChild(tb);

        windows[id] = { el: win, taskBtn: tb, minimized: false, maximized: false };

        // Title bar buttons
        var titleBar = win.querySelector('.xp-titlebar');
        var btns = titleBar.querySelectorAll('button');
        btns[0].onclick = function(e) { e.stopPropagation(); minimizeWindow(id); };
        btns[1].onclick = function(e) { e.stopPropagation(); toggleMaximize(id); };
        btns[2].onclick = function(e) { e.stopPropagation(); closeWindow(id); };

        // Click to focus
        win.addEventListener('mousedown', function() { focusWindow(id); });

        focusWindow(id);
    }

    function focusWindow(id) {
        if (!windows[id]) return;
        var win = windows[id];

        // Deactivate previous
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

    function toggleStartMenu() {
        if (menuOpen) {
            menuOpen = false;
            startMenu.classList.remove('show');
            startBtn.classList.remove('open');
        }
    }

    // Expose
    window.XPShell = {
        openWindow: openWindow,
        toggleStart: toggleStart,
        toggleStartMenu: toggleStartMenu,
        focusWindow: focusWindow,
        closeWindow: closeWindow
    };

})();
