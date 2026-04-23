import asyncio

from mcp_server.tools.mcp_tools import MCPTools


class DummyTool:
    def __init__(self) -> None:
        self.name = 'slow_tool'
        self.description = 'slow tool'
        self.input_schema = {'type': 'object', 'properties': {}, 'required': []}
        self.handler = self._handler
        self.dangerous = False
        self.annotations = {}

    async def _handler(self, args):
        await asyncio.sleep(0.05)
        return {'content': [{'type': 'text', 'text': 'ok'}], 'isError': False}


async def _run_timeout_regression() -> None:
    tools = MCPTools(None)
    tools._tool_timeout = 0.01
    tools._register_tool(DummyTool())

    first = await tools.execute_tool('slow_tool', {}, user='test')
    assert first['isError'] is True
    assert 'timed out' in first['content'][0]['text']

    second = await tools.execute_tool('system_status', {'code': '01'}, user='test')
    assert 'isError' in second


def test_timeout_does_not_break_next_call() -> None:
    asyncio.run(_run_timeout_regression())
