"""Intent and goal router tools for selecting and running high-level workflows."""
import json
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Tuple

SESSION_STATE_PATH = Path("/a0/usr/projects/mcp_server/.runtime/session_state.json")
ROUTER_STATE_PATH = Path("/a0/usr/projects/mcp_server/.runtime/router_state.json")


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


def _load_session() -> Dict[str, Any]:
    return _load_json(SESSION_STATE_PATH, {"workspace": None, "service": None, "repo": None})


def _load_router_state() -> Dict[str, Any]:
    state = _load_json(ROUTER_STATE_PATH, {"last_run": None, "history": []})
    state.setdefault("last_run", None)
    state.setdefault("history", [])
    return state


def _route_intent(intent: str) -> Tuple[str, str]:
    key = (intent or "").strip().lower()
    table = {
        "hotfix": ("full_hotfix_workflow", "Urgent production fix with optional edit, restart, verify, and git sync."),
        "release": ("full_release_workflow", "Release/build/deploy flow with verification and optional tag push."),
        "incident": ("full_incident_response_workflow", "Incident diagnostics, optional custom incident command, recovery, and final verification."),
        "debug": ("full_debug_and_fix_workflow", "Service diagnosis with optional edit, restart, verify, and git sync."),
        "fix": ("full_fix_workflow", "One-shot file fix with optional restart, health check, and git sync."),
        "deploy": ("full_deploy_workflow", "Deploy/build, restart, verify, and optional pre/post commands."),
        "recovery": ("full_service_recovery_workflow", "Focused service recovery with logs, restart, and optional health verification."),
        "maintenance": ("full_project_maintenance_workflow", "Project inspection, optional maintenance commands, service verification, and repo sync."),
        "sync": ("full_repo_sync_workflow", "Repo fetch/add/commit/push with pull --rebase fallback."),
    }
    return table.get(key, ("full_project_maintenance_workflow", "Default maintenance workflow for unknown intents."))


def _infer_intent_from_goal(goal: str) -> Tuple[str, str]:
    text = (goal or "").strip().lower()
    rules = [
        ("incident", ["incident", "outage", "down", "broken production", "p1", "sev", "alarm", "emergency"]),
        ("hotfix", ["hotfix", "urgent fix", "quick fix", "prod fix", "patch now"]),
        ("release", ["release", "publish", "rollout", "ship", "version", "tag", "deploy release"]),
        ("deploy", ["deploy", "redeploy", "build and deploy", "roll out"]),
        ("recovery", ["recover", "restart service", "bring back", "service recovery", "restore service"]),
        ("sync", ["sync", "push changes", "commit and push", "repo sync", "git sync"]),
        ("debug", ["debug", "investigate", "diagnose", "check logs", "find issue", "root cause"]),
        ("fix", ["fix", "edit file", "change config", "patch file", "replace text"]),
        ("maintenance", ["maintenance", "clean up", "housekeeping", "inspect project", "project maintenance"]),
    ]
    for intent, needles in rules:
        if any(needle in text for needle in needles):
            return intent, f"Matched goal keywords for {intent}."
    return "maintenance", "No strong keyword match; defaulted to maintenance workflow."


def _build_workflow_args(intent: str, args: Dict[str, Any], session: Dict[str, Any]) -> Dict[str, Any]:
    workflow_args: Dict[str, Any] = {}
    for key in (
        "project", "project_root", "workspace", "service", "port", "path", "search", "replace",
        "message", "use_sudo", "timeout", "pre_command", "post_command", "build_command",
        "deploy_command", "version", "tag_name", "incident_command", "rollback"
    ):
        if key in args and args.get(key) is not None:
            workflow_args[key] = args.get(key)
    if "project_root" not in workflow_args and session.get("workspace"):
        workflow_args["project_root"] = session.get("workspace")
    if "service" not in workflow_args and session.get("service"):
        workflow_args["service"] = session.get("service")
    if "project" not in workflow_args and session.get("repo"):
        workflow_args["project"] = session.get("repo")
    if intent == "maintenance" and "message" not in workflow_args:
        workflow_args["message"] = "intent maintenance workflow"
    if intent == "hotfix" and "message" not in workflow_args:
        workflow_args["message"] = "intent hotfix workflow"
    if intent == "release" and "message" not in workflow_args:
        workflow_args["message"] = "intent release workflow"
    if intent == "incident" and "message" not in workflow_args:
        workflow_args["message"] = "intent incident workflow"
    return workflow_args


