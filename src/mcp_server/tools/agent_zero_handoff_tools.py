"""Agent Zero handoff tools - direct delegation to a running Agent Zero service."""
import json
import logging
import os
import subprocess
import time
import uuid
from pathlib import Path
from typing import Any, Dict, Tuple
from datetime import datetime

logger = logging.getLogger(__name__)

QUEUE_ROOT = Path("/a0/usr/projects/mcp_server/.runtime/agent_zero_queue")
QUEUE_DIR = QUEUE_ROOT / "queued"
PROCESSING_DIR = QUEUE_ROOT / "processing"
COMPLETED_DIR = QUEUE_ROOT / "completed"
FAILED_DIR = QUEUE_ROOT / "failed"
RECONCILE_AUDIT_PATH = QUEUE_ROOT / "reconcile_audit.log"
LOOPBACK_SLOW_SECONDS = 10 * 60
LOOPBACK_STALE_SECONDS = 30 * 60
CONTEXT_STATUS_TIMEOUT = 8


def _append_reconcile_audit(event: Dict[str, Any]) -> None:
    RECONCILE_AUDIT_PATH.parent.mkdir(parents=True, exist_ok=True)
    with RECONCILE_AUDIT_PATH.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps({"at": datetime.utcnow().isoformat(), **event}, ensure_ascii=False) + "\n")


def _tool_result(payload: Dict[str, Any], is_error: bool = False) -> Dict[str, Any]:
    return {
        "content": [{"type": "text", "text": json.dumps(payload, indent=2, ensure_ascii=False)}],
        "isError": is_error,
    }


def ensure_queue_dirs() -> None:
    for directory in (QUEUE_DIR, PROCESSING_DIR, COMPLETED_DIR, FAILED_DIR):
        directory.mkdir(parents=True, exist_ok=True)


def _agent_zero_runtime() -> Tuple[str, str]:
    pid = subprocess.check_output(
        ["systemctl", "show", "-p", "MainPID", "--value", "agent-zero"],
        text=True,
    ).strip()
    if not pid or pid == "0":
        raise RuntimeError("agent-zero service is not running")

    python_exec = Path(f"/proc/{pid}/cmdline").read_bytes().split(b"\0")[0].decode()
    cwd = str(Path(f"/proc/{pid}/cwd").resolve())
    return python_exec, cwd


BRIDGE_CODE = """
import json
import os

from agent import AgentContext, AgentContextType, UserMessage
from initialize import initialize_agent

task = json.loads(os.environ[\"AZ_TASK_JSON\"])
ctxid = f\"mcp-{task['task_id']}\"
ctx = AgentContext.use(ctxid)
if not ctx:
    ctx = AgentContext(
        config=initialize_agent(),
        id=ctxid,
        name=f\"mcp:{task['task_id']}\",
        type=AgentContextType.BACKGROUND,
        set_current=True,
    )
else:
    ctx.type = AgentContextType.BACKGROUND
    AgentContext.set_current(ctx.id)

parts = [task.get(\"goal\", \"\").strip()]
for key in (\"project\", \"project_root\", \"service\", \"port\", \"path\", \"message\", \"priority\"):
    value = task.get(key)
    if value not in (None, \"\"):
        parts.append(f\"{key}: {value}\")

message = \"\\n\\n\".join([p for p in parts if p])
task_handle = ctx.communicate(UserMessage(message=message, id=f\"mcp-{task['task_id']}\"))
timeout = float(os.environ.get(\"AZ_RESULT_TIMEOUT\", \"2.5\"))
try:
    result = task_handle.result_sync(timeout=timeout)
    print(json.dumps({\"ok\": True, \"context\": ctx.id, \"type\": ctx.type.value, \"completed\": True, \"result_preview\": str(result)[:1200]}))
except Exception:
    print(json.dumps({\"ok\": True, \"context\": ctx.id, \"type\": ctx.type.value, \"completed\": False}))
""".strip()


