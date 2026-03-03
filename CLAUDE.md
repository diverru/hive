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
- `wait_for_reply(wait_seconds)` — keep waiting without re-sending the question
- `report(summary, details)` — send a structured progress report

## When to Use Telegram

If the user says to communicate via Telegram (or mentions Telegram as the
communication channel), **all** interaction happens through Telegram:

- Use `send_message()` for progress updates as you work.
- **Duplicate your responses and questions in the Claude Code chat** so the
  user can follow along in the IDE without switching to Telegram.
- Before calling `ask_user()`, check `get_messages()` first — the user may
  have sent updates or new tasks while you were working.
- **Every time you finish an action or need input, call `ask_user()`.**
  Never use `send_message()` at the end — always `ask_user()` so the user
  can reply. This is the most important rule.
- Use `report()` for major milestones (optional, still follow with `ask_user()`).

If the user did NOT ask to communicate via Telegram, use it only for
long-running tasks (builds, tests, large refactors) where the user is
not watching the Claude Code session.

**How to use it:**

1. On the first message, call `set_topic_name()` with the **project name
   and task** (e.g. "hive: Fix auth bug", "myapp: Add dark mode").
   Also include the repo and task context in the first `send_message()`
   so the user knows which project and what you're working on.
2. Send progress updates via `send_message()` as you work.
3. When you need the user's input, use `ask_user()` — it sends a question
   and polls for a reply (up to 2 minutes by default).
4. Use `get_messages()` to check for new messages from the user
   if you expect they might have sent comments or corrections.
5. **NEVER end a turn with `send_message()` — always end with `ask_user()`
   so the user has a chance to respond via Telegram.**
6. If `ask_user()` returns a timeout, use `wait_for_reply()` to keep waiting.
   Do NOT call `ask_user()` again — that would re-send the question.
   Keep calling `wait_for_reply()` in a loop until the user responds.
   Every few iterations, optionally send a playful reminder via `send_message()`
   (emojis, hearts, jokes). Make the user smile when they come back. 💛
