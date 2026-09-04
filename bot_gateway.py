"""
Honor Agent - Remote Bot Gateway.

Provides multi-channel remote access (Telegram Bot & extensible adapters)
enabling mobile triggering of desktop automation tasks, status monitoring,
and natural language query execution with built-in queue resilience and guardrails.
"""

import os
import sys
import time
import json
import asyncio
import argparse
import logging
from typing import Optional, Dict, Any, List
from pathlib import Path

# Ensure repo root is on sys.path
REPO_ROOT = Path(__file__).parent.resolve()
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from core.agent_runner import AgentRunner
from core.guardrails import GuardrailViolationError

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s"
)
logger = logging.getLogger("BotGateway")


class BotGateway:
    """
    Asynchronous gateway handling remote message queues, fault-tolerant retry loops,
    and dispatching requests into the core AgentRunner.
    """

    def __init__(self, token: Optional[str] = None, proxy: Optional[str] = None):
        self.token = token or os.environ.get("TELEGRAM_BOT_TOKEN")
        self.proxy = proxy or os.environ.get("TELEGRAM_PROXY")
        self.runner = AgentRunner()
        self.queue: asyncio.Queue = asyncio.Queue()
        self._is_running = False
        self.backoff_seconds = 2

    async def handle_command(self, text: str) -> str:
        """Parse incoming command text and dispatch to AgentRunner."""
        clean_text = text.strip()

        if clean_text == "/start" or clean_text == "/help":
            return (
                "Honor Agent Remote Gateway:\n"
                "/status - Check PC host health (OS, disk space, runtime)\n"
                "/run <command> - Execute a whitelisted system command\n"
                "/help - Show this instruction menu\n"
                "Or simply send any natural language prompt to ask the agent."
            )

        if clean_text == "/status":
            return self.runner.execute_tool("get_system_status", {})

        if clean_text.startswith("/run "):
            cmd = clean_text[5:].strip()
            try:
                result = self.runner.execute_tool("run_command", {"command": cmd, "silent": True})
                if "[Guardrail Intercepted]" in result:
                    return f"[Guardrail Alert] {result}"
                return f"[Result]\n{result}"
            except GuardrailViolationError as ge:
                return f"[Guardrail Alert] Command rejected: {ge}"
            except Exception as e:
                return f"[Execution Error] {e}"

        # Natural language query: stream tokens into a combined response
        messages = [{"role": "user", "content": clean_text}]
        response_text = ""
        try:
            for event in self.runner.run_stream(messages):
                if event.get("t") == "tok":
                    response_text += event.get("v", "")
                elif event.get("t") == "err":
                    response_text += f"\n[Stream Error]: {event.get('v')}"
            return response_text if response_text else "(No response generated)"
        except Exception as e:
            return f"[Agent Error]: {e}"

    async def _process_queue(self):
        """Worker consuming queued inbound messages sequentially to prevent race conditions."""
        while self._is_running:
            try:
                item = await asyncio.wait_for(self.queue.get(), timeout=1.0)
                sender_id, text, callback = item
                logger.info(f"Processing message from sender '{sender_id}': {text}")
                reply = await self.handle_command(text)
                if callback:
                    if asyncio.iscoroutinefunction(callback):
                        await callback(sender_id, reply)
                    else:
                        callback(sender_id, reply)
                self.queue.task_done()
            except asyncio.TimeoutError:
                continue
            except Exception as e:
                logger.error(f"Error while processing message: {e}")

    async def run_mock_session(self, test_inputs: Optional[List[str]] = None) -> List[Dict[str, str]]:
        """
        Execute simulated incoming messages in dry-run/test mode without network dependencies.
        Returns the list of processed input-output pairs.
        """
        inputs = test_inputs or [
            "/status",
            "/run dir",
            "/run format C:",
            "/help",
            "Check current system status"
        ]

        results = []
        logger.info(f"Running mock gateway session with {len(inputs)} test scenarios...")

        for inp in inputs:
            logger.info(f"Incoming Mock Message: {inp}")
            output = await self.handle_command(inp)
            logger.info(f"Gateway Response:\n{output}\n" + "-" * 40)
            results.append({"input": inp, "output": output})

        return results

    async def start_polling(self):
        """
        Start resilient Telegram long-polling loop with exponential backoff on network failures.
        """
        if not self.token:
            logger.error("No TELEGRAM_BOT_TOKEN provided. Use --mock mode for offline testing.")
            return

        try:
            import requests
        except ImportError:
            logger.error("requests library is required for Telegram polling.")
            return

        self._is_running = True
        asyncio.create_task(self._process_queue())

        api_url = f"https://api.telegram.org/bot{self.token}"
        proxies = {"https": self.proxy, "http": self.proxy} if self.proxy else None
        last_offset = 0

        logger.info("Starting Telegram Bot long-polling loop...")

        while self._is_running:
            try:
                # Long polling request with 20s timeout
                resp = requests.get(
                    f"{api_url}/getUpdates",
                    params={"offset": last_offset + 1, "timeout": 20},
                    proxies=proxies,
                    timeout=30
                )
                if resp.status_code != 200:
                    logger.warning(f"Telegram API returned status {resp.status_code}: {resp.text}")
                    await asyncio.sleep(self.backoff_seconds)
                    self.backoff_seconds = min(self.backoff_seconds * 2, 60)
                    continue

                # Reset backoff on success
                self.backoff_seconds = 2
                data = resp.json()

                for update in data.get("result", []):
                    update_id = update["update_id"]
                    last_offset = max(last_offset, update_id)

                    msg = update.get("message", {})
                    chat_id = msg.get("chat", {}).get("id")
                    text = msg.get("text", "")

                    if chat_id and text:
                        def send_reply(cid, reply_txt):
                            requests.post(
                                f"{api_url}/sendMessage",
                                json={"chat_id": cid, "text": reply_txt},
                                proxies=proxies,
                                timeout=10
                            )

                        await self.queue.put((chat_id, text, send_reply))

            except Exception as e:
                logger.warning(f"Connection error in polling loop: {e}. Backing off {self.backoff_seconds}s...")
                await asyncio.sleep(self.backoff_seconds)
                self.backoff_seconds = min(self.backoff_seconds * 2, 60)


def main():
    parser = argparse.ArgumentParser(description="Honor Agent - Remote Bot Gateway")
    parser.add_argument("--mock", action="store_true", help="Run in mock/dry-run test mode")
    parser.add_argument("--token", type=str, help="Telegram Bot Token")
    parser.add_argument("--proxy", type=str, help="Optional HTTP/SOCKS proxy URL")
    args = parser.parse_args()

    gateway = BotGateway(token=args.token, proxy=args.proxy)

    if args.mock:
        asyncio.run(gateway.run_mock_session())
    else:
        try:
            asyncio.run(gateway.start_polling())
        except KeyboardInterrupt:
            logger.info("Bot Gateway stopped by user.")


if __name__ == "__main__":
    main()
