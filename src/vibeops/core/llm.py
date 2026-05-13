from __future__ import annotations

import time
from collections.abc import Iterator
from typing import Any, Literal

import openai
import tiktoken

from vibeops.core.errors import LLMError
from vibeops.core.prices import (
    GPT_4O_INPUT_PER_1K,
    GPT_4O_MINI_INPUT_PER_1K,
    GPT_4O_MINI_OUTPUT_PER_1K,
    GPT_4O_OUTPUT_PER_1K,
    PRICES_AS_OF,
)
from vibeops.models.results import ChatResult

_HIGH_QUALITY_MODEL = "gpt-4o"
_DEFAULT_MODEL = "gpt-4o-mini"

_MAX_RETRIES_RATE = 3
_MAX_RETRIES_CONNECTION = 2
_BACKOFF_BASE = 1.5


class LLMClient:
    """Centralised OpenAI wrapper. Only module that imports openai."""

    def __init__(self, api_key: str, default_model: str = _DEFAULT_MODEL) -> None:
        self._client = openai.OpenAI(api_key=api_key)
        self._default_model = default_model
        self._encoder = tiktoken.encoding_for_model("gpt-4o-mini")
        self._session_input_tokens: int = 0
        self._session_output_tokens: int = 0
        self._session_high_input_tokens: int = 0
        self._session_high_output_tokens: int = 0
        self._scrub_targets: list[str] = []

    def set_scrub_targets(self, targets: list[str]) -> None:
        self._scrub_targets = [t for t in targets if t]

    def _scrub(self, text: str) -> str:
        for target in self._scrub_targets:
            text = text.replace(target, "[REDACTED]")
        return text

    def _scrub_messages(self, messages: list[dict[str, Any]]) -> list[dict[str, Any]]:
        return [
            {**m, "content": self._scrub(str(m.get("content", "")))} for m in messages
        ]

    def _estimate_input_tokens(self, messages: list[dict[str, Any]]) -> int:
        total = 0
        for m in messages:
            total += len(self._encoder.encode(str(m.get("content", ""))))
        return total

    def _model_for_quality(self, quality: Literal["standard", "high"]) -> str:
        return _HIGH_QUALITY_MODEL if quality == "high" else self._default_model

    def chat_completion(
        self,
        messages: list[dict[str, Any]],
        *,
        model: str | None = None,
        temperature: float = 0.2,
        response_format: dict[str, Any] | None = None,
        quality: Literal["standard", "high"] = "standard",
    ) -> ChatResult:
        resolved_model = model or self._model_for_quality(quality)
        scrubbed = self._scrub_messages(messages)
        estimated_input = self._estimate_input_tokens(scrubbed)

        kwargs: dict[str, Any] = {
            "model": resolved_model,
            "messages": scrubbed,
            "temperature": temperature,
        }
        if response_format is not None:
            kwargs["response_format"] = response_format

        last_exc: Exception | None = None
        for attempt in range(_MAX_RETRIES_RATE):
            try:
                response = self._client.chat.completions.create(**kwargs)
                usage = response.usage
                if usage is not None:
                    in_tok = usage.prompt_tokens
                    out_tok = usage.completion_tokens
                else:
                    out_tok = len(self._encoder.encode(
                        response.choices[0].message.content or ""
                    ))
                    in_tok = estimated_input
                self._accumulate(resolved_model, in_tok, out_tok)
                content = response.choices[0].message.content or ""
                return ChatResult(content=content, input_tokens=in_tok, output_tokens=out_tok)
            except (openai.RateLimitError, openai.APITimeoutError) as exc:
                last_exc = exc
                time.sleep(_BACKOFF_BASE**attempt)
            except openai.APIConnectionError as exc:
                last_exc = exc
                if attempt >= _MAX_RETRIES_CONNECTION - 1:
                    break
                time.sleep(_BACKOFF_BASE)
            except openai.OpenAIError as exc:
                raise LLMError(str(exc)) from exc

        raise LLMError(f"LLM call failed after retries: {last_exc}") from last_exc

    def stream_text(
        self,
        messages: list[dict[str, Any]],
        *,
        temperature: float = 0.3,
    ) -> Iterator[str]:
        scrubbed = self._scrub_messages(messages)
        estimated_input = self._estimate_input_tokens(scrubbed)
        collected: list[str] = []
        try:
            raw_stream = self._client.chat.completions.create(
                model=self._default_model,
                messages=scrubbed,  # type: ignore[arg-type]
                temperature=temperature,
                stream=True,
            )
            for chunk in raw_stream:
                content = chunk.choices[0].delta.content if chunk.choices else None  # type: ignore[union-attr]
                if content:
                    collected.append(content)
                    yield content
        except openai.OpenAIError as exc:
            raise LLMError(str(exc)) from exc
        output_text = "".join(collected)
        out_tok = len(self._encoder.encode(output_text))
        self._accumulate(self._default_model, estimated_input, out_tok)

    def _accumulate(self, model: str, in_tok: int, out_tok: int) -> None:
        if model == _HIGH_QUALITY_MODEL:
            self._session_high_input_tokens += in_tok
            self._session_high_output_tokens += out_tok
        else:
            self._session_input_tokens += in_tok
            self._session_output_tokens += out_tok

    def session_spend_usd(self) -> float:
        mini = (
            self._session_input_tokens / 1000 * GPT_4O_MINI_INPUT_PER_1K
            + self._session_output_tokens / 1000 * GPT_4O_MINI_OUTPUT_PER_1K
        )
        high = (
            self._session_high_input_tokens / 1000 * GPT_4O_INPUT_PER_1K
            + self._session_high_output_tokens / 1000 * GPT_4O_OUTPUT_PER_1K
        )
        return mini + high

    @property
    def prices_as_of(self) -> str:
        return PRICES_AS_OF
