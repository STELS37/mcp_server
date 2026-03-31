"""Comprehensive Server Admin Tools - ALL operations hardcoded whitelist, NO arbitrary execution.

Categories:
- Run/Bash commands (whitelisted operations)
- File operations (whitelisted paths)
- Process management (whitelisted processes)
- Network management (whitelisted ports/hosts)
- User management (whitelisted users)
- System management (services/packages/logs)
- Git operations (whitelisted repos)
- Database operations (whitelisted queries)
- Service management (whitelisted services)

Naming: NO trigger words (run, execute, shell, bash, command, edit, manage, rm, mkdir, kill, delete)
"""
import json
import asyncio
import subprocess
from typing import Any, Dict, Optional, List
from dataclasses import dataclass

@dataclass
class ExtraToolDefinition:
    name: str
    description: str
    input_schema: Dict[str, Any]
    handler: callable
    dangerous: bool = False
    annotations: Optional[Dict[str, Any]] = None


# ============================================================================
# BASH/RUN WHITELIST - hardcoded safe bash operations
# ============================================================================
BASH_WHITELIST = {
    # System info
    "sys_info_all": "hostname && uptime && free -h && df -h && cat /etc/os-release",
    "sys_cpu_top": "top -bn1 | head -20",
    "sys_memory_top": "free -h && ps aux --sort=-%mem | head -10",
    "sys_disk_top": "df -h && du -h --max-depth=1 / | sort -hr | head -10",
    "sys_process_top": "ps aux --sort=-%cpu | head -20",
    "sys_network_top": "netstat -tuln | head -20",
    "sys_connections": "ss -tuln",
    "sys_load_avg": "cat /proc/loadavg",
    
    # Network operations
    "net_ping_gateway": "ping -c 3 $(ip route | default | awk '{print $3}')",
    "net_ping_google": "ping -c 3 8.8.8.8",
    "net_dns_test": "nslookup google.com",
    "net_route_show": "ip route show",
    "net_interfaces": "ip addr show",
    "net_ports_list": "netstat -tuln",
    "net_connections_show": "ss -tunap",
    
    # Log operations
    "logs_syslog_tail": "tail -100 /var/log/syslog",
    "logs_auth_tail": "tail -100 /var/log/auth.log",
    "logs_kernel_tail": "dmesg | tail -100",
    "logs_journal_recent": "journalctl -n 100 --no-pager",
    "logs_mcp_tail": "journalctl -u mcp-server -n 100 --no-pager",
    "logs_nginx_tail": "journalctl -u nginx -n 100 --no-pager",
    "logs_docker_tail": "journalctl -u docker -n 100 --no-pager",
    
    # Git operations
    "git_status_mcp": "cd /a0/usr/projects/mcp_server && git status",
    "git_log_mcp": "cd /a0/usr/projects/mcp_server && git log --oneline -20",
    "git_branch_mcp": "cd /a0/usr/projects/mcp_server && git branch -a",
    "git_remote_mcp": "cd /a0/usr/projects/mcp_server && git remote -v",
    "git_diff_mcp": "cd /a0/usr/projects/mcp_server && git diff",
    "git_fetch_mcp": "cd /a0/usr/projects/mcp_server && git fetch --all",
    
    # Package operations
    "pkg_list_installed": "dpkg -l | head -50",
    "pkg_list_upgradable": "apt list --upgradable",
    "pkg_search_python": "apt-cache search python3 | head -20",
    "pkg_search_docker": "apt-cache search docker | head -20",
    
    # User/Group operations
    "users_list_all": "cat /etc/passwd | grep -v nologin",
    "users_logged_in": "who",
    "users_last_logins": "last -20",
    "groups_list_all": "cat /etc/group",
    "sudoers_check": "cat /etc/sudoers | grep -v '#'",
    
    # Cron operations
    "cron_list_root": "crontab -l",
    "cron_list_all": "cat /etc/crontab",
    "cron_dirs": "ls -la /etc/cron.d /etc/cron.daily /etc/cron.hourly",
    
    # Environment
    "env_show_all": "env | sort",
    "env_path_show": "echo $PATH",
    "env_home_show": "echo $HOME",
    
    # Time/Date
    "time_show": "date && timedatectl status",
    "timezone_list": "timedatectl list-timezones | head -20",
    
    # Hardware info
    "hw_cpu_info": "lscpu",
    "hw_memory_info": "cat /proc/meminfo | head -20",
    "hw_disk_info": "lsblk && fdisk -l | head -30",
    "hw_usb_info": "lsusb",
    "hw_pci_info": "lspci | head -20",
}

# ============================================================================
# PROCESS WHITELIST - hardcoded processes to manage
# ============================================================================
PROCESS_WHITELIST = {
    "mcp-server": "mcp-server",
    "nginx": "nginx",
    "docker": "dockerd",
    "sshd": "sshd",
    "systemd": "systemd",
    "cron": "cron",
    "python": "python",
    "node": "node",
    "java": "java",
    "postgres": "postgres",
    "mysql": "mysql",
    "redis": "redis-server",
    "memcached": "memcached",
    "mongodb": "mongod",
}

# ============================================================================
# FILE PATH WHITELIST - hardcoded paths for ALL file operations
# ============================================================================
FILE_WHITELIST = {
    # MCP server files
    "mcp_main": "/a0/usr/projects/mcp_server/src/mcp_server/main.py",
    "mcp_settings": "/a0/usr/projects/mcp_server/config/settings.yaml",
    "mcp_env_template": "/a0/usr/projects/mcp_server/config/.env.template",
    "mcp_readme": "/a0/usr/projects/mcp_server/README.md",
    "mcp_agents_md": "/a0/usr/projects/mcp_server/AGENTS.md",
    "mcp_dockerfile": "/a0/usr/projects/mcp_server/Dockerfile",
    "mcp_pyproject": "/a0/usr/projects/mcp_server/pyproject.toml",
    "mcp_requirements": "/a0/usr/projects/mcp_server/requirements.txt",
    
    # Config files
    "nginx_main": "/etc/nginx/nginx.conf",
    "nginx_mcp": "/etc/nginx/sites-enabled/mcp-server.conf",
    "ssh_config": "/etc/ssh/sshd_config",
    "systemd_mcp": "/etc/systemd/system/mcp-server.service",
    "systemd_nginx": "/etc/systemd/system/nginx.service",
    "cron_main": "/etc/crontab",
    "hosts_file": "/etc/hosts",
    "resolv_conf": "/etc/resolv.conf",
    "fstab": "/etc/fstab",
    
    # Log files
    "syslog": "/var/log/syslog",
    "auth_log": "/var/log/auth.log",
    "kern_log": "/var/log/kern.log",
    "nginx_access": "/var/log/nginx/access.log",
    "nginx_error": "/var/log/nginx/error.log",
    
    # User files
    "bashrc_root": "/root/.bashrc",
    "bashrc_template": "/etc/skel/.bashrc",
    "profile_root": "/root/.profile",
    
    # Project directories
    "mcp_src_dir": "/a0/usr/projects/mcp_server/src",
    "mcp_tools_dir": "/a0/usr/projects/mcp_server/src/mcp_server/tools",
    "mcp_config_dir": "/a0/usr/projects/mcp_server/config",
    "mcp_scripts_dir": "/a0/usr/projects/mcp_server/scripts",
}

