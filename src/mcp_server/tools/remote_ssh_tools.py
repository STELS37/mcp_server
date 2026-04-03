"""Remote SSH Tools - Multi-server SSH administration."""
import asyncio
import logging
import time
import base64
import json
from dataclasses import dataclass
from typing import Optional, Dict, Any, List
from pathlib import Path

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
    last_activity: float = 0

    def to_dict(self) -> Dict[str, Any]:
        return {"name": self.name, "host": self.host, "port": self.port,
                "user": self.user, "connected": self.connected}

class RemoteSSHPool:
    def __init__(self):
        self._connections: Dict[str, SSHClientConnection] = {}
        self._targets: Dict[str, SSHTarget] = {}
        self._locks: Dict[str, asyncio.Lock] = {}
        self._config_path = Path("/a0/usr/projects/mcp_server/.runtime/ssh_targets.json")
        self._load_targets()

    def _load_targets(self):
        if self._config_path.exists():
            try:
                data = json.loads(self._config_path.read_text())
                for name, t in data.items():
                    self._targets[name] = SSHTarget(name=name, host=t.get("host",""),
                        port=t.get("port",22), user=t.get("user","root"),
                        key_path=t.get("key_path"), password=t.get("password"))
            except Exception as e:
                logger.error(f"Load targets error: {e}")

    def _save_targets(self):
        self._config_path.parent.mkdir(parents=True, exist_ok=True)
        data = {n: {"host": t.host, "port": t.port, "user": t.user,
                    "key_path": t.key_path, "password": t.password}
                for n, t in self._targets.items()}
        self._config_path.write_text(json.dumps(data, indent=2))

    def list_targets(self) -> List[Dict]:
        return [t.to_dict() for t in self._targets.values()]

    def add_target(self, name, host, port=22, user="root", key_path=None, password=None):
        if name in self._targets:
            return {"error": f"Target exists: {name}"}
        self._targets[name] = SSHTarget(name=name, host=host, port=port, user=user,
                                         key_path=key_path, password=password)
        self._locks[name] = asyncio.Lock()
        self._save_targets()
        return {"success": True, "target": name}

    def remove_target(self, name):
        if name not in self._targets:
            return {"error": f"Target not found: {name}"}
        if name in self._connections:
            self._connections[name].close()
            del self._connections[name]
        del self._targets[name]
        self._save_targets()
        return {"success": True, "removed": name}

    async def connect(self, name) -> Dict[str, Any]:
        if name not in self._targets:
            return {"error": f"Target not found: {name}"}
        target = self._targets[name]
        async with self._locks.get(name, asyncio.Lock()):
            try:
                if target.key_path and Path(target.key_path).exists():
                    conn = await asyncssh.connect(target.host, port=target.port,
                        username=target.user, client_keys=[target.key_path],
                        known_hosts=None, connect_timeout=30)
                elif target.password:
                    conn = await asyncssh.connect(target.host, port=target.port,
                        username=target.user, password=target.password,
                        known_hosts=None, connect_timeout=30)
                else:
                    conn = await asyncssh.connect(target.host, port=target.port,
                        username=target.user, known_hosts=None, connect_timeout=30)
                self._connections[name] = conn
                target.connected = True
                target.last_activity = time.time()
                return {"success": True, "target": name, "host": target.host}
            except Exception as e:
                return {"error": str(e)}

    async def execute(self, name, command, timeout=60) -> Dict[str, Any]:
        if name not in self._targets:
            return {"error": f"Target not found: {name}"}
        if name not in self._connections:
            r = await self.connect(name)
            if "error" in r: return r
        async with self._locks.get(name, asyncio.Lock()):
            try:
                result = await asyncio.wait_for(
                    self._connections[name].run(command, check=False), timeout=timeout)
                self._targets[name].last_activity = time.time()
                return {"success": True, "target": name, "command": command,
                        "stdout": result.stdout, "stderr": result.stderr,
                        "exit_code": result.exit_status}
            except Exception as e:
                return {"error": str(e)}

    async def ping(self, name) -> Dict[str, Any]:
        if name not in self._targets:
            return {"error": f"Target not found: {name}"}
        r = await self.execute(name, "echo SSH_OK", timeout=10)
        if "error" in r: return {"success": False, "error": r["error"]}
        return {"success": True, "target": name}

    async def get_status(self, name) -> Dict[str, Any]:
        if name not in self._targets:
            return {"error": f"Target not found: {name}"}
        cmds = {"hostname": "hostname", "uptime": "uptime",
                "mem": "free -h | head -2", "disk": "df -h | head -5"}
        results = {}
        for k, cmd in cmds.items():
            r = await self.execute(name, cmd, timeout=10)
            results[k] = r.get("stdout", "error") if "success" in r else "error"
        return {"success": True, "target": name, "host": self._targets[name].host, "status": results}

_ssh_pool = None

def get_ssh_pool():
    global _ssh_pool
    if _ssh_pool is None:
        _ssh_pool = RemoteSSHPool()
    return _ssh_pool
