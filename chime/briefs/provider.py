"""LLM brief providers (Gemini + OpenAI-compatible HTTP).

``summarize(text) -> str`` is the only Phase-2 surface. Default off:
``AI_BRIEFS_ENABLED`` must be ``1`` and ``AI_API_KEY`` set, or
``summarize`` raises ``RuntimeError`` (never silently invents text).

Hardening (wave4): bounded HTTP timeout, non-JSON / empty-candidate fails,
and filing text isolated via system instruction + delimiters.

``AI_PROVIDER=gemini`` → Gemini ``generateContent``.
``AI_PROVIDER=groq`` → Groq OpenAI-compatible ``/chat/completions``.
``AI_PROVIDER=openrouter`` → OpenRouter OpenAI-compatible ``/chat/completions``.
"""

from __future__ import annotations

import json
from typing import Any, Protocol

import httpx
import structlog

from chime.briefs import BRIEF_SYSTEM_INSTRUCTION, BriefSettings, briefs_enabled

log = structlog.get_logger("chime.briefs.provider")

GEMINI_GENERATE_URL = (
    "https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"
)
GROQ_CHAT_COMPLETIONS_URL = "https://api.groq.com/openai/v1/chat/completions"
OPENROUTER_CHAT_COMPLETIONS_URL = "https://openrouter.ai/api/v1/chat/completions"

_DEFAULT_TIMEOUT_SECONDS = 30.0
_MAX_OUTPUT_TOKENS = 512


class BriefProvider(Protocol):
    async def summarize(self, text: str) -> str:
        """Return a short plain-language filing brief for ``text``."""


class BriefsDisabledError(RuntimeError):
    """Raised when summarize is called while AI briefs are off / unkeyed."""


class _HttpBriefProviderBase:
    """Shared httpx client lifecycle + filing sanitize for HTTP providers."""

    def __init__(
        self,
        settings: BriefSettings | None = None,
        *,
        client: httpx.AsyncClient | None = None,
        timeout: float | None = None,
    ) -> None:
        self._settings = settings or BriefSettings.from_env()
        self._owns_client = client is None
        timeout_s = float(
            timeout
            if timeout is not None
            else self._settings.http_timeout_seconds or _DEFAULT_TIMEOUT_SECONDS
        )
        self._timeout = httpx.Timeout(timeout_s, connect=min(10.0, timeout_s))
        self._client = client or httpx.AsyncClient(timeout=self._timeout)

    async def aclose(self) -> None:
        if self._owns_client:
            await self._client.aclose()

    def _require_enabled(self) -> None:
        if not briefs_enabled(self._settings):
            raise BriefsDisabledError("AI briefs disabled: set AI_BRIEFS_ENABLED=1 and AI_API_KEY")

    def _sanitize_user_text(self, text: str) -> str:
        """Treat caller text as untrusted filing payload (null-strip + wrap).

        Truncates the *inner* filing body so a small ``AI_MAX_INPUT_CHARS``
        cannot chop ``<<<END_FILING>>>`` and trigger a broken re-wrap.
        """
        body = (text or "").replace("\x00", "").strip()
        if not body:
            raise ValueError("summarize requires non-empty text")
        max_chars = max(1, int(self._settings.max_input_chars))
        start = "<<<FILING>>>"
        end = "<<<END_FILING>>>"
        if start in body and end in body:
            pre, _, rest = body.partition(start)
            inner, _, post = rest.partition(end)
            inner = inner.strip("\n")
            if len(inner) > max_chars:
                inner = inner[:max_chars]
            return f"{pre}{start}\n{inner}\n{end}{post}"
        if len(body) > max_chars:
            body = body[:max_chars]
        return f"{start}\n{body}\n{end}"


