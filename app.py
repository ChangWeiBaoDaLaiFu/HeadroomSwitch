# -*- coding: utf-8 -*-
"""HeadroomSwitch - a CC Switch style GUI manager for Headroom (https://github.com/headroomlabs-ai/headroom).

Scans local AI coding agents (Claude Code / Codex / OpenCode), and toggles
per-agent Headroom proxy integration on/off with automatic config backup and
restore. Manages the headroom proxy process lifecycle automatically.

Not affiliated with headroomlabs-ai. Requires the open-source `headroom` CLI.
"""
import json
import os
import subprocess
import sys
import threading
import time
import urllib.parse
import webbrowser
from pathlib import Path

import webview

HOME = Path.home()
STATE_DIR = HOME / ".headroom-switcher"
STATE_FILE = STATE_DIR / "state.json"
CONFIG_FILE = STATE_DIR / "config.json"
SAVINGS_FILE = HOME / ".headroom" / "proxy_savings.json"

CLAUDE_SETTINGS = HOME / ".claude" / "settings.json"
CODEX_CONFIG = HOME / ".codex" / "config.toml"
OPENCODE_CONFIG = HOME / ".config" / "opencode" / "opencode.json"
ZCODE_CONFIG = HOME / ".zcode" / "v2" / "config.json"
CURSOR_DIR = HOME / ".cursor"

ZAI_ANTHROPIC_DEFAULT = "https://api.z.ai/api/anthropic"

DEFAULT_CONFIG = {
    "port": 8787,
    "network_proxy": "auto",  # "auto" (follow system proxy) | "direct" | "http://host:port"
    "headroom_path": "",      # optional override of the headroom CLI path
    "autostart": False,       # launch this tool at Windows logon
}

APP_NAME = "HeadroomSwitch"
RUN_KEY = r"Software\Microsoft\Windows\CurrentVersion\Run"

APP_VERSION = "1.2.0"
REPO_URL = "https://github.com/ChangWeiBaoDaLaiFu/HeadroomSwitch"


def load_config():
    cfg = dict(DEFAULT_CONFIG)
    try:
        cfg.update(json.loads(CONFIG_FILE.read_text(encoding="utf-8")))
    except Exception:
        pass
    return cfg


CONFIG = load_config()
PORT = int(CONFIG.get("port", 8787))
PROXY_URL = f"http://127.0.0.1:{PORT}"
HEADROOM_EXE = Path(CONFIG.get("headroom_path") or (HOME / ".local" / "bin" / "headroom.exe"))

_LOCK = threading.Lock()

DETACHED = 0x00000008 | 0x00000200   # DETACHED_PROCESS | CREATE_NEW_PROCESS_GROUP
NO_WINDOW = 0x08000000               # CREATE_NO_WINDOW


# ---------------------------------------------------------------- state ----
def load_state():
    try:
        return json.loads(STATE_FILE.read_text(encoding="utf-8"))
    except Exception:
        return {}


def save_state(state):
    STATE_DIR.mkdir(parents=True, exist_ok=True)
    STATE_FILE.write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8")


# ------------------------------------------------------- system proxy ----
def detect_system_proxy():
    """Best-effort read of the Windows per-user proxy setting."""
    try:
        import winreg
        key = winreg.OpenKey(winreg.HKEY_CURRENT_USER,
                             r"Software\Microsoft\Windows\CurrentVersion\Internet Settings")
        enabled, _ = winreg.QueryValueEx(key, "ProxyEnable")
        if not enabled:
            return None
        server, _ = winreg.QueryValueEx(key, "ProxyServer")
        if not server:
            return None
        if "=" not in server:
            return "http://" + server
        for part in server.split(";"):
            scheme, _, addr = part.partition("=")
            if scheme in ("http", "https") and addr:
                return "http://" + addr
    except Exception:
        pass
    return None


def apply_proxy_env(env):
    """Fill HTTP(S)_PROXY in `env` according to the network_proxy setting."""
    mode = str(CONFIG.get("network_proxy", "auto")).strip() or "auto"
    addr = None
    if mode == "auto":
        addr = detect_system_proxy()
    elif mode != "direct" and mode.lower().startswith("http"):
        addr = mode
    for k in ("HTTP_PROXY", "HTTPS_PROXY"):
        if addr:
            env[k] = addr
        else:
            env.pop(k, None)


# ------------------------------------------------------- autostart ----
def _autostart_command():
    if getattr(sys, "frozen", False):
        return f'"{sys.executable}"'
    return f'"{sys.executable}" "{Path(__file__).resolve()}"'


def autostart_enabled():
    try:
        import winreg
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, RUN_KEY) as k:
            winreg.QueryValueEx(k, APP_NAME)
        return True
    except Exception:
        return False


def set_autostart(on):
    import winreg
    with winreg.CreateKey(winreg.HKEY_CURRENT_USER, RUN_KEY) as k:
        if on:
            winreg.SetValueEx(k, APP_NAME, 0, winreg.REG_SZ, _autostart_command())
        else:
            try:
                winreg.DeleteValue(k, APP_NAME)
            except FileNotFoundError:
                pass


# ------------------------------------------------------------- claude ----
def claude_detect():
    if not CLAUDE_SETTINGS.exists():
        return {"installed": False}
    try:
        data = json.loads(CLAUDE_SETTINGS.read_text(encoding="utf-8"))
    except Exception:
        return {"installed": False}
    env = data.get("env") or {}
    base = env.get("ANTHROPIC_BASE_URL", "")
    enabled = base == PROXY_URL
    detail = "经 Headroom 代理压缩" if enabled else ("直连 " + base if base else "直连官方 API")
    return {"installed": True, "enabled": enabled, "detail": detail,
            "path": str(CLAUDE_SETTINGS)}


