# HeadroomSwitch

**Headroom Agent 管理** — 一个为 [Headroom](https://github.com/headroomlabs-ai/headroom) 设计的 Windows 桌面管理工具。扫描本机已安装的 AI 编程 Agent，一键开关 Headroom 上下文压缩代理，关闭时自动还原原始配置。

> Not affiliated with headroomlabs-ai. This is an independent community tool that drives the open-source [`headroom`](https://github.com/headroomlabs-ai/headroom) CLI.

## 特性

- 🔍 **自动扫描**：启动时检测本机的 Claude Code / Codex / OpenCode（CLI 与桌面版均可识别）
- 🎛️ **一键开关**：每个 Agent 独立开关；开启 = 接入 Headroom 代理压缩，关闭 = **自动还原原始配置**（含备份）
- ⚙️ **代理全自动**：任一开关打开自动启动本地代理，全部关闭自动停止；重启电脑后自动恢复
- 🔁 **应用内重启**：内置"重启 Codex / 重启 OpenCode"按钮，配置即改即生效
- 🪞 **全模型镜像**（OpenCode）：自动为所有供应商的所有模型生成 `headroom-*` 镜像版，按请求路由到各自上游——切换任意模型都能享受压缩
- 📊 **节省可视化**：页脚实时显示累计压缩节省的 tokens 与美元估算，一键打开 Headroom 节省面板
- 🖥️ **托盘常驻**：关闭窗口最小化到托盘，左键唤出，右键退出
- 🔒 **安全还原**：所有配置修改均有备份，开关关闭即精确还原

## 工作原理

| Agent | 开关开启 | 开关关闭 |
|---|---|---|
| **Claude Code** | `settings.json` 的 `ANTHROPIC_BASE_URL` 指向本地代理（原上游自动记忆） | 还原原上游地址 |
| **Codex** | `config.toml` 写入 `openai_base_url`（桌面版 + CLI 全生效） | 移除该配置 |
| **OpenCode** | 注入 `headroom-*` 镜像供应商（带 `x-headroom-base-url` 按请求路由头） | 删除全部镜像配置 |

代理进程以独立后台进程运行，转发请求前完成压缩（SmartCrusher / CodeCompressor / CacheAligner），原始内容本地缓存、可随时取回（Headroom CCR）。

## 安装

### 前置要求

1. Windows 10/11
2. 已安装 [Headroom CLI](https://github.com/headroomlabs-ai/headroom)：
   ```bash
   uv tool install "headroom-ai[all]"
   # 或
   pip install "headroom-ai[all]"
   ```

### 方式一：下载构建产物

从 [Releases](../../releases) 下载 `HeadroomSwitch.exe`，双击即用。

### 方式二：源码运行

```bash
pip install -r requirements.txt
python app.py
```

### 从源码构建 EXE

```bash
build.bat
```

产物位于 `dist/HeadroomSwitch.exe`。

## 配置

设置入口：主窗口右上角 **设置**。配置持久化于 `~/.headroom-switcher/config.json`：

| 字段 | 默认 | 说明 |
|---|---|---|
| `port` | `8787` | 本地 Headroom 代理端口（修改需先关闭全部开关） |
| `network_proxy` | `"auto"` | 访问模型上游的网络代理：`auto` 跟随 Windows 系统代理 / `direct` 直连 / `http://host:port` 自定义 |
| `headroom_path` | `""` | headroom CLI 路径覆盖（默认 `~/.local/bin/headroom.exe`） |

## 常见问题

**开启后 Agent 无法联网？**
代理进程必须处于运行状态（状态灯为绿色）。管理工具会自动拉起，但如果你手动关闭了代理或重启后尚未打开管理工具，请先启动本工具。

**Claude Code 开启后没有立即生效？**
CLI 配置在**新会话**开始时读取，请退出当前会话后重新启动 `claude`。

**OpenCode 开启后模型列表没有变化？**
需要重启 OpenCode 应用（卡片上有"重启 OpenCode"按钮），并在模型列表中选择 `xxx via Headroom` 版模型。

**支持 macOS / Linux 吗？**
目前仅支持 Windows。核心逻辑是纯 Python + 路径操作，欢迎 PR 补充跨平台支持（macOS 的代理检测、`open`/`xdg-open` 启动方式等）。

## 致谢

- [Headroom](https://github.com/headroomlabs-ai/headroom) — 本工具管理的一切能力的来源（Apache-2.0）
- [cc-switch](https://github.com/farion1231/cc-switch) — UI 风格参考

## License

[MIT](LICENSE)
