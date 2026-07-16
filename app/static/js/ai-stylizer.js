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

  window.SGenerate = async function(){
    if(!pf)return;
    btn.disabled = true;
    btn.innerHTML = 'Generating...';
    st.style.display = 'block';
    st.className = '';
    st.style.background = '#ffffe0';
    st.style.border = '1px solid #ccc';
    st.style.color = '#666';
    st.innerHTML = 'AI is painting...';

    try{
      var fd = new FormData();
      fd.append('file', pf);
      fd.append('style', cs);
      fd.append('style_prompt', PROMPTS[cs]);
      var r = await fetch('/api/stylize', {method:'POST', body:fd});
      var d = await r.json();
      if(d.status === 'ok'){
        resImg.src = d.result_url;
        resImg.style.display = 'block';
        resEmp.style.display = 'none';
        st.style.background = '#e8f0d8';
        st.style.border = '1px solid #8a8';
        st.style.color = '#030';
        st.innerHTML = 'Done! <a href="'+d.result_url+'" download style="color:#36a">Download</a> <a href="'+d.result_url+'" target="_blank" style="color:#36a">Open</a>';
      } else {
        st.style.background = '#f0d8d8';
        st.style.border = '1px solid #a88';
        st.style.color = '#600';
        st.innerHTML = 'Error: ' + (d.message || 'Generation failed');
      }
    } catch(e){
      st.style.background = '#f0d8d8';
      st.style.border = '1px solid #a88';
      st.style.color = '#600';
      st.innerHTML = 'Error: ' + e.message;
    }
    btn.innerHTML = 'Generate';
    btn.disabled = false;
  };
})();
