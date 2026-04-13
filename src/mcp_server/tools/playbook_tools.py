"""Playbook tools that teach the MCP client how to operate this server efficiently."""
from dataclasses import dataclass
import json
import subprocess
import urllib.request
from typing import Any, Callable, Dict, Optional
from pathlib import Path


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



SESSION_STATE_PATH = Path("/a0/usr/projects/mcp_server/.runtime/session_state.json")


def _session_check_summary(project_root: str, service_name: str, local_base: str) -> Dict[str, Any]:
    summary = {
        "service_active": "unknown",
        "http_mcp_tools": None,
        "session_state_exists": SESSION_STATE_PATH.exists(),
        "issues": [],
    }
    try:
        active = subprocess.run(["systemctl", "is-active", service_name], text=True, capture_output=True).stdout.strip() or "unknown"
        summary["service_active"] = active
        if active not in {"active", "activating"}:
            summary["issues"].append("service_not_active")
    except Exception as exc:
        summary["issues"].append(f"service_check_error:{exc}")

    try:
        with urllib.request.urlopen(f"{local_base}/mcp", timeout=5) as r:
            body = json.loads(r.read().decode())
        names = [t.get("name") for t in body.get("result", {}).get("tools", [])]
        summary["http_mcp_tools"] = len(names)
        for required in ["start_work_session", "get_session_state", "auto_open_workspace", "self_check_server_state"]:
            if required not in names:
                summary["issues"].append(f"missing_tool:{required}")
    except Exception as exc:
        summary["issues"].append(f"http_discovery_error:{exc}")

    if not summary["session_state_exists"]:
        summary["issues"].append("session_state_missing")
    summary["healthy"] = not summary["issues"]
    return summary


