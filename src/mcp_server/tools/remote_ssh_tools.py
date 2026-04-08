"""Remote SSH Tools - Multi-server SSH administration."""
import asyncio
import json
import logging
import time
import base64
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional

import asyncssh
from asyncssh import SSHClientConnection

logger = logging.getLogger(__name__)


@dataclass
class SSHTarget:
    name: str
    host: str
    port: int = 22
    user: str = "root"
    key_path: Optional[str] = None
    password: Optional[str] = None
    connected: bool = False
    last_activity: float = 0.0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "host": self.host,
            "port": self.port,
            "user": self.user,
            "connected": self.connected,
        }


class RemoteSSHPool:
    """SSH connection pool with loop-aware context handling."""

    def __init__(self) -> None:
        self._connections: Dict[str, SSHClientConnection] = {}
        self._targets: Dict[str, SSHTarget] = {}
        self._locks: Dict[str, asyncio.Lock] = {}
        self._config_path = Path("/a0/usr/projects/mcp_server/.runtime/ssh_targets.json")
        self._loop_owner: Optional[int] = None
        self._load_targets()
        self._refresh_locks()

    def _load_targets(self) -> None:
        """Load SSH targets from config file."""
        if not self._config_path.exists():
            return
        try:
            data = json.loads(self._config_path.read_text())
            for name, target in data.items():
                self._targets[name] = SSHTarget(
                    name=name,
                    host=target.get("host", ""),
                    port=int(target.get("port", 22)),
                    user=target.get("user", "root"),
                    key_path=target.get("key_path"),
                    password=target.get("password"),
                )
        except Exception as exc:
            logger.error("Load targets error: %s", exc)

    def _save_targets(self) -> None:
        """Save SSH targets to config file."""
        self._config_path.parent.mkdir(parents=True, exist_ok=True)
        data = {
            name: {
                "host": t.host,
                "port": t.port,
                "user": t.user,
                "key_path": t.key_path,
                "password": t.password,
            }
            for name, t in self._targets.items()
        }
        self._config_path.write_text(json.dumps(data, indent=2))

    def _refresh_locks(self) -> None:
        """Refresh asyncio locks for current loop."""
        self._locks = {name: asyncio.Lock() for name in self._targets}

    async def _ensure_loop_context(self) -> None:
        """Ensure we are in correct asyncio loop context."""
        try:
            loop_id = id(asyncio.get_running_loop())
        except RuntimeError:
            # No running loop, skip context check
            return
        
        if self._loop_owner == loop_id:
            return
        
        # Close old connections from different loop
        for conn in list(self._connections.values()):
            try:
                conn.close()
            except Exception:
                pass
        
        self._connections = {}
        self._loop_owner = loop_id
        self._refresh_locks()
        
        for target in self._targets.values():
            target.connected = False

    def list_targets(self) -> List[Dict[str, Any]]:
        """List all SSH targets."""
        return [t.to_dict() for t in self._targets.values()]

    def add_target(
        self,
        name: str,
        host: str,
        port: int = 22,
        user: str = "root",
        key_path: Optional[str] = None,
        password: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Add new SSH target."""
        if name in self._targets:
            return {"error": f"Target exists: {name}"}
        self._targets[name] = SSHTarget(
            name=name,
            host=host,
            port=port,
            user=user,
            key_path=key_path,
            password=password,
        )
        self._locks[name] = asyncio.Lock()
        self._save_targets()
        return {"success": True, "target": name}

    def remove_target(self, name: str) -> Dict[str, Any]:
        """Remove SSH target."""
        if name not in self._targets:
            return {"error": f"Target not found: {name}"}
        if name in self._connections:
            try:
                self._connections[name].close()
            except Exception:
                pass
            del self._connections[name]
        del self._targets[name]
        if name in self._locks:
            del self._locks[name]
        self._save_targets()
        return {"success": True, "removed": name}

    async def connect(self, name: str) -> Dict[str, Any]:
        """Connect to SSH target."""
        await self._ensure_loop_context()
        
        if name not in self._targets:
            return {"error": f"Target not found: {name}"}
        
        target = self._targets[name]
        lock = self._locks.get(name)
        if not lock:
            return {"error": f"No lock for target: {name}"}
        
        async with lock:
            try:
                connect_kwargs = {
                    "host": target.host,
                    "port": target.port,
                    "username": target.user,
                    "known_hosts": None,
                    "connect_timeout": 30,
                }
                
                if target.key_path and Path(target.key_path).exists():
                    connect_kwargs["client_keys"] = [target.key_path]
                elif target.password:
                    connect_kwargs["password"] = target.password
                
                conn = await asyncssh.connect(**connect_kwargs)
                self._connections[name] = conn
                target.connected = True
                target.last_activity = time.time()
                return {"success": True, "target": name, "host": target.host}
            except Exception as e:
                return {"error": str(e)}

    async def disconnect(self, name: str) -> Dict[str, Any]:
        """Disconnect from SSH target."""
        await self._ensure_loop_context()
        
        if name not in self._targets:
            return {"error": f"Target not found: {name}"}
        if name not in self._connections:
            return {"success": True, "already disconnected": name}
        
        lock = self._locks.get(name)
        if lock:
            async with lock:
                try:
                    self._connections[name].close()
                    del self._connections[name]
                    self._targets[name].connected = False
                    return {"success": True, "disconnected": name}
                except Exception as e:
                    return {"error": str(e)}
        else:
            try:
                self._connections[name].close()
                del self._connections[name]
                self._targets[name].connected = False
                return {"success": True, "disconnected": name}
            except Exception as e:
                return {"error": str(e)}

    async def execute(self, name: str, command: str, timeout: int = 60) -> Dict[str, Any]:
        """Execute command on SSH target."""
        await self._ensure_loop_context()
        
        if name not in self._targets:
            return {"error": f"Target not found: {name}"}
        
        # Auto-connect if not connected
        if name not in self._connections:
            r = await self.connect(name)
            if "error" in r:
                return r
        
        lock = self._locks.get(name)
        if not lock:
            return {"error": f"No lock for target: {name}"}
        
        async with lock:
            try:
                result = await asyncio.wait_for(
                    self._connections[name].run(command, check=False),
                    timeout=timeout,
                )
                self._targets[name].last_activity = time.time()
                return {
                    "success": True,
                    "target": name,
                    "command": command,
                    "stdout": result.stdout,
                    "stderr": result.stderr,
                    "exit_code": result.exit_status,
                }
            except asyncio.TimeoutError:
                return {"error": f"Command timeout after {timeout}s"}
            except Exception as e:
                return {"error": str(e)}

    async def ping(self, name: str) -> Dict[str, Any]:
        """Test SSH connection."""
        r = await self.execute(name, "echo SSH_OK", timeout=10)
        if "error" in r:
            return {"success": False, "error": r["error"]}
        return {"success": True, "target": name}

    async def get_status(self, name: str) -> Dict[str, Any]:
        """Get remote server status."""
        await self._ensure_loop_context()
        
        if name not in self._targets:
            return {"error": f"Target not found: {name}"}
        
        results = {}
        commands = {
            "hostname": "hostname",
            "uptime": "uptime -p",
            "os": "cat /etc/os-release | head -2",
            "memory": "free -h | head -2",
            "disk": "df -h / | tail -1",
        }
        
        for key, cmd in commands.items():
            r = await self.execute(name, cmd, timeout=10)
            if "error" not in r:
                results[key] = r["stdout"].strip()
            else:
                results[key] = f"error: {r['error'][:30]}"
        
        return {"success": True, "target": name, "status": results}

    async def copy_to(
        self,
        name: str,
        local_path: str,
        remote_path: str,
    ) -> Dict[str, Any]:
        """Upload file to remote server."""
        await self._ensure_loop_context()
        
        if name not in self._targets:
            return {"error": f"Target not found: {name}"}
        if name not in self._connections:
            r = await self.connect(name)
            if "error" in r:
                return r
        
        lock = self._locks.get(name)
        if not lock:
            return {"error": f"No lock for target: {name}"}
        
        async with lock:
            try:
                await asyncssh.scp(
                    local_path,
                    (self._connections[name], remote_path),
                )
                self._targets[name].last_activity = time.time()
                return {
                    "success": True,
                    "target": name,
                    "action": "upload",
                    "local": local_path,
                    "remote": remote_path,
                }
            except Exception as e:
                return {"error": str(e)}

    async def copy_from(
        self,
        name: str,
        remote_path: str,
        local_path: str,
    ) -> Dict[str, Any]:
        """Download file from remote server."""
        await self._ensure_loop_context()
        
        if name not in self._targets:
            return {"error": f"Target not found: {name}"}
        if name not in self._connections:
            r = await self.connect(name)
            if "error" in r:
                return r
        
        lock = self._locks.get(name)
        if not lock:
            return {"error": f"No lock for target: {name}"}
        
        async with lock:
            try:
                await asyncssh.scp(
                    (self._connections[name], remote_path),
                    local_path,
                )
                self._targets[name].last_activity = time.time()
                return {
                    "success": True,
                    "target": name,
                    "action": "download",
                    "remote": remote_path,
                    "local": local_path,
                }
            except Exception as e:
                return {"error": str(e)}


# Global pool instance
_ssh_pool: Optional[RemoteSSHPool] = None


def get_ssh_pool() -> RemoteSSHPool:
    """Get global SSH pool instance."""
    global _ssh_pool
    if _ssh_pool is None:
        _ssh_pool = RemoteSSHPool()
    return _ssh_pool
