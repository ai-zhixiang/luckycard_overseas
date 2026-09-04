"""Chinese Culture — 每日一篇中国文化双语介绍（桌面 Chinese Culture 图标）.

流程: 按日期从主题池选一个主题 → 抓中文维基摘要作事实参考(官方 API, 免费无反爬)
      → DeepSeek 生成 中文介绍 + 地道英文翻译 → 当日缓存, 同一天重复打开秒出。
"""
import asyncio
import re
from datetime import date
from typing import Optional
from urllib.parse import quote

import httpx
from fastapi import APIRouter
from pydantic import BaseModel

from ..config import settings

router = APIRouter()

DEEPSEEK_URL = "https://api.deepseek.com/v1/chat/completions"
DEEPSEEK_KEY = settings.deepseek_api_key or ""
WIKI_REST = "https://zh.wikipedia.org/api/rest_v1/page/summary/"

# (中文名, 英文名, 中文维基词条)
TOPICS = [
    ("春节", "Spring Festival", "春节"),
    ("中秋节", "Mid-Autumn Festival", "中秋节"),
    ("端午节", "Dragon Boat Festival", "端午节"),
    ("元宵节", "Lantern Festival", "元宵节"),
    ("清明节", "Qingming Festival", "清明节"),
    ("长城", "The Great Wall", "长城"),
    ("故宫", "The Forbidden City", "故宫"),
    ("兵马俑", "Terracotta Army", "兵马俑"),
    ("京剧", "Peking Opera", "京剧"),
    ("书法", "Chinese Calligraphy", "书法"),
    ("中国画", "Chinese Painting", "中国画"),
    ("中国茶文化", "Chinese Tea Culture", "中国茶文化"),
    ("瓷器", "Chinese Porcelain", "中国陶瓷史"),
    ("丝绸之路", "The Silk Road", "丝绸之路"),
    ("孔子", "Confucius", "孔子"),
    ("老子与道家", "Laozi and Taoism", "老子"),
    ("孙子兵法", "The Art of War", "孙子兵法"),
    ("太极拳", "Tai Chi", "太极拳"),
    ("中国功夫", "Chinese Kung Fu", "中国武术"),
    ("中医", "Traditional Chinese Medicine", "中医学"),
    ("针灸", "Acupuncture", "针灸"),
    ("大熊猫", "The Giant Panda", "大熊猫"),
    ("饺子", "Jiaozi (Dumplings)", "饺子"),
    ("火锅", "Hot Pot", "火锅"),
    ("北京烤鸭", "Peking Duck", "北京烤鸭"),
    ("月饼", "Mooncake", "月饼"),
    ("筷子", "Chopsticks", "筷子"),
    ("汉字", "Chinese Characters", "汉字"),
    ("成语", "Chengyu (Chinese Idioms)", "成语"),
    ("古典诗词", "Classical Chinese Poetry", "中国古典诗歌"),
    ("红楼梦", "Dream of the Red Chamber", "红楼梦"),
    ("西游记", "Journey to the West", "西游记"),
    ("中国龙", "The Chinese Dragon", "龙"),
    ("十二生肖", "The Chinese Zodiac", "十二生肖"),
    ("苏州园林", "Suzhou Classical Gardens", "苏州园林"),
    ("皮影戏", "Chinese Shadow Puppetry", "皮影戏"),
    ("剪纸", "Chinese Paper Cutting", "剪纸"),
    ("舞狮", "Lion Dance", "舞狮"),
    ("天坛", "Temple of Heaven", "天坛"),
    ("颐和园", "Summer Palace", "颐和园"),
    ("西湖", "West Lake", "西湖"),
    ("黄山", "Huangshan Mountain", "黄山"),
    ("少林寺", "Shaolin Temple", "少林寺"),
]

_CACHE: dict = {}  # {date_str: CultureOut-ish dict}
_FALLBACK_ZH = "中华文化源远流长，每一个主题背后都是一段动人的故事。今天先从这里开始认识它吧。"
_FALLBACK_EN = "Chinese culture is vast and fascinating. Start here to discover a little more of it today."


