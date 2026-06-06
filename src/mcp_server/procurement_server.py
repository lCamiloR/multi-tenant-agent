"""
MCP Server exposing procurement search and retrieval tools.

This server can be consumed by any MCP-compatible client:
  - LangGraph agent (via langchain-mcp-adapters)
  - Claude Desktop (via stdio transport)
  - Any future agent or service

Transport: SSE over HTTP (suitable for LangGraph integration).
Run with: python -m src.mcp_server.procurement_server
"""

import asyncio
import json
import logging
from typing import Any

from mcp.server import Server
from mcp.server.sse import SseServerTransport
from mcp.types import Tool, TextContent
from starlette.applications import Starlette
from starlette.routing import Route

from src.pipeline.clients.milvus_client import MilvusLicitacoesClient
from src.pipeline.clients.embedding_client import EmbeddingClient
from src.db.repositories.procurement_repo import ProcurementRepository
from src.db.session import get_session_ctx
from src.core.config import SETTINGS

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# The MCP Server instance — this is what handles the protocol
server = Server("procurement-server")


# ── Tool Declarations ────────────────────────────────────────────────────────
# list_tools() is called by the host on startup to discover available tools.
# The JSON Schema here is what the LLM sees when deciding which tool to call.

@server.list_tools()
async def list_tools() -> list[Tool]:
    return [
        Tool(
            name="search_procurements",
            description=(
                "Search for Brazilian government procurements semantically. "
                "Use when the user describes their business area or the type of "
                "service/product they offer. Returns ranked results with control numbers."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "Natural language description of the procurement. "
                                       "Example: 'software development for web applications'",
                    },
                    "uf": {
                        "type": "string",
                        "description": "Brazilian state acronym (e.g. 'SP', 'RJ'). Optional.",
                    },
                    "modalidade_id": {
                        "type": "integer",
                        "description": "Modality code: 6=Pregão Eletrônico, 8=Dispensa Eletrônica. Optional.",
                    },
                    "apenas_abertas": {
                        "type": "boolean",
                        "description": "If true, only returns procurements with open proposal period.",
                        "default": False,
                    },
                    "limit": {
                        "type": "integer",
                        "description": "Maximum number of results (1-20).",
                        "default": 5,
                    },
                },
                "required": ["query"],
            },
        ),
        Tool(
            name="get_procurement_details",
            description=(
                "Retrieve full structured details of a specific procurement from the database. "
                "Use after search_procurements to get complete information about a result "
                "the user is interested in."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "pncp_control_number": {
                        "type": "string",
                        "description": "The PNCP control number returned by search_procurements.",
                    },
                },
                "required": ["pncp_control_number"],
            },
        ),
        Tool(
            name="get_multiple_procurement_details",
            description=(
                "Retrieve details for multiple procurements in a single call. "
                "More efficient than calling get_procurement_details repeatedly."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "pncp_control_numbers": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "List of PNCP control numbers (max 10).",
                        "maxItems": 10,
                    },
                },
                "required": ["pncp_control_numbers"],
            },
        ),
    ]


# ── Tool Implementations ─────────────────────────────────────────────────────
# call_tool() is invoked by the host when the LLM decides to use a tool.
# It receives the tool name and arguments, routes to the right handler,
# and returns a list of TextContent objects.

@server.call_tool()
async def call_tool(name: str, arguments: dict[str, Any]) -> list[TextContent]:
    """
    Single dispatch point for all tool calls.
    The MCP protocol routes every tool invocation here — we fan out
    to the appropriate handler based on the tool name.
    """
    handlers = {
        "search_procurements": _handle_search,
        "get_procurement_details": _handle_get_details,
        "get_multiple_procurement_details": _handle_get_multiple_details,
    }

    handler = handlers.get(name)
    if not handler:
        return [TextContent(type="text", text=f"Unknown tool: {name}")]

    try:
        result = await handler(arguments)
        return [TextContent(type="text", text=result)]
    except Exception as e:
        logger.error(f"Tool '{name}' failed: {e}", exc_info=True)
        return [TextContent(type="text", text=f"Tool execution failed: {str(e)}")]


# ── Handlers ─────────────────────────────────────────────────────────────────