def claude_set(on):
    data = json.loads(CLAUDE_SETTINGS.read_text(encoding="utf-8"))
    env = data.setdefault("env", {})
    state = load_state()
    orig = (state.get("agents", {}).get("claude", {}) or {}).get("original_base_url")
    if on:
        if env.get("ANTHROPIC_BASE_URL") != PROXY_URL:
            cur = env.get("ANTHROPIC_BASE_URL", "")
            ent = state.setdefault("agents", {}).setdefault("claude", {})
            ent["original_base_url"] = cur
            save_state(state)
            env["ANTHROPIC_BASE_URL"] = PROXY_URL
            CLAUDE_SETTINGS.write_text(json.dumps(data, ensure_ascii=False, indent=2),
                                       encoding="utf-8")
    else:
        if env.get("ANTHROPIC_BASE_URL") == PROXY_URL:
            env["ANTHROPIC_BASE_URL"] = orig or ""
            if not env["ANTHROPIC_BASE_URL"]:
                env.pop("ANTHROPIC_BASE_URL", None)
            CLAUDE_SETTINGS.write_text(json.dumps(data, ensure_ascii=False, indent=2),
                                       encoding="utf-8")
        agents = state.get("agents", {})
        if "claude" in agents:
            agents.pop("claude")
            save_state(state)


def claude_upstream():
    state = load_state()
    ent = (state.get("agents", {}).get("claude", {}) or {})
    return ent.get("original_base_url") or None


# --------------------------------------------------------------- codex ----
def codex_proxy_value():
    return PROXY_URL + "/p/Desktop/v1"


def codex_detect():
    if not CODEX_CONFIG.exists():
        return {"installed": False}
    text = CODEX_CONFIG.read_text(encoding="utf-8", errors="replace")
    enabled = False
    for line in text.splitlines():
        s = line.strip()
        if s.startswith("openai_base_url") and f"127.0.0.1:{PORT}" in s:
            enabled = True
            break
    detail = "经 Headroom 代理压缩" if enabled else "直连 ChatGPT 后端"
    return {"installed": True, "enabled": enabled, "detail": detail,
            "path": str(CODEX_CONFIG)}


def codex_set(on):
    lines = CODEX_CONFIG.read_text(encoding="utf-8", errors="replace").splitlines()
    key = "openai_base_url"
    lines = [l for l in lines if not l.strip().startswith(key)]
    if on:
        new_line = f'{key} = "{codex_proxy_value()}"'
        insert_at = len(lines)
        for i, l in enumerate(lines):
            if l.strip().startswith("["):
                insert_at = i
                break
        lines.insert(insert_at, new_line)
    CODEX_CONFIG.write_text("\n".join(lines).rstrip("\n") + "\n", encoding="utf-8")


# ------------------------------------------------------------ opencode ----
def opencode_detect():
    if not OPENCODE_CONFIG.exists():
        return {"installed": False}
    try:
        data = json.loads(OPENCODE_CONFIG.read_text(encoding="utf-8"))
    except Exception:
        return {"installed": False}
    providers = data.get("provider") or {}
    enabled = any(p.startswith("headroom") for p in providers)
    detail = "headroom-* 全部模型经代理压缩" if enabled else "直连各模型上游"
    return {"installed": True, "enabled": enabled, "detail": detail,
            "path": str(OPENCODE_CONFIG)}


def opencode_set(on):
    data = json.loads(OPENCODE_CONFIG.read_text(encoding="utf-8"))
    providers = data.setdefault("provider", {})
    if on:
        for pid, prov in list(providers.items()):
            if pid.startswith("headroom"):
                continue
            opts = prov.get("options") or {}
            src_base = opts.get("baseURL") or ""
            u = urllib.parse.urlparse(src_base)
            origin = f"{u.scheme}://{u.netloc}" if u.scheme and u.netloc else src_base
            models = {}
            for mid, m in (prov.get("models") or {}).items():
                nm = dict(m or {})
                nm["name"] = (nm.get("name") or mid) + " (Headroom)"
                models[mid] = nm
            providers["headroom-" + pid] = {
                "models": models,
                "name": (prov.get("name") or pid) + " via Headroom",
                "npm": "@ai-sdk/openai-compatible",
                "options": {
                    "apiKey": opts.get("apiKey", ""),
                    "baseURL": PROXY_URL + "/v1",
                    "headers": {"x-headroom-base-url": origin},
                },
            }
    else:
        for pid in [p for p in providers if p.startswith("headroom")]:
            providers.pop(pid)
    OPENCODE_CONFIG.write_text(json.dumps(data, ensure_ascii=False, indent=2),
                               encoding="utf-8")


def opencode_default_upstream():
    """Origin of the first mirrored headroom provider, as proxy fallback."""
    try:
        data = json.loads(OPENCODE_CONFIG.read_text(encoding="utf-8"))
        for pid, prov in (data.get("provider") or {}).items():
            if pid.startswith("headroom"):
                h = ((prov.get("options") or {}).get("headers") or {}).get(
                    "x-headroom-base-url")
                if h:
                    return h
    except Exception:
        pass
    return None


