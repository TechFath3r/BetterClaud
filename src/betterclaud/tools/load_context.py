"""MCP tool: load a context profile from the context directory."""

import os
from pathlib import Path

from .. import config


def load_context(profile: str) -> str:
    """Load a context profile with instructions for a specific use case.

    Context profiles are markdown files in the configured context directory.
    Each profile contains instructions that shape how Claude should behave.

    Args:
        profile: Profile name (e.g. "repair", "dev", "casual"). Maps to {profile}.md.
    """
    if not config.CONTEXT_DIR:
        return "Context profiles not configured. Set BETTERCLAUD_CONTEXT_DIR to enable."

    ctx_dir = Path(config.CONTEXT_DIR)
    if not ctx_dir.is_dir():
        return f"Context directory does not exist: {ctx_dir}"

    profile_path = ctx_dir / f"{profile}.md"
    if profile_path.is_file():
        return profile_path.read_text(encoding="utf-8")

    # List available profiles
    available = sorted(
        p.stem for p in ctx_dir.glob("*.md") if p.is_file()
    )
    if available:
        return f"Profile '{profile}' not found. Available profiles: {', '.join(available)}"
    return f"Profile '{profile}' not found. No profiles found in {ctx_dir}"
