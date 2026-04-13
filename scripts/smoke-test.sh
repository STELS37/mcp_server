#!/bin/bash
# Smoke Test Script for MCP SSH Gateway
# Run after deployment to verify everything works

#set -e

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

PASS=0
FAIL=0

test_pass() { echo -e "${GREEN}✓ PASS${NC}: $1"; ((PASS++)); }
test_fail() { echo -e "${RED}✗ FAIL${NC}: $1"; ((FAIL++)); }
test_warn() { echo -e "${YELLOW}! WARN${NC}: $1"; }

# Configuration - Default to local
MCP_URL="${MCP_URL:-http://127.0.0.1:8000}"
AUTH_TOKEN="${AUTH_TOKEN:-}"

echo "========================================="
echo "MCP SSH Gateway Smoke Tests"
echo "========================================="
echo "MCP URL: $MCP_URL"
echo ""

# --- Level 1: Runtime Health ---
echo "=== Level 1: Runtime Health ==="

# Test 1: Health Check
if curl -sf "$MCP_URL/health" > /dev/null 2>&1; then
    test_pass "Health endpoint accessible"
else
    test_fail "Health endpoint not accessible"
fi

# Test 2: Readiness Check
if curl -sf "$MCP_URL/ready" > /dev/null 2>&1; then
    test_pass "Ready endpoint accessible"
else
    test_fail "Ready endpoint not accessible"
fi

# Test 3: Control Health
if curl -sf "$MCP_URL/control-health" > /dev/null 2>&1; then
    test_pass "Control health endpoint accessible"
else
    test_fail "Control health endpoint not accessible"
fi

# Test 4: OIDC Discovery
if curl -sf "$MCP_URL/.well-known/openid-configuration" > /dev/null 2>&1; then
    test_pass "OIDC discovery endpoint accessible"
else
    test_warn "OIDC discovery endpoint not accessible (OAuth may be disabled)"
fi

# --- Level 2: Control Plane ---
echo ""
echo "=== Level 2: Control Plane ==="

# Test 5: GET /mcp (Tools Discovery)
RESPONSE=$(curl -sSf "$MCP_URL/mcp" 2>/dev/null)
if echo "$RESPONSE" | grep -q '"tools"'; then
    TOOL_COUNT=$(echo "$RESPONSE" | grep -o '"name"' | wc -l)
    test_pass "MCP discovery returned $TOOL_COUNT tools"
else
    test_fail "MCP discovery failed or returned no tools"
fi

# Test 6: Local-only probe via Control Health
CTRL_RESP=$(curl -sSf "$MCP_URL/control-health" 2>/dev/null)
if echo "$CTRL_RESP" | grep -q '"status":"healthy"'; then
    test_pass "Control plane status: healthy"
elif echo "$CTRL_RESP" | grep -q '"status":"degraded"'; then
    test_warn "Control plane status: degraded"
    test_pass "Control plane responding"
else
    test_fail "Control plane check failed"
fi

# --- Level 3: Authenticated MCP POST Path ---
echo ""
echo "=== Level 3: Authenticated MCP POST Path ==="

if [ -n "$AUTH_TOKEN" ]; then
    # Test 7: Initialize
    RESPONSE=$(curl -s -X POST "$MCP_URL/mcp" \
        -H "Authorization: Bearer $AUTH_TOKEN" \
        -H "Content-Type: application/json" \
        -d '{"jsonrpc":"2.0","id":1,"method":"initialize","params":{"protocolVersion":"2024-11-05","capabilities":{},"clientInfo":{"name":"smoke-test","version":"1.0"}}}')
    if echo "$RESPONSE" | grep -q '"result"'; then
        test_pass "MCP initialize successful"
    else
        test_fail "MCP initialize failed: $RESPONSE"
    fi

    # Test 8: List Tools
    RESPONSE=$(curl -s -X POST "$MCP_URL/mcp" \
        -H "Authorization: Bearer $AUTH_TOKEN" \
        -H "Content-Type: application/json" \
        -d '{"jsonrpc":"2.0","id":2,"method":"tools/list","params":{}}')
    if echo "$RESPONSE" | grep -q '"tools"'; then
        test_pass "Tools list retrieved"
    else
        test_fail "Tools list failed: $RESPONSE"
    fi

    # Test 9: Quick local tool call (project_quick_facts)
    RESPONSE=$(curl -s -X POST "$MCP_URL/mcp" \
        -H "Authorization: Bearer $AUTH_TOKEN" \
        -H "Content-Type: application/json" \
        -d '{"jsonrpc":"2.0","id":3,"method":"tools/call","params":{"name":"project_quick_facts","arguments":{}}}')
    if echo "$RESPONSE" | grep -q '"result"'; then
        test_pass "project_quick_facts tool executed successfully"
    else
        test_fail "project_quick_facts tool failed: $RESPONSE"
    fi
else
    test_warn "Authenticated tests skipped (no AUTH_TOKEN)"
fi

# Summary
echo ""
echo "========================================="
echo "Smoke Test Summary"
echo "========================================="
echo -e "${GREEN}Passed: $PASS${NC}"
echo -e "${RED}Failed: $FAIL${NC}"
echo ""

if [ $FAIL -gt 0 ]; then
    echo "Some tests failed. Check configuration and logs."
    exit 1
else
    echo "All tests passed!"
    exit 0
fi
