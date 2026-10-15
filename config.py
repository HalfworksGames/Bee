import os
from dataclasses import dataclass
from dotenv import load_dotenv

load_dotenv()

@dataclass(frozen=True)
class Config:
    discord_token: str = os.getenv("DISCORD_TOKEN", "")
    llama_server_url: str = os.getenv("LLAMA_SERVER_URL", "http://127.0.0.1:1235").rstrip("/")
    model_name: str = os.getenv("MODEL_NAME", "schizophyllume/beellm")
    queue_size: int = int(os.getenv("QUEUE_SIZE", "16"))
    max_tokens: int = int(os.getenv("MAX_TOKENS", "128"))
    temperature: float = float(os.getenv("TEMPERATURE", "0.7"))
    top_p: float = float(os.getenv("TOP_P", "0.9"))
    history_limit: int = int(os.getenv("HISTORY_LIMIT", "6"))
    reply_as_mention: bool = os.getenv("REPLY_AS_MENTION", "false").lower() in ("true", "1", "yes")
    log_level: str = os.getenv("LOG_LEVEL", "INFO").upper()

config = Config()