# ------------------------------------------------- zcode / cursor ----
def zcode_detect():
    if not ZCODE_CONFIG.exists():
        return {"installed": False}
    try:
        data = json.loads(ZCODE_CONFIG.read_text(encoding="utf-8"))
    except Exception:
        return {"installed": False}
    integrated = False
    for p in (data.get("provider") or {}).values():
        if str((p.get("options") or {}).get("baseURL", "")).startswith(
                f"http://127.0.0.1:{PORT}"):
            integrated = True
            break
    detail = ("已接入（自定义供应商指向本地代理）" if integrated
              else "手动接入：按指引把供应商 BaseURL 填为本地代理")
    return {"installed": True, "enabled": integrated, "manual": True,
            "detail": detail, "path": str(ZCODE_CONFIG)}


def zcode_manual_upstream():
    state = load_state()
    return (state.get("agents", {}).get("zcode", {}) or {}).get("upstream") or None


def cursor_detect():
    if not CURSOR_DIR.exists():
        return {"installed": False}
    detail = "手动接入：在 Cursor 设置中把 Override Base URL 填为本地代理"
    return {"installed": True, "enabled": False, "manual": True,
            "detail": detail, "path": str(CURSOR_DIR)}


# ---------------------------------------------------------------- proxy ----
def proxy_alive():
    try:
        import socket
        with socket.create_connection(("127.0.0.1", PORT), timeout=1.5):
            return True
    except Exception:
        return False


def spawn_proxy():
    env = os.environ.copy()
    # mirror index only helps users behind GFW; harmless elsewhere
    env["HF_ENDPOINT"] = "https://hf-mirror.com"
    apply_proxy_env(env)
    up = claude_upstream() or zcode_manual_upstream()
    if up:
        env["ANTHROPIC_TARGET_API_URL"] = up
    else:
        env.pop("ANTHROPIC_TARGET_API_URL", None)
    if opencode_detect().get("enabled"):
        upstream = opencode_default_upstream()
        if upstream:
            env["OPENAI_TARGET_API_URL"] = upstream
        else:
            env.pop("OPENAI_TARGET_API_URL", None)
    else:
        env.pop("OPENAI_TARGET_API_URL", None)
    env.pop("ANTHROPIC_BASE_URL", None)
    env.pop("OPENAI_BASE_URL", None)
    # CREATE_NO_WINDOW (not DETACHED): the uv-tool trampoline spawns a child
    # python that would otherwise create a visible console; with a hidden
    # console inherited by the whole tree no window ever flashes, and the
    # proxy outlives this app.
    proc = subprocess.Popen(
        [str(HEADROOM_EXE), "proxy", "--port", str(PORT)],
        creationflags=NO_WINDOW, stdin=subprocess.DEVNULL,
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, env=env)
    state = load_state()
    state["proxy_pid"] = proc.pid
    save_state(state)
    for _ in range(60):
        if proxy_alive():
            return True
        time.sleep(0.5)
    return False


def stop_proxy():
    state = load_state()
    pid = state.get("proxy_pid")
    if pid:
        subprocess.run(["taskkill", "/PID", str(pid), "/F", "/T"],
                       capture_output=True, creationflags=NO_WINDOW)
        state.pop("proxy_pid", None)
        save_state(state)


def sync_proxy():
    any_on = any(d.get("enabled") for d in
                 (claude_detect(), codex_detect(), opencode_detect(),
                  zcode_detect()))
    if not HEADROOM_EXE.exists():
        return {"ok": False, "error": "未找到 headroom.exe"}
    our_pid = load_state().get("proxy_pid")
    running = proxy_alive()
    if any_on:
        if running and our_pid:
            stop_proxy()
            running = False
        if not running:
            ok = spawn_proxy()
            if not ok:
                return {"ok": False, "error": "代理启动超时"}
        return {"ok": True}
    else:
        if running and our_pid:
            stop_proxy()
        return {"ok": True}


def read_savings():
    try:
        lt = json.loads(SAVINGS_FILE.read_text(encoding="utf-8")).get("lifetime") or {}
        return {"tokens": int(lt.get("tokens_saved") or 0),
                "usd": float(lt.get("compression_savings_usd") or 0)}
    except Exception:
        return {"tokens": 0, "usd": 0.0}


# ----------------------------------------------------------- agents ----
AGENTS = [
    {"id": "claude", "name": "Claude Code", "icon": "C", "color": "#d97757",
     "detect": claude_detect, "set": claude_set},
    {"id": "codex", "name": "Codex", "icon": "X", "color": "#10a37f",
     "detect": codex_detect, "set": codex_set},
    {"id": "opencode", "name": "OpenCode", "icon": "O", "color": "#5b6cff",
     "detect": opencode_detect, "set": opencode_set},
    {"id": "zcode", "name": "ZCode", "icon": "Z", "color": "#7c3aed",
     "detect": zcode_detect, "set": lambda on: None},
    {"id": "cursor", "name": "Cursor", "icon": "U", "color": "#0ea5e9",
     "detect": cursor_detect, "set": lambda on: None},
]

LOCALAPPDATA = os.environ.get("LOCALAPPDATA", "")


def _find_exe(candidates):
    for c in candidates:
        if c and Path(c).exists():
            return c
    return ""


