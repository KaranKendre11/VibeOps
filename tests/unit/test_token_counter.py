from __future__ import annotations

from unittest.mock import MagicMock, patch

from vibeops.core.llm import LLMClient
from vibeops.core.prices import (
    GPT_4O_MINI_INPUT_PER_1K,
    GPT_4O_MINI_OUTPUT_PER_1K,
)


def _make_response(content: str, input_tok: int, output_tok: int) -> MagicMock:
    resp = MagicMock()
    resp.choices = [MagicMock()]
    resp.choices[0].message.content = content
    resp.usage = MagicMock()
    resp.usage.prompt_tokens = input_tok
    resp.usage.completion_tokens = output_tok
    return resp


def _expected_spend(in_tok: int, out_tok: int) -> float:
    return (
        in_tok / 1000 * GPT_4O_MINI_INPUT_PER_1K
        + out_tok / 1000 * GPT_4O_MINI_OUTPUT_PER_1K
    )


def test_one_call_spend_within_5pct() -> None:
    client = LLMClient(api_key="sk-fake")
    with patch.object(client._client.chat.completions, "create") as mock_create:
        mock_create.return_value = _make_response("answer", input_tok=500, output_tok=100)
        client.chat_completion([{"role": "user", "content": "question"}])

    spend = client.session_spend_usd()
    expected = _expected_spend(500, 100)
    assert abs(spend - expected) / expected < 0.05


def test_five_call_spend_within_5pct() -> None:
    client = LLMClient(api_key="sk-fake")
    total_in = 0
    total_out = 0
    call_specs = [
        (300, 80),
        (400, 120),
        (350, 90),
        (420, 110),
        (380, 100),
    ]
    responses = [_make_response("ans", i, o) for i, o in call_specs]

    with patch.object(client._client.chat.completions, "create", side_effect=responses):
        for _ in call_specs:
            client.chat_completion([{"role": "user", "content": "q"}])

    for i, o in call_specs:
        total_in += i
        total_out += o

    spend = client.session_spend_usd()
    expected = _expected_spend(total_in, total_out)
    assert abs(spend - expected) / expected < 0.05
