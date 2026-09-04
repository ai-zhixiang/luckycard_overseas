from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import HTMLResponse
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from ..database import get_db
from ..models import GreetingCard
from ..config import settings
import httpx
import uuid
import json
import re
import os
import base64
import shutil

router = APIRouter()

# DeepSeek API (fallback)
DEEPSEEK_URL = "https://api.deepseek.com/v1/chat/completions"
DEEPSEEK_KEY = settings.deepseek_api_key or ""

# ARK (Volcengine/Doubao) API
ARK_URL = "https://ark.cn-beijing.volces.com/api/v3/chat/completions"
ARK_KEY = settings.ark_api_key or ""

# ── 相片卡策略：MD5 去重 + AI 识图缓存 ──
import hashlib

ANALYSIS_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "static", "uploads", "cards", "analysis")
os.makedirs(ANALYSIS_DIR, exist_ok=True)


def _md5(data: bytes) -> str:
    return hashlib.md5(data).hexdigest()


def _analysis_cache_path(md5_hex: str) -> str:
    return os.path.join(ANALYSIS_DIR, f"{md5_hex}.json")


def _load_analysis(md5_hex: str):
    """MD5 缓存命中：同照片不重复调 AI（中文版已验证策略）。"""
    p = _analysis_cache_path(md5_hex)
    if os.path.exists(p):
        try:
            with open(p, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return None
    return None


def _save_analysis(md5_hex: str, analysis: dict):
    try:
        with open(_analysis_cache_path(md5_hex), "w", encoding="utf-8") as f:
            json.dump(analysis, f, ensure_ascii=False)
    except Exception:
        pass


async def analyze_photo(file_bytes: bytes) -> dict:
    """豆包 vision 识图（英文）→ scene/emotion/mood。失败时返回中性兜底。"""
    import base64 as _b64
    if not ARK_KEY:
        return {"scene": "a warm moment", "emotion": "warm", "mood": "gentle"}

    b64_data = _b64.b64encode(file_bytes).decode("utf-8")
    data_url = f"data:image/jpeg;base64,{b64_data}"

    prompt = (
        "Describe this photo in English. Return ONLY JSON:\n"
        '{"scene": "scene description 5-15 words, e.g. sunset beach, city night, friends dinner", '
        '"emotion": "emotion 1-3 words, e.g. warm, romantic, joyful, nostalgic", '
        '"mood": "mood 1-3 words, e.g. cozy, lively, serene, fresh"}'
    )
    try:
        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.post(
                ARK_URL,
                json={
                    "model": "doubao-1-5-vision-pro-32k-250115",
                    "messages": [{
                        "role": "user",
                        "content": [
                            {"type": "image_url", "image_url": {"url": data_url}},
                            {"type": "text", "text": prompt},
                        ],
                    }],
                    "temperature": 0.7,
                    "max_tokens": 200,
                },
                headers={"Authorization": f"Bearer {ARK_KEY}"},
            )
            data = resp.json()
            content = data["choices"][0]["message"]["content"].strip()
            if content.startswith("```"):
                content = content.split("\n", 1)[1].rsplit("```", 1)[0].strip()
            parsed = json.loads(content)
            return {
                "scene": str(parsed.get("scene", "a warm moment"))[:80],
                "emotion": str(parsed.get("emotion", "warm"))[:30],
                "mood": str(parsed.get("mood", "gentle"))[:30],
            }
    except Exception:
        return {"scene": "a warm moment", "emotion": "warm", "mood": "gentle"}


async def pick_music_for_mood(emotion: str, db: AsyncSession) -> str | None:
    """按情绪从曲库匹配配乐；无匹配时随机。曲库 = static/music/*.mp3（文件目录）。"""
    import random as _random
    MUSIC_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "static", "music")
    try:
        files = sorted(
            f for f in os.listdir(MUSIC_DIR)
            if f.lower().endswith(".mp3") and os.path.isfile(os.path.join(MUSIC_DIR, f))
        )
    except Exception:
        return None
    if not files:
        return None
    # 情绪弱匹配：优先温和/平静类曲目名（文件是 bach_* 等古典）
    mood = (emotion or "").lower()
    prefer_kw = []
    for kw in ("calm", "peace", "serene", "gentle", "warm", "soft"):
        if kw in mood:
            prefer_kw.append(kw)
    if prefer_kw:
        cands = [f for f in files if any(k in f.lower() for k in ("aria", "da_capo"))]
        if cands:
            return _random.choice(cands).replace(".mp3", "")
    return _random.choice(files).replace(".mp3", "")

