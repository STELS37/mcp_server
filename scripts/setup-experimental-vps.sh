#!/bin/bash
# Setup script for Experimental VPS
# Run on the Experimental VPS to secure it and allow SSH only from Management VPS

set -e

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

log_info() { echo -e "${GREEN}[INFO]${NC} $1"; }
log_warn() { echo -e "${YELLOW}[WARN]${NC} $1"; }
log_error() { echo -e "${RED}[ERROR]${NC} $1"; }

# Configuration
MANAGEMENT_VPS_IP="${MANAGEMENT_VPS_IP:-}"
SSH_USER="${SSH_USER:-root}"

if [ -z "$MANAGEMENT_VPS_IP" ]; then
    log_error "Please set MANAGEMENT_VPS_IP environment variable"
    exit 1
fi

log_info "Securing Experimental VPS..."
log_info "Management VPS IP: $MANAGEMENT_VPS_IP"

# 1. Update system
log_info "Updating system packages..."
apt-get update
apt-get upgrade -y

# 2. Create mcp user (optional, for non-root access)
log_info "Creating mcp user..."
if ! id -u mcp &>/dev/null; then
    useradd -m -s /bin/bash mcp
    log_warn "Created user 'mcp'. Set password with: passwd mcp"
fi

# 3. Configure SSH
log_info "Configuring SSH..."
SSH_CONFIG="/etc/ssh/sshd_config"

# Backup original config
cp $SSH_CONFIG ${SSH_CONFIG}.backup

# Create SSH config for management VPS access only
cat > /etc/ssh/sshd_config.d/99-mcp-restrict.conf << SSHCONF
# MCP Server SSH Access Configuration
# Only allow SSH from Management VPS

# Listen on default port
Port 22

# Disable password authentication (key only)
PasswordAuthentication no
PubkeyAuthentication yes

# Disable root login with password
PermitRootLogin prohibit-password

# Allow the MCP user and root
AllowUsers root mcp@$MANAGEMENT_VPS_IP mcp

# Allow TCP forwarding for tunnels (if needed)
AllowTcpForwarding yes

# Max auth tries
MaxAuthTries 3

# Disable empty passwords
PermitEmptyPasswords no

# Strict modes
StrictModes yes
SSHCONF

log_info "SSH configured to accept connections from Management VPS only"

# 4. Configure UFW firewall
log_info "Configuring UFW firewall..."

# Reset UFW
ufw --force reset

# Default policies
ufw default deny incoming
ufw default allow outgoing

# Allow SSH only from Management VPS
ufw allow from $MANAGEMENT_VPS_IP to any port 22 comment 'MCP Management VPS SSH'

# Allow existing connections
ufw allow out established

# Enable UFW
ufw --force enable

log_info "UFW configured. Status:"
ufw status

# 5. Restart SSH
log_info "Restarting SSH service..."
systemctl restart sshd

# 6. Show authorized_keys location
log_info "SSH setup complete!"
echo ""
echo "========================================="
echo "Experimental VPS Setup Complete"
echo "========================================="
echo "Firewall: UFW enabled"
echo "SSH: Key-based auth only"
echo "Allowed IPs: $MANAGEMENT_VPS_IP"
echo ""
echo "Add the MCP server's public key to:"
if [ "$SSH_USER" = "root" ]; then
    echo "  /root/.ssh/authorized_keys"
else
    echo "  /home/$SSH_USER/.ssh/authorized_keys"
fi
echo ""
echo "Public key from Management VPS:"
echo "  cat /opt/mcp-server/secrets/ssh_key.pub"
echo "========================================="
