from fastapi import APIRouter, Depends, HTTPException
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

router = APIRouter()

# DeepSeek API (fallback)
DEEPSEEK_URL = "https://api.deepseek.com/v1/chat/completions"
DEEPSEEK_KEY = settings.deepseek_api_key or ""

# ARK (Volcengine/Doubao) API
ARK_URL = "https://ark.cn-beijing.volces.com/api/v3/chat/completions"
ARK_KEY = settings.ark_api_key or ""

async def generate_poem(recipient: str, occasion: str = "", message: str = "") -> str:
    """Generate a poem using ARK (Doubao) or DeepSeek in the appropriate language."""
    # Detect if input contains Chinese characters
    has_chinese = bool(re.search(r'[\u4e00-\u9fff]', recipient + occasion + message))

    if has_chinese:
        prompt = f"写一首简短温馨的祝福诗（4-6行），送给{recipient}"
        if occasion:
            prompt += f"，为了{occasion}"
        if message:
            prompt += f"。主题：{message}"
        prompt += "。要真挚、简洁，用中文。不要markdown，只要诗。"
        fallback_lang = "zh"
    else:
        prompt = f"Write a short, warm greeting poem (4-6 lines) for {recipient}"
        if occasion:
            prompt += f" for {occasion}"
        if message:
            prompt += f". Theme: {message}"
        prompt += ". Keep it heartfelt, simple, and in English. No markdown, just the poem."
        fallback_lang = "en"

    # Try ARK first, then DeepSeek, then fallback
    for url, key, model in [
        (ARK_URL, ARK_KEY, "doubao-1-5-vision-pro-32k-250115"),
        (DEEPSEEK_URL, DEEPSEEK_KEY, "deepseek-chat"),
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
async def create_card(data: dict, db: AsyncSession = Depends(get_db)):
    recipient = data.get("recipient", "Friend")
    sender = data.get("sender", "Someone")
    occasion = data.get("occasion", "")
    message = data.get("message", "")
    style = data.get("style", "shuimo")
    music_id = data.get("music_id")

    # Generate poem
    poem = await generate_poem(recipient, occasion, message)

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

    return {
        "status": "ok",
        "card_id": card.id,
        "poem": poem
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
        "view_count": card.view_count
    }


# Static card-share page
@router.get("/card-share/{card_id}", response_class=HTMLResponse)
async def card_share_page(card_id: str, db: AsyncSession = Depends(get_db)):
    """Serve the card view page with OG tags for social sharing."""
    result = await db.execute(
        select(GreetingCard).where(GreetingCard.id == card_id)
    )
    card = result.scalar_one_or_none()
    if not card:
        return HTMLResponse("<h1>Card not found</h1>", status_code=404)

    poem_first = card.poem.split('\n')[0][:80] if card.poem else ""
    title = f"💌 A card from {card.sender_name}"

    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{title}</title>
    <meta property="og:title" content="{title}">
    <meta property="og:description" content="{poem_first}">
    <meta property="og:type" content="website">
    <meta property="og:url" content="https://hicard.world/api/card-share/{card_id}">
    <script>
        window.__CARD_ID = "{card_id}";
    </script>
    <link rel="stylesheet" href="/static/css/xp.css?v=10">
</head>
<body class="xp-desktop" style="display:flex;align-items:center;justify-content:center;min-height:100vh">
    <div style="text-align:center;padding:2rem;max-width:500px">
        <div style="font-size:3rem;margin-bottom:1rem">💌</div>
        <h1 style="font-family:Georgia,serif;font-size:1.5rem;margin-bottom:0.5rem">A Card for {card.recipient_name}</h1>
        <p style="color:#888;margin-bottom:2rem">from {card.sender_name}</p>
        <div style="white-space:pre-line;font-family:Georgia,serif;font-size:1.1rem;line-height:1.8;margin-bottom:2rem;background:linear-gradient(135deg,#fffaf5,#fef3e2);padding:2rem;border-radius:12px;box-shadow:0 4px 20px rgba(0,0,0,0.06)">{card.poem}</div>
        <a href="/" style="display:inline-block;background:#C41E3A;color:#fff;padding:0.75rem 2rem;border-radius:8px;text-decoration:none;font-weight:600">✨ Create Your Own Card</a>
    </div>
</body>
</html>"""
    return HTMLResponse(html)
