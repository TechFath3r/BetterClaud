#!/usr/bin/env bash
set -euo pipefail

# BetterClaud Setup — One-command install
# Idempotent: safe to re-run.

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
VENV_DIR="$HOME/.local/share/betterclaud/venv"
CONFIG_DIR="$HOME/.config/betterclaud"
SETTINGS_FILE="$HOME/.claude/settings.json"

info()  { echo -e "\033[1;34m[betterclaud]\033[0m $*"; }
ok()    { echo -e "\033[1;32m[betterclaud]\033[0m $*"; }
warn()  { echo -e "\033[1;33m[betterclaud]\033[0m $*"; }
error() { echo -e "\033[1;31m[betterclaud]\033[0m $*"; exit 1; }

# --- Prerequisites ---

info "Checking prerequisites..."

command -v python3 >/dev/null 2>&1 || error "Python 3 is required but not found."

PY_VERSION=$(python3 -c 'import sys; print(f"{sys.version_info.major}.{sys.version_info.minor}")')
PY_MAJOR=$(echo "$PY_VERSION" | cut -d. -f1)
PY_MINOR=$(echo "$PY_VERSION" | cut -d. -f2)
if [ "$PY_MAJOR" -lt 3 ] || { [ "$PY_MAJOR" -eq 3 ] && [ "$PY_MINOR" -lt 10 ]; }; then
    error "Python >= 3.10 required, found $PY_VERSION"
fi
ok "Python $PY_VERSION"

# --- Ollama ---

if ! command -v ollama >/dev/null 2>&1; then
    info "Installing Ollama..."
    curl -fsSL https://ollama.ai/install.sh | sh
    ok "Ollama installed."
else
    ok "Ollama already installed."
fi

# Ensure ollama is running
if ! curl -sf http://localhost:11434/api/tags >/dev/null 2>&1; then
    info "Starting Ollama..."
    ollama serve &>/dev/null &
    sleep 3
    if ! curl -sf http://localhost:11434/api/tags >/dev/null 2>&1; then
        warn "Ollama may not be running. Start it with: ollama serve"
    fi
fi

# Pull embedding model
EMBED_MODEL="${BETTERCLAUD_EMBED_MODEL:-nomic-embed-text}"
if ollama list 2>/dev/null | grep -q "$EMBED_MODEL"; then
    ok "Model $EMBED_MODEL already pulled."
else
    info "Pulling $EMBED_MODEL (this may take a minute)..."
    ollama pull "$EMBED_MODEL"
    ok "Model $EMBED_MODEL ready."
fi

# --- Virtual Environment ---

if [ -d "$VENV_DIR" ]; then
    ok "Venv exists at $VENV_DIR"
else
    info "Creating venv at $VENV_DIR..."
    mkdir -p "$(dirname "$VENV_DIR")"
    python3 -m venv "$VENV_DIR"
    ok "Venv created."
fi

info "Installing betterclaud into venv..."
"$VENV_DIR/bin/pip" install --quiet --upgrade pip
"$VENV_DIR/bin/pip" install --quiet "$SCRIPT_DIR"
ok "Package installed."

# --- Config ---

mkdir -p "$CONFIG_DIR"
if [ ! -f "$CONFIG_DIR/.env" ]; then
    cp "$SCRIPT_DIR/.env.example" "$CONFIG_DIR/.env"
    info "Created $CONFIG_DIR/.env from template. Edit it to configure."
else
    ok "Config exists at $CONFIG_DIR/.env"
fi

# --- Register MCP Server ---

if command -v claude >/dev/null 2>&1; then
    info "Registering MCP server with Claude Code..."
    claude mcp remove betterclaud-memory 2>/dev/null || true
    claude mcp add --scope user betterclaud-memory -- "$VENV_DIR/bin/python3" -m betterclaud.server
    ok "MCP server registered."
else
    warn "Claude Code CLI not found. Register manually:"
    echo "  claude mcp add --scope user betterclaud-memory -- $VENV_DIR/bin/python3 -m betterclaud.server"
fi

