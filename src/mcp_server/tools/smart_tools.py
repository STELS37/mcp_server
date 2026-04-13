"""Smart workspace diagnosis and recovery tools."""
import json
import subprocess
import urllib.request
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Dict, Optional

PROJECTS_ROOT = Path("/a0/usr/projects")
SESSION_STATE_PATH = Path("/a0/usr/projects/mcp_server/.runtime/session_state.json")
LEDGER_PATH = Path("/a0/usr/projects/mcp_server/.runtime/agent_state.json")
AGENT_ZERO_QUEUE_ROOT = Path("/a0/usr/projects/mcp_server/.runtime/agent_zero_queue")
RECONCILE_AUDIT_PATH = AGENT_ZERO_QUEUE_ROOT / "reconcile_audit.log"


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


def _run(cmd, cwd=None):
    return subprocess.run(cmd, cwd=cwd, text=True, capture_output=True)


def _repo_info(repo: Path) -> Dict[str, Any]:
    branch = _run(["git", "branch", "--show-current"], cwd=repo).stdout.strip() or "main"
    head = _run(["git", "rev-parse", "--short", "HEAD"], cwd=repo).stdout.strip()
    status = _run(["git", "status", "--short"], cwd=repo).stdout.splitlines()
    recent = _run(["git", "log", "--oneline", "-n", "5"], cwd=repo).stdout.splitlines()
    return {"path": str(repo), "branch": branch, "head": head, "dirty": bool(status), "changed": status[:50], "recent_commits": recent[:5]}


def _resolve_workspace(project: Optional[str], workspace: Optional[str]) -> Path:
    if workspace:
        return Path(workspace)
    if project:
        path = Path(project)
        return path if str(path).startswith("/") else PROJECTS_ROOT / project
    session = _load_json(SESSION_STATE_PATH, {"workspace": None})
    return Path(session.get("workspace") or (PROJECTS_ROOT / "mcp_server"))


def _resolve_service(service: Optional[str], workspace: Path) -> str:
    if service:
        return service
    session = _load_json(SESSION_STATE_PATH, {"service": None})
    return session.get("service") or workspace.name.replace("_", "-")


