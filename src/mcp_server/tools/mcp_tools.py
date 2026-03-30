import os
"""MCP Tools implementation for ChatGPT."""
import logging
import json
import base64
import hashlib
import time
from pathlib import Path
from typing import Optional, Dict, Any, List, Callable
from dataclasses import dataclass

from mcp_server.tools.ssh_client import SSHClient, SSHResult
from mcp_server.tools.executor import CommandExecutor, ExecutionResult
from mcp_server.core.settings import get_settings
from mcp_server.tools.extra_tools import register_extra_tools
from mcp_server.tools.ops_tools import register_ops_tools
from mcp_server.tools.playbook_tools import register_playbook_tools
from mcp_server.tools.session_tools import register_session_tools
from mcp_server.tools.state_tools import register_state_tools
from mcp_server.tools.capability_tools import register_capability_tools
from mcp_server.tools.safe_edit_tools import register_safe_edit_tools
from mcp_server.tools.repo_tools import register_repo_tools
from mcp_server.tools.workflow_tools import register_workflow_tools
from mcp_server.tools.anti_loop_tools import register_anti_loop_tools
from mcp_server.tools.bootstrap_tools import register_bootstrap_tools
from mcp_server.tools.smart_tools import register_smart_tools
from mcp_server.tools.router_tools import register_router_tools
from mcp_server.tools.cache_tools import register_cache_tools
from mcp_server.tools.orchestrator_tools import register_orchestrator_tools
from mcp_server.tools.action_router_tools import register_action_router_tools

logger = logging.getLogger(__name__)


@dataclass
class ToolDefinition:
    """MCP Tool definition."""
    name: str
    description: str
    input_schema: Dict[str, Any]
    handler: Callable
    dangerous: bool = False
    annotations: Optional[Dict[str, Any]] = None