STATUS_BRIDGE_CODE = """
import json
import os
from pathlib import Path

from agent import AgentContext
from helpers.persist_chat import get_chat_folder_path

ctxid = os.environ["AZ_CONTEXT_ID"]
ctx = AgentContext.use(ctxid)
chat_file = Path(get_chat_folder_path(ctxid)) / "chat.json"
result = {
    "context": ctxid,
    "exists_in_memory": bool(ctx),
    "chat_file": str(chat_file),
    "chat_exists": chat_file.exists(),
}
if ctx:
    result["created_at"] = ctx.created_at.isoformat() if getattr(ctx, "created_at", None) else None
    result["last_message"] = ctx.last_message.isoformat() if getattr(ctx, "last_message", None) else None
    result["paused"] = bool(getattr(ctx, "paused", False))
    result["log_items"] = len(getattr(getattr(ctx, "log", None), "logs", []) or [])
elif chat_file.exists():
    try:
        data = json.loads(chat_file.read_text())
        result["created_at"] = data.get("created_at")
        result["last_message"] = data.get("last_message")
        result["persisted"] = True
    except Exception as exc:
        result["persist_error"] = str(exc)
print(json.dumps(result))
""".strip()

def _inspect_agent_zero_context(context_id: str | None, timeout: int = CONTEXT_STATUS_TIMEOUT) -> Dict[str, Any]:
    if not context_id:
        return {"context": None, "observed_status": "missing_context"}
    try:
        python_exec, cwd = _agent_zero_runtime()
    except Exception as exc:
        return {"context": context_id, "observed_status": "runtime_unavailable", "error": str(exc)}
    env = os.environ.copy()
    env["AZ_CONTEXT_ID"] = context_id
    try:
        proc = subprocess.run(
            [python_exec, "-c", STATUS_BRIDGE_CODE],
            cwd=cwd,
            env=env,
            capture_output=True,
            text=True,
            timeout=timeout,
        )
    except subprocess.TimeoutExpired:
        return {"context": context_id, "observed_status": "status_timeout", "timeout_seconds": timeout}
    if proc.returncode != 0:
        return {"context": context_id, "observed_status": "bridge_error", "error": proc.stderr.strip() or proc.stdout.strip()}
    lines = [line.strip() for line in proc.stdout.splitlines() if line.strip()]
    if not lines:
        return {"context": context_id, "observed_status": "bridge_empty"}
    try:
        data = json.loads(lines[-1])
    except Exception as exc:
        return {"context": context_id, "observed_status": "bridge_parse_error", "error": str(exc), "raw": lines[-1]}
    if data.get("exists_in_memory"):
        data["observed_status"] = "running"
    elif data.get("chat_exists"):
        data["observed_status"] = "persisted"
    else:
        data["observed_status"] = "dispatched"
    return data

def _context_status_for_task(task_data: Dict[str, Any], now: float | None = None) -> Dict[str, Any]:
    now = now or time.time()
    context = task_data.get("agent_zero_context")
    if not context:
        return {"context": None, "observed_status": "missing_context"}
    transport = task_data.get("transport")
    if transport == "loopback_http":
        dispatched_at = float(task_data.get("dispatched_at") or task_data.get("created_at") or now)
        age = max(0.0, now - dispatched_at)
        status = {
            "context": context,
            "transport": transport,
            "observed_status": "accepted_by_live_agent_zero_api",
            "age_seconds": round(age, 3),
        }
        if age > LOOPBACK_STALE_SECONDS:
            status["stale"] = True
            status["observed_status"] = "stale_live_agent_zero_api_task"
        elif age > LOOPBACK_SLOW_SECONDS:
            status["slow"] = True
            status["observed_status"] = "slow_live_agent_zero_api_task"
        return status
    return _inspect_agent_zero_context(context)

def _dispatch_to_agent_zero(task_data: Dict[str, Any]) -> Dict[str, Any]:
    context_id = f"mcp-{task_data['task_id']}"
    payload = {
        "goal": task_data.get("goal", ""),
        "context": context_id,
        "message_id": context_id,
        "result_timeout": float(task_data.get("result_timeout", 2.5)),
    }

    try:
        import urllib.request

        req = urllib.request.Request(
            "http://127.0.0.1:5000/api/mcp_handoff",
            data=json.dumps(payload).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=max(5.0, float(task_data.get("result_timeout", 2.5)) + 5.0)) as resp:
            data = json.loads(resp.read().decode("utf-8"))
        if not data.get("ok"):
            raise RuntimeError(data.get("error") or "Agent Zero loopback handoff failed")
        return {
            "context": data.get("context") or context_id,
            "type": "background",
            "completed": data.get("status") == "completed",
            "result_preview": data.get("result_preview"),
            "transport": "loopback_http",
        }
    except Exception:
        python_exec, cwd = _agent_zero_runtime()
        env = os.environ.copy()
        env["AZ_TASK_JSON"] = json.dumps(task_data, ensure_ascii=False)
        env["AZ_RESULT_TIMEOUT"] = str(task_data.get("result_timeout", 2.5))

        proc = subprocess.run(
            [python_exec, "-c", BRIDGE_CODE],
            cwd=cwd,
            env=env,
            capture_output=True,
            text=True,
            timeout=120,
        )

        if proc.returncode != 0:
            raise RuntimeError(proc.stderr.strip() or proc.stdout.strip() or "Agent Zero bridge failed")

        lines = [line.strip() for line in proc.stdout.splitlines() if line.strip()]
        if not lines:
            raise RuntimeError("Agent Zero bridge returned no output")

        try:
            data = json.loads(lines[-1])
        except json.JSONDecodeError as exc:
            raise RuntimeError(f"Failed to parse Agent Zero bridge response: {lines[-1]}") from exc
        data["transport"] = "subprocess_bridge"
        return data


