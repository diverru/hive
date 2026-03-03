# Hive — Telegram Bridge

## Setup

1. Install dependencies:

   ```bash
   python -m venv .venv
   source .venv/bin/activate
   pip install -r requirements.txt
   ```

2. Run initial setup (creates Telegram bot, connects to group):

   ```bash
   python hive.py init
   ```

3. Start the daemon (keep running in a separate terminal):

   ```bash
   python hive.py run
   ```

4. Enable the MCP server in Claude Code:
   - Open VSCode settings or `.claude/settings.local.json`
   - Add `"hive"` to `enabledMcpjsonServers`
   - Set `"enableAllProjectMcpServers": true`
   - Or: in Claude Code plugin, go to MCP Servers and enable "hive"

5. Restart Claude Code to pick up the MCP server.

## MCP Tools

You have access to Telegram communication tools via Hive MCP:

- `set_topic_name(name)` — set the Telegram topic name for this session
- `send_message(text)` — send a message to the user
- `get_messages(limit)` — get recent messages from the user
- `ask_user(question)` — ask a question and wait for the user's reply
- `report(summary, details)` — send a structured progress report

## When to Use Telegram

Use Telegram for communication when the user is not actively watching the
Claude Code session (long tasks, background work, waiting for builds, etc.).

**Always use Telegram when:**

- The task takes more than ~1 minute (builds, tests, large refactors)
- You finished a task and need the user's feedback before continuing
- You hit a blocker and need the user's decision
- You are running something in the background and have results

**How to use it:**

1. On the first message, call `set_topic_name()` or pass `topic_name` to
   `send_message()` to give the topic a short, meaningful name
   (e.g. "Fix auth bug", "Add dark mode").
2. Send progress updates via `send_message()` as you work.
3. When you need the user's input, use `ask_user()` — it sends a question
   and polls for a reply (up to 2 minutes by default).
4. Use `report()` when you complete a significant milestone.
5. Use `get_messages()` to check for new messages from the user
   if you expect they might send comments or corrections.
