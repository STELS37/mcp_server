"""File-backed task orchestrator for background workflow execution."""
import asyncio
import json
import traceback
import uuid
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from mcp_server.core.settings import get_settings
from mcp_server.tools.ssh_client import SSHClient

RUNTIME_ROOT = Path("/a0/usr/projects/mcp_server/.runtime")
QUEUE_ROOT = RUNTIME_ROOT / "task_queue"
QUEUED_DIR = QUEUE_ROOT / "queued"
RUNNING_DIR = QUEUE_ROOT / "running"
DONE_DIR = QUEUE_ROOT / "done"
FAILED_DIR = QUEUE_ROOT / "failed"
CANCELED_DIR = QUEUE_ROOT / "canceled"
LOG_DIR = QUEUE_ROOT / "logs"
QUEUE_STATE_PATH = QUEUE_ROOT / "queue_state.json"
WORKER_STATUS_PATH = QUEUE_ROOT / "worker_status.json"


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def ensure_queue_dirs() -> None:
    for path in (QUEUED_DIR, RUNNING_DIR, DONE_DIR, FAILED_DIR, CANCELED_DIR, LOG_DIR):
        path.mkdir(parents=True, exist_ok=True)


def load_json(path: Path, default: Dict[str, Any]) -> Dict[str, Any]:
    if not path.exists():
        return dict(default)
    try:
        data = json.loads(path.read_text())
        if isinstance(data, dict):
            return data
    except Exception:
        pass
    return dict(default)


def save_json(path: Path, data: Dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False))


def queue_state() -> Dict[str, Any]:
    return load_json(QUEUE_STATE_PATH, {"paused": False, "pause_reason": None, "updated_at": None})


def set_queue_paused(paused: bool, reason: Optional[str] = None) -> Dict[str, Any]:
    state = queue_state()
    state["paused"] = bool(paused)
    state["pause_reason"] = reason if paused else None
    state["updated_at"] = utc_now()
    save_json(QUEUE_STATE_PATH, state)
    return state


def update_worker_status(**kwargs: Any) -> Dict[str, Any]:
    state = load_json(WORKER_STATUS_PATH, {})
    state.update(kwargs)
    state["updated_at"] = utc_now()
    save_json(WORKER_STATUS_PATH, state)
    return state


def get_worker_status() -> Dict[str, Any]:
    ensure_queue_dirs()
    counts = {
        "queued": len(list(QUEUED_DIR.glob("*.json"))),
        "running": len(list(RUNNING_DIR.glob("*.json"))),
        "done": len(list(DONE_DIR.glob("*.json"))),
        "failed": len(list(FAILED_DIR.glob("*.json"))),
        "canceled": len(list(CANCELED_DIR.glob("*.json"))),
    }
    state = load_json(WORKER_STATUS_PATH, {})
    state["counts"] = counts
    state["queue_state"] = queue_state()
    return state


def status_dir(status: str) -> Path:
    mapping = {
        "queued": QUEUED_DIR,
        "running": RUNNING_DIR,
        "done": DONE_DIR,
        "failed": FAILED_DIR,
        "canceled": CANCELED_DIR,
    }
    return mapping[status]


def task_path(task_id: str, status: str) -> Path:
    return status_dir(status) / f"{task_id}.json"


def task_log_path(task_id: str) -> Path:
    return LOG_DIR / f"{task_id}.log"


def read_json(path: Path) -> Dict[str, Any]:
    return json.loads(path.read_text())


def summarize_result_text(result: Dict[str, Any]) -> str:
    parts: List[str] = []
    for item in result.get("content", []) or []:
        if isinstance(item, dict) and item.get("type") == "text" and item.get("text"):
            parts.append(str(item.get("text")))
    text = "\n".join(parts).strip()
    if not text:
        return "no textual result"
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    return " | ".join(lines[:6])[:1200]


def _route_tool_from_task(task: Dict[str, Any]) -> str:
    kind = str(task.get("kind") or "").lower()
    if kind == "intent":
        return "run_intent_workflow"
    if kind == "goal":
        return "run_goal_workflow"
    if kind == "workflow":
        return str(task.get("workflow_name") or "")
    return "run_goal_workflow"


