# Honor Agent

**A Personal Local, Privacy-First Desktop Automation Agent & Cross-Device Gateway**  
**基于本地大模型与轻量运行器的隐私优先型桌面智能体与跨端自动化助手**

---

[English](#english) | [中文说明](#chinese)

---

<a name="english"></a>
## English Version

### 1. Overview & Core Mission

Honor Agent is an open-source, privacy-first desktop intelligent assistant engineered for Windows. Built for power users and developers, it bridges conversational AI with native operating system automation:

1. **System Execution over Chatbot Toys**: Directly executes multi-step scripts, file operations, and system queries rather than remaining confined to browser chat.
2. **Data Sovereignty & Local Control**: Keeps workflow execution, context memory, and operational logs strictly on your local machine without proprietary cloud lock-in.
3. **Seamless Dual-Channel Interaction**:
   - **At the Desk**: Instant floating Spotlight interface summoned in sub-100ms via global hotkeys (`Ctrl + Shift + Space` or `F11`) for zero-friction multitasking while watching videos or gaming.
   - **Away from the Desk**: Asynchronous Telegram Bot gateway enabling mobile system queries (`/status`) and background script triggering (`/run <cmd>`).
4. **Engineering Rigor & Security Guardrails**: Eliminates LLM hallucination risks via risk-tiered command whitelisting and directory traversal sandboxing.

---

### 2. System Architecture

```
[ Trigger & Interface Layer ]
  +---------------------------+        +---------------------------+
  | Desktop Spotlight UI      |        | Remote Bot Gateway        |
  | (pywebview + launcher.ahk)|        | (Telegram Async Queue)    |
  +-------------+-------------+        +-------------+-------------+
                |                                    |
                +-----------------+------------------+
                                  |
                                  v
[ Orchestration & Core Engine ]
  +----------------------------------------------------------------+
  | core.agent_runner.AgentRunner                                  |
  | - LLM API Streaming (Xiaomi mimo-v2.5 / Anthropic Messages)    |
  | - Context & Memory Hydration (SOUL.md, MEMORY.md, USER.md)     |
  | - Tool Registry & Dispatching                                  |
  +-------------------------------+--------------------------------+
                                  |
                                  v
[ Security & Defense Layer ]
  +----------------------------------------------------------------+
  | core.guardrails.GuardrailsValidator                            |
  | - Tier 1: Path Traversal Sanitization (Blocks ..\Windows, etc.) |
  | - Tier 2: Sandboxed Write Permissions                           |
  | - Tier 3: Command Whitelist & Destructive Pattern Interception  |
  +-------------------------------+--------------------------------+
                                  |
                                  v
[ Execution & Tooling Layer ]
  +----------------------------------------------------------------+
  | Local OS Tools:                                                |
  | - read_file / write_file / list_directory / delete_file        |
  | - run_command (Whitelisted shell execution)                    |
  | - search_files (Fast recursive pattern search)                 |
  | - get_system_status (OS, CPU, memory, disk free telemetry)     |
  +----------------------------------------------------------------+
```

---

### 3. Repository Structure

```
Honor-agent/
|-- core/
|   |-- __init__.py
|   |-- agent_runner.py          # Headless orchestrator & tool execution
|   `-- guardrails.py            # Risk-tiered path & command validator
|-- docs/
|   `-- adr/
|       `-- 0001-hybrid-agent-architecture.md  # Architecture decision record
|-- tests/
|   |-- __init__.py
|   `-- test_harness.py          # 14 automated unit tests
|-- bot_gateway.py               # Async Telegram Bot gateway (with --mock mode)
|-- hermes_spotlight.py          # pywebview desktop launcher
|-- hermes_spotlight.html        # Floating Spotlight UI
|-- hermes_spotlight.bat         # Background process bootstrapper
|-- launcher.ahk                 # AutoHotkey v2 global hotkey hook
|-- copilot-to-hermes.ahk        # MagicBook Copilot hardware research script
|-- CONTEXT.md                   # Domain glossary & ubiquitous language
|-- AGENTS.md                    # Agent context & hardware scancode notes
`-- README.md                    # Bilingual documentation
```

---

### 4. Security & Guardrail Boundaries

The agent executes native OS commands. To prevent accidental data destruction or prompt injection escapes, `core.guardrails.GuardrailsValidator` enforces a three-tier risk model:

* **Tier 1 (Safe Read/Query)**: Path normalization rejects directory traversal attempts targeting OS roots (e.g. `..\..\Windows\System32`, `.ssh`, `.aws`).
* **Tier 2 (Controlled Write)**: File creation and deletion are strictly sandboxed within designated workspace roots.
* **Tier 3 (Execution Whitelist)**:
  * **Permitted Binaries**: `dir`, `echo`, `type`, `tasklist`, `netstat`, `ping`, `ipconfig`, `python`, `git`, `start`, `calc`, `notepad`, `curl`, `whoami`, `hostname`.
  * **Intercepted Patterns**: Automatic blocking of `format`, `rmdir /s`, `del /s /f`, `rm -rf`, `diskpart`, `shutdown`, `powershell -enc`, and fork bombs.

---

### 5. Quick Start (English)

#### Prerequisites
* Windows 10 / 11
* Python 3.12+
* AutoHotkey v2 (optional, for global hotkey support)

#### Installation
```powershell
git clone https://github.com/Tyleraltight/Honor-agent.git
cd Honor-agent
pip install pywebview requests
```

#### Running Desktop Spotlight
```powershell
# Option A: Start directly
python hermes_spotlight.py

# Option B: Run via AutoHotkey global hotkey
# Double-click launcher.ahk, then press:
# [Ctrl + Shift + Space] or [F11]
```

#### Running Remote Bot Gateway
```powershell
# Offline Dry-Run / Mock Mode (No tokens or internet required)
python bot_gateway.py --mock

# Live Telegram Bot Mode
$env:TELEGRAM_BOT_TOKEN="your_bot_token_here"
python bot_gateway.py
```

Available Remote Commands:
* `/status`: Retrieve host hardware telemetry (OS version, disk free space, Python environment).
* `/run <command>`: Safely execute a whitelisted system command and retrieve stdout/stderr.
* Natural text: Stream conversational queries directly to the local agent.

#### Running Automated Test Harness
```powershell
python -m unittest discover -s tests -v
```

---

<a name="chinese"></a>
## 中文说明

### 1. 项目定位与核心价值

Honor Agent 是一款专为 Windows 设计的本地隐私优先型桌面智能体与跨端自动化助手。旨在打破传统 Chatbot 只能在网页端文字聊天的局限，真正深入操作系统底层执行多步骤脚本与桌面工作流：

1. **拒绝对话玩具，聚焦系统执行**：直接调度系统命令、读写文件、自动化检索日志，打通大模型意图解析与本地系统操作；
2. **绝对隐私与本地自主**：数据与记忆完全保存在本地受控环境，摆脱昂贵、闭源且存在数据泄露风险的商业厂商云端助手；
3. **跨端移动双向交互**：
   - **在工位前**：类似 macOS Spotlight 风格的毫秒级极速悬浮搜索框，按下 `Ctrl + Shift + Space` 或 `F11` 瞬间呼出，在看电影或打游戏时不切屏完成快速多任务；
   - **离开电脑时**：集成异步 Telegram Bot 网关，手机随时发送 `/status` 查看电脑运行状态，或发送 `/run <cmd>` 远程调度本地脚本；
4. **防幻觉与分级安全护栏**：内置三级安全策略引擎（Risk-Tiered Guardrail）与命令白名单，严禁在无二次确认的情况下执行破坏性系统指令。

---

### 2. 系统架构分层

* **交互与触发层 (Trigger & Interface Layer)**：
  * 桌面端：基于 AutoHotkey v2 全局快捷键监听（`Ctrl + Shift + Space` 与 `F11`）与轻量 `pywebview` 胶囊悬浮框；
  * 移动端：集成异步 Telegram Bot 网关（具备 `asyncio.Queue` 消息防并发竞态队列与断线重连指数退避机制）。
* **调度与智能体大脑 (Agentic Orchestrator)**：
  * 核心位于 `core/agent_runner.py`，负责管理上下文记忆（`SOUL.md`、`MEMORY.md`、`USER.md`）、工具注册表与流式响应协议。
* **安全护栏与防御层 (Security & Guardrails Layer)**：
  * 核心位于 `core/guardrails.py`，实现路径遍历防护（防止越界访问 `C:\Windows\System32`、`.ssh` 等敏感目录）与可执行命令白名单过滤。
* **执行与系统工具层 (Tools & Execution Layer)**：
  * 提供 `read_file`、`write_file`、`list_directory`、`delete_file`、`run_command`、`search_files` 以及 `get_system_status` 等本地操作系统级能力。
* **健壮性与测试桩层 (Guardrails & Test Harnesses)**：
  * 核心位于 `tests/test_harness.py`，包含 14 个测试用例，覆盖路径注入、危险指令拦截、白名单校验与异步队列模拟。

---

### 3. 安全护栏与权限策略

Agent 拥有执行系统命令的能力。为杜绝提示词注入攻击与偶发幻觉造成的破坏性后果，系统执行以下三级约束：

* **Tier 1 (只读探针)**：规范化解析文件路径，拦截一切跳出工作区或访问系统敏感目录（如 `..\..\Windows\System32`）的尝试。
* **Tier 2 (受控写操作)**：文件写入与删除操作限制在工作区沙盒内，禁止修改系统关键根路径。
* **Tier 3 (执行白名单)**：
  * **放行指令**：`dir`, `echo`, `type`, `tasklist`, `netstat`, `ping`, `ipconfig`, `python`, `git`, `start`, `calc`, `notepad`, `curl` 等；
  * **拦截高危指令**：自动拦截 `format`, `rmdir /s`, `del /s /f`, `rm -rf`, `diskpart`, `shutdown`, `powershell -enc` 与 Fork 炸弹。

---

### 4. 快速上手指南 (中文)

#### 环境要求
* Windows 10 / 11
* Python 3.12+
* AutoHotkey v2（可选，用于全局快捷键唤起）

#### 安装依赖
```powershell
git clone https://github.com/Tyleraltight/Honor-agent.git
cd Honor-agent
pip install pywebview requests
```

#### 启动桌面悬浮搜索框 (Spotlight)
```powershell
# 方式一：直接运行 Python 脚本
python hermes_spotlight.py

# 方式二：双击运行 launcher.ahk
# 随后在任意界面按下快捷键唤出：
# [Ctrl + Shift + Space] 或 [F11]
```

#### 启动远程 Bot 网关
```powershell
# 离线空跑 / 测试模式（无需 Token 或公网网络，直接测试消息队列与护栏）
python bot_gateway.py --mock

# 真实 Telegram 机器人模式
$env:TELEGRAM_BOT_TOKEN="你的_bot_token"
python bot_gateway.py
```

远程指令：
* `/status`：获取当前电脑硬件指标（系统版本、磁盘剩余容量、Python 运行时）；
* `/run <命令>`：在安全护栏内执行白名单系统指令并回传标准输出；
* 普通文本消息：直接向本地 Agent 发起自然语言流式提问。

#### 运行自动化测试桩
```powershell
python -m unittest discover -s tests -v
```

---

### 5. 架构决策与规范文档

* [ADR 0001: 混合解耦架构与分级安全护栏决策记录](docs/adr/0001-hybrid-agent-architecture.md)
* [CONTEXT: 领域模型与通用语言词汇表](CONTEXT.md)
* [硬件探索记录: 荣耀 MagicBook Copilot 键按键扫描码分析](AGENTS.md)

---

### 6. 开源协议

本项目采用 MIT 许可证。详见 [LICENSE](LICENSE)。
