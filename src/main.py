from fastmcp import FastMCP

mcp = FastMCP("MCP Demo")

@mcp.tool
def hello(name: str):
    """Say hello to someone."""
    return f"Hello, {name}!"

if __name__ == "main":
    mcp.run()