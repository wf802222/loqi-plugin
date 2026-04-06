"""Format Loqi retrieval results for injection into Claude's context."""

from __future__ import annotations

MAX_SECTIONS = 5
MAX_CONTENT_CHARS = 500


def format_memory_context(result: dict) -> str:
    """Convert a query result into the <loqi-memory> injection block.

    Args:
        result: The dict returned by ProjectState.query() with 'sections' and 'metadata'.

    Returns:
        Formatted string for additionalContext, or empty string if nothing relevant.
    """
    sections = result.get("sections", [])
    if not sections:
        return ""

    sections = sections[:MAX_SECTIONS]
    metadata = result.get("metadata", {})

    lines = ["<loqi-memory>", "## Relevant Project Knowledge (auto-retrieved by Loqi)", ""]

    for section in sections:
        title = section.get("title", "Untitled")
        content = section.get("content", "")
        parent_id = section.get("parent_id", "")
        score = section.get("score", 0.0)

        # Truncate long content
        if len(content) > MAX_CONTENT_CHARS:
            content = content[:MAX_CONTENT_CHARS] + "..."

        # Show source document if available
        source = f" (from {parent_id})" if parent_id else ""
        lines.append(f"### {title}{source}")
        lines.append(content.strip())
        lines.append("")

    triggered = result.get("triggered", [])
    if triggered:
        lines.append(f"_Triggers fired: {len(triggered)} | "
                     f"Semantic candidates: {metadata.get('semantic_candidates', '?')} | "
                     f"Graph discovered: {metadata.get('graph_discovered', '?')}_")
        lines.append("")

    lines.append("</loqi-memory>")
    return "\n".join(lines)


def format_status(status_data: dict) -> str:
    """Format status for human-readable display."""
    if not status_data:
        return "Loqi server is not responding."

    lines = ["Loqi Memory Status", ""]

    uptime = status_data.get("uptime_seconds", 0)
    mins = uptime // 60
    lines.append(f"Server uptime: {mins}m {uptime % 60}s")
    lines.append(f"Model loaded: {status_data.get('model_loaded', False)}")

    project = status_data.get("project", {})
    if project:
        lines.append("")
        lines.append("Project Memory:")
        lines.append(f"  Sections: {project.get('sections', 0)}")
        lines.append(f"  Nodes: {project.get('nodes', 0)}")
        lines.append(f"  Edges: {project.get('edges', 0)}")
        lines.append(f"  Triggers (explicit): {project.get('triggers_explicit', 0)}")
        lines.append(f"  Triggers (learned): {project.get('triggers_hebbian', 0)}")
        lines.append(f"  Episodes logged: {project.get('episodes', 0)}")

    return "\n".join(lines)
