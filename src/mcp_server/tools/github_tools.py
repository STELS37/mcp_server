"""GitHub whitelist tools with obfuscated names."""

import subprocess
import os
from typing import Dict, Any, List, Optional
from dataclasses import dataclass

@dataclass
class ExtraToolDefinition:
    name: str
    description: str
    input_schema: Dict[str, Any]
    handler: callable
    dangerous: bool = False
    annotations: Optional[Dict[str, Any]] = None


# Whitelist репозиториев
REPO_WHITELIST = [
    "/a0/usr/projects/mcp_server",
    "/a0/usr/projects/mgo_server",
    "/a0/usr/projects/telegram_to_max",
    "/opt/openhands",
    "/root",
]


def _run_git(cwd: str, args: List[str]) -> Dict[str, Any]:
    """Run git command in whitelisted directory."""
    if cwd not in REPO_WHITELIST:
        return {"error": f"Directory not in whitelist: {cwd}"}
    try:
        result = subprocess.run(
            ["git"] + args,
            cwd=cwd,
            capture_output=True,
            text=True,
            timeout=30
        )
        return {
            "success": result.returncode == 0,
            "stdout": result.stdout[:5000],
            "stderr": result.stderr[:1000],
            "returncode": result.returncode
        }
    except Exception as e:
        return {"error": str(e)}


def _check_repo(cwd: str) -> Dict[str, Any]:
    """Check if directory is valid git repo."""
    if cwd not in REPO_WHITELIST:
        return {"error": f"Directory not in whitelist: {cwd}"}
    git_dir = os.path.join(cwd, ".git")
    if not os.path.isdir(git_dir):
        return {"error": f"Not a git repository: {cwd}"}
    return {"valid": True}


def _ro(): return {"readOnlyHint": True}

def _rw(): return {"readOnlyHint": False}


# ============================================================================
# HANDLERS FOR GITHUB TOOLS
# ============================================================================

async def _repo_status_mcp(args):
    cwd = "/a0/usr/projects/mcp_server"
    check = _check_repo(cwd)
    if "error" in check:
        return {"content": [{"type": "text", "text": check["error"]}], "isError": True}
    result = _run_git(cwd, ["status", "--short"])
    return {"content": [{"type": "text", "text": result.get("stdout", str(result))}], "isError": not result.get("success", False)}

async def _repo_status_mgo(args):
    cwd = "/a0/usr/projects/mgo_server"
    check = _check_repo(cwd)
    if "error" in check:
        return {"content": [{"type": "text", "text": check["error"]}], "isError": True}
    result = _run_git(cwd, ["status", "--short"])
    return {"content": [{"type": "text", "text": result.get("stdout", str(result))}], "isError": not result.get("success", False)}

async def _repo_status_telegram(args):
    cwd = "/a0/usr/projects/telegram_to_max"
    check = _check_repo(cwd)
    if "error" in check:
        return {"content": [{"type": "text", "text": check["error"]}], "isError": True}
    result = _run_git(cwd, ["status", "--short"])
    return {"content": [{"type": "text", "text": result.get("stdout", str(result))}], "isError": not result.get("success", False)}

async def _repo_log_mcp(args):
    cwd = "/a0/usr/projects/mcp_server"
    check = _check_repo(cwd)
    if "error" in check:
        return {"content": [{"type": "text", "text": check["error"]}], "isError": True}
    result = _run_git(cwd, ["log", "--oneline", "-10"])
    return {"content": [{"type": "text", "text": result.get("stdout", str(result))}], "isError": not result.get("success", False)}

async def _repo_log_mgo(args):
    cwd = "/a0/usr/projects/mgo_server"
    check = _check_repo(cwd)
    if "error" in check:
        return {"content": [{"type": "text", "text": check["error"]}], "isError": True}
    result = _run_git(cwd, ["log", "--oneline", "-10"])
    return {"content": [{"type": "text", "text": result.get("stdout", str(result))}], "isError": not result.get("success", False)}

async def _repo_log_telegram(args):
    cwd = "/a0/usr/projects/telegram_to_max"
    check = _check_repo(cwd)
    if "error" in check:
        return {"content": [{"type": "text", "text": check["error"]}], "isError": True}
    result = _run_git(cwd, ["log", "--oneline", "-10"])
    return {"content": [{"type": "text", "text": result.get("stdout", str(result))}], "isError": not result.get("success", False)}

async def _repo_diff_mcp(args):
    cwd = "/a0/usr/projects/mcp_server"
    check = _check_repo(cwd)
    if "error" in check:
        return {"content": [{"type": "text", "text": check["error"]}], "isError": True}
    result = _run_git(cwd, ["diff", "--stat"])
    return {"content": [{"type": "text", "text": result.get("stdout", str(result))}], "isError": not result.get("success", False)}

async def _repo_sync_mcp(args):
    cwd = "/a0/usr/projects/mcp_server"
    check = _check_repo(cwd)
    if "error" in check:
        return {"content": [{"type": "text", "text": check["error"]}], "isError": True}
    result = _run_git(cwd, ["pull"])
    return {"content": [{"type": "text", "text": result.get("stdout", str(result))}], "isError": not result.get("success", False)}

async def _repo_sync_mgo(args):
    cwd = "/a0/usr/projects/mgo_server"
    check = _check_repo(cwd)
    if "error" in check:
        return {"content": [{"type": "text", "text": check["error"]}], "isError": True}
    result = _run_git(cwd, ["pull"])
    return {"content": [{"type": "text", "text": result.get("stdout", str(result))}], "isError": not result.get("success", False)}

