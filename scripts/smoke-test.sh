#!/bin/bash
# Smoke Test Script for MCP SSH Gateway
# Run after deployment to verify everything works

set -e

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

# Configuration
MCP_URL="${MCP_URL:-https://mcp.yourdomain.com}"
AUTH_TOKEN="${AUTH_TOKEN:-}"

echo "========================================="
echo "MCP SSH Gateway Smoke Tests"
echo "========================================="
echo "MCP URL: $MCP_URL"
echo ""

# Test 1: Health Check
echo "--- Test 1: Health Check ---"
if curl -sf "$MCP_URL/health" > /dev/null; then
    test_pass "Health endpoint accessible"
else
    test_fail "Health endpoint not accessible"
fi

# Test 2: Readiness Check
echo "--- Test 2: Readiness Check ---"
if curl -sf "$MCP_URL/ready" > /dev/null; then
    test_pass "Ready endpoint accessible"
else
    test_fail "Ready endpoint not accessible"
fi

# Test 3: OIDC Discovery
echo "--- Test 3: OIDC Discovery ---"
if curl -sf "$MCP_URL/.well-known/openid-configuration" > /dev/null; then
    test_pass "OIDC discovery endpoint accessible"
else
    test_warn "OIDC discovery endpoint not accessible (OAuth may be disabled)"
fi

# Test 4: SSE Endpoint (requires auth)
echo "--- Test 4: SSE Endpoint ---"
if [ -n "$AUTH_TOKEN" ]; then
    RESPONSE=$(curl -s -H "Authorization: Bearer $AUTH_TOKEN" "$MCP_URL/sse" | head -1)
    if echo "$RESPONSE" | grep -q "endpoint"; then
        test_pass "SSE endpoint accessible with auth"
    else
        test_fail "SSE endpoint returned unexpected response"
    fi
else
    test_warn "SSE endpoint test skipped (no AUTH_TOKEN)"
fi

# Test 5: MCP Initialize (requires auth)
echo "--- Test 5: MCP Initialize ---"
if [ -n "$AUTH_TOKEN" ]; then
    RESPONSE=$(curl -s -X POST "$MCP_URL/mcp" \
        -H "Authorization: Bearer $AUTH_TOKEN" \
        -H "Content-Type: application/json" \
        -d '{"jsonrpc":"2.0","id":1,"method":"initialize","params":{"protocolVersion":"2024-11-05","capabilities":{},"clientInfo":{"name":"smoke-test","version":"1.0"}}}')
    if echo "$RESPONSE" | grep -q '"result"'; then
        test_pass "MCP initialize successful"
    else
        test_fail "MCP initialize failed: $RESPONSE"
    fi
else
    test_warn "MCP initialize test skipped (no AUTH_TOKEN)"
fi

# Test 6: List Tools (requires auth)
echo "--- Test 6: List Tools ---"
if [ -n "$AUTH_TOKEN" ]; then
    RESPONSE=$(curl -s -X POST "$MCP_URL/mcp" \
        -H "Authorization: Bearer $AUTH_TOKEN" \
        -H "Content-Type: application/json" \
        -d '{"jsonrpc":"2.0","id":2,"method":"tools/list","params":{}}')
    if echo "$RESPONSE" | grep -q '"tools"'; then
        TOOL_COUNT=$(echo "$RESPONSE" | grep -o '"name"' | wc -l)
        test_pass "Tools list retrieved ($TOOL_COUNT tools)"
    else
        test_fail "Tools list failed: $RESPONSE"
    fi
else
    test_warn "Tools list test skipped (no AUTH_TOKEN)"
fi

# Test 7: ping_host tool (requires auth and SSH)
echo "--- Test 7: ping_host Tool ---"
if [ -n "$AUTH_TOKEN" ]; then
    RESPONSE=$(curl -s -X POST "$MCP_URL/mcp" \
        -H "Authorization: Bearer $AUTH_TOKEN" \
        -H "Content-Type: application/json" \
        -d '{"jsonrpc":"2.0","id":3,"method":"tools/call","params":{"name":"ping_host","arguments":{"host":"localhost","count":1}}}')
    if echo "$RESPONSE" | grep -q '"result"'; then
        test_pass "ping_host tool executed"
    else
        test_fail "ping_host tool failed: $RESPONSE"
    fi
else
    test_warn "ping_host test skipped (no AUTH_TOKEN)"
fi

# Test 8: run_command tool (requires auth and SSH)
echo "--- Test 8: run_command Tool (whoami) ---"
if [ -n "$AUTH_TOKEN" ]; then
    RESPONSE=$(curl -s -X POST "$MCP_URL/mcp" \
        -H "Authorization: Bearer $AUTH_TOKEN" \
        -H "Content-Type: application/json" \
        -d '{"jsonrpc":"2.0","id":4,"method":"tools/call","params":{"name":"run_command","arguments":{"command":"whoami"}}}')
    if echo "$RESPONSE" | grep -q '"result"'; then
        test_pass "run_command(whoami) executed"
    else
        test_fail "run_command(whoami) failed: $RESPONSE"
    fi
else
    test_warn "run_command test skipped (no AUTH_TOKEN)"
fi

# Test 9: run_command tool (uname)
echo "--- Test 9: run_command Tool (uname -a) ---"
if [ -n "$AUTH_TOKEN" ]; then
    RESPONSE=$(curl -s -X POST "$MCP_URL/mcp" \
        -H "Authorization: Bearer $AUTH_TOKEN" \
        -H "Content-Type: application/json" \
        -d '{"jsonrpc":"2.0","id":5,"method":"tools/call","params":{"name":"run_command","arguments":{"command":"uname -a"}}}')
    if echo "$RESPONSE" | grep -q '"result"'; then
        test_pass "run_command(uname -a) executed"
    else
        test_fail "run_command(uname -a) failed: $RESPONSE"
    fi
else
    test_warn "run_command test skipped (no AUTH_TOKEN)"
fi

# Test 10: read_file tool
echo "--- Test 10: read_file Tool (/etc/os-release) ---"
if [ -n "$AUTH_TOKEN" ]; then
    RESPONSE=$(curl -s -X POST "$MCP_URL/mcp" \
        -H "Authorization: Bearer $AUTH_TOKEN" \
        -H "Content-Type: application/json" \
        -d '{"jsonrpc":"2.0","id":6,"method":"tools/call","params":{"name":"read_file","arguments":{"path":"/etc/os-release"}}}')
    if echo "$RESPONSE" | grep -q '"result"'; then
        test_pass "read_file(/etc/os-release) executed"
    else
        test_fail "read_file(/etc/os-release) failed: $RESPONSE"
    fi
else
    test_warn "read_file test skipped (no AUTH_TOKEN)"
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