async def generate_poem(recipient: str, occasion: str = "", message: str = "", photo_context: dict | None = None) -> str:
    """Generate a poem using DeepSeek (primary) or ARK (fallback)."""
    # Detect if input contains Chinese characters
    has_chinese = bool(re.search(r'[\u4e00-\u9fff]', recipient + occasion + message))

    if has_chinese:
        prompt = (
            f"写一首祝福诗，送给一位叫【{recipient}】的人。\n"
            f"要求：诗里要出现TA的名字【{recipient}】，诗的内容要温馨真挚（4-6行）。"
        )
        if photo_context:
            prompt += f"\n背景：这是一张照片卡，照片内容是「{photo_context.get('scene','')}」，氛围是「{photo_context.get('emotion','')}」。把照片的意境融进诗里。"
        if occasion:
            prompt += f"\n场合：{occasion}"
        if message:
            prompt += f"\n可以把这段话的意思融进诗里：{message}"
        prompt += "\n直接输出诗本身，不要加标题、不要加引号、不要markdown。"
        fallback_lang = "zh"
    else:
        prompt = (
            f"Write a short warm greeting poem for a person named {recipient}.\n"
            f"The poem must include {recipient}'s name naturally."
        )
        if photo_context:
            prompt += (
                f"\nThis is a PHOTO CARD. The photo shows: {photo_context.get('scene','')}. "
                f"The mood is {photo_context.get('emotion','')} / {photo_context.get('mood','')}. "
                f"Weave the photo's imagery and feeling into the poem."
            )
        if occasion:
            prompt += f"\nOccasion: {occasion}"
        if message:
            prompt += f"\nIncorporate this sentiment naturally: {message}"
        prompt += "\nOutput just the poem, no title, no quotes, no markdown."
        fallback_lang = "en"

    # Try DeepSeek first, then ARK, then fallback
    for url, key, model in [
        (DEEPSEEK_URL, DEEPSEEK_KEY, "deepseek-chat"),
        (ARK_URL, ARK_KEY, "doubao-1-5-vision-pro-32k-250115"),
    ]:
        if not key:
            continue
        try:
            async with httpx.AsyncClient(timeout=20) as client:
                resp = await client.post(url, json={
                    "model": model,
                    "messages": [{"role": "user", "content": prompt}],
                    "max_tokens": 200,
                    "temperature": 0.8
                }, headers={"Authorization": f"Bearer {key}"})
                data = resp.json()
                poem = data["choices"][0]["message"]["content"].strip()
                poem = re.sub(r'[\*\_\#\`]', '', poem)
                if poem:
                    return poem
        except Exception:
            continue

    # Hardcoded fallback
    fallbacks_en = [
        f"May every day bring you joy,\nAnd every night bring you peace.\nYou deserve all the happiness\nThat this world can release.",
        f"Like a gentle breeze on a summer day,\nMay this card bring a smile your way.\nWishing you laughter, love, and light,\nToday and every night.",
        f"A little card, a simple thought,\nTo remind you of the joy you've brought.\nInto the lives of those you meet,\nYou make this world a bit more sweet."
    ]
    fallbacks_zh = [
        f"愿你每一天都充满欢笑，\n每一个夜晚都恬静安宁。\n所有的美好都如期而至，\n所有的幸福都与你同行。",
        f"简单的卡片，真诚的心意，\n跨越千山万水来见你。\n祝你笑容常开，喜乐常在，\n每一天都过得精彩。",
        f"缘分让我们相遇相识，\n温暖在字里行间流淌。\n愿这份祝福如春风般温柔，\n陪伴你走过每个晨昏。"
    ]
    import random
    return random.choice(fallbacks_zh if fallback_lang == "zh" else fallbacks_en)


