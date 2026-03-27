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
            "1. Start with health_check, ready_check, and mcp_self_test for fast reality checks.\n"
            "2. For service trouble use diagnose_service or service_health_bundle before changing anything.\n"
            "3. For code/config discovery use find_files, grep_file, read_file, stat_path, list_tree, and read_env_file.\n"
            "4. Before changing important files create a backup when practical, then prefer narrow tools over generic shell.\n"
            "5. After edits re-run health_check, ready_check, and any service-specific check.\n"
            "6. Use run_command only when no narrow tool fits the task.\n"
            "7. Keep changes minimal, verify immediately, and avoid unnecessary user questions.\n"
        )
        return {"content": [{"type": "text", "text": text}], "isError": False}

    async def get_task_playbook(args: Dict[str, Any]) -> Dict[str, Any]:
        task_type = (args.get("task_type") or "general").strip().lower()
        playbooks = {
            "debug": "DEBUG PLAYBOOK\n1. health_check\n2. ready_check\n3. diagnose_service(service, optional port)\n4. grep_file/tail_file on relevant logs\n5. only then edit or restart\n6. verify with mcp_self_test",
            "edit": "EDIT PLAYBOOK\n1. locate target with find_files/grep_file\n2. inspect with read_file/stat_path\n3. back up important file if needed\n4. edit with write_file or replace_in_file\n5. reload/restart only if needed\n6. verify health/readiness",
            "deploy": "DEPLOY PLAYBOOK\n1. inspect service_health_bundle\n2. inspect tree and env\n3. apply minimal file changes\n4. restart target service\n5. verify health, readiness, logs, and port",
            "ops": "OPS PLAYBOOK\n1. inspect systemd/docker/process state\n2. use narrow service/process/log tools\n3. change state only with clear intent\n4. verify immediately after every mutation",
            "general": "GENERAL PLAYBOOK\n1. start_work_session\n2. inspect before changing\n3. prefer narrow tools\n4. verify after every mutation\n5. keep the user loop small and factual",
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