RESTARTS = {
    "codex": {"procs": ["ChatGPT", "Codex"],
              "launch": "shell:AppsFolder\\OpenAI.Codex_2p2nqsd0c76g0!App",
              "kind": "shell", "label": "Codex 桌面版"},
    "opencode": {"procs": ["OpenCode"],
                 "launch": LOCALAPPDATA + r"\Programs\@opencode-aidesktop\OpenCode.exe",
                 "kind": "exe", "label": "OpenCode 桌面版"},
    "zcode": {"procs": ["ZCode"],
              "launch": _find_exe([
                  r"D:\Program Files\ZCode\ZCode.exe",
                  r"C:\Program Files\ZCode\ZCode.exe",
                  LOCALAPPDATA + r"\Programs\ZCode\ZCode.exe"]),
              "kind": "exe", "label": "ZCode 桌面版"},
    "cursor": {"procs": ["Cursor"],
               "launch": _find_exe([
                   r"D:\Program Files\cursor\Cursor.exe",
                   LOCALAPPDATA + r"\Programs\cursor\Cursor.exe",
                   r"C:\Program Files\cursor\Cursor.exe"]),
               "kind": "exe", "label": "Cursor"},
}


def _proc_running(name):
    try:
        r = subprocess.run(["tasklist", "/FI", f"IMAGENAME eq {name}.exe"],
                           capture_output=True, text=True, creationflags=NO_WINDOW)
        return name.lower() in (r.stdout or "").lower()
    except Exception:
        return False


def snapshot():
    agents = []
    for a in AGENTS:
        d = a["detect"]()
        d.update({"id": a["id"], "name": a["name"], "icon": a["icon"],
                  "color": a["color"]})
        d.setdefault("installed", False)
        d.setdefault("enabled", False)
        d.setdefault("detail", "未检测到")
        d["manual"] = bool(d.get("manual"))
        d["has_restart"] = d["id"] in RESTARTS and (
            RESTARTS[d["id"]]["kind"] == "shell"
            or bool(RESTARTS[d["id"]]["launch"]))
        agents.append(d)
    our_pid = load_state().get("proxy_pid")
    alive = proxy_alive()
    if alive and our_pid:
        proxy = {"running": True, "managed": True, "pid": our_pid}
    elif alive:
        proxy = {"running": True, "managed": False, "pid": None}
    else:
        proxy = {"running": False, "managed": False, "pid": None}
    return {"agents": agents, "proxy": proxy,
            "headroom_installed": HEADROOM_EXE.exists(),
            "savings": read_savings()}


