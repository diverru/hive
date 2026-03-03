# Hive

Telegram bridge for Claude Code agents. Talk to your coding agents via Telegram — send text and voice messages, get progress updates, and manage multiple agents from a single Telegram group.

## How it works

```
Claude Code  →  MCP server (hive_mcp.py)  →  HTTP API (daemon.py)  →  Telegram Bot
   agent          stdio transport              localhost:7433          forum topics
```

- Each Claude Code session gets its own Telegram **forum topic**
- Multiple agents can run simultaneously — each in its own topic
- **Voice messages** are automatically transcribed using [Parakeet TDT](https://huggingface.co/istupakov/parakeet-tdt-0.6b-v3-onnx) (local, offline)
- Agents auto-register on first message — no manual setup per session

## Features

- **Text messaging** — send/receive messages via Telegram topics
- **Voice transcription** — send voice messages, agent receives text (OGG → WAV → ASR)
- **Topic naming** — agents name their topics based on current task
- **ask_user** — agent sends a question and waits for your reply
- **Progress reports** — structured status updates
- **Auto-registration** — new agents create their own topics automatically
- **Stable agent IDs** — based on parent process, survives MCP restarts

## Quick Start

```bash
# 1. Clone and install
git clone https://github.com/diverru/hive.git
cd hive
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

# 2. Setup (creates Telegram bot, downloads ASR model)
python hive.py init

# 3. Start the daemon
python hive.py run

# 4. Enable MCP in Claude Code
# Add to .claude/settings.local.json:
# {
#   "enableAllProjectMcpServers": true,
#   "enabledMcpjsonServers": ["hive"]
# }
# Copy .mcp.json to your project root
```

## Adding to Your Project

1. Copy `.mcp.json` to your project root
2. Enable the MCP server in `.claude/settings.local.json`
3. Copy the Telegram instructions from `telegram-instructions.md` into your project's `CLAUDE.md`
4. Make sure the Hive daemon is running (`python hive.py run`)

## Requirements

- Python 3.11+
- ffmpeg (for voice message conversion)
- Telegram bot + supergroup with topics enabled
- ~2.5 GB disk space for ASR model

## Architecture

| File | Description |
|------|-------------|
| `hive.py` | CLI entry point (`init`, `run`, `status`) |
| `daemon.py` | Telegram polling + HTTP API server |
| `hive_mcp.py` | MCP server (stdio) — tools for Claude Code |
| `telegram_api.py` | Telegram Bot API wrapper |
| `storage.py` | SQLite storage (agents, messages, state) |

Data is stored in `~/.hive/hive.db`.
