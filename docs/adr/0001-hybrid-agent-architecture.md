# ADR 0001: Hybrid Headless Architecture with Risk-Tiered Guardrails

* **Status**: Accepted
* **Date**: 2026-09-03
* **Author**: T (WelTec / Honor Agent Project)

## Context
The Honor Agent began as a desktop quick-launcher prototype (Spotlight style) built with Python and pywebview, tailored for personal low-latency use (invoking via F11 / hotkeys while gaming or watching movies).
However, as the project evolved into an enterprise-grade showcase for AI Engineer, Security/PrivSec, and Process Automation roles, three architectural challenges emerged:
1. **Coupled Monolith**: Tool execution, model API requests, and webview UI were bundled into a single 750-line script, making automated headless testing and multi-client integration impossible without launching a graphical window.
2. **Missing Security Boundaries**: The agent executed arbitrary shell commands (`subprocess.run(cmd, shell=True)`) without input validation, directly conflicting with least-privilege principles and posing severe data loss risks on developer workstations.
3. **No Remote Mobility**: The desktop tool could only be triggered while sitting in front of the keyboard, leaving background batch scripts and system telemetry inaccessible when away from the PC.

## Decision
We adopted a **Hybrid Headless Architecture with Risk-Tiered Guardrails**:
1. **Core Decoupling (`core/agent_runner.py`)**: Extracted a headless `AgentRunner` managing tool dispatching, system prompts, memory injection (`SOUL.md`, `MEMORY.md`), and streaming protocol handling.
2. **Multi-Tier Guardrails (`core/guardrails.py`)**:
   - **Tier 1 (Safe Read/Query)**: Workspace path validation preventing directory traversal attacks (`../Windows/System32`).
   - **Tier 2 (Controlled Write)**: Sandboxed file mutation with write permission boundaries.
   - **Tier 3 (Execution Whitelist)**: Strict command whitelist (`dir`, `tasklist`, `python`, `git`, `start`, etc.) with automatic regex interception of destructive commands (`format`, `rmdir /s`, `del /s /f`, `powershell -enc`).
3. **Multi-Channel Presentation**:
   - **Desktop Frontend (`hermes_spotlight.py` + `launcher.ahk`)**: Preserved the sub-second floating Spotlight interface for zero-friction desktop multitasking.
   - **Remote Gateway (`bot_gateway.py`)**: Asynchronous Telegram Bot client with message queues and exponential backoff retry loops, including a `--mock` dry-run mode for offline verification.
4. **Automated Test Harness (`tests/test_harness.py`)**: Built a comprehensive `unittest` matrix covering path traversal defense, destructive command interception, tool execution, and mock gateway queuing.

## Alternatives Considered
* **Alternative A (Keep Monolith + Standalone CLI Helper)**: Rejected because duplicate tool execution and streaming logic would drift over time, and security guardrails would not apply uniformly to both desktop and CLI triggers.
* **Alternative B (Heavy Client-Server Framework like FastAPI + WebSockets)**: Rejected based on KISS principles. Running a persistent HTTP server in the background would increase memory footprint (100MB+) and startup latency, impairing the instant Siri/Spotlight popping experience while watching movies or gaming.

## Consequences
* **Positive Trade-offs**:
  - Complete preservation of the fast Spotlight desktop experience (<100ms popup latency).
  - Robust security posture against prompt injection attacks and destructive commands.
  - Unified business logic shared between desktop and remote mobile channels.
  - 100% reproducible test suite executable in CI/CD without API keys or live network tokens.
* **Operational Costs & Technical Debt**:
  - Added module boundaries requiring `sys.path` awareness when executing scripts from different working directories.
  - Command whitelist requires deliberate updates when new developer CLI utilities are introduced.
