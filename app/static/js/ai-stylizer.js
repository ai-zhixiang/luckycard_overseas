// AI Stylizer — XP Window Script
(function() {
  var pf = null, cs = 'watercolor';

  var dz = document.getElementById('sz-drop');
  var fi = document.getElementById('sz-file');
  var btn = document.getElementById('sz-gen-btn');
  var st = document.getElementById('sz-status');
  var origImg = document.getElementById('sz-orig-img');
  var origEmp = document.getElementById('sz-orig-empty');
  var resImg = document.getElementById('sz-result-img');
  var resEmp = document.getElementById('sz-result-empty');

  fi.addEventListener('change',function(e){
    var f = e.target.files[0];
    if(!f)return;
    pf = f;
    var rd = new FileReader();
    rd.onload = function(ev){
      origImg.src = ev.target.result;
      origImg.style.display = 'block';
      origEmp.style.display = 'none';
      resImg.style.display = 'none';
      resEmp.style.display = 'block';
      btn.disabled = false;
      st.style.display = 'none';
    };
    rd.readAsDataURL(f);
  });

  dz.addEventListener('dragover',function(e){e.preventDefault();dz.classList.add('dragover')});
  dz.addEventListener('dragleave',function(){dz.classList.remove('dragover')});
  dz.addEventListener('drop',function(e){
    e.preventDefault();dz.classList.remove('dragover');
    var f = e.dataTransfer.files[0];
    if(f){fi.files = e.dataTransfer.files; fi.dispatchEvent(new Event('change'))}
  });

  window.SPick = function(el){
    document.querySelectorAll('.stylist-opt').forEach(function(s){s.classList.remove('selected')});
    el.classList.add('selected');
    cs = el.dataset.style;
  };

  var PROMPTS = {
    watercolor:'watercolor painting style, soft colors, painted on paper, artistic brush strokes',
    anime:'anime art style, vibrant colors, cel-shaded, Japanese animation style',
    oilpainting:'oil painting style, thick brush strokes, canvas texture, classical painting',
    pixelart:'pixel art style, 8-bit retro game graphics, blocky pixels, limited color palette',
    sketch:'pencil sketch style, black and white, hand-drawn, rough lines',
    cinematic:'cinematic photography style, dramatic lighting, film grain, professional photo'
  };

  var TIMEOUT_MS = 200000;  // 200s hard cap — otherwise the button says "Generating" forever

  function setStatus(html, bg, border, color){
    st.style.display = 'block';
    st.style.background = bg;
    st.style.border = border;
    st.style.color = color;
    st.innerHTML = html;
  }

  window.SGenerate = async function(){
    if(!pf)return;
    btn.disabled = true;
    btn.innerHTML = 'Generating...';

    // Live elapsed counter: a bare "Generating..." for 90s looks like a hang,
    // so show the seconds ticking and a rough expectation.
    var t0 = Date.now();
    function tick(){
      var s = Math.round((Date.now() - t0) / 1000);
      setStatus('AI is painting&hellip; <b>' + s + 's</b> ' +
        '<span style="color:#999">(usually 40-90s &mdash; keep this window open)</span>',
        '#ffffe0', '1px solid #ccc', '#666');
    }
    tick();
    var iv = setInterval(tick, 1000);
    var ctrl = new AbortController();
    var to = setTimeout(function(){ ctrl.abort(); }, TIMEOUT_MS);

    try{
      var fd = new FormData();
      fd.append('file', pf);
      fd.append('style', cs);
      fd.append('style_prompt', PROMPTS[cs]);
      var r = await fetch('/api/stylize', {method:'POST', body:fd, signal: ctrl.signal});
      var d = await r.json();
      if(r.status === 402 || (d && d.detail && d.detail.code === 'quota_blocked')){
        if(window.parent && parent.Lucky){ parent.Lucky.quotaBlocked(d.detail || d); }
        else { setStatus('Error: daily free quota used up', '#f0d8d8', '1px solid #a88', '#600'); }
        return;
      }
      if(d.status === 'ok'){
        resImg.src = d.result_url;
        resImg.style.display = 'block';
        resEmp.style.display = 'none';
        var secs = Math.round((Date.now() - t0) / 1000);
        setStatus('Done in ' + secs + 's! <a href="'+d.result_url+'" download style="color:#36a">Download</a> <a href="'+d.result_url+'" target="_blank" style="color:#36a">Open</a>',
          '#e8f0d8', '1px solid #8a8', '#030');
      } else {
        setStatus('Error: ' + (d.message || 'Generation failed') + ' <span style="color:#999">(you were not charged)</span>',
          '#f0d8d8', '1px solid #a88', '#600');
      }
    } catch(e){
      var msg = (e && e.name === 'AbortError')
        ? 'Timed out after ' + Math.round(TIMEOUT_MS/1000) + 's — the server may still be working, try again in a minute.'
        : ('Error: ' + (e && e.message ? e.message : e));
      setStatus(msg, '#f0d8d8', '1px solid #a88', '#600');
    } finally {
      clearInterval(iv);
      clearTimeout(to);
      btn.innerHTML = 'Generate';
      btn.disabled = false;
    }
  };
})();
