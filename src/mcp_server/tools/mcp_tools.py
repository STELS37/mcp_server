"""MCP Tools implementation for ChatGPT."""
import logging
import json
import base64
import time
from typing import Optional, Dict, Any, List, Callable
from dataclasses import dataclass

from mcp_server.tools.ssh_client import SSHClient, SSHResult
from mcp_server.tools.executor import CommandExecutor, ExecutionResult
from mcp_server.core.settings import get_settings

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
        self._register_all_tools()
    
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
            description="Execute a shell command on the VPS. Returns stdout, stderr, and exit_code.\n\nIMPORTANT: Dangerous commands (reboot, shutdown, rm -rf, ufw, iptables, userdel, passwd, systemctl, docker, etc.) require confirm=true to execute.",
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
                        "description": "Set to true to confirm execution of dangerous commands",
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
            description="Write content to a file on the VPS. Creates the file if it doesn't exist. Use with caution.",
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
                        "description": "Set to true to confirm overwriting existing files",
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
            description="Restart a systemd service. Requires confirmation.",
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
                        "description": "Set to true to confirm service restart",
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
            description="Execute a command in a Docker container. Use with caution.",
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
                        "description": "Set to true to confirm execution",
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

        # 16. execute_command_plan
        self._register_tool(ToolDefinition(
            name="execute_command_plan",
            description="Execute a multi-step command plan on the VPS in a single tool call. Useful for batching inspection or change operations to reduce repeated approvals. If any step is dangerous, set confirm=true once at the top level.",
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
                                    "description": "Optional per-step override for dangerous commands"
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
                        "description": "Set to true to allow dangerous steps in the plan with one approval",
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
            "destructiveHint": True,
            "idempotentHint": False,
            "openWorldHint": False,
        }

    def _register_tool(self, tool_def: ToolDefinition):
        """Register a tool."""
        if tool_def.annotations is None:
            tool_def.annotations = self._default_annotations_for_tool(tool_def.name)
        self._tools[tool_def.name] = tool_def
    
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
        if name not in self._tools:
            return {
                "isError": True,
                "content": [{
                    "type": "text",
                    "text": f"Unknown tool: {name}"
                }]
            }
        
        tool = self._tools[name]
        
        try:
            # Add user to arguments
            arguments["_user"] = user
            result = await tool.handler(arguments)
            return result
        except Exception as e:
            logger.error(f"Tool execution error: {e}")
            return {
                "isError": True,
                "content": [{
                    "type": "text",
                    "text": f"Error executing {name}: {str(e)}"
                }]
            }
    
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
        
        if not confirm:
            # Check if file exists
            check = await self.ssh.execute(f"test -f {path}", user=user)
            if check.exit_code == 0:
                return {
                    "content": [{
                        "type": "text",
                        "text": f"File {path} already exists. Set confirm=true to overwrite."
                    }],
                    "isError": True
                }
        
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
        
        if not confirm:
            return {
                "content": [{
                    "type": "text",
                    "text": f"Service restart requires confirm=true to proceed. This will restart the {service} service."
                }],
                "isError": False
            }
        
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
        
        if not confirm:
            return {
                "content": [{
                    "type": "text",
                    "text": f"Docker exec requires confirm=true. Command would be: docker exec {container} {command}"
                }],
                "isError": False
            }
        
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


def register_tools(ssh_client: SSHClient) -> MCPTools:
    """Create and return MCP tools instance."""
    return MCPTools(ssh_client)
