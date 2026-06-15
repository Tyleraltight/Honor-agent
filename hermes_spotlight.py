"""
Hermes Spotlight - macOS Spotlight 风格的快速搜索框
直接调用 Anthropic Messages API，支持工具调用和流式输出
"""
import json
import os
import sys
import threading
import time
import subprocess
from pathlib import Path
from queue import Queue, Empty
import webview
import requests
from http.server import HTTPServer, BaseHTTPRequestHandler

# ── 路径配置 ──────────────────────────────────────────────────────
HERMES_DIR = Path(r"E:\hermes")
HISTORY_PATH = HERMES_DIR / "hermes_spotlight_history.json"
MEMORY_PATH = HERMES_DIR / "memories" / "MEMORY.md"
USER_PATH = HERMES_DIR / "memories" / "USER.md"
SOUL_PATH = HERMES_DIR / "SOUL.md"
CONFIG_PATH = HERMES_DIR / "config.yaml"
ENV_PATH = HERMES_DIR / ".env"

HTML_PATH = Path(__file__).parent / "hermes_spotlight.html"

# ── 工具定义 ──────────────────────────────────────────────────────
TOOLS = [
    {
        "name": "read_file",
        "description": "读取文件内容",
        "input_schema": {
            "type": "object",
            "properties": {
                "path": {"type": "string", "description": "文件路径"},
                "limit": {"type": "integer", "description": "最大行数", "default": 200}
            },
            "required": ["path"]
        }
    },
    {
        "name": "write_file",
        "description": "创建或写入文件",
        "input_schema": {
            "type": "object",
            "properties": {
                "path": {"type": "string", "description": "文件路径"},
                "content": {"type": "string", "description": "文件内容"}
            },
            "required": ["path", "content"]
        }
    },
    {
        "name": "list_directory",
        "description": "列出目录内容",
        "input_schema": {
            "type": "object",
            "properties": {
                "path": {"type": "string", "description": "目录路径"},
                "show_hidden": {"type": "boolean", "description": "是否显示隐藏文件", "default": False}
            },
            "required": ["path"]
        }
    },
    {
        "name": "delete_file",
        "description": "删除文件或空目录",
        "input_schema": {
            "type": "object",
            "properties": {
                "path": {"type": "string", "description": "文件或目录路径"}
            },
            "required": ["path"]
        }
    },
    {
        "name": "run_command",
        "description": "执行 shell 命令",
        "input_schema": {
            "type": "object",
            "properties": {
                "command": {"type": "string", "description": "要执行的命令"},
                "cwd": {"type": "string", "description": "工作目录"}
            },
            "required": ["command"]
        }
    },
    {
        "name": "search_files",
        "description": "搜索文件内容",
        "input_schema": {
            "type": "object",
            "properties": {
                "pattern": {"type": "string", "description": "搜索关键词"},
                "path": {"type": "string", "description": "搜索目录", "default": "."},
                "glob": {"type": "string", "description": "文件过滤", "default": "*"}
            },
            "required": ["pattern"]
        }
    }
]

SYSTEM_PROMPT = """你是 Hermes Spotlight，一个快速助手。你运行在用户的 Windows 电脑上，可以直接操作文件和执行命令。

能力：
- 读写文件、列出目录、删除文件
- 执行 shell 命令（cmd.exe）
- 搜索文件内容

规则：
- 简洁高效，像 macOS Spotlight 一样快速
- 直接执行，不要问"你确定吗"
- 用中文回复
- 如果需要多步骤操作，直接一步步做
"""

# ── API 配置 ──────────────────────────────────────────────────────
API_BASE_URL = "https://token-plan-cn.xiaomimimo.com/anthropic"
API_MODEL = "mimo-v2.5"

# ── Gateway 配置 ──────────────────────────────────────────────────
GATEWAY_URL = "http://localhost:8642"
GATEWAY_SESSION_ID = "spotlight-session"


def _is_gateway_running():
    """检查 Gateway API Server 是否运行"""
    try:
        resp = requests.get(f"{GATEWAY_URL}/health", timeout=2)
        return resp.status_code == 200
    except:
        return False