class MCPTools:
    """Collection of MCP tools for VPS management."""
    
    def __init__(self, ssh_client: SSHClient):
        self.ssh = ssh_client
        self.executor = CommandExecutor(ssh_client)
        self.settings = get_settings()
        self._tools: Dict[str, ToolDefinition] = {}
        self.extra_tools: Dict[str, Dict[str, Any]] = {}
        self._read_cache: Dict[str, Dict[str, Any]] = {}
        self._read_cache_hits = 0
        self._read_cache_misses = 0
        self._register_all_tools()
        # Register action router for unified tool access
        register_action_router_tools(self)
    
    
    def _register_all_tools(self):
        """Register all available tools."""
        # 1. ping_host
        self._register_tool(ToolDefinition(
            name="ping_host",
            description="Ping a host to check network connectivity from the VPS",
            input_schema={
                "type": "object",
                "properties": {
                    "host": {
                        "type": "string",
                        "description": "Hostname or IP address to ping"
                    },
                    "count": {
                        "type": "integer",
                        "description": "Number of ping packets (default: 3)",
                        "default": 3
                    }
                },
                "required": ["host"]
            },
            handler=self._ping_host,
            dangerous=False
        ))
        
        # 2. run_command
        self._register_tool(ToolDefinition(
            name="run_command",
            description="Execute a shell command on the VPS. Returns stdout, stderr, and exit_code.",
            input_schema={
                "type": "object",
                "properties": {
                    "command": {
                        "type": "string",
                        "description": "Shell command to execute"
                    },
                    "timeout": {
                        "type": "integer",
                        "description": "Command timeout in seconds (default: 30)",
                        "default": 30
                    },
                    "working_dir": {
                        "type": "string",
                        "description": "Working directory for command execution"
                    },
                    "env": {
                        "type": "object",
                        "description": "Environment variables as key-value pairs"
                    },
                    "use_sudo": {
                        "type": "boolean",
                        "description": "Run command with sudo (default: false)",
                        "default": False
                    },
                    "confirm": {
                        "type": "boolean",
                        "description": "Compatibility flag; ignored when unrestricted mode is enabled",
                        "default": False
                    }
                },
                "required": ["command"]
            },
            handler=self._run_command,
            dangerous=True
        ))
        
        # 3. read_file
        self._register_tool(ToolDefinition(
            name="read_file",
            description="Read the contents of a file from the VPS",
            input_schema={
                "type": "object",
                "properties": {
                    "path": {
                        "type": "string",
                        "description": "Absolute path to the file"
                    },
                    "max_size": {
                        "type": "integer",
                        "description": "Maximum file size to read in bytes (default: 65536)",
                        "default": 65536
                    }
                },
                "required": ["path"]
            },
            handler=self._read_file,
            dangerous=False
        ))
        
        # 4. write_file
        self._register_tool(ToolDefinition(
            name="write_file",
            description="Write content to a file on the VPS. Creates the file if it does not exist.",
            input_schema={
                "type": "object",
                "properties": {
                    "path": {
                        "type": "string",
                        "description": "Absolute path to the file"
                    },
                    "content": {
                        "type": "string",
                        "description": "Content to write to the file"
                    },
                    "use_sudo": {
                        "type": "boolean",
                        "description": "Write with sudo privileges",
                        "default": False
                    },
                    "confirm": {
                        "type": "boolean",
                        "description": "Compatibility flag; ignored when unrestricted mode is enabled",
                        "default": False
                    }
                },
                "required": ["path", "content"]
            },
            handler=self._write_file,
            dangerous=True
        ))
        
        # 5. upload_file
        self._register_tool(ToolDefinition(
            name="upload_file",
            description="Upload a file to the VPS. Content should be base64 encoded.",
            input_schema={
                "type": "object",
                "properties": {
                    "path": {
                        "type": "string",
                        "description": "Destination path on the VPS"
                    },
                    "content_base64": {
                        "type": "string",
                        "description": "Base64 encoded file content"
                    },
                    "mode": {
                        "type": "string",
                        "description": "File permissions (default: 0644)",
                        "default": "0644"
                    },
                    "use_sudo": {
                        "type": "boolean",
                        "description": "Upload with sudo privileges",
                        "default": False
                    }
                },
                "required": ["path", "content_base64"]
            },
            handler=self._upload_file,
            dangerous=True
        ))
        
        # 6. download_file
        self._register_tool(ToolDefinition(
            name="download_file",
            description="Download a file from the VPS. Returns base64 encoded content.",
            input_schema={
                "type": "object",
                "properties": {
                    "path": {
                        "type": "string",
                        "description": "Path to the file on the VPS"
                    },
                    "max_size": {
                        "type": "integer",
                        "description": "Maximum file size in bytes (default: 1048576 = 1MB)",
                        "default": 1048576
                    }
                },
                "required": ["path"]
            },
            handler=self._download_file,
            dangerous=False
        ))
        
        # 7. list_dir
        self._register_tool(ToolDefinition(
            name="list_dir",
            description="List contents of a directory on the VPS",
            input_schema={
                "type": "object",
                "properties": {
                    "path": {
                        "type": "string",
                        "description": "Directory path to list"
                    },
                    "long_format": {
                        "type": "boolean",
                        "description": "Show detailed information (default: true)",
                        "default": True
                    }
                },
                "required": ["path"]
            },
            handler=self._list_dir,
            dangerous=False
        ))
        
        # 8. systemd_status
        self._register_tool(ToolDefinition(
            name="systemd_status",
            description="Get status of a systemd service",
            input_schema={
                "type": "object",
                "properties": {
                    "service": {
                        "type": "string",
                        "description": "Name of the systemd service"
                    }
                },
                "required": ["service"]
            },
            handler=self._systemd_status,
            dangerous=False
        ))
        
        # 9. systemd_restart
        self._register_tool(ToolDefinition(
            name="systemd_restart",
            description="Restart a systemd service.",
            input_schema={
                "type": "object",
                "properties": {
                    "service": {
                        "type": "string",
                        "description": "Name of the systemd service to restart"
                    },
                    "use_sudo": {
                        "type": "boolean",
                        "description": "Run with sudo (default: true)",
                        "default": True
                    },
                    "confirm": {
                        "type": "boolean",
                        "description": "Compatibility flag; ignored when unrestricted mode is enabled",
                        "default": False
                    }
                },
                "required": ["service"]
            },
            handler=self._systemd_restart,
            dangerous=True
        ))
        
        # 10. journal_tail
        self._register_tool(ToolDefinition(
            name="journal_tail",
            description="View recent journal logs for a service",
            input_schema={
                "type": "object",
                "properties": {
                    "service": {
                        "type": "string",
                        "description": "Service name to filter logs (optional)"
                    },
                    "lines": {
                        "type": "integer",
                        "description": "Number of lines to show (default: 100)",
                        "default": 100
                    },
                    "since": {
                        "type": "string",
                        "description": "Time filter (e.g., '1 hour ago', 'yesterday')"
                    }
                },
                "required": []
            },
            handler=self._journal_tail,
            dangerous=False
        ))
        
        # 11. docker_ps
        self._register_tool(ToolDefinition(
            name="docker_ps",
            description="List running Docker containers",
            input_schema={
                "type": "object",
                "properties": {
                    "all": {
                        "type": "boolean",
                        "description": "Show all containers including stopped (default: false)",
                        "default": False
                    },
                    "format": {
                        "type": "string",
                        "description": "Output format (json or table)",
                        "default": "json"
                    }
                },
                "required": []
            },
            handler=self._docker_ps,
            dangerous=False
        ))
        
        # 12. docker_logs
        self._register_tool(ToolDefinition(
            name="docker_logs",
            description="View logs from a Docker container",
            input_schema={
                "type": "object",
                "properties": {
                    "container": {
                        "type": "string",
                        "description": "Container name or ID"
                    },
                    "tail": {
                        "type": "integer",
                        "description": "Number of lines to show (default: 100)",
                        "default": 100
                    },
                    "since": {
                        "type": "string",
                        "description": "Time filter (e.g., '1h', '30m')"
                    },
                    "follow": {
                        "type": "boolean",
                        "description": "Follow log output (not recommended)",
                        "default": False
                    }
                },
                "required": ["container"]
            },
            handler=self._docker_logs,
            dangerous=False
        ))
        
        # 13. docker_exec
        self._register_tool(ToolDefinition(
            name="docker_exec",
            description="Execute a command in a Docker container.",
            input_schema={
                "type": "object",
                "properties": {
                    "container": {
                        "type": "string",
                        "description": "Container name or ID"
                    },
                    "command": {
                        "type": "string",
                        "description": "Command to execute"
                    },
                    "user": {
                        "type": "string",
                        "description": "User to run command as"
                    },
                    "confirm": {
                        "type": "boolean",
                        "description": "Compatibility flag; ignored when unrestricted mode is enabled",
                        "default": False
                    }
                },
                "required": ["container", "command"]
            },
            handler=self._docker_exec,
            dangerous=True
        ))
        
        # 14. get_public_ip
        self._register_tool(ToolDefinition(
            name="get_public_ip",
            description="Get the public IP address of the VPS",
            input_schema={
                "type": "object",
                "properties": {},
                "required": []
            },
            handler=self._get_public_ip,
            dangerous=False
        ))
        
        # 15. get_server_facts
        self._register_tool(ToolDefinition(
            name="get_server_facts",
            description="Get comprehensive server information including OS, CPU, memory, disk, and network",
            input_schema={
                "type": "object",
                "properties": {
                    "include_processes": {
                        "type": "boolean",
                        "description": "Include top processes by CPU/memory (default: false)",
                        "default": False
                    }
                },
                "required": []
            },
            handler=self._get_server_facts,
            dangerous=False
        ))


        # 16. health_check
        self._register_tool(ToolDefinition(
            name="health_check",
            description="Read the local MCP server /health endpoint from the VPS without using a generic shell command.",
            input_schema={
                "type": "object",
                "properties": {
                    "port": {
                        "type": "integer",
                        "description": "Local MCP HTTP port (default: 8000)",
                        "default": 8000
                    },
                    "host": {
                        "type": "string",
                        "description": "Local host to query (default: 127.0.0.1)",
                        "default": "127.0.0.1"
                    },
                    "timeout": {
                        "type": "integer",
                        "description": "Request timeout in seconds (default: 10)",
                        "default": 10
                    }
                },
                "required": []
            },
            handler=self._health_check,
            dangerous=False,
            annotations={
                "title": "Health Check",
                "readOnlyHint": True,
                "destructiveHint": False,
                "idempotentHint": True,
                "openWorldHint": False
            }
        ))

        # 17. ready_check
        self._register_tool(ToolDefinition(
            name="ready_check",
            description="Read the local MCP server /ready endpoint from the VPS without using a generic shell command.",
            input_schema={
                "type": "object",
                "properties": {
                    "port": {
                        "type": "integer",
                        "description": "Local MCP HTTP port (default: 8000)",
                        "default": 8000
                    },
                    "host": {
                        "type": "string",
                        "description": "Local host to query (default: 127.0.0.1)",
                        "default": "127.0.0.1"
                    },
                    "timeout": {
                        "type": "integer",
                        "description": "Request timeout in seconds (default: 10)",
                        "default": 10
                    }
                },
                "required": []
            },
            handler=self._ready_check,
            dangerous=False,
            annotations={
                "title": "Ready Check",
                "readOnlyHint": True,
                "destructiveHint": False,
                "idempotentHint": True,
                "openWorldHint": False
            }
        ))

        # 18. http_get_local
        self._register_tool(ToolDefinition(
            name="http_get_local",
            description="Read a local HTTP endpoint on the VPS for diagnostics without using a generic shell command. Restricted to localhost/127.0.0.1/::1.",
            input_schema={
                "type": "object",
                "properties": {
                    "path": {
                        "type": "string",
                        "description": "Absolute path on the local HTTP service, e.g. /health or /ready"
                    },
                    "port": {
                        "type": "integer",
                        "description": "Local TCP port (default: 8000)",
                        "default": 8000
                    },
                    "host": {
                        "type": "string",
                        "description": "Local host to query (default: 127.0.0.1)",
                        "default": "127.0.0.1"
                    },
                    "timeout": {
                        "type": "integer",
                        "description": "Request timeout in seconds (default: 10)",
                        "default": 10
                    }
                },
                "required": ["path"]
            },
            handler=self._http_get_local,
            dangerous=False,
            annotations={
                "title": "HTTP Get Local",
                "readOnlyHint": True,
                "destructiveHint": False,
                "idempotentHint": True,
                "openWorldHint": False
            }
        ))

        # 19. execute_command_plan
        self._register_tool(ToolDefinition(
            name="execute_command_plan",
            description="Execute a multi-step command plan on the VPS in a single tool call. Useful for batching inspection or change operations.",
            input_schema={
                "type": "object",
                "properties": {
                    "steps": {
                        "type": "array",
                        "description": "Ordered list of shell steps to execute",
                        "items": {
                            "type": "object",
                            "properties": {
                                "label": {
                                    "type": "string",
                                    "description": "Optional human-readable label for the step"
                                },
                                "command": {
                                    "type": "string",
                                    "description": "Shell command to execute"
                                },
                                "timeout": {
                                    "type": "integer",
                                    "description": "Command timeout in seconds (default: 30)",
                                    "default": 30
                                },
                                "working_dir": {
                                    "type": "string",
                                    "description": "Working directory for command execution"
                                },
                                "env": {
                                    "type": "object",
                                    "description": "Environment variables as key-value pairs"
                                },
                                "use_sudo": {
                                    "type": "boolean",
                                    "description": "Run command with sudo (default: false)",
                                    "default": False
                                },
                                "confirm": {
                                    "type": "boolean",
                                    "description": "Optional compatibility flag"
                                }
                            },
                            "required": ["command"]
                        }
                    },
                    "stop_on_error": {
                        "type": "boolean",
                        "description": "Stop plan execution after the first failed step (default: true)",
                        "default": True
                    },
                    "confirm": {
                        "type": "boolean",
                        "description": "Compatibility flag; ignored when unrestricted mode is enabled",
                        "default": False
                    }
                },
                "required": ["steps"]
            },
            handler=self._execute_command_plan,
            dangerous=True,
            annotations={
                "title": "Execute Command Plan",
                "readOnlyHint": False,
                "destructiveHint": True,
                "idempotentHint": False,
                "openWorldHint": False
            }
        ))
    
        register_extra_tools(self)
        register_ops_tools(self)
        register_playbook_tools(self)
        register_session_tools(self)
        register_state_tools(self)
        register_capability_tools(self)
        register_safe_edit_tools(self)
        register_repo_tools(self)
        register_workflow_tools(self)
        register_anti_loop_tools(self)
        register_bootstrap_tools(self)
        register_smart_tools(self)
        register_router_tools(self)
        register_cache_tools(self)
        register_orchestrator_tools(self)

        # Back-compat: modules that register via toolset.extra_tools
        if getattr(self, "extra_tools", None):
            for _name, _meta in list(self.extra_tools.items()):
                _handler = _meta.get("handler")
                if not callable(_handler):
                    logger.error(f"Skipping extra tool {_name}: handler is not callable")
                    continue
                self._register_tool(ToolDefinition(
                    name=_name,
                    description=_meta.get("description", ""),
                    input_schema=_meta.get("input_schema", {"type": "object", "properties": {}, "required": []}),
                    handler=_handler,
                    dangerous=bool(_meta.get("dangerous", False)),
                    annotations=_meta.get("annotations"),
                ))

    def _default_annotations_for_tool(self, name: str) -> Dict[str, Any]:
        """Infer safe default tool annotations for MCP clients."""
        read_only_tools = {
            "ping_host",
            "read_file",
            "download_file",
            "list_dir",
            "systemd_status",
            "journal_tail",
            "docker_ps",
            "docker_logs",
            "get_public_ip",
            "get_server_facts",
            "health_check",
            "ready_check",
            "http_get_local",
        }
        open_world_read_only_tools = {"ping_host", "get_public_ip"}

        if name in read_only_tools:
            return {
                "title": name.replace("_", " ").title(),
                "readOnlyHint": True,
                "destructiveHint": False,
                "idempotentHint": True,
                "openWorldHint": name in open_world_read_only_tools,
            }

        return {
            "title": name.replace("_", " ").title(),
            "readOnlyHint": False,
            "destructiveHint": False,
            "idempotentHint": False,
            "openWorldHint": True,
        }

    def _register_tool(self, tool_def: ToolDefinition):
        """Register a tool."""
        if tool_def.annotations is None:
            tool_def.annotations = self._default_annotations_for_tool(tool_def.name)
        self._tools[tool_def.name] = tool_def

    def _cache_ttl_for_tool(self, name: str) -> int:
        ttl_map = {
            "health_check": 5,
            "ready_check": 5,
            "get_capabilities_manifest": 10,
            "get_server_build_info": 10,
            "get_tool_registry_version": 10,
            "systemd_status": 5,
            "list_dir": 5,
            "list_tree": 5,
            "read_file": 5,
            "read_json_file": 5,
            "get_operational_brief": 5,
            "inspect_current_workspace": 5,
        }
        return ttl_map.get(name, 5)

    def _is_cacheable_tool(self, tool: ToolDefinition, arguments: Dict[str, Any]) -> bool:
        if arguments.get("bypass_cache"):
            return False
        annotations = tool.annotations or {}
        return bool(annotations.get("readOnlyHint")) and not tool.dangerous

    def _cache_key(self, name: str, arguments: Dict[str, Any]) -> str:
        clean = self._sanitize_arguments_for_ledger(arguments)
        return f"{name}:{self._hash_arguments(clean)}"

    def _get_cached_tool_result(self, name: str, arguments: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        key = self._cache_key(name, arguments)
        entry = self._read_cache.get(key)
        if not entry:
            self._read_cache_misses += 1
            return None
        if time.time() > float(entry.get("expires_at", 0)):
            self._read_cache.pop(key, None)
            self._read_cache_misses += 1
            return None
        self._read_cache_hits += 1
        return json.loads(json.dumps(entry.get("result")))

    def _set_cached_tool_result(self, name: str, arguments: Dict[str, Any], result: Dict[str, Any]) -> None:
        key = self._cache_key(name, arguments)
        ttl = self._cache_ttl_for_tool(name)
        self._read_cache[key] = {
            "tool_name": name,
            "expires_at": time.time() + ttl,
            "stored_at": time.time(),
            "result": json.loads(json.dumps(result)),
        }
        if len(self._read_cache) > 256:
            oldest_key = min(self._read_cache, key=lambda k: self._read_cache[k].get("stored_at", 0))
            self._read_cache.pop(oldest_key, None)

    def _clear_read_cache(self, tool_name: Optional[str] = None) -> int:
        if not tool_name:
            removed = len(self._read_cache)
            self._read_cache.clear()
            return removed
        keys = [k for k, v in self._read_cache.items() if v.get("tool_name") == tool_name]
        for key in keys:
            self._read_cache.pop(key, None)
        return len(keys)

    def _get_read_cache_stats_text(self) -> str:
        by_tool: Dict[str, int] = {}
        live_entries = 0
        now = time.time()
        for key, entry in list(self._read_cache.items()):
            if now > float(entry.get("expires_at", 0)):
                self._read_cache.pop(key, None)
                continue
            live_entries += 1
            tool_name = str(entry.get("tool_name") or "unknown")
            by_tool[tool_name] = by_tool.get(tool_name, 0) + 1
        payload = {
            "entries": live_entries,
            "hits": self._read_cache_hits,
            "misses": self._read_cache_misses,
            "tools": by_tool,
        }
        return json.dumps(payload, indent=2, ensure_ascii=False)

    def _ledger_path(self) -> Path:
        return Path("/a0/usr/projects/mcp_server/.runtime/agent_state.json")

    def _infer_action_category(self, name: str) -> str:
        edit_tokens = ("write", "replace", "append", "move", "copy", "remove", "chmod", "chown", "rollback", "safe_edit")
        health_tokens = ("health", "ready", "diagnose", "debug_service", "self_test")
        if any(token in name for token in edit_tokens):
            return "edit"
        if any(token in name for token in health_tokens):
            return "health"
        return "general"

    def _infer_action_target(self, arguments: Dict[str, Any]) -> str:
        for key in ("path", "service", "project", "workspace", "project_root", "root", "working_dir", "container", "host", "port", "repo", "repo_name", "service_name"):
            value = arguments.get(key)
            if value not in (None, ""):
                return str(value)
        steps = arguments.get("steps") or []
        if isinstance(steps, list) and steps:
            first = steps[0] if isinstance(steps[0], dict) else {}
            for key in ("working_dir", "label", "command"):
                value = first.get(key) if isinstance(first, dict) else None
                if value not in (None, ""):
                    return str(value)
        return ""

    def _extract_result_text(self, result: Dict[str, Any]) -> str:
        try:
            parts = []
            for item in result.get("content", []) or []:
                if isinstance(item, dict) and item.get("type") == "text" and item.get("text"):
                    parts.append(str(item.get("text")))
            text = "\n".join(parts).strip()
            return text[:1000]
        except Exception:
            return ""

    def _sanitize_arguments_for_ledger(self, arguments: Dict[str, Any]) -> Dict[str, Any]:
        clean = {}
        for key, value in (arguments or {}).items():
            if key == "_user":
                continue
            if isinstance(value, (str, int, float, bool)) or value is None:
                clean[key] = value
            elif isinstance(value, (list, dict)):
                clean[key] = value
            else:
                clean[key] = str(value)
        return clean

    def _hash_arguments(self, arguments: Dict[str, Any]) -> str:
        clean = self._sanitize_arguments_for_ledger(arguments)
        payload = json.dumps(clean, sort_keys=True, ensure_ascii=False)
        return hashlib.sha256(payload.encode()).hexdigest()[:16]

    def _fingerprint_action(self, name: str, arguments: Dict[str, Any]) -> str:
        return f"{name}:{self._hash_arguments(arguments)}"

    def _record_tool_result(self, name: str, arguments: Dict[str, Any], result: Dict[str, Any], user: str = "unknown", started_at: Optional[float] = None) -> None:
        if name == "record_action_result":
            return
        path = self._ledger_path()
        path.parent.mkdir(parents=True, exist_ok=True)
        try:
            state = json.loads(path.read_text()) if path.exists() else {}
            if not isinstance(state, dict):
                state = {}
        except Exception:
            state = {}
        state.setdefault("actions", [])
        state.setdefault("health_snapshots", [])
        state.setdefault("edits", [])
        category = self._infer_action_category(name)
        clean_args = self._sanitize_arguments_for_ledger(arguments)
        duration_ms = None
        if started_at is not None:
            try:
                duration_ms = int((time.time() - started_at) * 1000)
            except Exception:
                duration_ms = None
        item = {
            "action_name": name,
            "status": "error" if result.get("isError") else "ok",
            "is_error": bool(result.get("isError")),
            "target": self._infer_action_target(arguments),
            "details": self._extract_result_text(result),
            "user": user,
            "duration_ms": duration_ms,
            "args_hash": self._hash_arguments(clean_args),
            "call_fingerprint": self._fingerprint_action(name, clean_args),
            "arguments": clean_args,
            "at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        }
        state["actions"] = (state.get("actions") or [])[-199:] + [item]
        if category == "edit":
            state["edits"] = (state.get("edits") or [])[-199:] + [item]
        if category == "health":
            state["health_snapshots"] = (state.get("health_snapshots") or [])[-199:] + [item]
        path.write_text(json.dumps(state, indent=2, ensure_ascii=False))
    
    def get_tool_definitions(self) -> List[Dict[str, Any]]:
        """Get all tool definitions in MCP format."""
        definitions: List[Dict[str, Any]] = []
        for tool in self._tools.values():
            item = {
                "name": tool.name,
                "description": tool.description,
                "inputSchema": tool.input_schema,
            }
            if tool.annotations:
                item["annotations"] = tool.annotations
            definitions.append(item)
        return definitions
    
    async def execute_tool(
        self,
        name: str,
        arguments: Dict[str, Any],
        user: str = "unknown"
    ) -> Dict[str, Any]:
        """Execute a tool by name."""
        raw_arguments = dict(arguments or {})
        started_at = time.time()
        if name not in self._tools:
            result = {
                "isError": True,
                "content": [{
                    "type": "text",
                    "text": f"Unknown tool: {name}"
                }]
            }
            try:
                self._record_tool_result(name, raw_arguments, result, user=user, started_at=started_at)
            except Exception:
                pass
            return result

        tool = self._tools[name]
        cached_result = None
        if self._is_cacheable_tool(tool, raw_arguments):
            cached_result = self._get_cached_tool_result(name, raw_arguments)
            if cached_result is not None:
                return cached_result

        try:
            arguments["_user"] = user
            result = await tool.handler(arguments)
            if self._is_cacheable_tool(tool, raw_arguments) and not result.get("isError"):
                try:
                    self._set_cached_tool_result(name, raw_arguments, result)
                except Exception as cache_error:
                    logger.warning(f"Cache write skipped for {name}: {cache_error}")
            elif not result.get("isError"):
                try:
                    self._clear_read_cache()
                except Exception as cache_error:
                    logger.warning(f"Cache clear skipped after {name}: {cache_error}")
            try:
                self._record_tool_result(name, raw_arguments, result, user=user, started_at=started_at)
            except Exception as record_error:
                logger.warning(f"Ledger write skipped for {name}: {record_error}")
            return result
        except Exception as e:
            logger.error(f"Tool execution error: {e}")
            result = {
                "isError": True,
                "content": [{
                    "type": "text",
                    "text": f"Error executing {name}: {str(e)}"
                }]
            }
            try:
                self._record_tool_result(name, raw_arguments, result, user=user, started_at=started_at)
            except Exception as record_error:
                logger.warning(f"Ledger write skipped for failed {name}: {record_error}")
            return result
    
    # Tool implementations
    
    async def _ping_host(self, args: Dict[str, Any]) -> Dict[str, Any]:
        """Ping a host."""
        host = args.get("host")
        count = args.get("count", 3)
        user = args.get("_user", "unknown")
        
        result = await self.ssh.ping_host(host, count, user)
        
        return {
            "content": [{
                "type": "text",
                "text": f"Ping results for {host}:\n\n{result.stdout}\n{result.stderr}".strip()
            }],
            "isError": result.exit_code != 0
        }
    
    async def _run_command(self, args: Dict[str, Any]) -> Dict[str, Any]:
        """Execute a command."""
        command = args.get("command")
        timeout = args.get("timeout", 30)
        working_dir = args.get("working_dir")
        env = args.get("env")
        use_sudo = args.get("use_sudo", False)
        confirm = args.get("confirm", False)
        user = args.get("_user", "unknown")
        
        result = await self.executor.execute_safe(
            command=command,
            user=user,
            timeout=timeout,
            working_dir=working_dir,
            env=env,
            use_sudo=use_sudo,
            confirm=confirm,
        )
        
        output = []
        if result.stdout:
            output.append(f"STDOUT:\n{result.stdout}")
        if result.stderr:
            output.append(f"STDERR:\n{result.stderr}")
        output.append(f"EXIT CODE: {result.exit_code}")
        
        return {
            "content": [{
                "type": "text",
                "text": "\n".join(output)
            }],
            "isError": not result.success
        }
    
    async def _execute_command_plan(self, args: Dict[str, Any]) -> Dict[str, Any]:
        """Execute a sequence of commands with one top-level confirmation."""
        steps = args.get("steps", [])
        stop_on_error = args.get("stop_on_error", True)
        global_confirm = args.get("confirm", False)
        user = args.get("_user", "unknown")

        if not isinstance(steps, list) or not steps:
            return {
                "content": [{
                    "type": "text",
                    "text": "steps must be a non-empty array"
                }],
                "isError": True
            }

        sections: List[str] = []
        failures = 0
        executed = 0

        for idx, step in enumerate(steps, start=1):
            if not isinstance(step, dict):
                failures += 1
                sections.append(f"## Step {idx}\nInvalid step payload: expected object")
                if stop_on_error:
                    break
                continue

            command = step.get("command")
            if not command:
                failures += 1
                sections.append(f"## Step {idx}\nMissing command")
                if stop_on_error:
                    break
                continue

            label = step.get("label") or f"Step {idx}"
            result = await self.executor.execute_safe(
                command=command,
                user=user,
                timeout=step.get("timeout", 30),
                working_dir=step.get("working_dir"),
                env=step.get("env"),
                use_sudo=step.get("use_sudo", False),
                confirm=step.get("confirm", global_confirm),
            )
            executed += 1

            chunk = [f"## {idx}. {label}", f"COMMAND: {command}"]
            if result.stdout:
                chunk.append(f"STDOUT:\n{result.stdout}")
            if result.stderr:
                chunk.append(f"STDERR:\n{result.stderr}")
            chunk.append(f"EXIT CODE: {result.exit_code}")
            sections.append("\n\n".join(chunk))

            if not result.success:
                failures += 1
                if stop_on_error:
                    break

        summary = f"Executed {executed} of {len(steps)} step(s). Failures: {failures}. stop_on_error={stop_on_error}."
        return {
            "content": [{
                "type": "text",
                "text": summary + "\n\n" + "\n\n".join(sections)
            }],
            "isError": failures > 0
        }

    async def _read_file(self, args: Dict[str, Any]) -> Dict[str, Any]:
        """Read a file."""
        path = args.get("path")
        user = args.get("_user", "unknown")
        
        result = await self.ssh.read_file(path, user)
        
        if result.exit_code != 0:
            return {
                "content": [{
                    "type": "text",
                    "text": f"Failed to read file: {result.stderr}"
                }],
                "isError": True
            }
        
        return {
            "content": [{
                "type": "text",
                "text": f"Contents of {path}:\n\n{result.stdout}"
            }],
            "isError": False
        }
    
    async def _write_file(self, args: Dict[str, Any]) -> Dict[str, Any]:
        """Write a file."""
        path = args.get("path")
        content = args.get("content")
        use_sudo = args.get("use_sudo", False)
        confirm = args.get("confirm", False)
        user = args.get("_user", "unknown")
        
        result = await self.ssh.write_file(path, content, user, use_sudo)
        
        return {
            "content": [{
                "type": "text",
                "text": f"File written to {path}" if result.exit_code == 0 else f"Failed: {result.stderr}"
            }],
            "isError": result.exit_code != 0
        }
    
    async def _upload_file(self, args: Dict[str, Any]) -> Dict[str, Any]:
        """Upload a file."""
        path = args.get("path")
        content_base64 = args.get("content_base64")
        mode = args.get("mode", "0644")
        use_sudo = args.get("use_sudo", False)
        user = args.get("_user", "unknown")
        
        try:
            content = base64.b64decode(content_base64).decode("utf-8")
        except Exception as e:
            return {
                "content": [{
                    "type": "text",
                    "text": f"Failed to decode base64 content: {e}"
                }],
                "isError": True
            }
        
        result = await self.ssh.write_file(path, content, user, use_sudo)
        
        if result.exit_code == 0 and mode:
            await self.ssh.execute(f"chmod {mode} {path}", user=user, use_sudo=use_sudo)
        
        return {
            "content": [{
                "type": "text",
                "text": f"File uploaded to {path}" if result.exit_code == 0 else f"Failed: {result.stderr}"
            }],
            "isError": result.exit_code != 0
        }
    
    async def _download_file(self, args: Dict[str, Any]) -> Dict[str, Any]:
        """Download a file."""
        path = args.get("path")
        max_size = args.get("max_size", 1048576)
        user = args.get("_user", "unknown")
        
        # Check file size first
        size_check = await self.ssh.execute(f"stat -c %s {path} 2>/dev/null", user=user)
        if size_check.exit_code != 0:
            return {
                "content": [{
                    "type": "text",
                    "text": f"File not found: {path}"
                }],
                "isError": True
            }
        
        try:
            size = int(size_check.stdout.strip())
            if size > max_size:
                return {
                    "content": [{
                        "type": "text",
                        "text": f"File too large: {size} bytes (max: {max_size})"
                    }],
                    "isError": True
                }
        except ValueError:
            pass
        
        # Use base64 to safely encode file
        result = await self.ssh.execute(f"base64 {path}", user=user)
        
        if result.exit_code != 0:
            return {
                "content": [{
                    "type": "text",
                    "text": f"Failed to read file: {result.stderr}"
                }],
                "isError": True
            }
        
        return {
            "content": [{
                "type": "text",
                "text": f"File: {path}\nSize: {size} bytes\nContent (base64):\n{result.stdout}"
            }],
            "isError": False
        }
    
    async def _list_dir(self, args: Dict[str, Any]) -> Dict[str, Any]:
        """List directory contents."""
        path = args.get("path")
        long_format = args.get("long_format", True)
        user = args.get("_user", "unknown")
        
        result = await self.ssh.list_directory(path, user, long_format)
        
        return {
            "content": [{
                "type": "text",
                "text": f"Contents of {path}:\n\n{result.stdout}" if result.exit_code == 0 else f"Error: {result.stderr}"
            }],
            "isError": result.exit_code != 0
        }
    
    async def _systemd_status(self, args: Dict[str, Any]) -> Dict[str, Any]:
        """Get systemd service status."""
        service = args.get("service")
        user = args.get("_user", "unknown")
        
        result = await self.ssh.execute(f"systemctl status {service}", user=user)
        
        return {
            "content": [{
                "type": "text",
                "text": f"Status of {service}:\n\n{result.stdout}\n{result.stderr}".strip()
            }],
            "isError": result.exit_code not in [0, 3]  # 3 = service not running
        }
    
    async def _systemd_restart(self, args: Dict[str, Any]) -> Dict[str, Any]:
        """Restart a systemd service."""
        service = args.get("service")
        use_sudo = args.get("use_sudo", True)
        confirm = args.get("confirm", False)
        user = args.get("_user", "unknown")
        
        result = await self.ssh.execute(
            f"systemctl restart {service}",
            user=user,
            use_sudo=use_sudo,
            confirm=True
        )
        
        return {
            "content": [{
                "type": "text",
                "text": f"Service {service} restarted" if result.exit_code == 0 else f"Failed to restart: {result.stderr}"
            }],
            "isError": result.exit_code != 0
        }
    
    async def _journal_tail(self, args: Dict[str, Any]) -> Dict[str, Any]:
        """View journal logs."""
        service = args.get("service", "")
        lines = args.get("lines", 100)
        since = args.get("since")
        user = args.get("_user", "unknown")
        
        cmd_parts = ["journalctl", "-n", str(lines), "--no-pager"]
        if service:
            cmd_parts.extend(["-u", service])
        if since:
            cmd_parts.extend(["--since", f'"{since}"'])
        
        result = await self.ssh.execute(" ".join(cmd_parts), user=user)
        
        return {
            "content": [{
                "type": "text",
                "text": f"Journal logs{f' for {service}' if service else ''}:\n\n{result.stdout}"
            }],
            "isError": result.exit_code != 0
        }
    
    async def _docker_ps(self, args: Dict[str, Any]) -> Dict[str, Any]:
        """List Docker containers."""
        all_containers = args.get("all", False)
        fmt = args.get("format", "json")
        user = args.get("_user", "unknown")
        
        cmd = f"docker ps {'-a' if all_containers else ''} --format {fmt}"
        result = await self.ssh.execute(cmd, user=user)
        
        return {
            "content": [{
                "type": "text",
                "text": f"Docker containers:\n\n{result.stdout}" if result.exit_code == 0 else f"Error: {result.stderr}"
            }],
            "isError": result.exit_code != 0
        }
    
    async def _docker_logs(self, args: Dict[str, Any]) -> Dict[str, Any]:
        """View Docker container logs."""
        container = args.get("container")
        tail = args.get("tail", 100)
        since = args.get("since")
        user = args.get("_user", "unknown")
        
        cmd_parts = ["docker", "logs", "--tail", str(tail), container]
        if since:
            cmd_parts.extend(["--since", since])
        
        result = await self.ssh.execute(" ".join(cmd_parts), user=user)
        
        return {
            "content": [{
                "type": "text",
                "text": f"Logs for {container}:\n\n{result.stdout}\n{result.stderr}".strip()
            }],
            "isError": result.exit_code != 0
        }
    
    async def _docker_exec(self, args: Dict[str, Any]) -> Dict[str, Any]:
        """Execute command in Docker container."""
        container = args.get("container")
        command = args.get("command")
        exec_user = args.get("user")
        confirm = args.get("confirm", False)
        user = args.get("_user", "unknown")
        
        cmd_parts = ["docker", "exec"]
        if exec_user:
            cmd_parts.extend(["-u", exec_user])
        cmd_parts.extend([container, command])
        
        result = await self.ssh.execute(" ".join(cmd_parts), user=user, confirm=True)
        
        return {
            "content": [{
                "type": "text",
                "text": f"Executed in {container}:\n\nSTDOUT:\n{result.stdout}\n\nSTDERR:\n{result.stderr}\n\nEXIT CODE: {result.exit_code}"
            }],
            "isError": result.exit_code != 0
        }
    
    async def _get_public_ip(self, args: Dict[str, Any]) -> Dict[str, Any]:
        """Get public IP address."""
        user = args.get("_user", "unknown")
        
        # Try multiple services
        services = [
            "curl -s ifconfig.me",
            "curl -s icanhazip.com",
            "curl -s ipecho.net/plain",
        ]
        
        for service in services:
            result = await self.ssh.execute(service, user=user, timeout=10)
            if result.exit_code == 0 and result.stdout.strip():
                ip = result.stdout.strip()
                return {
                    "content": [{
                        "type": "text",
                        "text": f"Public IP: {ip}"
                    }],
                    "isError": False
                }
        
        return {
            "content": [{
                "type": "text",
                "text": "Failed to get public IP"
            }],
            "isError": True
        }
    
    async def _get_server_facts(self, args: Dict[str, Any]) -> Dict[str, Any]:
        """Get comprehensive server information."""
        include_processes = args.get("include_processes", False)
        user = args.get("_user", "unknown")
        
        facts = {}
        
        # OS Info
        result = await self.ssh.execute("cat /etc/os-release", user=user)
        if result.exit_code == 0:
            facts["os"] = result.stdout.strip()
        
        # Kernel
        result = await self.ssh.execute("uname -a", user=user)
        if result.exit_code == 0:
            facts["kernel"] = result.stdout.strip()
        
        # Hostname
        result = await self.ssh.execute("hostname", user=user)
        if result.exit_code == 0:
            facts["hostname"] = result.stdout.strip()
        
        # Uptime
        result = await self.ssh.execute("uptime -p", user=user)
        if result.exit_code == 0:
            facts["uptime"] = result.stdout.strip()
        
        # CPU Info
        result = await self.ssh.execute("lscpu", user=user)
        if result.exit_code == 0:
            facts["cpu"] = result.stdout.strip()
        
        # Memory
        result = await self.ssh.execute("free -h", user=user)
        if result.exit_code == 0:
            facts["memory"] = result.stdout.strip()
        
        # Disk
        result = await self.ssh.execute("df -h", user=user)
        if result.exit_code == 0:
            facts["disk"] = result.stdout.strip()
        
        # Network interfaces
        result = await self.ssh.execute("ip addr show", user=user)
        if result.exit_code == 0:
            facts["network"] = result.stdout.strip()
        
        # Public IP
        result = await self.ssh.execute("curl -s ifconfig.me", user=user, timeout=10)
        if result.exit_code == 0:
            facts["public_ip"] = result.stdout.strip()
        
        # Top processes if requested
        if include_processes:
            result = await self.ssh.execute("ps aux --sort=-%mem | head -10", user=user)
            if result.exit_code == 0:
                facts["top_memory_processes"] = result.stdout.strip()
            
            result = await self.ssh.execute("ps aux --sort=-%cpu | head -10", user=user)
            if result.exit_code == 0:
                facts["top_cpu_processes"] = result.stdout.strip()
        
        # Format output
        output = "# Server Facts\n\n"
        for key, value in facts.items():
            output += "## " + key.upper() + "\n```\n" + str(value) + "\n```\n\n"
        
        return {
            "content": [{
                "type": "text",
                "text": output
            }],
            "isError": False
        }



    async def _health_check(self, args: Dict[str, Any]) -> Dict[str, Any]:
        """Read the local /health endpoint."""
        user = args.get("_user", "unknown")
        host = args.get("host", "127.0.0.1")
        port = int(args.get("port", 8000))
        timeout = int(args.get("timeout", 10))
        return await self._read_local_http("/health", host, port, timeout, user)

    async def _ready_check(self, args: Dict[str, Any]) -> Dict[str, Any]:
        """Read the local /ready endpoint."""
        user = args.get("_user", "unknown")
        host = args.get("host", "127.0.0.1")
        port = int(args.get("port", 8000))
        timeout = int(args.get("timeout", 10))
        return await self._read_local_http("/ready", host, port, timeout, user)

    async def _http_get_local(self, args: Dict[str, Any]) -> Dict[str, Any]:
        """Read a localhost-only HTTP endpoint."""
        user = args.get("_user", "unknown")
        host = args.get("host", "127.0.0.1")
        port = int(args.get("port", 8000))
        timeout = int(args.get("timeout", 10))
        path = args.get("path", "/")
        return await self._read_local_http(path, host, port, timeout, user)

    async def _read_local_http(self, path: str, host: str, port: int, timeout: int, user: str) -> Dict[str, Any]:
        """Perform a localhost-only GET request using curl on the VPS."""
        allowed_hosts = {"127.0.0.1", "localhost", "::1"}
        if host not in allowed_hosts:
            return {
                "content": [{
                    "type": "text",
                    "text": f"Host {host} is not allowed. Use one of: {', '.join(sorted(allowed_hosts))}."
                }],
                "isError": True
            }

        if not isinstance(path, str) or not path.startswith('/'):
            return {
                "content": [{
                    "type": "text",
                    "text": "path must start with '/'."
                }],
                "isError": True
            }

        url = f"http://{host}:{port}{path}"
        result = await self.ssh.execute(
            f"curl -fsS --max-time {timeout} {url}",
            user=user,
            timeout=max(timeout + 2, 5),
        )

        if result.exit_code != 0:
            return {
                "content": [{
                    "type": "text",
                    "text": f"Failed to GET {url}: {result.stderr or result.stdout}"
                }],
                "isError": True
            }

        return {
            "content": [{
                "type": "text",
                "text": f"GET {url}\n\n{result.stdout.strip()}"
            }],
            "isError": False
        }

def register_tools(ssh_client: SSHClient) -> MCPTools:
    """Create and return MCP tools instance."""
    return MCPTools(ssh_client)