def gen_id():
    return uuid.uuid4().hex[:12]


# 照片保存目录（hicard.world 静态）
PHOTO_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "static", "uploads", "cards")
os.makedirs(PHOTO_DIR, exist_ok=True)


def save_photo(base64_data: str, card_id: str) -> str:
    """保存 base64 照片，返回 /static/uploads/cards/xxx.jpg 相对 URL"""
    if not base64_data:
        return ""
    # 去 data:image/...;base64, 前缀
    m = re.match(r"^data:image/(\w+);base64,(.+)$", base64_data, re.S)
    if not m:
        return ""
    ext = m.group(1).lower()
    if ext not in ("jpeg", "jpg", "png", "webp", "gif"):
        ext = "jpg"
    raw = base64.b64decode(m.group(2))
    fname = f"{card_id}.{ext if ext != 'jpeg' else 'jpg'}"
    fpath = os.path.join(PHOTO_DIR, fname)
    with open(fpath, "wb") as f:
        f.write(raw)
    return f"/static/uploads/cards/{fname}"


@router.get("/cards/list")
async def list_cards(skip: int = 0, limit: int = 20, db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(GreetingCard).where(GreetingCard.is_public == True)
        .order_by(GreetingCard.created_at.desc())
        .offset(skip).limit(limit)
    )
    cards = result.scalars().all()
    return {
        "cards": [
            {
                "id": c.id,
                "recipient_name": c.recipient_name,
                "sender_name": c.sender_name,
                "poem": c.poem,
                "style": c.style,
                "created_at": c.created_at.isoformat() if c.created_at else None,
                "view_count": c.view_count
            }
            for c in cards
        ],
        "total": len(cards)
    }


@router.post("/cards/create")
async def create_card(request: Request, data: dict, db: AsyncSession = Depends(get_db)):
    # ── 计费闸门：先免费额度后点数，失败自动退还 ──
    from .auth import charge_op, refund_op
    ops = ["poem"]
    photo_b64 = data.get("photo") or data.get("photo_base64") or ""
    if photo_b64:
        m = re.match(r"^data:image/(\w+);base64,(.+)$", photo_b64, re.S)
        if m:
            try:
                if not _load_analysis(_md5(base64.b64decode(m.group(2)))):
                    ops.append("vision")
            except Exception:
                ops.append("vision")
    charge = charge_op(request, ops)
    try:
        return await _create_card_impl(data, db)
    except HTTPException:
        refund_op(request, ops, charge)
        raise
    except Exception:
        refund_op(request, ops, charge)
        raise


async def _create_card_impl(data: dict, db: AsyncSession):
    recipient = data.get("recipient", "Friend")
    sender = data.get("sender", "Someone")
    occasion = data.get("occasion", "")
    message = data.get("message", "")
    style = data.get("style", "shuimo")
    music_id = data.get("music_id")
    photo_b64 = data.get("photo") or data.get("photo_base64") or ""

    # ── 相片卡策略：照片 → MD5 去重 → AI 识图 → 写诗注入 ──
    photo_context = None
    analysis = None
    photo_md5 = ""
    photo_file_bytes = None
    if photo_b64:
        m = re.match(r"^data:image/(\w+);base64,(.+)$", photo_b64, re.S)
        if m:
            try:
                photo_file_bytes = base64.b64decode(m.group(2))
                photo_md5 = _md5(photo_file_bytes)
                # MD5 缓存命中：同照片不重复调 AI
                analysis = _load_analysis(photo_md5)
                if not analysis:
                    analysis = await analyze_photo(photo_file_bytes)
                    _save_analysis(photo_md5, analysis)
                photo_context = analysis
            except Exception:
                photo_context = None

    # Generate poem (with photo context if available)
    poem = await generate_poem(recipient, occasion, message, photo_context)

    # 自动配乐：用户没选时按情绪从曲库匹配
    auto_music = None
    if not music_id:
        emotion = (analysis or {}).get("emotion", "") if analysis else ""
        auto_music = await pick_music_for_mood(emotion, db)
        if auto_music:
            music_id = auto_music

    # Save card
    card = GreetingCard(
        id=gen_id(),
        recipient_name=recipient,
        sender_name=sender,
        poem=poem,
        style=style,
        music_id=music_id
    )
    db.add(card)
    await db.commit()

    # 照片：先建卡拿 id，再存文件更新 art_url
    art_url = ""
    if photo_b64 and photo_file_bytes:
        art_url = save_photo(photo_b64, card.id)
        if art_url:
            card.art_url = art_url
            await db.commit()

    return {
        "status": "ok",
        "card_id": card.id,
        "poem": poem,
        "art_url": art_url or card.art_url or "",
        "music_id": music_id or "",
        "analysis": analysis or {},
        "photo_md5": photo_md5,
        "auto_music": bool(auto_music),
    }


