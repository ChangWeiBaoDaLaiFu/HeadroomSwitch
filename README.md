# HeadroomSwitch

**A Windows desktop manager for [Headroom](https://github.com/headroomlabs-ai/headroom)** — scan your locally installed AI coding agents, and toggle Headroom's context-compression proxy per agent with one click. Switch it off and the original configuration is restored automatically.

English | **[中文文档](README_zh.md)**

![screenshot](screenshots/main.png)

[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)
[![Release](https://img.shields.io/github/v/release/ChangWeiBaoDaLaiFu/HeadroomSwitch)](../../releases)

> **Why:** tool outputs — file reads, test runs, logs — quietly eat most of your token budget. [Headroom](https://github.com/headroomlabs-ai/headroom) compresses all of that locally before it reaches the LLM (same answers, 15–20% fewer tokens for coding agents, 60–95% for JSON, reversible via cache). HeadroomSwitch makes headroom a checkbox instead of a CLI ritual.

> Not affiliated with headroomlabs-ai. An independent, local-first community tool that drives the open-source [`headroom`](https://github.com/headroomlabs-ai/headroom) CLI.

## Features

- **Auto-scan** — detects 17 headroom-compatible agents at launch; only the ones you actually have are shown
- **One-click toggle** — on = routed through the local compression proxy; off = original config restored from backup, exactly
- **Zero-touch proxy** — starts automatically when any toggle is on, stops when all are off, auto-restores after reboot
- **Per-agent scope chips** — cards are labeled `CLI` / `CLI + Desktop` / `Desktop` so you always know what a switch affects
- **Launch-session buttons** — for CLI tools that integrate via environment (Aider, Goose, Kimi CLI, Grok CLI, OpenHands, Mistral Vibe, Oh My Pi, OpenClaw, GitHub Copilot CLI): one click opens a terminal running `headroom wrap <tool>` with the proxy attached
- **Guided setup** — Cursor, ZCode, Cline, Continue and VS Code Copilot get step-by-step in-app guides; ZCode includes one-click upstream switching (bigmodel CN / z.ai global)
- **OpenCode model mirroring** — every provider/model you have gets a `headroom-*` variant with per-request upstream routing; switch models freely
- **Savings widget** — live lifetime tokens (and $ estimate) saved, plus a link to headroom's dashboard
- **In-app restarts** — "Restart Codex / OpenCode / ZCode / Cursor" buttons apply config changes instantly
- **Tray-resident** — closing the window minimizes to tray; auto-start on Windows logon optional

## Supported agents

| Agent | Scope | Integration |
|---|---|---|
| Claude Code | CLI | Auto toggle (restore on off) |
| Codex | CLI + Desktop | Auto toggle |
| OpenCode | CLI + Desktop | Auto toggle + full model mirroring |
| ZCode | Desktop | Guide + upstream switcher |
| Cursor | Desktop | Guide |
| Cline | VS Code extension | Guide |
| Continue | VS Code / JetBrains | Guide |
| VS Code Copilot | VS Code extension | Transparent proxy session |
| Aider / Grok CLI / Goose / OpenHands / Mistral Vibe / Oh My Pi / Kimi CLI / OpenClaw / GitHub Copilot CLI | CLI | Launch session button |

> Out of scope by design: agents that headroom does not support yet (Devin, Windsurf, Qwen Code, Qoder, CodeBuddy, workBuddy, Google Code Assist).

## How it works

| Agent | Switch ON | Switch OFF |
|---|---|---|
| Claude Code | `ANTHROPIC_BASE_URL` in `settings.json` points at the local proxy (original upstream remembered) | Original upstream restored |
| Codex | `openai_base_url` written to `config.toml` (applies to desktop + CLI) | Key removed |
| OpenCode | `headroom-*` mirror providers injected with an `x-headroom-base-url` per-request routing header | Mirror providers removed |
| ZCode / Cursor / others | Guide dialog; the proxy forwards to your chosen upstream | Nothing persisted |

The proxy runs as an independent hidden background process. Requests are compressed before forwarding (SmartCrusher / CodeCompressor / CacheAligner); originals stay in a local cache and remain retrievable on demand (headroom CCR).

## Install

### Prerequisites

1. Windows 10/11
2. The [Headroom CLI](https://github.com/headroomlabs-ai/headroom):
   ```bash
   uv tool install "headroom-ai[all]"
   # or
   pip install "headroom-ai[all]"
   ```

> If the app can't find headroom, a yellow banner appears at the top with install commands and links to the official install page.

### Option A: download a build

Grab `HeadroomSwitch.exe` from [Releases](../../releases) — single file, no installer.

### Option B: run from source

```bash
pip install -r requirements.txt
python app.py
```

### Build the EXE yourself

```bash
build.bat
```

Output: `dist/HeadroomSwitch.exe`. Tagged versions (`v*`) are also built automatically by GitHub Actions and attached to the release.

## Configuration

Open **Settings** in the top-right corner. Persisted at `~/.headroom-switcher/config.json`:

| Key | Default | Description |
|---|---|---|
| `port` | `8787` | Local headroom proxy port (change only when all switches are off) |
| `network_proxy` | `"auto"` | Proxy used to reach model upstreams: `auto` = follow the Windows system proxy / `direct` / `http://host:port` |
| `headroom_path` | `""` | Optional override of the headroom CLI path |
| `autostart` | `false` | Launch HeadroomSwitch at Windows logon |

## FAQ

**An agent can't connect after enabling?**
The proxy must be running (green status pill). The tool starts it automatically, but after a reboot — or if the proxy was killed manually — open the tool once or use the "Start proxy" button.

**Claude Code change not taking effect?**
The CLI reads its config at session start — exit and relaunch `claude`. Claude **Desktop** is not supported by headroom yet (it overrides the base URL), which is why the card is labeled `CLI`.

**OpenCode model list unchanged?**
Restart the OpenCode app (use the "Restart OpenCode" button) and pick a `xxx via Headroom` model.

**Does it send my code anywhere?**
No. Compression and caching happen locally; the proxy only forwards requests to your configured upstream, exactly like the agents do without it.

**macOS / Linux?**
Windows only for now. The core is plain Python + path handling — PRs for cross-platform support (proxy detection, `open`/`xdg-open` launching) are welcome.

## Acknowledgements

- [Headroom](https://github.com/headroomlabs-ai/headroom) — the engine this tool manages (Apache-2.0)
- [cc-switch](https://github.com/farion1231/cc-switch) — UI inspiration

## License

[MIT](LICENSE)
