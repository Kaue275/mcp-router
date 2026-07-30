from fastmcp import FastMCP
import shutil
from mcp import ClientSession
from mcp.client.stdio import StdioServerParameters, stdio_client
import os

mcp = FastMCP("MCP Demo")

uvx_exe = shutil.which("uvx") or shutil.which("uvx.exe") or shutil.which("uv")

sub_mcp = {
    "git": StdioServerParameters(
        command=uvx_exe or "uvx",
        args=["mcp-server-git"],
        env=os.environ.copy(),
    )
}

# Armazena em memória as ferramentas descobertas nos sub-MCPs
TOOL_CATALOG = {}


async def discover_sub_mcp_tools():
    """Conecta nos sub-MCPs no startup e indexa suas ferramentas silenciosamente."""
    for mcp_name, params in sub_mcp.items():
        try:
            async with stdio_client(params) as (read, write):
                async with ClientSession(read, write) as session:
                    await session.initialize()
                    tools = await session.list_tools()

                    for tool in tools.tools:
                        TOOL_CATALOG[f"{mcp_name}:{tool.name}"] = {
                            "mcp_name": mcp_name,
                            "tool_name": tool.name,
                            "description": tool.description,
                            "inputSchema": tool.inputSchema,
                        }
        except Exception as exc:
            TOOL_CATALOG[mcp_name] = {
                "mcp_name": mcp_name,
                "tool_name": None,
                "description": f"Falha ao inicializar o sub-MCP: {exc}",
                "inputSchema": {},
            }


# 2. Ferramentas que o FastMCP expõe para o Claude Code
@mcp.tool()
async def search_tools(query: str) -> str:
    """Busca ferramentas disponíveis nos sub-MCPs instalados."""
    
    # Se o catálogo ainda não foi preenchido, inicializa agora!
    if not TOOL_CATALOG:
        await discover_sub_mcp_tools()

    matched = []
    for full_name, info in TOOL_CATALOG.items():
        # Trata caso a descrição venha vazia/None para não dar erro
        description = info.get("description") or ""
        
        if query.lower() in description.lower() or query.lower() in full_name.lower():
            matched.append(f"- {full_name}: {description}")
    
    if not matched:
        return f"Nenhuma ferramenta encontrada para a busca: '{query}'."
        
    return "Ferramentas encontradas:\n" + "\n".join(matched)


@mcp.tool()
async def execute_tool(mcp_name: str, tool_name: str, args: dict) -> str:
    """Executa uma ferramenta específica no sub-MCP correto."""
    if mcp_name not in sub_mcp:
        return f"Erro: Sub-MCP '{mcp_name}' não encontrado."

    params = sub_mcp[mcp_name]

    try:
        async with stdio_client(params) as (read, write):
            async with ClientSession(read, write) as session:
                await session.initialize()
                result = await session.call_tool(tool_name, arguments=args)
                return str(result.content)
    except Exception as exc:
        return f"Erro ao executar '{tool_name}' no sub-MCP '{mcp_name}': {exc}"

@mcp.tool
def hello(name: str):
    """Say hello to someone."""
    return f"Hello, {name}!"

if __name__ == "__main__":
    mcp.run()