def _load_env():
    if ENV_PATH.exists():
        for line in ENV_PATH.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                key, _, value = line.partition("=")
                os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))


def _load_api_key():
    _load_env()
    key = os.environ.get("ANTHROPIC_API_KEY") or os.environ.get("CLAUDE_API_KEY")
    if key:
        return key
    if CONFIG_PATH.exists():
        import re
        text = CONFIG_PATH.read_text(encoding="utf-8")
        m = re.search(r"api_key:\s*[\"']?([a-zA-Z0-9_-]+)", text)
        if m:
            return m.group(1)
    return None


def _load_memory():
    parts = [SYSTEM_PROMPT]
    for path, label in [(SOUL_PATH, "人格"), (USER_PATH, "用户画像"), (MEMORY_PATH, "记忆")]:
        if path.exists():
            content = path.read_text(encoding="utf-8").strip()
            if content:
                parts.append(f"\n\n<hermes_{label}>\n{content}\n</hermes_{label}>")
    return "\n".join(parts)


def _execute_tool(name, args):
    try:
        if name == "read_file":
            p = Path(args["path"])
            if not p.exists():
                return f"错误：文件不存在 {p}"
            limit = args.get("limit", 200)
            lines = p.read_text(encoding="utf-8", errors="replace").splitlines()[:limit]
            return "\n".join(lines)
        elif name == "write_file":
            p = Path(args["path"])
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_text(args["content"], encoding="utf-8")
            return f"已写入 {p}"
        elif name == "list_directory":
            p = Path(args["path"])
            if not p.exists():
                return f"错误：目录不存在 {p}"
            show_hidden = args.get("show_hidden", False)
            entries = []
            for item in sorted(p.iterdir()):
                if not show_hidden and item.name.startswith("."):
                    continue
                kind = "d" if item.is_dir() else "f"
                entries.append(f"[{kind}] {item.name}")
            return "\n".join(entries) if entries else "空目录"
        elif name == "delete_file":
            p = Path(args["path"])
            if not p.exists():
                return f"错误：不存在 {p}"
            if p.is_dir():
                p.rmdir()
            else:
                p.unlink()
            return f"已删除 {p}"
        elif name == "run_command":
            cmd = args["command"]
            cwd = args.get("cwd")
            result = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=60, cwd=cwd)
            output = result.stdout + result.stderr
            return output.strip() if output else "(无输出)"
        elif name == "search_files":
            pattern = args["pattern"]
            search_path = args.get("path", ".")
            glob_pattern = args.get("glob", "*")
            matches = []
            for f in Path(search_path).rglob(glob_pattern):
                if f.is_file():
                    try:
                        text = f.read_text(encoding="utf-8", errors="replace")
                        if pattern.lower() in text.lower():
                            for i, line in enumerate(text.splitlines(), 1):
                                if pattern.lower() in line.lower():
                                    matches.append(f"{f}:{i}: {line.strip()[:200]}")
                                    if len(matches) >= 50:
                                        break
                    except:
                        pass
                if len(matches) >= 50:
                    break
            return "\n".join(matches) if matches else f"未找到 '{pattern}'"
        else:
            return f"未知工具: {name}"
    except Exception as e:
        return f"工具执行错误: {e}"


