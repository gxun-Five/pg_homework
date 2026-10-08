"""CLI client to talk to the pg-mcp stdio server.

The server (`python -m pg_mcp`) only understands the MCP protocol over
stdio, not free-form text. This script spawns the server as a subprocess and
calls its `query` tool, so you can type a natural-language question and get
back the generated SQL / results.

Usage:
    python examples/ask.py "Return the number 42"
    python examples/ask.py "How many users registered in the last 30 days?" sql
"""

import asyncio
import sys

from mcp import ClientSession
from mcp.client.stdio import stdio_client
from mcp.client.stdio import StdioServerParameters


async def ask(question: str, return_type: str = "result") -> None:
    params = StdioServerParameters(command="python", args=["-m", "pg_mcp"])
    async with stdio_client(params) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()
            result = await session.call_tool(
                "query",
                {"question": question, "return_type": return_type},
            )
            for item in result.content:
                text = getattr(item, "text", None)
                if text is not None:
                    print(text)


def main() -> None:
    question = sys.argv[1] if len(sys.argv) > 1 else "Return the number 42"
    return_type = sys.argv[2] if len(sys.argv) > 2 else "result"
    asyncio.run(ask(question, return_type))


if __name__ == "__main__":
    main()
