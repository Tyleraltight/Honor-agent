"""
Hermes Spotlight - macOS Spotlight style quick desktop launcher.
Powered by core.agent_runner with risk-tiered security guardrails.
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
from http.server import HTTPServer, BaseHTTPRequestHandler

# Import unified core runner and schemas
from core.agent_runner import AgentRunner, TOOLS_SCHEMA, BASE_SYSTEM_PROMPT

# Path configuration
HERMES_DIR = Path(r"E:\hermes")
HISTORY_PATH = HERMES_DIR / "hermes_spotlight_history.json"
HTML_PATH = Path(__file__).parent / "hermes_spotlight.html"

# Backward compatibility aliases
TOOLS = TOOLS_SCHEMA
SYSTEM_PROMPT = BASE_SYSTEM_PROMPT

def _execute_tool(name, args):
    """Backward compatible helper delegating to AgentRunner with Guardrail enforcement."""
    runner = AgentRunner()
    return runner.execute_tool(name, args)



class SpotlightAPI:
    def __init__(self):
        self._window = None
        self._messages = []
        self.runner = AgentRunner()
        self._system_prompt = self.runner.system_prompt
        self._api_key = self.runner.api_key
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

        if not self._api_key:
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
        # 直接使用本地 API，保留本地工具执行能力
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

    def _do_stream(self):
        """后台线程：通过 AgentRunner 执行流式 API 调用与 Guardrail 工具分发"""
        try:
            for event in self.runner.run_stream(self._messages):
                self._queue.put(event)
            self._save_history()
        except Exception as e:
            self._queue.put({"t": "err", "v": str(e)})
        finally:
            self._busy = False



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
        height=300,
        frameless=True,
        on_top=True,
        easy_drag=False,
        js_api=api,
        text_select=True,  # 允许文本选择
    )
    api.set_window(window)

    # 启动信号文件监视器
    signal_thread = threading.Thread(target=watch_toggle_signal, args=(api,), daemon=True)
    signal_thread.start()

    webview.start(debug=False)


if __name__ == "__main__":
    main()