class SpotlightAPI:
    def __init__(self):
        self._window = None
        self._messages = []
        self._system_prompt = _load_memory()
        self._api_key = _load_api_key()
        self._queue = Queue()  # 传递给前端的事件队列
        self._busy = False
        self._visible = False
        self._load_history()

    def _load_history(self):
        if HISTORY_PATH.exists():
            try:
                data = json.loads(HISTORY_PATH.read_text(encoding="utf-8"))
                self._messages = data if isinstance(data, list) else data.get("messages", [])
                if len(self._messages) > 50:
                    self._messages = self._messages[-50:]
            except:
                self._messages = []

    def _save_history(self):
        try:
            HISTORY_PATH.parent.mkdir(parents=True, exist_ok=True)
            HISTORY_PATH.write_text(
                json.dumps(self._messages, ensure_ascii=False, indent=2),
                encoding="utf-8"
            )
        except:
            pass

    def set_window(self, window):
        self._window = window
        self._visible = True  # 窗口创建时是显示的

    def toggle_visibility(self):
        """切换搜索框的最小化/恢复状态"""
        if self._window:
            if self._visible:
                self._window.minimize()
                self._visible = False
            else:
                self._window.restore()
                self._visible = True
                # 聚焦到输入框
                self._window.evaluate_js("document.getElementById('queryInput').focus()")
        return json.dumps({"visible": self._visible})

    def show_window(self):
        """显示搜索框"""
        if self._window:
            self._window.show()
            self._visible = True
            self._window.evaluate_js("document.getElementById('queryInput').focus()")
        return json.dumps({"visible": True})

    def hide_window(self):
        """最小化搜索框"""
        if self._window:
            self._window.minimize()
            self._visible = False
        return json.dumps({"visible": False})

    def destroy(self):
        """关闭搜索框"""
        if self._window:
            self._window.destroy()
        return json.dumps({"ok": True})

    def move_window(self, x, y):
        if self._window:
            self._window.move(int(x), int(y))

    def get_history_summary(self):
        if not self._messages:
            return ""
        recent = self._messages[-6:]
        parts = []
        for msg in recent:
            role = "你" if msg["role"] == "user" else "AI"
            content = msg.get("content", "")
            if isinstance(content, str):
                parts.append(f"{role}: {content[:100]}")
            elif isinstance(content, list):
                text_parts = [b.get("text", "") for b in content if b.get("type") == "text"]
                if text_parts:
                    parts.append(f"{role}: {text_parts[0][:100]}")
        return "\n".join(parts)

    def new_conversation(self):
        self._messages = []
        self._save_history()
        return "ok"

    def get_config(self):
        """返回前端需要的所有配置"""
        return json.dumps({
            "api_key": self._api_key or "",
            "system_prompt": self._system_prompt,
            "messages": self._messages,
        })

    def chat(self, user_input):
        """
        前端调用：发送消息并在后台启动流式查询。
        返回 "ok" 表示已启动。
        """
        if self._busy:
            return json.dumps({"error": "正在处理中，请稍候"})

        # Gateway 模式不需要 API Key
        if not _is_gateway_running() and not self._api_key:
            return json.dumps({"error": "未找到 API Key"})

        if user_input.strip().lower() == "/new":
            self.new_conversation()
            return json.dumps({"type": "new"})

        self._messages.append({"role": "user", "content": user_input})
        self._save_history()

        # 清空队列
        while not self._queue.empty():
            try:
                self._queue.get_nowait()
            except Empty:
                break

        self._busy = True
        # 根据 Gateway 是否运行选择调用方式
        if _is_gateway_running():
            thread = threading.Thread(target=self._do_stream_gateway, daemon=True)
        else:
            thread = threading.Thread(target=self._do_stream, daemon=True)
        thread.start()
        return json.dumps({"type": "ok"})

    def reset_busy(self):
        """重置 busy 状态"""
        self._busy = False

    def poll(self):
        """前端轮询获取事件"""
        events = []
        while not self._queue.empty():
            try:
                events.append(self._queue.get_nowait())
            except Empty:
                break
        return json.dumps(events)

    def is_busy(self):
        return self._busy

    def _do_stream_gateway(self):
        """后台线程：通过 Gateway API 调用（OpenAI 格式）"""
        try:
            # 构建消息（Gateway 使用 OpenAI 格式）
            messages = [{"role": "system", "content": self._system_prompt}]
            for msg in self._messages:
                content = msg.get("content")
                if isinstance(content, str):
                    messages.append({"role": msg["role"], "content": content})
                elif isinstance(content, list):
                    # 处理工具调用结果
                    text_parts = [b.get("text", "") for b in content if b.get("type") == "text"]
                    if text_parts:
                        messages.append({"role": msg["role"], "content": "\n".join(text_parts)})

            resp = requests.post(
                f"{GATEWAY_URL}/v1/chat/completions",
                headers={
                    "Authorization": f"Bearer {os.environ.get('API_SERVER_KEY', 'hermes-spotlight-local-key')}",
                    "Content-Type": "application/json",
                    "X-Hermes-Session-Id": GATEWAY_SESSION_ID,
                },
                json={
                    "model": "hermes-agent",
                    "messages": messages,
                    "stream": True,
                },
                timeout=300,
                stream=True,
            )
            resp.encoding = "utf-8"
            resp.raise_for_status()

            full_response = ""

            for line in resp.iter_lines(decode_unicode=True):
                if not line or not line.startswith("data: "):
                    continue
                data = line[6:]
                if data == "[DONE]":
                    break

                try:
                    event = json.loads(data)
                except:
                    continue

                choices = event.get("choices", [])
                if choices:
                    delta = choices[0].get("delta", {})
                    content = delta.get("content")
                    if content:
                        full_response += content
                        self._queue.put({"t": "tok", "v": content})

            # 保存到历史
            if full_response:
                self._messages.append({"role": "assistant", "content": full_response})
                self._save_history()
            self._queue.put({"t": "done"})

        except Exception as e:
            self._queue.put({"t": "err", "v": str(e)})
        finally:
            self._busy = False

    def _do_stream(self):
        """后台线程：执行流式 API 调用"""
        try:
            resp = requests.post(
                f"{API_BASE_URL}/v1/messages",
                headers={
                    "x-api-key": self._api_key,
                    "anthropic-version": "2023-06-01",
                    "content-type": "application/json",
                },
                json={
                    "model": API_MODEL,
                    "max_tokens": 4096,
                    "system": self._system_prompt,
                    "tools": TOOLS,
                    "messages": self._messages,
                    "stream": True,
                },
                timeout=300,
                stream=True,
            )
            resp.encoding = "utf-8"
            resp.raise_for_status()

            assistant_content = []
            current_text = ""
            tool_calls = []

            for line in resp.iter_lines(decode_unicode=True):
                if not line or not line.startswith("data: "):
                    continue
                data = line[6:]
                if data == "[DONE]":
                    break

                try:
                    event = json.loads(data)
                except:
                    continue

                etype = event.get("type", "")

                if etype == "content_block_start":
                    block = event.get("content_block", {})
                    if block.get("type") == "text":
                        current_text = ""
                    elif block.get("type") == "tool_use":
                        tool_calls.append({
                            "id": block["id"],
                            "name": block["name"],
                            "input_json": ""
                        })
                    # thinking block 被忽略

                elif etype == "content_block_delta":
                    delta = event.get("delta", {})
                    if delta.get("type") == "text_delta":
                        current_text += delta["text"]
                        self._queue.put({"t": "tok", "v": delta["text"]})
                    elif delta.get("type") == "input_json_delta":
                        if tool_calls:
                            tool_calls[-1]["input_json"] += delta["partial_json"]
                    # thinking_delta 被忽略

                elif etype == "content_block_stop":
                    if current_text:
                        assistant_content.append({"type": "text", "text": current_text})
                        current_text = ""

                elif etype == "message_stop":
                    break

            # 处理工具调用
            if tool_calls:
                for tc in tool_calls:
                    assistant_content.append({
                        "type": "tool_use",
                        "id": tc["id"],
                        "name": tc["name"],
                        "input": json.loads(tc["input_json"]) if tc["input_json"] else {}
                    })
                self._messages.append({"role": "assistant", "content": assistant_content})

                tool_results = []
                for tc in tool_calls:
                    args = json.loads(tc["input_json"]) if tc["input_json"] else {}
                    self._queue.put({"t": "tool", "v": tc["name"]})
                    result = _execute_tool(tc["name"], args)
                    tool_results.append({
                        "type": "tool_result",
                        "tool_use_id": tc["id"],
                        "content": result
                    })

                self._messages.append({"role": "user", "content": tool_results})
                self._save_history()

                # 继续对话
                self._queue.put({"t": "cont"})
                self._do_stream_recursive()
            else:
                if assistant_content:
                    self._messages.append({"role": "assistant", "content": assistant_content})
                    self._save_history()
                self._queue.put({"t": "done"})

        except Exception as e:
            self._queue.put({"t": "err", "v": str(e)})
        finally:
            self._busy = False

    def _do_stream_recursive(self):
        """递归处理工具调用后的继续对话"""
        try:
            resp = requests.post(
                f"{API_BASE_URL}/v1/messages",
                headers={
                    "x-api-key": self._api_key,
                    "anthropic-version": "2023-06-01",
                    "content-type": "application/json",
                },
                json={
                    "model": API_MODEL,
                    "max_tokens": 4096,
                    "system": self._system_prompt,
                    "tools": TOOLS,
                    "messages": self._messages,
                    "stream": True,
                },
                timeout=300,
                stream=True,
            )
            resp.encoding = "utf-8"
            resp.raise_for_status()

            assistant_content = []
            current_text = ""
            tool_calls = []

            for line in resp.iter_lines(decode_unicode=True):
                if not line or not line.startswith("data: "):
                    continue
                data = line[6:]
                if data == "[DONE]":
                    break

                try:
                    event = json.loads(data)
                except:
                    continue

                etype = event.get("type", "")

                if etype == "content_block_start":
                    block = event.get("content_block", {})
                    if block.get("type") == "text":
                        current_text = ""
                    elif block.get("type") == "tool_use":
                        tool_calls.append({
                            "id": block["id"],
                            "name": block["name"],
                            "input_json": ""
                        })
                    # thinking block 被忽略

                elif etype == "content_block_delta":
                    delta = event.get("delta", {})
                    if delta.get("type") == "text_delta":
                        current_text += delta["text"]
                        self._queue.put({"t": "tok", "v": delta["text"]})
                    elif delta.get("type") == "input_json_delta":
                        if tool_calls:
                            tool_calls[-1]["input_json"] += delta["partial_json"]
                    # thinking_delta 被忽略

                elif etype == "content_block_stop":
                    if current_text:
                        assistant_content.append({"type": "text", "text": current_text})
                        current_text = ""

                elif etype == "message_stop":
                    break

            if tool_calls:
                for tc in tool_calls:
                    assistant_content.append({
                        "type": "tool_use",
                        "id": tc["id"],
                        "name": tc["name"],
                        "input": json.loads(tc["input_json"]) if tc["input_json"] else {}
                    })
                self._messages.append({"role": "assistant", "content": assistant_content})

                tool_results = []
                for tc in tool_calls:
                    args = json.loads(tc["input_json"]) if tc["input_json"] else {}
                    self._queue.put({"t": "tool", "v": tc["name"]})
                    result = _execute_tool(tc["name"], args)
                    tool_results.append({
                        "type": "tool_result",
                        "tool_use_id": tc["id"],
                        "content": result
                    })

                self._messages.append({"role": "user", "content": tool_results})
                self._save_history()

                self._queue.put({"t": "cont"})
                self._do_stream_recursive()
            else:
                if assistant_content:
                    self._messages.append({"role": "assistant", "content": assistant_content})
                    self._save_history()
                self._queue.put({"t": "done"})

        except Exception as e:
            self._queue.put({"t": "err", "v": str(e)})


