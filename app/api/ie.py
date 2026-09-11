"""Lucky Card IE 6 "proxy" — lets the retro IE window actually browse the web.

Modern sites send X-Frame-Options / CSP that forbid embedding in an iframe,
so a real browser cannot show them inside the XP IE window. This endpoint
fetches the page server-side (no framing headers involved) and rewrites
navigation links so clicking around stays inside the IE window.

Security: only whitelisted public hosts are proxied (bing.com / baidu.com),
which also keeps this from being a generic SSRF vector. Nothing from the
upstream response (headers, CSP, cookies) is passed through.
"""
import re
from urllib.parse import urlparse, quote

import httpx
from fastapi import APIRouter, Query, HTTPException
from fastapi.responses import HTMLResponse, Response

router = APIRouter(tags=["ie"])

ALLOWED = ("bing.com", "baidu.com")

UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36")


def _allowed(url: str) -> bool:
    try:
        p = urlparse(url)
        if p.scheme not in ("http", "https") or not p.hostname:
            return False
        h = p.hostname.lower().rstrip(".")
        return h == ALLOWED[0] or h.endswith("." + ALLOWED[0]) or h == ALLOWED[1] or h.endswith("." + ALLOWED[1])
    except Exception:
        return False


def _rewrite(html: str) -> str:
    """Rewrite whitelisted absolute hrefs/actions so navigation stays in IE."""

    def rep(m):
        attr, q, url = m.group(1), m.group(2), m.group(3)
        full = url if url.startswith("http") else "https:" + url
        if _allowed(full):
            return attr + "=" + q + "/api/ie/browse?u=" + quote(full, safe="") + q
        return m.group(0)

    html = re.sub(r'(href|action)=(["\'])((?:https?:)?//[^"\']+)', rep, html, flags=re.I)
    # Drop CSP / refresh / compat metas that could fight our embedding.
    html = re.sub(
        r'<meta[^>]+http-equiv=["\']?(?:Content-Security-Policy|Refresh|X-UA-Compatible|Pragma|Cache-Control)[^>]*>',
        "", html, flags=re.I)
    return html


def _interstitial(final_url: str) -> str:
    esc = final_url.replace("&", "&amp;").replace('"', "&quot;").replace("<", "&lt;")
    return (
        "<!DOCTYPE html><html><head><meta charset='utf-8'><title>Cannot display this page</title></head>"
        "<body style='font-family:Tahoma,Segoe UI,sans-serif;background:#ECE9D8;margin:0;padding:2rem'>"
        "<h3 style='color:#003399;margin:0 0 8px'>The page cannot be displayed</h3>"
        "<p style='color:#333'>This website refuses to be shown inside the Lucky Card IE 6 window "
        "(it sends a frame-busting header). Opening it in your real browser tab:</p>"
        "<p><button onclick='window.open(\"" + esc.replace('\\', '\\\\') + "\")' "
        "style='background:linear-gradient(180deg,#fff,#ECE9D8);border:1px solid #7F9DB9;"
        "border-radius:3px;padding:6px 18px;font:13px Tahoma,sans-serif;cursor:pointer'>"
        "Open in a new tab</button></p>"
        "<p style='color:#888;font-size:11px'>hicard.world · Lucky Card IE 6 · " + esc + "</p>"
        "</body></html>"
    )


@router.get("/ie/browse")
async def ie_browse(u: str = Query(...)):
    if not _allowed(u):
        raise HTTPException(400, "Lucky IE only browses bing.com / baidu.com through the proxy.")
    try:
        async with httpx.AsyncClient(
            follow_redirects=True,
            timeout=18,
            headers={"User-Agent": UA, "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.5"},
        ) as client:
            r = await client.get(u)
    except Exception as e:  # network / DNS / TLS failures
        raise HTTPException(502, "代理拉取失败: " + str(e)[:200])

    final = str(r.url)
    if not _allowed(final):
        return HTMLResponse(_interstitial(final))

    ct = (r.headers.get("content-type") or "application/octet-stream").split(";")[0].strip().lower()
    headers = {"Cache-Control": "no-store"}
    if "html" not in ct:
        return Response(content=r.content, media_type=ct or "application/octet-stream", headers=headers)
    return HTMLResponse(_rewrite(r.text), headers=headers)
