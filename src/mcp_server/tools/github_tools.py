"""GitHub whitelist tools with obfuscated names."""

import subprocess
import os
from typing import Dict, Any, List

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


def register_github_tools(mcp_tools):
    """Register GitHub whitelist tools."""
    
    # STATUS TOOLS
    
    @mcp_tools._tool(name="repo_status_mcp", description="Show MCP server repository status")
    def repo_status_mcp() -> Dict[str, Any]:
        cwd = "/a0/usr/projects/mcp_server"
        check = _check_repo(cwd)
        if "error" in check:
            return check
        return _run_git(cwd, ["status", "--short"])
    
    @mcp_tools._tool(name="repo_status_mgo", description="Show MGO server repository status")
    def repo_status_mgo() -> Dict[str, Any]:
        cwd = "/a0/usr/projects/mgo_server"
        check = _check_repo(cwd)
        if "error" in check:
            return check
        return _run_git(cwd, ["status", "--short"])
    
    @mcp_tools._tool(name="repo_status_telegram", description="Show Telegram repository status")
    def repo_status_telegram() -> Dict[str, Any]:
        cwd = "/a0/usr/projects/telegram_to_max"
        check = _check_repo(cwd)
        if "error" in check:
            return check
        return _run_git(cwd, ["status", "--short"])
    
    # LOG TOOLS
    
    @mcp_tools._tool(name="repo_log_mcp", description="Show MCP server recent commits")
    def repo_log_mcp() -> Dict[str, Any]:
        cwd = "/a0/usr/projects/mcp_server"
        check = _check_repo(cwd)
        if "error" in check:
            return check
        return _run_git(cwd, ["log", "--oneline", "-10"])
    
    @mcp_tools._tool(name="repo_log_mgo", description="Show MGO server recent commits")
    def repo_log_mgo() -> Dict[str, Any]:
        cwd = "/a0/usr/projects/mgo_server"
        check = _check_repo(cwd)
        if "error" in check:
            return check
        return _run_git(cwd, ["log", "--oneline", "-10"])
    
    @mcp_tools._tool(name="repo_log_telegram", description="Show Telegram repository recent commits")
    def repo_log_telegram() -> Dict[str, Any]:
        cwd = "/a0/usr/projects/telegram_to_max"
        check = _check_repo(cwd)
        if "error" in check:
            return check
        return _run_git(cwd, ["log", "--oneline", "-10"])
    
    # BRANCH TOOLS
    
    @mcp_tools._tool(name="repo_branch_mcp", description="Show MCP server branches")
    def repo_branch_mcp() -> Dict[str, Any]:
        cwd = "/a0/usr/projects/mcp_server"
        check = _check_repo(cwd)
        if "error" in check:
            return check
        return _run_git(cwd, ["branch", "-a"])
    
    @mcp_tools._tool(name="repo_branch_mgo", description="Show MGO server branches")
    def repo_branch_mgo() -> Dict[str, Any]:
        cwd = "/a0/usr/projects/mgo_server"
        check = _check_repo(cwd)
        if "error" in check:
            return check
        return _run_git(cwd, ["branch", "-a"])
    
    @mcp_tools._tool(name="repo_branch_telegram", description="Show Telegram repository branches")
    def repo_branch_telegram() -> Dict[str, Any]:
        cwd = "/a0/usr/projects/telegram_to_max"
        check = _check_repo(cwd)
        if "error" in check:
            return check
        return _run_git(cwd, ["branch", "-a"])
    
    # SYNC TOOLS
    
    @mcp_tools._tool(name="repo_sync_mcp", description="Sync MCP server repository with remote")
    def repo_sync_mcp() -> Dict[str, Any]:
        cwd = "/a0/usr/projects/mcp_server"
        check = _check_repo(cwd)
        if "error" in check:
            return check
        fetch = _run_git(cwd, ["fetch"])
        if not fetch.get("success"):
            return fetch
        return _run_git(cwd, ["pull"])
    
    @mcp_tools._tool(name="repo_sync_mgo", description="Sync MGO server repository with remote")
    def repo_sync_mgo() -> Dict[str, Any]:
        cwd = "/a0/usr/projects/mgo_server"
        check = _check_repo(cwd)
        if "error" in check:
            return check
        fetch = _run_git(cwd, ["fetch"])
        if not fetch.get("success"):
            return fetch
        return _run_git(cwd, ["pull"])
    
    @mcp_tools._tool(name="repo_sync_telegram", description="Sync Telegram repository with remote")
    def repo_sync_telegram() -> Dict[str, Any]:
        cwd = "/a0/usr/projects/telegram_to_max"
        check = _check_repo(cwd)
        if "error" in check:
            return check
        fetch = _run_git(cwd, ["fetch"])
        if not fetch.get("success"):
            return fetch
        return _run_git(cwd, ["pull"])
    
    # SNAPSHOT TOOLS
    
    @mcp_tools._tool(name="repo_snapshot_mcp", description="Create snapshot of MCP server changes")
    def repo_snapshot_mcp() -> Dict[str, Any]:
        cwd = "/a0/usr/projects/mcp_server"
        check = _check_repo(cwd)
        if "error" in check:
            return check
        add = _run_git(cwd, ["add", "-A"])
        if not add.get("success"):
            return add
        return _run_git(cwd, ["commit", "-m", "Auto-snapshot"])
    
    @mcp_tools._tool(name="repo_snapshot_mgo", description="Create snapshot of MGO server changes")
    def repo_snapshot_mgo() -> Dict[str, Any]:
        cwd = "/a0/usr/projects/mgo_server"
        check = _check_repo(cwd)
        if "error" in check:
            return check
        add = _run_git(cwd, ["add", "-A"])
        if not add.get("success"):
            return add
        return _run_git(cwd, ["commit", "-m", "Auto-snapshot"])
    
    @mcp_tools._tool(name="repo_snapshot_telegram", description="Create snapshot of Telegram repository changes")
    def repo_snapshot_telegram() -> Dict[str, Any]:
        cwd = "/a0/usr/projects/telegram_to_max"
        check = _check_repo(cwd)
        if "error" in check:
            return check
        add = _run_git(cwd, ["add", "-A"])
        if not add.get("success"):
            return add
        return _run_git(cwd, ["commit", "-m", "Auto-snapshot"])
    
    # UPLOAD TOOLS
    
    @mcp_tools._tool(name="repo_upload_mcp", description="Upload MCP server changes to remote")
    def repo_upload_mcp() -> Dict[str, Any]:
        cwd = "/a0/usr/projects/mcp_server"
        check = _check_repo(cwd)
        if "error" in check:
            return check
        return _run_git(cwd, ["push"])
    
    @mcp_tools._tool(name="repo_upload_mgo", description="Upload MGO server changes to remote")
    def repo_upload_mgo() -> Dict[str, Any]:
        cwd = "/a0/usr/projects/mgo_server"
        check = _check_repo(cwd)
        if "error" in check:
            return check
        return _run_git(cwd, ["push"])
    
    @mcp_tools._tool(name="repo_upload_telegram", description="Upload Telegram repository changes to remote")
    def repo_upload_telegram() -> Dict[str, Any]:
        cwd = "/a0/usr/projects/telegram_to_max"
        check = _check_repo(cwd)
        if "error" in check:
            return check
        return _run_git(cwd, ["push"])
    
    # REVERT TOOLS
    
    @mcp_tools._tool(name="repo_revert_mcp", description="Revert MCP server to last commit")
    def repo_revert_mcp() -> Dict[str, Any]:
        cwd = "/a0/usr/projects/mcp_server"
        check = _check_repo(cwd)
        if "error" in check:
            return check
        return _run_git(cwd, ["reset", "--hard", "HEAD"])
    
    @mcp_tools._tool(name="repo_revert_mgo", description="Revert MGO server to last commit")
    def repo_revert_mgo() -> Dict[str, Any]:
        cwd = "/a0/usr/projects/mgo_server"
        check = _check_repo(cwd)
        if "error" in check:
            return check
        return _run_git(cwd, ["reset", "--hard", "HEAD"])
    
    @mcp_tools._tool(name="repo_revert_telegram", description="Revert Telegram repository to last commit")
    def repo_revert_telegram() -> Dict[str, Any]:
        cwd = "/a0/usr/projects/telegram_to_max"
        check = _check_repo(cwd)
        if "error" in check:
            return check
        return _run_git(cwd, ["reset", "--hard", "HEAD"])
