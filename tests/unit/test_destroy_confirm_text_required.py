from __future__ import annotations

from vibeops.ui.deployment import _is_confirm_valid


def test_lowercase_destroy_valid() -> None:
    assert _is_confirm_valid("destroy") is True


def test_uppercase_destroy_valid() -> None:
    assert _is_confirm_valid("DESTROY") is True


def test_mixed_case_destroy_valid() -> None:
    assert _is_confirm_valid("Destroy") is True


def test_with_whitespace_valid() -> None:
    assert _is_confirm_valid("  destroy  ") is True


def test_yes_invalid() -> None:
    assert _is_confirm_valid("yes") is False


def test_empty_invalid() -> None:
    assert _is_confirm_valid("") is False


def test_partial_word_invalid() -> None:
    assert _is_confirm_valid("destro") is False


def test_extra_chars_invalid() -> None:
    assert _is_confirm_valid("destroy!") is False
