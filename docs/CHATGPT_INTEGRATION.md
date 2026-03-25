# ChatGPT Integration Guide - Final Values

## Values for ChatGPT New App Form

### NAME:
```
VPS SSH Gateway
```

### DESCRIPTION:
```
Remote MCP server for VPS management via SSH. Provides 15 tools for command execution, file management, Docker operations, systemd management, and system administration with safety safeguards for dangerous commands.
```

### MCP_SERVER_URL:
```
https://mcp.yourdomain.com/sse
```

### AUTHENTICATION:
```
OAuth
```

---

## OAuth Configuration Details

### OAUTH_NOTES:
```
- issuer: https://your-tenant.auth0.com/
- authorization_endpoint: https://your-tenant.auth0.com/authorize
- token_endpoint: https://your-tenant.auth0.com/oauth/token
- userinfo_endpoint: https://your-tenant.auth0.com/userinfo
- jwks_uri: https://your-tenant.auth0.com/.well-known/jwks.json
- scopes: openid, profile, email, offline_access
- offline_access enabled: yes
- audience: https://mcp.yourdomain.com
```

> **Note:** Replace `your-tenant.auth0.com` with your actual OAuth provider URLs.

---

## EXPOSED_TOOLS:

| # | Tool Name | Description | Requires Confirm |
|---|-----------|-------------|------------------|
| 1 | `ping_host` | Ping a host to check connectivity | No |
| 2 | `run_command` | Execute shell command on VPS | Yes* |
| 3 | `read_file` | Read file contents from VPS | No |
| 4 | `write_file` | Write content to file | Yes |
| 5 | `upload_file` | Upload file (base64 encoded) | Yes |
| 6 | `download_file` | Download file (base64 encoded) | No |
| 7 | `list_dir` | List directory contents | No |
| 8 | `systemd_status` | Get systemd service status | No |
| 9 | `systemd_restart` | Restart a systemd service | Yes |
| 10 | `journal_tail` | View systemd journal logs | No |
| 11 | `docker_ps` | List Docker containers | No |
| 12 | `docker_logs` | View Docker container logs | No |
| 13 | `docker_exec` | Execute command in container | Yes |
| 14 | `get_public_ip` | Get VPS public IP address | No |
| 15 | `get_server_facts` | Get comprehensive server info | No |

*Dangerous commands require `confirm=true` parameter.

---

## SSH_TARGET:
```
- host: <your-experimental-vps-ip>
- user: root (or configured user)
- auth method: SSH key (ed25519)
- sudo/root mode: enabled
```

---

## DEPLOYMENT_NOTES:

```
- systemd service name: mcp-server
- log path: /var/log/mcp-server/
- healthcheck URL: https://mcp.yourdomain.com/health
- readiness URL: https://mcp.yourdomain.com/ready
- config file: /opt/mcp-server/.env
- SSH key: /opt/mcp-server/secrets/ssh_key

Rollback steps:
1. systemctl stop mcp-server
2. rm -rf /opt/mcp-server
3. rm /etc/nginx/sites-enabled/mcp-server
4. systemctl reload nginx
5. userdel mcp
```

---

## SMOKE_TEST_RESULTS:

Run after deployment:
```bash
./scripts/smoke-test.sh
```

Expected results:
```
- list tools: OK
- auth flow: OK (requires valid OAuth token)
- ping_host: OK
- run_command('whoami'): OK
- run_command('uname -a'): OK
- read_file('/etc/os-release'): OK
```

---

## Quick Deployment Checklist

### On Management VPS:
1. [ ] Clone/copy project to `/opt/mcp-server`
2. [ ] Copy `.env.template` to `.env` and configure
3. [ ] Run `scripts/deploy.sh`
4. [ ] Copy SSH public key to experimental VPS
5. [ ] Configure OAuth provider
6. [ ] Run smoke tests

### On Experimental VPS:
1. [ ] Run `scripts/setup-experimental-vps.sh` with MANAGEMENT_VPS_IP
2. [ ] Add MCP server's SSH public key to authorized_keys
3. [ ] Verify SSH works from management VPS

### OAuth Provider:
1. [ ] Create application with redirect URI: `https://mcp.yourdomain.com/auth/callback`
2. [ ] Enable `offline_access` scope for refresh tokens
3. [ ] Copy client credentials to `.env`

### ChatGPT:
1. [ ] Go to Settings → Actions → Create new action
2. [ ] Enter Name, Description, MCP Server URL
3. [ ] Select OAuth authentication
4. [ ] Enter OAuth provider details
5. [ ] Test with a simple command

---

## Example Tool Calls

### ping_host
```json
{
  "name": "ping_host",
  "arguments": {
    "host": "google.com",
    "count": 3
  }
}
```

### run_command
```json
{
  "name": "run_command",
  "arguments": {
    "command": "df -h",
    "timeout": 30
  }
}
```

### Dangerous command (requires confirm)
```json
{
  "name": "run_command",
  "arguments": {
    "command": "systemctl restart nginx",
    "confirm": true
  }
}
```

### read_file
```json
{
  "name": "read_file",
  "arguments": {
    "path": "/etc/nginx/nginx.conf"
  }
}
```

### get_server_facts
```json
{
  "name": "get_server_facts",
  "arguments": {
    "include_processes": true
  }
}
```
