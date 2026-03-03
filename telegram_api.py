#!/usr/bin/env python3
"""Telegram Bot API wrapper."""

from pathlib import Path

import requests


class TelegramBot:
    def __init__(self, token: str):
        self.token = token
        self.base_url = f"https://api.telegram.org/bot{token}"

    def get_me(self) -> dict:
        """Verify bot token. Returns bot info."""
        return requests.get(f"{self.base_url}/getMe").json()

    def send_message(
        self, chat_id: int, text: str, message_thread_id: int = None
    ) -> dict:
        """Send a message. message_thread_id targets a specific forum topic."""
        payload = {"chat_id": chat_id, "text": text, "parse_mode": "Markdown"}
        if message_thread_id:
            payload["message_thread_id"] = message_thread_id
        return requests.post(
            f"{self.base_url}/sendMessage",
            json=payload,
        ).json()

    def create_forum_topic(self, chat_id: int, name: str) -> dict:
        """Create a new forum topic in the group."""
        return requests.post(
            f"{self.base_url}/createForumTopic",
            json={"chat_id": chat_id, "name": name},
        ).json()

    def edit_forum_topic(self, chat_id: int, message_thread_id: int, name: str) -> dict:
        """Rename a forum topic."""
        return requests.post(
            f"{self.base_url}/editForumTopic",
            json={
                "chat_id": chat_id,
                "message_thread_id": message_thread_id,
                "name": name,
            },
        ).json()

    def get_updates(self, offset: int = None, timeout: int = 30) -> dict:
        """Long poll for new updates.
        timeout — how long Telegram holds the connection (seconds).
        offset — ID of the first update to return (last processed + 1).
        """
        params = {"timeout": timeout}
        if offset is not None:
            params["offset"] = offset
        return requests.get(
            f"{self.base_url}/getUpdates", params=params, timeout=timeout + 5
        ).json()

    def download_file(self, file_id: str, dest: Path) -> Path:
        """Download a file from Telegram by file_id.
        Uses getFile to get the path, then downloads it.
        """
        info = requests.get(
            f"{self.base_url}/getFile", params={"file_id": file_id}
        ).json()
        file_path = info["result"]["file_path"]
        url = f"https://api.telegram.org/file/bot{self.token}/{file_path}"
        resp = requests.get(url)
        resp.raise_for_status()
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_bytes(resp.content)
        return dest