def register_playbook_tools(toolset) -> None:
    project_root = "/a0/usr/projects/mcp_server"
    service_name = "mcp-server"
    local_base = "http://127.0.0.1:8000"

    async def start_work_session(args: Dict[str, Any]) -> Dict[str, Any]:
        SESSION_STATE_PATH.parent.mkdir(parents=True, exist_ok=True)
        try:
            state = json.loads(SESSION_STATE_PATH.read_text(encoding="utf-8")) if SESSION_STATE_PATH.exists() else {}
        except Exception:
            state = {}
        history = list(state.get("history") or [])
        history.append({
            "action": "start_work_session",
            "payload": {"workspace": project_root, "service": service_name, "repo": "mcp_server"},
            "at": __import__("datetime").datetime.utcnow().isoformat(),
        })
        state.update({
            "workspace": project_root,
            "service": service_name,
            "repo": "mcp_server",
            "last_opened_at": __import__("datetime").datetime.utcnow().isoformat(),
            "history": history[-40:],
        })
        SESSION_STATE_PATH.write_text(json.dumps(state, indent=2, ensure_ascii=False), encoding="utf-8")
        check = _session_check_summary(project_root, service_name, local_base)
        check_text = json.dumps(check, indent=2, ensure_ascii=False)
        text = (
            "WORKSPACE\n"
            f"project_root: {project_root}\n"
            f"service_name: {service_name}\n"
            f"repo_name: mcp_server\n"
            f"local_base: {local_base}\n"
            f"health: {local_base}/health\n"
            f"ready: {local_base}/ready\n"
            f"main_log: {project_root}/server.log\n"
            f"runtime_dir: {project_root}/.runtime\n"
            f"source_dir: {project_root}/src/mcp_server\n"
            f"session_state: {SESSION_STATE_PATH}\n\n"
            "SELF CHECK\n"
            f"{check_text}\n\n"
            "DEFAULT WORKFLOW\n"
            "1. Start with project_quick_facts and debug_service_workflow for fast reality checks.\n"
            "2. Sticky workspace/session context has been initialized automatically for this server.\n"
            "3. For service trouble use debug_service_workflow before changing anything.\n"
            "4. For heavy edits, long local work, or repeated file mutations delegate immediately with enqueue_agent_zero_task.\n"
            "5. While Agent Zero works, continue analysis and monitor progress with get_agent_zero_queue_status.\n"
            "6. For multi-step operational work prefer run_goal_workflow or run_intent_workflow before low-level commands.\n"
            "7. For narrow text/file edits prefer safe_edit_workflow first. For broader MCP edits prefer prepare_bulk_staging_workflow, make changes in the staging worktree, then apply them back once with apply_bulk_staging_workflow.\n"
            "8. Use the structured direct tools only when you need lower-level control: local_exec, read_file, write_file, patch_file, list_dir, path_ops, and service_control.\n"
            "9. Session/bootstrap/smart tools are available for lower-friction reuse of workspace context.\n"
            "10. Use low-level system_status only as a fallback path when higher-level tools do not fit.\n"
        )
        return {"content": [{"type": "text", "text": text}], "isError": False}

    async def get_task_playbook(args: Dict[str, Any]) -> Dict[str, Any]:
        task_type = (args.get("task_type") or "general").strip().lower()
        playbooks = {
            "debug": (
                "DEBUG PLAYBOOK\n"
                "1. project_quick_facts\n"
                "2. debug_service_workflow\n"
                "3. If the fix is multi-file or long-running, enqueue_agent_zero_task immediately\n"
                "4. For narrow targeted edits prefer safe_edit_workflow; for broader MCP edits prefer prepare_bulk_staging_workflow then apply_bulk_staging_workflow; otherwise use local_exec, read_file, patch_file, and service_control\n"
                "5. verify with debug_service_workflow"
            ),
            "edit": (
                "EDIT PLAYBOOK\n"
                "1. inspect target and scope the change\n"
                "2. if the edit is large, multi-file, or likely to take time, prepare_bulk_staging_workflow first or enqueue_agent_zero_task for autonomous execution\n"
                "3. use safe_edit_workflow first for narrow targeted changes\n"
                "4. for broader MCP edits, work in staging and apply back once with apply_bulk_staging_workflow\n"
                "5. use read_file, write_file, patch_file, and local_exec only when you need lower-level control\n"
                "6. reload/restart only if needed\n"
                "7. verify with debug_service_workflow"
            ),
            "deploy": (
                "DEPLOY PLAYBOOK\n"
                "1. prefer run_goal_workflow first\n"
                "2. if work is heavy, enqueue_agent_zero_task\n"
                "3. use enqueue_goal_task for background flows\n"
                "4. for targeted local actions use service_control and local_exec\n"
                "5. restart only when needed\n"
                "6. verify with debug_service_workflow"
            ),
            "ops": (
                "OPS PLAYBOOK\n"
                "1. inspect systemd/docker/process state\n"
                "2. use narrow service/process/log tools\n"
                "3. change state only with clear intent\n"
                "4. verify immediately after every mutation"
            ),
            "general": (
                "GENERAL PLAYBOOK\n"
                "1. start_work_session\n"
                "2. inspect before changing\n"
                "3. if work is heavy or long-running, enqueue_agent_zero_task\n"
                "4. while Agent Zero runs, monitor get_agent_zero_queue_status\n"
                "5. for narrow targeted edits prefer safe_edit_workflow; for broad MCP edits prefer prepare_bulk_staging_workflow and apply_bulk_staging_workflow; otherwise use the direct structured tools\n"
                "6. verify after every mutation\n"
                "7. keep the user loop small and factual"
            ),
        }
        text = playbooks.get(task_type, playbooks["general"])
        return {"content": [{"type": "text", "text": text}], "isError": False}

    async def project_quick_facts(args: Dict[str, Any]) -> Dict[str, Any]:
        text = (
            f"project_root={project_root}\n"
            f"service_name={service_name}\n"
            f"local_base={local_base}\n"
            f"health={local_base}/health\n"
            f"ready={local_base}/ready\n"
            f"log={project_root}/server.log\n"
            f"source_dir={project_root}/src/mcp_server\n"
            f"runtime_dir={project_root}/.runtime\n"
        )
        return {"content": [{"type": "text", "text": text}], "isError": False}

    extra = [
        ExtraToolDefinition(
            "start_work_session",
            "Return the recommended working context and default workflow for this server so the MCP client knows how to operate efficiently after approval.",
            {"type": "object", "properties": {}, "required": []},
            start_work_session,
            False,
            _ro("Start Work Session"),
        ),
        ExtraToolDefinition(
            "get_task_playbook",
            "Return a compact recommended workflow for a task type such as debug, edit, deploy, ops, or general.",
            {"type": "object", "properties": {"task_type": {"type": "string", "description": "debug, edit, deploy, ops, or general"}}, "required": []},
            get_task_playbook,
            False,
            _ro("Get Task Playbook"),
        ),
        ExtraToolDefinition(
            "project_quick_facts",
            "Return the key project paths, service name, and local endpoints for this server.",
            {"type": "object", "properties": {}, "required": []},
            project_quick_facts,
            False,
            _ro("Project Quick Facts"),
        ),
    ]

    for tool in extra:
        toolset._register_tool(tool)