class Api:
    def get_state(self):
        with _LOCK:
            return snapshot()

    def toggle(self, agent_id, enable):
        with _LOCK:
            try:
                a = next(x for x in AGENTS if x["id"] == agent_id)
                det = a["detect"]()
                if not det.get("installed"):
                    return {"ok": False, "error": "未检测到该 Agent"}
                a["set"](bool(enable))
                r = sync_proxy()
                if not r.get("ok"):
                    return r
                return {"ok": True, "state": snapshot()}
            except Exception as e:
                return {"ok": False, "error": str(e)}

    def restart(self, agent_id):
        with _LOCK:
            info = RESTARTS.get(agent_id)
            if not info:
                return {"ok": False,
                        "error": "该 Agent 为 CLI，配置对新会话自动生效，无需重启"}
            was = any(_proc_running(pn) for pn in info["procs"])
            for pn in info["procs"]:
                subprocess.run(["taskkill", "/IM", pn + ".exe", "/F", "/T"],
                               capture_output=True, creationflags=NO_WINDOW)
            time.sleep(1.5)
            if not was:
                return {"ok": True, "message": info["label"] + " 未在运行，无需重启"}
            try:
                if info["kind"] == "shell":
                    os.startfile(info["launch"])
                else:
                    subprocess.Popen([info["launch"]], creationflags=DETACHED)
                return {"ok": True, "message": info["label"] + " 已重启"}
            except Exception as e:
                return {"ok": False, "error": "重启失败: " + str(e)}

    def start_proxy(self):
        with _LOCK:
            if not HEADROOM_EXE.exists():
                return {"ok": False, "error": "未找到 headroom.exe"}
            if proxy_alive():
                return {"ok": True, "message": "代理已在运行"}
            if not spawn_proxy():
                return {"ok": False, "error": "代理启动超时，请检查 headroom 安装"}
            return {"ok": True, "message": "代理已启动"}

    def open_dashboard(self):
        webbrowser.open(f"http://127.0.0.1:{PORT}/dashboard")
        return {"ok": True}

    def open_url(self, url):
        if url.startswith("http://") or url.startswith("https://"):
            webbrowser.open(url)
        return {"ok": True}

    def set_zcode_upstream(self, url):
        with _LOCK:
            if not url.startswith("http"):
                return {"ok": False, "error": "无效地址"}
            state = load_state()
            state.setdefault("agents", {}).setdefault("zcode", {})["upstream"] = url
            save_state(state)
            if proxy_alive() and load_state().get("proxy_pid"):
                stop_proxy()
            sync_proxy()
            return {"ok": True, "message": "上游已切换为 " + url}

    def get_guide(self, agent_id):
        openai_url = PROXY_URL + "/v1"
        anthropic_url = PROXY_URL
        if agent_id == "cursor":
            html = (
                "<p><b>前提：</b>代理状态灯为绿色（未运行请先点「启动代理」）。</p>"
                "<p><b>1.</b> 打开 Cursor 设置（Ctrl+Shift+J）→ <b>Models</b> 页签。</p>"
                "<p><b>2.</b> 在 <b>OpenAI API Key</b> 区域：</p>"
                f"<p>· 勾选 <b>Override OpenAI Base URL</b>，填 <code>{openai_url}</code></p>"
                "<p>· API Key 填你自己的任意 OpenAI 兼容 Key</p>"
                "<p><b>3.</b> 勾选需要的模型，点击 Verify。</p>"
                "<p class='mnote'>Anthropic 模型如需走代理：把 Anthropic Base URL 填为 "
                f"<code>{anthropic_url}</code>（新版 Cursor 支持）。Cursor 不支持自定义请求头，"
                "上游请在本工具「ZCode/Cursor 上游」中选择或默认。</p>")
            return {"ok": True, "title": "Cursor 接入指引", "html": html}
        if agent_id == "zcode":
            cur = zcode_manual_upstream() or ZAI_ANTHROPIC_DEFAULT
            html = (
                "<p><b>前提：</b>代理状态灯为绿色。</p>"
                "<p><b>1.</b> 打开 ZCode 设置 → 模型服务 / 供应商。</p>"
                "<p><b>2.</b> 新建/编辑自定义供应商（类型 <b>anthropic</b>）：</p>"
                f"<p>· BaseURL 填 <code>{anthropic_url}</code></p>"
                "<p>· API Key 填你的智谱 Key</p>"
                "<p><b>3.</b> 选择该供应商后即可使用（工具会自动识别为已接入）。</p>"
                "<p class='mnote'>上游转发地址当前为：<code>" + cur + "</code></p>"
                "<div class='mrow' style='justify-content:flex-start'>"
                "<button class='mini' onclick=\"pywebview.api.set_zcode_upstream('https://open.bigmodel.cn/api/anthropic').then(()=>toast('上游已切换 智谱国内'))\">上游：智谱国内 bigmodel</button>"
                "<button class='mini' onclick=\"pywebview.api.set_zcode_upstream('https://api.z.ai/api/anthropic').then(()=>toast('上游已切换 z.ai 国际'))\">上游：z.ai 国际</button>"
                "</div>")
            return {"ok": True, "title": "ZCode 接入指引", "html": html}
        return {"ok": False, "error": "该 Agent 无需指引"}

    def get_config(self):
        return {"port": PORT, "network_proxy": CONFIG.get("network_proxy", "auto"),
                "autostart": autostart_enabled()}

    def save_config(self, cfg):
        with _LOCK:
            global PORT, PROXY_URL, HEADROOM_EXE
            try:
                port = int(cfg.get("port", PORT))
            except Exception:
                return {"ok": False, "error": "端口必须是数字"}
            if not (1 <= port <= 65535):
                return {"ok": False, "error": "端口范围 1-65535"}
            if port != PORT and any(d.get("enabled") for d in
                                    (claude_detect(), codex_detect(), opencode_detect())):
                return {"ok": False, "error": "有开关处于开启状态，请先全部关闭再改端口"}
            mode = str(cfg.get("network_proxy", "auto")).strip() or "auto"
            if mode not in ("auto", "direct") and not mode.lower().startswith("http"):
                return {"ok": False, "error": "网络代理格式应为 auto / direct / http://地址"}
            hp = str(cfg.get("headroom_path", "") or "").strip()
            CONFIG.update({"port": port, "network_proxy": mode, "headroom_path": hp})
            if "autostart" in cfg:
                want = bool(cfg["autostart"])
                if want != autostart_enabled():
                    set_autostart(want)
                CONFIG["autostart"] = want
            STATE_DIR.mkdir(parents=True, exist_ok=True)
            CONFIG_FILE.write_text(json.dumps(CONFIG, ensure_ascii=False, indent=2),
                                   encoding="utf-8")
            PORT, PROXY_URL = port, f"http://127.0.0.1:{port}"
            HEADROOM_EXE = Path(hp) if hp else (HOME / ".local" / "bin" / "headroom.exe")
            our_pid = load_state().get("proxy_pid")
            if our_pid:
                stop_proxy()  # restart with new settings on next toggle/sync
            sync_proxy()
            return {"ok": True, "state": snapshot()}


# ----------------------------------------------------------------- tray ----
def _res(name):
    base = getattr(sys, "_MEIPASS", os.path.dirname(os.path.abspath(__file__)))
    return os.path.join(base, name)


_tray_icon = None
_tray_notified = False


def _tray_on_show(icon=None, item=None):
    win = webview.windows[0] if webview.windows else None
    if win:
        try:
            win.restore()
        except Exception:
            pass
        win.show()


def _tray_on_quit(icon=None, item=None):
    try:
        if icon:
            icon.stop()
    except Exception:
        pass
    os._exit(0)


def start_tray():
    global _tray_icon
    try:
        import pystray
        from PIL import Image as PILImage
        img = PILImage.open(_res("icon.ico"))
        menu = pystray.Menu(
            pystray.MenuItem("显示窗口", _tray_on_show, default=True),
            pystray.Menu.SEPARATOR,
            pystray.MenuItem("退出", _tray_on_quit),
        )
        _tray_icon = pystray.Icon("HeadroomSwitch", img, "Headroom Agent 管理", menu)
        threading.Thread(target=_tray_icon.run, daemon=True).start()
    except Exception:
        _tray_icon = None


