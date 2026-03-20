#!/usr/bin/env python3
"""PostCompact hook — remind Claude that memory tools exist after context compaction."""

import json

message = {
    "systemMessage": (
        "Context was compacted. You may have lost earlier context. "
        "Use recall_memory to retrieve relevant memories from previous sessions."
    )
}

print(json.dumps(message))