class GeminiBriefProvider(_HttpBriefProviderBase):
    """Gemini ``generateContent`` via httpx (no official SDK)."""

    async def __aenter__(self) -> GeminiBriefProvider:
        return self

    async def __aexit__(self, *args: object) -> None:
        await self.aclose()

    async def summarize(self, text: str) -> str:
        self._require_enabled()
        body = self._sanitize_user_text(text)

        url = GEMINI_GENERATE_URL.format(model=self._settings.model)
        payload: dict[str, Any] = {
            "systemInstruction": {
                "parts": [{"text": BRIEF_SYSTEM_INSTRUCTION}],
            },
            "contents": [{"role": "user", "parts": [{"text": body}]}],
            "generationConfig": {
                "temperature": 0.2,
                "maxOutputTokens": _MAX_OUTPUT_TOKENS,
            },
        }
        headers = {
            "Content-Type": "application/json",
            "x-goog-api-key": self._settings.api_key,
        }
        log.info(
            "gemini_summarize_request",
            model=self._settings.model,
            input_chars=len(body),
        )
        try:
            response = await self._client.post(
                url,
                headers=headers,
                json=payload,
                timeout=self._timeout,
            )
        except httpx.TimeoutException as exc:
            raise RuntimeError(f"Gemini request timed out: {exc}") from exc
        except httpx.HTTPError as exc:
            raise RuntimeError(f"Gemini transport error: {exc}") from exc

        try:
            response.raise_for_status()
        except httpx.HTTPStatusError as exc:
            raise RuntimeError(
                f"Gemini HTTP {exc.response.status_code}: {exc.response.text[:300]}"
            ) from exc

        try:
            data = response.json()
        except (json.JSONDecodeError, ValueError) as exc:
            raise RuntimeError(f"Gemini response was not JSON: {response.text[:300]!r}") from exc

        brief = _extract_gemini_text(data)
        if not brief:
            reason = _gemini_failure_reason(data)
            raise RuntimeError(f"Gemini response missing candidates text ({reason})")
        return brief


class _OpenAICompatibleBriefProvider(_HttpBriefProviderBase):
    """Shared OpenAI-compatible ``/chat/completions`` (Groq, OpenRouter, …)."""

    _chat_url: str = ""
    _label: str = "OpenAI-compatible"
    _log_event: str = "openai_compatible_summarize_request"

    async def summarize(self, text: str) -> str:
        self._require_enabled()
        body = self._sanitize_user_text(text)

        payload: dict[str, Any] = {
            "model": self._settings.model,
            "messages": [
                {"role": "system", "content": BRIEF_SYSTEM_INSTRUCTION},
                {"role": "user", "content": body},
            ],
            "temperature": 0.2,
            "max_tokens": _MAX_OUTPUT_TOKENS,
        }
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self._settings.api_key}",
        }
        log.info(
            self._log_event,
            model=self._settings.model,
            input_chars=len(body),
        )
        label = self._label
        try:
            response = await self._client.post(
                self._chat_url,
                headers=headers,
                json=payload,
                timeout=self._timeout,
            )
        except httpx.TimeoutException as exc:
            raise RuntimeError(f"{label} request timed out: {exc}") from exc
        except httpx.HTTPError as exc:
            raise RuntimeError(f"{label} transport error: {exc}") from exc

        try:
            response.raise_for_status()
        except httpx.HTTPStatusError as exc:
            raise RuntimeError(
                f"{label} HTTP {exc.response.status_code}: {exc.response.text[:300]}"
            ) from exc

        try:
            data = response.json()
        except (json.JSONDecodeError, ValueError) as exc:
            raise RuntimeError(f"{label} response was not JSON: {response.text[:300]!r}") from exc

        brief = _extract_openai_chat_text(data)
        if not brief:
            reason = _openai_chat_failure_reason(data)
            raise RuntimeError(f"{label} response missing message content ({reason})")
        return brief


class GroqBriefProvider(_OpenAICompatibleBriefProvider):
    """Groq OpenAI-compatible ``/chat/completions`` via httpx."""

    _chat_url = GROQ_CHAT_COMPLETIONS_URL
    _label = "Groq"
    _log_event = "groq_summarize_request"

    async def __aenter__(self) -> GroqBriefProvider:
        return self

    async def __aexit__(self, *args: object) -> None:
        await self.aclose()


class OpenRouterBriefProvider(_OpenAICompatibleBriefProvider):
    """OpenRouter OpenAI-compatible ``/chat/completions`` via httpx.

    Sends ``HTTP-Referer`` + ``X-Title`` (OpenRouter attribution headers);
    missing them can yield 401/403 on free-tier routes.
    """

    _chat_url = OPENROUTER_CHAT_COMPLETIONS_URL
    _label = "OpenRouter"
    _log_event = "openrouter_summarize_request"

    async def __aenter__(self) -> OpenRouterBriefProvider:
        return self

    async def __aexit__(self, *args: object) -> None:
        await self.aclose()

    async def summarize(self, text: str) -> str:
        self._require_enabled()
        body = self._sanitize_user_text(text)

        payload: dict[str, Any] = {
            "model": self._settings.model,
            "messages": [
                {"role": "system", "content": BRIEF_SYSTEM_INSTRUCTION},
                {"role": "user", "content": body},
            ],
            "temperature": 0.2,
            "max_tokens": _MAX_OUTPUT_TOKENS,
        }
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self._settings.api_key}",
            # OpenRouter ranks / gates some models on these attribution headers.
            "HTTP-Referer": "https://github.com/chime-cse",
            "X-Title": "Chime CSE alerts",
        }
        log.info(
            self._log_event,
            model=self._settings.model,
            input_chars=len(body),
        )
        label = self._label
        try:
            response = await self._client.post(
                self._chat_url,
                headers=headers,
                json=payload,
                timeout=self._timeout,
            )
        except httpx.TimeoutException as exc:
            raise RuntimeError(f"{label} request timed out: {exc}") from exc
        except httpx.HTTPError as exc:
            raise RuntimeError(f"{label} transport error: {exc}") from exc

        try:
            response.raise_for_status()
        except httpx.HTTPStatusError as exc:
            raise RuntimeError(
                f"{label} HTTP {exc.response.status_code}: {exc.response.text[:300]}"
            ) from exc

        try:
            data = response.json()
        except (json.JSONDecodeError, ValueError) as exc:
            raise RuntimeError(f"{label} response was not JSON: {response.text[:300]!r}") from exc

        brief = _extract_openai_chat_text(data)
        if not brief:
            reason = _openai_chat_failure_reason(data)
            raise RuntimeError(f"{label} response missing message content ({reason})")
        return brief


