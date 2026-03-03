#!/usr/bin/env python3
"""Hive CLI — Telegram bridge for coding agents."""

import argparse
import asyncio
import os
import sys
from pathlib import Path

import onnx_asr
import requests
from dotenv import load_dotenv
from loguru import logger

from daemon import run as run_daemon
from telegram_api import TelegramBot


ENV_PATH = Path(__file__).parent / ".env"


def cmd_init():
    """Interactive setup: create a Telegram bot and connect to a group."""
    print("=== Hive Setup ===\n")
    print("1. Open @BotFather in Telegram")
    print("2. Create a bot: /newbot")
    print("3. Copy the token")
    token = input("\nPaste bot token: ").strip()

    bot = TelegramBot(token)
    me = bot.get_me()
    if not me.get("ok"):
        print("Error: invalid token")
        sys.exit(1)
    print(f"Bot: @{me['result']['username']}\n")

    print("4. Create a group in Telegram")
    print("5. Enable topics (Group settings -> Topics)")
    print("6. Add the bot to the group as admin")
    print("7. Send any message in the group")
    input("\nPress Enter when ready...")

    print("Detecting group chat_id...")
    updates = bot.get_updates(timeout=10)
    chat_id = None
    for u in updates.get("result", []):
        msg = u.get("message", {})
        # Handle group -> supergroup migration
        if msg.get("migrate_to_chat_id"):
            chat_id = msg["migrate_to_chat_id"]
            break
        chat = msg.get("chat", {})
        if chat.get("type") in ("supergroup", "group"):
            chat_id = chat["id"]
            break

    if not chat_id:
        print("Could not detect chat_id automatically.")
        chat_id = input("Enter the group chat_id manually: ").strip()

    chat_id = int(chat_id)

    # Detect owner user_id from the setup message
    owner_id = None
    for u in updates.get("result", []):
        msg = u.get("message", {})
        sender = msg.get("from", {})
        if sender.get("id"):
            owner_id = sender["id"]
            break
    if owner_id:
        print(f"Owner: {owner_id}")
    else:
        print("Warning: could not detect owner_id")
    result = bot.send_message(chat_id, "Hive connected. Bot is ready.")
    if not result.get("ok"):
        # Group upgraded to supergroup — use the new chat_id
        migrate_id = (result.get("parameters") or {}).get("migrate_to_chat_id")
        if migrate_id:
            chat_id = migrate_id
            print(f"Group migrated to supergroup, using chat_id: {chat_id}")
            result = bot.send_message(chat_id, "Hive connected. Bot is ready.")
        if not result.get("ok"):
            print(f"Warning: test message failed: {result}")

    env_lines = f"TELEGRAM_BOT_TOKEN={token}\nTELEGRAM_CHAT_ID={chat_id}\n"
    if owner_id:
        env_lines += f"TELEGRAM_OWNER_ID={owner_id}\n"
    ENV_PATH.write_text(env_lines)
    print(f"\nConfig saved to {ENV_PATH}")

    print("\nDownloading ASR model for voice transcription...")
    onnx_asr.load_model("nemo-parakeet-tdt-0.6b-v3")
    print("ASR model ready.")

    print("\nRun: python hive.py run")


def cmd_run():
    """Start the Hive daemon (Telegram polling + HTTP API)."""
    load_dotenv(ENV_PATH)
    token = os.environ.get("TELEGRAM_BOT_TOKEN")
    chat_id = os.environ.get("TELEGRAM_CHAT_ID")
    if not token or not chat_id:
        print("Error: run 'python hive.py init' first")
        sys.exit(1)

    owner_id = os.environ.get("TELEGRAM_OWNER_ID")
    owner_id = int(owner_id) if owner_id else None

    logger.info("Starting Hive daemon (chat_id={}, owner_id={})", chat_id, owner_id)
    asyncio.run(run_daemon(token, int(chat_id), owner_id=owner_id))


def cmd_status():
    """Check if the daemon is running."""
    try:
        r = requests.get("http://127.0.0.1:7433/health", timeout=2)
        if r.json().get("ok"):
            print("Daemon: running")
        else:
            print("Daemon: error")
    except requests.ConnectionError:
        print("Daemon: not running")


def main():
    parser = argparse.ArgumentParser(
        prog="hive", description="Telegram bridge for coding agents"
    )
    sub = parser.add_subparsers(dest="command")
    sub.add_parser("init", help="Interactive setup")
    sub.add_parser("run", help="Start the daemon")
    sub.add_parser("status", help="Check daemon status")

    args = parser.parse_args()
    commands = {"init": cmd_init, "run": cmd_run, "status": cmd_status}
    fn = commands.get(args.command)
    if fn:
        fn()
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
