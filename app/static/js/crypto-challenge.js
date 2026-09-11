/* Crypto Challenge window logic (XP form, EN UI only).
   Loaded via XPShell.openWindow -> fetch + innerHTML, scripts re-executed.
   Keep functions global (no IIFE) so inline onclick handlers can find them.
   Never inline 'onclick' inside JS-built HTML strings — use event delegation. */
(function () {
  var TAB = 'challenges';

  function esc(s) {
    return String(s == null ? '' : s).replace(/&/g, '&amp;').replace(/</g, '&lt;')
      .replace(/>/g, '&gt;').replace(/"/g, '&quot;');
  }

  function stars(d) {
    var n = parseInt(d, 10) || 1, s = '';
    for (var i = 0; i < n; i++) s += '★';
    return s;
  }

  function medal(r) {
    return r === 1 ? '1st' : r === 2 ? '2nd' : r === 3 ? '3rd' : String(r) + '.';
  }

  var NAMES = {
    Q1: 'Base64', Q2: 'Caesar', Q3: 'ROT13', Q4: 'boon-enc v1 (10 rounds)',
    Q5: 'boon-enc v1 (8 rounds)', Q6: 'Vigenere', Q7: 'SHA-256 preimage',
    Q8: 'boon-enc v1 (34 rounds) - FINAL BOSS'
  };

  // ───────────────────────── challenges tab ─────────────────────────

  function render(data) {
    var list = data.challenges || [], solvedN = 0, html = '';
    for (var i = 0; i < list.length; i++) if (list[i].solved) solvedN++;
    document.getElementById('stats').textContent =
      'Challenges: ' + list.length + '  |  Solved by you: ' + solvedN +
      '  |  One answer per challenge. 5 tries per 5 minutes.';

    for (var j = 0; j < list.length; j++) {
      var c = list[j], cipherArea = '';
      if (c.cipher) {
        cipherArea = '<div class="ch-cipher">' + esc(c.cipher) + '</div>';
      } else if (c.file) {
        cipherArea = '<div class="ch-cipher">Cipher is a large file (' +
          'download it, then crack it locally):<br><a class="dl" href="' +
          esc(c.file) + '" download>Download cipher file</a></div>';
      }
      var solvedTag = c.solved ? '<span class="ch-solved">[SOLVED]</span>' : '';
      var submitRow = c.solved ? '' :
        '<div class="ch-row">' +
          '<input type="text" id="ans-' + esc(c.qid) + '" placeholder="Your plaintext answer" autocomplete="off">' +
          '<button class="xp-btn" data-submit="' + esc(c.qid) + '">Submit</button>' +
        '</div><div class="ch-msg" id="msg-' + esc(c.qid) + '"></div>';
      html += '<div class="ch">' +
        '<div class="ch-head">' +
          '<span class="ch-qid">' + esc(c.qid) + '</span>' +
          '<span class="ch-diff">' + stars(c.diff) + '</span>' +
          '<span class="ch-algo">' + esc(c.algo) + '</span>' + solvedTag +
          '<span class="ch-pts">' + (c.pts || 0) + ' pts</span>' +
        '</div>' +
        '<div class="ch-hint">' + esc(c.hint) + '</div>' +
        cipherArea + submitRow + '</div>';
    }
    document.getElementById('chlist').innerHTML = html;
  }

  function showMsg(qid, cls, text) {
    var el = document.getElementById('msg-' + qid);
    if (el) { el.className = 'ch-msg ' + cls; el.textContent = text; }
  }

  function submit(qid) {
    var input = document.getElementById('ans-' + qid);
    var answer = input ? input.value : '';
    if (!answer.trim()) { showMsg(qid, 'msg-info', 'Type your answer first.'); return; }
    showMsg(qid, 'msg-info', 'Checking...');
    fetch('/api/crypto/submit', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ qid: qid, answer: answer })
    })
      .then(function (r) { return r.json().then(function (d) { return { status: r.status, data: d }; }); })
      .then(function (res) {
        var d = res.data;
        if (res.status === 429) { showMsg(qid, 'msg-bad', d.detail || 'Too many tries.'); return; }
        if (!d.ok) {
          var left = (d.attempts_left !== undefined) ? ' Attempts left: ' + d.attempts_left + '.' : '';
          showMsg(qid, 'msg-bad', 'Wrong answer.' + left);
          return;
        }
        if (d.already) {
          showMsg(qid, 'msg-ok', 'Correct! (already solved)');
        } else if (d.credited) {
          showMsg(qid, 'msg-ok', 'Correct! +' + (d.pts || 0) +
            ' pts added to your wallet. Balance: ' + d.balance + ' pts.');
        } else {
          showMsg(qid, 'msg-ok', 'Correct! +' + (d.pts || 0) +
            ' pts on the leaderboard. Log in to bank them in your wallet.');
        }
        load();
      })
      .catch(function () { showMsg(qid, 'msg-bad', 'Network error. Try again.'); });
  }

  // ───────────────────────── leaderboard + certificate tab ─────────────────────────

  function boardHead(d) {
    return '<div class="board-head">' +
      '<div class="stat"><b>' + (d.total_players || 0) + '</b><span>players on the board</span></div>' +
      '<div class="stat"><b>' + (d.total_challenges || 0) + '</b><span>challenges live</span></div>' +
      '<div class="stat"><b>100</b><span>pts for the final boss</span></div>' +
      '</div>';
  }

  function boardTable(d) {
    var rows = d.rows || [];
    if (!rows.length) {
      return '<div class="empty">Nobody has cracked a single challenge yet.<br>' +
        '<b>You could be the first name on this board.</b><br>' +
        '<span class="muted">Solve anything on the Challenges tab - your name appears here instantly.</span></div>';
    }
    var h = '<table class="board-table"><tr><th>#</th><th>Player</th><th>Solved</th>' +
      '<th>Points</th><th>Last solve</th></tr>';
    for (var i = 0; i < rows.length; i++) {
      var r = rows[i];
      h += '<tr class="' + (r.rank <= 3 ? 'top' : '') + '">' +
        '<td class="medal">' + medal(r.rank) + '</td>' +
        '<td><b>' + esc(r.name) + '</b>' +
          (r.kind === 'user' ? ' <span class="tag">member</span>' :
            ' <span class="tag g">guest</span>') + '</td>' +
        '<td>' + r.solved_count + '</td>' +
        '<td class="pts">' + r.points + '</td>' +
        '<td class="when">' + esc(r.last || '') + '</td>' +
      '</tr>';
    }
    return h + '</table><div class="board-note">Guests can be ranked, but points only land in the wallet ' +
      'of a logged-in account. <b>Log in before you crack the next one.</b></div>';
  }

  function certBox(c) {
    if (!c || !c.ok) {
      return '<div class="empty">No certificate yet.<br>' +
        '<b>Solve at least one challenge</b> and your certificate is generated here automatically.<br>' +
        '<span class="muted">Start with Q1 on the Challenges tab - it is only Base64.</span></div>';
    }
    var chips = '';
    for (var i = 0; i < (c.solved || []).length; i++) {
      var q = c.solved[i];
      chips += '<div class="chip' + (q === 'Q8' ? ' boss' : '') + '"><b>' + esc(q) + '</b><span>' +
        esc(NAMES[q] || 'cipher') + '</span></div>';
    }
    var pct = Math.round((c.solved.length / Math.max(1, c.total_challenges)) * 100);
    return '<div class="cert">' +
      '<div class="cert-frame">' +
      '  <div class="cert-top">LUCKY CARD &middot; HICARD.WORLD</div>' +
      '  <div class="cert-title">Certificate of Cracking</div>' +
      '  <div class="cert-name">' + esc(c.name) + '</div>' +
      '  <div class="cert-line">has broken <b>' + c.solved.length + ' of ' + c.total_challenges +
        '</b> ciphers on the Crypto Challenge wall,<br>earning <b>' + c.points + ' Lucky Points</b>.</div>' +
      '  <div class="chips">' + chips + '</div>' +
      '  <div class="cert-bar"><div style="width:' + pct + '%"></div></div>' +
      '  <div class="cert-meta"><span>First solve: <b>' + esc(c.first || '-') + '</b></span>' +
        '<span>Latest: <b>' + esc(c.last || '-') + '</b></span></div>' +
      '  <div class="cert-foot">Verified by SHA-256 &middot; answers are never stored in plaintext.<br>' +
        'hicard.world - Lucky Card, an XP desktop on the web.</div>' +
      '</div>' +
      '<div class="cert-actions">' +
      '  <button class="xp-btn" id="cert-copy">Copy certificate link</button>' +
      '  <span id="cert-msg" class="muted"></span>' +
      '</div></div>';
  }

  function certLink() {
    var m = document.getElementById('cert-msg');
    var url = location.origin + '/?open=crypto&cert=1';
    if (navigator.clipboard && navigator.clipboard.writeText) {
      navigator.clipboard.writeText(url).then(
        function () { if (m) m.textContent = 'Copied - go show it off.'; },
        function () { if (m) m.textContent = url; });
    } else if (m) { m.textContent = url; }
  }

  function loadBoard() {
    var box = document.getElementById('board');
    box.innerHTML = '<div class="empty muted">Loading...</div>';
    Promise.all([
      fetch('/api/crypto/leaderboard?limit=20').then(function (r) { return r.json(); })
        .catch(function () { return { rows: [], total_players: 0 }; }),
      fetch('/api/crypto/cert').then(function (r) { return r.json(); })
        .catch(function () { return { ok: false }; })
    ]).then(function (res) {
      box.innerHTML = boardHead(res[0]) + boardTable(res[0]) +
        '<div class="sect">Your certificate</div>' + certBox(res[1]);
      var cp = document.getElementById('cert-copy');
      if (cp) cp.onclick = certLink;
    });
  }

  // ───────────────────────── tabs + load ─────────────────────────

  function setTab(name) {
    TAB = name;
    var tabs = document.querySelectorAll('.tab');
    for (var i = 0; i < tabs.length; i++) {
      var on = tabs[i].getAttribute('data-tab') === name;
      tabs[i].className = on ? 'tab on' : 'tab';
    }
    document.getElementById('pane-challenges').style.display = name === 'challenges' ? 'block' : 'none';
    document.getElementById('pane-board').style.display = name === 'board' ? 'block' : 'none';
    if (name === 'challenges') load(); else loadBoard();
  }

  function load() {
    fetch('/api/crypto/list')
      .then(function (r) { return r.json(); })
      .then(render)
      .catch(function () {
        document.getElementById('stats').textContent = 'Failed to load challenges.';
      });
  }

  document.addEventListener('click', function (e) {
    var t = e.target;
    if (!t || !t.closest) return;
    var btn = t.closest('[data-submit]');
    if (btn) { submit(btn.getAttribute('data-submit')); return; }
    var tab = t.closest('[data-tab]');
    if (tab) setTab(tab.getAttribute('data-tab'));
  });

  document.addEventListener('keydown', function (e) {
    if (e.key !== 'Enter') return;
    var t = e.target;
    if (t && t.id && t.id.indexOf('ans-') === 0) submit(t.id.slice(4));
  });

  // Deep link: /?open=crypto&cert=1 lands on the board tab
  if (/[?&]cert=1/.test(location.search)) setTab('board');
  else load();
})();
