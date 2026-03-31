"""Batch executor tool - ONE confirmation for MULTIPLE operations."""
import json
from typing import Any, Dict, Optional
from dataclasses import dataclass

@dataclass
class ExtraToolDefinition:
    name: str
    description: str
    input_schema: Dict[str, Any]
    handler: callable
    dangerous: bool = False
    annotations: Optional[Dict[str, Any]] = None


def _ro_ann(title: str) -> Dict[str, Any]:
    return {
        "title": title,
        "readOnlyHint": True,
        "destructiveHint": False,
        "idempotentHint": True,
        "openWorldHint": False
    }

SAFE_COMMANDS = {
    "hostname": "hostname",
    "uptime": "uptime",
    "memory": "free -h",
    "disk": "df -h",
    "docker_ps": "docker ps",
    "processes": "ps aux --sort=-%mem | head -20",
    "ports": "ss -tulpn",
}


def _fmt(title: str, results: dict, errors: list = None) -> str:
    lines = ["# " + title, ""]
    for k, v in results.items():
        lines.append("## " + k)
        lines.append(str(v))
        lines.append("")
    if errors:
        lines.append("## Errors")
        lines.append(json.dumps(errors))
    return chr(10).join(lines)


def register_batch_executor_tools(toolset) -> None:
    async def server_info(args):
        results, errors = {}, []
        keys = args.get("include", ["hostname", "uptime", "memory", "disk"])
        for k in keys:
            if k in SAFE_COMMANDS:
                try:
                    r = await toolset._run_command({"command": SAFE_COMMANDS[k]})
                    c = r.get("content", [{}])
                    if c:
                        results[k] = c[0].get("text", "")
                except Exception as e:
                    errors.append(k + ": " + str(e))
        return {"content": [{"type": "text", "text": _fmt("Server Info", results, errors)}], "isError": False}

    async def server_health(args):
        results = {}
        for k in ["uptime", "memory", "disk"]:
            if k in SAFE_COMMANDS:
                try:
                    r = await toolset._run_command({"command": SAFE_COMMANDS[k]})
                    c = r.get("content", [{}])
                    if c:
                        results[k] = c[0].get("text", "")
                except Exception as e:
                    results[k] = "ERROR: " + str(e)
        return {"content": [{"type": "text", "text": _fmt("Health", results)}], "isError": False}

    tools = [
        ExtraToolDefinition("server_info", "Get server info in one call", {"type": "object", "properties": {}, "required": []}, server_info, False, _ro_ann("Info")),
        ExtraToolDefinition("server_health", "Get health in one call", {"type": "object", "properties": {}, "required": []}, server_health, False, _ro_ann("Health")),
    ]
    for t in tools:
        toolset._register_tool(t)
