#!/usr/bin/env python3
"""Hive MCP server — exposes Telegram tools to Claude Code agents."""

import hashlib
import os
import subprocess
import time

import requests
from mcp.server.fastmcp import FastMCP

API_URL = os.environ.get("HIVE_API_URL", "http://127.0.0.1:7433")
AGENT_NAME = os.environ.get("HIVE_AGENT_NAME", "Claude Agent")


def _make_agent_id() -> str:
    """Stable agent ID from parent PID + its start time.
    Same Claude Code session = same ID, even across MCP restarts.
    PID reuse is safe because start time will differ."""
    ppid = os.getppid()
    try:
        lstart = subprocess.check_output(
            ["ps", "-p", str(ppid), "-o", "lstart="],
            text=True,
        ).strip()
        key = f"{ppid}-{lstart}"
    except Exception:
        key = str(ppid)
    return f"agent-{hashlib.sha256(key.encode()).hexdigest()[:8]}"


AGENT_ID = _make_agent_id()

mcp = FastMCP("Hive")


def _api(method: str, path: str, **kwargs) -> dict:
    """Make a request to the Hive daemon API.
    Passes agent name in header for auto-registration."""
    headers = kwargs.pop("headers", {})
    headers["X-Agent-Name"] = AGENT_NAME
    resp = getattr(requests, method)(f"{API_URL}{path}", headers=headers, **kwargs)
    return resp.json()


@mcp.tool()
def send_message(text: str, topic_name: str = "") -> str:
    """Send a message to the user via Telegram. Use this to report progress,
    ask questions, or share results. The message appears in your dedicated
    Telegram topic.

    Set topic_name on the first message to give the topic a meaningful name
    describing your current task (e.g. 'Fix auth bug', 'Add dark mode')."""
    resp = _api("post", f"/agents/{AGENT_ID}/messages", json={"text": text})
    if topic_name and resp.get("ok"):
        _api("put", f"/agents/{AGENT_ID}/topic", json={"name": topic_name})
    return "Message sent" if resp.get("ok") else f"Error: {resp}"


@mcp.tool()
def get_messages(limit: int = 10) -> list[dict]:
    """Get recent messages from the user via Telegram. Returns messages
    the user sent in your Telegram topic. Use this to check if the user
    has replied to your questions."""
    resp = _api("get", f"/agents/{AGENT_ID}/messages", params={"limit": limit})
    return resp.get("messages", [])


@mcp.tool()
def ask_user(question: str, wait_seconds: int = 120) -> str:
    """Ask the user a question via Telegram and wait for their response.
    Sends the question, then polls for a reply (up to wait_seconds).
    Returns the user's answer or 'No response' if timeout."""
    _api(
        "post",
        f"/agents/{AGENT_ID}/messages",
        json={"text": f"Question: {question}"},
    )

    before = _api("get", f"/agents/{AGENT_ID}/messages", params={"limit": 1})
    last_id = before["messages"][0]["id"] if before.get("messages") else 0

    deadline = time.time() + wait_seconds
    while time.time() < deadline:
        time.sleep(3)
        after = _api(
            "get",
            f"/agents/{AGENT_ID}/messages",
            params={"limit": 1, "since_id": last_id},
        )
        if after.get("messages"):
            return after["messages"][0]["text"]

    return "No response (timeout)"


@mcp.tool()
def set_topic_name(name: str) -> str:
    """Set the Telegram topic name for this agent. Call this early
    in the conversation to give the topic a meaningful name that
    describes what you're working on (e.g. 'Fix auth bug',
    'Add dark mode', 'Refactor API')."""
    resp = _api(
        "put",
        f"/agents/{AGENT_ID}/topic",
        json={"name": name},
    )
    return "Topic renamed" if resp.get("ok") else f"Error: {resp}"


@mcp.tool()
def report(summary: str, details: str = "") -> str:
    """Send a structured progress report to the user via Telegram.
    Use after completing a significant task or milestone."""
    text = f"Report\n\n{summary}"
    if details:
        text += f"\n\n{details}"
    _api("post", f"/agents/{AGENT_ID}/messages", json={"text": text})
    return "Report sent"


if __name__ == "__main__":
    mcp.run(transport="stdio")
