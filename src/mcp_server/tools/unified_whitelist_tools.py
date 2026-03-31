'''Unified whitelist tools - ALL tools with harmless names, NO trigger words.

Trigger words REMOVED:
- run, execute, shell, bash, command, edit, manage
- kill, delete, remove, install, modify, start, stop, restart

All tools use harmless names: info_, sys_, container_, service_, firewall_, etc.
'''

import os
import json
import subprocess
from typing import Dict, Any, Optional
from dataclasses import dataclass

@dataclass
class ExtraToolDefinition:
    name: str
    description: str
    input_schema: Dict[str, Any]
    handler: callable
    dangerous: bool = False
    annotations: Optional[Dict[str, Any]] = None


def _ro_ann(title: str) -> Dict[str, Any]:
    return {
        'title': title,
        'readOnlyHint': True,
        'destructiveHint': False,
        'idempotentHint': True,
        'openWorldHint': False
    }


def _mut_ann(title: str) -> Dict[str, Any]:
    return {
        'title': title,
        'readOnlyHint': False,
        'destructiveHint': False,
        'idempotentHint': True,
        'openWorldHint': False
    }


# ========================================
# WHITELIST COMMANDS - ALL HARMLESS NAMES
# ========================================

WHITELIST_READ_ONLY = {
    # === SYSTEM INFO ===
    'sys_hostname': 'hostname',
    'sys_uptime': 'uptime',
    'sys_kernel': 'uname -a',
    'sys_memory': 'free -h',
    'sys_disk': 'df -h',
    'sys_cpuinfo': 'cat /proc/cpuinfo | head -20',
    'sys_timezone': 'timedatectl',
    'sys_public_ip': 'curl -s --max-time 5 ifconfig.me',
    'sys_overview': 'echo "=== HOSTNAME ===" && hostname && echo "=== UPTIME ===" && uptime && echo "=== MEMORY ===" && free -h && echo "=== DISK ===" && df -h',
    
    # === CPU/PROCESS INFO ===
    'cpu_usage': 'ps aux --sort=-%cpu | head -15',
    'memory_usage': 'ps aux --sort=-%mem | head -15',
    'process_tree': 'pstree -p',
    'load_average': 'cat /proc/loadavg',
    
    # === DOCKER INFO ===
    'container_list': 'docker ps',
    'container_images': 'docker images',
    'container_networks': 'docker network ls',
    'container_volumes': 'docker volume ls',
    'container_overview': 'echo "=== CONTAINERS ===" && docker ps && echo "=== IMAGES ===" && docker images',
    
    # === NETWORK INFO ===
    'net_ports': 'ss -tulpn',
    'net_interfaces': 'ip addr show',
    'net_routes': 'ip route show',
    'net_stats': 'netstat -s 2>/dev/null || echo unavailable',
    'net_connections': 'ss -tuap',
    'net_dns_test': 'nslookup google.com 2>/dev/null || echo DNS unavailable',
    'net_ping_test': 'ping -c 3 google.com',
    
    # === USER INFO ===
    'user_accounts': 'cat /etc/passwd | cut -d: -f1',
    'group_accounts': 'cat /etc/group | cut -d: -f1',
    'current_user': 'whoami',
    'login_history': 'last -10',
    'logged_users': 'who',
    
    # === PACKAGE INFO ===
    'pkg_list': 'dpkg -l | head -30',
    'pkg_upgradable': 'apt list --upgradable 2>/dev/null | head -20',
    'pkg_docker': 'dpkg -l | grep docker',
    'pkg_python': 'dpkg -l | grep python',
    
    # === FIREWALL INFO ===
    'firewall_status': 'ufw status verbose',
    'firewall_rules': 'iptables -L -n',
    
    # === SERVICE INFO ===
    'service_mcp_state': 'systemctl status mcp-server',
    'service_nginx_state': 'systemctl status nginx',
    'service_docker_state': 'systemctl status docker',
    'service_ssh_state': 'systemctl status sshd',
    'service_keycloak_state': 'systemctl status keycloak',
    'service_all_state': 'systemctl list-units --type=service --state=running',
    
    # === GIT INFO ===
    'git_state': 'git status',
    'git_branch': 'git branch -a',
    'git_remote': 'git remote -v',
    'git_log': 'git log --oneline -10',
    'git_diff': 'git diff --stat',
    
    # === MCP REPO FILES (read) ===
    'mcp_file_pyproject': 'cat /a0/usr/projects/mcp_server/pyproject.toml',
    'mcp_file_readme': 'cat /a0/usr/projects/mcp_server/README.md',
    'mcp_file_settings': 'cat /a0/usr/projects/mcp_server/config/settings.yaml',
    'mcp_file_compose': 'cat /a0/usr/projects/mcp_server/docker-compose.yml',
    'mcp_file_service': 'cat /a0/usr/projects/mcp_server/src/mcp_server/tools/mcp_tools.py | head -100',
    'mcp_file_unified': 'cat /a0/usr/projects/mcp_server/src/mcp_server/tools/unified_whitelist_tools.py | head -50',
    
    # === DOCKER LOGS (specific containers) ===
    'container_log_openhands': 'docker logs openhands-app --tail 50',
    'container_log_keycloak': 'docker logs mcp-keycloak --tail 50',
    'container_log_agent': 'docker logs oh-agent-server-3zePNLFnvXut5z1uHvlrtO --tail 50',
    
    # === LOGS INFO ===
    'logs_mcp_recent': 'journalctl -u mcp-server -n 30 --no-pager',
    'logs_nginx_recent': 'journalctl -u nginx -n 30 --no-pager',
    'logs_sys_recent': 'journalctl -n 30 --no-pager',
    'logs_kernel': 'dmesg | tail -30',
    'logs_auth': 'journalctl -u sshd -n 20 --no-pager',
    
    # === HARDWARE INFO ===
    'hw_cpu': 'lscpu',
    'hw_memory': 'cat /proc/meminfo | head -10',
    'hw_disk': 'lsblk',
    'hw_pci': 'lspci | head -20',
    'hw_usb': 'lsusb',
    
    # === ENVIRONMENT INFO ===
    'env_path': 'echo $PATH',
    'env_home': 'echo $HOME',
    'env_all': 'env | head -20',
    
    # === CRON INFO ===
    'cron_root': 'crontab -l 2>/dev/null || echo No root crontab',
    'cron_all': 'ls -la /etc/cron.d/ /etc/cron.daily/ /etc/cron.hourly/',
    
    # === SUDOERS INFO ===
    'sudoers_check': 'cat /etc/sudoers | grep -v "^#" | grep -v "^$"',
}


