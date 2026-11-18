"""nctb-corpus MCP server (stdio). Run: python -m mcp_server.server
Tools are READ-ONLY. Use a read-only DB role in production."""
try:
    from mcp.server.mcpserver import MCPServer as FastMCP
except ImportError:
    from mcp.server.fastmcp import FastMCP

from pathshala import db, retrieval

mcp = FastMCP("nctb-corpus")


@mcp.tool()
def search_textbook(query: str, class_level: int, subject: str | None = None, k: int = 5) -> list[dict]:
    """Hybrid search NCTB textbook chunks. Returns id, chunk_ref, class/subject, chapter, text, sim."""
    out = retrieval.search(query, class_level, subject, k=min(max(k, 1), 10))
    return [
        {x: c[x] for x in ("id", "chunk_ref", "book", "book_id", "class_level", "subject", "chapter_no", "chapter", "text", "sim") if x in c}
        for c in out
    ]


@mcp.tool()
def get_chapter(book_id: int, chapter_no: int) -> list[dict]:
    """All chunks of one chapter of a textbook."""
    return db.get_chapter(book_id, chapter_no)


@mcp.tool()
def list_chapters(book_id: int) -> list[dict]:
    """Chapters of a textbook: chapter_no, title, chunk count."""
    return db.list_chapters(book_id)


@mcp.tool()
def explain_citation(chunk_id: int) -> dict:
    """Return the source chunk (class, subject, chapter, full text) behind a citation."""
    return db.get_chunk(chunk_id) or {"error": "not found"}


if __name__ == "__main__":
    mcp.run()
