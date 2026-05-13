from __future__ import annotations

from unittest.mock import MagicMock, patch

import openai
import pytest

from vibeops.core.llm import LLMClient


def _make_response(content: str, input_tok: int = 10, output_tok: int = 20) -> MagicMock:
    resp = MagicMock()
    resp.choices = [MagicMock()]
    resp.choices[0].message.content = content
    resp.usage = MagicMock()
    resp.usage.prompt_tokens = input_tok
    resp.usage.completion_tokens = output_tok
    return resp


def test_standard_quality_uses_mini_model() -> None:
    client = LLMClient(api_key="sk-fake")
    with patch.object(client._client.chat.completions, "create") as mock_create:
        mock_create.return_value = _make_response("hello")
        client.chat_completion([{"role": "user", "content": "hi"}], quality="standard")
    call_kwargs = mock_create.call_args[1]
    assert "gpt-4o-mini" in call_kwargs.get("model", "")


def test_high_quality_uses_gpt4o_model() -> None:
    client = LLMClient(api_key="sk-fake")
    with patch.object(client._client.chat.completions, "create") as mock_create:
        mock_create.return_value = _make_response("hello")
        client.chat_completion([{"role": "user", "content": "hi"}], quality="high")
    call_kwargs = mock_create.call_args[1]
    assert call_kwargs.get("model") == "gpt-4o"


def test_spend_accumulates_across_calls() -> None:
    client = LLMClient(api_key="sk-fake")
    with patch.object(client._client.chat.completions, "create") as mock_create:
        mock_create.return_value = _make_response("hello", input_tok=1000, output_tok=500)
        client.chat_completion([{"role": "user", "content": "hi"}])
        client.chat_completion([{"role": "user", "content": "hi again"}])
    spend = client.session_spend_usd()
    assert spend > 0
    # 2000 input tokens + 1000 output at gpt-4o-mini rates
    expected = (2000 / 1000 * 0.00015) + (1000 / 1000 * 0.00060)
    assert abs(spend - expected) < 0.001


def test_retries_on_rate_limit() -> None:
    client = LLMClient(api_key="sk-fake")
    responses = [
        openai.RateLimitError("rate limit", response=MagicMock(), body={}),
        openai.RateLimitError("rate limit", response=MagicMock(), body={}),
        _make_response("ok"),
    ]
    with patch.object(client._client.chat.completions, "create", side_effect=responses):
        with patch("vibeops.core.llm.time.sleep"):
            result = client.chat_completion([{"role": "user", "content": "test"}])
    assert result.content == "ok"


def test_raises_llm_error_after_max_retries() -> None:
    from vibeops.core.errors import LLMError

    client = LLMClient(api_key="sk-fake")
    with patch.object(
        client._client.chat.completions,
        "create",
        side_effect=openai.RateLimitError("rate limit", response=MagicMock(), body={}),
    ):
        with patch("vibeops.core.llm.time.sleep"):
            with pytest.raises(LLMError):
                client.chat_completion([{"role": "user", "content": "test"}])


def test_scrubbing_removes_project_id() -> None:
    client = LLMClient(api_key="sk-fake")
    client.set_scrub_targets(["my-secret-project"])
    captured: list[dict[str, str]] = []

    def _capture(**kwargs: object) -> MagicMock:
        captured.extend(kwargs.get("messages", []))  # type: ignore[arg-type]
        return _make_response("ok")

    with patch.object(client._client.chat.completions, "create", side_effect=_capture):
        client.chat_completion(
            [{"role": "user", "content": "use project my-secret-project"}]
        )

    assert all("my-secret-project" not in m["content"] for m in captured)


def test_tiktoken_encoder_loads() -> None:
    client = LLMClient(api_key="sk-fake")
    tokens = client._encoder.encode("hello world")
    assert len(tokens) > 0


def test_zero_spend_initially() -> None:
    client = LLMClient(api_key="sk-fake")
    assert client.session_spend_usd() == 0.0


def test_high_quality_spend_uses_gpt4o_rates() -> None:
    """quality='high' tokens are billed at gpt-4o rates, not gpt-4o-mini rates."""
    from vibeops.core.prices import GPT_4O_INPUT_PER_1K, GPT_4O_OUTPUT_PER_1K

    client = LLMClient(api_key="sk-fake")
    with patch.object(client._client.chat.completions, "create") as mock_create:
        mock_create.return_value = _make_response("hello", input_tok=1000, output_tok=500)
        client.chat_completion([{"role": "user", "content": "hi"}], quality="high")

    spend = client.session_spend_usd()
    expected = (1000 / 1000 * GPT_4O_INPUT_PER_1K) + (500 / 1000 * GPT_4O_OUTPUT_PER_1K)
    assert abs(spend - expected) < 0.0001


def test_mixed_quality_spend_accumulates_separately() -> None:
    """Standard and high-quality calls accumulate spend independently."""
    from vibeops.core.prices import (
        GPT_4O_INPUT_PER_1K,
        GPT_4O_MINI_INPUT_PER_1K,
        GPT_4O_MINI_OUTPUT_PER_1K,
        GPT_4O_OUTPUT_PER_1K,
    )

    client = LLMClient(api_key="sk-fake")
    with patch.object(client._client.chat.completions, "create") as mock_create:
        mock_create.return_value = _make_response("ok", input_tok=1000, output_tok=200)
        client.chat_completion([{"role": "user", "content": "standard"}], quality="standard")
        client.chat_completion([{"role": "user", "content": "high"}], quality="high")

    spend = client.session_spend_usd()
    mini_spend = (1000 / 1000 * GPT_4O_MINI_INPUT_PER_1K) + (200 / 1000 * GPT_4O_MINI_OUTPUT_PER_1K)
    high_spend = (1000 / 1000 * GPT_4O_INPUT_PER_1K) + (200 / 1000 * GPT_4O_OUTPUT_PER_1K)
    assert abs(spend - (mini_spend + high_spend)) < 0.0001