@router.get("/cards/{card_id}")
async def view_card(card_id: str, db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(GreetingCard).where(GreetingCard.id == card_id)
    )
    card = result.scalar_one_or_none()
    if not card:
        raise HTTPException(status_code=404, detail="Card not found")

    # Increment view count
    card.view_count = (card.view_count or 0) + 1
    await db.commit()

    return {
        "id": card.id,
        "recipient_name": card.recipient_name,
        "sender_name": card.sender_name,
        "poem": card.poem,
        "style": card.style,
        "music_id": card.music_id,
        "created_at": card.created_at.isoformat() if card.created_at else None,
        "view_count": card.view_count,
        "art_url": card.art_url
    }


# Static card-share page — 3D flip card (hi-card style)
@router.get("/card-share/{card_id}", response_class=HTMLResponse)
async def card_share_page(card_id: str, db: AsyncSession = Depends(get_db)):
    """Serve the card view page with 3D flip + OG tags for social sharing."""
    result = await db.execute(
        select(GreetingCard).where(GreetingCard.id == card_id)
    )
    card = result.scalar_one_or_none()
    if not card:
        return HTMLResponse("<h1>Card not found</h1>", status_code=404)

    poem_first = card.poem.split('\n')[0][:80] if card.poem else ""
    title = f"💌 A card from {card.sender_name}"
    recipient = card.recipient_name or "You"
    sender = card.sender_name or "Someone"
    poem_html = card.poem.replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')
    poem_lines = poem_html.split('\n')
    poem_block = '<br>'.join([f'<span class="pl">{l}</span>' for l in poem_lines])
    art_url = card.art_url or ""
    # 音乐：music_id → /api/music/play/{id}.mp3
    music_file = ""
    if card.music_id:
        music_file = f"/api/music/play/{card.music_id}.mp3"

    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{title}</title>
    <meta property="og:title" content="{title}">
    <meta property="og:description" content="{poem_first}">
    <meta property="og:type" content="website">
    <meta property="og:url" content="https://hicard.world/card/{card_id}">
    <meta property="og:image" content="https://hicard.world{art_url if art_url else '/static/img/card-og-default.png'}">
    <style>
        * {{ margin:0; padding:0; box-sizing:border-box; }}
        body {{
            min-height:100vh; display:flex; align-items:center; justify-content:center;
            background:linear-gradient(135deg,#e8e0d8,#f7f1e8); font-family:Georgia,serif;
            padding:20px;
        }}
        .wrap {{ text-align:center; max-width:400px; width:100%; }}
        .scene {{ perspective:1400px; margin:0 auto 24px; width:100%; max-width:340px; }}
        .card {{
            position:relative; width:100%; aspect-ratio:3/4.2; transform-style:preserve-3d;
            transition:transform .8s cubic-bezier(.4,.1,.2,1); cursor:pointer;
        }}
        .card.flipped {{ transform:rotateY(180deg); }}
        .face {{
            position:absolute; inset:0; backface-visibility:hidden; -webkit-backface-visibility:hidden;
            border-radius:18px; overflow:hidden; box-shadow:0 12px 40px rgba(0,0,0,.18);
            display:flex; flex-direction:column;
        }}
        .front {{
            background:#fff; transform:rotateY(0deg);
        }}
        .front .art {{
            flex:1; background:linear-gradient(135deg,#c41e3a,#8a1530); position:relative;
            display:flex; align-items:center; justify-content:center; overflow:hidden;
        }}
        .front .art img {{
            width:100%; height:100%; object-fit:cover; position:absolute; inset:0;
        }}
        .front .art .mono {{
            color:#fff; font-size:2.4rem; opacity:.9; text-shadow:0 2px 12px rgba(0,0,0,.3);
        }}
        .front .art .to-overlay {{
            position:absolute; bottom:14px; left:0; right:0; text-align:center;
            color:#fff; font-size:1.1rem; font-weight:600; text-shadow:0 1px 8px rgba(0,0,0,.5);
            background:linear-gradient(transparent,rgba(0,0,0,.35)); padding:24px 12px 12px;
        }}
        .front .from {{
            padding:14px 18px; text-align:center; background:#fff;
        }}
        .front .from .from-label {{ font-size:.8rem; color:#888; }}
        .front .from .from-name {{ font-size:1.05rem; font-weight:600; color:#333; margin-top:2px; }}
        .back {{
            transform:rotateY(180deg); background:linear-gradient(160deg,#fffaf5,#fdf3e6);
            padding:28px 22px; justify-content:space-between;
        }}
        .back .bc-head {{ text-align:center; }}
        .back .bc-head .heart {{ font-size:1.6rem; }}
        .back .bc-head .to {{ font-size:.95rem; color:#666; margin-top:4px; }}
        .back .bc-poem {{
            flex:1; display:flex; flex-direction:column; align-items:center; justify-content:center;
            gap:6px; padding:16px 4px;
        }}
        .back .bc-poem .pl {{ font-size:1.02rem; line-height:1.7; color:#333; }}
        .back .bc-foot {{ text-align:center; border-top:1px solid #eee; padding-top:12px; }}
        .back .bc-foot .brand {{ font-size:.8rem; color:#C41E3A; font-weight:600; }}
        .back .bc-foot .music {{ font-size:.75rem; color:#888; margin-top:4px; }}
        .hint {{ color:#999; font-size:.85rem; margin-bottom:14px; }}
        .cta {{
            display:inline-block; background:#C41E3A; color:#fff; padding:12px 28px;
            border-radius:10px; text-decoration:none; font-weight:600; font-size:1rem;
            box-shadow:0 6px 20px rgba(196,30,58,.3);
        }}
        .cta:hover {{ background:#a01a30; }}
        .music-btn {{
            margin-top:14px; display:inline-flex; align-items:center; gap:6px;
            background:#fff; border:1.5px solid #e0d0c0; color:#666; padding:8px 18px;
            border-radius:20px; cursor:pointer; font-size:.85rem; font-family:Georgia,serif;
        }}
        .music-btn.playing {{ background:#C41E3A; border-color:#C41E3A; color:#fff; }}
        .tap-hint {{
            position:absolute; top:10px; left:50%; transform:translateX(-50%);
            background:rgba(0,0,0,.5); color:#fff; font-size:.7rem; padding:4px 12px;
            border-radius:12px; z-index:2; letter-spacing:.5px;
        }}
        .share-row {{ display:flex; gap:8px; justify-content:center; flex-wrap:wrap; margin:16px 0 4px; }}
        .share-btn {{
            display:inline-flex; align-items:center; gap:6px; padding:9px 16px;
            border-radius:22px; font-size:.85rem; font-weight:600; text-decoration:none;
            border:none; cursor:pointer; font-family:Georgia,serif;
        }}
        .share-btn.email {{ background:#fff; color:#C41E3A; border:1.5px solid #C41E3A; }}
        .share-btn.whatsapp {{ background:#25D366; color:#fff; }}
        .share-btn.x {{ background:#000; color:#fff; }}
        .share-btn.fb {{ background:#1877F2; color:#fff; }}
        .share-btn.copy {{ background:#fff; color:#333; border:1.5px solid #ccc; }}
        .share-note {{ color:#999; font-size:.72rem; margin-top:8px; word-break:break-all; }}
    </style>
    <script>
        window.__CARD_ID = "{card_id}";
        window.__MUSIC = "{music_file}";
    </script>
</head>
<body>
    <div class="wrap">
        <div class="scene">
            <div class="card" id="flipCard" onclick="this.classList.toggle('flipped')">
                <div class="face front">
                    <div class="tap-hint">TAP TO FLIP</div>
                    <div class="art">
                        {f'<img src="{art_url}" alt="Card Art">' if art_url else '<div class="mono">💌</div>'}
                        <div class="to-overlay">For {recipient}</div>
                    </div>
                    <div class="from">
                        <div class="from-label">with love from</div>
                        <div class="from-name">{sender}</div>
                    </div>
                </div>
                <div class="face back">
                    <div class="bc-head">
                        <div class="heart">💌</div>
                        <div class="to">Dear {recipient},</div>
                    </div>
                    <div class="bc-poem">{poem_block}</div>
                    <div class="bc-foot">
                        <div class="brand">🃏 Lucky Card</div>
                        <div class="music">{('🎵 ' + music_file.replace('/api/music/play/','').replace('.mp3','')) if music_file else ''}</div>
                    </div>
                </div>
            </div>
        </div>
        {f'<button class="music-btn" id="musicBtn" onclick="toggleMusic()">🎵 Play Music</button>' if music_file else ''}
        <div class="hint" style="margin-top:12px">Tap the card to flip it ✨</div>
        <div class="share-row">
            <button class="share-btn email" onclick="shareEmail()">✉️ Email</button>
            <button class="share-btn whatsapp" onclick="shareWA()">💬 WhatsApp</button>
            <button class="share-btn x" onclick="shareX()">𝕏 Share</button>
            <button class="share-btn fb" onclick="shareFB()">f Facebook</button>
            <button class="share-btn copy" onclick="copyLink()">📋 Copy Link</button>
        </div>
        <div class="share-note" id="shareNote">https://hicard.world/card/{card_id}</div>
        <a class="cta" href="/">✨ Create Your Own Card</a>
    </div>

    <audio id="cardAudio" preload="none" loop></audio>
    <script>
        var _cardUrl = 'https://hicard.world/card/{card_id}';
        var _cardText = '💌 A card from {sender} — open it!';
        function _share(url) {{ var w = window.open(url, '_blank', 'width=600,height=500'); if (w) w.focus(); }}
        function shareEmail() {{ var subj = encodeURIComponent('A Lucky Card for {recipient}'); var body = encodeURIComponent(_cardText + '\\n' + _cardUrl); window.location.href = 'mailto:?subject=' + subj + '&body=' + body; }}
        function shareWA() {{ _share('https://wa.me/?text=' + encodeURIComponent(_cardText + ' ' + _cardUrl)); }}
        function shareX() {{ _share('https://twitter.com/intent/tweet?text=' + encodeURIComponent(_cardText + ' ' + _cardUrl)); }}
        function shareFB() {{ _share('https://www.facebook.com/sharer/sharer.php?u=' + encodeURIComponent(_cardUrl)); }}
        function copyLink() {{
            if (navigator.clipboard) {{
                navigator.clipboard.writeText(_cardUrl).then(function() {{ document.getElementById('shareNote').textContent = '✓ Link copied!'; }});
            }} else {{
                var ta = document.createElement('textarea'); ta.value = _cardUrl; document.body.appendChild(ta); ta.select();
                try {{ document.execCommand('copy'); document.getElementById('shareNote').textContent = '✓ Link copied!'; }} catch(e) {{}}
                document.body.removeChild(ta);
            }}
        }}
    </script>
    <script>
        var _audio = document.getElementById('cardAudio');
        var _musicUrl = window.__MUSIC;
        if(_musicUrl) _audio.src = _musicUrl;
        function toggleMusic() {{
            var b = document.getElementById('musicBtn');
            if(!_audio.src) return;
            if(_audio.paused) {{
                _audio.play().then(function(){{ b.textContent='⏸ Pause Music'; b.classList.add('playing'); }}).catch(function(){{}});
            }} else {{
                _audio.pause(); b.textContent='🎵 Play Music'; b.classList.remove('playing');
            }}
        }}
    </script>
</body>
</html>"""
    return HTMLResponse(html)
