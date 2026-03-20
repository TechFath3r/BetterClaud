"""MCP tool: write a session summary log."""

import hashlib
import os
import time
from datetime import datetime, timezone
from pathlib import Path

from .. import config


def session_log(
    summary: str,
    project: str = "general",
    title: str = "",
) -> str:
    """Write a session summary as a markdown file.

    If an Obsidian vault is configured, writes to the vault's session directory.
    Otherwise writes to ~/.local/share/betterclaud/sessions/.

    Args:
        summary: The session summary text.
        project: Project name for organization (default "general").
        title: Optional title for the session log.
    """
    now = datetime.now(timezone.utc)
    date_str = now.strftime("%Y-%m-%d")
    short_hash = hashlib.sha256(summary.encode()).hexdigest()[:8]

    filename = f"{date_str}_{project}_{short_hash}.md"

    # Determine output directory
    if config.VAULT_PATH:
        out_dir = Path(config.VAULT_PATH) / config.VAULT_SESSION_DIR
    else:
        out_dir = Path.home() / ".local" / "share" / "betterclaud" / "sessions"

    os.makedirs(out_dir, exist_ok=True)
    filepath = out_dir / filename

    # Build markdown
    display_title = title or f"Session: {project} ({date_str})"
    content = (
        f"---\n"
        f"created: {now.isoformat()}\n"
        f"project: {project}\n"
        f"tags: [claude-session]\n"
        f"---\n\n"
        f"# {display_title}\n\n"
        f"{summary}\n"
    )

    filepath.write_text(content, encoding="utf-8")

    return f"Session log written to {filepath}"