def enqueue_agent_zero_task(arguments: Dict[str, Any]) -> Dict[str, Any]:
    ensure_queue_dirs()

    goal = arguments.get("goal")
    if not goal:
        return _tool_result({"success": False, "error": "'goal' is required for Agent Zero task"}, True)

    task_id = str(uuid.uuid4())[:8]
    created_at = time.time()
    task_data = {
        "task_id": task_id,
        "goal": goal,
        "goal_execution_policy": "Use /a0/usr/workdir or staging/worktree paths for scratch work. Keep the mcp_server project tree clean and only sync back intentional final changes.",
        "project": arguments.get("project", "mcp_server"),
        "project_root": arguments.get("project_root", "/a0/usr/projects/mcp_server"),
        "service": arguments.get("service"),
        "port": arguments.get("port"),
        "path": arguments.get("path"),
        "message": arguments.get("message"),
        "priority": arguments.get("priority", "normal"),
        "max_attempts": arguments.get("max_attempts", 3),
        "result_timeout": arguments.get("result_timeout", 2.5),
        "created_at": created_at,
        "status": "queued",
        "source": "mcp_handoff",
    }

    queued_file = QUEUE_DIR / f"{task_id}.json"
    queued_file.write_text(json.dumps(task_data, indent=2, ensure_ascii=False))
    logger.info("Enqueued Agent Zero task %s: %s", task_id, goal[:120])

    try:
        bridge = _dispatch_to_agent_zero(task_data)
        task_data["agent_zero_context"] = bridge.get("context")
        task_data["agent_zero_context_type"] = bridge.get("type")
        task_data["transport"] = bridge.get("transport")
        queued_file.unlink(missing_ok=True)

        if bridge.get("completed"):
            task_data["status"] = "completed"
            task_data["completed_at"] = time.time()
            task_data["result_preview"] = bridge.get("result_preview")
            completed_file = COMPLETED_DIR / f"{task_id}.json"
            completed_file.write_text(json.dumps(task_data, indent=2, ensure_ascii=False))
            return _tool_result({
                "success": True,
                "task_id": task_id,
                "status": "completed",
                "goal": goal[:160],
                "message": "Task completed directly in Agent Zero",
                "completed_path": str(completed_file),
                "agent_zero_context": bridge.get("context"),
                "result_preview": bridge.get("result_preview"),
            })

        task_data["dispatched_at"] = time.time()
        if task_data.get("transport") == "loopback_http":
            task_data["status"] = "processing"
            task_data["context_status"] = {"observed_status": "accepted_by_live_agent_zero_api"}
            processing_file = PROCESSING_DIR / f"{task_id}.json"
            processing_file.write_text(json.dumps(task_data, indent=2, ensure_ascii=False))
            return _tool_result({
                "success": True,
                "task_id": task_id,
                "status": "processing",
                "goal": goal[:160],
                "message": "Task accepted by live Agent Zero API",
                "processing_path": str(processing_file),
                "agent_zero_context": bridge.get("context"),
                "agent_zero_context_type": bridge.get("type"),
                "transport": bridge.get("transport"),
                "context_status": task_data["context_status"],
            })

        context_status = _inspect_agent_zero_context(task_data.get("agent_zero_context"))
        task_data["context_status"] = context_status
        observed = context_status.get("observed_status")
        if observed in {"running", "persisted"}:
            task_data["status"] = "processing"
            processing_file = PROCESSING_DIR / f"{task_id}.json"
            processing_file.write_text(json.dumps(task_data, indent=2, ensure_ascii=False))
            return _tool_result({
                "success": True,
                "task_id": task_id,
                "status": "processing",
                "goal": goal[:160],
                "message": "Task dispatched directly to Agent Zero",
                "processing_path": str(processing_file),
                "agent_zero_context": bridge.get("context"),
                "agent_zero_context_type": bridge.get("type"),
                "transport": bridge.get("transport"),
                "context_status": context_status,
            })

        task_data["status"] = "failed"
        task_data["failed_at"] = time.time()
        task_data["failure_reason"] = "dispatch_unverified_no_live_context"
        failed_file = FAILED_DIR / f"{task_id}.json"
        failed_file.write_text(json.dumps(task_data, indent=2, ensure_ascii=False))
        return _tool_result({
            "success": False,
            "task_id": task_id,
            "status": "failed",
            "goal": goal[:160],
            "message": "Agent Zero dispatch could not be verified",
            "failed_path": str(failed_file),
            "agent_zero_context": bridge.get("context"),
            "agent_zero_context_type": bridge.get("type"),
            "context_status": context_status,
        }, True)
    except Exception as exc:
        logger.warning("Agent Zero direct dispatch failed for %s: %s", task_id, exc)
        return _tool_result({
            "success": True,
            "task_id": task_id,
            "status": "queued",
            "goal": goal[:160],
            "message": f"Task queued; direct dispatch failed: {exc}",
            "queue_path": str(queued_file),
        })


