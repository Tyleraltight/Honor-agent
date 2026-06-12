"""调试测试：验证 chat + poll 流程"""
import json
import threading
import time
from queue import Queue, Empty
import webview
import requests

API_BASE_URL = "https://token-plan-cn.xiaomimimo.com/anthropic"
API_MODEL = "mimo-v2.5"

# 加载 API key
import os
from pathlib import Path

ENV_PATH = Path(r"E:\hermes\.env")
if ENV_PATH.exists():
    for line in ENV_PATH.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            key, _, value = line.partition("=")
            os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))

API_KEY = os.environ.get("ANTHROPIC_API_KEY") or os.environ.get("CLAUDE_API_KEY")
print(f"[DEBUG] API Key: {API_KEY[:20]}..." if API_KEY else "[DEBUG] No API Key!")

class DebugAPI:
    def __init__(self):
        self._queue = Queue()
        self._window = None
        self._busy = False

    def set_window(self, window):
        self._window = window

    def chat(self, user_input):
        print(f"[DEBUG] chat() called with: {user_input}")
        if self._busy:
            print("[DEBUG] Already busy, returning error")
            return json.dumps({"error": "正在处理中"})

        self._busy = True
        print("[DEBUG] Starting background thread...")
        thread = threading.Thread(target=self._do_api_call, args=(user_input,), daemon=True)
        thread.start()
        return json.dumps({"type": "ok"})

    def poll(self):
        events = []
        while not self._queue.empty():
            try:
                events.append(self._queue.get_nowait())
            except Empty:
                break
        if events:
            print(f"[DEBUG] poll() returning {len(events)} events: {[e['t'] for e in events]}")
        return json.dumps(events)

    def _do_api_call(self, user_input):
        print(f"[DEBUG] _do_api_call started")
        try:
            resp = requests.post(
                f"{API_BASE_URL}/v1/messages",
                headers={
                    "x-api-key": API_KEY,
                    "anthropic-version": "2023-06-01",
                    "content-type": "application/json",
                },
                json={
                    "model": API_MODEL,
                    "max_tokens": 100,
                    "messages": [{"role": "user", "content": user_input}],
                    "stream": True,
                },
                timeout=30,
                stream=True,
            )
            print(f"[DEBUG] API response status: {resp.status_code}")
            resp.encoding = "utf-8"
            resp.raise_for_status()

            line_count = 0
            all_text = ""
            current_block_type = None
            for line in resp.iter_lines(decode_unicode=True):
                line_count += 1
                if not line or not line.startswith("data: "):
                    continue
                data = line[6:]
                if data == "[DONE]":
                    print(f"[DEBUG] [DONE] received")
                    break
                try:
                    event = json.loads(data)
                    etype = event.get("type", "")
                    if etype == "content_block_start":
                        block = event.get("content_block", {})
                        current_block_type = block.get("type")
                        print(f"[DEBUG] Block started: {current_block_type}")
                    elif etype == "content_block_delta":
                        delta = event.get("delta", {})
                        if delta.get("type") == "text_delta":
                            text = delta["text"]
                            all_text += text
                            print(f"[DEBUG] Text token: {repr(text)}")
                            self._queue.put({"t": "tok", "v": text})
                        elif delta.get("type") == "thinking_delta":
                            # 忽略 thinking delta
                            pass
                    elif etype == "content_block_stop":
                        print(f"[DEBUG] Block stopped: {current_block_type}")
                        current_block_type = None
                    elif etype == "message_stop":
                        print(f"[DEBUG] Message stopped")
                        break
                    elif etype == "error":
                        print(f"[DEBUG] API Error: {event}")
                        self._queue.put({"t": "err", "v": json.dumps(event.get("error", {}))})
                        return
                except Exception as e:
                    print(f"[DEBUG] JSON parse error: {e}")

            print(f"[DEBUG] Total lines: {line_count}, text tokens: {len(all_text)}")
            self._queue.put({"t": "done"})
            print("[DEBUG] Done event sent")

        except Exception as e:
            print(f"[DEBUG] Error: {e}")
            import traceback
            traceback.print_exc()
            self._queue.put({"t": "err", "v": str(e)})
        finally:
            self._busy = False
            print("[DEBUG] _do_api_call finished")

HTML = """<!DOCTYPE html>
<html><head><meta charset="utf-8">
<style>
  body { font-family: sans-serif; background: #222; color: #fff; padding: 20px; }
  input { width: 400px; padding: 10px; font-size: 16px; }
  button { padding: 10px 20px; font-size: 16px; margin: 10px; }
  #out { background: #333; padding: 10px; min-height: 200px; margin-top: 10px; white-space: pre-wrap; font-size: 14px; }
  #debug { background: #111; color: #0f0; padding: 10px; margin-top: 10px; font-size: 12px; }
</style></head><body>
  <h2>Hermes Debug Test</h2>
  <input id="inp" type="text" placeholder="输入消息..." value="你好" />
  <button onclick="send()">发送</button>
  <button onclick="pollOnce()">手动轮询一次</button>
  <div id="out"></div>
  <div id="debug"></div>
  <script>
    const out = document.getElementById('out');
    const debug = document.getElementById('debug');
    const inp = document.getElementById('inp');
    let timer = null;

    function log(msg) {
      out.innerHTML += msg + '\\n';
      out.scrollTop = out.scrollHeight;
    }
    function dbg(msg) {
      debug.innerHTML += msg + '\\n';
      debug.scrollTop = debug.scrollHeight;
      console.log(msg);
    }

    window.addEventListener('pywebviewready', () => {
      dbg('pywebview ready');
    });

    async function send() {
      const text = inp.value.trim();
      if (!text) return;

      log('>>> ' + text);
      dbg('Calling chat...');

      try {
        const raw = await pywebview.api.chat(text);
        dbg('chat returned: ' + raw);
        const resp = JSON.parse(raw);

        if (resp.error) {
          log('ERROR: ' + resp.error);
          return;
        }

        log('AI: ');
        startPolling();
      } catch (e) {
        dbg('chat error: ' + e.message);
        log('ERROR: ' + e.message);
      }
    }

    function startPolling() {
      if (timer) clearInterval(timer);
      dbg('Starting polling...');
      timer = setInterval(async () => {
        try {
          const raw = await pywebview.api.poll();
          const events = JSON.parse(raw);
          if (events.length > 0) {
            dbg('Got ' + events.length + ' events');
            for (const ev of events) {
              if (ev.t === 'tok') {
                out.innerHTML += ev.v;
                out.scrollTop = out.scrollHeight;
              } else if (ev.t === 'done') {
                out.innerHTML += '\\n[DONE]\\n';
                clearInterval(timer);
                timer = null;
                dbg('Polling stopped');
              } else if (ev.t === 'err') {
                out.innerHTML += '\\n[ERROR: ' + ev.v + ']\\n';
                clearInterval(timer);
                timer = null;
              }
            }
          }
        } catch (e) {
          dbg('Poll error: ' + e.message);
        }
      }, 100);
    }

    async function pollOnce() {
      dbg('Manual poll...');
      try {
        const raw = await pywebview.api.poll();
        dbg('poll returned: ' + raw);
        const events = JSON.parse(raw);
        log('Events: ' + JSON.stringify(events));
      } catch (e) {
        dbg('poll error: ' + e.message);
      }
    }
  </script>
</body></html>"""

def main():
    api = DebugAPI()
    window = webview.create_window("Debug Test", html=HTML, width=800, height=600, js_api=api)
    api.set_window(window)
    webview.start(debug=True)

if __name__ == "__main__":
    main()