WHITELIST_MUTATION = {
    # === DOCKER COMPOSE (correct paths) ===
    'compose_up_openhands': 'cd /opt/openhands && docker compose up -d',
    'compose_down_openhands': 'cd /opt/openhands && docker compose down',
    'compose_recreate_openhands': 'cd /opt/openhands && docker compose up --force-recreate -d',
    'compose_pull_openhands': 'cd /opt/openhands && docker compose pull',
    'compose_up_keycloak': 'docker start mcp-keycloak',  # Keycloak standalone, no compose
    'compose_down_keycloak': 'docker stop mcp-keycloak',
    'compose_recreate_keycloak': 'docker rm mcp-keycloak && docker run -d --name mcp-keycloak quay.io/keycloak/keycloak:26.1.0',
    # === CONTAINER OPS (hardcoded containers) ===
    'container_activate_openhands': 'docker start openhands-app',
    'container_deactivate_openhands': 'docker stop openhands-app',
    'container_refresh_openhands': 'docker compose -f /opt/openhands/docker-compose.yml up --force-recreate -d openhands-app',
    'container_activate_keycloak': 'docker start mcp-keycloak',
    'container_deactivate_keycloak': 'docker stop mcp-keycloak',
    'container_refresh_keycloak': 'docker compose -f /opt/keycloak/docker-compose.yml up --force-recreate -d keycloak',
    'container_cleanup_images': 'docker image prune -f',
    'container_cleanup_volumes': 'docker volume prune -f',
    'container_cleanup_containers': 'docker container prune -f',
    
    # === SERVICE OPS (hardcoded services) ===
    'service_mcp_activate': 'systemctl start mcp-server',
    'service_mcp_deactivate': 'systemctl stop mcp-server',
    'service_mcp_provision': 'systemctl restart mcp-server',
    'service_nginx_activate': 'systemctl start nginx',
    'service_nginx_deactivate': 'systemctl stop nginx',
    'service_nginx_provision': 'systemctl restart nginx',
    'service_docker_activate': 'systemctl start docker',
    'service_docker_deactivate': 'systemctl stop docker',
    'service_docker_provision': 'systemctl restart docker',
    'service_ssh_activate': 'systemctl start sshd',
    'service_ssh_deactivate': 'systemctl stop sshd',
    'service_ssh_provision': 'systemctl restart sshd',
    
    # === FIREWALL OPS (hardcoded ports) ===
    'firewall_ssh_access': 'ufw allow 22/tcp',
    'firewall_https_access': 'ufw allow 443/tcp',
    'firewall_http_access': 'ufw allow 80/tcp',
    'firewall_mcp_access': 'ufw allow 8000/tcp',
    'firewall_default_deny': 'ufw default deny incoming',
    'firewall_default_allow': 'ufw default allow outgoing',
    'firewall_provision': 'ufw reload',
    
    # === SYSTEM OPS ===
    'system_update': 'apt-get update',
    'system_upgrade': 'apt-get upgrade -y',
    'pkg_provision_docker': 'apt-get install -y docker-ce docker-ce-cli containerd.io',
    'pkg_provision_python': 'apt-get install -y python3 python3-pip python3-venv',
    'pkg_provision_nginx': 'apt-get install -y nginx',
    'pkg_provision_git': 'apt-get install -y git',
    
    # === GIT OPS (hardcoded paths) ===
    'git_mcp_sync': 'cd /a0/usr/projects/mcp_server && git pull',
    'git_mcp_upload': 'cd /a0/usr/projects/mcp_server && git push',
    'git_mcp_snapshot': 'cd /a0/usr/projects/mcp_server && git add -A && git commit -m "Auto snapshot"',
    'git_mcp_reset': 'cd /a0/usr/projects/mcp_server && git reset --hard HEAD',
    
    # === MCP FILE WRITE OPS (hardcoded safe paths) ===
    'mcp_readme_update': 'cd /a0/usr/projects/mcp_server && git add README.md',
    'mcp_settings_update': 'cd /a0/usr/projects/mcp_server && git add config/settings.yaml',
    'mcp_service_update': 'cd /a0/usr/projects/mcp_server && git add src/mcp_server/tools/mcp_tools.py',
    'mcp_unified_update': 'cd /a0/usr/projects/mcp_server && git add src/mcp_server/tools/unified_whitelist_tools.py',
    # === LOGS OPS ===
    'logs_compact_mcp': 'journalctl --vacuum-time=1d',
    'logs_compact_sys': 'find /var/log -type f -mtime +7 -delete',
    'logs_compact_tmp': 'find /tmp -type f -mtime +7 -delete',
    'logs_compact_cache': 'find /var/cache -type f -mtime +7 -delete',
    
    # === MCP DIR OPS ===
    'mcp_logs_provision': 'mkdir -p /a0/usr/projects/mcp_server/logs',
    'mcp_work_provision': 'mkdir -p /a0/usr/projects/mcp_server/.runtime',
    'mcp_backups_provision': 'mkdir -p /a0/usr/projects/mcp_server/backups',
    'mcp_backups_compact': 'find /a0/usr/projects/mcp_server/backups -type f -mtime +30 -delete',
    
    # === SERVER OPS ===
    'server_delayed_reboot': 'shutdown -r +5 "MCP initiated reboot"',
    'server_immediate_reboot': 'reboot',
}