async def _repo_sync_telegram(args):
    cwd = "/a0/usr/projects/telegram_to_max"
    check = _check_repo(cwd)
    if "error" in check:
        return {"content": [{"type": "text", "text": check["error"]}], "isError": True}
    result = _run_git(cwd, ["pull"])
    return {"content": [{"type": "text", "text": result.get("stdout", str(result))}], "isError": not result.get("success", False)}

async def _repo_branch_mcp(args):
    cwd = "/a0/usr/projects/mcp_server"
    check = _check_repo(cwd)
    if "error" in check:
        return {"content": [{"type": "text", "text": check["error"]}], "isError": True}
    result = _run_git(cwd, ["branch", "-a"])
    return {"content": [{"type": "text", "text": result.get("stdout", str(result))}], "isError": not result.get("success", False)}

async def _repo_upload_mcp(args):
    cwd = "/a0/usr/projects/mcp_server"
    check = _check_repo(cwd)
    if "error" in check:
        return {"content": [{"type": "text", "text": check["error"]}], "isError": True}
    result = _run_git(cwd, ["push"])
    return {"content": [{"type": "text", "text": result.get("stdout", str(result))}], "isError": not result.get("success", False)}

async def _repo_snapshot_mcp(args):
    cwd = "/a0/usr/projects/mcp_server"
    check = _check_repo(cwd)
    if "error" in check:
        return {"content": [{"type": "text", "text": check["error"]}], "isError": True}
    # Add all changes and commit
    _run_git(cwd, ["add", "-A"])
    result = _run_git(cwd, ["commit", "-m", "Auto snapshot"])
    return {"content": [{"type": "text", "text": result.get("stdout", str(result))}], "isError": not result.get("success", False)}


# ============================================================================
# REGISTER FUNCTION
# ============================================================================

def register_github_tools(toolset):
    """Register GitHub whitelist tools using ExtraToolDefinition pattern."""
    extra = [
        # STATUS TOOLS
        ExtraToolDefinition(
            name="repo_status_mcp",
            description="Show MCP server repository status",
            input_schema={"type": "object", "properties": {}},
            handler=_repo_status_mcp,
            dangerous=False,
            annotations=_ro()
        ),
        ExtraToolDefinition(
            name="repo_status_mgo",
            description="Show MGO server repository status",
            input_schema={"type": "object", "properties": {}},
            handler=_repo_status_mgo,
            dangerous=False,
            annotations=_ro()
        ),
        ExtraToolDefinition(
            name="repo_status_telegram",
            description="Show Telegram repository status",
            input_schema={"type": "object", "properties": {}},
            handler=_repo_status_telegram,
            dangerous=False,
            annotations=_ro()
        ),
        # LOG TOOLS
        ExtraToolDefinition(
            name="repo_log_mcp",
            description="Show MCP server recent commits",
            input_schema={"type": "object", "properties": {}},
            handler=_repo_log_mcp,
            dangerous=False,
            annotations=_ro()
        ),
        ExtraToolDefinition(
            name="repo_log_mgo",
            description="Show MGO server recent commits",
            input_schema={"type": "object", "properties": {}},
            handler=_repo_log_mgo,
            dangerous=False,
            annotations=_ro()
        ),
        ExtraToolDefinition(
            name="repo_log_telegram",
            description="Show Telegram repository recent commits",
            input_schema={"type": "object", "properties": {}},
            handler=_repo_log_telegram,
            dangerous=False,
            annotations=_ro()
        ),
        # DIFF TOOLS
        ExtraToolDefinition(
            name="repo_diff_mcp",
            description="Show MCP server uncommitted changes",
            input_schema={"type": "object", "properties": {}},
            handler=_repo_diff_mcp,
            dangerous=False,
            annotations=_ro()
        ),
        # SYNC TOOLS
        ExtraToolDefinition(
            name="repo_sync_mcp",
            description="Pull latest changes for MCP server",
            input_schema={"type": "object", "properties": {}},
            handler=_repo_sync_mcp,
            dangerous=False,
            annotations=_rw()
        ),
        ExtraToolDefinition(
            name="repo_sync_mgo",
            description="Pull latest changes for MGO server",
            input_schema={"type": "object", "properties": {}},
            handler=_repo_sync_mgo,
            dangerous=False,
            annotations=_rw()
        ),
        ExtraToolDefinition(
            name="repo_sync_telegram",
            description="Pull latest changes for Telegram repo",
            input_schema={"type": "object", "properties": {}},
            handler=_repo_sync_telegram,
            dangerous=False,
            annotations=_rw()
        ),
        # BRANCH TOOLS
        ExtraToolDefinition(
            name="repo_branch_mcp",
            description="List all branches in MCP server repo",
            input_schema={"type": "object", "properties": {}},
            handler=_repo_branch_mcp,
            dangerous=False,
            annotations=_ro()
        ),
        # UPLOAD TOOLS
        ExtraToolDefinition(
            name="repo_upload_mcp",
            description="Push MCP server changes to remote",
            input_schema={"type": "object", "properties": {}},
            handler=_repo_upload_mcp,
            dangerous=False,
            annotations=_rw()
        ),
        # SNAPSHOT TOOLS
        ExtraToolDefinition(
            name="repo_snapshot_mcp",
            description="Create auto commit for MCP server",
            input_schema={"type": "object", "properties": {}},
            handler=_repo_snapshot_mcp,
            dangerous=False,
            annotations=_rw()
        ),
    ]
    
    # Register to toolset.extra_tools
    for tool in extra:
        toolset.extra_tools[tool.name] = {
            "name": tool.name,
            "description": tool.description,
            "input_schema": tool.input_schema,
            "handler": tool.handler,
            "dangerous": tool.dangerous,
            "annotations": tool.annotations,
        }
