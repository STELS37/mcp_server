"""Bootstrap and operational brief tools for faster autonomous sessions."""
import json
import os
import subprocess
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Dict, Optional

PROJECTS_ROOT = Path("/a0/usr/projects")
SESSION_STATE_PATH = Path("/a0/usr/projects/mcp_server/.runtime/session_state.json")
LEDGER_PATH = Path("/a0/usr/projects/mcp_server/.runtime/agent_state.json")


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


def _run(cmd, cwd=None):
    return subprocess.run(cmd, cwd=cwd, text=True, capture_output=True)


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _load_json(path: Path, default: Dict[str, Any]) -> Dict[str, Any]:
    if not path.exists():
        return dict(default)
    try:
        data = json.loads(path.read_text())
        if isinstance(data, dict):
            return data
    except Exception:
        pass
    return dict(default)


def _save_json(path: Path, data: Dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False))


def _iter_repos(root: Path):
    for cur, dirs, _ in os.walk(root):
        curp = Path(cur)
        if (curp / ".git").exists():
            yield curp
            dirs[:] = []


def _repo_info(repo: Path) -> Dict[str, Any]:
    branch = _run(["git", "branch", "--show-current"], cwd=repo).stdout.strip() or "main"
    head = _run(["git", "rev-parse", "--short", "HEAD"], cwd=repo).stdout.strip()
    origin = _run(["git", "remote", "get-url", "origin"], cwd=repo).stdout.strip()
    dirty = bool(_run(["git", "status", "--porcelain"], cwd=repo).stdout.strip())
    return {"name": repo.name, "path": str(repo), "branch": branch, "head": head, "origin": origin, "dirty": dirty}


def _service_exists(name: str) -> bool:
    p = _run(["systemctl", "status", name])
    return p.returncode in {0, 3}


def _load_session() -> Dict[str, Any]:
    return _load_json(SESSION_STATE_PATH, {"workspace": None, "service": None, "repo": None, "last_opened_at": None, "history": []})


def _load_ledger() -> Dict[str, Any]:
    return _load_json(LEDGER_PATH, {"actions": [], "health_snapshots": [], "edits": []})


