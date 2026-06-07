"""Async OpenAI-compatible gateway for translation.

Handles both local ``llama.cpp`` (OpenAI-compatible mode) and official
OpenAI with the same ``openai.AsyncOpenAI`` client.  Features:

* Bounded retry with exponential backoff (configurable max retries).
* Strict JSON extraction from model output.
* One repair pass for malformed JSON (strip markdown fences, trailing commas).
* Typed error mapping to ``translation_errors`` classes.
"""

from __future__ import annotations

import asyncio
import json
import logging
import re
import time
from urllib.parse import parse_qs, urlencode, urlparse, urlunparse
from typing import Any

from openai import (
    AsyncOpenAI,
    APIConnectionError,
    APIStatusError,
    InternalServerError,
    APITimeoutError,
    RateLimitError,
)

from app.core.config import settings
from app.schemas.translation import LLMTranslationResponse
from app.services.translation_errors import (
    TranslationInvalidJSONError,
    TranslationProviderNetworkError,
    TranslationProviderTimeoutError,
    TranslationSchemaMismatchError,
)

logger = logging.getLogger("manga_api.translation_gateway")


class TranslationGateway:
    """Async gateway wrapping ``openai.AsyncOpenAI`` for translation calls."""

    def __init__(
        self,
        *,
        base_url: str | None = None,
        api_key: str | None = None,
        model: str | None = None,
        max_output_tokens: int | None = None,
        timeout: int | None = None,
        max_retries: int | None = None,
        use_streaming: bool = False,
        local_compat_mode: bool = False,
    ) -> None:
        effective_base_url = base_url or settings.translation_base_url
        effective_api_key = api_key or (
            settings.translation_api_key.get_secret_value()
            if settings.translation_api_key
            else "not-needed"
        )
        self._model = model or settings.translation_model
        self._max_output_tokens = (
            max_output_tokens
            if max_output_tokens is not None
            else settings.translation_max_output_tokens
        )
        self._timeout = timeout or settings.translation_timeout_seconds
        self._max_retries = max_retries if max_retries is not None else settings.translation_max_retries
        self._use_streaming = use_streaming
        self._local_compat_mode = local_compat_mode

        self._base_url_candidates = self._build_base_url_candidates(
            effective_base_url=effective_base_url,
            fallback_urls=settings.translation_base_urls,
        )
        self._clients: list[tuple[str, AsyncOpenAI]] = [
            (
                candidate,
                AsyncOpenAI(
                    base_url=candidate,
                    api_key=effective_api_key,
                    timeout=float(self._timeout),
                    max_retries=0,  # We handle retries ourselves for typed errors.
                ),
            )
            for candidate in self._base_url_candidates
        ]

    async def translate(
        self,
        messages: list[dict[str, Any]],
        *,
        enable_thinking: bool = True,
    ) -> tuple[LLMTranslationResponse, dict[str, Any]]:
        """Send translation request and return parsed response + gateway metrics.

        Returns
        -------
        tuple[LLMTranslationResponse, dict]
            Parsed model output and a metrics dict with ``latency_ms``,
            ``retry_count``, ``enable_thinking_effective``, and
            ``thinking_control_strategy``.

        Raises
        ------
        TranslationProviderTimeoutError
        TranslationProviderNetworkError
        TranslationInvalidJSONError
        TranslationSchemaMismatchError
        """
        last_error: Exception | None = None
        retry_count = 0
        start_time = time.monotonic()

        for attempt in range(1 + self._max_retries):
            try:
                raw_text, finish_reason = await self._call_model(messages, enable_thinking=enable_thinking)
                break
            except TranslationProviderTimeoutError:
                last_error = TranslationProviderTimeoutError(
                    f"Timeout after {self._timeout}s (attempt {attempt + 1})"
                )
                retry_count = attempt + 1
            except TranslationProviderNetworkError:
                last_error = TranslationProviderNetworkError(
                    f"Network error (attempt {attempt + 1})"
                )
                retry_count = attempt + 1

            if attempt < self._max_retries:
                delay = min(1.0 * (2 ** attempt), 10.0)
                logger.info("Retry %d/%d in %.1fs", attempt + 1, self._max_retries, delay)
                await asyncio.sleep(delay)
        else:
            raise last_error  # type: ignore[misc]

        latency_ms = int((time.monotonic() - start_time) * 1000)

        json_retry_count = 0

        # If the output was truncated, treat it as invalid JSON to trigger the recovery pass.
        if finish_reason == "length":
            logger.warning("LLM output truncated due to length; forcing token expansion.")
            parsed = None
        else:
            # Parse JSON — attempt raw first, then one repair pass.
            parsed = self._extract_json(raw_text)
        if parsed is None:
            repaired = self._repair_json(raw_text)
            parsed = self._extract_json(repaired)
            if parsed is None:
                # Final salvage pass: ask the model once more for strict JSON
                # with a larger output budget in case the first answer was truncated.
                json_retry_count = 1
                base_tokens = self._max_output_tokens or 2048
                retry_tokens = min(8192, max(base_tokens + 512, base_tokens * 2))
                retry_messages = self._build_json_recovery_messages(messages)
                retry_text, _ = await self._call_model(
                    retry_messages,
                    enable_thinking=enable_thinking,
                    max_output_tokens=retry_tokens,
                    temperature=0.1,
                )
                parsed = self._extract_json(retry_text)
                if parsed is None:
                    repaired_retry = self._repair_json(retry_text)
                    parsed = self._extract_json(repaired_retry)
                if parsed is None:
                    # Schema rescue pass: force a fresh schema-only answer with
                    # very low temperature to reduce free-form reasoning output.
                    json_retry_count = 2
                    rescue_messages = self._build_schema_rescue_messages(messages)
                    rescue_text, _ = await self._call_model(
                        rescue_messages,
                        enable_thinking=enable_thinking,
                        max_output_tokens=retry_tokens,
                        temperature=0.0,
                    )
                    parsed = self._extract_json(rescue_text)
                    if parsed is None:
                        repaired_rescue = self._repair_json(rescue_text)
                        parsed = self._extract_json(repaired_rescue)
                if parsed is None:
                    raise TranslationInvalidJSONError(
                        f"Could not parse LLM output as JSON after recovery retry. "
                        f"First raw (first 500 chars): {raw_text[:500]}"
                    )

        # Validate against Pydantic schema.
        try:
            response = LLMTranslationResponse.model_validate(parsed)
        except Exception as exc:
            raise TranslationSchemaMismatchError(
                f"LLM JSON does not match schema: {exc}"
            ) from exc

        gateway_metrics = {
            "latency_ms": latency_ms,
            "retry_count": retry_count,
            "json_recovery_retry_count": json_retry_count,
            "max_output_tokens_effective": self._max_output_tokens,
            "raw_response_text": raw_text,
        }

        return response, gateway_metrics

    # ── Internal ──────────────────────────────────────────────────────

    async def _call_model(
        self,
        messages: list[dict[str, Any]],
        *,
        enable_thinking: bool = False,
        max_output_tokens: int | None = None,
        temperature: float = 0.3,
    ) -> tuple[str, str | None]:
        """Make one chat completion call, mapping SDK errors to typed errors."""
        logger.info("LLM Request Messages: %s", json.dumps(messages, ensure_ascii=False))
        effective_max_tokens = (
            max_output_tokens if max_output_tokens is not None else self._max_output_tokens
        )
        errors: list[str] = []
        for idx, (base_url, client) in enumerate(self._clients):
            try:
                request_kwargs: dict[str, Any] = {
                    "model": self._model,
                    "messages": messages,  # type: ignore[arg-type]
                    "temperature": temperature,
                    "response_format": {"type": "json_object"},
                }
                if effective_max_tokens is not None:
                    request_kwargs["max_tokens"] = effective_max_tokens
                # llama.cpp compatibility: some deployments honor n_predict more
                # consistently than max_tokens in OpenAI-compatible mode.
                if self._local_compat_mode:
                    extra_body: dict[str, Any] = {
                        "chat_template_kwargs": {"enable_thinking": enable_thinking},
                    }
                    if effective_max_tokens is not None:
                        extra_body["n_predict"] = effective_max_tokens
                    request_kwargs["extra_body"] = extra_body

                if self._use_streaming:
                    stream = await client.chat.completions.create(**request_kwargs, stream=True)
                    chunks: list[str] = []
                    finish_reason = None
                    async for event in stream:
                        if not event.choices:
                            continue
                        choice = event.choices[0]
                        if choice.finish_reason:
                            finish_reason = choice.finish_reason
                        delta = choice.delta
                        if not delta:
                            continue
                        if getattr(delta, "content", None):
                            chunks.append(delta.content)
                            continue
                        # Some OpenAI-compatible local servers can emit
                        # reasoning or text under alternate delta fields.
                        if getattr(delta, "text", None):
                            chunks.append(delta.text)

                    streamed_text = "".join(chunks).strip()
                    if streamed_text:
                        return streamed_text, finish_reason

                    # Fallback: if streaming produced no usable text, retry the
                    # same request in non-streaming mode.
                    logger.warning(
                        "Streaming produced empty content for %s; retrying non-streaming",
                        base_url,
                    )
                    completion = await client.chat.completions.create(**request_kwargs)
                    choice = completion.choices[0]
                    content = (choice.message.content or "").strip()
                    logger.info("LLM Response Content: %s", content)
                    return content, choice.finish_reason

                completion = await client.chat.completions.create(**request_kwargs)
                choice = completion.choices[0]
                content = (choice.message.content or "").strip()
                logger.info("LLM Response Content: %s", content)
                return content, choice.finish_reason
            except APITimeoutError as exc:
                raise TranslationProviderTimeoutError(str(exc)) from exc
            except RateLimitError as exc:
                errors.append(f"{base_url}: rate limited ({exc})")
            except APIConnectionError as exc:
                detail = self._format_connection_error(exc)
                logger.warning(
                    "Translation API connection failed for %s: %s",
                    base_url,
                    detail,
                )
                errors.append(f"{base_url}: {detail}")
            except InternalServerError as exc:
                errors.append(f"{base_url}: {exc}")
            except APIStatusError as exc:
                status = getattr(exc, "status_code", None)
                if status is not None and status >= 500:
                    errors.append(f"{base_url}: server error {status}")
                else:
                    # Non-retryable 4xx from upstream.
                    raise TranslationProviderNetworkError(
                        f"Provider returned status {status} at {base_url}: {exc}"
                    ) from exc

            if idx < len(self._clients) - 1:
                logger.warning(
                    "Translation provider failed for base URL %s; trying fallback",
                    base_url,
                )

        raise TranslationProviderNetworkError(
            "All configured translation base URLs failed: " + " | ".join(errors)
        )

    @staticmethod
    def _format_connection_error(exc: APIConnectionError) -> str:
        """Render SDK connection errors with nested root-cause details."""
        parts: list[str] = []
        msg = str(exc).strip()
        if msg:
            parts.append(msg)

        root: BaseException | None = exc
        for _ in range(5):
            next_root = (
                getattr(root, "__cause__", None)
                or getattr(root, "__context__", None)
                or getattr(root, "cause", None)
            )
            if not next_root or next_root is root:
                break
            root = next_root

        if root and root is not exc:
            parts.append(f"root_cause={type(root).__name__}: {root}")

        return " | ".join(parts) if parts else "connection error"

    @staticmethod
    def _build_json_recovery_messages(messages: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """Append a strict JSON-only reminder for one recovery retry."""
        recovery_note = {
            "role": "user",
            "content": (
                "Your previous output was invalid or truncated JSON. "
                "Return ONLY valid JSON matching the required schema. "
                "No markdown, no prose, no code fences."
            ),
        }
        return [*messages, recovery_note]

    @staticmethod
    def _build_schema_rescue_messages(messages: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """Append schema-only rescue instructions without adding a late system message.

        Some OpenAI-compatible local servers enforce chat templates that allow a
        system message only at the very beginning.  The original prompt already
        starts with the system role, so the rescue pass must add user guidance
        instead of appending another system message after user content.
        """
        schema_json = json.dumps(
            LLMTranslationResponse.model_json_schema(), indent=2
        )
        rescue_user = {
            "role": "user",
            "content": (
                "Re-answer the original task now as a strict JSON API. "
                "Output ONE valid JSON object only. "
                "No markdown, no explanations, no planning text.\n"
                "Return valid JSON matching this schema:\n"
                f"{schema_json}\n"
                "Use only orders that were provided in the original input."
            ),
        }
        return [*messages, rescue_user]

    @staticmethod
    def _build_base_url_candidates(
        *,
        effective_base_url: str,
        fallback_urls: list[str] | str,
    ) -> list[str]:
        """Build and normalize translation base URL candidates with light heuristics."""
        raw_candidates: list[str] = [effective_base_url]
        if isinstance(fallback_urls, list):
            raw_candidates.extend(fallback_urls)
        elif isinstance(fallback_urls, str) and fallback_urls.strip():
            raw_candidates.extend(
                [item.strip() for item in fallback_urls.split(",") if item.strip()]
            )

        normalized: list[str] = []
        seen: set[str] = set()
        for item in raw_candidates:
            for candidate in TranslationGateway._expand_base_url_candidate(item):
                if candidate not in seen:
                    normalized.append(candidate)
                    seen.add(candidate)

        return normalized or ["http://localhost:8033/v1"]

    @staticmethod
    def _expand_base_url_candidate(item: str) -> list[str]:
        """Expand one raw base URL into likely OpenAI-compatible variants."""
        candidate = item.strip().rstrip("/")
        if not candidate:
            return []

        variants: list[str] = []
        seen: set[str] = set()

        def add(url: str) -> None:
            normalized = url.strip().rstrip("/")
            if normalized and normalized not in seen:
                variants.append(normalized)
                seen.add(normalized)

        add(candidate)

        # Heuristic fallback: try with and without '/v1'.
        if candidate.endswith("/v1"):
            add(candidate[:-3].rstrip("/"))
        else:
            add(f"{candidate}/v1")

        # Lightning Studio URL support:
        # Convert ".../web-ui?port=8038" to ".../proxy/8038[/v1]".
        parsed = urlparse(candidate)
        port_param = parse_qs(parsed.query).get("port", [None])[0]
        if parsed.scheme in {"http", "https"} and port_param and port_param.isdigit():
            proxy_path = parsed.path.rstrip("/") + f"/proxy/{port_param}"
            base_proxy = urlunparse(
                parsed._replace(path=proxy_path, query="", fragment="")
            )
            add(base_proxy)
            add(f"{base_proxy}/v1")

            # Keep query variant for environments that route directly from web-ui.
            kept_query = urlencode({"port": port_param})
            query_variant = urlunparse(
                parsed._replace(query=kept_query, fragment="")
            )
            add(query_variant)
            add(f"{query_variant}/v1")

        return variants

    @staticmethod
    def _extract_json(text: str) -> dict[str, Any] | None:
        """Try to parse JSON from raw model output."""
        # Strip <think> or <thinking> blocks if present.
        text = re.sub(r"<(think|thinking)>.*?(?:</\1>|$)", "", text, flags=re.DOTALL).strip()

        # Try direct parse first.
        try:
            return json.loads(text)
        except json.JSONDecodeError:
            pass

        # Try extracting JSON from markdown code fences.
        match = re.search(r"```(?:json)?\s*\n?(.*?)\n?```", text, re.DOTALL)
        if match:
            try:
                return json.loads(match.group(1).strip())
            except json.JSONDecodeError:
                pass

        # Try finding first { ... } block.
        brace_match = re.search(r"\{.*\}", text, re.DOTALL)
        if brace_match:
            try:
                return json.loads(brace_match.group(0))
            except json.JSONDecodeError:
                pass

        # Last attempt for truncated payloads: repair + balance braces/brackets.
        repaired = TranslationGateway._repair_json(text)
        balanced = TranslationGateway._balance_json_delimiters(repaired)
        try:
            return json.loads(balanced)
        except json.JSONDecodeError:
            pass

        return None

    @staticmethod
    def _repair_json(text: str) -> str:
        """One-pass attempt to fix common JSON issues from LLM output."""
        # Strip markdown fences.
        text = re.sub(r"```(?:json)?\s*\n?", "", text)
        text = re.sub(r"\n?```", "", text)

        # Strip <think> or <thinking> blocks.
        text = re.sub(r"<(think|thinking)>.*?(?:</\1>|$)", "", text, flags=re.DOTALL)

        # Remove trailing commas before } or ].
        text = re.sub(r",\s*([}\]])", r"\1", text)

        # Remove any non-JSON prefix/suffix.
        brace_start = text.find("{")
        if brace_start != -1:
            brace_end = text.rfind("}")
            if brace_end != -1 and brace_end > brace_start:
                text = text[brace_start : brace_end + 1]
            else:
                # Keep from first object start to end; balancing step may recover.
                text = text[brace_start:]

        return text.strip()

    @staticmethod
    def _balance_json_delimiters(text: str) -> str:
        """Close missing JSON braces/brackets for truncated outputs."""
        if not text:
            return text

        stack: list[str] = []
        out: list[str] = []
        in_string = False
        escaped = False

        for ch in text:
            if escaped:
                out.append(ch)
                escaped = False
                continue
            if ch == "\\":
                out.append(ch)
                escaped = True
                continue
            if ch == '"':
                out.append(ch)
                in_string = not in_string
                continue
            if in_string:
                # JSON strings cannot contain raw control characters.
                if ch == "\n":
                    out.append("\\n")
                elif ch == "\r":
                    out.append("\\r")
                elif ch == "\t":
                    out.append("\\t")
                elif ord(ch) < 0x20:
                    out.append(" ")
                else:
                    out.append(ch)
                continue
            out.append(ch)
            if ch in "{[":
                stack.append(ch)
            elif ch == "}" and stack and stack[-1] == "{":
                stack.pop()
            elif ch == "]" and stack and stack[-1] == "[":
                stack.pop()

        text = "".join(out)

        # Handle a dangling escape at end of truncated string.
        if escaped:
            text += "\\\\"

        if in_string:
            text += '"'

        while stack:
            opener = stack.pop()
            text += "}" if opener == "{" else "]"

        # Remove trailing comma before newly closed delimiters.
        text = re.sub(r",\s*([}\]])", r"\1", text)
        return text
