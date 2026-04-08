"""Agent Zero Handoff Tools - Task delegation to Agent Zero."""
import json
import logging
import uuid
import time
from pathlib import Path
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)

# Task queue directory
QUEUE_DIR = Path("/a0/usr/projects/mcp_server/.runtime/agent_zero_queue/queued")
COMPLETED_DIR = Path("/a0/usr/projects/mcp_server/.runtime/agent_zero_queue/completed")


def ensure_queue_dirs() -> None:
    """Ensure queue directories exist."""
    QUEUE_DIR.mkdir(parents=True, exist_ok=True)
    COMPLETED_DIR.mkdir(parents=True, exist_ok=True)


def enqueue_agent_zero_task(arguments: Dict[str, Any]) -> Dict[str, Any]:
    """Enqueue a task for Agent Zero to process.
    
    Args (from arguments dict):
        goal: Required - The goal/task description
        project: Optional - Project name
        project_root: Optional - Project root path
        service: Optional - Service name
        port: Optional - Service port
        path: Optional - Path context
        message: Optional - Additional message/instructions
        priority: Optional - Task priority (low, normal, high, urgent)
        max_attempts: Optional - Maximum retry attempts
    
    Returns:
        Task metadata with task_id and status
    """
    ensure_queue_dirs()
    
    # Extract required goal
    goal = arguments.get("goal")
    if not goal:
        return {
            "content": [{"type": "text", "text": "Error: 'goal' is required for Agent Zero task"}],
            "isError": True
        }
    
    # Generate task ID
    task_id = str(uuid.uuid4())[:8]
    timestamp = time.time()
    
    # Build task data
    task_data = {
        "task_id": task_id,
        "goal": goal,
        "project": arguments.get("project", "mcp_server"),
        "project_root": arguments.get("project_root", "/a0/usr/projects/mcp_server"),
        "service": arguments.get("service"),
        "port": arguments.get("port"),
        "path": arguments.get("path"),
        "message": arguments.get("message"),
        "priority": arguments.get("priority", "normal"),
        "max_attempts": arguments.get("max_attempts", 3),
        "created_at": timestamp,
        "status": "queued",
        "source": "mcp_handoff"
    }
    
    # Write task file
    task_file = QUEUE_DIR / f"{task_id}.json"
    try:
        task_file.write_text(json.dumps(task_data, indent=2))
        logger.info(f"Enqueued Agent Zero task: {task_id} - {goal[:50]}")
        
        return {
            "content": [{
                "type": "text",
                "text": json.dumps({
                    "success": True,
                    "task_id": task_id,
                    "status": "queued",
                    "goal": goal[:100],
                    "queue_path": str(task_file),
                    "message": f"Task {task_id} enqueued for Agent Zero processing"
                }, indent=2)
            }],
            "isError": False
        }
    except Exception as e:
        logger.error(f"Failed to enqueue task: {e}")
        return {
            "content": [{"type": "text", "text": f"Error writing task file: {e}"}],
            "isError": True
        }


def get_agent_zero_queue_status(arguments: Dict[str, Any]) -> Dict[str, Any]:
    """Get status of Agent Zero task queue.
    
    Returns:
        Queue status with counts and pending tasks
    """
    ensure_queue_dirs()
    
    queued_tasks = list(QUEUE_DIR.glob("*.json"))
    completed_tasks = list(COMPLETED_DIR.glob("*.json"))
    
    pending = []
    for task_file in queued_tasks[:10]:
        try:
            task_data = json.loads(task_file.read_text())
            pending.append({
                "task_id": task_data.get("task_id"),
                "goal": task_data.get("goal", "")[:50],
                "status": task_data.get("status"),
                "created_at": task_data.get("created_at")
            })
        except Exception:
            pass
    
    return {
        "content": [{
            "type": "text",
            "text": json.dumps({
                "queued_count": len(queued_tasks),
                "completed_count": len(completed_tasks),
                "pending_tasks": pending
            }, indent=2)
        }],
        "isError": False
    }


def register_agent_zero_handoff_tools(mcp_tools) -> None:
    """Register Agent Zero handoff tools with MCP tools registry."""
    # Add to extra_tools
    mcp_tools.extra_tools["enqueue_agent_zero_task"] = {
        "name": "enqueue_agent_zero_task",
        "description": "Enqueue a task for Agent Zero autonomous processing. Use for complex tasks requiring full AI agent capabilities.",
        "input_schema": {
            "type": "object",
            "properties": {
                "goal": {
                    "type": "string",
                    "description": "Required. The goal/task description for Agent Zero to accomplish"
                },
                "project": {
                    "type": "string",
                    "description": "Optional. Project name context"
                },
                "project_root": {
                    "type": "string",
                    "description": "Optional. Project root path"
                },
                "service": {
                    "type": "string",
                    "description": "Optional. Service name context"
                },
                "port": {
                    "type": "integer",
                    "description": "Optional. Service port"
                },
                "path": {
                    "type": "string",
                    "description": "Optional. Path context"
                },
                "message": {
                    "type": "string",
                    "description": "Optional. Additional instructions or context"
                },
                "priority": {
                    "type": "string",
                    "enum": ["low", "normal", "high", "urgent"],
                    "description": "Optional. Task priority"
                },
                "max_attempts": {
                    "type": "integer",
                    "description": "Optional. Maximum retry attempts"
                }
            },
            "required": ["goal"]
        },
        "handler": enqueue_agent_zero_task,
        "annotations": {"readOnlyHint": False}
    }
    
    mcp_tools.extra_tools["get_agent_zero_queue_status"] = {
        "name": "get_agent_zero_queue_status",
        "description": "Get status of Agent Zero task queue with pending and completed counts",
        "input_schema": {
            "type": "object",
            "properties": {}
        },
        "handler": get_agent_zero_queue_status,
        "annotations": {"readOnlyHint": True}
    }
    
    logger.info("Agent Zero handoff tools registered in extra_tools")
