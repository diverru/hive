#!/usr/bin/env python3
"""Hive daemon — Telegram polling + HTTP API."""

import asyncio
import subprocess
import sys
import tempfile
from pathlib import Path

import onnx_asr
from aiohttp import web
from loguru import logger

from storage import Storage
from telegram_api import TelegramBot

logger.remove()
logger.add(sys.stderr, level="INFO")


_asr_model = None


def _ogg_to_wav(ogg_path: Path) -> Path:
    """Convert OGG/Opus to WAV using ffmpeg."""
    wav_path = ogg_path.with_suffix(".wav")
    subprocess.run(
        [
            "ffmpeg",
            "-y",
            "-i",
            str(ogg_path),
            "-ar",
            "16000",
            "-ac",
            "1",
            str(wav_path),
        ],
        check=True,
        capture_output=True,
    )
    return wav_path


def transcribe_voice(audio_path: Path) -> str:
    """Transcribe a voice message using Parakeet TDT v3 via onnx-asr."""
    global _asr_model
    if _asr_model is None:
        logger.info("Loading Parakeet TDT v3 model (first time)...")
        _asr_model = onnx_asr.load_model("nemo-parakeet-tdt-0.6b-v3")
    wav_path = _ogg_to_wav(audio_path)
    try:
        return _asr_model.recognize(str(wav_path))
    finally:
        wav_path.unlink(missing_ok=True)


