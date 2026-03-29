#!/bin/bash
# install.sh — Install my-agentkit tools into Hermes Agent
# Usage: ./install.sh [tool_name]
# Example: ./install.sh matrix_tool

set -e

HERMES_TOOLS_DIR="${HERMES_HOME:-$HOME/.hermes}/hermes-agent/tools"
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"

if [ ! -d "$HERMES_TOOLS_DIR" ]; then
    echo "Error: Hermes tools directory not found at $HERMES_TOOLS_DIR"
    echo "Set HERMES_HOME if Hermes is installed elsewhere."
    exit 1
fi

install_tool() {
    local tool="$1"
    local src="$SCRIPT_DIR/tools/${tool}.py"
    local dst="$HERMES_TOOLS_DIR/${tool}.py"

    if [ ! -f "$src" ]; then
        echo "Error: Tool not found: $src"
        return 1
    fi

    cp "$src" "$dst"
    echo "Installed: $tool -> $dst"

    # Check if already registered in model_tools.py
    local model_tools="$HERMES_TOOLS_DIR/../model_tools.py"
    if [ -f "$model_tools" ] && ! grep -q "tools.${tool}" "$model_tools"; then
        echo "Note: Add \"tools.${tool}\" to _modules list in model_tools.py"
    fi
}

if [ -n "$1" ]; then
    install_tool "$1"
else
    echo "Installing all tools..."
    for f in "$SCRIPT_DIR"/tools/*_tool.py; do
        tool=$(basename "$f" .py)
        install_tool "$tool"
    done
fi

echo ""
echo "Done. Restart Hermes gateway to activate: hermes gateway restart"