def reconcile_agent_zero_queue(arguments: Dict[str, Any]) -> Dict[str, Any]:
    ensure_queue_dirs()
    now = time.time()
    moved = []
    kept = []
    for task_file in sorted(PROCESSING_DIR.glob("*.json")):
        try:
            task_data = json.loads(task_file.read_text())
        except Exception as exc:
            moved.append({"task_id": task_file.stem, "action": "failed_unreadable", "error": str(exc)})
            broken = {"task_id": task_file.stem, "status": "failed", "failed_at": now, "failure_reason": f"unreadable_processing_file: {exc}"}
            (FAILED_DIR / task_file.name).write_text(json.dumps(broken, indent=2, ensure_ascii=False))
            task_file.unlink(missing_ok=True)
            continue
        status = _context_status_for_task(task_data, now=now)
        observed = status.get("observed_status")
        age = round(now - float(task_data.get("dispatched_at") or task_data.get("created_at") or now), 3)
        task_data["context_status"] = status
        if observed in {"stale_live_agent_zero_api_task", "dispatched", "bridge_error", "runtime_unavailable", "status_timeout", "bridge_empty", "bridge_parse_error"}:
            task_data["status"] = "failed"
            task_data["failed_at"] = now
            task_data["failure_reason"] = f"reconciled_{observed}"
            failed_path = FAILED_DIR / task_file.name
            failed_path.write_text(json.dumps(task_data, indent=2, ensure_ascii=False))
            _append_reconcile_audit({
                "task_id": task_data.get("task_id"),
                "action": "moved_to_failed",
                "observed_status": observed,
                "age_seconds": age,
                "failed_path": str(failed_path),
            })
            task_file.unlink(missing_ok=True)
            moved.append({"task_id": task_data.get("task_id"), "action": "moved_to_failed", "observed_status": observed, "age_seconds": age, "failed_path": str(failed_path)})
        else:
            kept.append({"task_id": task_data.get("task_id"), "observed_status": observed, "age_seconds": age})
    return _tool_result({
        "processing_remaining": len(kept),
        "moved_to_failed_count": len(moved),
        "moved_to_failed": moved[:20],
        "still_processing": kept[:20],
        "thresholds": {"slow_seconds": LOOPBACK_SLOW_SECONDS, "stale_seconds": LOOPBACK_STALE_SECONDS},
    })



