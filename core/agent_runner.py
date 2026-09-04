"""
Honor Agent - Headless Agent Runner & Tool Orchestrator.

Decouples the core agent logic from frontend presentation layers.
Coordinates tool definitions, system memory injection, model API streaming,
and guardrail-enforced execution.
"""

import os
import sys
import json
import time
import shutil
import platform
import subprocess
from pathlib import Path
from typing import Dict, Any, List, Generator, Optional

try:
    import requests
except ImportError:
    requests = None

from core.guardrails import GuardrailsValidator, GuardrailViolationError

# Default Hermes paths
HERMES_DIR = Path(r"E:\hermes")
HISTORY_PATH = HERMES_DIR / "hermes_spotlight_history.json"
MEMORY_PATH = HERMES_DIR / "memories" / "MEMORY.md"
USER_PATH = HERMES_DIR / "memories" / "USER.md"
SOUL_PATH = HERMES_DIR / "SOUL.md"
CONFIG_PATH = HERMES_DIR / "config.yaml"
ENV_PATH = HERMES_DIR / ".env"

API_BASE_URL = "https://token-plan-cn.xiaomimimo.com/anthropic"
API_MODEL = "mimo-v2.5"

TOOLS_SCHEMA = [
    {
        "name": "read_file",
        "description": "Read contents from a file within permitted workspace paths",
        "input_schema": {
            "type": "object",
            "properties": {
                "path": {"type": "string", "description": "Target file path"},
                "limit": {"type": "integer", "description": "Maximum lines to read", "default": 200}
            },
            "required": ["path"]
        }
    },
    {
        "name": "write_file",
        "description": "Create or write content to a file with directory traversal checks",
        "input_schema": {
            "type": "object",
            "properties": {
                "path": {"type": "string", "description": "Target file path"},
                "content": {"type": "string", "description": "Text content to write"}
            },
            "required": ["path", "content"]
        }
    },
    {
        "name": "list_directory",
        "description": "List files and subdirectories within a directory",
        "input_schema": {
            "type": "object",
            "properties": {
                "path": {"type": "string", "description": "Directory path"},
                "show_hidden": {"type": "boolean", "description": "Whether to include hidden entries", "default": False}
            },
            "required": ["path"]
        }
    },
    {
        "name": "delete_file",
        "description": "Delete a file or empty directory safely",
        "input_schema": {
            "type": "object",
            "properties": {
                "path": {"type": "string", "description": "File or empty directory path"}
            },
            "required": ["path"]
        }
    },
    {
        "name": "run_command",
        "description": "Execute a permitted shell command under strict security whitelist",
        "input_schema": {
            "type": "object",
            "properties": {
                "command": {"type": "string", "description": "Shell command to execute"},
                "cwd": {"type": "string", "description": "Working directory path"},
                "silent": {"type": "boolean", "description": "Run silently without popup window", "default": True}
            },
            "required": ["command"]
        }
    },
    {
        "name": "search_files",
        "description": "Search text patterns across files in a directory",
        "input_schema": {
            "type": "object",
            "properties": {
                "pattern": {"type": "string", "description": "Text pattern to search"},
                "path": {"type": "string", "description": "Search root directory", "default": "."},
                "glob": {"type": "string", "description": "File glob pattern", "default": "*"}
            },
            "required": ["pattern"]
        }
    },
    {
        "name": "get_system_status",
        "description": "Retrieve host machine telemetry (OS, disk space, Python runtime, uptime)",
        "input_schema": {
            "type": "object",
            "properties": {}
        }
    }
]

BASE_SYSTEM_PROMPT = """You are Honor Agent, a privacy-first personal desktop intelligence assistant running locally on Windows.
You help users inspect system status, manage files, search documents, and trigger desktop workflows efficiently.

Security Rules:
- All commands and file operations pass through an automated Guardrail verification engine.
- High-risk operations (formatting disks, deleting system root directories) are strictly blocked.
- Provide concise, actionable answers. Respond in Chinese when the user prompts in Chinese.
"""


