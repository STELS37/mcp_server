"""SSH client for secure connections to experimental VPS."""
import asyncio
import logging
import os
import re
import time
from dataclasses import dataclass, field
from typing import Optional, List, Dict, Any, Tuple
from pathlib import Path
import json

import asyncssh
from asyncssh import SSHClientConnection, SSHClientProcess, SSHCompletedProcess

from mcp_server.core.settings import get_settings, SSHSettings

logger = logging.getLogger(__name__)


@dataclass
class SSHResult:
    """Result of an SSH command execution."""
    stdout: str
    stderr: str
    exit_code: int
    command: str
    duration: float
    user: Optional[str] = None
    working_dir: Optional[str] = None
    timestamp: str = field(default_factory=lambda: time.strftime("%Y-%m-%d %H:%M:%S"))
    truncated: bool = False
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "stdout": self.stdout,
            "stderr": self.stderr,
            "exit_code": self.exit_code,
            "command": self.command,
            "duration": round(self.duration, 3),
            "user": self.user,
            "working_dir": self.working_dir,
            "timestamp": self.timestamp,
            "truncated": self.truncated,
        }


@dataclass
class CommandLog:
    """Log entry for command execution."""
    timestamp: str
    user: str
    tool_name: str
    parameters: Dict[str, Any]
    result: str
    exit_code: int
    duration: float
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "timestamp": self.timestamp,
            "user": self.user,
            "tool_name": self.tool_name,
            "parameters": self.parameters,
            "result": self.result,
            "exit_code": self.exit_code,
            "duration": round(self.duration, 3),
        }


