"""MCP Tools - Router architecture with execution isolation."""
import asyncio
import inspect
import json
import logging
from typing import Dict, Any, Callable, Optional, List
from dataclasses import dataclass
from pathlib import Path

# Import single router tool and extra modules
from mcp_server.tools.single_router_tool import register_single_router_tool
from mcp_server.tools.session_tools import register_session_tools
from mcp_server.tools.bootstrap_tools import register_bootstrap_tools
from mcp_server.tools.smart_tools import register_smart_tools

logger = logging.getLogger(__name__)


@dataclass
class ToolDefinition:
    """MCP Tool definition."""
    name: str
    description: str
    input_schema: Dict[str, Any]
    handler: Callable
    dangerous: bool = False
    annotations: Optional[Dict[str, Any]] = None

class MCPTools:
    """MCP Tools - Router architecture with workflow support."""
    
    def __init__(self, ssh_client=None):
        self.ssh = ssh_client
        self._tools: Dict[str, ToolDefinition] = {}
        self.extra_tools: Dict[str, Dict[str, Any]] = {}
        self._action_history: List[Dict[str, Any]] = []
        # Execution isolation configuration
        self._executor_semaphore = asyncio.Semaphore(4)
        self._tool_timeout = 120
        
        # Register single router tool first
        count = register_single_router_tool(self)
        logger.info(f"Registered {count} tool (system_status)")
        
        # Register extra tools (workflow, orchestrator, etc.)
        self._register_extra_tools()
        
        # Convert dict to ToolDefinition
        self._convert_dict_to_tooldef()
        
        # Merge extra tools
        self._merge_extra_tools()
    
    def _register_tool(self, name_or_tool, description: str = None, input_schema: Dict[str, Any] = None,
                       handler: Callable = None, dangerous: bool = False,
                       annotations: Optional[Dict[str, Any]] = None) -> None:
        """Register a tool. Accepts either positional args or a tool object."""
        # Support passing a tool object (ExtraToolDefinition, dict, etc.)
        if hasattr(name_or_tool, 'name'):
            # It's a tool object like ExtraToolDefinition
            tool = name_or_tool
            self._tools[tool.name] = ToolDefinition(
                name=tool.name,
                description=tool.description,
                input_schema=tool.input_schema,
                handler=tool.handler,
                dangerous=getattr(tool, 'dangerous', False),
                annotations=getattr(tool, 'annotations', None) or {}
            )
            logger.info(f"Registered tool: {tool.name}")
        elif isinstance(name_or_tool, dict):
            # It's a dict
            tool_data = name_or_tool
            name = tool_data.get('name', 'unknown')
            self._tools[name] = ToolDefinition(
                name=name,
                description=tool_data.get('description', ''),
                input_schema=tool_data.get('input_schema', {}),
                handler=tool_data['handler'],
                dangerous=tool_data.get('dangerous', False),
                annotations=tool_data.get('annotations', {})
            )
            logger.info(f"Registered tool: {name}")
        else:
            # Positional args
            self._tools[name_or_tool] = ToolDefinition(
                name=name_or_tool,
                description=description or '',
                input_schema=input_schema or {},
                handler=handler,
                dangerous=dangerous,
                annotations=annotations or {}
            )
            logger.info(f"Registered tool: {name_or_tool}")
    
    def _register_extra_tools(self) -> None:
        """Register workflow, orchestrator, router, and playbook tools."""
        # Workflow tools
        try:
            from mcp_server.tools.workflow_tools import register_workflow_tools
            register_workflow_tools(self)
            logger.info("Workflow tools registered")
        except ImportError as e:
            logger.warning(f"Workflow tools not available: {e}")
        
        # Router tools
        try:
            from mcp_server.tools.router_tools import register_router_tools
            register_router_tools(self)
            logger.info("Router tools registered")
        except ImportError as e:
            logger.warning(f"Router tools not available: {e}")
        
        # Orchestrator tools
        try:
            from mcp_server.tools.orchestrator_tools import register_orchestrator_tools
            register_orchestrator_tools(self)
            logger.info("Orchestrator tools registered")
        except ImportError as e:
            logger.warning(f"Orchestrator tools not available: {e}")
        
        # Playbook tools
        try:
            from mcp_server.tools.playbook_tools import register_playbook_tools
            register_playbook_tools(self)
            logger.info("Playbook tools registered")
        except ImportError as e:
            logger.warning(f"Playbook tools not available: {e}")
        
        # Agent Zero handoff tools
        try:
            from mcp_server.tools.agent_zero_handoff_tools import register_agent_zero_handoff_tools
            register_agent_zero_handoff_tools(self)
            logger.info("Agent Zero handoff tools registered")
        except ImportError as e:
            logger.warning(f"Agent Zero handoff tools not available: {e}")
        
        # Direct ops tools
        try:
            from mcp_server.tools.direct_ops_tools import register_direct_ops_tools
            register_direct_ops_tools(self)
            logger.info("Direct ops tools registered")
        except ImportError as e:
            logger.warning(f"Direct ops tools not available: {e}")

        # Session tools (sticky context)
        try:
            register_session_tools(self)
            logger.info("Session tools registered")
        except Exception as e:
            logger.warning(f"Session tools not available: {e}")

        # Bootstrap tools
        try:
            register_bootstrap_tools(self)
            logger.info("Bootstrap tools registered")
        except Exception as e:
            logger.warning(f"Bootstrap tools not available: {e}")

        # Smart tools
        try:
            register_smart_tools(self)
            logger.info("Smart tools registered")
        except Exception as e:
            logger.warning(f"Smart tools not available: {e}")
    
    def _convert_dict_to_tooldef(self) -> None:
        """Convert dict format tools to ToolDefinition objects."""
        for name, tool_data in list(self._tools.items()):
            if isinstance(tool_data, dict) and 'handler' in tool_data:
                self._tools[name] = ToolDefinition(
                    name=tool_data.get('name', name),
                    description=tool_data.get('description', ''),
                    input_schema=tool_data.get('input_schema', {}),
                    handler=tool_data['handler'],
                    dangerous=tool_data.get('dangerous', False),
                    annotations=tool_data.get('annotations', {})
                )
                logger.info(f"Converted {name} to ToolDefinition")
    
    def _merge_extra_tools(self) -> None:
        """Merge extra tools into main tools dict."""
        for name, tool_data in self.extra_tools.items():
            if isinstance(tool_data, dict) and 'handler' in tool_data:
                self._tools[name] = ToolDefinition(
                    name=tool_data.get('name', name),
                    description=tool_data.get('description', ''),
                    input_schema=tool_data.get('input_schema', {}),
                    handler=tool_data['handler'],
                    dangerous=tool_data.get('dangerous', False),
                    annotations=tool_data.get('annotations', {})
                )
                logger.info(f"Merged extra tool: {name}")
        
        total = len(self._tools)
        logger.info(f"Total tools registered: {total}")
    
    def list_tools(self) -> List[ToolDefinition]:
        """List all registered tools."""
        return list(self._tools.values())
    
    def get_tool_definitions(self) -> List[Dict[str, Any]]:
        """Get tool definitions for MCP manifest."""
        definitions = []
        for tool in self.list_tools():
            definitions.append({
                'name': tool.name,
                'description': tool.description,
                'inputSchema': tool.input_schema,
                'annotations': tool.annotations or {}
            })
        return definitions

    def get_tool(self, name: str) -> Optional[ToolDefinition]:
        """Get tool by name."""
        return self._tools.get(name)
    
    async def execute_tool(self, name: str, arguments: Dict[str, Any], user: str = "unknown") -> Dict[str, Any]:
        """Execute tool by name with per-tool timeout and execution isolation."""
        tool = self.get_tool(name)
        if not tool:
            return {
                'content': [{'type': 'text', 'text': f'Unknown tool: {name}'}],
                'isError': True
            }

        logger.info(f"[MCP] execute_tool: name={name}, args={json.dumps(arguments)[:100]}")
        # Ensure semaphore exists (safety fallback)
        sem = getattr(self, "_executor_semaphore", None)
        if sem is None:
            self._executor_semaphore = asyncio.Semaphore(4)
            sem = self._executor_semaphore
        
        # Use semaphore to limit concurrent execution
        # Use semaphore to limit concurrent execution
        async with sem:
            try:
                call_args = dict(arguments or {})
                call_args["_user"] = user

                # Determine if this is a local-only tool (shorter timeout)
                local_only_tools = {"local_exec", "read_file", "write_file", "patch_file",
                                    "list_dir", "http_probe", "path_ops", "service_control",
                                    "project_quick_facts", "get_task_playbook", "start_work_session",
                                    "summarize_repo_state", "self_check_server_state"}
                timeout = 30 if name in local_only_tools else self._tool_timeout

                # Execute with timeout
                import time
                start = time.monotonic()
                outcome = tool.handler(call_args)
                if inspect.isawaitable(outcome):
                    result = await asyncio.wait_for(outcome, timeout=timeout)
                else:
                    result = outcome
                elapsed = time.monotonic() - start

                logger.info(f"[MCP] result: isError={result.get('isError', False)}, elapsed={elapsed:.2f}s")
                return result

            except asyncio.TimeoutError as e:
                logger.error(f"[MCP] TIMEOUT: tool={name} after {timeout}s")
                return {
                    'content': [{'type': 'text', 'text': f'Tool execution timed out after {timeout}s: {name}'}],
                    'isError': True
                }
            except Exception as e:
                logger.error(f"[MCP] error: {e}")
                return {
                    'content': [{'type': 'text', 'text': f'Error executing {name}: {e}'}],
                    'isError': True
                }


def register_tools(ssh_client=None) -> MCPTools:
    """Register all MCP tools."""
    return MCPTools(ssh_client)