class HiveDaemon:
    def __init__(self, bot: TelegramBot, storage: Storage, chat_id: int):
        self.bot = bot
        self.storage = storage
        self.chat_id = chat_id

    # --- Telegram polling ---

    async def poll_telegram(self):
        """Long-poll Telegram for new messages, store incoming ones."""
        offset = self.storage.get_update_offset()
        logger.info("Starting Telegram polling (offset={})", offset)

        while True:
            try:
                resp = await asyncio.to_thread(
                    self.bot.get_updates, offset=offset, timeout=30
                )
                for update in resp.get("result", []):
                    offset = update["update_id"] + 1
                    self.storage.set_update_offset(offset)
                    await self._handle_update(update)
            except Exception:
                logger.exception("Polling error, retrying in 5s")
                await asyncio.sleep(5)

    async def _handle_update(self, update: dict):
        msg = update.get("message")
        if not msg:
            return

        topic_id = msg.get("message_thread_id")
        if not topic_id:
            return

        agent = self.storage.get_agent_by_topic(topic_id)
        if not agent:
            return

        # Voice message
        voice = msg.get("voice")
        if voice:
            try:
                text = await self._transcribe_voice_message(voice["file_id"])
            except Exception:
                logger.exception("Voice transcription failed for topic {}", topic_id)
                text = "[voice transcription failed]"
            else:
                logger.info("Voice from topic {}: {}", topic_id, text)
        else:
            text = msg.get("text")

        if text:
            self.storage.save_message(
                agent["id"],
                "in",
                text,
                telegram_message_id=msg.get("message_id"),
            )

    async def _transcribe_voice_message(self, file_id: str) -> str:
        with tempfile.NamedTemporaryFile(suffix=".ogg", delete=False) as f:
            tmp_path = Path(f.name)
        try:
            await asyncio.to_thread(self.bot.download_file, file_id, tmp_path)
            return await asyncio.to_thread(transcribe_voice, tmp_path)
        finally:
            tmp_path.unlink(missing_ok=True)

    # --- HTTP API ---

    async def _get_or_create_agent(self, agent_id: str, request: web.Request):
        """Return agent dict, auto-registering with a new topic if needed.
        Agent name comes from X-Agent-Name header or falls back to agent_id."""
        agent = self.storage.get_agent(agent_id)
        if agent:
            return agent

        name = request.headers.get("X-Agent-Name", agent_id)
        result = await asyncio.to_thread(
            self.bot.create_forum_topic, self.chat_id, name
        )
        if not result.get("ok"):
            logger.error("Failed to create topic for '{}': {}", agent_id, result)
            return None

        topic_id = result["result"]["message_thread_id"]
        self.storage.register_agent(agent_id, name, topic_id)
        logger.info("Auto-registered agent '{}' (topic {})", agent_id, topic_id)
        return self.storage.get_agent(agent_id)

    @web.middleware
    async def _log_requests(self, request, handler):
        resp = await handler(request)
        if resp.status >= 400:
            logger.warning(
                "{} {} -> {} {}",
                request.method,
                request.path,
                resp.status,
                resp.text,
            )
        else:
            logger.debug(
                "{} {} -> {}",
                request.method,
                request.path,
                resp.status,
            )
        return resp

    def create_app(self) -> web.Application:
        app = web.Application(middlewares=[self._log_requests])
        app.router.add_get("/health", self._handle_health)
        app.router.add_post(
            "/agents/{agent_id}/messages",
            self._handle_send,
        )
        app.router.add_get(
            "/agents/{agent_id}/messages",
            self._handle_get_messages,
        )
        app.router.add_put(
            "/agents/{agent_id}/topic",
            self._handle_rename_topic,
        )
        app.router.add_get(
            "/agents/{agent_id}/cursor",
            self._handle_get_cursor,
        )
        app.router.add_put(
            "/agents/{agent_id}/cursor",
            self._handle_set_cursor,
        )
        return app

    async def _handle_health(self, request: web.Request) -> web.Response:
        return web.json_response({"ok": True})

    async def _handle_send(
        self,
        request: web.Request,
    ) -> web.Response:
        agent_id = request.match_info["agent_id"]
        data = await request.json()
        text = data["text"]

        agent = await self._get_or_create_agent(agent_id, request)
        if not agent:
            return web.json_response(
                {"ok": False, "error": "failed to create agent"},
                status=500,
            )

        await asyncio.to_thread(
            self.bot.send_message,
            self.chat_id,
            text,
            agent["topic_id"],
        )
        self.storage.save_message(agent_id, "out", text)
        return web.json_response({"ok": True})

    async def _handle_get_messages(
        self,
        request: web.Request,
    ) -> web.Response:
        agent_id = request.match_info["agent_id"]
        limit = int(request.query.get("limit", 20))
        since_id = request.query.get("since_id")
        since_id = int(since_id) if since_id is not None else None

        messages = self.storage.get_messages(
            agent_id,
            limit,
            since_id,
        )
        return web.json_response({"messages": messages})

    async def _handle_rename_topic(
        self,
        request: web.Request,
    ) -> web.Response:
        agent_id = request.match_info["agent_id"]
        data = await request.json()
        name = data["name"]

        agent = await self._get_or_create_agent(agent_id, request)
        if not agent:
            return web.json_response(
                {"ok": False, "error": "failed to create agent"},
                status=500,
            )

        result = await asyncio.to_thread(
            self.bot.edit_forum_topic,
            self.chat_id,
            agent["topic_id"],
            name,
        )
        if not result.get("ok"):
            return web.json_response(
                {"ok": False, "error": result},
                status=500,
            )

        logger.info("Renamed topic for '{}' to '{}'", agent_id, name)
        return web.json_response({"ok": True})

    async def _handle_get_cursor(
        self,
        request: web.Request,
    ) -> web.Response:
        agent_id = request.match_info["agent_id"]
        cursor = self.storage.get_cursor(agent_id)
        return web.json_response({"cursor": cursor})

    async def _handle_set_cursor(
        self,
        request: web.Request,
    ) -> web.Response:
        agent_id = request.match_info["agent_id"]
        data = await request.json()
        self.storage.set_cursor(agent_id, data["cursor"])
        return web.json_response({"ok": True})


async def run(token: str, chat_id: int, host: str = "127.0.0.1", port: int = 7433):
    bot = TelegramBot(token)
    storage = Storage()
    daemon = HiveDaemon(bot, storage, chat_id)

    app = daemon.create_app()
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, host, port)
    await site.start()
    logger.info("HTTP API listening on {}:{}", host, port)

    await daemon.poll_telegram()
