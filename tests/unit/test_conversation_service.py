"""Pure requirement-conversation logic extracted from ui/chat.py."""
from __future__ import annotations

from vibeops.models.conversation import ConversationTurn, TurnRole
from vibeops.services.conversation import evaluate_turn, is_affirmative


def test_is_affirmative() -> None:
    assert is_affirmative("yes")
    assert is_affirmative("Yes!")
    assert is_affirmative("looks good")
    assert is_affirmative("lgtm")
    assert not is_affirmative("")
    assert not is_affirmative("no, change the disk")
    assert not is_affirmative("can you use an A100 instead")  # long → not a confirmation


def test_proceeds_only_with_token_and_confirmation() -> None:
    r = evaluate_turn([], "yes", "Great, deploying now. [[PROCEED]]")
    assert r.proceed is True
    assert "[[PROCEED]]" not in r.cleaned_response
    assert r.new_conversation[-2]["content"] == "yes"


def test_token_without_confirmation_does_not_proceed() -> None:
    r = evaluate_turn([], "actually use 2 GPUs", "Sure. [[PROCEED]]")
    assert r.proceed is False
    assert "[[PROCEED]]" not in r.cleaned_response


def test_no_token_does_not_proceed() -> None:
    r = evaluate_turn([], "yes", "How much disk do you need?")
    assert r.proceed is False


def test_appends_user_and_agent_turns() -> None:
    existing = [ConversationTurn(role=TurnRole.AGENT, content="hi")]
    r = evaluate_turn(existing, "yes", "ok [[PROCEED]]")
    assert len(r.new_conversation) == 3
    assert r.new_conversation[-1]["content"] == "ok"
