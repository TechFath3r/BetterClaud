#!/usr/bin/env python3
"""Stop hook — nudge Claude to summarize the session before ending."""

import json
import sys

message = {
    "systemMessage": (
        "Session ending. Please:\n"
        "1. Call store_memory for any key learnings, decisions, or preferences discovered.\n"
        "2. Call log_session with a brief summary of what was accomplished."
    )
}

print(json.dumps(message))
