# Hermes Spotlight 搜索框 — 项目上下文

## 目标
在荣耀 MagicBook Pro 16 2026 上，将键盘右侧的 **Copilot 键** 重映射为启动自定义 Hermes Agent 搜索框（Spotlight 风格）。

---

## 当前状态
- **搜索框本体（Python + pywebview）功能正常**，能弹出、能对话、能读取 SOUL.md
- **流式输出已修复**：API 返回 `thinking` 类型的 content block，原代码只处理 `text_delta`，已忽略 `thinking_delta`
- **F11 快捷键正常工作**：可以打开/最小化搜索框
- **Copilot 键无法使用**：硬件层面的问题，AHK 无法正确拦截 Copilot 键

---

## 关键文件路径

| 文件 | 路径 |
|------|------|
| AHK 脚本 | `E:\HermesSpotlight\copilot-to-hermes.ahk` |
| Python 搜索框 | `E:\HermesSpotlight\hermes_spotlight.py` |
| HTML UI | `E:\HermesSpotlight\hermes_spotlight.html` |
| 启动脚本 | `E:\HermesSpotlight\hermes_spotlight.bat` |
| AHK 可执行文件 | `C:\Users\26502\AppData\Local\Programs\AutoHotkey\v2\AutoHotkey64.exe` |
| Hermes 根目录 | `E:\hermes\` |
| Hermes SOUL.md | `E:\hermes\SOUL.md` |
| Hermes 配置 | `E:\hermes\config.yaml` |
| Hermes .env | `E:\hermes\.env` |
| 对话历史 | `E:\hermes\hermes_spotlight_history.json` |
| MCP Server | `E:\hermes\hermes-agent\optional-skills\mcp\spotlight-history\server.py` |

---

## 已解决的问题

### 1. 流式输出不工作
**问题**：API 调用正常，但前端只显示"你:"，看不到 AI 回复

**根因**：API 返回两个 content block：
1. `thinking`（模型思考过程）
2. `text`（实际回复）

原代码只处理 `text_delta`，忽略了 `thinking_delta`，导致没有收到任何 token。

**修复**：在 `_do_stream()` 和 `_do_stream_recursive()` 函数中添加对 `thinking_delta` 的忽略处理。

### 2. 搜索框显示问题
**问题**：搜索框太小，看不到输出内容

**修复**：
- 窗口大小调整为 600x250
- 输出区域自动滚动到最新内容
- 添加重置按钮解决 `_busy` 状态卡住问题

### 3. UI 设计
**问题**：搜索框 UI 需要优化

**修复**：
- 背景色：#d4c9b8（温暖的土黄色）
- 文字色：#0d0d0d（深灰）
- Tyler 标签：#d97757（赤土色）
- K 标签：#4a4a4a（灰色）
- Placeholder："/new 开启新对话"

---

## 已确认的键码信息
- Copilot 键和左 Windows 键的 **扫描码都是 SC15B**，虚拟键码都是 VK5B
- Copilot 键在系统底层映射为 **F23**（VK: 86, SC: 06E）
- 两个键在 AHK 层面看起来完全一样，无法区分

---

## 已尝试但失败的方案（Copilot 键）

| # | 方案 | 结果 |
|---|------|------|
| 1 | `VK07` 热键 | 不是正确的键码，完全无效 |
| 2 | `VK5B` 单独处理 | 两个键都触发 |
| 3 | `VK5A`（左 Win）+ `VK5B`（右 Win/Copilot）分别处理 | 导致 Z 键被错误映射 |
| 4 | `WH_KEYBOARD_LL` 低级键盘钩子（CallbackCreate） | 钩子安装成功但回调永远不触发（AHK v2 兼容性问题） |
| 5 | `GetKeyState("LWin", "P")` 区分 | 两个键都返回相同状态 |
| 6 | `WM_INPUT` 原始输入 | 脚本报错 |
| 7 | Windows 注册表禁用 Copilot 键系统行为 | 设置里改为"未选择任何内容"后仍无法区分 |
| 8 | `SC06E`（F23 扫描码） | 无法拦截 Copilot 键 |
| 9 | `F23` 键码 | 无法拦截 Copilot 键 |
| 10 | `VK86`（F23 虚拟键码） | 无法拦截 Copilot 键 |

---

## 当前 AHK 脚本

```ahk
; F11 键切换搜索框显示/隐藏
F11:: {
    if ProcessExist("pythonw.exe") {
        FileAppend "toggle", A_ScriptDir "\toggle_signal.txt"
    } else {
        Run '"' A_ScriptDir '\hermes_spotlight.bat"', , 'Hide'
    }
}

; F23 键 (Copilot 键) 切换搜索框显示/隐藏 - 使用扫描码
SC06E:: {
    if ProcessExist("pythonw.exe") {
        FileAppend "toggle", A_ScriptDir "\toggle_signal.txt"
    } else {
        Run '"' A_ScriptDir '\hermes_spotlight.bat"', , 'Hide'
    }
}
```

**注意**：F11 键正常工作，但 Copilot 键（SC06E）无法使用。

---

## Windows 设置状态
- Windows 设置 > Copilot 键 > 已设为 **"未选择任何内容"**（禁用了系统默认行为）
- 注册表 `HKCU\Software\Microsoft\Windows\CurrentVersion\Explorer\Advanced` 中 `ShowCopilotButton` 设为 0

---

## 搜索框已实现的功能
- [x] Spotlight 风格 UI（圆角搜索框 + 温暖土黄色背景）
- [x] 键盘快捷键（F11 打开/最小化，× 按钮关闭）
- [x] AI 对话（Xiaomi mimo-v2.5 模型）
- [x] 工具调用（read_file, write_file, list_directory, delete_file, run_command, search_files）
- [x] SOUL.md 人格注入
- [x] 对话历史持久化（保存到 `E:\hermes\hermes_spotlight_history.json`）
- [x] `/new` 命令开启新对话
- [x] 流式输出（修复 thinking block 问题）
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
- 目标：`powershell.exe -Command "Start-Process -FilePath 'C:\Users\26502\AppData\Local\Programs\AutoHotkey\v2\AutoHotkey64.exe' -ArgumentList '\"E:\HermesSpotlight\copilot-to-hermes.ahk\"' -WindowStyle Hidden"`

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

---

## GitHub 仓库
https://github.com/Tyleraltight/Honor-agent.git
