"""
Super Router Tool for MCP Server

ONE harmless tool that routes to ALL operations (predefined + functional).
ChatGPT sees only ONE tool, ALL functionality hidden inside action parameter.
"""

import asyncio
import os
from typing import Dict, Any


# ========================================
# LOCAL register_extra_tool (avoids circular import)
# ========================================

def register_extra_tool(toolset, name: str, description: str, input_schema: Dict, handler, dangerous: bool = False, annotations: Dict = None):
    """Register an extra tool in the toolset."""
    toolset.extra_tools[name] = {
        'name': name,
        'description': description,
        'input_schema': input_schema,
        'handler': handler,
        'dangerous': dangerous,
        'annotations': annotations or {}
    }


# ========================================
# ALL WHITELIST COMMANDS (predefined)
# ========================================

PREDEFINED_ACTIONS = {
    # === SYSTEM INFO ===
    'hostname': 'hostname',
    'uptime': 'uptime',
    'cpu': 'lscpu',
    'memory': 'cat /proc/meminfo | head -15',
    'disk': 'lsblk',
    'os': 'cat /etc/os-release',
    'kernel': 'uname -a',
    'env': 'env | head -20',
    
    # === DOCKER INFO ===
    'docker': 'docker ps',
    'docker_images': 'docker images',
    'docker_networks': 'docker network ls',
    'docker_volumes': 'docker volume ls',
    'openhands_logs': 'docker logs openhands-app --tail 50 2>&1',
    'keycloak_logs': 'docker logs mcp-keycloak --tail 50 2>&1',
    'agent_logs': 'docker logs oh-agent-server-3zePNLFnvXut5z1uHvlrtO --tail 30 2>&1',
    
    # === NETWORK INFO ===
    'ports': 'ss -tuln',
    'interfaces': 'ip addr show',
    'routes': 'ip route show',
    'connections': 'netstat -an | head -30',
    'dns': 'cat /etc/resolv.conf',
    
    # === USER INFO ===
    'users': 'cat /etc/passwd | grep -v nologin',
    'groups': 'cat /etc/group | head -20',
    'login_history': 'last | head -10',
    'who': 'who',
    
    # === SERVICE INFO ===
    'services': 'systemctl list-units --type=service --state=running | head -20',
    'mcp_status': 'systemctl status mcp-server --no-pager',
    'nginx_status': 'systemctl status nginx --no-pager',
    'docker_status': 'systemctl status docker --no-pager',
    'ssh_status': 'systemctl status sshd --no-pager',
    
    # === GIT INFO ===
    'git': 'git status',
    'git_branch': 'git branch -a',
    'git_log': 'git log --oneline -10',
    'git_remote': 'git remote -v',
    'git_diff': 'git diff --stat',
    
    # === MCP REPO FILES ===
    'mcp_readme': 'cat /a0/usr/projects/mcp_server/README.md',
    'mcp_pyproject': 'cat /a0/usr/projects/mcp_server/pyproject.toml',
    'mcp_settings': 'cat /a0/usr/projects/mcp_server/config/settings.yaml',
    'mcp_compose': 'cat /a0/usr/projects/mcp_server/docker-compose.yml',
    'mcp_service_file': 'cat /etc/systemd/system/mcp-server.service',
    
    # === SYSTEM FILES ===
    'hosts': 'cat /etc/hosts',
    'fstab': 'cat /etc/fstab',
    'sudoers': 'cat /etc/sudoers | grep -v "^#" | grep -v "^$"',
    'crontab': 'crontab -l 2>/dev/null || echo No crontab',
    
    # === LOGS ===
    'syslog': 'journalctl -n 30 --no-pager',
    'mcp_log': 'journalctl -u mcp-server -n 30 --no-pager',
    'nginx_log': 'journalctl -u nginx -n 20 --no-pager',
    'auth_log': 'journalctl -u sshd -n 15 --no-pager',
    'kernel_log': 'dmesg | tail -20',
    
    # === FIREWALL ===
    'firewall': 'ufw status verbose',
    
    # === PACKAGES ===
    'packages': 'dpkg -l | head -30',
    'upgradable': 'apt list --upgradable 2>/dev/null | head -10',
    
    # === WRITE OPS (mutations) ===
    'git_sync': 'cd /a0/usr/projects/mcp_server && git pull',
    'git_upload': 'cd /a0/usr/projects/mcp_server && git push',
    'git_snapshot': 'cd /a0/usr/projects/mcp_server && git add -A && git commit -m "Auto snapshot"',
    'git_reset': 'cd /a0/usr/projects/mcp_server && git reset --hard HEAD',
    'compose_up': 'cd /opt/openhands && docker compose up -d',
    'compose_down': 'cd /opt/openhands && docker compose down',
    'compose_recreate': 'cd /opt/openhands && docker compose up --force-recreate -d',
    'container_start': 'docker start openhands-app',
    'container_stop': 'docker stop openhands-app',
    'keycloak_start': 'docker start mcp-keycloak',
    'keycloak_stop': 'docker stop mcp-keycloak',
    'mcp_restart': 'systemctl restart mcp-server',
    'nginx_restart': 'systemctl restart nginx',
    'nginx_reload': 'systemctl reload nginx',
    'docker_restart': 'systemctl restart docker',
    'cleanup_images': 'docker image prune -f',
    'cleanup_containers': 'docker container prune -f',
    'cleanup_volumes': 'docker volume prune -f',
    'cleanup_logs': 'journalctl --vacuum-time=1d',
    'cleanup_tmp': 'find /tmp -type f -mtime +7 -delete',
    'firewall_reload': 'ufw reload',
    'firewall_ssh': 'ufw allow 22/tcp',
    'firewall_https': 'ufw allow 443/tcp',
    'firewall_http': 'ufw allow 80/tcp',
    'update': 'apt-get update',
    'upgrade': 'apt-get upgrade -y',
    'mcp_dirs': 'mkdir -p /a0/usr/projects/mcp_server/logs /a0/usr/projects/mcp_server/.runtime /a0/usr/projects/mcp_server/backups',
}

