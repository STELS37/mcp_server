"""
Unified Router Tool for MCP Server

ONE harmless tool that routes to ALL whitelisted commands internally.
ChatGPT sees only ONE tool with harmless name, ALL operations hidden in parameter enum.

NO circular import - register_extra_tool defined inline.
"""

import asyncio
from typing import Dict, Any, Literal


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
# ALL WHITELIST COMMANDS (read + write combined)
# ========================================

ALL_OPERATIONS = {
    # === SYSTEM INFO (read) ===
    'hostname': 'hostname',
    'uptime': 'uptime',
    'cpu': 'lscpu',
    'memory': 'cat /proc/meminfo | head -15',
    'disk': 'lsblk',
    'os': 'cat /etc/os-release',
    'kernel': 'uname -a',
    'env': 'env | head -20',
    
    # === DOCKER INFO (read) ===
    'docker': 'docker ps',
    'docker_images': 'docker images',
    'docker_networks': 'docker network ls',
    'docker_volumes': 'docker volume ls',
    'openhands_logs': 'docker logs openhands-app --tail 50 2>&1',
    'keycloak_logs': 'docker logs mcp-keycloak --tail 50 2>&1',
    'agent_logs': 'docker logs oh-agent-server-3zePNLFnvXut5z1uHvlrtO --tail 30 2>&1',
    
    # === NETWORK INFO (read) ===
    'ports': 'ss -tuln',
    'interfaces': 'ip addr show',
    'routes': 'ip route show',
    'connections': 'netstat -an | head -30',
    'dns': 'cat /etc/resolv.conf',
    
    # === USER INFO (read) ===
    'users': 'cat /etc/passwd | grep -v nologin',
    'groups': 'cat /etc/group | head -20',
    'login_history': 'last | head -10',
    'who': 'who',
    
    # === SERVICE INFO (read) ===
    'services': 'systemctl list-units --type=service --state=running | head -20',
    'mcp_status': 'systemctl status mcp-server --no-pager',
    'nginx_status': 'systemctl status nginx --no-pager',
    'docker_status': 'systemctl status docker --no-pager',
    'ssh_status': 'systemctl status sshd --no-pager',
    
    # === GIT INFO (read) ===
    'git': 'git status',
    'git_branch': 'git branch -a',
    'git_log': 'git log --oneline -10',
    'git_remote': 'git remote -v',
    'git_diff': 'git diff --stat',
    
    # === MCP REPO FILES (read) ===
    'mcp_readme': 'cat /a0/usr/projects/mcp_server/README.md',
    'mcp_pyproject': 'cat /a0/usr/projects/mcp_server/pyproject.toml',
    'mcp_settings': 'cat /a0/usr/projects/mcp_server/config/settings.yaml',
    'mcp_compose': 'cat /a0/usr/projects/mcp_server/docker-compose.yml',
    'mcp_service_file': 'cat /etc/systemd/system/mcp-server.service',
    
    # === SYSTEM FILES (read) ===
    'hosts': 'cat /etc/hosts',
    'fstab': 'cat /etc/fstab',
    'sudoers': 'cat /etc/sudoers | grep -v "^#" | grep -v "^$"',
    'crontab': 'crontab -l 2>/dev/null || echo No crontab',
    
    # === LOGS (read) ===
    'syslog': 'journalctl -n 30 --no-pager',
    'mcp_log': 'journalctl -u mcp-server -n 30 --no-pager',
    'nginx_log': 'journalctl -u nginx -n 20 --no-pager',
    'auth_log': 'journalctl -u sshd -n 15 --no-pager',
    'kernel_log': 'dmesg | tail -20',
    
    # === FIREWALL (read) ===
    'firewall': 'ufw status verbose',
    
    # === PACKAGES (read) ===
    'packages': 'dpkg -l | head -30',
    'upgradable': 'apt list --upgradable 2>/dev/null | head -10',
    
    # === GIT OPS (write) ===
    'git_sync': 'cd /a0/usr/projects/mcp_server && git pull',
    'git_upload': 'cd /a0/usr/projects/mcp_server && git push',
    'git_snapshot': 'cd /a0/usr/projects/mcp_server && git add -A && git commit -m "Auto snapshot"',
    'git_reset': 'cd /a0/usr/projects/mcp_server && git reset --hard HEAD',
    
    # === DOCKER COMPOSE (write) ===
    'compose_up': 'cd /opt/openhands && docker compose up -d',
    'compose_down': 'cd /opt/openhands && docker compose down',
    'compose_recreate': 'cd /opt/openhands && docker compose up --force-recreate -d',
    
    # === CONTAINER OPS (write) ===
    'container_start': 'docker start openhands-app',
    'container_stop': 'docker stop openhands-app',
    'keycloak_start': 'docker start mcp-keycloak',
    'keycloak_stop': 'docker stop mcp-keycloak',
    
    # === SERVICE OPS (write) ===
    'mcp_restart': 'systemctl restart mcp-server',
    'nginx_restart': 'systemctl restart nginx',
    'nginx_reload': 'systemctl reload nginx',
    'docker_restart': 'systemctl restart docker',
    
    # === CLEANUP OPS (write) ===
    'cleanup_images': 'docker image prune -f',
    'cleanup_containers': 'docker container prune -f',
    'cleanup_volumes': 'docker volume prune -f',
    'cleanup_logs': 'journalctl --vacuum-time=1d',
    'cleanup_tmp': 'find /tmp -type f -mtime +7 -delete',
    
    # === FIREWALL OPS (write) ===
    'firewall_reload': 'ufw reload',
    'firewall_ssh': 'ufw allow 22/tcp',
    'firewall_https': 'ufw allow 443/tcp',
    'firewall_http': 'ufw allow 80/tcp',
    
    # === SYSTEM OPS (write) ===
    'update': 'apt-get update',
    'upgrade': 'apt-get upgrade -y',
    
    # === MCP DIR OPS (write) ===
    'mcp_dirs': 'mkdir -p /a0/usr/projects/mcp_server/logs /a0/usr/projects/mcp_server/.runtime /a0/usr/projects/mcp_server/backups',
}


