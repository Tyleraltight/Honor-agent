"""最小化测试：验证 pywebview.api.poll() 是否正常工作"""
import json
import threading
import time
from queue import Queue, Empty
import webview

class API:
    def __init__(self):
        self._queue = Queue()
        self._window = None

    def set_window(self, window):
        self._window = window

    def start_test(self):
        """模拟后台产生事件"""
        def worker():
            for i in range(5):
                time.sleep(1)
                self._queue.put({"t": "tok", "v": f"token-{i} "})
            self._queue.put({"t": "done"})
        threading.Thread(target=worker, daemon=True).start()
        return "ok"

    def poll(self):
        events = []
        while not self._queue.empty():
            try:
                events.append(self._queue.get_nowait())
            except Empty:
                break
        return json.dumps(events)

HTML = """<!DOCTYPE html>
<html><head><meta charset="utf-8">
<style>
  body { font-family: sans-serif; background: #222; color: #fff; padding: 20px; }
  button { padding: 10px 20px; font-size: 16px; margin: 10px; }
  #out { background: #333; padding: 10px; min-height: 150px; margin-top: 10px; white-space: pre-wrap; font-size: 18px; }
</style></head><body>
  <h2>pywebview poll 测试</h2>
  <button onclick="start()">开始测试</button>
  <div id="out"></div>
  <script>
    const out = document.getElementById('out');
    let timer = null;

    window.addEventListener('pywebviewready', () => {
      out.innerHTML += 'pywebview 就绪\\n';
    });

    async function start() {
      out.innerHTML += '调用 start_test...\\n';
      const r = await pywebview.api.start_test();
      out.innerHTML += 'start_test 返回: ' + r + '\\n';
      out.innerHTML += '开始轮询...\\n';

      timer = setInterval(async () => {
        const raw = await pywebview.api.poll();
        const events = JSON.parse(raw);
        if (events.length > 0) {
          for (const ev of events) {
            out.innerHTML += '事件: ' + ev.t + ' = ' + (ev.v || '') + '\\n';
            if (ev.t === 'done') {
              clearInterval(timer);
              out.innerHTML += '完成！\\n';
            }
          }
        }
      }, 100);
    }
  </script>
</body></html>"""

def main():
    api = API()
    window = webview.create_window("测试", html=HTML, width=500, height=400, js_api=api)
    api.set_window(window)
    webview.start(debug=True)

if __name__ == "__main__":
    main()