def create_task(kind: str, payload: Dict[str, Any], requested_by: str = "unknown") -> Dict[str, Any]:
    ensure_queue_dirs()
    task_id = uuid.uuid4().hex[:16]
    task = {
        "task_id": task_id,
        "kind": kind,
        "status": "queued",
        "requested_by": requested_by,
        "created_at": utc_now(),
        "started_at": None,
        "finished_at": None,
        "payload": payload,
        "workflow_name": payload.get("workflow_name"),
        "result_summary": None,
        "error": None,
        "attempts": 0,
        "max_attempts": int(payload.get("max_attempts", 2)),
        "priority": int(payload.get("priority", 0)),
        "log_path": str(task_log_path(task_id)),
    }
    save_json(task_path(task_id, "queued"), task)
    task_log_path(task_id).write_text(f"[{utc_now()}] enqueued by {requested_by} priority={task['priority']} max_attempts={task['max_attempts']}\n")
    return task


def find_task(task_id: str) -> Optional[Dict[str, Any]]:
    ensure_queue_dirs()
    for status in ("queued", "running", "done", "failed", "canceled"):
        path = task_path(task_id, status)
        if path.exists():
            data = read_json(path)
            data["status"] = status
            return data
    return None


def list_tasks(limit: int = 20, status: Optional[str] = None) -> List[Dict[str, Any]]:
    ensure_queue_dirs()
    statuses = [status] if status in {"queued", "running", "done", "failed", "canceled"} else ["queued", "running", "done", "failed", "canceled"]
    rows: List[Dict[str, Any]] = []
    for st in statuses:
        for path in sorted(status_dir(st).glob("*.json"), key=lambda p: p.stat().st_mtime, reverse=True):
            try:
                data = read_json(path)
                data["status"] = st
                rows.append(data)
            except Exception:
                continue
    rows.sort(key=lambda x: str(x.get("created_at") or ""), reverse=True)
    return rows[:limit]


def cancel_task(task_id: str) -> Dict[str, Any]:
    ensure_queue_dirs()
    task = find_task(task_id)
    if not task:
        return {"ok": False, "message": "task not found"}
    if task.get("status") in {"done", "failed", "canceled"}:
        return {"ok": False, "message": f"task already {task.get('status')}"}
    src = task_path(task_id, str(task.get("status")))
    task["status"] = "canceled"
    task["finished_at"] = utc_now()
    save_json(task_path(task_id, "canceled"), task)
    if src.exists():
        src.unlink(missing_ok=True)
    with task_log_path(task_id).open("a") as fh:
        fh.write(f"[{utc_now()}] canceled\n")
    return {"ok": True, "message": "task canceled"}


def retry_task(task_id: str, requested_by: str = "unknown") -> Dict[str, Any]:
    task = find_task(task_id)
    if not task:
        return {"ok": False, "message": "task not found"}
    if task.get("status") not in {"failed", "canceled", "done"}:
        return {"ok": False, "message": f"task status {task.get('status')} cannot be retried yet"}
    src = task_path(task_id, str(task.get("status")))
    task["status"] = "queued"
    task["started_at"] = None
    task["finished_at"] = None
    task["error"] = None
    task["result_summary"] = None
    save_json(task_path(task_id, "queued"), task)
    src.unlink(missing_ok=True)
    with task_log_path(task_id).open("a") as fh:
        fh.write(f"[{utc_now()}] requeued by {requested_by}\n")
    return {"ok": True, "message": "task requeued", "task_id": task_id}


def requeue_stale_running_tasks(stale_after_minutes: int = 10) -> Dict[str, Any]:
    ensure_queue_dirs()
    requeued = []
    cutoff = datetime.now(timezone.utc) - timedelta(minutes=stale_after_minutes)
    for path in list(RUNNING_DIR.glob("*.json")):
        try:
            task = read_json(path)
        except Exception:
            path.unlink(missing_ok=True)
            continue
        started_at = str(task.get("started_at") or task.get("created_at") or "")
        try:
            dt = datetime.fromisoformat(started_at.replace("Z", "+00:00"))
        except Exception:
            dt = cutoff - timedelta(seconds=1)
        if dt <= cutoff:
            task["status"] = "queued"
            task["started_at"] = None
            save_json(task_path(str(task.get("task_id")), "queued"), task)
            path.unlink(missing_ok=True)
            with task_log_path(str(task.get("task_id"))).open("a") as fh:
                fh.write(f"[{utc_now()}] stale running task requeued after worker recovery\n")
            requeued.append(str(task.get("task_id")))
    return {"requeued": requeued, "count": len(requeued)}


