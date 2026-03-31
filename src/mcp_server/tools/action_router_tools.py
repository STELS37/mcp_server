"""Universal action router for MCP server - single entry point for all server actions.

This module provides a unified tool interface that routes to existing handlers
without requiring per-action confirmations in ChatGPT UI.
"""
import json
import hashlib
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

ACTION_ROUTER_STATE_PATH = Path("/a0/usr/projects/mcp_server/.runtime/action_router_state.json")
ACTION_CACHE_PATH = Path("/a0/usr/projects/mcp_server/.runtime/action_cache.json")

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

# ============================================================================
# ACTION SPECS - COMPLETE SERVER ADMINISTRATION
# ============================================================================

ACTION_SPECS = {
    # ==================== FILE SYSTEM - READ ====================
    "read_file": {
        "risk": "read_only", "cacheable": True, "cache_ttl": 5,
        "handler_method": "_router_read_file",
        "description": "Read file contents",
        "args": {"path": "required", "max_size": "optional(default:65536)"}
    },
    "list_dir": {
        "risk": "read_only", "cacheable": True, "cache_ttl": 5,
        "handler_method": "_router_list_dir",
        "description": "List directory contents",
        "args": {"path": "required", "recursive": "optional(default:false)"}
    },
    "exists_path": {
        "risk": "read_only", "cacheable": True, "cache_ttl": 10,
        "handler_method": "_router_exists_path",
        "description": "Check if path exists",
        "args": {"path": "required"}
    },
    "stat_path": {
        "risk": "read_only", "cacheable": True, "cache_ttl": 10,
        "handler_method": "_router_stat_path",
        "description": "Get file/dir metadata (size, mode, mtime)",
        "args": {"path": "required"}
    },
    "tail_file": {
        "risk": "read_only", "cacheable": False,
        "handler_method": "_router_tail_file",
        "description": "Tail last N lines of file",
        "args": {"path": "required", "lines": "optional(default:100)"}
    },
    "grep_files": {
        "risk": "read_only", "cacheable": False,
        "handler_method": "_router_grep_files",
        "description": "Grep pattern in files",
        "args": {"path": "required", "pattern": "required", "recursive": "optional(default:false)"}
    },
    "find_files": {
        "risk": "read_only", "cacheable": True, "cache_ttl": 30,
        "handler_method": "_router_find_files",
        "description": "Find files by name pattern",
        "args": {"path": "required", "pattern": "required", "type": "optional(f/d)"}
    },
    "disk_usage": {
        "risk": "read_only", "cacheable": True, "cache_ttl": 30,
        "handler_method": "_router_disk_usage",
        "description": "Get disk usage for path",
        "args": {"path": "optional(default:/)"}
    },
    "df_report": {
        "risk": "read_only", "cacheable": True, "cache_ttl": 30,
        "handler_method": "_router_df_report",
        "description": "Full disk space report",
        "args": {}
    },
    
    # ==================== SYSTEM INFO ====================
    "get_server_facts": {
        "risk": "read_only", "cacheable": True, "cache_ttl": 30,
        "handler_method": "_router_get_server_facts",
        "description": "Get server facts (hostname, uptime, CPU, RAM)",
        "args": {}
    },
    "uptime_info": {
        "risk": "read_only", "cacheable": True, "cache_ttl": 30,
        "handler_method": "_router_uptime_info",
        "description": "Get system uptime and load",
        "args": {}
    },
    "free_memory": {
        "risk": "read_only", "cacheable": True, "cache_ttl": 10,
        "handler_method": "_router_free_memory",
        "description": "Get memory usage info",
        "args": {}
    },
    "hostname_info": {
        "risk": "read_only", "cacheable": True, "cache_ttl": 60,
        "handler_method": "_router_hostname_info",
        "description": "Get hostname and domain info",
        "args": {}
    },
    "env_vars": {
        "risk": "read_only", "cacheable": False,
        "handler_method": "_router_env_vars",
        "description": "Get environment variables (filtered)",
        "args": {"filter": "optional"}
    },
    "sysctl_get": {
        "risk": "read_only", "cacheable": True, "cache_ttl": 60,
        "handler_method": "_router_sysctl_get",
        "description": "Get sysctl kernel parameter",
        "args": {"param": "optional"}
    },
    
    # ==================== SERVICES - READ ====================
    "systemd_status": {
        "risk": "read_only", "cacheable": True, "cache_ttl": 5,
        "handler_method": "_router_systemd_status",
        "description": "Get systemd service status",
        "args": {"service": "required"}
    },
    "systemd_list_units": {
        "risk": "read_only", "cacheable": True, "cache_ttl": 30,
        "handler_method": "_router_systemd_list_units",
        "description": "List all systemd units",
        "args": {"type": "optional(service/mount/socket)"}
    },
    "systemd_list_failed": {
        "risk": "read_only", "cacheable": True, "cache_ttl": 10,
        "handler_method": "_router_systemd_list_failed",
        "description": "List failed systemd services",
        "args": {}
    },
    "journal_tail": {
        "risk": "read_only", "cacheable": False,
        "handler_method": "_router_journal_tail",
        "description": "Read systemd journal logs",
        "args": {"service": "optional", "lines": "optional(default:100)"}
    },
    
    # ==================== DOCKER - READ ====================
    "docker_ps": {
        "risk": "read_only", "cacheable": True, "cache_ttl": 5,
        "handler_method": "_router_docker_ps",
        "description": "List docker containers",
        "args": {"all": "optional(default:false)"}
    },
    "docker_images": {
        "risk": "read_only", "cacheable": True, "cache_ttl": 30,
        "handler_method": "_router_docker_images",
        "description": "List docker images",
        "args": {}
    },
    "docker_inspect": {
        "risk": "read_only", "cacheable": True, "cache_ttl": 10,
        "handler_method": "_router_docker_inspect",
        "description": "Inspect docker container/image details",
        "args": {"container": "required"}
    },
    "docker_logs": {
        "risk": "read_only", "cacheable": False,
        "handler_method": "_router_docker_logs",
        "description": "Get docker container logs",
        "args": {"container": "required", "tail": "optional(default:100)"}
    },
    "docker_networks": {
        "risk": "read_only", "cacheable": True, "cache_ttl": 30,
        "handler_method": "_router_docker_networks",
        "description": "List docker networks",
        "args": {}
    },
    "docker_volumes": {
        "risk": "read_only", "cacheable": True, "cache_ttl": 30,
        "handler_method": "_router_docker_volumes",
        "description": "List docker volumes",
        "args": {}
    },
    
    # ==================== PROCESS & NETWORK ====================
    "process_list": {
        "risk": "read_only", "cacheable": True, "cache_ttl": 5,
        "handler_method": "_router_process_list",
        "description": "List running processes",
        "args": {"user": "optional", "name": "optional"}
    },
    "process_info": {
        "risk": "read_only", "cacheable": True, "cache_ttl": 10,
        "handler_method": "_router_process_info",
        "description": "Get process details by PID",
        "args": {"pid": "required"}
    },
    "port_listeners": {
        "risk": "read_only", "cacheable": True, "cache_ttl": 10,
        "handler_method": "_router_port_listeners",
        "description": "List listening ports",
        "args": {"port": "optional"}
    },
    "netstat_summary": {
        "risk": "read_only", "cacheable": True, "cache_ttl": 10,
        "handler_method": "_router_netstat_summary",
        "description": "Network connections summary",
        "args": {}
    },
    "iptables_list": {
        "risk": "read_only", "cacheable": True, "cache_ttl": 30,
        "handler_method": "_router_iptables_list",
        "description": "List iptables rules",
        "args": {}
    },
    "ufw_status": {
        "risk": "read_only", "cacheable": True, "cache_ttl": 30,
        "handler_method": "_router_ufw_status",
        "description": "Get UFW firewall status",
        "args": {}
    },
    "get_public_ip": {
        "risk": "read_only", "cacheable": True, "cache_ttl": 60,
        "handler_method": "_router_get_public_ip",
        "description": "Get server public IP",
        "args": {}
    },
    "ping_host": {
        "risk": "read_only", "cacheable": False,
        "handler_method": "_router_ping_host",
        "description": "Ping remote host",
        "args": {"host": "required", "count": "optional(default:3)"}
    },
    
    # ==================== USERS & SECURITY ====================
    "user_list": {
        "risk": "read_only", "cacheable": True, "cache_ttl": 60,
        "handler_method": "_router_user_list",
        "description": "List system users",
        "args": {}
    },
    "user_info": {
        "risk": "read_only", "cacheable": True, "cache_ttl": 60,
        "handler_method": "_router_user_info",
        "description": "Get user details",
        "args": {"user": "required"}
    },
    "group_list": {
        "risk": "read_only", "cacheable": True, "cache_ttl": 60,
        "handler_method": "_router_group_list",
        "description": "List system groups",
        "args": {}
    },
    "last_logins": {
        "risk": "read_only", "cacheable": True, "cache_ttl": 60,
        "handler_method": "_router_last_logins",
        "description": "Show recent logins",
        "args": {"lines": "optional(default:20)"}
    },
    "sudo_audit": {
        "risk": "read_only", "cacheable": True, "cache_ttl": 60,
        "handler_method": "_router_sudo_audit",
        "description": "Check sudoers configuration",
        "args": {}
    },
    
    # ==================== CRON & SCHEDULES ====================
    "cron_list": {
        "risk": "read_only", "cacheable": True, "cache_ttl": 60,
        "handler_method": "_router_cron_list",
        "description": "List cron jobs for user",
        "args": {"user": "optional(default:current)"}
    },
    "cron_list_all": {
        "risk": "read_only", "cacheable": True, "cache_ttl": 60,
        "handler_method": "_router_cron_list_all",
        "description": "List all users cron jobs",
        "args": {}
    },
    
    # ==================== PACKAGES ====================
    "apt_list_installed": {
        "risk": "read_only", "cacheable": True, "cache_ttl": 60,
        "handler_method": "_router_apt_list_installed",
        "description": "List installed packages",
        "args": {"filter": "optional"}
    },
    "apt_show_package": {
        "risk": "read_only", "cacheable": True, "cache_ttl": 60,
        "handler_method": "_router_apt_show_package",
        "description": "Show package info",
        "args": {"package": "required"}
    },
    "apt_check_updates": {
        "risk": "read_only", "cacheable": False,
        "handler_method": "_router_apt_check_updates",
        "description": "Check available updates",
        "args": {}
    },
    
    # ==================== MCP HEALTH ====================
    "health_check": {
        "risk": "read_only", "cacheable": True, "cache_ttl": 5,
        "handler_method": "_router_health_check",
        "description": "MCP server health check",
        "args": {}
    },
    "ready_check": {
        "risk": "read_only", "cacheable": True, "cache_ttl": 5,
        "handler_method": "_router_ready_check",
        "description": "MCP server readiness check",
        "args": {}
    },
    "http_get_local": {
        "risk": "read_only", "cacheable": False,
        "handler_method": "_router_http_get_local",
        "description": "HTTP GET on localhost",
        "args": {"path": "required", "port": "optional(default:8000)"}
    },
    
    # ==================== FILE SYSTEM - WRITE ====================
    "mkdir_p": {
        "risk": "controlled_mutation", "cacheable": False,
        "handler_method": "_router_mkdir_p",
        "description": "Create directory tree",
        "args": {"path": "required", "mode": "optional(default:755)"}
    },
    "touch_file": {
        "risk": "controlled_mutation", "cacheable": False,
        "handler_method": "_router_touch_file",
        "description": "Create empty file or update timestamp",
        "args": {"path": "required"}
    },
    "copy_file": {
        "risk": "controlled_mutation", "cacheable": False,
        "handler_method": "_router_copy_file",
        "description": "Copy file/directory",
        "args": {"src": "required", "dst": "required"}
    },
    "move_file": {
        "risk": "controlled_mutation", "cacheable": False,
        "handler_method": "_router_move_file",
        "description": "Move/rename file/directory",
        "args": {"src": "required", "dst": "required"}
    },
    "delete_file": {
        "risk": "controlled_mutation", "cacheable": False,
        "handler_method": "_router_delete_file",
        "description": "Delete file (single file only)",
        "args": {"path": "required", "force": "optional(default:false)"}
    },
    "chmod_path": {
        "risk": "controlled_mutation", "cacheable": False,
        "handler_method": "_router_chmod_path",
        "description": "Change file permissions",
        "args": {"path": "required", "mode": "required(e.g. 644)"}
    },
    "chown_path": {
        "risk": "controlled_mutation", "cacheable": False,
        "handler_method": "_router_chown_path",
        "description": "Change file owner",
        "args": {"path": "required", "owner": "required", "group": "optional"}
    },
    "backup_file": {
        "risk": "controlled_mutation", "cacheable": False,
        "handler_method": "_router_backup_file",
        "description": "Create backup of file",
        "args": {"path": "required", "suffix": "optional(default:.bak)"}
    },
    "restore_backup": {
        "risk": "controlled_mutation", "cacheable": False,
        "handler_method": "_router_restore_backup",
        "description": "Restore file from backup",
        "args": {"path": "required", "suffix": "optional(default:.bak)"}
    },
    "write_file_safe": {
        "risk": "controlled_mutation", "cacheable": False,
        "handler_method": "_router_write_file_safe",
        "description": "Write file with backup",
        "args": {"path": "required", "content": "required"}
    },
    "append_file": {
        "risk": "controlled_mutation", "cacheable": False,
        "handler_method": "_router_append_file",
        "description": "Append content to file",
        "args": {"path": "required", "content": "required"}
    },
    
    # ==================== SERVICES - CONTROL ====================
    "service_start": {
        "risk": "controlled_mutation", "cacheable": False,
        "handler_method": "_router_service_start",
        "description": "Start systemd service",
        "args": {"service": "required"}
    },
    "service_stop": {
        "risk": "controlled_mutation", "cacheable": False,
        "handler_method": "_router_service_stop",
        "description": "Stop systemd service",
        "args": {"service": "required"}
    },
    "service_restart": {
        "risk": "controlled_mutation", "cacheable": False,
        "handler_method": "_router_service_restart",
        "description": "Restart systemd service",
        "args": {"service": "required", "timeout": "optional(default:30)"}
    },
    "service_reload": {
        "risk": "controlled_mutation", "cacheable": False,
        "handler_method": "_router_service_reload",
        "description": "Reload systemd service config",
        "args": {"service": "required"}
    },
    "service_enable": {
        "risk": "controlled_mutation", "cacheable": False,
        "handler_method": "_router_service_enable",
        "description": "Enable systemd service (autostart)",
        "args": {"service": "required"}
    },
    "service_disable": {
        "risk": "controlled_mutation", "cacheable": False,
        "handler_method": "_router_service_disable",
        "description": "Disable systemd service",
        "args": {"service": "required"}
    },
    "daemon_reload": {
        "risk": "controlled_mutation", "cacheable": False,
        "handler_method": "_router_daemon_reload",
        "description": "Reload systemd daemon config",
        "args": {}
    },
    
    # ==================== DOCKER - CONTROL ====================
    "docker_start": {
        "risk": "controlled_mutation", "cacheable": False,
        "handler_method": "_router_docker_start",
        "description": "Start docker container",
        "args": {"container": "required"}
    },
    "docker_stop": {
        "risk": "controlled_mutation", "cacheable": False,
        "handler_method": "_router_docker_stop",
        "description": "Stop docker container",
        "args": {"container": "required", "timeout": "optional(default:10)"}
    },
    "docker_restart": {
        "risk": "controlled_mutation", "cacheable": False,
        "handler_method": "_router_docker_restart",
        "description": "Restart docker container",
        "args": {"container": "required", "timeout": "optional(default:10)"}
    },
    "docker_pull": {
        "risk": "controlled_mutation", "cacheable": False,
        "handler_method": "_router_docker_pull",
        "description": "Pull docker image",
        "args": {"image": "required"}
    },
    "docker_prune": {
        "risk": "controlled_mutation", "cacheable": False,
        "handler_method": "_router_docker_prune",
        "description": "Prune unused docker resources",
        "args": {"type": "optional(images/containers/volumes/all)"}
    },
    "docker_rm": {
        "risk": "controlled_mutation", "cacheable": False,
        "handler_method": "_router_docker_rm",
        "description": "Remove docker container",
        "args": {"container": "required", "force": "optional(default:false)"}
    },
    "docker_rmi": {
        "risk": "controlled_mutation", "cacheable": False,
        "handler_method": "_router_docker_rmi",
        "description": "Remove docker image",
        "args": {"image": "required", "force": "optional(default:false)"}
    },
    
    # ==================== PACKAGES - CONTROL ====================
    "apt_install": {
        "risk": "controlled_mutation", "cacheable": False,
        "handler_method": "_router_apt_install",
        "description": "Install package(s)",
        "args": {"packages": "required(list)"}
    },
    "apt_remove": {
        "risk": "controlled_mutation", "cacheable": False,
        "handler_method": "_router_apt_remove",
        "description": "Remove package(s)",
        "args": {"packages": "required(list)"}
    },
    "apt_update": {
        "risk": "controlled_mutation", "cacheable": False,
        "handler_method": "_router_apt_update",
        "description": "Update package lists",
        "args": {}
    },
    "apt_upgrade": {
        "risk": "controlled_mutation", "cacheable": False,
        "handler_method": "_router_apt_upgrade",
        "description": "Upgrade packages",
        "args": {"dist": "optional(default:false)"}
    },
    
    # ==================== FIREWALL - CONTROL ====================
    "ufw_allow_port": {
        "risk": "controlled_mutation", "cacheable": False,
        "handler_method": "_router_ufw_allow_port",
        "description": "Allow port in UFW",
        "args": {"port": "required", "proto": "optional(tcp/udp)"}
    },
    "ufw_deny_port": {
        "risk": "controlled_mutation", "cacheable": False,
        "handler_method": "_router_ufw_deny_port",
        "description": "Deny port in UFW",
        "args": {"port": "required", "proto": "optional(tcp/udp)"}
    },
    "ufw_enable": {
        "risk": "controlled_mutation", "cacheable": False,
        "handler_method": "_router_ufw_enable",
        "description": "Enable UFW firewall",
        "args": {}
    },
    "ufw_disable": {
        "risk": "controlled_mutation", "cacheable": False,
        "handler_method": "_router_ufw_disable",
        "description": "Disable UFW firewall",
        "args": {}
    },
    "ufw_reset": {
        "risk": "controlled_mutation", "cacheable": False,
        "handler_method": "_router_ufw_reset",
        "description": "Reset UFW rules",
        "args": {}
    },
    
    # ==================== CRON - CONTROL ====================
    "cron_add": {
        "risk": "controlled_mutation", "cacheable": False,
        "handler_method": "_router_cron_add",
        "description": "Add cron job",
        "args": {"user": "optional", "schedule": "required", "command": "required"}
    },
    "cron_remove": {
        "risk": "controlled_mutation", "cacheable": False,
        "handler_method": "_router_cron_remove",
        "description": "Remove cron job by line number",
        "args": {"user": "optional", "line": "required"}
    },
    
    # ==================== SHELL COMMANDS ====================
    "bash_command": {
        "risk": "shell", "cacheable": False,
        "handler_method": "_router_bash_command",
        "description": "Execute shell command",
        "args": {"command": "required", "timeout": "optional(default:30)"}
    },
    "docker_exec": {
        "risk": "shell", "cacheable": False,
        "handler_method": "_router_docker_exec",
        "description": "Execute command in container",
        "args": {"container": "required", "command": "required"}
    },
    "script_run": {
        "risk": "shell", "cacheable": False,
        "handler_method": "_router_script_run",
        "description": "Run shell script",
        "args": {"path": "required", "args": "optional"}
    },
}

