# HeadroomSwitch

**为 [Headroom](https://github.com/headroomlabs-ai/headroom) 打造的 Windows 桌面管理工具** —— 自动扫描本机已安装的 AI 编程 Agent，一键开关 Headroom 上下文压缩代理；关闭时自动还原原始配置。

**[English](README.md)** | 中文

![screenshot](screenshots/main.png)

[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)
[![Release](https://img.shields.io/github/v/release/ChangWeiBaoDaLaiFu/HeadroomSwitch)](../../releases)

> **为什么做这个：** Agent 的 token 大头不是对话，而是每次工具调用的返回——读个文件、跑个测试，几万 token 就没了。[Headroom](https://github.com/headroomlabs-ai/headroom) 会在本地把这些内容压缩后再发给模型（答案不变：编码场景省 15–20%，JSON 能省 60–95%，且可通过缓存取回原文）。HeadroomSwitch 把它从"命令行仪式"变成一个复选框。

> 本项目为独立社区工具，与 headroomlabs-ai 官方无关；数据全部本地处理。

## 特性

- **自动扫描** —— 启动时识别 17 种 Headroom 兼容 Agent，只显示你实际安装的
- **一键开关** —— 开 = 接入本地压缩代理；关 = 从备份**精确还原**原始配置
- **代理全自动** —— 任一开关打开自动拉起，全部关闭自动停止，重启电脑自动恢复
- **作用范围标签** —— 卡片标注 `CLI` / `CLI + 桌面版` / `桌面版`，开关影响范围一目了然
- **会话启动按钮** —— 环境变量型 CLI 工具（Aider、Goose、Kimi CLI、Grok CLI、OpenHands、Mistral Vibe、Oh My Pi、OpenClaw、GitHub Copilot CLI）一键在新终端经代理拉起会话
- **接入指引** —— Cursor、ZCode、Cline、Continue、VS Code Copilot 提供应用内分步指引；ZCode 支持一键切换上游（智谱国内 / z.ai 国际）
- **OpenCode 全模型镜像** —— 你的每个供应商/模型都会生成 `headroom-*` 压缩版，按请求路由上游，随便切模型
- **节省可视化** —— 页脚实时显示累计节省 token 与美元估算，一键打开 Headroom 节省面板
- **应用内重启** —— "重启 Codex / OpenCode / ZCode / Cursor"按钮，配置即改即生效
- **托盘常驻** —— 关闭窗口最小化到托盘；可选开机自启动

## 支持的 Agent

| Agent | 范围 | 接入方式 |
|---|---|---|
| Claude Code | CLI | 自动开关（关闭即还原） |
| Codex | CLI + 桌面版 | 自动开关 |
| OpenCode | CLI + 桌面版 | 自动开关 + 全模型镜像 |
| ZCode | 桌面版 | 指引 + 上游切换 |
| Cursor | 桌面版 | 指引 |
| Cline | VS Code 扩展 | 指引 |
| Continue | VS Code / JetBrains | 指引 |
| VS Code Copilot | VS Code 扩展 | 透明代理会话 |
| Aider / Grok CLI / Goose / OpenHands / Mistral Vibe / Oh My Pi / Kimi CLI / OpenClaw / GitHub Copilot CLI | CLI | 启动会话按钮 |

> Headroom 尚不支持的 Agent（Devin、Windsurf、Qwen Code、Qoder、CodeBuddy、workBuddy、Google Code Assist）暂不在范围内。

## 工作原理

| Agent | 开关开启 | 开关关闭 |
|---|---|---|
| Claude Code | `settings.json` 的 `ANTHROPIC_BASE_URL` 指向本地代理（原上游自动记忆） | 还原原上游地址 |
| Codex | `config.toml` 写入 `openai_base_url`（桌面版 + CLI 全生效） | 移除该配置 |
| OpenCode | 注入 `headroom-*` 镜像供应商（带 `x-headroom-base-url` 按请求路由头） | 删除全部镜像配置 |
| ZCode / Cursor / 其他 | 指引引导；代理按所选上游转发 | 不落地任何配置 |

代理进程以独立隐藏后台进程运行。请求转发前完成压缩（SmartCrusher / CodeCompressor / CacheAligner），原始内容本地缓存、可随时取回（Headroom CCR）。

## 安装

### 前置要求

1. Windows 10/11
2. 已安装 [Headroom CLI](https://github.com/headroomlabs-ai/headroom)：
   ```bash
   uv tool install "headroom-ai[all]"
   # 或
   pip install "headroom-ai[all]"
   ```

> 若程序找不到 headroom，顶部会出现黄色横幅，附安装命令与官网链接。

### 方式一：下载构建产物

从 [Releases](../../releases) 下载 `HeadroomSwitch.exe` —— 单文件，免安装。

### 方式二：源码运行

```bash
pip install -r requirements.txt
python app.py
```

### 从源码构建 EXE

```bash
build.bat
```

产物：`dist/HeadroomSwitch.exe`。推送 `v*` 标签时 GitHub Actions 也会自动构建并挂到 Release。

## 配置

设置入口：主窗口右上角 **设置**。持久化于 `~/.headroom-switcher/config.json`：

| 字段 | 默认 | 说明 |
|---|---|---|
| `port` | `8787` | 本地 Headroom 代理端口（修改需先关闭全部开关） |
| `network_proxy` | `"auto"` | 访问模型上游的代理：`auto` 跟随系统代理 / `direct` 直连 / `http://host:port` 自定义 |
| `headroom_path` | `""` | headroom CLI 路径覆盖 |
| `autostart` | `false` | 开机自启动 |

## 常见问题

**开启后 Agent 无法联网？**
代理必须处于运行状态（状态灯绿色）。工具会自动拉起；若刚重启电脑或代理被手动结束，打开本工具或点"启动代理"即可。

**Claude Code 开启后没生效？**
CLI 在**新会话**开始时读取配置，请退出当前会话重新启动 `claude`。Claude **桌面版**暂不被 Headroom 支持（它会覆写 Base URL），所以卡片标注为 `CLI`。

**OpenCode 模型列表没变化？**
重启 OpenCode 应用（卡片上有"重启 OpenCode"按钮），并选择 `xxx via Headroom` 模型。

**会把我的代码发到别处吗？**
不会。压缩与缓存全部在本地；代理只是把请求转发给你配置的上游——和不用代理时完全一致。

**支持 macOS / Linux 吗？**
目前仅 Windows。核心逻辑是纯 Python + 路径操作，欢迎 PR 补充跨平台支持（系统代理检测、`open`/`xdg-open` 启动等）。

## 致谢

- [Headroom](https://github.com/headroomlabs-ai/headroom) —— 本工具管理的一切能力的来源（Apache-2.0）
- [cc-switch](https://github.com/farion1231/cc-switch) —— UI 风格参考

## License

[MIT](LICENSE)