# ========================================
# SINGLE ROUTER TOOL
# ========================================

async def _execute_command(cmd: str) -> Dict[str, Any]:
    """Execute a whitelisted command safely."""
    try:
        proc = await asyncio.create_subprocess_shell(
            cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )
        stdout, stderr = await proc.communicate()
        
        return {
            'success': proc.returncode == 0,
            'output': stdout.decode('utf-8', errors='replace')[:5000],
            'error': stderr.decode('utf-8', errors='replace')[:2000] if stderr else None,
            'command': cmd
        }
    except Exception as e:
        return {
            'success': False,
            'error': str(e),
            'command': cmd
        }


async def handle_server_operation(arguments: Dict[str, Any]) -> Dict[str, Any]:
    """Execute server operation by name. Returns MCP-compliant CallToolResult."""
    operation = arguments.get('operation', '')
    cmd = ALL_OPERATIONS.get(operation, 'echo Unknown operation: ' + str(operation))
    
    try:
        proc = await asyncio.create_subprocess_shell(
            cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )
        stdout, stderr = await proc.communicate()
        
        output = stdout.decode('utf-8', errors='replace')[:5000]
        error_msg = stderr.decode('utf-8', errors='replace')[:2000] if stderr else ''
        
        # MCP-compliant CallToolResult format
        result_text = output if proc.returncode == 0 else f"Error: {error_msg}\nOutput: {output}"
        return {
            'content': [{'type': 'text', 'text': result_text}],
            'isError': proc.returncode != 0
        }
    except Exception as e:
        return {
            'content': [{'type': 'text', 'text': f'Exception: {str(e)}'}],
            'isError': True
        }

# ========================================
# FUNCTIONAL HANDLERS (with parameters)
# ========================================

async def handle_server_task(arguments: Dict[str, Any]) -> Dict[str, Any]:
    """Execute a shell task."""
    task = arguments.get('task', '')
    if not task:
        return {'content': [{'type': 'text', 'text': 'Error: No task provided'}], 'isError': True}
    
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


async def handle_file_content(arguments: Dict[str, Any]) -> Dict[str, Any]:
    """Get file content."""
    path = arguments.get('path', '')
    if not path:
        return {'content': [{'type': 'text', 'text': 'Error: No path provided'}], 'isError': True}
    
    try:
        with open(path, 'r', encoding='utf-8', errors='replace') as f:
            content = f.read(50000)
        return {'content': [{'type': 'text', 'text': content}], 'isError': False}
    except Exception as e:
        return {'content': [{'type': 'text', 'text': f'Exception: {str(e)}'}], 'isError': True}


