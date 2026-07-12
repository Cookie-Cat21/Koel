"""LLM brief providers (Gemini HTTP stub).

``summarize(text) -> str`` is the only Phase-2 surface. Default off:
``AI_BRIEFS_ENABLED`` must be ``1`` and ``AI_API_KEY`` set, or
``summarize`` raises ``RuntimeError`` (never silently invents text).

Hardening (wave4): bounded HTTP timeout, non-JSON / empty-candidate fails,
and filing text isolated via ``systemInstruction`` + delimiters.
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

_DEFAULT_TIMEOUT_SECONDS = 30.0
_MAX_OUTPUT_TOKENS = 512


class BriefProvider(Protocol):
    async def summarize(self, text: str) -> str:
        """Return a short plain-language filing brief for ``text``."""


class BriefsDisabledError(RuntimeError):
    """Raised when summarize is called while AI briefs are off / unkeyed."""


class GeminiBriefProvider:
    """Gemini ``generateContent`` via httpx (no official SDK)."""

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
            else self._settings.http_timeout_seconds
            or _DEFAULT_TIMEOUT_SECONDS
        )
        self._timeout = httpx.Timeout(timeout_s, connect=min(10.0, timeout_s))
        self._client = client or httpx.AsyncClient(timeout=self._timeout)

    async def aclose(self) -> None:
        if self._owns_client:
            await self._client.aclose()

    async def __aenter__(self) -> GeminiBriefProvider:
        return self

    async def __aexit__(self, *args: object) -> None:
        await self.aclose()

    def _require_enabled(self) -> None:
        if not briefs_enabled(self._settings):
            raise BriefsDisabledError(
                "AI briefs disabled: set AI_BRIEFS_ENABLED=1 and AI_API_KEY"
            )

    def _sanitize_user_text(self, text: str) -> str:
        """Treat caller text as untrusted filing payload (null-strip + wrap)."""
        body = (text or "").replace("\x00", "").strip()
        if not body:
            raise ValueError("summarize requires non-empty text")
        max_chars = max(1, int(self._settings.max_input_chars))
        if len(body) > max_chars:
            body = body[:max_chars]
        if "<<<FILING>>>" in body and "<<<END_FILING>>>" in body:
            return body
        return f"<<<FILING>>>\n{body}\n<<<END_FILING>>>"

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
            raise RuntimeError(
                f"Gemini response was not JSON: {response.text[:300]!r}"
            ) from exc

        brief = _extract_gemini_text(data)
        if not brief:
            reason = _gemini_failure_reason(data)
            raise RuntimeError(f"Gemini response missing candidates text ({reason})")
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


def make_brief_provider(
    settings: BriefSettings | None = None,
    *,
    client: httpx.AsyncClient | None = None,
) -> BriefProvider:
    """Build a provider. Disabled settings still return Gemini provider that raises."""
    cfg = settings or BriefSettings.from_env()
    if cfg.provider and cfg.provider != "gemini":
        raise RuntimeError(f"Unsupported AI_PROVIDER={cfg.provider!r} (only gemini)")
    return GeminiBriefProvider(cfg, client=client)
