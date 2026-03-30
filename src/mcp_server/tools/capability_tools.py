"""Capability and build info tools."""
import hashlib
import json
import subprocess
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Dict, Optional

PROJECT_ROOT = Path("/a0/usr/projects/mcp_server")


@dataclass
class ExtraToolDefinition:
    name: str
    description: str
    input_schema: Dict[str, Any]
    handler: Callable
    dangerous: bool = False
    annotations: Optional[Dict[str, Any]] = None


def _ro(title: str) -> Dict[str, Any]:
    return {
        "title": title,
        "readOnlyHint": True,
        "destructiveHint": False,
        "idempotentHint": True,
        "openWorldHint": False,
    }


def _run(cmd):
    return subprocess.run(cmd, cwd=PROJECT_ROOT, text=True, capture_output=True)


def register_capability_tools(toolset) -> None:
    async def get_tool_registry_version(args: Dict[str, Any]) -> Dict[str, Any]:
        defs = toolset.get_tool_definitions()
        names = sorted(t["name"] for t in defs)
        digest = hashlib.sha256(json.dumps(names).encode()).hexdigest()[:16]
        text = json.dumps({"tool_count": len(names), "registry_version": digest}, indent=2)
        return {"content": [{"type": "text", "text": text}], "isError": False}

    async def get_capabilities_manifest(args: Dict[str, Any]) -> Dict[str, Any]:
        defs = toolset.get_tool_definitions()
        names = sorted(t["name"] for t in defs)
        digest = hashlib.sha256(json.dumps(names).encode()).hexdigest()[:16]
        groups = {
            "diagnostics": [n for n in names if any(k in n for k in ["health", "ready", "diagnose", "journal", "process", "port", "listener", "self_test"])],
            "files": [n for n in names if any(k in n for k in ["file", "path", "dir", "tree", "json", "env"])],
            "workflow": [n for n in names if any(k in n for k in ["workspace", "playbook", "session", "workflow", "capabilities", "build_info", "repo", "sync"])],
        }
        text = json.dumps({"tool_count": len(names), "registry_version": digest, "groups": groups, "all_tools": names}, indent=2, ensure_ascii=False)
        return {"content": [{"type": "text", "text": text}], "isError": False}

    async def get_server_build_info(args: Dict[str, Any]) -> Dict[str, Any]:
        head = _run(["git", "rev-parse", "HEAD"]).stdout.strip()
        short = _run(["git", "rev-parse", "--short", "HEAD"]).stdout.strip()
        branch = _run(["git", "branch", "--show-current"]).stdout.strip()
        tag = _run(["git", "describe", "--tags", "--always"]).stdout.strip()
        pid = str(getattr(toolset, "pid", "")) or str(__import__("os").getpid())
        text = json.dumps({
            "project_root": str(PROJECT_ROOT),
            "branch": branch,
            "commit": head,
            "short_commit": short,
            "describe": tag,
            "pid": pid,
            "generated_at": datetime.now(timezone.utc).isoformat(),
        }, indent=2, ensure_ascii=False)
        return {"content": [{"type": "text", "text": text}], "isError": False}

    extra = [
        ExtraToolDefinition("get_tool_registry_version", "Return the current tool count and a registry digest for snapshot/version checks.", {"type": "object", "properties": {}, "required": []}, get_tool_registry_version, False, _ro("Get Tool Registry Version")),
        ExtraToolDefinition("get_capabilities_manifest", "Return a machine-readable manifest of the currently registered toolset.", {"type": "object", "properties": {}, "required": []}, get_capabilities_manifest, False, _ro("Get Capabilities Manifest")),
        ExtraToolDefinition("get_server_build_info", "Return git/build/runtime identity for the current MCP server process.", {"type": "object", "properties": {}, "required": []}, get_server_build_info, False, _ro("Get Server Build Info")),
    ]

    for tool in extra:
        toolset._register_tool(tool)