def _normalize_payload(payload_str: str) -> Dict[str, Any]:
    if not payload_str:
        return {}
    try:
        data = json.loads(payload_str.strip())
        if not isinstance(data, dict):
            raise ValueError("Payload must be a JSON object")
        return data
    except json.JSONDecodeError as e:
        raise ValueError(f"Invalid JSON payload: {e}")

def _payload_fingerprint(action_type: str, payload: Dict[str, Any]) -> str:
    canonical = json.dumps({"action": action_type, "payload": payload}, sort_keys=True)
    return hashlib.sha256(canonical.encode()).hexdigest()[:16]

def _get_cached_result(fingerprint: str, ttl: int) -> Optional[Dict[str, Any]]:
    cache = _load_json(ACTION_CACHE_PATH, {})
    entry = cache.get(fingerprint)
    if not entry:
        return None
    cached_at = entry.get("cached_at", 0)
    if time.time() - cached_at > ttl:
        return None
    return entry.get("result")

def _set_cached_result(fingerprint: str, result: Dict[str, Any]) -> None:
    cache = _load_json(ACTION_CACHE_PATH, {})
    cache[fingerprint] = {"result": result, "cached_at": time.time()}
    if len(cache) > 200:
        keys = sorted(cache.keys())[:-100]
        for k in keys:
            cache.pop(k, None)
    _save_json(ACTION_CACHE_PATH, cache)