# --- Hooks ---

info "Configuring hooks..."
mkdir -p "$HOME/.claude"

# Ensure hooks are executable
chmod +x "$SCRIPT_DIR/hooks/session_end.py"
chmod +x "$SCRIPT_DIR/hooks/post_compact.py"

# Merge hooks into settings.json
python3 - "$SETTINGS_FILE" "$SCRIPT_DIR" <<'PYEOF'
import json
import sys
from pathlib import Path

settings_path = Path(sys.argv[1])
script_dir = sys.argv[2]

settings = {}
if settings_path.exists():
    try:
        settings = json.loads(settings_path.read_text())
    except (json.JSONDecodeError, OSError):
        settings = {}

hooks = settings.get("hooks", {})

# Stop hook
stop_hooks = hooks.get("Stop", [])
stop_cmd = f"python3 {script_dir}/hooks/session_end.py"
if not any(h.get("command") == stop_cmd for h in stop_hooks):
    stop_hooks.append({"command": stop_cmd})
hooks["Stop"] = stop_hooks

# PostCompact hook
compact_hooks = hooks.get("PostCompact", [])
compact_cmd = f"python3 {script_dir}/hooks/post_compact.py"
if not any(h.get("command") == compact_cmd for h in compact_hooks):
    compact_hooks.append({"command": compact_cmd})
hooks["PostCompact"] = compact_hooks

settings["hooks"] = hooks

settings_path.parent.mkdir(parents=True, exist_ok=True)
settings_path.write_text(json.dumps(settings, indent=2) + "\n")
PYEOF
ok "Hooks configured in $SETTINGS_FILE"

# --- CLAUDE.md template ---

GLOBAL_CLAUDE_MD="$HOME/.claude/CLAUDE.md"
if [ ! -f "$GLOBAL_CLAUDE_MD" ]; then
    read -r -p "$(echo -e '\033[1;34m[betterclaud]\033[0m') Copy CLAUDE.md template to $GLOBAL_CLAUDE_MD? [y/N] " response
    if [[ "$response" =~ ^[Yy]$ ]]; then
        cp "$SCRIPT_DIR/CLAUDE.md.template" "$GLOBAL_CLAUDE_MD"
        ok "CLAUDE.md installed."
    fi
else
    info "Global CLAUDE.md already exists — not overwriting. See CLAUDE.md.template for reference."
fi

# --- Optional: Vault setup ---

if [ -z "${BETTERCLAUD_VAULT_PATH:-}" ]; then
    read -r -p "$(echo -e '\033[1;34m[betterclaud]\033[0m') Set up Obsidian vault path? [y/N] " response
    if [[ "$response" =~ ^[Yy]$ ]]; then
        read -r -p "  Vault path: " vault_path
        if [ -d "$vault_path" ]; then
            # Add to .env
            echo "BETTERCLAUD_VAULT_PATH=$vault_path" >> "$CONFIG_DIR/.env"
            ok "Vault path set. Run 'betterclaud-index' to index it."
        else
            warn "Path '$vault_path' does not exist. Skipping."
        fi
    fi
fi

# --- Verify ---

echo ""
info "Verifying installation..."

# Check Ollama
if curl -sf http://localhost:11434/api/tags >/dev/null 2>&1; then
    ok "Ollama is responding."
else
    warn "Ollama is not responding at localhost:11434."
fi

# Check embedding
if "$VENV_DIR/bin/python3" -c "from betterclaud.embeddings import embed_one; v = embed_one('test'); print(f'Embedding dim: {len(v)}')" 2>/dev/null; then
    ok "Embeddings working."
else
    warn "Embedding test failed. Is Ollama running with $EMBED_MODEL?"
fi

# Check MCP registration
if command -v claude >/dev/null 2>&1; then
    if claude mcp list 2>/dev/null | grep -q betterclaud-memory; then
        ok "MCP server registered."
    else
        warn "MCP server not showing in 'claude mcp list'."
    fi
fi

echo ""
ok "Setup complete! Start a new Claude Code session to use memory tools."