def _gemini_failure_reason(data: Any) -> str:
    if not isinstance(data, dict):
        return f"non-object body type={type(data).__name__}"
    feedback = data.get("promptFeedback")
    if isinstance(feedback, dict):
        blocked = feedback.get("blockReason")
        if blocked:
            return f"promptFeedback.blockReason={blocked}"
    candidates = data.get("candidates")
    if not isinstance(candidates, list) or not candidates:
        return "empty candidates"
    first = candidates[0]
    if not isinstance(first, dict):
        return "candidate not an object"
    finish = first.get("finishReason")
    if finish:
        return f"finishReason={finish}"
    return "no text parts"


def _extract_gemini_text(data: Any) -> str:
    if not isinstance(data, dict):
        return ""
    candidates = data.get("candidates")
    if not isinstance(candidates, list) or not candidates:
        return ""
    first = candidates[0]
    if not isinstance(first, dict):
        return ""
    content = first.get("content")
    if not isinstance(content, dict):
        return ""
    parts = content.get("parts")
    if not isinstance(parts, list):
        return ""
    chunks: list[str] = []
    for part in parts:
        if isinstance(part, dict):
            piece = part.get("text")
            if isinstance(piece, str) and piece.strip():
                chunks.append(piece.strip())
    return "\n".join(chunks).strip()


def _openai_chat_failure_reason(data: Any) -> str:
    if not isinstance(data, dict):
        return f"non-object body type={type(data).__name__}"
    err = data.get("error")
    if isinstance(err, dict):
        msg = err.get("message")
        if isinstance(msg, str) and msg.strip():
            return f"error.message={msg.strip()[:200]}"
        code = err.get("code")
        if code is not None:
            return f"error.code={code}"
    choices = data.get("choices")
    if not isinstance(choices, list) or not choices:
        return "empty choices"
    first = choices[0]
    if not isinstance(first, dict):
        return "choice not an object"
    finish = first.get("finish_reason")
    if finish:
        return f"finish_reason={finish}"
    return "no message content"


def _extract_openai_chat_text(data: Any) -> str:
    if not isinstance(data, dict):
        return ""
    choices = data.get("choices")
    if not isinstance(choices, list) or not choices:
        return ""
    first = choices[0]
    if not isinstance(first, dict):
        return ""
    message = first.get("message")
    if not isinstance(message, dict):
        return ""
    content = message.get("content")
    if isinstance(content, str):
        return content.strip()
    # OpenAI-compatible multimodal content: list of typed parts.
    if isinstance(content, list):
        chunks: list[str] = []
        for part in content:
            if isinstance(part, str) and part.strip():
                chunks.append(part.strip())
            elif isinstance(part, dict):
                piece = part.get("text")
                if isinstance(piece, str) and piece.strip():
                    chunks.append(piece.strip())
        return "\n".join(chunks).strip()
    return ""


def make_brief_provider(
    settings: BriefSettings | None = None,
    *,
    client: httpx.AsyncClient | None = None,
) -> BriefProvider:
    """Build a provider from ``AI_PROVIDER`` (``gemini``, ``groq``, or ``openrouter``)."""
    cfg = settings or BriefSettings.from_env()
    provider = (cfg.provider or "gemini").strip().lower()
    if provider == "gemini":
        return GeminiBriefProvider(cfg, client=client)
    if provider == "groq":
        return GroqBriefProvider(cfg, client=client)
    if provider == "openrouter":
        return OpenRouterBriefProvider(cfg, client=client)
    raise RuntimeError(f"Unsupported AI_PROVIDER={cfg.provider!r} (gemini|groq|openrouter)")
