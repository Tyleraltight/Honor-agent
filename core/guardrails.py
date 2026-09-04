"""
Honor Agent - Security Guardrails & Risk-Tiered Command Filter.

Provides multi-layer security validation for desktop agent actions:
1. Path traversal & sensitive directory access prevention
2. Command whitelist & destructive argument interception
3. Risk tier categorization for auditing and privilege enforcement
"""

import os
import re
import shlex
from enum import Enum
from pathlib import Path
from typing import Tuple, List, Optional


class RiskTier(Enum):
    TIER_1_SAFE_QUERY = "tier_1_safe_query"
    TIER_2_CONTROLLED_WRITE = "tier_2_controlled_write"
    TIER_3_EXECUTION = "tier_3_execution"


class GuardrailViolationError(PermissionError):
    """Raised when an operation violates security guardrails."""
    def __init__(self, message: str, tier: RiskTier, details: Optional[dict] = None):
        super().__init__(message)
        self.tier = tier
        self.details = details or {}


class GuardrailsValidator:
    """Security engine enforcing least-privilege boundaries on agent operations."""

    # Sensitive paths that the agent is strictly forbidden from modifying or writing to
    SENSITIVE_DIR_PATTERNS = [
        re.compile(r"^[a-zA-Z]:\\windows", re.IGNORECASE),
        re.compile(r"^[a-zA-Z]:\\program files\\windows defender", re.IGNORECASE),
        re.compile(r"[\\/]\.ssh([\\/]|$)", re.IGNORECASE),
        re.compile(r"[\\/]\.aws([\\/]|$)", re.IGNORECASE),
        re.compile(r"[\\/]\.gnupg([\\/]|$)", re.IGNORECASE),
        re.compile(r"^[a-zA-Z]:\\\$recycle\.bin", re.IGNORECASE),
        re.compile(r"^[a-zA-Z]:\\boot", re.IGNORECASE),
    ]

    # Whitelist of allowed executable commands for system diagnostics and productivity
    COMMAND_WHITELIST = {
        "dir", "echo", "type", "tasklist", "netstat", "ping", "ipconfig",
        "python", "pythonw", "git", "start", "calc", "notepad", "code",
        "whoami", "hostname", "date", "time", "findstr", "curl", "where"
    }

    # Explicit blacklist patterns for destructive or privilege escalation commands
    DESTRUCTIVE_PATTERNS = [
        re.compile(r"\bformat\b", re.IGNORECASE),
        re.compile(r"\brmdir\s+/[sS]\b", re.IGNORECASE),
        re.compile(r"\bdel\s+.*(/s|/f|/q)\b", re.IGNORECASE),
        re.compile(r"\brm\s+-[a-zA-Z]*r[a-zA-Z]*f\b", re.IGNORECASE),
        re.compile(r"\bdiskpart\b", re.IGNORECASE),
        re.compile(r"\bbcdedit\b", re.IGNORECASE),
        re.compile(r"\bvssadmin\b", re.IGNORECASE),
        re.compile(r"\breg\s+(add|delete|import)\b", re.IGNORECASE),
        re.compile(r"\bshutdown\b", re.IGNORECASE),
        re.compile(r"\bpowershell.*(-enc|-encodedcommand)\b", re.IGNORECASE),
        re.compile(r":\s*\|\s*:\s*&\s*:", re.IGNORECASE),  # Fork bomb pattern
    ]

    def __init__(self, allowed_workspace_roots: Optional[List[Path]] = None):
        """
        Initialize validator with optional workspace root boundaries.
        If not specified, defaults to current working directory and user home.
        """
        self.allowed_roots = allowed_workspace_roots or [
            Path.cwd().resolve(),
            Path.home().resolve(),
            Path("E:/").resolve() if Path("E:/").exists() else Path.cwd().resolve()
        ]

    def validate_path(self, target_path: str, is_write: bool = False) -> Tuple[bool, str]:
        """
        Validate path to prevent directory traversal and unauthorized system modifications.
        Returns (is_valid, reason).
        """
        if not target_path or not str(target_path).strip():
            return False, "Target path cannot be empty"

        raw_str = str(target_path).strip()

        # Check raw string for directory traversal tricks
        if ".." in raw_str.replace("\\", "/").split("/"):
            resolved = Path(raw_str).resolve()
            resolved_str = str(resolved).lower()
            if re.match(r"^[a-z]:\\windows", resolved_str) or re.match(r"^[a-z]:\\?$", resolved_str):
                return False, f"Directory traversal to critical system location blocked: {raw_str}"

        try:
            resolved_path = Path(raw_str).resolve()
        except Exception as e:
            return False, f"Invalid path syntax: {e}"

        resolved_str = str(resolved_path)

        # Check against sensitive directories
        for pattern in self.SENSITIVE_DIR_PATTERNS:
            if pattern.search(resolved_str):
                if is_write:
                    return False, f"Write access to sensitive system directory is prohibited: {resolved_str}"
                # For critical paths like System32, block read as well
                if "windows\\system32" in resolved_str.lower():
                    return False, f"Access to system core directory is prohibited: {resolved_str}"

        return True, "Path validation passed"

    def validate_command(self, command_str: str) -> Tuple[bool, str, RiskTier]:
        """
        Validate shell commands against whitelist and destructive patterns.
        Returns (is_allowed, reason, risk_tier).
        """
        if not command_str or not command_str.strip():
            return False, "Command cannot be empty", RiskTier.TIER_3_EXECUTION

        clean_cmd = command_str.strip()

        # Check destructive regex patterns first
        for pattern in self.DESTRUCTIVE_PATTERNS:
            if pattern.search(clean_cmd):
                return False, f"Destructive command pattern detected: {pattern.pattern}", RiskTier.TIER_3_EXECUTION

        # Extract primary executable/command token
        # Handle Windows command chaining (&&, ||, ;, |)
        sub_commands = re.split(r"(&&|\|\||;|\|)", clean_cmd)
        
        for sub in sub_commands:
            sub = sub.strip()
            if not sub or sub in ("&&", "||", ";", "|"):
                continue

            # Tokenize sub-command safely
            try:
                tokens = shlex.split(sub, posix=False)
            except Exception:
                tokens = sub.split()

            if not tokens:
                continue

            base_binary = tokens[0].lower()
            for ext in (".exe", ".bat", ".cmd"):
                base_binary = base_binary.removesuffix(ext)

            # Validate against whitelist
            if base_binary not in self.COMMAND_WHITELIST:
                return (
                    False,
                    f"Command '{base_binary}' is not permitted by execution whitelist",
                    RiskTier.TIER_3_EXECUTION
                )

        return True, "Command validation passed whitelist inspection", RiskTier.TIER_3_EXECUTION

    def check_and_enforce_path(self, path_str: str, is_write: bool = False) -> Path:
        """Enforce path validation, raising GuardrailViolationError on failure."""
        ok, reason = self.validate_path(path_str, is_write=is_write)
        if not ok:
            tier = RiskTier.TIER_2_CONTROLLED_WRITE if is_write else RiskTier.TIER_1_SAFE_QUERY
            raise GuardrailViolationError(reason, tier=tier, details={"path": path_str})
        return Path(path_str).resolve()

    def check_and_enforce_command(self, command_str: str) -> str:
        """Enforce command validation, raising GuardrailViolationError on failure."""
        ok, reason, tier = self.validate_command(command_str)
        if not ok:
            raise GuardrailViolationError(reason, tier=tier, details={"command": command_str})
        return command_str
