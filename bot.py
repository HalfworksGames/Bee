import asyncio
import collections
import logging
import re
import sys
from typing import Deque, Dict, Tuple
import discord

from config import config
from llama_client import LlamaClient

# Setup logging
logging.basicConfig(
    level=getattr(logging, config.log_level, logging.INFO),
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("BeeBot")

MENTION_REGEX = re.compile(r"<@&?!?([0-9]+)>")


class BeeBot(discord.Client):
    """Discord Bot that monitors mentions, enqueues incoming requests, and buzzes via BeeLLM."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.message_queue: asyncio.Queue[Tuple[discord.Message, str]] = asyncio.Queue(
            maxsize=config.queue_size
        )
        self.llama_client = LlamaClient(
            base_url=config.llama_server_url,
            model_name=config.model_name,
        )
        self.worker_task: asyncio.Task | None = None
        # Per-channel history tracking: deque of {"role": "user"|"assistant", "content": ...}
        self.channel_histories: Dict[int, Deque[dict]] = collections.defaultdict(
            lambda: collections.deque(maxlen=max(2, config.history_limit * 2))
        )

    async def setup_hook(self):
        """Called by discord.py when client starts up, before on_ready."""
        self.worker_task = asyncio.create_task(self.queue_worker(), name="BeeQueueWorker")
        logger.info(f"Worker task started. Queue maxsize: {config.queue_size}")

    async def on_ready(self):
        channel_count = sum(len(guild.text_channels) for guild in self.guilds)
        logger.info(f"Logged in as {self.user} (ID: {self.user.id})")
        logger.info(f"Connected to {len(self.guilds)} guild(s) with {channel_count} visible text channel(s).")
        logger.info(f"Targeting llama.cpp server at: {config.llama_server_url}")

    async def on_message(self, message: discord.Message):
        # Ignore own messages or messages from other bots
        if message.author.bot or message.author == self.user:
            return

        channel_name = getattr(message.channel, "name", str(message.channel))

        # Check if the bot is mentioned via user mention
        is_user_mention = self.user in message.mentions or (
            self.user and any(m.id == self.user.id for m in message.mentions)
        )

        # Check if the bot is mentioned via role mention (e.g. @Bee role)
        is_role_mention = False
        if message.guild and message.guild.me and message.role_mentions:
            bot_role_ids = {r.id for r in message.guild.me.roles}
            is_role_mention = any(role.id in bot_role_ids for role in message.role_mentions)

        # Check if message is a direct reply to one of the bot's messages
        is_reply_to_bot = False
        if message.reference and message.reference.resolved:
            resolved = message.reference.resolved
            if isinstance(resolved, discord.Message) and resolved.author == self.user:
                is_reply_to_bot = True

        # Check if this is a DM
        is_dm = isinstance(message.channel, discord.DMChannel)

        is_mentioned = is_user_mention or is_role_mention or is_reply_to_bot or is_dm

        logger.info(
            f"Message in #{channel_name} from {message.author}: {message.content!r} (mentioned={is_mentioned})"
        )

        if not is_mentioned:
            return

        # Extract message content with mentions cleaned out
        clean_prompt = MENTION_REGEX.sub("", message.content).strip()
        if not clean_prompt:
            clean_prompt = "hi bee!"

        # Enqueue the message
        try:
            self.message_queue.put_nowait((message, clean_prompt))
            current_size = self.message_queue.qsize()
            logger.info(f"Enqueued message from {message.author}. Queue depth: {current_size}/{config.queue_size}")
            # Add a subtle reaction to indicate message was enqueued
            try:
                await message.add_reaction("🐝")
            except Exception:
                pass
        except asyncio.QueueFull:
            logger.warning(f"Queue is full ({config.queue_size}). Dropping message from {message.author}.")
            try:
                await message.reply(
                    "*bzzzt... Bee is overwhelmed right now! Please try again in a moment.*",
                    mention_author=False,
                )
            except Exception as e:
                logger.error(f"Failed to send queue full reply: {e}")

    async def queue_worker(self):
        """Continuously processes messages from the queue and queries llama.cpp."""
        logger.info("Bee queue worker is running and waiting for messages.")
        while True:
            try:
                message, prompt = await self.message_queue.get()
            except asyncio.CancelledError:
                logger.info("Worker task received cancellation signal.")
                break
            except Exception as e:
                logger.error(f"Error getting item from queue: {e}")
                continue

            try:
                await self.process_message(message, prompt)
            except Exception as e:
                logger.exception(f"Unexpected error while processing message from {message.author}: {e}")
            finally:
                self.message_queue.task_done()

    async def process_message(self, message: discord.Message, prompt: str):
        channel_id = message.channel.id
        history = self.channel_histories[channel_id]

        # Append current user prompt to history
        history.append({"role": "user", "content": prompt})

        # Indicate typing while awaiting Bee's response
        try:
            async with message.channel.typing():
                response = await self.llama_client.generate_response(
                    messages=list(history),
                    max_tokens=config.max_tokens,
                    temperature=config.temperature,
                    top_p=config.top_p,
                )
        except ConnectionError:
            error_text = "*bzzz... (Could not reach local llama.cpp server. Is it running?)*"
            await self._safe_send(message, error_text)
            return
        except Exception as e:
            logger.error(f"Error querying BeeLLM: {e}")
            await self._safe_send(message, "*bzzzt... (Bee got confused and flew into a window)*")
            return

        # BeeLLM behavior: if placed in a jar or stunned, it may output nothing (silence)
        if not response or not response.strip():
            logger.info("BeeLLM returned empty output (Bee is silent/in a jar).")
            response = "*...*"

        # Append assistant response to history
        history.append({"role": "assistant", "content": response})

        # Send back to channel (chunked if over 2000 chars)
        await self._safe_send(message, response)

    async def _safe_send(self, message: discord.Message, text: str):
        """Sends a response back to the message channel, splitting if needed."""
        # Discord limit is 2000 characters
        max_chunk = 1990
        chunks = [text[i : i + max_chunk] for i in range(0, len(text), max_chunk)] or [text]

        for idx, chunk in enumerate(chunks):
            try:
                if idx == 0:
                    await message.reply(chunk, mention_author=config.reply_as_mention)
                else:
                    await message.channel.send(chunk)
            except discord.HTTPException:
                # Fallback to direct channel send if reply fails (e.g. original message was deleted)
                await message.channel.send(chunk)

    async def close(self):
        logger.info("Shutting down BeeBot...")
        if self.worker_task and not self.worker_task.done():
            self.worker_task.cancel()
            try:
                await self.worker_task
            except asyncio.CancelledError:
                pass
        await self.llama_client.close()
        await super().close()


def main():
    if not config.discord_token:
        logger.error("No DISCORD_TOKEN set. Please configure DISCORD_TOKEN in .env or environment.")
        sys.exit(1)

    intents = discord.Intents.default()
    intents.message_content = True  # Required to read mention text content
    intents.guild_messages = True

    client = BeeBot(intents=intents)

    try:
        client.run(config.discord_token)
    except KeyboardInterrupt:
        logger.info("Interrupted by user. Exiting.")


if __name__ == "__main__":
    main()