class AgentRunner:
    """Core headless agent runner supporting streaming interaction and guarded execution."""

    def __init__(self, validator: Optional[GuardrailsValidator] = None, api_key: Optional[str] = None):
        self.validator = validator or GuardrailsValidator()
        self._load_env()
        self.api_key = api_key or self._load_api_key()
        self.system_prompt = self._assemble_system_prompt()

    @staticmethod
    def _load_env():
        if ENV_PATH.exists():
            try:
                for line in ENV_PATH.read_text(encoding="utf-8").splitlines():
                    line = line.strip()
                    if line and not line.startswith("#") and "=" in line:
                        key, _, value = line.partition("=")
                        os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))
            except Exception:
                pass

    @classmethod
    def _load_api_key(cls) -> Optional[str]:
        cls._load_env()
        key = (
            os.environ.get("ANTHROPIC_API_KEY") or
            os.environ.get("CLAUDE_API_KEY") or
            os.environ.get("XIAOMI_API_KEY")
        )
        if key:
            return key
        if CONFIG_PATH.exists():
            try:
                import re
                text = CONFIG_PATH.read_text(encoding="utf-8")
                m = re.search(r"api_key:\s*[\"']?([a-zA-Z0-9_.-]+)", text)
                if m:
                    return m.group(1)
            except Exception:
                pass
        return None

    def _assemble_system_prompt(self) -> str:
        parts = [BASE_SYSTEM_PROMPT]
        for path, label in [(SOUL_PATH, "Persona"), (USER_PATH, "UserProfile"), (MEMORY_PATH, "Memory")]:
            if path.exists():
                try:
                    content = path.read_text(encoding="utf-8").strip()
                    if content:
                        parts.append(f"\n\n<hermes_{label}>\n{content}\n</hermes_{label}>")
                except Exception:
                    pass
        return "\n".join(parts)

    def execute_tool(self, name: str, args: Dict[str, Any]) -> str:
        """Execute a tool with strict guardrail enforcement."""
        try:
            if name == "read_file":
                target_path = args.get("path", "")
                self.validator.check_and_enforce_path(target_path, is_write=False)
                p = Path(target_path).resolve()
                if not p.exists():
                    return f"Error: File does not exist ({p})"
                limit = args.get("limit", 200)
                lines = p.read_text(encoding="utf-8", errors="replace").splitlines()[:limit]
                return "\n".join(lines)

            elif name == "write_file":
                target_path = args.get("path", "")
                self.validator.check_and_enforce_path(target_path, is_write=True)
                p = Path(target_path).resolve()
                p.parent.mkdir(parents=True, exist_ok=True)
                p.write_text(args.get("content", ""), encoding="utf-8")
                return f"Successfully wrote to {p}"

            elif name == "list_directory":
                target_path = args.get("path", ".")
                self.validator.check_and_enforce_path(target_path, is_write=False)
                p = Path(target_path).resolve()
                if not p.exists():
                    return f"Error: Directory does not exist ({p})"
                show_hidden = args.get("show_hidden", False)
                entries = []
                for item in sorted(p.iterdir()):
                    if not show_hidden and item.name.startswith("."):
                        continue
                    kind = "d" if item.is_dir() else "f"
                    entries.append(f"[{kind}] {item.name}")
                return "\n".join(entries) if entries else "(Empty directory)"

            elif name == "delete_file":
                target_path = args.get("path", "")
                self.validator.check_and_enforce_path(target_path, is_write=True)
                p = Path(target_path).resolve()
                if not p.exists():
                    return f"Error: Path does not exist ({p})"
                if p.is_dir():
                    p.rmdir()
                else:
                    p.unlink()
                return f"Successfully deleted {p}"

            elif name == "run_command":
                cmd = args.get("command", "")
                self.validator.check_and_enforce_command(cmd)
                cwd = args.get("cwd")
                silent = args.get("silent", True)

                creationflags = subprocess.CREATE_NO_WINDOW if (silent and os.name == "nt") else 0
                result = subprocess.run(
                    cmd, shell=True, capture_output=True, text=True, timeout=60, cwd=cwd,
                    creationflags=creationflags
                )
                output = (result.stdout + result.stderr).strip()
                return output if output else "(Command executed with no output)"

            elif name == "search_files":
                pattern = args.get("pattern", "")
                search_path = args.get("path", ".")
                self.validator.check_and_enforce_path(search_path, is_write=False)
                glob_pattern = args.get("glob", "*")
                matches = []
                for f in Path(search_path).resolve().rglob(glob_pattern):
                    if f.is_file():
                        try:
                            text = f.read_text(encoding="utf-8", errors="replace")
                            if pattern.lower() in text.lower():
                                for i, line in enumerate(text.splitlines(), 1):
                                    if pattern.lower() in line.lower():
                                        matches.append(f"{f}:{i}: {line.strip()[:200]}")
                                        if len(matches) >= 50:
                                            break
                        except Exception:
                            pass
                    if len(matches) >= 50:
                        break
                return "\n".join(matches) if matches else f"No matches found for '{pattern}'"

            elif name == "get_system_status":
                total, used, free = shutil.disk_usage(Path.cwd().anchor)
                free_gb = free // (2**30)
                total_gb = total // (2**30)
                status_info = {
                    "os": f"{platform.system()} {platform.release()} ({platform.version()})",
                    "machine": platform.machine(),
                    "python": sys.version.split()[0],
                    "disk_free_gb": f"{free_gb} GB / {total_gb} GB",
                    "working_directory": str(Path.cwd()),
                }
                return json.dumps(status_info, ensure_ascii=False, indent=2)

            else:
                return f"Error: Unknown tool '{name}'"

        except GuardrailViolationError as ge:
            return f"[Guardrail Intercepted] Operation rejected: {ge} (Tier: {ge.tier.value})"
        except Exception as e:
            return f"Tool execution failed: {type(e).__name__} - {e}"

    def run_stream(self, messages: List[Dict[str, Any]]) -> Generator[Dict[str, Any], None, None]:
        """
        Stream model response and handle tool calls recursively.
        Yields events matching the protocol:
        - {"t": "tok", "v": "chunk"}
        - {"t": "tool", "v": "tool_name"}
        - {"t": "done"}
        - {"t": "err", "v": "error message"}
        """
        if not self.api_key:
            yield {"t": "err", "v": "API key not configured in environment or E:\\hermes\\.env"}
            return

        if requests is None:
            yield {"t": "err", "v": "requests library is not installed"}
            return

        working_messages = messages
        max_turns = 5

        while max_turns > 0:
            max_turns -= 1
            tool_calls = []
            assistant_content = []
            current_text = ""

            try:
                resp = requests.post(
                    f"{API_BASE_URL}/v1/messages",
                    headers={
                        "x-api-key": self.api_key,
                        "anthropic-version": "2023-06-01",
                        "content-type": "application/json",
                    },
                    json={
                        "model": API_MODEL,
                        "max_tokens": 4096,
                        "system": self.system_prompt,
                        "tools": TOOLS_SCHEMA,
                        "messages": working_messages,
                        "stream": True,
                    },
                    timeout=180,
                    stream=True,
                )
                resp.encoding = "utf-8"
                resp.raise_for_status()

                for line in resp.iter_lines(decode_unicode=True):
                    if not line or not line.startswith("data: "):
                        continue
                    data = line[6:]
                    if data == "[DONE]":
                        break

                    try:
                        event = json.loads(data)
                    except Exception:
                        continue

                    etype = event.get("type", "")

                    if etype == "content_block_start":
                        block = event.get("content_block", {})
                        btype = block.get("type")
                        if btype == "text":
                            current_text = ""
                        elif btype == "tool_use":
                            tool_calls.append({
                                "id": block["id"],
                                "name": block["name"],
                                "input_json": ""
                            })

                    elif etype == "content_block_delta":
                        delta = event.get("delta", {})
                        dtype = delta.get("type")
                        if dtype == "text_delta":
                            text_chunk = delta.get("text", "")
                            current_text += text_chunk
                            yield {"t": "tok", "v": text_chunk}
                        elif dtype == "input_json_delta":
                            if tool_calls:
                                tool_calls[-1]["input_json"] += delta.get("partial_json", "")

                    elif etype == "content_block_stop":
                        if current_text:
                            assistant_content.append({"type": "text", "text": current_text})
                            current_text = ""

                    elif etype == "message_stop":
                        break

            except Exception as e:
                yield {"t": "err", "v": f"Network/Model streaming error: {e}"}
                return

            if tool_calls:
                for tc in tool_calls:
                    parsed_args = {}
                    if tc["input_json"]:
                        try:
                            parsed_args = json.loads(tc["input_json"])
                        except Exception:
                            parsed_args = {}
                    assistant_content.append({
                        "type": "tool_use",
                        "id": tc["id"],
                        "name": tc["name"],
                        "input": parsed_args
                    })

                working_messages.append({"role": "assistant", "content": assistant_content})

                tool_results = []
                for tc in tool_calls:
                    yield {"t": "tool", "v": tc["name"]}
                    parsed_args = {}
                    if tc["input_json"]:
                        try:
                            parsed_args = json.loads(tc["input_json"])
                        except Exception:
                            parsed_args = {}
                    result = self.execute_tool(tc["name"], parsed_args)
                    tool_results.append({
                        "type": "tool_result",
                        "tool_use_id": tc["id"],
                        "content": result
                    })

                working_messages.append({"role": "user", "content": tool_results})
                # Loop back to let model produce final explanation with tool result
                continue
            else:
                if assistant_content:
                    working_messages.append({"role": "assistant", "content": assistant_content})
                yield {"t": "done"}
                return

        yield {"t": "done"}
