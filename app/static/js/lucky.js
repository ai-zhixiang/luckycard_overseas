/* Lucky Card add-ons: XP login gate, Lucky Points wallet, PayPal recharge.
   Loaded after xp.js. Exposes window.Lucky. */
(function () {
  'use strict';

  var API = {
    status: '/api/session/status',
    guest: '/api/session/guest',
    login: '/api/session/login',
    register: '/api/session/register',
    logout: '/api/session/logout',
    wallet: '/api/wallet',
    ppConfig: '/api/payment/paypal/config',
    rechargeCreate: '/api/wallet/recharge/create',
    rechargeCapture: function (id) { return '/api/wallet/recharge/capture/' + id; },
  };

  var state = { has_session: false, kind: 'ip', name: 'Guest', user_id: null, free: { remaining: 3, limit: 3 }, balance: 0, costs: {} };
  var paypalLoaded = false;
  // Stack of xpBox modal overlays (login / wallet / quota / notices), for
  // XP-style "close the top-most dialog" (used by desktop Alt+F4).
  var xpBoxes = [];

  function esc(s) { return String(s == null ? '' : s).replace(/[&<>"']/g, function (c) { return { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]; }); }

  function jget(url) { return fetch(url).then(function (r) { return r.json().then(function (d) { return { http: r.status, data: d }; }); }); }
  function jpost(url, body) { return fetch(url, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body || {}) }).then(function (r) { return r.json().then(function (d) { return { http: r.status, data: d }; }); }); }

  function refreshStatus() {
    return jget(API.status).then(function (r) {
      if (r.http === 200) state = Object.assign({}, state, r.data);
      else state.has_session = false;
      return state;
    }).catch(function () { return state; });
  }

  function el(tag, attrs, html) {
    var n = document.createElement(tag);
    if (attrs) Object.keys(attrs).forEach(function (k) { n.setAttribute(k, attrs[k]); });
    if (html != null) n.innerHTML = html;
    return n;
  }

  function xpBox(title, bodyHtml, w, z) {
    var ov = el('div', { style: 'position:fixed;inset:0;z-index:' + (z || 210000) + ';display:flex;align-items:center;justify-content:center;background:rgba(0,0,0,0.35);font-family:Tahoma,\'Microsoft Sans Serif\',sans-serif;' });
    var box = el('div', { style: 'width:' + (w || 460) + 'px;max-width:94vw;background:#ECE9D8;border:2px solid #0054E3;border-radius:8px 8px 0 0;box-shadow:4px 4px 18px rgba(0,0,0,.45);overflow:hidden;' });
    var tb = el('div', { style: 'background:linear-gradient(180deg,#0058E6 0%,#2E82F0 3%,#4090F0 8%,#1A6AE0 50%,#0058E6 95%,#0048C8 100%);padding:5px 8px;color:#fff;font-size:13px;font-weight:bold;text-shadow:1px 1px 1px rgba(0,0,0,.5);display:flex;align-items:center;' });
    tb.innerHTML = title;
    var x = el('span', { title: 'Close', style: 'margin-left:auto;cursor:pointer;width:20px;height:20px;line-height:18px;text-align:center;font-weight:bold;font-size:13px;color:#fff;background:linear-gradient(180deg,#E0432F 0%,#B02018 100%);border:1px solid #8E1008;border-radius:3px;user-select:none;flex-shrink:0;' });
    x.textContent = '\u00D7';
    x.addEventListener('click', function (e) { e.stopPropagation(); ov.remove(); });
    tb.appendChild(x);
    box.appendChild(tb);
    var body = el('div', { style: 'padding:16px 18px;color:#000;font-size:13px;line-height:1.55;max-height:78vh;overflow:auto;' });
    body.innerHTML = bodyHtml;
    box.appendChild(body);
    ov.appendChild(box);
    ov.addEventListener('click', function (e) { if (e.target === ov) ov.remove(); });
    document.body.appendChild(ov);
    xpBoxes.push(ov);
    return { ov: ov, body: body };
  }

  // Close the most recently shown xpBox overlay that is still on screen.
  // Returns true if one was closed. (Keyboard/Alt+F4 closing of these dialogs
  // is handled by the desktop app shell, not by page keydown listeners — the
  // page can never see Alt+F4 in a real browser.)
  function closeTopOverlay() {
    for (var i = xpBoxes.length - 1; i >= 0; i--) {
      var o = xpBoxes[i];
      if (o && o.parentNode === document.body) { o.remove(); return true; }
    }
    return false;
  }

  function okBox(title, msg) {
    var r = xpBox(title, '<div style="display:flex;gap:14px;align-items:flex-start">' +
      '<img src="/static/img/xp-users_48.png" style="width:40px;height:40px">' +
      '<div style="flex:1;padding-top:6px">' + esc(msg) + '</div></div>' +
      '<div style="text-align:center;margin-top:14px"><button class="lucky-btn">OK</button></div>');
    r.body.querySelector('button').onclick = function () { r.ov.remove(); };
  }

  // ─────────────────── Login window (XPShell style) ───────────────────

  var LOGIN_TEMPLATE =
    '<div style="display:flex;align-items:center;gap:16px">' +
    '  <img src="/static/img/xp-users_48.png" style="width:56px;height:56px">' +
    '  <div style="flex:1">' +
    '    <div style="font-size:15px;font-weight:bold" id="lk-login-title">Welcome to Lucky Card</div>' +
    '    <div style="color:#555;margin-top:2px">Free AI: <b>3 per IP per day</b> · more needs Lucky Points</div>' +
    '  </div>' +
    '</div>' +
    '<div id="lk-login-mode" style="margin-top:14px">' +
    '  <button class="lucky-btn" id="lk-mode-guest" style="width:100%;margin-bottom:8px;text-align:left">' +
    '    <b>Guest</b> <span style="color:#666">(no password · quota by IP)</span></button>' +
    '  <button class="lucky-btn" id="lk-mode-acct" style="width:100%;margin-bottom:8px;text-align:left">' +
    '    <b>Account sign-in</b> <span style="color:#666">(has Lucky Points / recharge)</span></button>' +
    '  <button class="lucky-btn" id="lk-mode-reg" style="width:100%;text-align:left">' +
    '    <b>Register</b> <span style="color:#666">(email + password)</span></button>' +
    '</div>' +
    '<div id="lk-login-form" style="display:none;margin-top:10px">' +
    '  <div style="display:none" id="lk-f-nick"><label style="display:block;color:#333">Nickname</label><input id="lk-in-nick" class="lucky-input" style="width:100%" placeholder="nickname (optional)"></div>' +
    '  <label style="display:block;color:#333;margin-top:6px">Email</label><input id="lk-in-email" class="lucky-input" style="width:100%" placeholder="you@example.com">' +
    '  <label style="display:block;color:#333;margin-top:6px">Password</label><input id="lk-in-pass" type="password" class="lucky-input" style="width:100%" placeholder="min 8 chars">' +
    '  <div style="text-align:right;margin-top:10px">' +
    '    <button class="lucky-btn" id="lk-form-back" style="margin-right:8px">Back</button>' +
    '    <button class="lucky-btn lucky-btn-primary" id="lk-form-go">Log in</button>' +
    '  </div>' +
    '  <div id="lk-form-err" style="color:#B00020;margin-top:8px;display:none"></div>' +
    '</div>';

  var loginBox = null, loginMode = '';

  function showLogin(reason) {
    hideLogin();
    var r = xpBox('<img src="/static/img/xp-users_20.png" style="width:18px;height:18px;margin-right:6px;vertical-align:middle">Log On to Lucky Card', LOGIN_TEMPLATE, 480, 230000);
    loginBox = r;
    r.ov.style.background = 'rgba(0,20,60,.5)';
    var modeEl = r.body.querySelector('#lk-login-mode');
    var formEl = r.body.querySelector('#lk-login-form');
    var errEl = r.body.querySelector('#lk-form-err');
    function setMode(m) {
      loginMode = m;
      modeEl.style.display = m ? 'none' : 'block';
      formEl.style.display = m ? 'block' : 'none';
      r.body.querySelector('#lk-f-nick').style.display = m === 'reg' ? 'block' : 'none';
      r.body.querySelector('#lk-login-title').textContent =
        m === 'reg' ? 'Create your account' : 'Sign in to your account';
      r.body.querySelector('#lk-form-go').textContent =
        m === 'reg' ? 'Register & log in' : 'Log in';
      errEl.style.display = 'none';
    }
    r.body.querySelector('#lk-mode-guest').onclick = function () {
      r.body.querySelector('#lk-form-go').style.display = 'none';
      jpost(API.guest).then(function (res) {
        if (res.http === 200) { hideLogin(); refreshStatus().then(function () { document.dispatchEvent(new CustomEvent('lucky:login')); }); }
        else errEl.style.display = 'block';
      });
    };
    r.body.querySelector('#lk-mode-acct').onclick = function () { setMode('login'); };
    r.body.querySelector('#lk-mode-reg').onclick = function () { setMode('reg'); };
    r.body.querySelector('#lk-form-back').onclick = function () { setMode(''); };
    r.body.querySelector('#lk-form-go').onclick = function () {
      var email = r.body.querySelector('#lk-in-email').value.trim();
      var pass = r.body.querySelector('#lk-in-pass').value;
      var nick = r.body.querySelector('#lk-in-nick').value.trim();
      var p = loginMode === 'reg' ? jpost(API.register, { email: email, password: pass, nickname: nick })
        : jpost(API.login, { email: email, password: pass });
      p.then(function (res) {
        if (res.http === 200) {
          hideLogin();
          refreshStatus().then(function () {
            document.dispatchEvent(new CustomEvent('lucky:login'));
            if (reason === 'wallet') showWallet();
          });
        } else {
          errEl.textContent = (res.data && res.data.detail) || 'Failed. Please retry.';
          errEl.style.display = 'block';
        }
      });
    };
    // auto-fill convenience: fetch status shows guest free info
    refreshStatus().then(function (s) {
      r.body.querySelector('#lk-login-title').textContent =
        'Welcome to Lucky Card · ' + (s.kind === 'user' ? esc(s.name) : 'Guest') +
        ' · Free today: ' + s.free.remaining + '/' + s.free.limit;
    });
  }

  function hideLogin() {
    if (loginBox) { loginBox.ov.remove(); loginBox = null; }
  }

  // ─────────────────── Quota blocked → upsell ───────────────────

  function quotaBlocked(body) {
    var d = (body && (body.detail || body)) || {};
    var msg = (d.message || 'Daily free quota used up') +
      '.<br><br>Free cards left (this IP): <b>' + (d.free ? d.free.remaining : 0) + '</b>' +
      '<br>This card costs: <b>' + (d.cost || 0) + ' pts</b>' +
      '<br>Your balance: <b>' + (d.balance != null ? d.balance : state.balance) + ' pts</b>';
    var r = xpBox('<img src="/static/img/xp-users_20.png" style="width:18px;height:18px;margin-right:6px;vertical-align:middle">Lucky Points', '<div style="display:flex;gap:14px;align-items:flex-start"><img src="/static/img/xp_shield_48.png" style="width:40px;height:40px"><div style="flex:1;padding-top:4px">' + msg + '</div></div><div style="text-align:center;margin-top:16px"><button class="lucky-btn" id="lk-qb-ok" style="margin-right:8px">Close</button><button class="lucky-btn lucky-btn-primary" id="lk-qb-go">Recharge Lucky Points</button></div>');
    r.body.querySelector('#lk-qb-ok').onclick = function () { r.ov.remove(); };
    r.body.querySelector('#lk-qb-go').onclick = function () {
      r.ov.remove();
      if (state.kind === 'user' && state.user_id) showWallet();
      else showLogin('wallet');
    };
  }

  // ─────────────────── Wallet & PayPal recharge ───────────────────

  function costTable(costs) {
    var names = { poem: 'Poem', vision: 'Vision', art: 'Art', stylize: 'Stylize' };
    return Object.keys(costs).map(function (k) {
      return '<tr><td>' + (names[k] || k) + '</td><td style="text-align:right">' + costs[k] + ' pts</td></tr>';
    }).join('');
  }

  function showWallet() {
    if (!window.XPShell || !window.XPShell.openWindow) { okBox('Lucky Wallet', 'Desktop not ready yet. Please retry.'); return; }
    refreshStatus().then(function (s) {
      var icon = '<img src="/static/img/xp-users_20.png" style="width:20px;height:20px;vertical-align:middle">';
      var inner;
      if (s.kind !== 'user' || !s.user_id) {
        inner = '<div style="text-align:center;padding:24px 12px;font-family:Tahoma,sans-serif">' +
          '<p style="font-size:1.2rem;font-weight:bold;margin-bottom:6px">Account required</p>' +
          '<p style="color:#666;margin-bottom:14px">Guests get 3 free cards per day. Sign in to recharge Lucky Points and keep creating.</p>' +
          '<button class="lucky-btn lucky-btn-primary" id="lk-w-login">Log in / Register</button></div>';
        window.XPShell.openWindow('wallet', 'Lucky Wallet', icon, inner);
        var b = document.getElementById('lk-w-login');
        if (b) b.onclick = function () { showLogin('wallet'); window.XPShell.closeWindow('wallet'); };
        return;
      }
      var hist = (s.history || []).slice(0, 8).map(function (h) {
        return '<div style="display:flex;justify-content:space-between;gap:10px;border-bottom:1px solid #ddd;padding:3px 0"><span style="color:#666">' + esc(h.note || h.t) + '</span><b>' + esc(h.delta) + '</b></div>';
      }).join('') || '<div style="color:#999">No records yet</div>';
      inner =
        '<div style="font-family:Tahoma,sans-serif;min-width:380px">' +
        '  <div style="display:flex;gap:16px;align-items:center;padding-bottom:10px;border-bottom:2px solid #0054E3">' +
        '    <img src="/static/img/xp-users_48.png" style="width:44px;height:44px">' +
        '    <div><div style="color:#666;font-size:12px">' + esc(s.name) + ' &#39;s Lucky Points</div>' +
        '    <div style="font-size:26px;font-weight:bold;color:#003399">' + s.balance + ' <span style="font-size:13px;color:#666">pts</span></div></div>' +
        '    <div style="margin-left:auto;text-align:right;font-size:12px;color:#666">Free today<br><b style="color:#060;font-size:15px">' + s.free.remaining + '/' + s.free.limit + '</b></div>' +
        '  </div>' +
        '  <div style="margin-top:12px;background:#f4f1e6;border:1px solid #d5d0bd;padding:10px">' +
        '    <div style="font-weight:bold;margin-bottom:6px">Recharge Lucky Points <span style="color:#666;font-weight:normal">($1 = 100 pts)</span></div>' +
        '    <div style="display:flex;gap:8px;align-items:center">' +
        '      <span>$</span><input id="lk-pp-amount" type="number" min="1" step="1" value="5" class="lucky-input" style="width:90px">' +
        '      <span id="lk-pp-preview" style="color:#666;font-size:12px">= 500 pts</span>' +
        '    </div>' +
        '    <div id="lk-pp-btn" style="margin-top:10px"></div>' +
        '    <div id="lk-pp-msg" style="color:#B00020;margin-top:6px;font-size:12px"></div>' +
        (s.dev_grant ? '<div style="margin-top:10px"><button class="lucky-btn" id="lk-dev-grant">DEV: +100 pts free</button></div>' : '') +
        '  </div>' +
        '  <div style="margin-top:12px"><div style="font-weight:bold;margin-bottom:4px">Pricing</div>' +
        '  <table style="width:100%;border-collapse:collapse;font-size:12px"><tr><th style="text-align:left">Service</th><th style="text-align:right">Price</th></tr>' + costTable(s.costs || {}) + '</table></div>' +
        '  <div style="margin-top:12px"><div style="font-weight:bold;margin-bottom:4px">Recent activity</div>' + hist + '</div>' +
        '</div>';
      window.XPShell.openWindow('wallet', 'Lucky Wallet', icon, inner);
      wireRecharge(s.user_id);
      var dg = document.getElementById('lk-dev-grant');
      if (dg) dg.onclick = function () {
        dg.disabled = true;
        jpost('/api/wallet/grant', { points: 100 }).then(function (r) {
          dg.disabled = false;
          if (r.http === 200) {
            okBox('Test credit added', '+' + r.data.added + ' pts. Balance: ' + r.data.balance + ' pts');
            refreshStatus().then(function () { showWallet(); });
          } else okBox('Credit failed', (r.data && r.data.detail) || 'Failed');
        });
      };
    });
  }

  function wireRecharge(uid) {
    var amountEl = document.getElementById('lk-pp-amount');
    var preview = document.getElementById('lk-pp-preview');
    var msgEl = document.getElementById('lk-pp-msg');
    if (!amountEl) return;
    function upd() {
      var v = parseInt(amountEl.value, 10);
      if (isNaN(v) || v < 1) { preview.textContent = 'Minimum $1'; return; }
      preview.textContent = '= ' + (v * 100) + ' pts';
    }
    amountEl.addEventListener('input', upd); upd();
    loadPayPal().then(function (ok) {
      if (!ok) { msgEl.textContent = 'PayPal failed to load. Refresh and try again.'; return; }
      var btnBox = document.getElementById('lk-pp-btn');
      if (!btnBox) return;
      btnBox.innerHTML = '';
      try {
        paypal.Buttons({
          style: { layout: 'vertical', label: 'paypal' },
          createOrder: function () {
            var v = parseInt(amountEl.value, 10);
            if (isNaN(v) || v < 1) { msgEl.textContent = 'Enter a whole amount of at least $1'; return Promise.reject(); }
            return jpost(API.rechargeCreate, { amount_usd: v }).then(function (r) {
              if (r.http !== 200) { msgEl.textContent = (r.data && r.data.detail) || 'Order failed'; throw new Error('create'); }
              return r.data.order_id;
            });
          },
          onApprove: function (data) {
            return jpost(API.rechargeCapture(data.orderID)).then(function (r) {
              if (r.http === 200 && r.data.success) {
                refreshStatus().then(function () {
                  var w = document.getElementById('wallet');
                  showWallet();
                });
                okBox('Recharge OK', 'Added ' + r.data.added + ' pts. Balance: ' + r.data.balance + ' pts');
              } else {
                okBox('Recharge not completed', (r.data && r.data.detail) || 'Retry later from the wallet');
              }
            });
          },
          onCancel: function () { msgEl.textContent = 'Cancelled'; },
          onError: function (e) { msgEl.textContent = 'PayPal error: ' + e; },
        }).render('#lk-pp-btn');
      } catch (e) { msgEl.textContent = 'PayPal failed to initialize'; }
    });
  }

  function loadPayPal() {
    if (window.paypal) return Promise.resolve(true);
    if (paypalLoaded) return Promise.resolve(!!window.paypal);
    paypalLoaded = true;
    return jget(API.ppConfig).then(function (r) {
      if (r.http !== 200 || !r.data || !r.data.client_id) return false;
      return new Promise(function (resolve) {
        var s = document.createElement('script');
        s.src = 'https://www.paypal.com/sdk/js?client-id=' + encodeURIComponent(r.data.client_id) +
          '&currency=USD&intent=capture&disable-funding=credit,card';
        s.onload = function () { resolve(!!window.paypal); };
        s.onerror = function () { resolve(false); };
        document.head.appendChild(s);
      });
    }).catch(function () { return false; });
  }

  // ─────────────────── init & hooks ───────────────────

  function patchXPShell() {
    if (!window.XPShell) return;
    if (!window.XPShell.logOff || window.XPShell.logOff.__lucky) return;
    var orig = window.XPShell.logOff;
    window.XPShell.logOff = function () {
      try { orig.apply(window.XPShell, arguments); } catch (e) {}
      jpost(API.logout).catch(function () {});
      setTimeout(function () { showLogin(''); }, 4200);
    };
    window.XPShell.logOff.__lucky = true;
    var st = document.querySelector('.xp-start-user');
    if (st) st.onclick = function () { showWallet(); };
  }

  function boot() {
    // wait until BIOS screen is gone, then decide whether to show login
    var tries = 0;
    var iv = setInterval(function () {
      tries++;
      var biosGone = !document.getElementById('bios-screen');
      var ready = !!window.XPShell;
      if ((biosGone && ready) || tries > 120) {
        clearInterval(iv);
        patchXPShell();
        refreshStatus().then(function (s) {
          var st = document.querySelector('.xp-start-user');
          if (st) {
            st.textContent = (s.kind === 'user' ? s.name : 'Guest') + ' · ' + (s.balance || 0) + ' pts';
            st.title = 'Free today: ' + s.free.remaining + '/' + s.free.limit;
          }
          if (!s.has_session) showLogin('');
        });
      }
    }, 250);
  }

  // inject shared XP-ish button styles once
  var style = el('style');
  style.textContent = '.lucky-btn{background:linear-gradient(180deg,#fff 0%,#ECE9D8 100%);border:1px solid #7F9DB9;border-radius:3px;padding:5px 16px;font:13px Tahoma,sans-serif;cursor:pointer;color:#000}.lucky-btn:hover{background:linear-gradient(180deg,#f0e5c8,#ECE9D8)}.lucky-btn-primary{background:linear-gradient(180deg,#3a8bff,#1a5ae0);color:#fff;border-color:#1a5ae0}.lucky-btn-primary:hover{background:linear-gradient(180deg,#5aa0ff,#2a6af0)}.lucky-input{border:1px solid #7F9DB9;padding:4px 6px;font:13px Tahoma,sans-serif;border-radius:2px;background:#fff}';
  document.head.appendChild(style);

  window.Lucky = {
    showLogin: showLogin,
    hideLogin: hideLogin,
    showWallet: showWallet,
    quotaBlocked: quotaBlocked,
    refreshStatus: refreshStatus,
    getState: function () { return state; },
    _closeTopOverlay: closeTopOverlay,
  };

  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', boot);
  else boot();
})();