def get_agent_zero_queue_status(arguments: Dict[str, Any]) -> Dict[str, Any]:
    ensure_queue_dirs()

    queued_tasks = sorted(QUEUE_DIR.glob("*.json"))
    processing_tasks = sorted(PROCESSING_DIR.glob("*.json"))
    completed_tasks = sorted(COMPLETED_DIR.glob("*.json"))
    failed_tasks = sorted(FAILED_DIR.glob("*.json"))

    def _read_tasks(paths):
        result = []
        now = time.time()
        for task_file in paths[:20]:
            try:
                task_data = json.loads(task_file.read_text())
                context = task_data.get("agent_zero_context")
                item = {
                    "task_id": task_data.get("task_id"),
                    "goal": (task_data.get("goal") or "")[:80],
                    "status": task_data.get("status"),
                    "created_at": task_data.get("created_at"),
                    "context": context,
                }
                if task_data.get("created_at"):
                    item["age_seconds"] = round(now - float(task_data.get("created_at")), 3)
                if task_data.get("dispatched_at"):
                    item["dispatched_age_seconds"] = round(now - float(task_data.get("dispatched_at")), 3)
                if context:
                    item["context_status"] = _context_status_for_task(task_data, now=now)
                    observed = item["context_status"].get("observed_status")
                    if observed in {"dispatched", "bridge_error", "runtime_unavailable", "status_timeout", "bridge_empty", "bridge_parse_error", "stale_live_agent_zero_api_task"} and item.get("dispatched_age_seconds", 0) > 300:
                        task_data["status"] = "failed"
                        task_data["failed_at"] = time.time()
                        task_data["failure_reason"] = f"stale_processing_{observed}"
                        (FAILED_DIR / task_file.name).write_text(json.dumps(task_data, indent=2, ensure_ascii=False))
                        task_file.unlink(missing_ok=True)
                        continue
                result.append(item)
            except Exception as exc:
                result.append({
                    "task_id": task_file.stem,
                    "goal": "<unreadable>",
                    "status": "unknown",
                    "created_at": None,
                    "context": None,
                    "error": str(exc),
                })
        return result

    queued_rows = _read_tasks(queued_tasks)
    processing_rows = _read_tasks(processing_tasks)
    completed_rows = _read_tasks(completed_tasks)
    failed_rows = _read_tasks(failed_tasks)

    return _tool_result({
        "queued_count": len(queued_rows),
        "processing_count": len(processing_rows),
        "completed_count": len(completed_rows),
        "failed_count": len(failed_rows),
        "queued_tasks": queued_rows,
        "processing_tasks": processing_rows,
        "completed_tasks": completed_rows[:10],
        "failed_tasks": failed_rows[:10],
    })


def register_agent_zero_handoff_tools(mcp_tools) -> None:
    mcp_tools.extra_tools["enqueue_agent_zero_task"] = {
        "name": "enqueue_agent_zero_task",
        "description": "Delegate a task directly to the running Agent Zero service; falls back to queueing if immediate dispatch fails.",
        "input_schema": {
            "type": "object",
            "properties": {
                "goal": {"type": "string", "description": "Required. Goal/task for Agent Zero."},
                "project": {"type": "string"},
                "project_root": {"type": "string"},
                "service": {"type": "string"},
                "port": {"type": "integer"},
                "path": {"type": "string"},
                "message": {"type": "string"},
                "priority": {"type": "string", "enum": ["low", "normal", "high", "urgent"]},
                "max_attempts": {"type": "integer"}
            },
            "required": ["goal"]
        },
        "handler": enqueue_agent_zero_task,
        "annotations": {"readOnlyHint": False}
    }

    mcp_tools.extra_tools["reconcile_agent_zero_queue"] = {
        "name": "reconcile_agent_zero_queue",
        "description": "Reconcile Agent Zero processing tasks, moving stale or broken entries to failed and summarizing what remains.",
        "input_schema": {"type": "object", "properties": {}},
        "handler": reconcile_agent_zero_queue,
        "annotations": {"readOnlyHint": False}
    }

    mcp_tools.extra_tools["reconcile_agent_zero_queue"] = {
        "name": "reconcile_agent_zero_queue",
        "description": "Reconcile Agent Zero processing tasks, moving stale or broken entries to failed and summarizing what remains.",
        "input_schema": {"type": "object", "properties": {}},
        "handler": reconcile_agent_zero_queue,
        "annotations": {"readOnlyHint": False}
    }

    mcp_tools.extra_tools["get_agent_zero_queue_status"] = {
        "name": "get_agent_zero_queue_status",
        "description": "Get queue and processing status for Agent Zero delegated work.",
        "input_schema": {"type": "object", "properties": {}},
        "handler": get_agent_zero_queue_status,
        "annotations": {"readOnlyHint": True}
    }

    logger.info("Agent Zero handoff tools registered in extra_tools")
