"""Anti-loop and pivot suggestion tools."""
import json
from collections import Counter
from dataclasses import dataclass
from pathlib import Path
from statistics import mean
from typing import Any, Callable, Dict, Optional

STATE_PATH = Path("/a0/usr/projects/mcp_server/.runtime/agent_state.json")


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


def _load_actions():
    if not STATE_PATH.exists():
        return []
    try:
        data = json.loads(STATE_PATH.read_text())
        return list(data.get("actions") or [])
    except Exception:
        return []


def _suggest(action_name: str, target: str) -> str:
    joined = f"{action_name} {target}".lower()
    if "run_command" in joined or "shell" in joined or "execute_command_plan" in joined:
        return "Prefer a narrower tool or a workflow tool instead of repeating generic shell or command-plan execution."
    if "service" in joined or "systemd" in joined:
        return "Use debug_service_workflow, auto_diagnose_workspace, or service_health_bundle before repeating service mutations."
    if "git" in joined or "repo_sync" in joined:
        return "Use git_sync_repo or repo_sync_workflow instead of repeating raw git commands."
    if "write" in joined or "replace" in joined or "edit" in joined:
        return "Prefer read_file_with_hash plus replace_in_file_if_hash_matches, or use safe_edit_workflow with one verification pass."
    return "Change strategy instead of repeating the same call. Prefer a narrower tool or a workflow tool."


def register_anti_loop_tools(toolset) -> None:
    async def detect_repeated_failures(args: Dict[str, Any]) -> Dict[str, Any]:
        limit = int(args.get("limit", 60))
        threshold = int(args.get("threshold", 2))
        group_by = (args.get("group_by") or "fingerprint").strip().lower()
        actions = _load_actions()[-limit:]
        counter = Counter()
        latest = {}
        durations = {}
        same_args = {}
        for item in actions:
            status = str(item.get("status") or "").lower()
            if status in {"ok", "success", "passed"}:
                continue
            if group_by == "tool":
                key = (item.get("action_name"), item.get("target"), status)
            else:
                key = (item.get("call_fingerprint") or f"{item.get('action_name')}::{item.get('target')}::{status}", status)
            counter[key] += 1
            latest[key] = item
            durations.setdefault(key, [])
            if item.get("duration_ms") is not None:
                try:
                    durations[key].append(int(item.get("duration_ms")))
                except Exception:
                    pass
            same_args.setdefault(key, set())
            same_args[key].add(str(item.get("args_hash") or ""))
        rows = []
        for key, count in counter.items():
            if count >= threshold:
                item = latest[key]
                vals = durations.get(key, [])
                rows.append({
                    "action_name": item.get("action_name"),
                    "target": item.get("target"),
                    "status": item.get("status"),
                    "count": count,
                    "same_args_repeat": len(same_args.get(key, set()) - {""}) <= 1,
                    "args_hash": item.get("args_hash"),
                    "call_fingerprint": item.get("call_fingerprint"),
                    "last_duration_ms": vals[-1] if vals else item.get("duration_ms"),
                    "avg_duration_ms": int(mean(vals)) if vals else item.get("duration_ms"),
                    "suggestion": _suggest(str(item.get("action_name") or ""), str(item.get("target") or "")),
                    "last_details": item.get("details"),
                    "last_at": item.get("at"),
                })
        text = json.dumps(sorted(rows, key=lambda x: x["count"], reverse=True), indent=2, ensure_ascii=False)
        return {"content": [{"type": "text", "text": text}], "isError": False}

    async def suggest_pivot_strategy(args: Dict[str, Any]) -> Dict[str, Any]:
        action_name = args.get("action_name", "")
        target = args.get("target", "")
        text = _suggest(action_name, target)
        return {"content": [{"type": "text", "text": text}], "isError": False}

    extra = [
        ExtraToolDefinition("detect_repeated_failures", "Scan the state ledger for repeated failures and suggest pivot strategies. By default it groups by call fingerprint so exact same-args retries are detected precisely.", {"type": "object", "properties": {"limit": {"type": "integer", "default": 60}, "threshold": {"type": "integer", "default": 2}, "group_by": {"type": "string", "description": "fingerprint or tool", "default": "fingerprint"}}, "required": []}, detect_repeated_failures, False, _ro("Detect Repeated Failures")),
        ExtraToolDefinition("suggest_pivot_strategy", "Suggest a better next step when an action/target pair keeps failing or getting blocked.", {"type": "object", "properties": {"action_name": {"type": "string"}, "target": {"type": "string"}}, "required": ["action_name"]}, suggest_pivot_strategy, False, _ro("Suggest Pivot Strategy")),
    ]

    for tool in extra:
        toolset._register_tool(tool)