def register_bootstrap_tools(toolset) -> None:
    async def list_projects_inventory(args: Dict[str, Any]) -> Dict[str, Any]:
        root = Path(args.get("root") or str(PROJECTS_ROOT))
        rows = [_repo_info(repo) for repo in _iter_repos(root)]
        return {"content": [{"type": "text", "text": json.dumps(rows, indent=2, ensure_ascii=False)}], "isError": False}

    async def auto_open_workspace(args: Dict[str, Any]) -> Dict[str, Any]:
        session = _load_session()
        project = args.get("project") or args.get("repo_name") or session.get("repo") or "mcp_server"
        workspace = Path(args.get("project_root") or args.get("workspace") or (PROJECTS_ROOT / project))
        repo_name = args.get("repo_name") or workspace.name
        service_name = args.get("service_name") or session.get("service") or repo_name.replace("_", "-")
        if not _service_exists(service_name):
            fallback = repo_name
            if _service_exists(fallback):
                service_name = fallback
            elif _service_exists("mcp-server") and repo_name == "mcp_server":
                service_name = "mcp-server"
            else:
                service_name = service_name
        session["workspace"] = str(workspace)
        session["service"] = service_name
        session["repo"] = repo_name
        session["last_opened_at"] = _utc_now()
        history = list(session.get("history") or [])
        history.append({"action": "auto_open_workspace", "at": _utc_now(), "workspace": str(workspace), "service": service_name, "repo": repo_name})
        session["history"] = history[-40:]
        _save_json(SESSION_STATE_PATH, session)
        payload = {"workspace": str(workspace), "service": service_name, "repo": repo_name, "last_opened_at": session["last_opened_at"]}
        return {"content": [{"type": "text", "text": json.dumps(payload, indent=2, ensure_ascii=False)}], "isError": False}

    async def inspect_current_workspace(args: Dict[str, Any]) -> Dict[str, Any]:
        session = _load_session()
        workspace = Path(session.get("workspace") or PROJECTS_ROOT / "mcp_server")
        repo = _repo_info(workspace) if (workspace / ".git").exists() else {"name": workspace.name, "path": str(workspace)}
        service = session.get("service") or workspace.name
        status = _run(["systemctl", "is-active", service]).stdout.strip() or "unknown"
        tree = _run(["find", str(workspace), "-maxdepth", "2"]).stdout.splitlines()[:80]
        payload = {"session": session, "repo": repo, "service_active": status, "tree_sample": tree}
        return {"content": [{"type": "text", "text": json.dumps(payload, indent=2, ensure_ascii=False)}], "isError": False}

    async def get_operational_brief(args: Dict[str, Any]) -> Dict[str, Any]:
        session = _load_session()
        ledger = _load_ledger()
        recent_failures = [x for x in ledger.get("actions", []) if str(x.get("status", "")).lower() not in {"ok", "success", "passed"}][-5:]
        recent_edits = (ledger.get("edits") or [])[-5:]
        last_health = (ledger.get("health_snapshots") or [])[-1:] or []
        suggestions = []
        if not session.get("workspace"):
            suggestions.append("Run auto_open_workspace or open_workspace first.")
        if recent_failures:
            suggestions.append("Run detect_repeated_failures before retrying the same path.")
        if session.get("service"):
            suggestions.append(f"For service issues, start with debug_service_workflow(service='{session.get('service')}').")
        if session.get("workspace"):
            suggestions.append("For code changes, use read_file_with_hash plus replace_in_file_if_hash_matches or safe_edit_workflow.")
        payload = {
            "session": session,
            "recent_failures": recent_failures,
            "recent_edits": recent_edits,
            "last_health_snapshot": last_health[0] if last_health else {},
            "suggestions": suggestions,
        }
        return {"content": [{"type": "text", "text": json.dumps(payload, indent=2, ensure_ascii=False)}], "isError": False}

    async def suggest_next_actions(args: Dict[str, Any]) -> Dict[str, Any]:
        task_type = (args.get("task_type") or "general").strip().lower()
        session = _load_session()
        actions = []
        if not session.get("workspace"):
            actions.append("auto_open_workspace")
        if task_type == "debug":
            actions.extend(["get_operational_brief", "debug_service_workflow", "detect_repeated_failures"])
        elif task_type == "edit":
            actions.extend(["inspect_current_workspace", "read_file_with_hash", "safe_edit_workflow", "git_sync_repo"])
        elif task_type == "ops":
            actions.extend(["get_operational_brief", "collect_project_diagnostics", "git_sync_all_projects"])
        else:
            actions.extend(["get_operational_brief", "inspect_current_workspace", "detect_repeated_failures"])
        payload = {"task_type": task_type, "recommended_actions": actions, "session": session}
        return {"content": [{"type": "text", "text": json.dumps(payload, indent=2, ensure_ascii=False)}], "isError": False}

    extra = [
        ExtraToolDefinition("list_projects_inventory", "List git-backed projects under /a0/usr/projects with branch, head, origin, and dirty state.", {"type": "object", "properties": {"root": {"type": "string"}}, "required": []}, list_projects_inventory, False, _ro("List Projects Inventory")),
        ExtraToolDefinition("auto_open_workspace", "Infer and set sticky workspace/service/repo context automatically from a project or path.", {"type": "object", "properties": {"project": {"type": "string"}, "project_root": {"type": "string"}, "workspace": {"type": "string"}, "service_name": {"type": "string"}, "repo_name": {"type": "string"}}, "required": []}, auto_open_workspace, False, _rw("Auto Open Workspace", False)),
        ExtraToolDefinition("inspect_current_workspace", "Return a compact session/repo/service/tree snapshot for the current sticky workspace.", {"type": "object", "properties": {}, "required": []}, inspect_current_workspace, False, _ro("Inspect Current Workspace")),
        ExtraToolDefinition("get_operational_brief", "Summarize current session context, recent failures, recent edits, and recommended next steps.", {"type": "object", "properties": {}, "required": []}, get_operational_brief, False, _ro("Get Operational Brief")),
        ExtraToolDefinition("suggest_next_actions", "Return an ordered next-step list for debug, edit, ops, or general tasks using current session context.", {"type": "object", "properties": {"task_type": {"type": "string", "description": "debug, edit, ops, or general"}}, "required": []}, suggest_next_actions, False, _ro("Suggest Next Actions")),
    ]

    for tool in extra:
        toolset._register_tool(tool)