def _make_prefix(intent: str, workflow_name: str, description: str, workflow_args: Dict[str, Any], session: Dict[str, Any], extra: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    payload = {
        "intent": intent,
        "selected_workflow": workflow_name,
        "description": description,
        "session": session,
        "workflow_args": workflow_args,
    }
    if extra:
        payload.update(extra)
    return payload


def _summarize_result(result: Dict[str, Any]) -> str:
    parts: List[str] = []
    for item in result.get("content", []) or []:
        if isinstance(item, dict) and item.get("type") == "text" and item.get("text"):
            parts.append(str(item.get("text")))
    text = "\n".join(parts).strip()
    if not text:
        return "no textual result"
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    summary = " | ".join(lines[:4])
    return summary[:800]


def _record_router_run(metadata: Dict[str, Any]) -> None:
    state = _load_router_state()
    state["last_run"] = metadata
    history = list(state.get("history") or [])
    history.append(metadata)
    state["history"] = history[-40:]
    _save_json(ROUTER_STATE_PATH, state)


def register_router_tools(toolset) -> None:
    async def preview_intent_workflow(args: Dict[str, Any]) -> Dict[str, Any]:
        session = _load_session()
        intent = args.get("intent") or "maintenance"
        workflow_name, description = _route_intent(intent)
        workflow_args = _build_workflow_args(intent, args, session)
        payload = _make_prefix(intent, workflow_name, description, workflow_args, session)
        return {"content": [{"type": "text", "text": json.dumps(payload, indent=2, ensure_ascii=False)}], "isError": False}

    async def run_intent_workflow(args: Dict[str, Any]) -> Dict[str, Any]:
        session = _load_session()
        intent = args.get("intent") or "maintenance"
        workflow_name, description = _route_intent(intent)
        workflow_args = _build_workflow_args(intent, args, session)
        user = args.get("_user", "unknown")
        result = await toolset.execute_tool(workflow_name, workflow_args, user=user)
        metadata = {
            "ran_at": _utc_now(),
            "intent": intent,
            "selected_workflow": workflow_name,
            "description": description,
            "workflow_args": workflow_args,
            "is_error": bool(result.get("isError")),
            "summary": _summarize_result(result),
        }
        _record_router_run(metadata)
        if result.get("content") and isinstance(result["content"], list) and result["content"]:
            prefix = _make_prefix(intent, workflow_name, description, workflow_args, session, {"result_summary": metadata["summary"], "ran_at": metadata["ran_at"]})
            text = json.dumps(prefix, indent=2, ensure_ascii=False) + "\n\n=== WORKFLOW RESULT ===\n\n"
            first = result["content"][0]
            if isinstance(first, dict) and first.get("type") == "text":
                first["text"] = text + str(first.get("text") or "")
        return result

    async def preview_goal_routing(args: Dict[str, Any]) -> Dict[str, Any]:
        session = _load_session()
        goal = args.get("goal") or ""
        inferred_intent, reason = _infer_intent_from_goal(goal)
        workflow_name, description = _route_intent(inferred_intent)
        workflow_args = _build_workflow_args(inferred_intent, args, session)
        payload = _make_prefix(inferred_intent, workflow_name, description, workflow_args, session, {"goal": goal, "routing_reason": reason})
        return {"content": [{"type": "text", "text": json.dumps(payload, indent=2, ensure_ascii=False)}], "isError": False}

    async def run_goal_workflow(args: Dict[str, Any]) -> Dict[str, Any]:
        session = _load_session()
        goal = args.get("goal") or ""
        inferred_intent, reason = _infer_intent_from_goal(goal)
        workflow_name, description = _route_intent(inferred_intent)
        workflow_args = _build_workflow_args(inferred_intent, args, session)
        user = args.get("_user", "unknown")
        result = await toolset.execute_tool(workflow_name, workflow_args, user=user)
        metadata = {
            "ran_at": _utc_now(),
            "goal": goal,
            "intent": inferred_intent,
            "selected_workflow": workflow_name,
            "description": description,
            "workflow_args": workflow_args,
            "routing_reason": reason,
            "is_error": bool(result.get("isError")),
            "summary": _summarize_result(result),
        }
        _record_router_run(metadata)
        if result.get("content") and isinstance(result["content"], list) and result["content"]:
            prefix = _make_prefix(inferred_intent, workflow_name, description, workflow_args, session, {"goal": goal, "routing_reason": reason, "result_summary": metadata["summary"], "ran_at": metadata["ran_at"]})
            text = json.dumps(prefix, indent=2, ensure_ascii=False) + "\n\n=== WORKFLOW RESULT ===\n\n"
            first = result["content"][0]
            if isinstance(first, dict) and first.get("type") == "text":
                first["text"] = text + str(first.get("text") or "")
        return result

    async def rerun_last_routed_workflow(args: Dict[str, Any]) -> Dict[str, Any]:
        router_state = _load_router_state()
        last_run = router_state.get("last_run") or {}
        workflow_name = last_run.get("selected_workflow")
        workflow_args = dict(last_run.get("workflow_args") or {})
        if not workflow_name:
            return {"content": [{"type": "text", "text": "No last routed workflow found."}], "isError": True}
        for key in ("project", "project_root", "service", "port", "path", "search", "replace", "message", "use_sudo", "timeout", "pre_command", "post_command", "build_command", "deploy_command", "version", "tag_name", "incident_command", "rollback"):
            if key in args and args.get(key) is not None:
                workflow_args[key] = args.get(key)
        user = args.get("_user", "unknown")
        result = await toolset.execute_tool(workflow_name, workflow_args, user=user)
        metadata = {
            "ran_at": _utc_now(),
            "rerun": True,
            "intent": last_run.get("intent") or "maintenance",
            "selected_workflow": workflow_name,
            "description": "Rerun of last routed workflow.",
            "workflow_args": workflow_args,
            "last_run_metadata": last_run,
            "is_error": bool(result.get("isError")),
            "summary": _summarize_result(result),
        }
        _record_router_run(metadata)
        if result.get("content") and isinstance(result["content"], list) and result["content"]:
            prefix = {
                "rerun": True,
                "selected_workflow": workflow_name,
                "workflow_args": workflow_args,
                "last_run_metadata": last_run,
                "result_summary": metadata["summary"],
                "ran_at": metadata["ran_at"],
            }
            text = json.dumps(prefix, indent=2, ensure_ascii=False) + "\n\n=== WORKFLOW RESULT ===\n\n"
            first = result["content"][0]
            if isinstance(first, dict) and first.get("type") == "text":
                first["text"] = text + str(first.get("text") or "")
        return result

    async def get_router_history(args: Dict[str, Any]) -> Dict[str, Any]:
        state = _load_router_state()
        limit = int(args.get("limit", 10))
        rows = list(state.get("history") or [])[-limit:]
        return {"content": [{"type": "text", "text": json.dumps(rows, indent=2, ensure_ascii=False)}], "isError": False}

    async def get_last_workflow_summary(args: Dict[str, Any]) -> Dict[str, Any]:
        state = _load_router_state()
        last_run = state.get("last_run") or {}
        payload = {
            "ran_at": last_run.get("ran_at"),
            "goal": last_run.get("goal"),
            "intent": last_run.get("intent"),
            "selected_workflow": last_run.get("selected_workflow"),
            "is_error": last_run.get("is_error"),
            "summary": last_run.get("summary"),
            "workflow_args": last_run.get("workflow_args") or {},
        }
        return {"content": [{"type": "text", "text": json.dumps(payload, indent=2, ensure_ascii=False)}], "isError": False}

    extra = [
        ExtraToolDefinition("preview_intent_workflow", "Preview which high-level workflow will be selected for an intent and what arguments will be passed after session-context merging.", {"type": "object", "properties": {"intent": {"type": "string", "description": "hotfix, release, incident, debug, fix, deploy, recovery, maintenance, or sync"}, "project": {"type": "string"}, "project_root": {"type": "string"}, "service": {"type": "string"}, "port": {"type": "integer"}, "path": {"type": "string"}, "search": {"type": "string"}, "replace": {"type": "string"}, "message": {"type": "string"}, "use_sudo": {"type": "boolean"}, "timeout": {"type": "integer"}, "pre_command": {"type": "string"}, "post_command": {"type": "string"}, "build_command": {"type": "string"}, "deploy_command": {"type": "string"}, "version": {"type": "string"}, "tag_name": {"type": "string"}, "incident_command": {"type": "string"}, "rollback": {"type": "boolean"}}, "required": []}, preview_intent_workflow, False, _ro("Preview Intent Workflow")),
        ExtraToolDefinition("run_intent_workflow", "Run a selected high-level workflow by intent, automatically merging sticky session context such as workspace, repo, and service.", {"type": "object", "properties": {"intent": {"type": "string", "description": "hotfix, release, incident, debug, fix, deploy, recovery, maintenance, or sync"}, "project": {"type": "string"}, "project_root": {"type": "string"}, "service": {"type": "string"}, "port": {"type": "integer"}, "path": {"type": "string"}, "search": {"type": "string"}, "replace": {"type": "string"}, "message": {"type": "string"}, "use_sudo": {"type": "boolean"}, "timeout": {"type": "integer"}, "pre_command": {"type": "string"}, "post_command": {"type": "string"}, "build_command": {"type": "string"}, "deploy_command": {"type": "string"}, "version": {"type": "string"}, "tag_name": {"type": "string"}, "incident_command": {"type": "string"}, "rollback": {"type": "boolean"}}, "required": ["intent"]}, run_intent_workflow, False, _rw("Run Intent Workflow", False)),
        ExtraToolDefinition("preview_goal_routing", "Preview how a freeform goal will be mapped to an intent and high-level workflow after session-context merging.", {"type": "object", "properties": {"goal": {"type": "string"}, "project": {"type": "string"}, "project_root": {"type": "string"}, "service": {"type": "string"}, "port": {"type": "integer"}, "path": {"type": "string"}, "search": {"type": "string"}, "replace": {"type": "string"}, "message": {"type": "string"}, "use_sudo": {"type": "boolean"}, "timeout": {"type": "integer"}, "pre_command": {"type": "string"}, "post_command": {"type": "string"}, "build_command": {"type": "string"}, "deploy_command": {"type": "string"}, "version": {"type": "string"}, "tag_name": {"type": "string"}, "incident_command": {"type": "string"}, "rollback": {"type": "boolean"}}, "required": ["goal"]}, preview_goal_routing, False, _ro("Preview Goal Routing")),
        ExtraToolDefinition("run_goal_workflow", "Infer an intent from a freeform goal and run the selected high-level workflow with merged session context.", {"type": "object", "properties": {"goal": {"type": "string"}, "project": {"type": "string"}, "project_root": {"type": "string"}, "service": {"type": "string"}, "port": {"type": "integer"}, "path": {"type": "string"}, "search": {"type": "string"}, "replace": {"type": "string"}, "message": {"type": "string"}, "use_sudo": {"type": "boolean"}, "timeout": {"type": "integer"}, "pre_command": {"type": "string"}, "post_command": {"type": "string"}, "build_command": {"type": "string"}, "deploy_command": {"type": "string"}, "version": {"type": "string"}, "tag_name": {"type": "string"}, "incident_command": {"type": "string"}, "rollback": {"type": "boolean"}}, "required": ["goal"]}, run_goal_workflow, False, _rw("Run Goal Workflow")),
        ExtraToolDefinition("rerun_last_routed_workflow", "Rerun the most recent routed workflow, optionally overriding selected arguments like path, service, port, message, or timeout.", {"type": "object", "properties": {"project": {"type": "string"}, "project_root": {"type": "string"}, "service": {"type": "string"}, "port": {"type": "integer"}, "path": {"type": "string"}, "search": {"type": "string"}, "replace": {"type": "string"}, "message": {"type": "string"}, "use_sudo": {"type": "boolean"}, "timeout": {"type": "integer"}, "pre_command": {"type": "string"}, "post_command": {"type": "string"}, "build_command": {"type": "string"}, "deploy_command": {"type": "string"}, "version": {"type": "string"}, "tag_name": {"type": "string"}, "incident_command": {"type": "string"}, "rollback": {"type": "boolean"}}, "required": []}, rerun_last_routed_workflow, False, _rw("Rerun Last Routed Workflow")),
        ExtraToolDefinition("get_router_history", "Return the recent history of routed workflow runs with timestamps, chosen workflows, error flags, and short summaries.", {"type": "object", "properties": {"limit": {"type": "integer", "default": 10}}, "required": []}, get_router_history, False, _ro("Get Router History")),
        ExtraToolDefinition("get_last_workflow_summary", "Return a compact summary of the most recent routed workflow run, including the chosen workflow, error flag, and merged args.", {"type": "object", "properties": {}, "required": []}, get_last_workflow_summary, False, _ro("Get Last Workflow Summary")),
    ]

    for tool in extra:
        toolset._register_tool(tool)

