import logging
from typing import List, Dict, Optional
import aiohttp

logger = logging.getLogger(__name__)

class LlamaClient:
    """Async client for interacting with a local llama.cpp server."""

    def __init__(
        self,
        base_url: str = "http://127.0.0.1:8080",
        model_name: str = "schizophyllume/beellm",
        timeout_seconds: float = 60.0,
    ):
        self.base_url = base_url.rstrip("/")
        self.model_name = model_name
        self.timeout = aiohttp.ClientTimeout(total=timeout_seconds)
        self.session: Optional[aiohttp.ClientSession] = None

    async def _get_session(self) -> aiohttp.ClientSession:
        if self.session is None or self.session.closed:
            self.session = aiohttp.ClientSession(timeout=self.timeout)
        return self.session

    async def close(self):
        if self.session and not self.session.closed:
            await self.session.close()

    async def generate_response(
        self,
        messages: List[Dict[str, str]],
        max_tokens: int = 128,
        temperature: float = 0.7,
        top_p: float = 0.9,
    ) -> str:
        """
        Sends messages to llama.cpp server.
        Attempts OpenAI-compatible /v1/chat/completions first,
        falling back to /completion using BeeLLM format if needed.
        """
        session = await self._get_session()
        chat_url = f"{self.base_url}/v1/chat/completions"

        payload = {
            "model": self.model_name,
            "messages": messages,
            "max_tokens": max_tokens,
            "temperature": temperature,
            "top_p": top_p,
            "stream": False,
        }

        try:
            async with session.post(chat_url, json=payload) as response:
                if response.status == 200:
                    data = await response.json()
                    choices = data.get("choices", [])
                    if choices:
                        return choices[0].get("message", {}).get("content", "").strip()
                    return ""
                elif response.status != 404:
                    text = await response.text()
                    logger.error(f"/v1/chat/completions returned {response.status}: {text}")
        except aiohttp.ClientConnectorError as e:
            logger.error(f"Cannot connect to llama.cpp at {self.base_url}: {e}")
            raise ConnectionError(f"Cannot connect to llama.cpp server at {self.base_url}") from e
        except Exception as e:
            logger.warning(f"Error querying /v1/chat/completions: {e}. Falling back to /completion.")

        # Fallback to /completion with BeeLLM specific prompt format
        completion_url = f"{self.base_url}/completion"
        formatted_prompt = self._format_bee_prompt(messages)
        completion_payload = {
            "prompt": formatted_prompt,
            "n_predict": max_tokens,
            "temperature": temperature,
            "top_p": top_p,
            "stop": ["</s>", "<|user|>", "<|bee|>"],
        }

        try:
            async with session.post(completion_url, json=completion_payload) as response:
                if response.status == 200:
                    data = await response.json()
                    return data.get("content", "").strip()
                else:
                    error_msg = await response.text()
                    logger.error(f"/completion returned {response.status}: {error_msg}")
                    raise RuntimeError(f"llama-server error {response.status}: {error_msg}")
        except aiohttp.ClientConnectorError as e:
            logger.error(f"Cannot connect to llama.cpp at {self.base_url}: {e}")
            raise ConnectionError(f"Cannot connect to llama.cpp server at {self.base_url}") from e

    def _format_bee_prompt(self, messages: List[Dict[str, str]]) -> str:
        """
        Formats messages matching BeeLLM Jinja template:
        {% for m in messages %}
          {% if m['role'] == 'user' %}<|user|>{{ m['content'] }}
          {% elif m['role'] == 'assistant' %}<|bee|>{{ m['content'] }}</s>
          {% endif %}
        {% endfor %}
        <|bee|>
        """
        prompt_parts = []
        for msg in messages:
            role = msg.get("role")
            content = msg.get("content", "")
            if role == "user":
                prompt_parts.append(f"<|user|>{content}")
            elif role == "assistant":
                prompt_parts.append(f"<|bee|>{content}</s>")
        prompt_parts.append("<|bee|>")
        return "".join(prompt_parts)
