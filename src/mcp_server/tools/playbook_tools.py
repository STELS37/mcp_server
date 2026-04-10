"""Playbook tools that teach the MCP client how to operate this server efficiently."""
from dataclasses import dataclass
from typing import Any, Callable, Dict, Optional


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


def register_playbook_tools(toolset) -> None:
    project_root = "/a0/usr/projects/mcp_server"
    service_name = "mcp-server"
    local_base = "http://127.0.0.1:8000"

    async def start_work_session(args: Dict[str, Any]) -> Dict[str, Any]:
        text = (
            "WORKSPACE\n"
            f"project_root: {project_root}\n"
            f"service_name: {service_name}\n"
            f"local_base: {local_base}\n"
            f"health: {local_base}/health\n"
            f"ready: {local_base}/ready\n"
            f"main_log: {project_root}/server.log\n"
            f"runtime_dir: {project_root}/.runtime\n"
            f"source_dir: {project_root}/src/mcp_server\n\n"
            "DEFAULT WORKFLOW\n"
            "1. Start with project_quick_facts and debug_service_workflow for fast reality checks.\n"
            "2. For service trouble use debug_service_workflow before changing anything.\n"
            "3. For heavy edits, long local work, or repeated file mutations delegate immediately with enqueue_agent_zero_task.\n"
            "4. While Agent Zero works, continue analysis and monitor progress with get_agent_zero_queue_status.\n"
            "5. For multi-step operational work prefer run_goal_workflow or run_intent_workflow before low-level commands.\n"
            "6. For targeted local actions use the structured direct tools: local_exec, read_file, write_file, patch_file, list_dir, path_ops, and service_control.\n7. For background execution use enqueue_goal_task and monitor with get_orchestrator_status.\n"
            "8. Use low-level system_status only as a fallback path when higher-level tools do not fit.\n"
        )
        return {"content": [{"type": "text", "text": text}], "isError": False}

    async def get_task_playbook(args: Dict[str, Any]) -> Dict[str, Any]:
        task_type = (args.get("task_type") or "general").strip().lower()
        playbooks = {
            "debug": "DEBUG PLAYBOOK\n1. project_quick_facts\n2. debug_service_workflow\n3. If the fix is multi-file or long-running, enqueue_agent_zero_task immediately\n4. For targeted local actions use local_exec, read_file, patch_file, and service_control\n5. verify with debug_service_workflow",
            "edit": "EDIT PLAYBOOK\n1. inspect target and scope the change\n2. if the edit is large, multi-file, or likely to take time, enqueue_agent_zero_task immediately\n3. use safe_edit_workflow only for narrow targeted changes\n4. for direct local edits use read_file, write_file, patch_file, and local_exec\n5. reload/restart only if needed\n6. verify with debug_service_workflow",
            "deploy": "DEPLOY PLAYBOOK\n1. prefer run_goal_workflow first\n2. if work is heavy, enqueue_agent_zero_task\n3. use enqueue_goal_task for background flows\n4. for targeted local actions use service_control and local_exec\n5. restart only when needed\n6. verify with debug_service_workflow",
            "ops": "OPS PLAYBOOK\n1. inspect systemd/docker/process state\n2. use narrow service/process/log tools\n3. change state only with clear intent\n4. verify immediately after every mutation",
            "general": "GENERAL PLAYBOOK\n1. start_work_session\n2. inspect before changing\n3. if work is heavy or long-running, enqueue_agent_zero_task\n4. while Agent Zero runs, monitor get_agent_zero_queue_status\n5. for targeted local work use the direct structured tools\n6. verify after every mutation\n7. keep the user loop small and factual",
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
        ExtraToolDefinition("start_work_session", "Return the recommended working context and default workflow for this server so the MCP client knows how to operate efficiently after approval.", {"type": "object", "properties": {}, "required": []}, start_work_session, False, _ro("Start Work Session")),
        ExtraToolDefinition("get_task_playbook", "Return a compact recommended workflow for a task type such as debug, edit, deploy, ops, or general.", {"type": "object", "properties": {"task_type": {"type": "string", "description": "debug, edit, deploy, ops, or general"}}, "required": []}, get_task_playbook, False, _ro("Get Task Playbook")),
        ExtraToolDefinition("project_quick_facts", "Return the key project paths, service name, and local endpoints for this server.", {"type": "object", "properties": {}, "required": []}, project_quick_facts, False, _ro("Project Quick Facts")),
    ]

    for tool in extra:
        toolset._register_tool(tool)