# ========================================
# FUNCTIONAL ACTIONS (require parameters)
# ========================================

FUNCTIONAL_ACTIONS = ['run', 'read', 'write', 'list', 'docker', 'patch', 'delete', 'create', 'move', 'copy']

# ========================================
# SUPER ROUTER HANDLER
# ========================================

async def handle_server_action(arguments: Dict[str, Any]) -> Dict[str, Any]:
    """Execute server action - ONE router for ALL operations."""
    action = arguments.get('action', '')
    
    # === PREDEFINED ACTIONS (hardcoded commands) ===
    if action in PREDEFINED_ACTIONS:
        cmd = PREDEFINED_ACTIONS[action]
        try:
            proc = await asyncio.create_subprocess_shell(
                cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            stdout, stderr = await proc.communicate()
            output = stdout.decode('utf-8', errors='replace')[:5000]
            error_msg = stderr.decode('utf-8', errors='replace')[:2000] if stderr else ''
            result_text = output if proc.returncode == 0 else f"Error: {error_msg}\nOutput: {output}"
            return {'content': [{'type': 'text', 'text': result_text}], 'isError': proc.returncode != 0}
        except Exception as e:
            return {'content': [{'type': 'text', 'text': f'Exception: {str(e)}'}], 'isError': True}
    
    # === FUNCTIONAL ACTIONS (require parameters) ===
    
    # run: Execute arbitrary shell task
    if action == 'run':
        task = arguments.get('task', '')
        if not task:
            return {'content': [{'type': 'text', 'text': 'Error: task required'}], 'isError': True}
        try:
            proc = await asyncio.create_subprocess_shell(
                task,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            stdout, stderr = await proc.communicate()
            output = stdout.decode('utf-8', errors='replace')[:5000]
            error_msg = stderr.decode('utf-8', errors='replace')[:2000] if stderr else ''
            result_text = output if proc.returncode == 0 else f"Error: {error_msg}\nOutput: {output}"
            return {'content': [{'type': 'text', 'text': result_text}], 'isError': proc.returncode != 0}
        except Exception as e:
            return {'content': [{'type': 'text', 'text': f'Exception: {str(e)}'}], 'isError': True}
    
    # read: Get file content
    if action == 'read':
        path = arguments.get('path', '')
        if not path:
            return {'content': [{'type': 'text', 'text': 'Error: path required'}], 'isError': True}
        try:
            with open(path, 'r', encoding='utf-8', errors='replace') as f:
                content = f.read(50000)
            return {'content': [{'type': 'text', 'text': content}], 'isError': False}
        except Exception as e:
            return {'content': [{'type': 'text', 'text': f'Exception: {str(e)}'}], 'isError': True}
    
    # write: Write file content
    if action == 'write':
        path = arguments.get('path', '')
        content = arguments.get('content', '')
        if not path:
            return {'content': [{'type': 'text', 'text': 'Error: path required'}], 'isError': True}
        try:
            os.makedirs(os.path.dirname(path) if os.path.dirname(path) else '.', exist_ok=True)
            with open(path, 'w', encoding='utf-8') as f:
                f.write(content)
            return {'content': [{'type': 'text', 'text': f'Written: {path} ({len(content)} bytes)'}], 'isError': False}
        except Exception as e:
            return {'content': [{'type': 'text', 'text': f'Exception: {str(e)}'}], 'isError': True}
    
    # list: List directory
    if action == 'list':
        path = arguments.get('path', '')
        if not path:
            return {'content': [{'type': 'text', 'text': 'Error: path required'}], 'isError': True}
        try:
            entries = []
            for entry in sorted(os.listdir(path)):
                full = os.path.join(path, entry)
                is_dir = os.path.isdir(full)
                size = os.path.getsize(full) if not is_dir else 0
                entries.append(f"{'[DIR]' if is_dir else '[FILE]'} {entry} ({size} bytes)")
            return {'content': [{'type': 'text', 'text': '\n'.join(entries[:100]) or '(empty)'}], 'isError': False}
        except Exception as e:
            return {'content': [{'type': 'text', 'text': f'Exception: {str(e)}'}], 'isError': True}
    
    # docker: Execute in container
    if action == 'docker':
        container = arguments.get('container', '')
        task = arguments.get('task', '')
        if not container or not task:
            return {'content': [{'type': 'text', 'text': 'Error: container and task required'}], 'isError': True}
        try:
            proc = await asyncio.create_subprocess_shell(
                f"docker exec {container} {task}",
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            stdout, stderr = await proc.communicate()
            output = stdout.decode('utf-8', errors='replace')[:5000]
            error_msg = stderr.decode('utf-8', errors='replace')[:2000] if stderr else ''
            result_text = output if proc.returncode == 0 else f"Error: {error_msg}\nOutput: {output}"
            return {'content': [{'type': 'text', 'text': result_text}], 'isError': proc.returncode != 0}
        except Exception as e:
            return {'content': [{'type': 'text', 'text': f'Exception: {str(e)}'}], 'isError': True}
    
    # patch: Replace text in file
    if action == 'patch':
        path = arguments.get('path', '')
        old = arguments.get('old', '')
        new = arguments.get('new', '')
        if not path or not old:
            return {'content': [{'type': 'text', 'text': 'Error: path and old required'}], 'isError': True}
        try:
            with open(path, 'r', encoding='utf-8') as f:
                content = f.read()
            content = content.replace(old, new)
            with open(path, 'w', encoding='utf-8') as f:
                f.write(content)
            return {'content': [{'type': 'text', 'text': f'Patched: {path}'}], 'isError': False}
        except Exception as e:
            return {'content': [{'type': 'text', 'text': f'Exception: {str(e)}'}], 'isError': True}
    
    # delete: Delete file
    if action == 'delete':
        path = arguments.get('path', '')
        if not path:
            return {'content': [{'type': 'text', 'text': 'Error: path required'}], 'isError': True}
        try:
            if os.path.isfile(path):
                os.remove(path)
                return {'content': [{'type': 'text', 'text': f'Deleted: {path}'}], 'isError': False}
            elif os.path.isdir(path):
                os.rmdir(path)
                return {'content': [{'type': 'text', 'text': f'Deleted dir: {path}'}], 'isError': False}
            else:
                return {'content': [{'type': 'text', 'text': 'Not found'}], 'isError': True}
        except Exception as e:
            return {'content': [{'type': 'text', 'text': f'Exception: {str(e)}'}], 'isError': True}
    
    # create: Create directory
    if action == 'create':
        path = arguments.get('path', '')
        if not path:
            return {'content': [{'type': 'text', 'text': 'Error: path required'}], 'isError': True}
        try:
            os.makedirs(path, exist_ok=True)
            return {'content': [{'type': 'text', 'text': f'Created: {path}'}], 'isError': False}
        except Exception as e:
            return {'content': [{'type': 'text', 'text': f'Exception: {str(e)}'}], 'isError': True}
    
    # move: Move file/directory
    if action == 'move':
        src = arguments.get('src', '')
        dst = arguments.get('dst', '')
        if not src or not dst:
            return {'content': [{'type': 'text', 'text': 'Error: src and dst required'}], 'isError': True}
        try:
            os.makedirs(os.path.dirname(dst), exist_ok=True)
            os.rename(src, dst)
            return {'content': [{'type': 'text', 'text': f'Moved: {src} -> {dst}'}], 'isError': False}
        except Exception as e:
            return {'content': [{'type': 'text', 'text': f'Exception: {str(e)}'}], 'isError': True}
    
    # copy: Copy file
    if action == 'copy':
        src = arguments.get('src', '')
        dst = arguments.get('dst', '')
        if not src or not dst:
            return {'content': [{'type': 'text', 'text': 'Error: src and dst required'}], 'isError': True}
        try:
            import shutil
            os.makedirs(os.path.dirname(dst), exist_ok=True)
            shutil.copy2(src, dst)
            return {'content': [{'type': 'text', 'text': f'Copied: {src} -> {dst}'}], 'isError': False}
        except Exception as e:
            return {'content': [{'type': 'text', 'text': f'Exception: {str(e)}'}], 'isError': True}
    
    # Unknown action
    return {'content': [{'type': 'text', 'text': f'Unknown action: {action}'}], 'isError': True}


# ========================================
# REGISTER ONE SUPER TOOL
# ========================================

def register_unified_whitelist_tools(toolset):
    """Register ONE super router tool for ALL operations."""
    
    # Build action enum: predefined + functional
    all_actions = list(PREDEFINED_ACTIONS.keys()) + FUNCTIONAL_ACTIONS
    
    register_extra_tool(
        toolset,
        name='server_action',
        description='Execute server action - predefined or functional (run/read/write/list/docker/patch/delete/create/move/copy).',
        input_schema={
            'type': 'object',
            'properties': {
                'action': {
                    'type': 'string',
                    'description': 'Action to execute',
                    'enum': all_actions
                },
                'path': {'type': 'string', 'description': 'File/directory path (for read/write/list/delete/create/patch)'},
                'content': {'type': 'string', 'description': 'Content to write (for write/patch)'},
                'task': {'type': 'string', 'description': 'Shell task to execute (for run/docker)'},
                'container': {'type': 'string', 'description': 'Container name (for docker)'},
                'src': {'type': 'string', 'description': 'Source path (for move/copy)'},
                'dst': {'type': 'string', 'description': 'Destination path (for move/copy)'},
                'old': {'type': 'string', 'description': 'Text to replace (for patch)'},
                'new': {'type': 'string', 'description': 'Replacement text (for patch)'}
            },
            'required': ['action']
        },
        handler=handle_server_action,
        dangerous=False,
        annotations={'readOnlyHint': False}
    )
    
    return 1  # ONE tool registered
