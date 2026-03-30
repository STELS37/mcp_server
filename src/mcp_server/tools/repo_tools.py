"""Git-native repo tools for project sync and repo inspection."""
import json
import os
import subprocess
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Dict, Optional

DEFAULT_ROOT = Path("/a0/usr/projects")


@dataclass
class ExtraToolDefinition:
    name: str
    description: str
    input_schema: Dict[str, Any]
    handler: Callable
    dangerous: bool = False
    annotations: Optional[Dict[str, Any]] = None


def _ro(title: str) -> Dict[str, Any]:
    return {"title": title, "readOnlyHint": True, "destructiveHint": False, "idempotentHint": True, "openWorldHint": False}


def _rw(title: str, destructive: bool = False) -> Dict[str, Any]:
    return {"title": title, "readOnlyHint": False, "destructiveHint": destructive, "idempotentHint": False, "openWorldHint": False}


def _repo_path(project: str) -> Path:
    path = Path(project)
    return path if str(path).startswith("/") else DEFAULT_ROOT / project


def _run(repo: Path, cmd):
    return subprocess.run(cmd, cwd=repo, text=True, capture_output=True)


def _ensure_identity(repo: Path) -> None:
    name = _run(repo, ["git", "config", "user.name"]).stdout.strip()
    email = _run(repo, ["git", "config", "user.email"]).stdout.strip()
    if not name:
        _run(repo, ["git", "config", "user.name", "Agent Zero"])
    if not email:
        _run(repo, ["git", "config", "user.email", "agent-zero@localhost"])