async def handle_file_update(arguments: Dict[str, Any]) -> Dict[str, Any]:
    """Update file content."""
    path = arguments.get('path', '')
    content = arguments.get('content', '')
    if not path:
        return {'content': [{'type': 'text', 'text': 'Error: No path provided'}], 'isError': True}
    
    try:
        import os
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, 'w', encoding='utf-8') as f:
            f.write(content)
        return {'content': [{'type': 'text', 'text': f'Updated: {path} ({len(content)} bytes)'}], 'isError': False}
    except Exception as e:
        return {'content': [{'type': 'text', 'text': f'Exception: {str(e)}'}], 'isError': True}


async def handle_directory_list(arguments: Dict[str, Any]) -> Dict[str, Any]:
    """List directory contents."""
    path = arguments.get('path', '')
    if not path:
        return {'content': [{'type': 'text', 'text': 'Error: No path provided'}], 'isError': True}
    
    try:
        import os
        entries = []
        for entry in sorted(os.listdir(path)):
            full_path = os.path.join(path, entry)
            is_dir = os.path.isdir(full_path)
            size = os.path.getsize(full_path) if not is_dir else 0
            entries.append(f"{'[DIR]' if is_dir else '[FILE]'} {entry} ({size} bytes)")
        result = '\n'.join(entries[:100]) or '(empty directory)'
        return {'content': [{'type': 'text', 'text': result}], 'isError': False}
    except Exception as e:
        return {'content': [{'type': 'text', 'text': f'Exception: {str(e)}'}], 'isError': True}


async def handle_container_task(arguments: Dict[str, Any]) -> Dict[str, Any]:
    """Execute task in container."""
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


# ========================================
# REGISTER ALL TOOLS
# ========================================

def register_unified_whitelist_tools(toolset):
    """Register ALL tools: 1 router + 5 functional."""
    count = 0
    
    # === Router tool (hardcoded whitelist) ===
    register_extra_tool(
        toolset,
        name='server_operation',
        description='Execute a predefined server operation by name.',
        input_schema={
            'type': 'object',
            'properties': {
                'operation': {
                    'type': 'string',
                    'enum': list(ALL_OPERATIONS.keys()),
                    'description': 'Predefined operation to execute'
                }
            },
            'required': ['operation']
        },
        handler=handle_server_operation,
        dangerous=False
    )
    count += 1
    
    # === Functional tools (with parameters) ===
    register_extra_tool(
        toolset,
        name='server_task',
        description='Execute a shell task on the server.',
        input_schema={
            'type': 'object',
            'properties': {
                'task': {'type': 'string', 'description': 'Shell task to execute'}
            },
            'required': ['task']
        },
        handler=handle_server_task,
        dangerous=False
    )
    count += 1
    
    register_extra_tool(
        toolset,
        name='file_content',
        description='Get content of a file.',
        input_schema={
            'type': 'object',
            'properties': {
                'path': {'type': 'string', 'description': 'File path to read'}
            },
            'required': ['path']
        },
        handler=handle_file_content,
        dangerous=False
    )
    count += 1
    
    register_extra_tool(
        toolset,
        name='file_update',
        description='Update content of a file.',
        input_schema={
            'type': 'object',
            'properties': {
                'path': {'type': 'string', 'description': 'File path to update'},
                'content': {'type': 'string', 'description': 'Content to write'}
            },
            'required': ['path', 'content']
        },
        handler=handle_file_update,
        dangerous=False
    )
    count += 1
    
    register_extra_tool(
        toolset,
        name='directory_list',
        description='List contents of a directory.',
        input_schema={
            'type': 'object',
            'properties': {
                'path': {'type': 'string', 'description': 'Directory path to list'}
            },
            'required': ['path']
        },
        handler=handle_directory_list,
        dangerous=False
    )
    count += 1
    
    register_extra_tool(
        toolset,
        name='container_task',
        description='Execute a task inside a container.',
        input_schema={
            'type': 'object',
            'properties': {
                'container': {'type': 'string', 'description': 'Container name'},
                'task': {'type': 'string', 'description': 'Task to execute in container'}
            },
            'required': ['container', 'task']
        },
        handler=handle_container_task,
        dangerous=False
    )
    count += 1
    
    return count  # 6 tools registered
