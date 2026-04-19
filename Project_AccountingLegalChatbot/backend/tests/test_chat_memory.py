"""Tests for chat sliding window memory."""
import pytest

from api.chat import _build_sliding_context


class FakeMessage:
    def __init__(self, content: str):
        self.content = content


def test_sliding_window_keeps_last_20():
    msgs = [FakeMessage(f"msg {i}") for i in range(30)]
    result = _build_sliding_context(msgs, max_messages=20)
    assert len(result) == 20
    assert result[0].content == "msg 10"
    assert result[-1].content == "msg 29"


def test_sliding_window_trims_long_messages():
    # Each message is ~2000 chars = ~500 tokens; 20 messages = ~10000 tokens > 6000 limit
    msgs = [FakeMessage("x" * 2000) for _ in range(20)]
    result = _build_sliding_context(msgs, max_messages=20, max_tokens_estimate=6000)
    assert len(result) < 20
    assert len(result) >= 2  # minimum 2 kept


def test_sliding_window_keeps_minimum_2():
    msgs = [FakeMessage("x" * 50000) for _ in range(5)]
    result = _build_sliding_context(msgs, max_messages=20, max_tokens_estimate=100)
    assert len(result) == 2


def test_sliding_window_short_history():
    msgs = [FakeMessage("hello") for _ in range(3)]
    result = _build_sliding_context(msgs, max_messages=20)
    assert len(result) == 3
