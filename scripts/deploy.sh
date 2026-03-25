#!/bin/bash
# MCP SSH Gateway Deployment Script
# Run on Management VPS

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

log_info() { echo -e "${GREEN}[INFO]${NC} $1"; }
log_warn() { echo -e "${YELLOW}[WARN]${NC} $1"; }
log_error() { echo -e "${RED}[ERROR]${NC} $1"; }

# Configuration
APP_DIR="/opt/mcp-server"
APP_USER="mcp"
DOMAIN="${DOMAIN:-mcp.yourdomain.com}"
SSH_TARGET_HOST="${SSH_TARGET_HOST:-}"
SSH_TARGET_USER="${SSH_TARGET_USER:-root}"

# Check if running as root
if [ "$EUID" -ne 0 ]; then
    log_error "Please run as root"
    exit 1
fi

log_info "Starting MCP SSH Gateway deployment..."

# 1. Install dependencies
log_info "Installing system dependencies..."
apt-get update
apt-get install -y python3 python3-pip python3-venv nginx redis-server certbot python3-certbot-nginx

# 2. Create app user
log_info "Creating application user..."
if ! id -u $APP_USER &>/dev/null; then
    useradd -r -s /bin/false $APP_USER
fi

# 3. Create directories
log_info "Creating directories..."
mkdir -p $APP_DIR/{secrets,logs,config}
mkdir -p /var/log/mcp-server

# 4. Copy application files
log_info "Copying application files..."
cp -r src/ $APP_DIR/
cp -r config/ $APP_DIR/
cp pyproject.toml $APP_DIR/
cp requirements.txt $APP_DIR/

# 5. Create virtual environment
log_info "Setting up Python virtual environment..."
cd $APP_DIR
python3 -m venv venv
source venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt

# 6. Create SSH key for connecting to experimental VPS
log_info "Generating SSH key for experimental VPS connection..."
if [ ! -f "$APP_DIR/secrets/ssh_key" ]; then
    ssh-keygen -t ed25519 -f $APP_DIR/secrets/ssh_key -N "" -C "mcp-server"
    log_info "SSH key generated. Add this public key to your experimental VPS:"
    cat $APP_DIR/secrets/ssh_key.pub
    log_warn "Add the above public key to ~/.ssh/authorized_keys on your experimental VPS"
fi

# 7. Create environment file
log_info "Creating environment configuration..."
if [ ! -f "$APP_DIR/.env" ]; then
    cp config/.env.template $APP_DIR/.env
    log_warn "Please edit $APP_DIR/.env with your configuration"
fi

# 8. Set permissions
log_info "Setting permissions..."
chown -R $APP_USER:$APP_USER $APP_DIR
chown -R $APP_USER:$APP_USER /var/log/mcp-server
chmod 600 $APP_DIR/secrets/*
chmod 600 $APP_DIR/.env

# 9. Install systemd service
log_info "Installing systemd service..."
cp scripts/mcp-server.service /etc/systemd/system/
systemctl daemon-reload
systemctl enable mcp-server

# 10. Configure nginx
log_info "Configuring nginx..."
sed "s/mcp.yourdomain.com/$DOMAIN/g" config/nginx.conf > /etc/nginx/sites-available/mcp-server
ln -sf /etc/nginx/sites-available/mcp-server /etc/nginx/sites-enabled/
rm -f /etc/nginx/sites-enabled/default
nginx -t && systemctl reload nginx

# 11. Setup SSL with Let's Encrypt
log_info "Setting up SSL certificate..."
if [ "$DOMAIN" != "mcp.yourdomain.com" ]; then
    certbot --nginx -d $DOMAIN --non-interactive --agree-tos --email admin@$DOMAIN
else
    log_warn "Please set DOMAIN environment variable and run: certbot --nginx -d your-domain"
fi

# 12. Start the service
log_info "Starting MCP server..."
systemctl start mcp-server

# 13. Show status
log_info "Deployment complete!"
echo ""
echo "========================================="
echo "MCP SSH Gateway Deployment Summary"
echo "========================================="
echo "Application Directory: $APP_DIR"
echo "Configuration File: $APP_DIR/.env"
echo "Log Directory: /var/log/mcp-server"
echo "SSH Key: $APP_DIR/secrets/ssh_key"
echo ""
echo "Next steps:"
echo "1. Edit $APP_DIR/.env with your configuration"
echo "2. Add the SSH public key to your experimental VPS"
echo "3. Configure OAuth provider"
echo "4. Restart service: systemctl restart mcp-server"
echo "5. Check status: systemctl status mcp-server"
echo ""
echo "Health check: https://$DOMAIN/health"
echo "SSE endpoint: https://$DOMAIN/sse"
echo "========================================="
