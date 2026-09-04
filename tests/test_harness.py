"""
Honor Agent - Test Harness & Security Guardrail Test Matrix.

Verifies:
1. Security guardrails (path traversal attacks, destructive command interception, command whitelist)
2. Core AgentRunner execution (file management sandbox, system telemetry retrieval, error resiliency)
3. Bot Gateway asynchronous queue dispatch and resilience
"""

import os
import sys
import json
import shutil
import asyncio
import tempfile
import unittest
from pathlib import Path

# Ensure project root is in python module search path
REPO_ROOT = Path(__file__).parent.parent.resolve()
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from core.guardrails import GuardrailsValidator, GuardrailViolationError, RiskTier
from core.agent_runner import AgentRunner
from bot_gateway import BotGateway


class TestGuardrails(unittest.TestCase):
    """Test suite validating boundary constraints and injection defenses."""

    def setUp(self):
        self.validator = GuardrailsValidator()

    def test_path_traversal_detection(self):
        """Verify that directory traversal attempts to system roots are blocked."""
        bad_paths = [
            r"..\..\..\..\Windows\System32",
            r"C:\Windows\System32\drivers\etc\hosts",
            r"E:\ClaudeCode\..\..\..\Windows",
        ]
        for p in bad_paths:
            ok, reason = self.validator.validate_path(p, is_write=False)
            self.assertFalse(ok, f"Expected path to be blocked: {p}")

    def test_sensitive_directory_write_protection(self):
        """Verify that write operations into OS sensitive directories are rejected."""
        forbidden_writes = [
            r"C:\Windows\System32\test.dll",
            r"C:\Program Files\Windows Defender\config.json",
            r"C:\Users\26502\.ssh\id_rsa",
            r"C:\Users\26502\.aws\credentials",
        ]
        for target in forbidden_writes:
            ok, reason = self.validator.validate_path(target, is_write=True)
            self.assertFalse(ok, f"Expected write to be blocked: {target}")

    def test_destructive_command_interception(self):
        """Verify that destructive shell commands trigger immediate rejection."""
        dangerous_commands = [
            "format C: /fs:NTFS",
            "rmdir /s /q E:\\target",
            "del /s /f /q C:\\Users",
            "rm -rf /",
            "diskpart /s script.txt",
            "shutdown /s /t 0",
            "powershell -encodedcommand dGVzdA==",
            ":(){ :|:& };:",
        ]
        for cmd in dangerous_commands:
            ok, reason, tier = self.validator.validate_command(cmd)
            self.assertFalse(ok, f"Dangerous command passed validation: {cmd}")
            self.assertEqual(tier, RiskTier.TIER_3_EXECUTION)

    def test_whitelist_command_approval(self):
        """Verify that safe diagnostic and launcher commands pass whitelist checks."""
        safe_commands = [
            "dir",
            "echo hello world",
            "tasklist",
            "netstat -ano",
            "ping 127.0.0.1",
            "start notepad",
            "python --version",
        ]
        for cmd in safe_commands:
            ok, reason, _ = self.validator.validate_command(cmd)
            self.assertTrue(ok, f"Legitimate command was incorrectly blocked: {cmd} ({reason})")

    def test_unregistered_binary_rejection(self):
        """Verify that commands not present in whitelist are rejected by default."""
        alien_commands = [
            "nc -lvp 4444",
            "nmap -sS 192.168.1.1",
            "mimikatz.exe",
            "custom_backdoor.bat",
        ]
        for cmd in alien_commands:
            ok, reason, _ = self.validator.validate_command(cmd)
            self.assertFalse(ok, f"Unregistered command was allowed: {cmd}")


class TestAgentRunner(unittest.TestCase):
    """Test suite validating core headless runner tool execution and error handling."""

    def setUp(self):
        self.temp_dir = tempfile.mkdtemp(prefix="honor_agent_test_")
        self.runner = AgentRunner()

    def tearDown(self):
        if os.path.exists(self.temp_dir):
            shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_system_status_telemetry(self):
        """Verify telemetry tool returns structured JSON with essential host fields."""
        raw_status = self.runner.execute_tool("get_system_status", {})
        status = json.loads(raw_status)
        self.assertIn("os", status)
        self.assertIn("machine", status)
        self.assertIn("python", status)
        self.assertIn("disk_free_gb", status)

    def test_safe_file_lifecycle(self):
        """Verify writing, reading, listing, and deleting files within allowed path."""
        test_file = Path(self.temp_dir) / "test_artifact.txt"
        test_content = "Honor Agent Test Verification Content"

        # 1. Write file
        write_res = self.runner.execute_tool("write_file", {"path": str(test_file), "content": test_content})
        self.assertIn("Successfully wrote", write_res)
        self.assertTrue(test_file.exists())

        # 2. Read file
        read_res = self.runner.execute_tool("read_file", {"path": str(test_file)})
        self.assertEqual(read_res, test_content)

        # 3. List directory
        list_res = self.runner.execute_tool("list_directory", {"path": self.temp_dir})
        self.assertIn("test_artifact.txt", list_res)

        # 4. Delete file
        del_res = self.runner.execute_tool("delete_file", {"path": str(test_file)})
        self.assertIn("Successfully deleted", del_res)
        self.assertFalse(test_file.exists())

    def test_guardrail_enforcement_in_runner(self):
        """Verify runner intercepts destructive command and returns clean alert without crashing."""
        result = self.runner.execute_tool("run_command", {"command": "format D:"})
        self.assertIn("[Guardrail Intercepted]", result)

    def test_unknown_tool_graceful_handling(self):
        """Verify calling an unregistered tool returns an informative error string."""
        result = self.runner.execute_tool("non_existent_tool", {})
        self.assertIn("Unknown tool", result)


class TestBotGateway(unittest.IsolatedAsyncioTestCase):
    """Test suite validating asynchronous bot gateway handling and mock execution."""

    async def asyncSetUp(self):
        self.gateway = BotGateway(token=None)

    async def test_help_command(self):
        """Verify /help returns standard command overview."""
        res = await self.gateway.handle_command("/help")
        self.assertIn("/status", res)
        self.assertIn("/run", res)

    async def test_status_command(self):
        """Verify /status returns parsed host status."""
        res = await self.gateway.handle_command("/status")
        data = json.loads(res)
        self.assertIn("os", data)
        self.assertIn("disk_free_gb", data)

    async def test_run_command_safe(self):
        """Verify whitelisted /run command executes properly."""
        res = await self.gateway.handle_command("/run echo TestGatewaySafe")
        self.assertIn("TestGatewaySafe", res)

    async def test_run_command_blocked(self):
        """Verify dangerous /run command is intercepted by guardrail."""
        res = await self.gateway.handle_command("/run del /s /f C:\\")
        self.assertIn("[Guardrail Alert]", res)

    async def test_mock_session_execution(self):
        """Verify full dry-run mock session processes all test scenarios."""
        scenarios = ["/help", "/status", "/run echo hello"]
        results = await self.gateway.run_mock_session(test_inputs=scenarios)
        self.assertEqual(len(results), 3)
        self.assertIn("/status", results[0]["output"])
        self.assertIn("os", results[1]["output"])
        self.assertIn("hello", results[2]["output"])


if __name__ == "__main__":
    unittest.main()