class ToggleHandler(BaseHTTPRequestHandler):
    """处理切换信号的 HTTP 服务器"""
    api = None

    def do_POST(self):
        if self.path == '/toggle':
            if self.api:
                self.api.toggle_visibility()
            self.send_response(200)
            self.send_header('Content-type', 'application/json')
            self.end_headers()
            self.wfile.write(b'{"ok": true}')
        else:
            self.send_response(404)
            self.end_headers()

    def log_message(self, format, *args):
        pass  # 禁用日志

def watch_toggle_signal(api):
    """监视信号文件"""
    signal_path = Path(__file__).parent / "toggle_signal.txt"
    while True:
        try:
            if signal_path.exists():
                api.toggle_visibility()
                signal_path.unlink()
        except:
            pass
        time.sleep(0.1)

def main():
    api = SpotlightAPI()
    window = webview.create_window(
        "Hermes Spotlight",
        url=str(HTML_PATH),
        width=600,
        height=400,
        frameless=True,
        on_top=True,
        easy_drag=False,
        js_api=api,
    )
    api.set_window(window)

    # 启动信号文件监视器
    signal_thread = threading.Thread(target=watch_toggle_signal, args=(api,), daemon=True)
    signal_thread.start()

    webview.start(debug=False)


if __name__ == "__main__":
    main()