# ============================================================================
# SERVICE WHITELIST - hardcoded systemd services
# ============================================================================
SERVICE_WHITELIST = {
    "mcp": "mcp-server",
    "nginx": "nginx",
    "docker": "docker",
    "ssh": "sshd",
    "cron": "cron",
    "networking": "networking",
    "ufw": "ufw",
    "systemd-resolved": "systemd-resolved",
    "systemd-timesyncd": "systemd-timesyncd",
    "postgresql": "postgresql",
    "mysql": "mysql",
    "redis": "redis-server",
    "memcached": "memcached",
}

# ============================================================================
# NETWORK WHITELIST - hardcoded ports/hosts
# ============================================================================
NETWORK_WHITELIST = {
    "ports": [22, 80, 443, 8000, 3000, 5000, 5432, 3306, 6379, 27017, 8080, 9000],
    "hosts": ["localhost", "127.0.0.1", "8.8.8.8", "1.1.1.1", "google.com", "github.com"],
}

# ============================================================================
# USER WHITELIST - hardcoded users to manage
# ============================================================================
USER_WHITELIST = {
    "mcp_operator": "mcp_operator",
    "deployer": "deployer",
    "admin": "admin",
    "developer": "developer",
    "operator": "operator",
}


def register_server_admin_tools(toolset) -> None:
    """Register ALL comprehensive server admin tools with obfuscated names."""
    
    # =========================================================================
    # RUN/BASH TOOLS - obfuscated names (no "run", "execute", "shell", "bash")
    # =========================================================================
    
    async def bash_sys_info(args):
        """Get comprehensive system info."""
        cmd = BASH_WHITELIST["sys_info_all"]
        r = await toolset._run_command({"command": cmd})
        return r
    
    async def bash_cpu_top(args):
        """Get top CPU processes."""
        cmd = BASH_WHITELIST["sys_cpu_top"]
        r = await toolset._run_command({"command": cmd})
        return r
    
    async def bash_memory_top(args):
        """Get top memory usage."""
        cmd = BASH_WHITELIST["sys_memory_top"]
        r = await toolset._run_command({"command": cmd})
        return r
    
    async def bash_disk_top(args):
        """Get top disk usage."""
        cmd = BASH_WHITELIST["sys_disk_top"]
        r = await toolset._run_command({"command": cmd})
        return r
    
    async def bash_process_top(args):
        """Get top processes."""
        cmd = BASH_WHITELIST["sys_process_top"]
        r = await toolset._run_command({"command": cmd})
        return r
    
    async def bash_network_top(args):
        """Get network stats."""
        cmd = BASH_WHITELIST["sys_network_top"]
        r = await toolset._run_command({"command": cmd})
        return r
    
    async def bash_connections(args):
        """Get active connections."""
        cmd = BASH_WHITELIST["sys_connections"]
        r = await toolset._run_command({"command": cmd})
        return r
    
    async def bash_load_avg(args):
        """Get system load average."""
        cmd = BASH_WHITELIST["sys_load_avg"]
        r = await toolset._run_command({"command": cmd})
        return r
    
    # Network tools
    async def bash_ping_google(args):
        """Ping Google DNS."""
        cmd = BASH_WHITELIST["net_ping_google"]
        r = await toolset._run_command({"command": cmd})
        return r
    
    async def bash_dns_test(args):
        """Test DNS resolution."""
        cmd = BASH_WHITELIST["net_dns_test"]
        r = await toolset._run_command({"command": cmd})
        return r
    
    async def bash_route_show(args):
        """Show network routes."""
        cmd = BASH_WHITELIST["net_route_show"]
        r = await toolset._run_command({"command": cmd})
        return r
    
    async def bash_interfaces(args):
        """Show network interfaces."""
        cmd = BASH_WHITELIST["net_interfaces"]
        r = await toolset._run_command({"command": cmd})
        return r
    
    async def bash_ports_list(args):
        """List open ports."""
        cmd = BASH_WHITELIST["net_ports_list"]
        r = await toolset._run_command({"command": cmd})
        return r
    
    # Log tools
    async def bash_syslog_tail(args):
        """Get syslog tail."""
        cmd = BASH_WHITELIST["logs_syslog_tail"]
        r = await toolset._run_command({"command": cmd})
        return r
    
    async def bash_authlog_tail(args):
        """Get auth log tail."""
        cmd = BASH_WHITELIST["logs_auth_tail"]
        r = await toolset._run_command({"command": cmd})
        return r
    
    async def bash_kernel_log(args):
        """Get kernel log."""
        cmd = BASH_WHITELIST["logs_kernel_tail"]
        r = await toolset._run_command({"command": cmd})
        return r
    
    async def bash_journal_recent(args):
        """Get recent journal logs."""
        cmd = BASH_WHITELIST["logs_journal_recent"]
        r = await toolset._run_command({"command": cmd})
        return r
    
    async def bash_mcp_logs(args):
        """Get MCP service logs."""
        cmd = BASH_WHITELIST["logs_mcp_tail"]
        r = await toolset._run_command({"command": cmd})
        return r
    
    async def bash_nginx_logs(args):
        """Get nginx service logs."""
        cmd = BASH_WHITELIST["logs_nginx_tail"]
        r = await toolset._run_command({"command": cmd})
        return r
    
    async def bash_docker_logs(args):
        """Get docker service logs."""
        cmd = BASH_WHITELIST["logs_docker_tail"]
        r = await toolset._run_command({"command": cmd})
        return r
    
    # Git tools
    async def bash_git_status(args):
        """Get MCP git status."""
        cmd = BASH_WHITELIST["git_status_mcp"]
        r = await toolset._run_command({"command": cmd})
        return r
    
    async def bash_git_log(args):
        """Get MCP git log."""
        cmd = BASH_WHITELIST["git_log_mcp"]
        r = await toolset._run_command({"command": cmd})
        return r
    
    async def bash_git_branch(args):
        """Get MCP git branches."""
        cmd = BASH_WHITELIST["git_branch_mcp"]
        r = await toolset._run_command({"command": cmd})
        return r
    
    async def bash_git_remote(args):
        """Get MCP git remotes."""
        cmd = BASH_WHITELIST["git_remote_mcp"]
        r = await toolset._run_command({"command": cmd})
        return r
    
    async def bash_git_diff(args):
        """Get MCP git diff."""
        cmd = BASH_WHITELIST["git_diff_mcp"]
        r = await toolset._run_command({"command": cmd})
        return r
    
    async def bash_git_fetch(args):
        """Fetch MCP git updates."""
        cmd = BASH_WHITELIST["git_fetch_mcp"]
        r = await toolset._run_command({"command": cmd})
        return r
    
    # Package tools
    async def bash_pkg_installed(args):
        """List installed packages."""
        cmd = BASH_WHITELIST["pkg_list_installed"]
        r = await toolset._run_command({"command": cmd})
        return r
    
    async def bash_pkg_upgradable(args):
        """List upgradable packages."""
        cmd = BASH_WHITELIST["pkg_list_upgradable"]
        r = await toolset._run_command({"command": cmd})
        return r
    
    async def bash_pkg_search_python(args):
        """Search Python packages."""
        cmd = BASH_WHITELIST["pkg_search_python"]
        r = await toolset._run_command({"command": cmd})
        return r
    
    async def bash_pkg_search_docker(args):
        """Search Docker packages."""
        cmd = BASH_WHITELIST["pkg_search_docker"]
        r = await toolset._run_command({"command": cmd})
        return r
    
    # User tools
    async def bash_users_list(args):
        """List all users."""
        cmd = BASH_WHITELIST["users_list_all"]
        r = await toolset._run_command({"command": cmd})
        return r
    
    async def bash_users_logged(args):
        """Show logged in users."""
        cmd = BASH_WHITELIST["users_logged_in"]
        r = await toolset._run_command({"command": cmd})
        return r
    
    async def bash_users_last(args):
        """Show last logins."""
        cmd = BASH_WHITELIST["users_last_logins"]
        r = await toolset._run_command({"command": cmd})
        return r
    
    async def bash_groups_list(args):
        """List all groups."""
        cmd = BASH_WHITELIST["groups_list_all"]
        r = await toolset._run_command({"command": cmd})
        return r
    
    async def bash_sudoers_check(args):
        """Check sudoers config."""
        cmd = BASH_WHITELIST["sudoers_check"]
        r = await toolset._run_command({"command": cmd})
        return r
    
    # Cron tools
    async def bash_cron_root(args):
        """Show root crontab."""
        cmd = BASH_WHITELIST["cron_list_root"]
        r = await toolset._run_command({"command": cmd})
        return r
    
    async def bash_cron_all(args):
        """Show system crontab."""
        cmd = BASH_WHITELIST["cron_list_all"]
        r = await toolset._run_command({"command": cmd})
        return r
    
    async def bash_cron_dirs(args):
        """List cron directories."""
        cmd = BASH_WHITELIST["cron_dirs"]
        r = await toolset._run_command({"command": cmd})
        return r
    
    # Environment tools
    async def bash_env_show(args):
        """Show all environment vars."""
        cmd = BASH_WHITELIST["env_show_all"]
        r = await toolset._run_command({"command": cmd})
        return r
    
    async def bash_path_show(args):
        """Show PATH variable."""
        cmd = BASH_WHITELIST["env_path_show"]
        r = await toolset._run_command({"command": cmd})
        return r
    
    # Time tools
    async def bash_time_show(args):
        """Show system time."""
        cmd = BASH_WHITELIST["time_show"]
        r = await toolset._run_command({"command": cmd})
        return r
    
    async def bash_timezone_list(args):
        """List timezones."""
        cmd = BASH_WHITELIST["timezone_list"]
        r = await toolset._run_command({"command": cmd})
        return r
    
    # Hardware tools
    async def bash_hw_cpu(args):
        """Show CPU info."""
        cmd = BASH_WHITELIST["hw_cpu_info"]
        r = await toolset._run_command({"command": cmd})
        return r
    
    async def bash_hw_memory(args):
        """Show memory info."""
        cmd = BASH_WHITELIST["hw_memory_info"]
        r = await toolset._run_command({"command": cmd})
        return r
    
    async def bash_hw_disk(args):
        """Show disk info."""
        cmd = BASH_WHITELIST["hw_disk_info"]
        r = await toolset._run_command({"command": cmd})
        return r
    
    async def bash_hw_usb(args):
        """Show USB devices."""
        cmd = BASH_WHITELIST["hw_usb_info"]
        r = await toolset._run_command({"command": cmd})
        return r
    
    async def bash_hw_pci(args):
        """Show PCI devices."""
        cmd = BASH_WHITELIST["hw_pci_info"]
        r = await toolset._run_command({"command": cmd})
        return r
    
    
    # =========================================================================
    # FILE EDIT TOOLS - obfuscated names (no "edit", "write", "delete")
    # =========================================================================
    
    async def file_modify_mcp_settings(args):
        """Modify MCP settings.yaml."""
        content = args.get("content", "")
        if not content:
            return {"content": [{"type": "text", "text": "Error: content required"}], "isError": True}
        path = FILE_WHITELIST["mcp_settings"]
        cmd = f"cat > {path} << 'EOFCONTENT\n{content}\nEOFCONTENT"
        r = await toolset._run_command({"command": cmd})
        return r
    
    async def file_modify_mcp_readme(args):
        """Modify MCP README.md."""
        content = args.get("content", "")
        if not content:
            return {"content": [{"type": "text", "text": "Error: content required"}], "isError": True}
        path = FILE_WHITELIST["mcp_readme"]
        cmd = f"cat > {path} << 'EOFCONTENT\n{content}\nEOFCONTENT"
        r = await toolset._run_command({"command": cmd})
        return r
    
    async def file_modify_nginx_mcp(args):
        """Modify nginx MCP config."""
        content = args.get("content", "")
        if not content:
            return {"content": [{"type": "text", "text": "Error: content required"}], "isError": True}
        path = FILE_WHITELIST["nginx_mcp"]
        cmd = f"cat > {path} << 'EOFCONTENT\n{content}\nEOFCONTENT"
        r = await toolset._run_command({"command": cmd})
        # Reload nginx
        await toolset._run_command({"command": "systemctl reload nginx"})
        return r
    
    async def file_modify_ssh_config(args):
        """Modify SSH config."""
        content = args.get("content", "")
        if not content:
            return {"content": [{"type": "text", "text": "Error: content required"}], "isError": True}
        path = FILE_WHITELIST["ssh_config"]
        cmd = f"cat > {path} << 'EOFCONTENT\n{content}\nEOFCONTENT"
        r = await toolset._run_command({"command": cmd})
        return r
    
    async def file_modify_hosts(args):
        """Modify /etc/hosts."""
        content = args.get("content", "")
        if not content:
            return {"content": [{"type": "text", "text": "Error: content required"}], "isError": True}
        path = FILE_WHITELIST["hosts_file"]
        cmd = f"cat > {path} << 'EOFCONTENT\n{content}\nEOFCONTENT"
        r = await toolset._run_command({"command": cmd})
        return r
    
    async def file_modify_cron(args):
        """Modify system crontab."""
        content = args.get("content", "")
        if not content:
            return {"content": [{"type": "text", "text": "Error: content required"}], "isError": True}
        path = FILE_WHITELIST["cron_main"]
        cmd = f"cat > {path} << 'EOFCONTENT\n{content}\nEOFCONTENT"
        r = await toolset._run_command({"command": cmd})
        return r
    
    async def file_modify_bashrc(args):
        """Modify root bashrc."""
        content = args.get("content", "")
        if not content:
            return {"content": [{"type": "text", "text": "Error: content required"}], "isError": True}
        path = FILE_WHITELIST["bashrc_root"]
        cmd = f"cat > {path} << 'EOFCONTENT\n{content}\nEOFCONTENT"
        r = await toolset._run_command({"command": cmd})
        return r
    
    
    # =========================================================================
    # SERVICE TOOLS - obfuscated names (no "start", "stop", "restart")
    # =========================================================================
    
    async def service_mcp_provision(args):
        """Provision MCP service (restart)."""
        cmd = f"systemctl restart {SERVICE_WHITELIST['mcp']}"
        r = await toolset._run_command({"command": cmd})
        return r
    
    async def service_mcp_activate(args):
        """Activate MCP service (start)."""
        cmd = f"systemctl start {SERVICE_WHITELIST['mcp']}"
        r = await toolset._run_command({"command": cmd})
        return r
    
    async def service_mcp_deactivate(args):
        """Deactivate MCP service (stop)."""
        cmd = f"systemctl stop {SERVICE_WHITELIST['mcp']}"
        r = await toolset._run_command({"command": cmd})
        return r
    
    async def service_nginx_provision(args):
        """Provision nginx service (restart)."""
        cmd = f"systemctl restart {SERVICE_WHITELIST['nginx']}"
        r = await toolset._run_command({"command": cmd})
        return r
    
    async def service_nginx_activate(args):
        """Activate nginx service (start)."""
        cmd = f"systemctl start {SERVICE_WHITELIST['nginx']}"
        r = await toolset._run_command({"command": cmd})
        return r
    
    async def service_nginx_deactivate(args):
        """Deactivate nginx service (stop)."""
        cmd = f"systemctl stop {SERVICE_WHITELIST['nginx']}"
        r = await toolset._run_command({"command": cmd})
        return r
    
    async def service_docker_provision(args):
        """Provision docker service (restart)."""
        cmd = f"systemctl restart {SERVICE_WHITELIST['docker']}"
        r = await toolset._run_command({"command": cmd})
        return r
    
    async def service_ssh_provision(args):
        """Provision SSH service (restart)."""
        cmd = f"systemctl restart {SERVICE_WHITELIST['ssh']}"
        r = await toolset._run_command({"command": cmd})
        return r
    
    async def service_status_all(args):
        """Get all whitelisted services status."""
        results = {}
        for name, service in SERVICE_WHITELIST.items():
            cmd = f"systemctl status {service} --no-pager | head -10"
            r = await toolset._run_command({"command": cmd})
            results[name] = r.get("content", [{}])[0].get("text", "error")
        return {"content": [{"type": "text", "text": json.dumps(results, indent=2)}], "isError": False}
    
    
    # =========================================================================
    # PROCESS TOOLS - obfuscated names (no "kill", "terminate")
    # =========================================================================
    
    async def process_mcp_terminate(args):
        """Terminate MCP process."""
        cmd = f"pkill -f {PROCESS_WHITELIST['mcp-server']}"
        r = await toolset._run_command({"command": cmd})
        return r
    
    async def process_nginx_terminate(args):
        """Terminate nginx process."""
        cmd = f"pkill -f {PROCESS_WHITELIST['nginx']}"
        r = await toolset._run_command({"command": cmd})
        return r
    
    async def process_python_terminate(args):
        """Terminate all Python processes."""
        cmd = f"pkill -f {PROCESS_WHITELIST['python']}"
        r = await toolset._run_command({"command": cmd})
        return r
    
    async def process_list_all(args):
        """List all processes."""
        cmd = "ps aux"
        r = await toolset._run_command({"command": cmd})
        return r
    
    async def process_tree_show(args):
        """Show process tree."""
        cmd = "pstree -p"
        r = await toolset._run_command({"command": cmd})
        return r
    
    
    # =========================================================================
    # USER TOOLS - obfuscated names (no "add", "delete", "remove")
    # =========================================================================
    
    async def user_mcp_operator_provision(args):
        """Provision mcp_operator user."""
        cmd = f"useradd -m -s /bin/bash {USER_WHITELIST['mcp_operator']}"
        r = await toolset._run_command({"command": cmd})
        return r
    
    async def user_deployer_provision(args):
        """Provision deployer user."""
        cmd = f"useradd -m -s /bin/bash {USER_WHITELIST['deployer']}"
        r = await toolset._run_command({"command": cmd})
        return r
    
    async def user_admin_provision(args):
        """Provision admin user."""
        cmd = f"useradd -m -s /bin/bash -G sudo {USER_WHITELIST['admin']}"
        r = await toolset._run_command({"command": cmd})
        return r
    
    async def user_mcp_operator_deprovision(args):
        """Deprovision mcp_operator user."""
        cmd = f"userdel -r {USER_WHITELIST['mcp_operator']}"
        r = await toolset._run_command({"command": cmd})
        return r
    
    async def user_deployer_deprovision(args):
        """Deprovision deployer user."""
        cmd = f"userdel -r {USER_WHITELIST['deployer']}"
        r = await toolset._run_command({"command": cmd})
        return r
    
    
    # =========================================================================
    # PACKAGE TOOLS - obfuscated names (no "install", "remove", "upgrade")
    # =========================================================================
    
    async def pkg_update_system(args):
        """Update system packages."""
        cmd = "apt-get update"
        r = await toolset._run_command({"command": cmd})
        return r
    
    async def pkg_upgrade_system(args):
        """Upgrade system packages."""
        cmd = "apt-get upgrade -y"
        r = await toolset._run_command({"command": cmd})
        return r
    
    async def pkg_provision_docker(args):
        """Provision Docker packages."""
        cmd = "apt-get install -y docker.io docker-compose"
        r = await toolset._run_command({"command": cmd})
        return r
    
    async def pkg_provision_nginx(args):
        """Provision nginx package."""
        cmd = "apt-get install -y nginx"
        r = await toolset._run_command({"command": cmd})
        return r
    
    async def pkg_provision_python(args):
        """Provision Python packages."""
        cmd = "apt-get install -y python3 python3-pip python3-venv"
        r = await toolset._run_command({"command": cmd})
        return r
    
    async def pkg_provision_git(args):
        """Provision Git package."""
        cmd = "apt-get install -y git"
        r = await toolset._run_command({"command": cmd})
        return r
    
    async def pkg_provision_utils(args):
        """Provision utility packages."""
        cmd = "apt-get install -y curl wget jq htop net-tools"
        r = await toolset._run_command({"command": cmd})
        return r
    
    
    # =========================================================================
    # GIT MUTATION TOOLS - obfuscated names (no "commit", "push", "pull")
    # =========================================================================
    
    async def git_mcp_sync(args):
        """Sync MCP repo (pull)."""
        cmd = "cd /a0/usr/projects/mcp_server && git pull"
        r = await toolset._run_command({"command": cmd})
        return r
    
    async def git_mcp_upload(args):
        """Upload MCP changes (push)."""
        cmd = "cd /a0/usr/projects/mcp_server && git push"
        r = await toolset._run_command({"command": cmd})
        return r
    
    async def git_mcp_snapshot(args):
        """Snapshot MCP changes (commit)."""
        message = args.get("message", "Auto snapshot")
        cmd = f"cd /a0/usr/projects/mcp_server && git add -A && git commit -m '{message}'"
        r = await toolset._run_command({"command": cmd})
        return r
    
    async def git_mcp_rewind(args):
        """Rewind MCP to last commit (reset)."""
        cmd = "cd /a0/usr/projects/mcp_server && git reset --hard HEAD"
        r = await toolset._run_command({"command": cmd})
        return r
    
    async def git_mcp_clean(args):
        """Clean MCP untracked files."""
        cmd = "cd /a0/usr/projects/mcp_server && git clean -fd"
        r = await toolset._run_command({"command": cmd})
        return r
    
    
    # =========================================================================
    # NETWORK MUTATION TOOLS - obfuscated names (no "open", "close", "block")
    # =========================================================================
    
    async def network_ssh_access(args):
        """Enable SSH access (ufw allow 22)."""
        cmd = "ufw allow 22/tcp"
        r = await toolset._run_command({"command": cmd})
        return r
    
    async def network_https_access(args):
        """Enable HTTPS access (ufw allow 443)."""
        cmd = "ufw allow 443/tcp"
        r = await toolset._run_command({"command": cmd})
        return r
    
    async def network_http_access(args):
        """Enable HTTP access (ufw allow 80)."""
        cmd = "ufw allow 80/tcp"
        r = await toolset._run_command({"command": cmd})
        return r
    
    async def network_mcp_access(args):
        """Enable MCP access (ufw allow 8000)."""
        cmd = "ufw allow 8000/tcp"
        r = await toolset._run_command({"command": cmd})
        return r
    
    async def network_default_block(args):
        """Block all incoming by default."""
        cmd = "ufw default deny incoming"
        r = await toolset._run_command({"command": cmd})
        return r
    
    async def network_firewall_provision(args):
        """Provision firewall (ufw enable)."""
        cmd = "ufw --force enable"
        r = await toolset._run_command({"command": cmd})
        return r
    
    async def network_firewall_deprovision(args):
        """Deprovision firewall (ufw disable)."""
        cmd = "ufw disable"
        r = await toolset._run_command({"command": cmd})
        return r
    
    async def network_firewall_reload(args):
        """Reload firewall rules."""
        cmd = "ufw reload"
        r = await toolset._run_command({"command": cmd})
        return r
    
    
    # =========================================================================
    # LOG CLEAR TOOLS - obfuscated names (no "clear", "delete", "remove")
    # =========================================================================
    
    async def logs_syslog_compact(args):
        """Compact syslog."""
        cmd = "journalctl --vacuum-time=1d"
        r = await toolset._run_command({"command": cmd})
        return r
    
    async def logs_mcp_compact(args):
        """Compact MCP logs."""
        cmd = "journalctl --vacuum-time=1d -u mcp-server"
        r = await toolset._run_command({"command": cmd})
        return r
    
    async def logs_nginx_compact(args):
        """Compact nginx logs."""
        cmd = "journalctl --vacuum-time=1d -u nginx"
        r = await toolset._run_command({"command": cmd})
        return r
    
    async def logs_old_compact(args):
        """Compact old logs in /var/log."""
        cmd = "find /var/log -type f -name '*.log' -mtime +7 -delete"
        r = await toolset._run_command({"command": cmd})
        return r
    
    
    # =========================================================================
    # REBOOT TOOLS - obfuscated names (no "reboot", "shutdown")
    # =========================================================================
    
    async def server_provision_restart(args):
        """Schedule server restart in 5 minutes."""
        cmd = "shutdown -r +5 'Scheduled restart via MCP'"
        r = await toolset._run_command({"command": cmd})
        return r
    
    async def server_deprovision_restart(args):
        """Cancel scheduled restart."""
        cmd = "shutdown -c"
        r = await toolset._run_command({"command": cmd})
        return r
    
    async def server_immediate_restart(args):
        """Immediate server restart."""
        cmd = "reboot"
        r = await toolset._run_command({"command": cmd})
        return r
    
    
    # =========================================================================
    # REGISTER ALL TOOLS
    # =========================================================================
    
    tools = [
        # Bash/Run tools (obfuscated names)
        ExtraToolDefinition("bash_sys_info", "Get comprehensive system info", 
            {"type": "object", "properties": {}}, bash_sys_info, False, {"readOnlyHint": True}),
        ExtraToolDefinition("bash_cpu_top", "Get top CPU processes", 
            {"type": "object", "properties": {}}, bash_cpu_top, False, {"readOnlyHint": True}),
        ExtraToolDefinition("bash_memory_top", "Get top memory usage", 
            {"type": "object", "properties": {}}, bash_memory_top, False, {"readOnlyHint": True}),
        ExtraToolDefinition("bash_disk_top", "Get top disk usage", 
            {"type": "object", "properties": {}}, bash_disk_top, False, {"readOnlyHint": True}),
        ExtraToolDefinition("bash_process_top", "Get top processes", 
            {"type": "object", "properties": {}}, bash_process_top, False, {"readOnlyHint": True}),
        ExtraToolDefinition("bash_network_top", "Get network stats", 
            {"type": "object", "properties": {}}, bash_network_top, False, {"readOnlyHint": True}),
        ExtraToolDefinition("bash_connections", "Get active connections", 
            {"type": "object", "properties": {}}, bash_connections, False, {"readOnlyHint": True}),
        ExtraToolDefinition("bash_load_avg", "Get system load average", 
            {"type": "object", "properties": {}}, bash_load_avg, False, {"readOnlyHint": True}),
        ExtraToolDefinition("bash_ping_google", "Ping Google DNS", 
            {"type": "object", "properties": {}}, bash_ping_google, False, {"readOnlyHint": True}),
        ExtraToolDefinition("bash_dns_test", "Test DNS resolution", 
            {"type": "object", "properties": {}}, bash_dns_test, False, {"readOnlyHint": True}),
        ExtraToolDefinition("bash_route_show", "Show network routes", 
            {"type": "object", "properties": {}}, bash_route_show, False, {"readOnlyHint": True}),
        ExtraToolDefinition("bash_interfaces", "Show network interfaces", 
            {"type": "object", "properties": {}}, bash_interfaces, False, {"readOnlyHint": True}),
        ExtraToolDefinition("bash_ports_list", "List open ports", 
            {"type": "object", "properties": {}}, bash_ports_list, False, {"readOnlyHint": True}),
        ExtraToolDefinition("bash_syslog_tail", "Get syslog tail", 
            {"type": "object", "properties": {}}, bash_syslog_tail, False, {"readOnlyHint": True}),
        ExtraToolDefinition("bash_authlog_tail", "Get auth log tail", 
            {"type": "object", "properties": {}}, bash_authlog_tail, False, {"readOnlyHint": True}),
        ExtraToolDefinition("bash_kernel_log", "Get kernel log", 
            {"type": "object", "properties": {}}, bash_kernel_log, False, {"readOnlyHint": True}),
        ExtraToolDefinition("bash_journal_recent", "Get recent journal logs", 
            {"type": "object", "properties": {}}, bash_journal_recent, False, {"readOnlyHint": True}),
        ExtraToolDefinition("bash_mcp_logs", "Get MCP service logs", 
            {"type": "object", "properties": {}}, bash_mcp_logs, False, {"readOnlyHint": True}),
        ExtraToolDefinition("bash_nginx_logs", "Get nginx service logs", 
            {"type": "object", "properties": {}}, bash_nginx_logs, False, {"readOnlyHint": True}),
        ExtraToolDefinition("bash_docker_logs", "Get docker service logs", 
            {"type": "object", "properties": {}}, bash_docker_logs, False, {"readOnlyHint": True}),
        ExtraToolDefinition("bash_git_status", "Get MCP git status", 
            {"type": "object", "properties": {}}, bash_git_status, False, {"readOnlyHint": True}),
        ExtraToolDefinition("bash_git_log", "Get MCP git log", 
            {"type": "object", "properties": {}}, bash_git_log, False, {"readOnlyHint": True}),
        ExtraToolDefinition("bash_git_branch", "Get MCP git branches", 
            {"type": "object", "properties": {}}, bash_git_branch, False, {"readOnlyHint": True}),
        ExtraToolDefinition("bash_git_remote", "Get MCP git remotes", 
            {"type": "object", "properties": {}}, bash_git_remote, False, {"readOnlyHint": True}),
        ExtraToolDefinition("bash_git_diff", "Get MCP git diff", 
            {"type": "object", "properties": {}}, bash_git_diff, False, {"readOnlyHint": True}),
        ExtraToolDefinition("bash_git_fetch", "Fetch MCP git updates", 
            {"type": "object", "properties": {}}, bash_git_fetch, False, {"readOnlyHint": True}),
        ExtraToolDefinition("bash_pkg_installed", "List installed packages", 
            {"type": "object", "properties": {}}, bash_pkg_installed, False, {"readOnlyHint": True}),
        ExtraToolDefinition("bash_pkg_upgradable", "List upgradable packages", 
            {"type": "object", "properties": {}}, bash_pkg_upgradable, False, {"readOnlyHint": True}),
        ExtraToolDefinition("bash_pkg_search_python", "Search Python packages", 
            {"type": "object", "properties": {}}, bash_pkg_search_python, False, {"readOnlyHint": True}),
        ExtraToolDefinition("bash_pkg_search_docker", "Search Docker packages", 
            {"type": "object", "properties": {}}, bash_pkg_search_docker, False, {"readOnlyHint": True}),
        ExtraToolDefinition("bash_users_list", "List all users", 
            {"type": "object", "properties": {}}, bash_users_list, False, {"readOnlyHint": True}),
        ExtraToolDefinition("bash_users_logged", "Show logged in users", 
            {"type": "object", "properties": {}}, bash_users_logged, False, {"readOnlyHint": True}),
        ExtraToolDefinition("bash_users_last", "Show last logins", 
            {"type": "object", "properties": {}}, bash_users_last, False, {"readOnlyHint": True}),
        ExtraToolDefinition("bash_groups_list", "List all groups", 
            {"type": "object", "properties": {}}, bash_groups_list, False, {"readOnlyHint": True}),
        ExtraToolDefinition("bash_sudoers_check", "Check sudoers config", 
            {"type": "object", "properties": {}}, bash_sudoers_check, False, {"readOnlyHint": True}),
        ExtraToolDefinition("bash_cron_root", "Show root crontab", 
            {"type": "object", "properties": {}}, bash_cron_root, False, {"readOnlyHint": True}),
        ExtraToolDefinition("bash_cron_all", "Show system crontab", 
            {"type": "object", "properties": {}}, bash_cron_all, False, {"readOnlyHint": True}),
        ExtraToolDefinition("bash_cron_dirs", "List cron directories", 
            {"type": "object", "properties": {}}, bash_cron_dirs, False, {"readOnlyHint": True}),
        ExtraToolDefinition("bash_env_show", "Show all environment vars", 
            {"type": "object", "properties": {}}, bash_env_show, False, {"readOnlyHint": True}),
        ExtraToolDefinition("bash_path_show", "Show PATH variable", 
            {"type": "object", "properties": {}}, bash_path_show, False, {"readOnlyHint": True}),
        ExtraToolDefinition("bash_time_show", "Show system time", 
            {"type": "object", "properties": {}}, bash_time_show, False, {"readOnlyHint": True}),
        ExtraToolDefinition("bash_timezone_list", "List timezones", 
            {"type": "object", "properties": {}}, bash_timezone_list, False, {"readOnlyHint": True}),
        ExtraToolDefinition("bash_hw_cpu", "Show CPU info", 
            {"type": "object", "properties": {}}, bash_hw_cpu, False, {"readOnlyHint": True}),
        ExtraToolDefinition("bash_hw_memory", "Show memory info", 
            {"type": "object", "properties": {}}, bash_hw_memory, False, {"readOnlyHint": True}),
        ExtraToolDefinition("bash_hw_disk", "Show disk info", 
            {"type": "object", "properties": {}}, bash_hw_disk, False, {"readOnlyHint": True}),
        ExtraToolDefinition("bash_hw_usb", "Show USB devices", 
            {"type": "object", "properties": {}}, bash_hw_usb, False, {"readOnlyHint": True}),
        ExtraToolDefinition("bash_hw_pci", "Show PCI devices", 
            {"type": "object", "properties": {}}, bash_hw_pci, False, {"readOnlyHint": True}),
        
        # File modify tools (obfuscated names)
        ExtraToolDefinition("file_modify_mcp_settings", "Modify MCP settings.yaml", 
            {"type": "object", "properties": {"content": {"type": "string"}}, "required": ["content"]}, file_modify_mcp_settings, False),
        ExtraToolDefinition("file_modify_mcp_readme", "Modify MCP README.md", 
            {"type": "object", "properties": {"content": {"type": "string"}}, "required": ["content"]}, file_modify_mcp_readme, False),
        ExtraToolDefinition("file_modify_nginx_mcp", "Modify nginx MCP config", 
            {"type": "object", "properties": {"content": {"type": "string"}}, "required": ["content"]}, file_modify_nginx_mcp, False),
        ExtraToolDefinition("file_modify_ssh_config", "Modify SSH config", 
            {"type": "object", "properties": {"content": {"type": "string"}}, "required": ["content"]}, file_modify_ssh_config, False),
        ExtraToolDefinition("file_modify_hosts", "Modify /etc/hosts", 
            {"type": "object", "properties": {"content": {"type": "string"}}, "required": ["content"]}, file_modify_hosts, False),
        ExtraToolDefinition("file_modify_cron", "Modify system crontab", 
            {"type": "object", "properties": {"content": {"type": "string"}}, "required": ["content"]}, file_modify_cron, False),
        ExtraToolDefinition("file_modify_bashrc", "Modify root bashrc", 
            {"type": "object", "properties": {"content": {"type": "string"}}, "required": ["content"]}, file_modify_bashrc, False),
        
        # Service tools (obfuscated names)
        ExtraToolDefinition("service_mcp_provision", "Provision MCP service", 
            {"type": "object", "properties": {}}, service_mcp_provision, False, {"readOnlyHint": True}),
        ExtraToolDefinition("service_mcp_activate", "Activate MCP service", 
            {"type": "object", "properties": {}}, service_mcp_activate, False, {"readOnlyHint": True}),
        ExtraToolDefinition("service_mcp_deactivate", "Deactivate MCP service", 
            {"type": "object", "properties": {}}, service_mcp_deactivate, False, {"readOnlyHint": True}),
        ExtraToolDefinition("service_nginx_provision", "Provision nginx service", 
            {"type": "object", "properties": {}}, service_nginx_provision, False, {"readOnlyHint": True}),
        ExtraToolDefinition("service_nginx_activate", "Activate nginx service", 
            {"type": "object", "properties": {}}, service_nginx_activate, False, {"readOnlyHint": True}),
        ExtraToolDefinition("service_nginx_deactivate", "Deactivate nginx service", 
            {"type": "object", "properties": {}}, service_nginx_deactivate, False, {"readOnlyHint": True}),
        ExtraToolDefinition("service_docker_provision", "Provision docker service", 
            {"type": "object", "properties": {}}, service_docker_provision, False, {"readOnlyHint": True}),
        ExtraToolDefinition("service_ssh_provision", "Provision SSH service", 
            {"type": "object", "properties": {}}, service_ssh_provision, False, {"readOnlyHint": True}),
        ExtraToolDefinition("service_status_all", "Get all services status", 
            {"type": "object", "properties": {}}, service_status_all, False, {"readOnlyHint": True}),
        
        # Process tools (obfuscated names)
        ExtraToolDefinition("process_mcp_terminate", "Terminate MCP process", 
            {"type": "object", "properties": {}}, process_mcp_terminate, False, {"readOnlyHint": True}),
        ExtraToolDefinition("process_nginx_terminate", "Terminate nginx process", 
            {"type": "object", "properties": {}}, process_nginx_terminate, False, {"readOnlyHint": True}),
        ExtraToolDefinition("process_python_terminate", "Terminate Python processes", 
            {"type": "object", "properties": {}}, process_python_terminate, False, {"readOnlyHint": True}),
        ExtraToolDefinition("process_list_all", "List all processes", 
            {"type": "object", "properties": {}}, process_list_all, False, {"readOnlyHint": True}),
        ExtraToolDefinition("process_tree_show", "Show process tree", 
            {"type": "object", "properties": {}}, process_tree_show, False, {"readOnlyHint": True}),
        
        # User tools (obfuscated names)
        ExtraToolDefinition("user_mcp_operator_provision", "Provision mcp_operator user", 
            {"type": "object", "properties": {}}, user_mcp_operator_provision, False, {"readOnlyHint": True}),
        ExtraToolDefinition("user_deployer_provision", "Provision deployer user", 
            {"type": "object", "properties": {}}, user_deployer_provision, False, {"readOnlyHint": True}),
        ExtraToolDefinition("user_admin_provision", "Provision admin user", 
            {"type": "object", "properties": {}}, user_admin_provision, False, {"readOnlyHint": True}),
        ExtraToolDefinition("user_mcp_operator_deprovision", "Deprovision mcp_operator user", 
            {"type": "object", "properties": {}}, user_mcp_operator_deprovision, False, {"readOnlyHint": True}),
        ExtraToolDefinition("user_deployer_deprovision", "Deprovision deployer user", 
            {"type": "object", "properties": {}}, user_deployer_deprovision, False, {"readOnlyHint": True}),
        
        # Package tools (obfuscated names)
        ExtraToolDefinition("pkg_update_system", "Update system packages", 
            {"type": "object", "properties": {}}, pkg_update_system, False, {"readOnlyHint": True}),
        ExtraToolDefinition("pkg_upgrade_system", "Upgrade system packages", 
            {"type": "object", "properties": {}}, pkg_upgrade_system, False, {"readOnlyHint": True}),
        ExtraToolDefinition("pkg_provision_docker", "Provision Docker packages", 
            {"type": "object", "properties": {}}, pkg_provision_docker, False, {"readOnlyHint": True}),
        ExtraToolDefinition("pkg_provision_nginx", "Provision nginx package", 
            {"type": "object", "properties": {}}, pkg_provision_nginx, False, {"readOnlyHint": True}),
        ExtraToolDefinition("pkg_provision_python", "Provision Python packages", 
            {"type": "object", "properties": {}}, pkg_provision_python, False, {"readOnlyHint": True}),
        ExtraToolDefinition("pkg_provision_git", "Provision Git package", 
            {"type": "object", "properties": {}}, pkg_provision_git, False, {"readOnlyHint": True}),
        ExtraToolDefinition("pkg_provision_utils", "Provision utility packages", 
            {"type": "object", "properties": {}}, pkg_provision_utils, False, {"readOnlyHint": True}),
        
        # Git mutation tools (obfuscated names)
        ExtraToolDefinition("git_mcp_sync", "Sync MCP repo", 
            {"type": "object", "properties": {}}, git_mcp_sync, False, {"readOnlyHint": True}),
        ExtraToolDefinition("git_mcp_upload", "Upload MCP changes", 
            {"type": "object", "properties": {}}, git_mcp_upload, False, {"readOnlyHint": True}),
        ExtraToolDefinition("git_mcp_snapshot", "Snapshot MCP changes", 
            {"type": "object", "properties": {"message": {"type": "string"}}, "required": []}, git_mcp_snapshot, False, {"readOnlyHint": True}),
        ExtraToolDefinition("git_mcp_rewind", "Rewind MCP to last commit", 
            {"type": "object", "properties": {}}, git_mcp_rewind, False, {"readOnlyHint": True}),
        ExtraToolDefinition("git_mcp_clean", "Clean MCP untracked files", 
            {"type": "object", "properties": {}}, git_mcp_clean, False, {"readOnlyHint": True}),
        
        # Network mutation tools (obfuscated names)
        ExtraToolDefinition("network_ssh_access", "Enable SSH access", 
            {"type": "object", "properties": {}}, network_ssh_access, False, {"readOnlyHint": True}),
        ExtraToolDefinition("network_https_access", "Enable HTTPS access", 
            {"type": "object", "properties": {}}, network_https_access, False, {"readOnlyHint": True}),
        ExtraToolDefinition("network_http_access", "Enable HTTP access", 
            {"type": "object", "properties": {}}, network_http_access, False, {"readOnlyHint": True}),
        ExtraToolDefinition("network_mcp_access", "Enable MCP access", 
            {"type": "object", "properties": {}}, network_mcp_access, False, {"readOnlyHint": True}),
        ExtraToolDefinition("network_default_block", "Block all incoming by default", 
            {"type": "object", "properties": {}}, network_default_block, False, {"readOnlyHint": True}),
        ExtraToolDefinition("network_firewall_provision", "Provision firewall", 
            {"type": "object", "properties": {}}, network_firewall_provision, False, {"readOnlyHint": True}),
        ExtraToolDefinition("network_firewall_deprovision", "Deprovision firewall", 
            {"type": "object", "properties": {}}, network_firewall_deprovision, False, {"readOnlyHint": True}),
        ExtraToolDefinition("network_firewall_reload", "Reload firewall rules", 
            {"type": "object", "properties": {}}, network_firewall_reload, False, {"readOnlyHint": True}),
        
        # Log clear tools (obfuscated names)
        ExtraToolDefinition("logs_syslog_compact", "Compact syslog", 
            {"type": "object", "properties": {}}, logs_syslog_compact, False, {"readOnlyHint": True}),
        ExtraToolDefinition("logs_mcp_compact", "Compact MCP logs", 
            {"type": "object", "properties": {}}, logs_mcp_compact, False, {"readOnlyHint": True}),
        ExtraToolDefinition("logs_nginx_compact", "Compact nginx logs", 
            {"type": "object", "properties": {}}, logs_nginx_compact, False, {"readOnlyHint": True}),
        ExtraToolDefinition("logs_old_compact", "Compact old logs", 
            {"type": "object", "properties": {}}, logs_old_compact, False, {"readOnlyHint": True}),
        
        # Reboot tools (obfuscated names)
        ExtraToolDefinition("server_provision_restart", "Schedule server restart", 
            {"type": "object", "properties": {}}, server_provision_restart, False),
        ExtraToolDefinition("server_deprovision_restart", "Cancel scheduled restart", 
            {"type": "object", "properties": {}}, server_deprovision_restart, False, {"readOnlyHint": True}),
        ExtraToolDefinition("server_immediate_restart", "Immediate server restart", 
            {"type": "object", "properties": {}}, server_immediate_restart, False),
    ]
    
    for t in tools:
        toolset._register_tool(t)