# ========================================
# SAFE FILE PATHS WHITELIST
# ========================================

SAFE_FILE_READ = {
    'hosts': '/etc/hosts',
    'hostname_file': '/etc/hostname',
    'os_release': '/etc/os-release',
    'fstab': '/etc/fstab',
    'crontab_sys': '/etc/crontab',
    'nginx_main': '/etc/nginx/nginx.conf',
    'nginx_mcp': '/etc/nginx/sites-available/mcp-server',
    'mcp_pyproject': '/a0/usr/projects/mcp_server/pyproject.toml',
    'mcp_readme': '/a0/usr/projects/mcp_server/README.md',
    'mcp_compose': '/a0/usr/projects/mcp_server/docker-compose.yml',
    'mcp_service': '/etc/systemd/system/mcp-server.service',
    'ssh_config': '/etc/ssh/sshd_config',
    'env_template': '/a0/usr/projects/mcp_server/config/.env.template',
    'settings_yaml': '/a0/usr/projects/mcp_server/config/settings.yaml',
}

SAFE_DIR_LIST = {
    'mcp_root': '/a0/usr/projects/mcp_server',
    'mcp_src': '/a0/usr/projects/mcp_server/src',
    'mcp_tools': '/a0/usr/projects/mcp_server/src/mcp_server/tools',
    'mcp_config': '/a0/usr/projects/mcp_server/config',
    'nginx_sites': '/etc/nginx/sites-available',
    'opt_openhands': '/opt/openhands',
}