def register_repo_tools(toolset) -> None:
    async def git_status_repo(args: Dict[str, Any]) -> Dict[str, Any]:
        repo = _repo_path(args.get("project"))
        p = _run(repo, ["git", "status", "--short"])
        return {"content": [{"type": "text", "text": p.stdout.strip() or "clean"}], "isError": p.returncode != 0}

    async def git_changed_files(args: Dict[str, Any]) -> Dict[str, Any]:
        repo = _repo_path(args.get("project"))
        p = _run(repo, ["git", "status", "--porcelain"])
        files = []
        for line in p.stdout.splitlines():
            if len(line) > 3:
                files.append(line[3:])
        return {"content": [{"type": "text", "text": json.dumps(files, indent=2, ensure_ascii=False)}], "isError": p.returncode != 0}

    async def git_current_head(args: Dict[str, Any]) -> Dict[str, Any]:
        repo = _repo_path(args.get("project"))
        head = _run(repo, ["git", "rev-parse", "HEAD"]).stdout.strip()
        short = _run(repo, ["git", "rev-parse", "--short", "HEAD"]).stdout.strip()
        branch = _run(repo, ["git", "branch", "--show-current"]).stdout.strip()
        origin = _run(repo, ["git", "remote", "get-url", "origin"]).stdout.strip()
        text = json.dumps({"repo": str(repo), "branch": branch, "head": head, "short": short, "origin": origin}, indent=2, ensure_ascii=False)
        return {"content": [{"type": "text", "text": text}], "isError": False}

    async def git_add_all(args: Dict[str, Any]) -> Dict[str, Any]:
        repo = _repo_path(args.get("project"))
        p = _run(repo, ["git", "add", "-A"])
        return {"content": [{"type": "text", "text": "added"}], "isError": p.returncode != 0}

    async def git_commit_repo(args: Dict[str, Any]) -> Dict[str, Any]:
        repo = _repo_path(args.get("project"))
        _ensure_identity(repo)
        msg = args.get("message") or f"auto-sync: {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%SZ')}"
        p = _run(repo, ["git", "commit", "-m", msg])
        text = (p.stdout + p.stderr).strip() or "done"
        is_error = p.returncode != 0 and "nothing to commit" not in text.lower()
        return {"content": [{"type": "text", "text": text}], "isError": is_error}

    async def git_push_repo(args: Dict[str, Any]) -> Dict[str, Any]:
        repo = _repo_path(args.get("project"))
        branch = args.get("branch") or _run(repo, ["git", "branch", "--show-current"]).stdout.strip() or "main"
        p = _run(repo, ["git", "push", "origin", branch])
        return {"content": [{"type": "text", "text": (p.stdout + p.stderr).strip() or "done"}], "isError": p.returncode != 0}

    async def git_pull_rebase_repo(args: Dict[str, Any]) -> Dict[str, Any]:
        repo = _repo_path(args.get("project"))
        branch = args.get("branch") or _run(repo, ["git", "branch", "--show-current"]).stdout.strip() or "main"
        p = _run(repo, ["git", "pull", "--rebase", "origin", branch])
        return {"content": [{"type": "text", "text": (p.stdout + p.stderr).strip() or "done"}], "isError": p.returncode != 0}

    async def git_sync_repo(args: Dict[str, Any]) -> Dict[str, Any]:
        repo = _repo_path(args.get("project"))
        branch = args.get("branch") or _run(repo, ["git", "branch", "--show-current"]).stdout.strip() or "main"
        _ensure_identity(repo)
        _run(repo, ["git", "fetch", "origin"])
        status = _run(repo, ["git", "status", "--porcelain"]).stdout.strip()
        if status:
            _run(repo, ["git", "add", "-A"])
            _run(repo, ["git", "commit", "-m", args.get("message") or f"auto-sync: {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%SZ')}"])
        p = _run(repo, ["git", "push", "origin", branch])
        combined = (p.stdout + p.stderr).strip()
        low = combined.lower()
        if p.returncode != 0 and ("non-fast-forward" in low or "fetch first" in low or "rejected" in low):
            pr = _run(repo, ["git", "pull", "--rebase", "origin", branch])
            p2 = _run(repo, ["git", "push", "origin", branch])
            combined = (combined + "\n" + pr.stdout + pr.stderr + "\n" + p2.stdout + p2.stderr).strip()
            return {"content": [{"type": "text", "text": combined}], "isError": p2.returncode != 0}
        return {"content": [{"type": "text", "text": combined or "sync ok"}], "isError": p.returncode != 0}

    async def git_sync_all_projects(args: Dict[str, Any]) -> Dict[str, Any]:
        root = Path(args.get("root") or str(DEFAULT_ROOT))
        results = []
        for cur, dirs, _ in os.walk(root):
            curp = Path(cur)
            if (curp / ".git").exists():
                branch = _run(curp, ["git", "branch", "--show-current"]).stdout.strip() or "main"
                _ensure_identity(curp)
                _run(curp, ["git", "fetch", "origin"])
                status = _run(curp, ["git", "status", "--porcelain"]).stdout.strip()
                if status:
                    _run(curp, ["git", "add", "-A"])
                    _run(curp, ["git", "commit", "-m", args.get("message") or f"auto-sync: {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%SZ')}"])
                p = _run(curp, ["git", "push", "origin", branch])
                results.append({"repo": str(curp), "branch": branch, "ok": p.returncode == 0, "output": (p.stdout + p.stderr).strip()})
                dirs[:] = []
        return {"content": [{"type": "text", "text": json.dumps(results, indent=2, ensure_ascii=False)}], "isError": False}

    extra = [
        ExtraToolDefinition("git_status_repo", "Return git status for a repo under /a0/usr/projects or an absolute repo path.", {"type": "object", "properties": {"project": {"type": "string"}}, "required": ["project"]}, git_status_repo, False, _ro("Git Status Repo")),
        ExtraToolDefinition("git_changed_files", "Return changed files for a repo.", {"type": "object", "properties": {"project": {"type": "string"}}, "required": ["project"]}, git_changed_files, False, _ro("Git Changed Files")),
        ExtraToolDefinition("git_current_head", "Return branch/head/origin for a repo.", {"type": "object", "properties": {"project": {"type": "string"}}, "required": ["project"]}, git_current_head, False, _ro("Git Current Head")),
        ExtraToolDefinition("git_add_all", "Stage all local changes in a repo.", {"type": "object", "properties": {"project": {"type": "string"}}, "required": ["project"]}, git_add_all, False, _rw("Git Add All", False)),
        ExtraToolDefinition("git_commit_repo", "Create a git commit in a repo.", {"type": "object", "properties": {"project": {"type": "string"}, "message": {"type": "string"}}, "required": ["project"]}, git_commit_repo, False, _rw("Git Commit Repo", False)),
        ExtraToolDefinition("git_push_repo", "Push the current branch of a repo to origin.", {"type": "object", "properties": {"project": {"type": "string"}, "branch": {"type": "string"}}, "required": ["project"]}, git_push_repo, False, _rw("Git Push Repo", False)),
        ExtraToolDefinition("git_pull_rebase_repo", "Pull --rebase from origin for a repo.", {"type": "object", "properties": {"project": {"type": "string"}, "branch": {"type": "string"}}, "required": ["project"]}, git_pull_rebase_repo, False, _rw("Git Pull Rebase Repo", False)),
        ExtraToolDefinition("git_sync_repo", "Stage, commit, and push a repo with automatic pull --rebase on non-fast-forward.", {"type": "object", "properties": {"project": {"type": "string"}, "branch": {"type": "string"}, "message": {"type": "string"}}, "required": ["project"]}, git_sync_repo, False, _rw("Git Sync Repo", False)),
        ExtraToolDefinition("git_sync_all_projects", "Run a git sync pass across all repos under a root path.", {"type": "object", "properties": {"root": {"type": "string"}, "message": {"type": "string"}}, "required": []}, git_sync_all_projects, False, _rw("Git Sync All Projects", False)),
    ]

    for tool in extra:
        toolset._register_tool(tool)

