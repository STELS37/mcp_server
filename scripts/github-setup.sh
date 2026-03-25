#!/bin/bash
# GitHub Repository Setup Script
# Run this to initialize git and push to GitHub

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
REPO_NAME="mcp-ssh-gateway"
REPO_DESCRIPTION="Remote MCP Server for ChatGPT with SSH Gateway to VPS"
GITHUB_USER="${GITHUB_USER:-}"
GITHUB_TOKEN="${GITHUB_TOKEN:-}"

echo "========================================="
echo "MCP SSH Gateway - GitHub Setup"
echo "========================================="
echo ""

# Check if git is installed
if ! command -v git &> /dev/null; then
    log_info "Installing git..."
    apt-get update && apt-get install -y git
fi

# Initialize git if not already
if [ ! -d ".git" ]; then
    log_info "Initializing git repository..."
    git init
    git branch -M main
else
    log_info "Git repository already initialized"
fi

# Add all files
log_info "Adding files to git..."
git add -A

# Create initial commit if needed
if ! git log --oneline 2>/dev/null | head -1 | grep -q "."; then
    log_info "Creating initial commit..."
    git commit -m "Initial commit: MCP SSH Gateway for ChatGPT

- Remote MCP server with SSE transport
- 15 tools for VPS management
- OAuth/OIDC authentication with refresh tokens
- SSH gateway with safety safeguards
- Docker support with auto-update
- Complete deployment scripts

Features:
- ping_host, run_command, read_file, write_file
- upload_file, download_file, list_dir
- systemd_status, systemd_restart, journal_tail
- docker_ps, docker_logs, docker_exec
- get_public_ip, get_server_facts"
fi

# GitHub CLI or API setup
if command -v gh &> /dev/null && [ -n "$GITHUB_TOKEN" ]; then
    log_info "Using GitHub CLI..."
    
    # Create private repository
    if ! gh repo view "$GITHUB_USER/$REPO_NAME" 2>/dev/null; then
        log_info "Creating private GitHub repository..."
        gh repo create "$REPO_NAME" \
            --private \
            --description "$REPO_DESCRIPTION" \
            --source=. \
            --remote=origin
    else
        log_info "Repository already exists"
        git remote add origin "https://github.com/$GITHUB_USER/$REPO_NAME.git" 2>/dev/null || true
    fi
    
    # Push to GitHub
    log_info "Pushing to GitHub..."
    git push -u origin main --force
    
    log_info "Repository created: https://github.com/$GITHUB_USER/$REPO_NAME"
    
elif [ -n "$GITHUB_USER" ] && [ -n "$GITHUB_TOKEN" ]; then
    log_info "Using GitHub API..."
    
    # Create repository via API
    RESPONSE=$(curl -s -X POST "https://api.github.com/user/repos" \
        -H "Authorization: token $GITHUB_TOKEN" \
        -H "Accept: application/vnd.github.v3+json" \
        -d "{
            \"name\": \"$REPO_NAME\",
            \"description\": \"$REPO_DESCRIPTION\",
            \"private\": true,
            \"has_issues\": true,
            \"has_projects\": true,
            \"has_wiki\": true
        }")
    
    if echo "$RESPONSE" | grep -q "full_name"; then
        log_info "Repository created successfully"
        
        # Add remote and push
        git remote add origin "https://$GITHUB_USER:$GITHUB_TOKEN@github.com/$GITHUB_USER/$REPO_NAME.git" 2>/dev/null || true
        git push -u origin main --force
        
        log_info "Repository created: https://github.com/$GITHUB_USER/$REPO_NAME"
    else
        log_error "Failed to create repository: $RESPONSE"
        exit 1
    fi
else
    log_warn "GitHub credentials not set. Please provide:"
    echo "  export GITHUB_USER=your-username"
    echo "  export GITHUB_TOKEN=your-personal-access-token"
    echo ""
    echo "Then run this script again."
    echo ""
    echo "Or manually create a private repo on GitHub and run:"
    echo "  git remote add origin https://github.com/YOUR_USERNAME/$REPO_NAME.git"
    echo "  git push -u origin main"
fi

echo ""
echo "========================================="
echo "Setup Complete!"
echo "========================================="