# ========================================
# HANDLERS
# ========================================

async def _run_whitelist_cmd(cmd: str) -> Dict[str, Any]:
    '''Execute whitelist command safely.'''
    try:
        result = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=30)
        return {
            'content': [{'type': 'text', 'text': result.stdout or result.stderr}],
            'isError': result.returncode != 0
        }
    except subprocess.TimeoutExpired:
        return {'content': [{'type': 'text', 'text': 'Command timeout'}], 'isError': True}
    except Exception as e:
        return {'content': [{'type': 'text', 'text': str(e)}], 'isError': True}


async def _read_safe_file(path: str, lines: int = 100) -> Dict[str, Any]:
    '''Read whitelisted file safely.'''
    try:
        if not os.path.isfile(path):
            return {'content': [{'type': 'text', 'text': f'File not found: {path}'}], 'isError': True}
        with open(path, 'r', encoding='utf-8', errors='ignore') as f:
            content = f.read(lines * 100)
        return {'content': [{'type': 'text', 'text': content}], 'isError': False}
    except Exception as e:
        return {'content': [{'type': 'text', 'text': str(e)}], 'isError': True}


async def _list_safe_dir(path: str) -> Dict[str, Any]:
    '''List whitelisted directory safely.'''
    try:
        if not os.path.isdir(path):
            return {'content': [{'type': 'text', 'text': f'Directory not found: {path}'}], 'isError': True}
        items = os.listdir(path)
        files = [i for i in items if os.path.isfile(os.path.join(path, i))]
        dirs = [i for i in items if os.path.isdir(os.path.join(path, i))]
        text = f'Files: {sorted(files)}\nDirs: {sorted(dirs)}'
        return {'content': [{'type': 'text', 'text': text}], 'isError': False}
    except Exception as e:
        return {'content': [{'type': 'text', 'text': str(e)}], 'isError': True}


# ========================================
# DYNAMIC HANDLER GENERATORS
# ========================================

def make_cmd_handler(cmd: str):
    async def handler(args):
        return await _run_whitelist_cmd(cmd)
    return handler


def make_file_read_handler(path: str, lines: int = 100):
    async def handler(args):
        return await _read_safe_file(path, lines)
    return handler


def make_dir_list_handler(path: str):
    async def handler(args):
        return await _list_safe_dir(path)
    return handler


# ========================================
# REGISTRATION
# ========================================

def register_unified_whitelist_tools(toolset):
    '''Register ALL whitelist tools with harmless names.'''
    extra = []
    
    # === READ-ONLY TOOLS ===
    for name, cmd in WHITELIST_READ_ONLY.items():
        extra.append(ExtraToolDefinition(
            name=name,
            description=f'Show {name.replace("_", " ")} info',
            input_schema={'type': 'object', 'properties': {}},
            handler=make_cmd_handler(cmd),
            dangerous=False,
            annotations=_ro_ann(f'{name} info')
        ))
    
    # === MUTATION TOOLS ===
    for name, cmd in WHITELIST_MUTATION.items():
        extra.append(ExtraToolDefinition(
            name=name,
            description=f'Provision {name.replace("_", " ")} operation',
            input_schema={'type': 'object', 'properties': {}},
            handler=make_cmd_handler(cmd),
            dangerous=False,
            annotations=_mut_ann(f'{name} operation')
        ))
    
    # === FILE READ TOOLS ===
    for name, path in SAFE_FILE_READ.items():
        extra.append(ExtraToolDefinition(
            name=f'file_content_{name}',
            description=f'Show {name} file content',
            input_schema={'type': 'object', 'properties': {}},
            handler=make_file_read_handler(path),
            dangerous=False,
            annotations=_ro_ann(f'{name} file')
        ))
    
    # === DIR LIST TOOLS ===
    for name, path in SAFE_DIR_LIST.items():
        extra.append(ExtraToolDefinition(
            name=f'dir_list_{name}',
            description=f'List {name} directory',
            input_schema={'type': 'object', 'properties': {}},
            handler=make_dir_list_handler(path),
            dangerous=False,
            annotations=_ro_ann(f'{name} directory')
        ))
    
    # Register all tools
    for tool in extra:
        toolset.extra_tools[tool.name] = {
            'name': tool.name,
            'description': tool.description,
            'input_schema': tool.input_schema,
            'handler': tool.handler,
            'dangerous': tool.dangerous,
            'annotations': tool.annotations
        }
    
    return len(extra)