def register_smart_tools(toolset) -> None:
    async def summarize_repo_state(args: Dict[str, Any]) -> Dict[str, Any]:
        workspace = _resolve_workspace(args.get("project"), args.get("workspace"))
        payload = _repo_info(workspace) if (workspace / ".git").exists() else {"path": str(workspace), "error": "not a git repo"}
        return {"content": [{"type": "text", "text": json.dumps(payload, indent=2, ensure_ascii=False)}], "isError": False}

    async def auto_diagnose_workspace(args: Dict[str, Any]) -> Dict[str, Any]:
        workspace = _resolve_workspace(args.get("project"), args.get("workspace"))
        service = _resolve_service(args.get("service"), workspace)
        port = args.get("port")
        ledger = _load_json(LEDGER_PATH, {"actions": [], "health_snapshots": [], "edits": []})
        repo = _repo_info(workspace) if (workspace / ".git").exists() else {"path": str(workspace), "error": "not a git repo"}
        active = _run(["systemctl", "is-active", service]).stdout.strip() or "unknown"
        status = _run(["systemctl", "status", service, "--no-pager"]).stdout.splitlines()[:25]
        logs = _run(["journalctl", "-u", service, "-n", "40", "--no-pager"]).stdout.splitlines()[-40:]
        payload = {
            "workspace": str(workspace),
            "service": service,
            "service_active": active,
            "status_excerpt": status,
            "logs_excerpt": logs,
            "repo": repo,
            "recent_failures": [x for x in ledger.get("actions", []) if str(x.get("status", "")).lower() not in {"ok", "success", "passed"}][-5:],
            "recent_edits": (ledger.get("edits") or [])[-5:],
        }
        if port:
            payload["port"] = int(port)
            payload["port_check"] = _run(["bash", "-lc", f"ss -ltnp | grep ':{int(port)} ' || true"]).stdout.splitlines()
            payload["health"] = _run(["curl", "-fsS", f"http://127.0.0.1:{int(port)}/health"]).stdout.strip()
            payload["ready"] = _run(["curl", "-fsS", f"http://127.0.0.1:{int(port)}/ready"]).stdout.strip()
        return {"content": [{"type": "text", "text": json.dumps(payload, indent=2, ensure_ascii=False)}], "isError": False}

    async def quick_recovery_plan(args: Dict[str, Any]) -> Dict[str, Any]:
        workspace = _resolve_workspace(args.get("project"), args.get("workspace"))
        service = _resolve_service(args.get("service"), workspace)
        task_type = (args.get("task_type") or "general").lower()
        plan = ["auto_diagnose_workspace"]
        if task_type == "debug":
            plan += ["detect_repeated_failures", "debug_service_workflow", "get_operational_brief"]
        elif task_type == "edit":
            plan += ["read_file_with_hash", "safe_edit_workflow", "git_sync_repo"]
        elif task_type == "ops":
            plan += ["collect_project_diagnostics", "repo_sync_workflow", "git_sync_all_projects"]
        else:
            plan += ["inspect_current_workspace", "suggest_next_actions"]
        payload = {"workspace": str(workspace), "service": service, "task_type": task_type, "recommended_actions": plan}
        return {"content": [{"type": "text", "text": json.dumps(payload, indent=2, ensure_ascii=False)}], "isError": False}

    async def self_check_server_state(args: Dict[str, Any]) -> Dict[str, Any]:
        workspace = _resolve_workspace(args.get("project"), args.get("workspace"))
        service = _resolve_service(args.get("service"), workspace)
        checks = {}
        issues = []

        session = _load_json(SESSION_STATE_PATH, {"workspace": None, "service": None, "repo": None})
        checks["session_state"] = {
            "path": str(SESSION_STATE_PATH),
            "exists": SESSION_STATE_PATH.exists(),
            "workspace": session.get("workspace"),
            "service": session.get("service"),
            "repo": session.get("repo"),
        }
        if not SESSION_STATE_PATH.exists():
            issues.append("session_state_missing")

        local_names = []
        http_names = []
        http_error = None
        try:
            from mcp_server.tools.mcp_tools import MCPTools
            local_names = sorted([t.name for t in MCPTools(None).list_tools()])
        except Exception as exc:
            issues.append("local_registry_build_failed")
            checks["local_registry_error"] = str(exc)
        try:
            with urllib.request.urlopen("http://127.0.0.1:8000/mcp", timeout=10) as r:
                body = json.loads(r.read().decode())
            http_names = sorted([t.get("name") for t in body.get("result", {}).get("tools", [])])
        except Exception as exc:
            http_error = str(exc)
            issues.append("http_discovery_failed")
        missing_in_http = [n for n in local_names if n not in http_names]
        extra_in_http = [n for n in http_names if n not in local_names]
        checks["tool_registry"] = {
            "local_count": len(local_names),
            "http_count": len(http_names),
            "missing_in_http": missing_in_http,
            "extra_in_http": extra_in_http,
            "http_error": http_error,
        }
        if missing_in_http or extra_in_http:
            issues.append("tool_registry_mismatch")

        service_active = _run(["systemctl", "is-active", service]).stdout.strip() or "unknown"
        checks["service"] = {"service": service, "active": service_active}
        if service_active not in {"active", "activating"}:
            issues.append("service_not_active")

        processing = sorted((AGENT_ZERO_QUEUE_ROOT / "processing").glob("*.json")) if AGENT_ZERO_QUEUE_ROOT.exists() else []
        failed = sorted((AGENT_ZERO_QUEUE_ROOT / "failed").glob("*.json")) if AGENT_ZERO_QUEUE_ROOT.exists() else []
        audit_exists = RECONCILE_AUDIT_PATH.exists()
        checks["agent_zero_queue"] = {
            "processing_count": len(processing),
            "failed_count": len(failed),
            "audit_exists": audit_exists,
            "processing_tasks": [p.stem for p in processing[:20]],
            "failed_tasks": [p.stem for p in failed[:20]],
        }
        if len(processing) > 3:
            issues.append("agent_zero_processing_backlog")

        payload = {
            "workspace": str(workspace),
            "service": service,
            "checks": checks,
            "issues": issues,
            "healthy": not issues,
        }
        return {"content": [{"type": "text", "text": json.dumps(payload, indent=2, ensure_ascii=False)}], "isError": bool(issues)}

    async def auto_recover_service(args: Dict[str, Any]) -> Dict[str, Any]:
        workspace = _resolve_workspace(args.get("project"), args.get("workspace"))
        service = _resolve_service(args.get("service"), workspace)
        port = args.get("port")
        before = _run(["systemctl", "is-active", service]).stdout.strip() or "unknown"
        restart = _run(["systemctl", "restart", service])
        after = _run(["systemctl", "is-active", service]).stdout.strip() or "unknown"
        payload = {"service": service, "before": before, "after": after, "restart_stdout": restart.stdout.strip(), "restart_stderr": restart.stderr.strip()}
        if port:
            payload["health"] = _run(["curl", "-fsS", f"http://127.0.0.1:{int(port)}/health"]).stdout.strip()
            payload["ready"] = _run(["curl", "-fsS", f"http://127.0.0.1:{int(port)}/ready"]).stdout.strip()
        return {"content": [{"type": "text", "text": json.dumps(payload, indent=2, ensure_ascii=False)}], "isError": after not in {"active", "activating"}}

    extra = [
        ExtraToolDefinition("summarize_repo_state", "Return a concise git summary for the current or specified workspace including changed files and recent commits.", {"type": "object", "properties": {"project": {"type": "string"}, "workspace": {"type": "string"}}, "required": []}, summarize_repo_state, False, _ro("Summarize Repo State")),
        ExtraToolDefinition("auto_diagnose_workspace", "Collect service, repo, failure, edit, and optional health context for the current or specified workspace.", {"type": "object", "properties": {"project": {"type": "string"}, "workspace": {"type": "string"}, "service": {"type": "string"}, "port": {"type": "integer"}}, "required": []}, auto_diagnose_workspace, False, _ro("Auto Diagnose Workspace")),
        ExtraToolDefinition("quick_recovery_plan", "Suggest the fastest next-step sequence for debug, edit, ops, or general recovery in the current workspace.", {"type": "object", "properties": {"project": {"type": "string"}, "workspace": {"type": "string"}, "service": {"type": "string"}, "task_type": {"type": "string"}}, "required": []}, quick_recovery_plan, False, _ro("Quick Recovery Plan")),
        ExtraToolDefinition("auto_recover_service", "Attempt a direct restart/recovery for the current or specified service and optionally verify health endpoints.", {"type": "object", "properties": {"project": {"type": "string"}, "workspace": {"type": "string"}, "service": {"type": "string"}, "port": {"type": "integer"}}, "required": []}, auto_recover_service, False, _rw("Auto Recover Service", False)),
        ExtraToolDefinition("self_check_server_state", "Run a self-check across session state, local tool registry, HTTP discovery, service activity, and Agent Zero queue health.", {"type": "object", "properties": {"project": {"type": "string"}, "workspace": {"type": "string"}, "service": {"type": "string"}}, "required": []}, self_check_server_state, False, _ro("Self Check Server State")),
    ]

    for tool in extra:
        toolset._register_tool(tool)

