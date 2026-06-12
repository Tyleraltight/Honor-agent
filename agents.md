# Hermes Spotlight 搜索框 — 项目上下文

## 目标
在荣耀 MagicBook Pro 16 2026 上，将键盘右侧的 **Copilot 键** 重映射为启动自定义 Hermes Agent 搜索框（Spotlight 风格）。

---

## 当前状态
- **搜索框本体（Python + pywebview）功能正常**，能弹出、能对话、能读取 SOUL.md
- **AHK 脚本存在核心问题**：Copilot 键和左 Windows 键无法区分
- **搜索框无法正常回答**：按 Copilot 键弹出后，提问只显示"你:"，无回复内容（流式输出问题）

---

## 关键文件路径

| 文件 | 路径 |
|------|------|
| AHK 脚本 | `E:\ClaudeCode\scripts\copilot-to-hermes.ahk` |
| Python 搜索框 | `E:\ClaudeCode\scripts\hermes_spotlight.py` |
| HTML UI | `E:\ClaudeCode\scripts\hermes_spotlight.html` |
| 启动脚本 | `E:\ClaudeCode\scripts\hermes_spotlight.bat` |
| AHK 可执行文件 | `C:\Users\26502\AppData\Local\Programs\AutoHotkey\v2\AutoHotkey64.exe` |
| Hermes 根目录 | `E:\hermes\` |
| Hermes SOUL.md | `E:\hermes\SOUL.md` |
| Hermes 配置 | `E:\hermes\config.yaml` |
| Hermes .env | `E:\hermes\.env` |
| 原始备份目录 | `E:\HermesSpotlight\` |
| 对话历史 | `E:\hermes\hermes_spotlight_history.json` |
| MCP Server | `E:\hermes\hermes-agent\optional-skills\mcp\spotlight-history\server.py` |

---

## 已确认的键码信息
- Copilot 键和左 Windows 键的 **扫描码都是 SC15B**，虚拟键码都是 VK5B
- 两个键在 AHK 层面看起来完全一样
- 用简单的 `SC15B::` 热键可以让 Copilot 键工作，但左 Win 键也会被拦截

---

## 已尝试但失败的方案

| # | 方案 | 结果 |
|---|------|------|
| 1 | `VK07` 热键 | 不是正确的键码，完全无效 |
| 2 | `VK5B` 单独处理 | 两个键都触发 |
| 3 | `VK5A`（左 Win）+ `VK5B`（右 Win/Copilot）分别处理 | 导致 Z 键被错误映射 |
| 4 | `WH_KEYBOARD_LL` 低级键盘钩子（CallbackCreate） | 钩子安装成功但回调永远不触发（AHK v2 兼容性问题） |
| 5 | `GetKeyState("LWin", "P")` 区分 | 两个键都返回相同状态 |
| 6 | `WM_INPUT` 原始输入 | 脚本报错 |
| 7 | Windows 注册表禁用 Copilot 键系统行为 | 设置里改为"未选择任何内容"后仍无法区分 |

---

## 当前 AHK 脚本（能用但不完美）

```ahk
; Copilot 键扫描码: SC15B
SC15B:: {
    Run '"' A_ScriptDir '\hermes_spotlight.bat"', , 'Hide'
}
```

这段代码让 Copilot 键能打开搜索框，但左 Win 键也会被拦截。

---

## Windows 设置状态
- Windows 设置 > Copilot 键 > 已设为 **"未选择任何内容"**（禁用了系统默认行为）
- 注册表 `HKCU\Software\Microsoft\Windows\CurrentVersion\Explorer\Advanced` 中 `ShowCopilotButton` 设为 0

---

## 需要解决的核心问题

### 问题 1：区分 Copilot 键和左 Windows 键
让：
- **左 Win 键** → 正常打开开始菜单
- **Copilot 键** → 打开 Hermes Spotlight 搜索框

### 问题 2：搜索框流式输出不工作
- API 调用正常（历史记录有回复内容）
- 前端只显示"你:"，看不到 AI 回复
- 尝试过 `evaluate_js` 推送、轮询模式、同步返回，均未解决
- pywebview 的 JS 桥可能存在线程兼容问题

---

## 可能的解决方向

### 区分按键
1. 研究 AHK v2 的 `WH_KEYBOARD_LL` 钩子正确写法（`CallbackCreate` + `OnMessage` 组合）
2. 用其他工具（PowerShell、C#、Rust）编写独立的键盘钩子程序
3. 研究荣耀 MagicBook 的 Copilot 键是否有特殊 HID 信号
4. 用 `RegisterRawInputDevices` + `WM_INPUT` 方式，需要正确的 AHK v2 语法

### 流式输出
1. 检查 pywebview 版本兼容性（`evaluate_js` 从后台线程调用可能被丢弃）
2. 尝试用 `webview.windows[0].evaluate_js()` 替代 `pywebview.api`
3. 考虑用 WebSocket 代替 JS 桥通信

---

## 搜索框已实现的功能
- [x] Spotlight 风格 UI（圆角搜索框 + 半透明背景）
- [x] 键盘快捷键（Esc 关闭）
- [x] AI 对话（Xiaomi mimo-v2.5 模型）
- [x] 工具调用（read_file, write_file, list_directory, delete_file, run_command, search_files）
- [x] SOUL.md 人格注入
- [x] 对话历史持久化（保存到 `E:\hermes\hermes_spotlight_history.json`）
- [x] `/new` 命令开启新对话
- [x] Markdown 渲染（标题、粗体、斜体、列表、行内代码、代码块）
- [x] 代码块横向滚动 + 复制按钮
- [x] 输出内容可选中复制
- [x] MCP Server（让 Hermes 能读取 Spotlight 历史）

---

## 环境信息
- **操作系统**：Windows 11 Home China
- **电脑型号**：荣耀 MagicBook Pro 16 2026
- **Python**：`C:\Users\26502\AppData\Local\Programs\Python\Python312\`
- **Hermes 虚拟环境**：`E:\hermes\hermes-agent\venv\`
- **AHK 版本**：v2（AutoHotkey64.exe）
- **API**：Xiaomi mimo-v2.5（token-pla...开头的 key）

---

## 开机自启动
- AHK 快捷方式位于：`C:\Users\26502\AppData\Roaming\Microsoft\Windows\Start Menu\Programs\Startup\HermesSpotlight.lnk`
- 目标：`powershell.exe -Command "Start-Process -FilePath 'C:\Users\26502\AppData\Local\Programs\AutoHotkey\v2\AutoHotkey64.exe' -ArgumentList '\"E:\ClaudeCode\scripts\copilot-to-hermes.ahk\"' -WindowStyle Hidden"`

---

## MCP Server 配置（已完成）
在 `E:\hermes\config.yaml` 中添加了：
```yaml
mcp_servers:
  spotlight-history:
    command: "C:/Users/26502/AppData/Local/Programs/Python/Python312/python.exe"
    args: ["E:/hermes/hermes-agent/optional-skills/mcp/spotlight-history/server.py"]
```

Hermes 可用工具：
- `read_spotlight_history` — 读取最近的 Spotlight 对话
- `search_spotlight_history` — 搜索包含关键词的历史对话
