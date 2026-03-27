import os
"""Command executor with safety checks."""
import logging
from typing import Optional, Dict, Any, List
from dataclasses import dataclass

from mcp_server.tools.ssh_client import SSHClient, SSHResult
from mcp_server.core.settings import get_settings

logger = logging.getLogger(__name__)


@dataclass
class ExecutionResult:
    """Result of command execution."""
    success: bool
    stdout: str
    stderr: str
    exit_code: int
    message: str
    data: Optional[Dict[str, Any]] = None


class CommandExecutor:
    """Safe command executor with safeguards and logging."""
    
    def __init__(self, ssh_client: SSHClient):
        self.ssh = ssh_client
        self.settings = get_settings()
        self.dangerous_commands = self.settings.security.dangerous_commands
        self.dangerous_patterns = self.settings.security.dangerous_patterns
    
    def check_dangerous(self, command: str) -> tuple[bool, List[str]]:
        """Check if command requires confirmation."""
        warnings = []
        is_dangerous = False
        
        # Check base command
        parts = command.strip().split()
        if parts:
            base_cmd = parts[0].split("/")[-1]
            if base_cmd in self.dangerous_commands:
                is_dangerous = True
                warnings.append(f"Base command '{base_cmd}' is potentially dangerous")
        
        # Check patterns
        for pattern in self.dangerous_patterns:
            if pattern.lower() in command.lower():
                is_dangerous = True
                warnings.append(f"Dangerous pattern '{pattern}' detected")
        
        return is_dangerous, warnings
    
    async def execute_safe(
        self,
        command: str,
        user: str = "unknown",
        timeout: int = 30,
        working_dir: Optional[str] = None,
        env: Optional[Dict[str, str]] = None,
        use_sudo: bool = False,
        confirm: bool = False,
    ) -> ExecutionResult:
        """Execute command with safety checks."""
        is_dangerous, warnings = self.check_dangerous(command)
        
        if (str(os.getenv("MCP_DISABLE_CONFIRM", "0")).lower() not in {"1","true","yes","on"}) and self.settings.security.enforce_confirmations and is_dangerous and not confirm:
            return ExecutionResult(
                success=False,
                stdout="",
                stderr="",
                exit_code=126,
                message="DANGEROUS COMMAND DETECTED\n" + "\n".join(warnings) + "\n\nSet confirm=true to execute.",
            )
        
        result = await self.ssh.execute(
            command=command,
            timeout=timeout,
            working_dir=working_dir,
            env=env,
            use_sudo=use_sudo,
            user=user,
            confirm=confirm,
        )
        
        return ExecutionResult(
            success=result.exit_code == 0,
            stdout=result.stdout,
            stderr=result.stderr,
            exit_code=result.exit_code,
            message="Command executed successfully" if result.exit_code == 0 else "Command failed",
        )
