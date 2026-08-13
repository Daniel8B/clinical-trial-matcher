"""LLM client seam.

The protocol is what generation.py depends on. Everything below it is swappable:
Ollama today, a hosted OpenAI-compatible endpoint later, a stub in tests.
"""

from __future__ import annotations

from typing import Protocol

import httpx


class LLMClient(Protocol):
    """The only surface generation.py is allowed to use."""

    def is_available(self) -> bool:
        """True if the backend answers. Never raises."""
        ...

    def complete(self, system: str, user: str, max_tokens: int) -> str:
        """Return the model's text. Raises on transport or protocol failure."""
        ...


class OllamaClient:
    """Talks to Ollama's OpenAI-compatible surface.

    The path is /v1/chat/completions, not Ollama's native /api/generate, so the
    same client works against any OpenAI-compatible provider by changing
    base_url and model.
    """

    def __init__(
        self,
        base_url: str,
        model: str,
        temperature: float = 0.0,
        connect_timeout: float = 5.0,
        read_timeout: float = 120.0,
    ) -> None:
        base = base_url.rstrip("/")
        self._completions_url = f"{base}/v1/chat/completions"
        self._models_url = f"{base}/v1/models"
        self._model = model
        self._temperature = temperature
        self._client = httpx.Client(
            timeout=httpx.Timeout(read_timeout, connect=connect_timeout)
        )

    def is_available(self) -> bool:
        try:
            response = self._client.get(self._models_url, timeout=2.0)
        except httpx.HTTPError:
            return False
        return response.status_code == 200

    def complete(self, system: str, user: str, max_tokens: int = 400) -> str:
        payload = {
            "model": self._model,
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            # Deterministic by decision: Day 3 compares evaluation runs against
            # each other, and a sampled model makes two runs incomparable.
            "temperature": self._temperature,
            "max_tokens": max_tokens,
        }
        response = self._client.post(self._completions_url, json=payload)
        response.raise_for_status()
        return response.json()["choices"][0]["message"]["content"]

    def close(self) -> None:
        self._client.close()


class StubClient:
    """Deterministic client for tests. No network, no Ollama, no GPU."""

    def __init__(self, response: str = "", available: bool = True) -> None:
        self._response = response
        self._available = available
        self.calls: list[tuple[str, str]] = []

    def is_available(self) -> bool:
        return self._available

    def complete(self, system: str, user: str, max_tokens: int = 400) -> str:
        self.calls.append((system, user))
        return self._response

    def close(self) -> None:
        pass