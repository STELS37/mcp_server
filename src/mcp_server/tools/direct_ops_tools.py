"""Direct operations tools - fast structured layer for local server operations."""
import asyncio
import json
import os
import shutil
import subprocess
import tempfile
from pathlib import Path
from typing import Any, Dict, List, Optional
from dataclasses import dataclass


@dataclass
class ExtraToolDefinition:
    name: str
    description: str
    input_schema: Dict[str, Any]
    handler: callable
    dangerous: bool = False
    annotations: Optional[Dict[str, Any]] = None


def _ro(title: str) -> Dict[str, Any]:
    return {"title": title, "readOnlyHint": True, "destructiveHint": False, "idempotentHint": True, "openWorldHint": False}


def _rw(title: str, destructive: bool = False) -> Dict[str, Any]:
    return {"title": title, "readOnlyHint": False, "destructiveHint": destructive, "idempotentHint": False, "openWorldHint": False}


def _result(text: str, is_error: bool = False) -> Dict[str, Any]:
    return {"content": [{"type": "text", "text": text}], "isError": is_error}


def _json_result(data: Any, is_error: bool = False) -> Dict[str, Any]:
    return _result(json.dumps(data, indent=2, default=str), is_error)


def register_direct_ops_tools(toolset) -> None:
    """Register direct operation tools."""
    
    async def local_exec(arguments: Dict[str, Any]) -> Dict[str, Any]:
        """Execute a local command with structured output."""
        command = arguments.get("command", "")
        if not command:
            return _result("Error: command is required", True)
        
        cwd = arguments.get("cwd", "/a0/usr/projects/mcp_server")
        timeout = arguments.get("timeout", 60)
        env_override = arguments.get("env") or {}
        
        env = os.environ.copy()
        env.update({str(k): str(v) for k, v in env_override.items()})
        
        # For long commands, write to temp script
        if len(command) > 1500 or '\n' in command:
            runtime_dir = Path("/a0/usr/projects/mcp_server/.runtime")
            runtime_dir.mkdir(parents=True, exist_ok=True)
            script_file = runtime_dir / f"exec_{os.getpid()}_{id(command)}.sh"
            script_file.write_text(f"#!/bin/bash\nset -e\n{command}")
            script_file.chmod(0o700)
            cmd = ["/bin/bash", str(script_file)]
        else:
            cmd = ["/bin/bash", "-c", command]
            script_file = None
        
        try:
            proc = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                cwd=cwd,
                env=env,
            )
            stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=timeout)
            
            result = {
                "success": proc.returncode == 0,
                "exit_code": proc.returncode,
                "stdout": stdout.decode("utf-8", errors="replace"),
                "stderr": stderr.decode("utf-8", errors="replace"),
                "command": command[:200],
                "cwd": cwd,
            }
            return _json_result(result)
        except asyncio.TimeoutError:
            return _result(f"Error: command timed out after {timeout}s", True)
        except Exception as e:
            return _result(f"Error: {e}", True)
        finally:
            if script_file and script_file.exists():
                script_file.unlink()
    
    async def read_file(arguments: Dict[str, Any]) -> Dict[str, Any]:
        """Read a file with structured output."""
        path = arguments.get("path", "")
        if not path:
            return _result("Error: path is required", True)
        
        try:
            p = Path(path)
            if not p.exists():
                return _result(f"Error: file not found: {path}", True)
            if p.is_dir():
                return _result(f"Error: path is a directory: {path}", True)
            
            content = await asyncio.to_thread(p.read_text)
            return _json_result({
                "success": True,
                "path": str(p),
                "size": len(content),
                "content": content[:50000],  # Limit size
                "truncated": len(content) > 50000,
            })
        except Exception as e:
            return _result(f"Error: {e}", True)
    
    async def write_file(arguments: Dict[str, Any]) -> Dict[str, Any]:
        """Write a file with atomic replace and verification."""
        path = arguments.get("path", "")
        content = arguments.get("content", "")
        if not path:
            return _result("Error: path is required", True)
        
        try:
            p = Path(path)
            p.parent.mkdir(parents=True, exist_ok=True)
            
            # Atomic write via temp file
            tmp_path = p.with_suffix(p.suffix + ".tmp")
            await asyncio.to_thread(tmp_path.write_text, content)
            await asyncio.to_thread(tmp_path.rename, p)
            
            # Verify
            written = await asyncio.to_thread(p.read_text)
            if written != content:
                return _result(f"Error: verification failed - content mismatch", True)
            
            return _json_result({
                "success": True,
                "path": str(p),
                "size": len(content),
            })
        except Exception as e:
            return _result(f"Error: {e}", True)
    
    async def patch_file(arguments: Dict[str, Any]) -> Dict[str, Any]:
        """Patch a file by replacing text with verification."""
        path = arguments.get("path", "")
        search = arguments.get("search", "")
        replace = arguments.get("replace", "")
        if not path or not search:
            return _result("Error: path and search are required", True)
        
        try:
            p = Path(path)
            if not p.exists():
                return _result(f"Error: file not found: {path}", True)
            
            content = await asyncio.to_thread(p.read_text)
            matches = content.count(search)
            
            if matches == 0:
                return _result(f"Error: search pattern not found (0 matches)", True)
            
            new_content = content.replace(search, replace)
            
            # Atomic write
            tmp_path = p.with_suffix(p.suffix + ".tmp")
            await asyncio.to_thread(tmp_path.write_text, new_content)
            await asyncio.to_thread(tmp_path.rename, p)
            
            # Verify
            written = await asyncio.to_thread(p.read_text)
            if search in written:
                return _result(f"Error: verification failed - search pattern still present", True)
            
            return _json_result({
                "success": True,
                "path": str(p),
                "matches_replaced": matches,
            })
        except Exception as e:
            return _result(f"Error: {e}", True)
    
    async def list_dir(arguments: Dict[str, Any]) -> Dict[str, Any]:
        """List directory contents with structured output."""
        path = arguments.get("path", "/a0/usr/projects/mcp_server")
        
        try:
            p = Path(path)
            if not p.exists():
                return _result(f"Error: path not found: {path}", True)
            if not p.is_dir():
                return _result(f"Error: not a directory: {path}", True)
            
            items = []
            for item in sorted(p.iterdir(), key=lambda x: (not x.is_dir(), x.name.lower())):
                try:
                    stat = item.stat()
                    items.append({
                        "name": item.name,
                        "type": "dir" if item.is_dir() else "file",
                        "size": stat.st_size if item.is_file() else None,
                        "modified": stat.st_mtime,
                    })
                except Exception:
                    items.append({"name": item.name, "type": "unknown"})
            
            return _json_result({
                "success": True,
                "path": str(p),
                "count": len(items),
                "items": items[:200],  # Limit
            })
        except Exception as e:
            return _result(f"Error: {e}", True)
    
    async def path_ops(arguments: Dict[str, Any]) -> Dict[str, Any]:
        """Perform path operations: mkdir, copy, move, delete."""
        op = arguments.get("operation") or arguments.get("action") or ""
        src = arguments.get("source") or arguments.get("src") or arguments.get("path") or ""
        dst = arguments.get("destination") or arguments.get("dst") or ""
        
        if not op:
            return _result("Error: operation/action is required (mkdir/copy/move/delete)", True)
        
        try:
            if op == "mkdir":
                if not src:
                    return _result("Error: source path required for mkdir", True)
                p = Path(src)
                p.mkdir(parents=True, exist_ok=True)
                return _json_result({"success": True, "path": str(p), "operation": "mkdir"})
            
            elif op == "copy":
                if not src or not dst:
                    return _result("Error: source and destination required for copy", True)
                src_p, dst_p = Path(src), Path(dst)
                dst_p.parent.mkdir(parents=True, exist_ok=True)
                await asyncio.to_thread(shutil.copy2, src_p, dst_p)
                return _json_result({"success": True, "source": src, "destination": dst, "operation": "copy"})
            
            elif op == "move":
                if not src or not dst:
                    return _result("Error: source and destination required for move", True)
                src_p, dst_p = Path(src), Path(dst)
                dst_p.parent.mkdir(parents=True, exist_ok=True)
                await asyncio.to_thread(shutil.move, str(src_p), str(dst_p))
                return _json_result({"success": True, "source": src, "destination": dst, "operation": "move"})
            
            elif op == "delete":
                if not src:
                    return _result("Error: source path required for delete", True)
                p = Path(src)
                if p.is_dir():
                    await asyncio.to_thread(shutil.rmtree, p)
                else:
                    await asyncio.to_thread(p.unlink)
                return _json_result({"success": True, "path": src, "operation": "delete"})
            
            else:
                return _result(f"Error: unknown operation: {op}", True)
        except Exception as e:
            return _result(f"Error: {e}", True)
    
    async def service_control(arguments: Dict[str, Any]) -> Dict[str, Any]:
        """Control systemd services: status, logs, start, stop, restart, reload."""
        service = arguments.get("service", "mcp-server")
        action = arguments.get("action", "status")
        lines = arguments.get("lines", 50)
        
        valid_actions = ["status", "logs", "start", "stop", "restart", "reload", "is-active"]
        if action not in valid_actions:
            return _result(f"Error: invalid action. Use: {valid_actions}", True)
        
        try:
            if action == "logs":
                cmd = ["journalctl", "-u", service, "-n", str(lines), "--no-pager"]
            else:
                cmd = ["systemctl", action, service]
            
            proc = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            stdout, stderr = await proc.communicate()
            
            return _json_result({
                "success": proc.returncode == 0,
                "action": action,
                "service": service,
                "exit_code": proc.returncode,
                "output": stdout.decode("utf-8", errors="replace"),
                "error": stderr.decode("utf-8", errors="replace"),
            })
        except Exception as e:
            return _result(f"Error: {e}", True)
    
    # Register all tools
    tools = [
        ExtraToolDefinition(
            "local_exec", "Execute a local shell command with structured output.",
            {"type": "object", "properties": {
                "command": {"type": "string", "description": "Shell command to execute"},
                "cwd": {"type": "string", "description": "Working directory"},
                "timeout": {"type": "integer", "description": "Timeout in seconds", "default": 60},
                "env": {"type": "object", "description": "Environment variables"}
            }, "required": ["command"]},
            local_exec, False, _rw("Local Exec")
        ),
        ExtraToolDefinition(
            "read_file", "Read a file and return structured content.",
            {"type": "object", "properties": {
                "path": {"type": "string", "description": "File path to read"}
            }, "required": ["path"]},
            read_file, False, _ro("Read File")
        ),
        ExtraToolDefinition(
            "write_file", "Write content to a file with atomic replace and verification.",
            {"type": "object", "properties": {
                "path": {"type": "string", "description": "File path to write"},
                "content": {"type": "string", "description": "Content to write"}
            }, "required": ["path", "content"]},
            write_file, False, _rw("Write File")
        ),
        ExtraToolDefinition(
            "patch_file", "Patch a file by replacing text with verification.",
            {"type": "object", "properties": {
                "path": {"type": "string", "description": "File path"},
                "search": {"type": "string", "description": "Text to find"},
                "replace": {"type": "string", "description": "Replacement text"}
            }, "required": ["path", "search"]},
            patch_file, False, _rw("Patch File")
        ),
        ExtraToolDefinition(
            "list_dir", "List directory contents with structured output.",
            {"type": "object", "properties": {
                "path": {"type": "string", "description": "Directory path"}
            }, "required": []},
            list_dir, False, _ro("List Dir")
        ),
        ExtraToolDefinition(
            "path_ops", "Perform path operations: mkdir, copy, move, delete. Accepts operation/source/destination or action/path/src/dst aliases.",
            {"type": "object", "properties": {
                "operation": {"type": "string", "enum": ["mkdir", "copy", "move", "delete"]},
                "action": {"type": "string", "enum": ["mkdir", "copy", "move", "delete"]},
                "source": {"type": "string", "description": "Source path"},
                "destination": {"type": "string", "description": "Destination path (for copy/move)"},
                "path": {"type": "string", "description": "Path alias for mkdir/delete"},
                "src": {"type": "string", "description": "Source alias"},
                "dst": {"type": "string", "description": "Destination alias"}
            }},
            path_ops, False, _rw("Path Ops", destructive=True)
        ),
        ExtraToolDefinition(
            "service_control", "Control systemd services: status, logs, start, stop, restart, reload.",
            {"type": "object", "properties": {
                "service": {"type": "string", "description": "Service name", "default": "mcp-server"},
                "action": {"type": "string", "enum": ["status", "logs", "start", "stop", "restart", "reload", "is-active"]},
                "lines": {"type": "integer", "description": "Lines for logs action", "default": 50}
            }, "required": []},
            service_control, False, _rw("Service Control")
        ),
    ]
    
    for tool in tools:
        toolset._register_tool(tool)
    
    print(f"Registered {len(tools)} direct ops tools")
