import json, sys, time
sys.path.insert(0, r"C:\Tools\HeadroomSwitcher")
import app

api = app.Api()

# reset phase: turn off anything left enabled, clear state
for a in app.AGENTS:
    if a["detect"]().get("enabled"):
        r = api.toggle(a["id"], False)
        print("reset", a["id"], "->", r["ok"])
app.STATE_FILE.unlink(missing_ok=True)

def show(tag):
    s = app.snapshot()
    print(f"-- {tag}: proxy={s['proxy']}")
    for a in s["agents"]:
        print(f"   {a['id']}: installed={a['installed']} enabled={a['enabled']}")

show("initial")
assert not any(a["enabled"] for a in app.snapshot()["agents"])

r = api.toggle("claude", True)
print("claude ON ->", r["ok"], r.get("error", ""))
assert r["ok"]
s = api.get_state()
assert next(a for a in s["agents"] if a["id"]=="claude")["enabled"] is True
assert s["proxy"]["running"], "proxy should be running"
data = json.loads(app.CLAUDE_SETTINGS.read_text(encoding="utf-8"))
assert data["env"]["ANTHROPIC_BASE_URL"] == app.PROXY_URL
print("   saved upstream =", app.claude_upstream())

r = api.toggle("codex", True)
print("codex ON ->", r["ok"], r.get("error", ""))
assert r["ok"]
text = app.CODEX_CONFIG.read_text(encoding="utf-8")
assert 'openai_base_url = "http://127.0.0.1:8787/p/Desktop/v1"' in text

r = api.toggle("opencode", True)
print("opencode ON ->", r["ok"], r.get("error", ""))
assert r["ok"]
j = json.loads(app.OPENCODE_CONFIG.read_text(encoding="utf-8"))
assert "headroom" in j["provider"]

for aid in ("claude", "codex", "opencode"):
    r = api.toggle(aid, False)
    print(aid, "OFF ->", r["ok"], r.get("error", ""))
    assert r["ok"]
time.sleep(1)
s = api.get_state()
assert not any(a["enabled"] for a in s["agents"])
assert not s["proxy"]["running"], "proxy should have stopped"
data = json.loads(app.CLAUDE_SETTINGS.read_text(encoding="utf-8"))
assert data["env"].get("ANTHROPIC_BASE_URL") == "https://api.deepseek.com/anthropic"
assert "openai_base_url" not in app.CODEX_CONFIG.read_text(encoding="utf-8")
assert "headroom" not in json.loads(app.OPENCODE_CONFIG.read_text(encoding="utf-8"))["provider"]
print("ALL LOGIC TESTS PASSED")

