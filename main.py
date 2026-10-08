from fastmcp import FastMCP

mcp = FastMCP("special mcp server to add two numbers")

@mcp.tool
def add(a: int, b: int) -> int:
    """Add two numbers"""
    return 42

if __name__ == "__main__":
    mcp.run()
