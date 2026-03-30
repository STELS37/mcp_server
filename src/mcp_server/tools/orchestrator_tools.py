"""Task orchestrator tools for background workflow execution."""
import json
from dataclasses import dataclass
from typing import Any, Callable, Dict, Optional

from mcp_server.core.task_orchestrator import (
    create_task,
    find_task,
    list_tasks,
    cancel_task,
    retry_task,
    task_log_path,
    get_worker_status,
    set_queue_paused,
)


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


def register_orchestrator_tools(toolset) -> None:
    async def enqueue_goal_task(args: Dict[str, Any]) -> Dict[str, Any]:
        payload = {k: v for k, v in args.items() if k not in {"_user"} and v is not None}
        task = create_task("goal", payload, requested_by=args.get("_user", "unknown"))
        return {"content": [{"type": "text", "text": json.dumps(task, indent=2, ensure_ascii=False)}], "isError": False}

    async def enqueue_intent_task(args: Dict[str, Any]) -> Dict[str, Any]:
        payload = {k: v for k, v in args.items() if k not in {"_user"} and v is not None}
        task = create_task("intent", payload, requested_by=args.get("_user", "unknown"))
        return {"content": [{"type": "text", "text": json.dumps(task, indent=2, ensure_ascii=False)}], "isError": False}

    async def get_task_status(args: Dict[str, Any]) -> Dict[str, Any]:
        task = find_task(args.get("task_id"))
        if not task:
            return {"content": [{"type": "text", "text": "task not found"}], "isError": True}
        return {"content": [{"type": "text", "text": json.dumps(task, indent=2, ensure_ascii=False)}], "isError": False}

    async def list_recent_tasks(args: Dict[str, Any]) -> Dict[str, Any]:
        rows = list_tasks(limit=int(args.get("limit", 20)), status=args.get("status"))
        return {"content": [{"type": "text", "text": json.dumps(rows, indent=2, ensure_ascii=False)}], "isError": False}

    async def tail_task_log(args: Dict[str, Any]) -> Dict[str, Any]:
        path = task_log_path(args.get("task_id"))
        if not path.exists():
            return {"content": [{"type": "text", "text": "task log not found"}], "isError": True}
        lines = int(args.get("lines", 120))
        content = path.read_text().splitlines()[-lines:]
        return {"content": [{"type": "text", "text": "\n".join(content)}], "isError": False}

    async def cancel_background_task(args: Dict[str, Any]) -> Dict[str, Any]:
        result = cancel_task(args.get("task_id"))
        return {"content": [{"type": "text", "text": json.dumps(result, indent=2, ensure_ascii=False)}], "isError": not result.get("ok")}

    async def retry_background_task(args: Dict[str, Any]) -> Dict[str, Any]:
        result = retry_task(args.get("task_id"), requested_by=args.get("_user", "unknown"))
        return {"content": [{"type": "text", "text": json.dumps(result, indent=2, ensure_ascii=False)}], "isError": not result.get("ok")}

    async def get_orchestrator_status(args: Dict[str, Any]) -> Dict[str, Any]:
        payload = get_worker_status()
        return {"content": [{"type": "text", "text": json.dumps(payload, indent=2, ensure_ascii=False)}], "isError": False}

    async def pause_orchestrator(args: Dict[str, Any]) -> Dict[str, Any]:
        payload = set_queue_paused(True, reason=args.get("reason") or "paused by user")
        return {"content": [{"type": "text", "text": json.dumps(payload, indent=2, ensure_ascii=False)}], "isError": False}

    async def resume_orchestrator(args: Dict[str, Any]) -> Dict[str, Any]:
        payload = set_queue_paused(False)
        return {"content": [{"type": "text", "text": json.dumps(payload, indent=2, ensure_ascii=False)}], "isError": False}

    extra = [
        ExtraToolDefinition("enqueue_goal_task", "Queue a freeform goal for background execution by the task orchestrator. One confirmation queues the task; the server-side worker performs the long workflow asynchronously.", {"type": "object", "properties": {"goal": {"type": "string"}, "project": {"type": "string"}, "project_root": {"type": "string"}, "service": {"type": "string"}, "port": {"type": "integer"}, "path": {"type": "string"}, "search": {"type": "string"}, "replace": {"type": "string"}, "message": {"type": "string"}, "use_sudo": {"type": "boolean"}, "timeout": {"type": "integer"}, "pre_command": {"type": "string"}, "post_command": {"type": "string"}, "build_command": {"type": "string"}, "deploy_command": {"type": "string"}, "version": {"type": "string"}, "tag_name": {"type": "string"}, "incident_command": {"type": "string"}, "rollback": {"type": "boolean"}, "priority": {"type": "integer", "default": 0}, "max_attempts": {"type": "integer", "default": 2}}, "required": ["goal"]}, enqueue_goal_task, False, _rw("Enqueue Goal Task", False)),
        ExtraToolDefinition("enqueue_intent_task", "Queue a structured intent for background execution by the task orchestrator.", {"type": "object", "properties": {"intent": {"type": "string"}, "project": {"type": "string"}, "project_root": {"type": "string"}, "service": {"type": "string"}, "port": {"type": "integer"}, "path": {"type": "string"}, "search": {"type": "string"}, "replace": {"type": "string"}, "message": {"type": "string"}, "use_sudo": {"type": "boolean"}, "timeout": {"type": "integer"}, "pre_command": {"type": "string"}, "post_command": {"type": "string"}, "build_command": {"type": "string"}, "deploy_command": {"type": "string"}, "version": {"type": "string"}, "tag_name": {"type": "string"}, "incident_command": {"type": "string"}, "rollback": {"type": "boolean"}, "priority": {"type": "integer", "default": 0}, "max_attempts": {"type": "integer", "default": 2}}, "required": ["intent"]}, enqueue_intent_task, False, _rw("Enqueue Intent Task", False)),
        ExtraToolDefinition("get_task_status", "Return current status and stored result metadata for a background task.", {"type": "object", "properties": {"task_id": {"type": "string"}}, "required": ["task_id"]}, get_task_status, False, _ro("Get Task Status")),
        ExtraToolDefinition("list_recent_tasks", "List recent background tasks from the orchestrator queue and history store.", {"type": "object", "properties": {"limit": {"type": "integer", "default": 20}, "status": {"type": "string", "description": "queued, running, done, failed, or canceled"}}, "required": []}, list_recent_tasks, False, _ro("List Recent Tasks")),
        ExtraToolDefinition("tail_task_log", "Read the tail of a background task log file.", {"type": "object", "properties": {"task_id": {"type": "string"}, "lines": {"type": "integer", "default": 120}}, "required": ["task_id"]}, tail_task_log, False, _ro("Tail Task Log")),
        ExtraToolDefinition("cancel_background_task", "Cancel a queued or running background task if it has not already finished.", {"type": "object", "properties": {"task_id": {"type": "string"}}, "required": ["task_id"]}, cancel_background_task, False, _rw("Cancel Background Task", False)),
        ExtraToolDefinition("retry_background_task", "Requeue a finished failed/canceled/done background task for another run.", {"type": "object", "properties": {"task_id": {"type": "string"}}, "required": ["task_id"]}, retry_background_task, False, _rw("Retry Background Task", False)),
        ExtraToolDefinition("get_orchestrator_status", "Return worker state, queue counts, pause state, and recent recovery metadata for the background task orchestrator.", {"type": "object", "properties": {}, "required": []}, get_orchestrator_status, False, _ro("Get Orchestrator Status")),
        ExtraToolDefinition("pause_orchestrator", "Pause the background task orchestrator so queued tasks stay queued until resumed.", {"type": "object", "properties": {"reason": {"type": "string"}}, "required": []}, pause_orchestrator, False, _rw("Pause Orchestrator", False)),
        ExtraToolDefinition("resume_orchestrator", "Resume the background task orchestrator after a pause.", {"type": "object", "properties": {}, "required": []}, resume_orchestrator, False, _rw("Resume Orchestrator", False)),
    ]

    for tool in extra:
        toolset._register_tool(tool)