def _record_action(action_type: str, payload: Dict[str, Any], result: Dict[str, Any], user: str) -> None:
    state = _load_json(ACTION_ROUTER_STATE_PATH, {"history": []})
    entry = {
        "timestamp": _utc_now(),
        "action_type": action_type,
        "fingerprint": _payload_fingerprint(action_type, payload),
        "risk": ACTION_SPECS.get(action_type, {}).get("risk", "unknown"),
        "user": user,
        "is_error": bool(result.get("isError"))
    }
    history = list(state.get("history", []))
    history.append(entry)
    state["history"] = history[-200:]
    state["last_action"] = entry
    _save_json(ACTION_ROUTER_STATE_PATH, state)

def register_action_router_tools(toolset) -> None:
    """Register split tools: server_query (read-only) and server_manage (mutation)."""
    
    # Define read-only actions (safe for autonomous execution)
    READ_ONLY_ACTIONS = [
        "read_file", "list_dir", "stat_path", "exists_path", "tail_file", "grep_file",
        "find_files", "disk_usage", "df_report", "tree", "du_path",
        "hostname", "uptime", "kernel_info", "cpu_info", "memory_info", "disk_info",
        "env_vars", "timezone", "get_public_ip", "ping_host",
        "systemd_status", "systemd_list_units", "systemd_list_failed", "journal_tail",
        "docker_ps", "docker_images", "docker_containers", "docker_networks", "docker_volumes", "docker_logs",
        "process_list", "process_info", "port_listeners", "netstat_summary",
        "iptables_list", "ufw_status",
        "user_list", "group_list", "whoami", "last_logins",
        "apt_list", "dpkg_info",
        "service_status", "http_get_local",
        "get_server_facts", "get_action_history"
    ]
    
    # Define mutation/admin actions (require confirmation)
    MUTATION_ACTIONS = [
        "mkdir", "rm", "mv", "cp", "touch", "chmod", "chown", "symlink",
        "archive_create", "archive_extract",
        "service_start", "service_stop", "service_restart", "service_reload",
        "docker_restart", "docker_exec",
        "apt_install", "apt_remove",
        "bash_command", "crontab_edit",
        "ufw_enable", "ufw_disable", "ufw_allow", "ufw_deny",
        "write_file", "replace_in_file",
        "reboot_server"
    ]

    async def list_server_actions(args: Dict[str, Any]) -> Dict[str, Any]:
        return {
            "content": [{
                "type": "text",
                "text": json.dumps({
                    "read_only_actions": READ_ONLY_ACTIONS,
                    "mutation_actions": MUTATION_ACTIONS,
                    "total": len(READ_ONLY_ACTIONS) + len(MUTATION_ACTIONS)
                }, indent=2)
            }],
            "isError": False
        }

    async def server_query(args: Dict[str, Any]) -> Dict[str, Any]:
        """Execute read-only server query actions without confirmation."""
        action_type = args.get("action_type", "").strip()
        payload_str = args.get("payload", "{}")
        user = args.get("_user", "unknown")
        use_cache = args.get("use_cache", True)

        if action_type not in READ_ONLY_ACTIONS:
            return {"content": [{"type": "text", "text": f"Action '{action_type}' not allowed in server_query. Use server_manage for mutation actions.\nRead-only actions: {READ_ONLY_ACTIONS[:10]}..."}], "isError": True}

        spec = ACTION_SPECS.get(action_type)
        if not spec:
            return {"content": [{"type": "text", "text": f"Unknown action: {action_type}"}], "isError": True}

        try:
            payload = _normalize_payload(payload_str)
        except ValueError as e:
            return {"content": [{"type": "text", "text": f"Payload error: {e}"}], "isError": True}

        if spec.get("cacheable") and use_cache:
            fingerprint = _payload_fingerprint(action_type, payload)
            cached = _get_cached_result(fingerprint, spec.get("cache_ttl", 5))
            if cached:
                return cached

        handler_method = spec.get("handler_method")
        handler = getattr(toolset, handler_method, None)
        if not handler:
            return {"content": [{"type": "text", "text": f"Handler not found: {handler_method}"}], "isError": True}

        try:
            result = await handler(payload)
        except Exception as e:
            result = {"content": [{"type": "text", "text": f"Error: {type(e).__name__}: {e}"}], "isError": True}

        _record_action(action_type, payload, result, user)

        if spec.get("cacheable") and not result.get("isError") and use_cache:
            _set_cached_result(_payload_fingerprint(action_type, payload), result)

        return result

    async def server_manage(args: Dict[str, Any]) -> Dict[str, Any]:
        """Execute mutation/admin actions (requires confirmation in ChatGPT)."""
        action_type = args.get("action_type", "").strip()
        payload_str = args.get("payload", "{}")
        user = args.get("_user", "unknown")

        spec = ACTION_SPECS.get(action_type)
        if not spec:
            return {"content": [{"type": "text", "text": f"Unknown action: {action_type}"}], "isError": True}

        try:
            payload = _normalize_payload(payload_str)
        except ValueError as e:
            return {"content": [{"type": "text", "text": f"Payload error: {e}"}], "isError": True}

        handler_method = spec.get("handler_method")
        handler = getattr(toolset, handler_method, None)
        if not handler:
            return {"content": [{"type": "text", "text": f"Handler not found: {handler_method}"}], "isError": True}

        try:
            result = await handler(payload)
        except Exception as e:
            result = {"content": [{"type": "text", "text": f"Error: {type(e).__name__}: {e}"}], "isError": True}

        _record_action(action_type, payload, result, user)
        return result

    async def get_action_history(args: Dict[str, Any]) -> Dict[str, Any]:
        limit = int(args.get("limit", 20))
        state = _load_json(ACTION_ROUTER_STATE_PATH, {"history": []})
        history = list(state.get("history", []))[-limit:]
        return {"content": [{"type": "text", "text": json.dumps(history, indent=2)}], "isError": False}

    # Register tools with explicit separation
    tools = [
        # READ-ONLY tool - NO confirmation needed
        ExtraToolDefinition(
            "server_query",
            "Query server state: status, logs, files, processes, containers. Read-only operations only. No modifications. Safe for autonomous execution.",
            {
                "type": "object",
                "properties": {
                    "action_type": {
                        "type": "string",
                        "enum": READ_ONLY_ACTIONS,
                        "description": "Read-only query action"
                    },
                    "payload": {
                        "type": "string",
                        "description": "JSON args"
                    },
                    "use_cache": {
                        "type": "boolean",
                        "default": True
                    }
                },
                "required": ["action_type"]
            },
            server_query,
            False,
            _ro("Server Query")
        ),
        # MUTATION tool - confirmation needed
        ExtraToolDefinition(
            "server_manage",
            "Manage server: restart services, modify files, run commands. Mutation operations that change server state.",
            {
                "type": "object",
                "properties": {
                    "action_type": {
                        "type": "string",
                        "description": "Mutation action type"
                    },
                    "payload": {
                        "type": "string",
                        "description": "JSON args"
                    }
                },
                "required": ["action_type"]
            },
            server_manage,
            True,  # dangerous=True
            _rw("Server Manage", destructive=True)  # NO readOnlyHint
        ),
        ExtraToolDefinition("list_server_actions", "List all available server actions separated by type.", {"type": "object", "properties": {}, "required": []}, list_server_actions, False, _ro("List Actions")),
        ExtraToolDefinition("get_action_history", "Get recent action execution history.", {"type": "object", "properties": {"limit": {"type": "integer", "default": 20}}, "required": []}, get_action_history, False, _ro("Get History")),
    ]
    for t in tools:
        toolset._register_tool(t)
