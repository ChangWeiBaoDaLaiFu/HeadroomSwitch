# -*- coding: utf-8 -*-
"""Fetch official favicons for each supported agent and write icons.json.

Run once (needs network + proxy for some domains):  python fetch_icons.py
Output: icons.json  {agent_id: "data:image/png;base64,..."}
"""
import base64
import io
import json
import os
import urllib.request

AGENTS = {
    "claude": "https://claude.ai",
    "codex": "https://openai.com",
    "opencode": "https://opencode.ai",
    "zcode": "https://z.ai",
    "cursor": "https://cursor.com",
    "aider": "https://aider.chat",
    "grok": "https://grok.com",
    "goose": "https://block.github.io/goose",
    "openhands": "https://all-hands.dev",
    "vibe": "https://mistral.ai",
    "omp": "https://github.com/canthar/oh-my-pi",
    "kimi": "https://www.kimi.com",
    "openclaw": "https://openclaw.ai",
    "copilot": "https://github.com/features/copilot",
    "cline": "https://cline.bot",
    "continue": "https://continue.dev",
}

proxies = {}
if os.environ.get("HTTPS_PROXY"):
    proxies["https"] = os.environ["HTTPS_PROXY"]
opener = urllib.request.build_opener(
    urllib.request.ProxyHandler(proxies),
    urllib.request.HTTPSHandler(context=__import__("ssl")._create_unverified_context()))
opener.addheaders = [("User-Agent", "Mozilla/5.0")]

out = {}
for aid, site in AGENTS.items():
    try:
        url = f"https://www.google.com/s2/favicons?domain={site}&sz=128"
        raw = opener.open(url, timeout=20).read()
        if len(raw) < 100:
            raise ValueError("too small")
        # normalize to PNG so the data URI mime is always right
        from PIL import Image
        im = Image.open(io.BytesIO(raw)).convert("RGBA")
        buf = io.BytesIO()
        im.save(buf, "PNG")
        out[aid] = "data:image/png;base64," + base64.b64encode(buf.getvalue()).decode()
        print(f"{aid:10} OK  ({len(raw)} bytes)")
    except Exception as e:
        print(f"{aid:10} SKIP ({e})")

with open("icons.json", "w", encoding="utf-8") as f:
    json.dump(out, f)
print(f"written {len(out)} icons -> icons.json")