class SSHClient:
    """Async SSH client with connection pooling and safety checks."""
    
    def __init__(self, settings: Optional[SSHSettings] = None):
        self.settings = settings or get_settings().ssh
        self._connection: Optional[SSHClientConnection] = None
        self._lock = asyncio.Lock()
        self._connected = False
        self._last_activity: float = 0
        self._command_log: List[CommandLog] = []
        self._max_log_entries = 1000
        
        # Load dangerous commands and patterns
        self.dangerous_commands = get_settings().security.dangerous_commands
        self.dangerous_patterns = get_settings().security.dangerous_patterns
        
    async def connect(self) -> bool:
        """Establish SSH connection."""
        async with self._lock:
            if self._connected and self._connection:
                try:
                    # Test connection
                    await asyncio.wait_for(
                        self._connection.run("echo alive", check=True),
                        timeout=5
                    )
                    return True
                except Exception:
                    self._connected = False
                    self._connection = None
            
            try:
                # Load private key
                key_path = Path(self.settings.private_key_path)
                if not key_path.exists():
                    raise FileNotFoundError(f"SSH key not found: {key_path}")
                
                private_key = await asyncio.to_thread(
                    self._load_private_key,
                    key_path,
                    self.settings.private_key_passphrase
                )
                
                # Connect
                self._connection = await asyncssh.connect(
                    self.settings.host,
                    port=self.settings.port,
                    username=self.settings.user,
                    private_key=private_key,
                    known_hosts=None,  # In production, use known_hosts
                    connect_timeout=self.settings.connection_timeout,
                    keepalive_interval=self.settings.keepalive_interval,
                )
                
                self._connected = True
                self._last_activity = time.time()
                logger.info(f"SSH connected to {self.settings.host}")
                return True
                
            except Exception as e:
                logger.error(f"SSH connection failed: {e}")
                self._connected = False
                self._connection = None
                raise
    
    def _load_private_key(self, key_path: Path, passphrase: Optional[str] = None):
        """Load private key from file."""
        import asyncssh
        
        with open(key_path, "rb") as f:
            key_data = f.read()
        
        try:
            # Try without passphrase first
            return asyncssh.import_private_key(key_data)
        except asyncssh.KeyImportError:
            # Try with passphrase
            if passphrase:
                return asyncssh.import_private_key(key_data, passphrase)
            raise
    
    async def disconnect(self):
        """Close SSH connection."""
        async with self._lock:
            if self._connection:
                self._connection.close()
                try:
                    await asyncio.wait_for(self._connection.wait_closed(), timeout=5)
                except asyncio.TimeoutError:
                    pass
                self._connection = None
                self._connected = False
                logger.info("SSH disconnected")
    
    @property
    def is_connected(self) -> bool:
        """Check if connection is active."""
        return self._connected and self._connection is not None
    
    def is_dangerous_command(self, command: str) -> Tuple[bool, List[str]]:
        """Check if command is potentially dangerous."""
        warnings = []
        is_dangerous = False
        
        # Check command name
        cmd_parts = command.strip().split()
        if cmd_parts:
            base_cmd = cmd_parts[0].split("/")[-1]  # Get base command name
            if base_cmd in self.dangerous_commands:
                is_dangerous = True
                warnings.append(f"Command '{base_cmd}' requires confirmation")
        
        # Check patterns
        for pattern in self.dangerous_patterns:
            if pattern.lower() in command.lower():
                is_dangerous = True
                warnings.append(f"Pattern '{pattern}' detected")
        
        return is_dangerous, warnings
    
    async def execute(
        self,
        command: str,
        timeout: Optional[int] = None,
        working_dir: Optional[str] = None,
        env: Optional[Dict[str, str]] = None,
        use_sudo: bool = False,
        user: str = "unknown",
        require_confirm: bool = False,
        confirm: bool = False,
    ) -> SSHResult:
        """Execute a command over SSH with safety checks."""
        start_time = time.time()
        timeout = timeout or self.settings.command_timeout
        
        # Check for dangerous command
        is_dangerous, warnings = self.is_dangerous_command(command)
        
        if is_dangerous and not confirm:
            return SSHResult(
                stdout="",
                stderr=f"DANGEROUS COMMAND DETECTED\n" + "\n".join(warnings) + "\n\nSet confirm=true to execute.",
                exit_code=126,  # Command cannot execute
                command=command,
                duration=time.time() - start_time,
                user=user,
                working_dir=working_dir,
            )
        
        # Ensure connection
        if not self.is_connected:
            await self.connect()
        
        # Build full command
        full_command = command
        if use_sudo:
            full_command = f"sudo {command}"
        if working_dir:
            full_command = f"cd {working_dir} && {full_command}"
        if env:
            env_str = " ".join(f"{k}={v}" for k, v in env.items())
            full_command = f"export {env_str} && {full_command}"
        
        try:
            # Execute with timeout
            result = await asyncio.wait_for(
                self._connection.run(full_command, check=False),
                timeout=timeout
            )
            
            # Truncate output if needed
            max_size = self.settings.max_output_size
            stdout = result.stdout[:max_size] if len(result.stdout) > max_size else result.stdout
            stderr = result.stderr[:max_size] if len(result.stderr) > max_size else result.stderr
            truncated = len(result.stdout) > max_size or len(result.stderr) > max_size
            
            ssh_result = SSHResult(
                stdout=stdout,
                stderr=stderr,
                exit_code=result.exit_status,
                command=command,
                duration=time.time() - start_time,
                user=user,
                working_dir=working_dir,
                truncated=truncated,
            )
            
            # Log the command
            self._log_command(
                user=user,
                tool_name="run_command",
                parameters={"command": command, "sudo": use_sudo},
                result="success" if result.exit_status == 0 else "failed",
                exit_code=result.exit_status,
                duration=ssh_result.duration,
            )
            
            return ssh_result
            
        except asyncio.TimeoutError:
            error_msg = f"Command timed out after {timeout} seconds"
            logger.error(error_msg)
            
            self._log_command(
                user=user,
                tool_name="run_command",
                parameters={"command": command, "sudo": use_sudo},
                result="timeout",
                exit_code=-1,
                duration=timeout,
            )
            
            return SSHResult(
                stdout="",
                stderr=error_msg,
                exit_code=-1,
                command=command,
                duration=timeout,
                user=user,
                working_dir=working_dir,
            )
            
        except Exception as e:
            logger.error(f"SSH execute error: {e}")
            
            self._log_command(
                user=user,
                tool_name="run_command",
                parameters={"command": command, "sudo": use_sudo},
                result=str(e),
                exit_code=-1,
                duration=time.time() - start_time,
            )
            
            return SSHResult(
                stdout="",
                stderr=str(e),
                exit_code=-1,
                command=command,
                duration=time.time() - start_time,
                user=user,
                working_dir=working_dir,
            )
    
    async def read_file(
        self,
        path: str,
        user: str = "unknown",
    ) -> SSHResult:
        """Read a file from the remote server."""
        # Use cat to read file
        command = f"cat {path}"
        return await self.execute(command, user=user)
    
    async def write_file(
        self,
        path: str,
        content: str,
        user: str = "unknown",
        use_sudo: bool = False,
    ) -> SSHResult:
        """Write content to a file on the remote server."""
        # Escape content for shell
        escaped_content = content.replace("'", "'\\''")
        command = f"echo '{escaped_content}' > {path}"
        return await self.execute(command, user=user, use_sudo=use_sudo)
    
    async def list_directory(
        self,
        path: str,
        user: str = "unknown",
        long_format: bool = True,
    ) -> SSHResult:
        """List directory contents."""
        cmd = "ls -la" if long_format else "ls -a"
        command = f"{cmd} {path}"
        return await self.execute(command, user=user)
    
    async def ping_host(
        self,
        host: str,
        count: int = 3,
        user: str = "unknown",
    ) -> SSHResult:
        """Ping a host from the remote server."""
        command = f"ping -c {count} {host}"
        return await self.execute(command, user=user)
    
    async def get_system_info(self, user: str = "unknown") -> Dict[str, Any]:
        """Get system information from the remote server."""
        info = {}
        
        # Get OS info
        result = await self.execute("cat /etc/os-release", user=user)
        if result.exit_code == 0:
            info["os_release"] = result.stdout
        
        # Get uname
        result = await self.execute("uname -a", user=user)
        if result.exit_code == 0:
            info["uname"] = result.stdout.strip()
        
        # Get hostname
        result = await self.execute("hostname", user=user)
        if result.exit_code == 0:
            info["hostname"] = result.stdout.strip()
        
        # Get uptime
        result = await self.execute("uptime", user=user)
        if result.exit_code == 0:
            info["uptime"] = result.stdout.strip()
        
        # Get memory info
        result = await self.execute("free -h", user=user)
        if result.exit_code == 0:
            info["memory"] = result.stdout
        
        # Get disk usage
        result = await self.execute("df -h", user=user)
        if result.exit_code == 0:
            info["disk"] = result.stdout
        
        return info
    
    def _log_command(
        self,
        user: str,
        tool_name: str,
        parameters: Dict[str, Any],
        result: str,
        exit_code: int,
        duration: float,
    ):
        """Log command execution."""
        log_entry = CommandLog(
            timestamp=time.strftime("%Y-%m-%d %H:%M:%S"),
            user=user,
            tool_name=tool_name,
            parameters=parameters,
            result=result,
            exit_code=exit_code,
            duration=duration,
        )
        
        self._command_log.append(log_entry)
        
        # Keep log size manageable
        if len(self._command_log) > self._max_log_entries:
            self._command_log = self._command_log[-self._max_log_entries:]
        
        # Also write to file if logging is enabled
        if get_settings().logging.log_tool_calls:
            logger.info(f"Tool call: {log_entry.to_dict()}")
    
    def get_command_log(self, limit: int = 100) -> List[Dict[str, Any]]:
        """Get command log entries."""
        return [entry.to_dict() for entry in self._command_log[-limit:]]
    
    async def __aenter__(self):
        """Async context manager entry."""
        await self.connect()
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit."""
        await self.disconnect()
