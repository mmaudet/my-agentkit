# my-agentkit

Collection of portable AI agent skills and tools. Designed to work with [Hermes Agent](https://github.com/NousResearch/hermes-agent), but adaptable to other AI agent platforms (Claude Code, OpenAI Agents, LangChain, etc.).

## Tools

### Matrix (`tools/matrix_tool.py`)

Full Matrix protocol integration for AI agents. Lets your agent read notifications, list rooms, read messages, and send messages on any Matrix homeserver.

**Features:**
- `matrix_get_notifications` — Check pending mentions and highlights
- `matrix_list_rooms` — Search joined rooms by name
- `matrix_read_messages` — Read recent messages from a room
- `matrix_send_message` — Send a message to a room

**Works with:** Any Matrix homeserver (Synapse, Conduit, Dendrite, matrix.org, Twake Chat)

**Setup:**

```bash
# Install dependency
pip install 'matrix-nio[e2e]'

# Set environment variables
export MATRIX_HOMESERVER=https://matrix.example.com
export MATRIX_ACCESS_TOKEN=syt_your_token_here
```

**For Hermes Agent:**

1. Copy `tools/matrix_tool.py` to `~/.hermes/hermes-agent/tools/`
2. Add `"tools.matrix_tool"` to the `_modules` list in `model_tools.py`
3. Add `matrix` to your `platform_toolsets.cli` list in `config.yaml`
4. Restart the gateway: `hermes gateway restart`

## Installation

```bash
git clone https://github.com/mmaudet/my-agentkit.git
```

Each tool is self-contained. Copy what you need into your agent's tools directory.

## License

MIT License — see [LICENSE](LICENSE) for details.
