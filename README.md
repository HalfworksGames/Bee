# 🐝 Bee Discord Bot (BeeLLM)

A Discord bot for [BeeLLM](https://huggingface.co/schizophyllume/BeeLLM) running on a local `llama.cpp` server.

## Features

- **Server Monitoring:** Monitors Discord channels for `@Bee` mentions.
- **Asynchronous Queue:** Buffers incoming requests in an `asyncio.Queue` (default size 16, configurable).
- **Safe Handling:** Gracefully handles queue saturation and informs users if Bee is overwhelmed.
- **Channel Replies:** Dispatches Bee's buzzes, emotes, and reactions directly back into the channel.
- **Short-term Memory:** Retains configurable multi-turn context per channel so Bee can remember flowers, grudges, apologies, or revivals.
- **Typing Indicator & Visual Feedback:** Shows a `🐝` reaction when enqueued and Discord typing indicator while generating.
- **Silence & Jar Awareness:** Appropriately handles BeeLLM's dead/jar states when the model produces silence.

---

## Prerequisites

1. Python 3.10+
2. A running `llama.cpp` server (`llama-server`) with a BeeLLM GGUF model (e.g., `BeeLLM-1M-Mood.gguf` or `BeeLLM-12M-Mood.gguf`).
3. A Discord Bot Token with **Message Content Intent** enabled.

---

## 1. Setting up llama.cpp with BeeLLM

Download any BeeLLM GGUF variant from [Hugging Face](https://huggingface.co/schizophyllume/BeeLLM), for example:
- `BeeLLM-12M-Mood.gguf` (full mood dynamics, grudge holding, name recognition)
- `BeeLLM-1M-Mood.gguf` (lightweight, chaotic)

Run `llama-server`:

```bash
llama-server -m BeeLLM-12M-Mood.gguf -c 4096 --port 8080
```

---

## 2. Discord Developer Portal Setup

1. Go to the [Discord Developer Portal](https://discord.com/developers/applications) and create a **New Application**.
2. Go to the **Bot** tab:
   - Click **Reset Token** and copy your bot token.
   - Under **Privileged Gateway Intents**, turn **ON**:
     - **Message Content Intent** *(Required to read mentions & message text)*
3. Go to **OAuth2 -> URL Generator**:
   - Scopes: `bot`
   - Bot Permissions:
     - `Send Messages`
     - `Read Messages/View Channels`
     - `Read Message History`
     - `Add Reactions`
4. Copy the generated invite URL and invite the bot to your Discord server.

---

## 3. Installation & Configuration

1. Initialize the virtual environment and install requirements:
   ```bash
   python -m venv .venv
   source .venv/bin/activate
   pip install -r requirements.txt
   ```

2. Create your `.env` configuration file:
   ```bash
   cp .env.example .env
   ```

3. Edit `.env` and paste your Discord bot token:
   ```env
   DISCORD_TOKEN=your_token_here
   ```

---

## 4. Running the Bot

Activate the virtual environment or run directly:

```bash
.venv/bin/python bot.py
```

---

## 5. Talking to Bee

Mention the bot in any channel it has access to:

- `@Bee hi bee!`
- `@Bee *gives you a flower*`
- `@Bee are you scintilla?`
- `@Bee *swats you*` -> `@Bee sorry`
- `@Bee *puts you in a jar*` -> *(Bee goes completely silent)*
- `@Bee *opens the jar*` -> *(Bee files a formal complaint)*