def pick_next_task() -> Optional[Tuple[Path, Dict[str, Any]]]:
    queued_paths = list(QUEUED_DIR.glob("*.json"))
    if not queued_paths:
        return None
    candidates: List[Tuple[int, float, Path, Dict[str, Any]]] = []
    for path in queued_paths:
        try:
            task = read_json(path)
            priority = int(task.get("priority", 0))
            created_key = path.stat().st_mtime
            candidates.append((-priority, created_key, path, task))
        except Exception:
            path.unlink(missing_ok=True)
    if not candidates:
        return None
    candidates.sort(key=lambda x: (x[0], x[1]))
    _, _, path, task = candidates[0]
    return path, task


@dataclass
class WorkerRunResult:
    task_id: str
    final_status: str
    summary: str



STALL_CLASS_TIMEOUT = "timeout"
STALL_CLASS_PATTERN_NOT_FOUND = "pattern_not_found"
STALL_CLASS_SERVICE_NOT_READY = "service_not_ready"
STALL_CLASS_SSH_CONNECTIVITY = "ssh_connectivity"
STALL_CLASS_AGENT_ZERO_HANDOFF = "agent_zero_handoff"
STALL_CLASS_SERVER_RUNTIME = "server_runtime"
STALL_CLASS_UNKNOWN = "unknown"

def classify_error(summary: str) -> str:
    if not summary: return STALL_CLASS_UNKNOWN
    s = summary.lower()
    if any(k in s for k in ["timeout", "timed out", "took too long", "deadline"]): return STALL_CLASS_TIMEOUT
    if any(k in s for k in ["pattern not found", "no pattern matched", "regex failed"]): return STALL_CLASS_PATTERN_NOT_FOUND
    if any(k in s for k in ["service not ready", "connection refused", "not running", "unavailable"]): return STALL_CLASS_SERVICE_NOT_READY
    if any(k in s for k in ["ssh", "authentication failed", "host key"]): return STALL_CLASS_SSH_CONNECTIVITY
    if any(k in s for k in ["agent zero", "handoff", "queue"]): return STALL_CLASS_AGENT_ZERO_HANDOFF
    if any(k in s for k in ["exception", "runtime", "traceback", "error", "failed"]): return STALL_CLASS_SERVER_RUNTIME
    return STALL_CLASS_UNKNOWN

def get_recovery_workflow_for_class(err_class: str) -> str:
    return {
        STALL_CLASS_TIMEOUT: "debug_service_workflow",
        STALL_CLASS_SERVICE_NOT_READY: "full_service_recovery_workflow",
        STALL_CLASS_SSH_CONNECTIVITY: "collect_project_diagnostics",
        STALL_CLASS_AGENT_ZERO_HANDOFF: "get_agent_zero_queue_status",
    }.get(err_class, "prepare_bulk_staging_workflow")
