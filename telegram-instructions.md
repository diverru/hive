## Telegram Communication (Hive MCP)

When Hive MCP tools are available (`send_message`, `ask_user`, etc.):

- If the user asks to communicate via Telegram, **all** interaction goes
  through Telegram. Every action ends with `ask_user()`.
- On the first message, set the topic name to **"project: task"**
  (e.g. "hive: Fix auth bug", "myapp: Add dark mode").
  Include repo name and task context in the first message.
- **Duplicate your responses and questions in the Claude Code chat** so the
  user can follow along in the IDE without switching to Telegram.
- Before calling `ask_user()`, check `get_messages()` for any updates.
- **NEVER end a turn with `send_message()` — always end with `ask_user()`.**
- If `ask_user()` times out, use `wait_for_reply()` to keep waiting.
  Do NOT call `ask_user()` again (it re-sends the question).
  Every few iterations, optionally `send_message()` a playful reminder.
- For long-running tasks (>1 min), send progress updates via Telegram
  even if the user didn't explicitly ask for Telegram communication.

### MCP Tools

- `set_topic_name(name)` — set the Telegram topic name for this session
- `send_message(text, topic_name="")` — send a message; also returns unread user messages
- `get_messages(limit)` — get recent messages from the user
- `ask_user(question)` — ask a question and wait for the user's reply
- `wait_for_reply(wait_seconds)` — keep waiting without re-sending the question
- `report(summary, details)` — send a structured progress report
