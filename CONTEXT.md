# Honor Agent - Domain Context & Ubiquitous Language

This document establishes domain models, system boundaries, and standardized terminology for the **Honor Agent** ecosystem across all agent sessions and technical reviews.

---

## 1. Domain Entities & Components

### Spotlight Frontend
* **Definition**: A lightweight, frameless floating UI built with Python `pywebview` and HTML/CSS.
* **Characteristics**: Centered on the primary screen, strictly configured with `on_top=True`, activated in sub-100ms via global hotkeys (`Ctrl + Shift + Space` or `F11`), and optimized for low-latency multitasking while watching movies or gaming.
* **Component Path**: `hermes_spotlight.py`, `hermes_spotlight.html`.

### Agentic Orchestrator (Core Runner)
* **Definition**: The headless execution engine that manages LLM interactions, streaming protocols, memory hydration, and tool execution.
* **Design Rule**: Agnostic to the presentation layer. Can be consumed by the Spotlight window, CLI scripts, or the remote bot gateway.
* **Component Path**: `core/agent_runner.py`.

### Risk-Tiered Guardrail (Security Layer)
* **Definition**: A security filter that audits every incoming path manipulation and system command before handing execution to the OS kernel.
* **Tiers**:
  * **Tier 1 (Safe Query)**: Read-only operations, system telemetry inspection, and directory exploration within permitted workspace paths.
  * **Tier 2 (Controlled Write)**: Workspace-bounded file writing with strict directory traversal prevention (`../` escaping to system roots).
  * **Tier 3 (Sensitive Execution)**: System command execution gated by an explicit whitelist (`COMMAND_WHITELIST`) and regex filters blocking destructive commands (`format`, `rmdir /s`, `del /s /f`, `powershell -enc`).
* **Component Path**: `core/guardrails.py`.

### Remote Bot Gateway
* **Definition**: An asynchronous communication bridge connecting mobile messaging platforms (Telegram Bot / WeCom) to the local desktop Agent Runner.
* **Resilience Features**: Sequential message queue processing (`asyncio.Queue`) to prevent concurrent state corruption, exponential backoff retry loops on network drops, and a `--mock` execution mode for offline verification.
* **Component Path**: `bot_gateway.py`.

### Test Harness
* **Definition**: A standardized, reproducible automated test suite built on Python's native `unittest` framework.
* **Purpose**: Verifies injection defense, path sanitization, command whitelisting, and mock queue processing in CI or local development environments without requiring active API keys or live network tokens.
* **Component Path**: `tests/test_harness.py`.

---

## 2. Shared Invariants & Operational Rules

1. **Least-Privilege System Invocation**: The agent must never invoke `shell=True` without first passing the command string through `GuardrailsValidator.check_and_enforce_command()`.
2. **Path Sanitization**: Relative paths must be resolved and checked against `SENSITIVE_DIR_PATTERNS`. Operations attempting to target `C:\Windows` or system configuration folders must immediately fail with `GuardrailViolationError`.
3. **Deterministic Suffix Removal**: Command token normalization must use `.removesuffix()` rather than `.rstrip()` to prevent character-set truncation bugs (see Lessons Learned L047).
4. **Offline Verifiability**: Any feature touching remote APIs or external platforms must provide a mock or dry-run execution path allowing offline demonstration and automated test execution.