class TaskOrchestratorWorker:
    def __init__(self, poll_interval: float = 2.0):
        self.poll_interval = poll_interval
        self.settings = get_settings()
        self.ssh = SSHClient(self.settings.ssh)
        self.tools = None

    async def initialize(self) -> None:
        ensure_queue_dirs()
        await self.ssh.connect()
        from mcp_server.tools.mcp_tools import MCPTools
        self.tools = MCPTools(self.ssh)
        recovery = requeue_stale_running_tasks()
        update_worker_status(state="idle", recovery=recovery)

    async def shutdown(self) -> None:
        update_worker_status(state="stopped")
        try:
            await self.ssh.disconnect()
        except Exception:
            pass

    async def run_forever(self) -> None:
        await self.initialize()
        try:
            while True:
                if queue_state().get("paused"):
                    update_worker_status(state="paused")
                    await asyncio.sleep(self.poll_interval)
                    continue
                processed = await self.process_one()
                if not processed:
                    update_worker_status(state="idle")
                    await asyncio.sleep(self.poll_interval)
        finally:
            await self.shutdown()

    async def process_one(self) -> bool:
        ensure_queue_dirs()
        selected = pick_next_task()
        if not selected:
            return False
        src, task = selected
        task_id = str(task.get("task_id"))
        running_path = task_path(task_id, "running")
        task["status"] = "running"
        task["started_at"] = utc_now()
        task["attempts"] = int(task.get("attempts") or 0) + 1
        save_json(running_path, task)
        src.unlink(missing_ok=True)
        with task_log_path(task_id).open("a") as fh:
            fh.write(f"[{utc_now()}] started attempt={task['attempts']} priority={task.get('priority', 0)}\n")
        update_worker_status(state="running", active_task_id=task_id, active_workflow=_route_tool_from_task(task))
        result = await self.execute_task(task)
        with task_log_path(task_id).open("a") as fh:
            fh.write(f"[{utc_now()}] finished status={result.final_status}\n")
            fh.write(result.summary + "\n")
        update_worker_status(state="idle", active_task_id=None, active_workflow=None, last_task_id=task_id, last_status=result.final_status)
        return True

    async def execute_task(self, task: Dict[str, Any]) -> WorkerRunResult:
        task_id = str(task.get("task_id"))
        workflow_tool = _route_tool_from_task(task)
        payload = dict(task.get("payload") or {})
        user = str(task.get("requested_by") or "orchestrator")
        try:
            result = await self.tools.execute_tool(workflow_tool, payload, user=f"orchestrator:{user}")
            summary = summarize_result_text(result)
            task["finished_at"] = utc_now()
            task["result_summary"] = summary
            task["result"] = result
            if result.get("isError"):
                return self._finalize_failure(task, summary)
            task["status"] = "done"
            save_json(task_path(task_id, "done"), task)
            task_path(task_id, "running").unlink(missing_ok=True)
            return WorkerRunResult(task_id=task_id, final_status="done", summary=summary)
        except Exception as exc:
            summary = f"exception: {exc}\n{traceback.format_exc()}"[:2000]
            task["finished_at"] = utc_now()
            task["result_summary"] = summary[:1200]
            task["error"] = str(exc)
            return self._finalize_failure(task, summary[:1200])

    def _finalize_failure(self, task: Dict[str, Any], summary: str) -> WorkerRunResult:
        task_id = str(task.get("task_id"))
        max_attempts = int(task.get("max_attempts", 2))
        attempts = int(task.get("attempts", 1))
        payload = dict(task.get("payload") or {})

        err_class = classify_error(summary)
        stall_analysis = {"class": err_class, "summary_snippet": summary[:500]}
        recovery_plan = {}

        if err_class == STALL_CLASS_TIMEOUT:
            for key in ("timeout_seconds", "timeout"):
                if key in payload:
                    try: payload[key] = int(payload[key]) * 2
                    except (ValueError, TypeError): pass
                    recovery_plan["action"] = "widen_timeout"
                    break
            task["payload"] = payload
        elif err_class == STALL_CLASS_SERVICE_NOT_READY:
            recovery_plan["action"] = "service_recovery_bias"
            payload["service_recovery"] = True
            for key in ("timeout", "timeout_seconds"):
                try:
                    current = int(payload.get(key, 30))
                    payload[key] = current + 30
                except (ValueError, TypeError):
                    payload[key] = 60
            task["payload"] = payload
        elif err_class in (STALL_CLASS_PATTERN_NOT_FOUND, STALL_CLASS_SERVER_RUNTIME):
            recovery_plan["action"] = "no_retry_classified"
            max_attempts = attempts
            task["max_attempts"] = max_attempts

        task["stall_analysis"] = stall_analysis
        task["recovery_plan"] = recovery_plan
        task["error"] = summary
        task["finished_at"] = utc_now()
        running = task_path(task_id, "running")

        if attempts < max_attempts:
            task["status"] = "queued"
            task["started_at"] = None
            save_json(task_path(task_id, "queued"), task)
            running.unlink(missing_ok=True)
            with task_log_path(task_id).open("a") as fh:
                fh.write(f"[{utc_now()}] auto-requeue attempts={attempts}/{max_attempts} class={err_class}\n")
            return WorkerRunResult(task_id=task_id, final_status="queued", summary=summary)

        task["status"] = "failed"
        save_json(task_path(task_id, "failed"), task)
        running.unlink(missing_ok=True)

        if not payload.get("is_auto_recovery"):
            recovery_workflow = get_recovery_workflow_for_class(err_class)
            rec_task = create_task(
                kind="workflow",
                payload={
                    "workflow_name": recovery_workflow,
                    "source_task_id": task_id,
                    "error_class": err_class,
                    "is_auto_recovery": True,
                    "max_attempts": 1
                },
                requested_by="system_recovery"
            )
            task["recovery_task_id"] = rec_task["task_id"]
            save_json(task_path(task_id, "failed"), task)
            with task_log_path(task_id).open("a") as fh:
                fh.write(f"[{utc_now()}] enqueued recovery task {rec_task['task_id']} ({recovery_workflow})\n")

        return WorkerRunResult(task_id=task_id, final_status="failed", summary=summary)


async def main() -> None:
    worker = TaskOrchestratorWorker()
    await worker.run_forever()


if __name__ == "__main__":
    asyncio.run(main())

