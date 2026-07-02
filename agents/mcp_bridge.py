"""Bridges the MCP client protocol to Ollama's tool-calling format. Launches
mcp_servers/server.py as a stdio subprocess per call -- a few hundred ms of
overhead, acceptable for a single-user local tool answering on the order of
seconds."""

import sys
from contextlib import asynccontextmanager
from pathlib import Path

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client
from mcp.types import Tool

REPO_ROOT = Path(__file__).parent.parent

SERVER_PARAMS = StdioServerParameters(
    command=sys.executable,
    args=["-m", "mcp_servers.server"],
    cwd=str(REPO_ROOT),
)


@asynccontextmanager
async def connect():
    async with stdio_client(SERVER_PARAMS) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()
            yield session


def _to_ollama_tool(tool: Tool) -> dict:
    return {
        "type": "function",
        "function": {
            "name": tool.name,
            "description": tool.description or "",
            "parameters": tool.inputSchema,
        },
    }


async def list_ollama_tools(session: ClientSession) -> list[dict]:
    result = await session.list_tools()
    return [_to_ollama_tool(t) for t in result.tools]


async def call_tool(session: ClientSession, name: str, arguments: dict):
    """Calls an MCP tool and returns its result as plain Python data --
    structuredContent when the tool returned a dict/list (all of ours do),
    falling back to concatenated text content."""
    result = await session.call_tool(name, arguments)
    if result.structuredContent is not None:
        # FastMCP wraps non-object returns (e.g. our list-returning tools)
        # under a "result" key to satisfy the JSON-object-at-top-level rule.
        return result.structuredContent.get("result", result.structuredContent)
    return "\n".join(block.text for block in result.content if hasattr(block, "text"))
