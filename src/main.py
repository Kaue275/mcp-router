from fastmcp import FastMCP
import shutil
from mcp import ClientSession
from mcp.client.stdio import StdioServerParameters, stdio_client
import os
import sys
from pathlib import Path

mcp = FastMCP("MCP Demo")


def resolve_uvx() -> str:
    """Localiza o executável do uvx, incluindo o venv que roda este script.

    O PATH do processo que inicia o servidor (ex.: Claude Code) pode não conter
    os Scripts/bin do venv, então procuramos primeiro ao lado do interpretador.
    """
    scripts_dir = Path(sys.executable).parent
    for candidate in ("uvx.exe", "uvx"):
        local = scripts_dir / candidate
        if local.is_file():
            return str(local)

    found = shutil.which("uvx")
    if found:
        return found

    raise RuntimeError(
        "'uvx' não encontrado. Instale com: pip install uv (ou instale o uv globalmente)."
    )


uvx_exe = resolve_uvx()

sub_mcp = {
    # O mcp-server-git declara "mcp>=1.0.0" sem teto, mas quebra com o SDK 1.29+
    # ('Server' object has no attribute 'list_tools'). Fixamos o SDK do subprocesso.
    "git": StdioServerParameters(
        command=uvx_exe,
        args=["--with", "mcp<1.29", "mcp-server-git"],
        env=os.environ.copy(),
    )
}

# Armazena em memória as ferramentas descobertas nos sub-MCPs
TOOL_CATALOG = {}
# Erros de inicialização por sub-MCP, mantidos fora do catálogo de ferramentas
DISCOVERY_ERRORS = {}


async def discover_sub_mcp_tools():
    """Conecta nos sub-MCPs e indexa suas ferramentas silenciosamente."""
    DISCOVERY_ERRORS.clear()
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
            DISCOVERY_ERRORS[mcp_name] = f"{type(exc).__name__}: {exc}"


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
        resposta = f"Nenhuma ferramenta encontrada para a busca: '{query}'."
    else:
        resposta = "Ferramentas encontradas:\n" + "\n".join(matched)

    if DISCOVERY_ERRORS:
        falhas = "\n".join(f"- {nome}: {erro}" for nome, erro in DISCOVERY_ERRORS.items())
        resposta += f"\n\nSub-MCPs que falharam ao inicializar:\n{falhas}"

    return resposta


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