def _topic_at(offset: int = 0) -> tuple:
    d = date.today()
    idx = (d.toordinal() + offset) % len(TOPICS)
    return TOPICS[idx], d.isoformat()


async def _fetch_wiki(title_zh: str, timeout: float = 8.0) -> str:
    """中文维基 REST summary → extract 文本。任何异常都返回空串(不影响主流程)。"""
    try:
        async with httpx.AsyncClient(
            timeout=timeout, follow_redirects=True,
            headers={"User-Agent": "LuckyCard-CultureBot/1.0 (hicard.world)"},
        ) as client:
            r = await client.get(WIKI_REST + quote(title_zh, safe=""))
            if r.status_code == 200:
                j = r.json()
                ext = (j.get("extract") or "").strip()
                if ext and "可能指" not in ext[:20]:
                    return ext
    except Exception:
        pass
    return ""


async def _generate(zh_name: str, en_name: str, wiki_zh: str) -> tuple:
    """DeepSeek 生成 中文介绍 + 英文翻译。失败返回 ('', '')。"""
    if not DEEPSEEK_KEY:
        return "", ""
    system = (
        "你是一位中国文化专家。你的任务是把中国文化讲给外国友人听："
        "内容要准确、生动、有温度，既保留文化深度，又让外国读者容易理解。"
    )
    user = (
        f"今日主题：{zh_name}（{en_name}）\n\n"
        "参考资料（来自维基百科，可能为空，只作事实参考，不要照抄）：\n"
        f"{wiki_zh[:1500] if wiki_zh else '(无)'}\n\n"
        f"请用两段输出：\n"
        f"第一段：用中文介绍「{zh_name}」，150字以内，讲清楚它是什么、为什么值得了解。\n"
        "第二段：把第一段翻译成地道英文，面向外国友人。\n\n"
        "格式：两段之间单独一行放三个等号 ===，除此之外不要任何标题或多余内容。"
    )
    try:
        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.post(
                DEEPSEEK_URL,
                json={
                    "model": "deepseek-chat",
                    "messages": [
                        {"role": "system", "content": system},
                        {"role": "user", "content": user},
                    ],
                    "max_tokens": 700,
                    "temperature": 0.8,
                },
                headers={"Authorization": f"Bearer {DEEPSEEK_KEY}"},
            )
            data = resp.json()
            text = data["choices"][0]["message"]["content"].strip()
    except Exception:
        return "", ""
    parts = re.split(r"\n?\s*===\s*\n?", text, maxsplit=1)
    zh = (parts[0] or "").strip()
    en = (parts[1] or "").strip() if len(parts) > 1 else ""
    return zh, en


class CultureOut(BaseModel):
    date: str
    title_zh: str
    title_en: str
    zh: str
    en: str


@router.get("/culture/today", response_model=CultureOut)
async def culture_today(offset: int = 0):
    topic, ds = _topic_at(offset)
    zh_name, en_name, wiki_title = topic
    cache_key = f"{ds}#{offset}"

    if cache_key in _CACHE:
        return CultureOut(**_CACHE[cache_key])

    # 事实参考: 维基摘要(最多 1.5s 超时, 失败不阻塞)
    wiki_zh = await asyncio.wait_for(_fetch_wiki(wiki_title), timeout=8)
    zh, en = await _generate(zh_name, en_name, wiki_zh)

    if not zh and wiki_zh:
        zh = wiki_zh[:400].strip()
    if not en:
        en = f"Today we explore {en_name} — one window into the rich culture of China. {_FALLBACK_EN if not zh else ''}".strip()
    if not zh:
        zh = _FALLBACK_ZH

    out = CultureOut(
        date=ds, title_zh=zh_name, title_en=en_name, zh=zh, en=en,
    )
    _CACHE[cache_key] = out.model_dump()
    return out
