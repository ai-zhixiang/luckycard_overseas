// Lucky Card XP Shell — taskbar clock, start menu, window management
(function() {
    'use strict';
    // ===== Audio autoplay: start muted, unmute on desktop =====
    var _xpAudio = new Audio('/static/audio/xp-startup.mp3');
    _xpAudio.volume = 0.7;
    _xpAudio.muted = true;
    _xpAudio.loop = false;
    _xpAudio.play().catch(function(){});
    var _xpAudioReady = false;
    function playStartupSound() {
        if (_xpAudioReady) return;
        _xpAudioReady = true;
        _xpAudio.muted = false;
        _xpAudio.currentTime = 0;
        _xpAudio.play().catch(function(){});
    }

    // ===== XP Startup Sound =====
    function playStartupSound() {
        try {
            var audio = new Audio('/static/audio/xp-startup.mp3');
            audio.volume = 0.7;
            var playPromise = audio.play();
            if (playPromise) {
                playPromise.catch(function() {
                    // Autoplay blocked, will retry on interaction
                });
            }
        } catch(e) {}
    }

    // Play startup sound after boot — but only if audio already unlocked
    var checkReady = setInterval(function() {
        if (!document.getElementById('bios-screen')) {
            clearInterval(checkReady);
            playStartupSound();
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

        // If content is a URL, fetch it
        if (contentHTML && (contentHTML.startsWith('/') || contentHTML.startsWith('http'))) {
            var url = contentHTML;
            _doOpen(id, title, icon, '<p style="text-align:center;padding:2rem;color:#888">Loading...</p>');
            fetch(url).then(function(r) { return r.text(); }).then(function(html) {
                var bodyEl = document.getElementById('xp-win-body-' + id);
                if (bodyEl) bodyEl.innerHTML = html;
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
        // Title bar — drag to move
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

    window.XPShell = {
        openWindow: openWindow,
        toggleStart: toggleStart,
        focusWindow: focusWindow,
        closeWindow: closeWindow
    };

})();