# ----------------------------------------------------------------- gui ----
HTML = r"""<!DOCTYPE html>
<html lang="zh">
<head>
<meta charset="utf-8">
<style>
:root{--bg:#f3f4f6;--card:#fff;--text:#1f2328;--sub:#6b7280;--line:#e5e7eb;
--accent:#5b6cff;--green:#22c55e;--red:#ef4444}
*{margin:0;padding:0;box-sizing:border-box;font-family:"Segoe UI","Microsoft YaHei",sans-serif}
body{background:var(--bg);color:var(--text);height:100vh;display:flex;flex-direction:column;
overflow:hidden;user-select:none}
header{padding:18px 22px 14px;display:flex;align-items:center;justify-content:space-between}
header h1{font-size:17px;font-weight:600;display:flex;align-items:center;gap:9px}
.logo{width:26px;height:26px;border-radius:8px;background:linear-gradient(135deg,#5b6cff,#8b5cf6);
color:#fff;font-size:14px;font-weight:700;display:flex;align-items:center;justify-content:center}
.hright{display:flex;align-items:center;gap:8px}
.pill{display:flex;align-items:center;gap:7px;font-size:12px;padding:5px 12px;border-radius:99px;
background:#fff;border:1px solid var(--line);color:var(--sub)}
.dot{width:8px;height:8px;border-radius:50%;background:#9ca3af}
.dot.on{background:var(--green);box-shadow:0 0 0 3px rgba(34,197,94,.18)}
.dot.ext{background:#f59e0b;box-shadow:0 0 0 3px rgba(245,158,11,.18)}
#banner{margin:0 22px 10px;padding:10px 14px;border-radius:10px;font-size:12.5px;
background:#fef3c7;border:1px solid #fde68a;color:#92400e;display:none}
#banner code{background:rgba(0,0,0,.06);padding:1px 6px;border-radius:5px}
main{flex:1;overflow-y:auto;padding:4px 22px 10px;display:flex;flex-direction:column;gap:12px}
.card{background:var(--card);border:1px solid var(--line);border-radius:14px;padding:16px 18px;
display:flex;align-items:center;gap:14px;box-shadow:0 1px 2px rgba(0,0,0,.04);transition:box-shadow .15s}
.card:hover{box-shadow:0 3px 10px rgba(0,0,0,.07)}
.card.off-inst{opacity:.55}
.avatar{width:42px;height:42px;border-radius:11px;color:#fff;font-size:18px;font-weight:700;
display:flex;align-items:center;justify-content:center;flex-shrink:0}
.meta{flex:1;min-width:0}
.meta .name{font-size:14.5px;font-weight:600}
.meta .detail{font-size:12px;color:var(--sub);margin-top:3px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
.badge{display:inline-block;font-size:10.5px;padding:1px 7px;border-radius:99px;margin-left:8px;
vertical-align:1px;background:rgba(34,197,94,.12);color:#15803d;font-weight:600}
.badge.off{background:#f3f4f6;color:var(--sub)}
.switch{position:relative;width:46px;height:26px;flex-shrink:0;cursor:pointer}
.switch input{display:none}
.slider{position:absolute;inset:0;background:#d1d5db;border-radius:99px;transition:.2s}
.slider:before{content:"";position:absolute;width:20px;height:20px;border-radius:50%;background:#fff;
top:3px;left:3px;transition:.2s;box-shadow:0 1px 3px rgba(0,0,0,.25)}
input:checked+.slider{background:var(--green)}
input:checked+.slider:before{transform:translateX(20px)}
.switch.locked{opacity:.5;pointer-events:none}
.mini{border:1px solid var(--line);background:#fff;border-radius:8px;padding:5px 11px;
font-size:11.5px;color:var(--sub);cursor:pointer;flex-shrink:0}
.mini:hover{border-color:var(--accent);color:var(--accent)}
.mini:disabled{opacity:.5;cursor:default}
.spin{display:inline-block;width:13px;height:13px;border:2px solid #d1d5db;
border-top-color:var(--accent);border-radius:50%;animation:sp .7s linear infinite;
vertical-align:-2px}
@keyframes sp{to{transform:rotate(360deg)}}
.busytext{font-size:11.5px;color:var(--sub);flex-shrink:0;white-space:nowrap}
footer{padding:12px 22px 16px;display:flex;align-items:center;gap:10px;
font-size:12px;color:var(--sub)}
#savetext{flex:1;color:#15803d;font-weight:600}
.linkbtn{border:1px solid var(--line);background:#fff;border-radius:8px;padding:6px 14px;
font-size:12px;color:var(--text);cursor:pointer}
.linkbtn:hover{border-color:var(--accent);color:var(--accent)}
#toast{position:fixed;left:50%;bottom:56px;transform:translateX(-50%) translateY(20px);
background:#1f2328;color:#fff;font-size:12.5px;padding:9px 18px;border-radius:10px;
opacity:0;transition:.25s;pointer-events:none;max-width:80%}
#toast.show{opacity:1;transform:translateX(-50%) translateY(0)}
#toast.err{background:var(--red)}
#modal{position:fixed;inset:0;background:rgba(0,0,0,.35);display:none;
align-items:center;justify-content:center;z-index:50}
#modal.open{display:flex}
.mcard{background:#fff;border-radius:14px;padding:22px 24px;width:400px;box-shadow:0 10px 40px rgba(0,0,0,.2)}
.mcard h3{font-size:15px;margin-bottom:14px}
.mcard label{display:block;font-size:12px;color:var(--sub);margin:10px 0 4px}
.mcard input,.mcard select{width:100%;border:1px solid var(--line);border-radius:8px;
padding:7px 10px;font-size:13px;outline:none}
.mcard input:focus,.mcard select:focus{border-color:var(--accent)}
.mrow{display:flex;gap:10px;justify-content:flex-end;margin-top:18px}
.mrow .primary{background:var(--accent);border:none;color:#fff;border-radius:8px;
padding:7px 18px;font-size:12.5px;cursor:pointer}
.about p{font-size:12.5px;line-height:1.7;margin-bottom:8px;color:var(--text)}
.about code{background:#f3f4f6;border:1px solid var(--line);border-radius:5px;
padding:1px 6px;font-size:11.5px;word-break:break-all}
.about a{color:var(--accent);text-decoration:none}
.mnote{font-size:11.5px;color:var(--sub)}
</style>
</head>
<body>
<header>
  <h1><span class="logo">H</span>Headroom Agent 管理</h1>
  <div class="hright">
    <div class="pill" id="proxypill"><span class="dot" id="proxydot"></span><span id="proxytext">检测中…</span></div>
    <button class="linkbtn" id="proxystart" style="display:none" onclick="onProxyStart(this)">启动代理</button>
    <button class="linkbtn" onclick="openSettings()">设置</button>
    <button class="linkbtn" onclick="openAbout()">关于</button>
  </div>
</header>
<div id="banner">未检测到 <code>headroom</code> CLI，请先安装：<code>uv tool install "headroom-ai[all]"</code> 或 <code>pip install "headroom-ai[all]"</code>（也可在设置中指定路径）</div>
<main id="cards"></main>
<footer>
  <span id="savetext"></span>
  <span>开启任一 Agent 时自动启动本地代理，全部关闭时自动停止</span>
  <button class="linkbtn" onclick="pywebview.api.open_dashboard()">节省面板</button>
</footer>
<div id="toast"></div>
<div id="modal">
  <div class="mcard" id="m_settings">
    <h3>设置</h3>
    <label>本地代理端口</label>
    <input id="cfg_port" type="number" min="1" max="65535">
    <label>网络代理（访问模型上游时使用）</label>
    <select id="cfg_mode" onchange="modeChanged()">
      <option value="auto">自动（跟随系统代理）</option>
      <option value="direct">直连</option>
      <option value="custom">自定义地址</option>
    </select>
    <input id="cfg_custom" placeholder="http://127.0.0.1:7897" style="display:none;margin-top:6px">
    <label style="display:flex;align-items:center;gap:8px;margin-top:14px;cursor:pointer;font-size:12.5px;color:var(--text)">
      <input id="cfg_autostart" type="checkbox" style="width:auto">
      开机自启动（登录后自动运行本工具并恢复代理）
    </label>
    <div class="mrow">
      <button class="linkbtn" onclick="closeModal()">取消</button>
      <button class="primary" onclick="saveCfg()">保存</button>
    </div>
  </div>
  <div class="mcard" id="m_about" style="display:none">
    <h3>关于 HeadroomSwitch</h3>
    <div class="about">
      <p><b>HeadroomSwitch v__VER__</b></p>
      <p>为 <a href="javascript:void(0)" onclick="pywebview.api.open_url('__HEADROOM_URL__')">Headroom</a> 设计的开源 GUI 管理工具：扫描本机 AI Agent，一键开关上下文压缩代理，关闭自动还原。</p>
      <p>本项目为独立社区工具，与 headroomlabs-ai 无关。</p>
      <p>项目主页：<a href="javascript:void(0)" onclick="pywebview.api.open_url('__REPO_URL__')">GitHub</a> · License: MIT</p>
    </div>
    <div class="mrow"><button class="primary" onclick="closeModal()">关闭</button></div>
  </div>
  <div class="mcard" id="m_guide" style="display:none">
    <h3 id="guide_title">接入指引</h3>
    <div class="about" id="guide_html"></div>
    <div class="mrow"><button class="primary" onclick="closeModal()">关闭</button></div>
  </div>
</div>
<script>
let busy={};
function toast(msg,err){const t=document.getElementById('toast');t.textContent=msg;
t.className=err?'show err':'show';setTimeout(()=>t.className='',2600);}
function card(a){
  const anyBusy=Object.keys(busy).length>0;
  const me=busy[a.id];
  const dis=!a.installed||anyBusy||a.manual?'locked':'';
  const busyHtml=me?`<span class="busytext"><span class="spin"></span> ${me}</span>`:'';
  const guideBtn=a.installed&&a.manual?`<button class="mini" title="查看接入步骤" onclick="openGuide('${a.id}')">接入指引</button>`:'';
  const sw=a.manual?'':`<label class="switch ${dis}" title="${a.path||''}">
      <input type="checkbox" ${a.enabled?'checked':''} ${a.installed?'':'disabled'}
        onchange="onToggle('${a.id}',this)">
      <span class="slider"></span>
    </label>`;
  return `<div class="card ${a.installed?'':'off-inst'}">
    <div class="avatar" style="background:${a.color}">${a.icon}</div>
    <div class="meta">
      <div class="name">${a.name}
        <span class="badge ${a.enabled?'':'off'}">${a.installed?(a.enabled?'已接入Headroom':'未接入'):'未检测到'}</span>
      </div>
      <div class="detail">${a.detail||''}</div>
    </div>
    ${a.installed&&a.has_restart?`<button class="mini" title="重启应用以加载新配置" onclick="onRestart('${a.id}','${a.name}',this)">重启 ${a.name}</button>`:''}
    ${guideBtn}
    ${busyHtml}
    ${sw}
  </div>`;
}
function fmt(n){return n.toLocaleString('en-US');}
async function refresh(){
  const s=await pywebview.api.get_state();
  document.getElementById('cards').innerHTML=s.agents.map(card).join('');
  document.getElementById('banner').style.display=s.headroom_installed?'none':'block';
  const sv=s.savings;
  document.getElementById('savetext').textContent=
    sv.tokens>0?`累计压缩节省 ${fmt(sv.tokens)} tokens`+(sv.usd>0?` ≈ $${sv.usd.toFixed(2)}`:''):'';
  const p=s.proxy,d=document.getElementById('proxydot'),t=document.getElementById('proxytext');
  if(p.running&&p.managed){d.className='dot on';t.textContent=`代理运行中 · PID ${p.pid}`;}
  else if(p.running){d.className='dot ext';t.textContent='代理运行中（外部启动）';}
  else{d.className='dot';t.textContent='代理未运行';}
  document.getElementById('proxystart').style.display=p.running?'none':'';
}
async function onToggle(id,el){
  const want=el.checked;
  busy[id]=want?'接入中…':'还原中…';
  refresh();
  const r=await pywebview.api.toggle(id,want);
  delete busy[id];
  if(!r||!r.ok){toast((r&&r.error)||'操作失败',true);}
  else{toast(want?'已接入 Headroom':'已还原为直连');}
  refresh();
}
async function onProxyStart(btn){
  btn.disabled=true;btn.textContent='启动中…';
  const r=await pywebview.api.start_proxy();
  if(r&&r.ok){toast(r.message||'代理已启动');}else{toast((r&&r.error)||'启动失败',true);}
  btn.disabled=false;btn.textContent='启动代理';
  refresh();
}
async function onRestart(id,name,btn){
  btn.disabled=true;btn.textContent='重启中…';
  const r=await pywebview.api.restart(id);
  if(r&&r.ok){toast(r.message||'已重启');}else{toast((r&&r.error)||'重启失败',true);}
  btn.disabled=false;btn.textContent='重启 '+name;
  refresh();
}
function closeModal(){document.getElementById('modal').classList.remove('open');}
function openAbout(){
  document.getElementById('m_settings').style.display='none';
  document.getElementById('m_guide').style.display='none';
  document.getElementById('m_about').style.display='block';
  document.getElementById('modal').classList.add('open');
}
async function openGuide(id){
  const g=await pywebview.api.get_guide(id);
  if(!g||!g.ok){toast((g&&g.error)||'无指引',true);return;}
  document.getElementById('m_settings').style.display='none';
  document.getElementById('m_about').style.display='none';
  document.getElementById('m_guide').style.display='block';
  document.getElementById('guide_title').textContent=g.title;
  document.getElementById('guide_html').innerHTML=g.html;
  document.getElementById('modal').classList.add('open');
}
function openSettings(){
  document.getElementById('m_about').style.display='none';
  document.getElementById('m_guide').style.display='none';
  document.getElementById('m_settings').style.display='block';
  pywebview.api.get_config().then(c=>{
    document.getElementById('cfg_port').value=c.port;
    document.getElementById('cfg_autostart').checked=!!c.autostart;
    const m=c.network_proxy;
    if(m==='auto'||m==='direct'){document.getElementById('cfg_mode').value=m;
      document.getElementById('cfg_custom').style.display='none';}
    else{document.getElementById('cfg_mode').value='custom';
      document.getElementById('cfg_custom').style.display='block';
      document.getElementById('cfg_custom').value=m;}
    document.getElementById('modal').classList.add('open');
  });
}
function modeChanged(){
  const custom=document.getElementById('cfg_mode').value==='custom';
  document.getElementById('cfg_custom').style.display=custom?'block':'none';
}
async function saveCfg(){
  let mode=document.getElementById('cfg_mode').value;
  if(mode==='custom')mode=document.getElementById('cfg_custom').value.trim()||'auto';
  const r=await pywebview.api.save_config({
    port:parseInt(document.getElementById('cfg_port').value||'8787'),
    network_proxy:mode,
    autostart:document.getElementById('cfg_autostart').checked});
  if(r&&r.ok){toast('设置已保存');closeModal();}else{toast((r&&r.error)||'保存失败',true);}
  refresh();
}
window.addEventListener('DOMContentLoaded',()=>{refresh();setInterval(refresh,2500);});
</script>
</body>
</html>"""