async def _handle_search(args: dict) -> str:
    embedder = EmbeddingClient(api_key=SETTINGS.openai_api_key)
    milvus = MilvusLicitacoesClient(uri=SETTINGS.milvus_uri)

    try:
        query_vector = await embedder.embed(args["query"])
        results = milvus.search(
            query_vector=query_vector,
            uf=args.get("uf"),
            modalidade_id=args.get("modalidade_id"),
            apenas_abertas=args.get("apenas_abertas", False),
            limit=args.get("limit", 5),
        )

        if not results:
            return "No procurements found matching your criteria."

        lines = [f"Found {len(results)} matching procurement(s):\n"]
        for i, r in enumerate(results, 1):
            lines.append(
                f"{i}. Control Number: {r['id']}\n"
                f"   Similarity Score: {r['score']:.4f}\n"
                f"   State: {r.get('uf_sigla') or 'N/A'}\n"
                f"   Modality ID: {r.get('modalidade_id') or 'N/A'}\n"
            )
        return "\n".join(lines)
    finally:
        milvus.close()


async def _handle_get_details(args: dict) -> str:
    pncp_number = args["pncp_control_number"]

    async with get_session_ctx() as session:
        repo = ProcurementRepository(session)
        procurement = await repo.get_by_pncp_control_number(pncp_number)

    if not procurement:
        return f"Procurement '{pncp_number}' not found."

    price = f"R$ {procurement.estimated_price:,.2f}" if procurement.estimated_price else "Not informed"
    start = procurement.tender_start_date.strftime("%d/%m/%Y %H:%M") if procurement.tender_start_date else "N/A"
    deadline = procurement.tender_deadline.strftime("%d/%m/%Y %H:%M") if procurement.tender_deadline else "N/A"
    published = procurement.published_at.strftime("%d/%m/%Y") if procurement.published_at else "N/A"

    return (
        f"= Procurement Details =\n"
        f"Control Number: {procurement.pncp_control_number}\n"
        f"Object: {procurement.procurement_object}\n"
        f"Additional Info: {procurement.additional_information or 'None'}\n"
        f"Estimated Price: {price}\n"
        f"Proposal Start: {start}\n"
        f"Proposal Deadln: {deadline}\n"
        f"Published At: {published}\n"
    )


async def _handle_get_multiple_details(args: dict) -> str:
    numbers = args["pncp_control_numbers"]

    async with get_session_ctx() as session:
        repo = ProcurementRepository(session)
        procurements = await repo.get_many_by_pncp_control_numbers(numbers)

    if not procurements:
        return "No procurements found for the provided control numbers."

    results = []
    for p in procurements:
        price = f"R$ {p.estimated_price:,.2f}" if p.estimated_price else "Not informed"
        deadline = p.tender_deadline.strftime("%d/%m/%Y %H:%M") if p.tender_deadline else "N/A"
        results.append(
            f"• {p.pncp_control_number}\n"
            f"  Object  : {p.procurement_object[:120]}...\n"
            f"  Price   : {price}\n"
            f"  Deadline: {deadline}\n"
        )

    return f"Found {len(procurements)} procurement(s):\n\n" + "\n".join(results)


# ── Server Startup (SSE transport) ───────────────────────────────────────────

def create_starlette_app() -> Starlette:
    """
    Wraps the MCP server in a Starlette app using SSE transport.

    SSE (Server-Sent Events) is the right transport for LangGraph integration
    because it works over HTTP — the LangGraph agent connects as a client,
    just like it would connect to any external API.

    The /sse endpoint is where the MCP handshake and tool calls happen.
    """
    sse_transport = SseServerTransport("/messages/")

    async def handle_sse(request):
        async with sse_transport.connect_sse(
            request.scope, request.receive, request._send
        ) as streams:
            await server.run(
                streams[0],
                streams[1],
                server.create_initialization_options(),
            )

    return Starlette(
        routes=[
            Route("/sse", endpoint=handle_sse),
            Route("/messages/", endpoint=sse_transport.handle_post_message, methods=["POST"]),
        ]
    )


if __name__ == "__main__":
    import uvicorn
    app = create_starlette_app()
    uvicorn.run(app, host="0.0.0.0", port=8000)
    logger.info("MCP Server running at http://localhost:8000/sse")