import os
import sys
from pathlib import Path


# Test collection imports the FastAPI app, whose production settings correctly
# require an SSH target. Keep tests hermetic without weakening production
# validation or attempting any network connection.
os.environ.setdefault("MCP_SSH__HOST", "127.0.0.1")
os.environ.setdefault("MCP_SSH__USER", "ci-test")
os.environ.setdefault("MCP_HEALTH__SSH_CHECK", "false")

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"

if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))