HTML = HTML.replace("__VER__", APP_VERSION) \
           .replace("__HEADROOM_URL__", "https://github.com/headroomlabs-ai/headroom") \
           .replace("__REPO_URL__", REPO_URL)


def _single_instance():
    import ctypes
    ctypes.windll.kernel32.CreateMutexW(None, False, "HeadroomSwitch_Mutex")
    return ctypes.windll.kernel32.GetLastError() != 183  # ERROR_ALREADY_EXISTS


def main():
    if not _single_instance():
        import ctypes
        ctypes.windll.user32.MessageBoxW(0, "HeadroomSwitch 已在运行", "提示", 0x40)
        return
    # restore proxy on startup if any agent is still enabled (e.g. after reboot)
    threading.Thread(target=sync_proxy, daemon=True).start()
    win = webview.create_window("Headroom Agent 管理", html=HTML, js_api=Api(),
                                width=760, height=560, min_size=(660, 480))

    def _on_closing():
        global _tray_notified
        try:
            win.hide()
        except Exception:
            return True
        if _tray_icon and not _tray_notified:
            _tray_notified = True
            try:
                _tray_icon.notify("程序已最小化到托盘，右下角图标可随时打开",
                                  "Headroom Agent 管理")
            except Exception:
                pass
        return False  # cancel real close: minimize to tray instead

    win.events.closing += _on_closing
    start_tray()
    webview.start()


if __name__ == "__main__":
    main()
