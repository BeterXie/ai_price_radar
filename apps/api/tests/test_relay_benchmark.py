import json

import pytest

from app.services.relay_benchmark import candy_answer
from app.services.relay_probe_metrics import ProbeStream, completion_text, output_truncated


@pytest.mark.parametrize("answer", ["21", " ２１。 ", "**21**", "最终答案是：21颗糖果。", "二十一", "The answer is 21."])
def test_single_final_answer_passes(answer):
    assert candy_answer(answer) == ("passed", "21")


@pytest.mark.parametrize("answer", ["121", "31", "答案：20", "0"])
def test_other_final_integers_fail(answer):
    verdict, value = candy_answer(answer)
    assert verdict == "failed" and value != "21"


@pytest.mark.parametrize("answer", ["", "2 1", "2\n1", "2**1", "21.0", "21 or 31", "不是21，应该是31", "I think it could be 21", "21" + " " * 512])
def test_ambiguous_or_missing_answers_are_inconclusive(answer):
    assert candy_answer(answer) == ("inconclusive", None)


def test_truncated_correct_answer_is_not_a_pass():
    assert candy_answer("21", truncated=True) == ("inconclusive", None)


@pytest.mark.parametrize(("protocol", "payload"), [
    ("openai", {"choices": [{"message": {"content": "21"}, "finish_reason": "length"}]}),
    ("anthropic", {"content": [{"type": "thinking", "thinking": "31"}, {"type": "text", "text": "21"}], "stop_reason": "max_tokens"}),
    ("gemini", {"candidates": [{"content": {"parts": [{"text": "31", "thought": True}, {"text": "21"}]}, "finishReason": "MAX_TOKENS"}]}),
])
def test_json_extracts_only_final_text_and_tracks_truncation(protocol, payload):
    assert completion_text(protocol, payload) == "21"
    assert output_truncated(protocol, payload)


def test_stream_keeps_split_final_text_but_not_reasoning_or_unbounded_answers():
    stream = ProbeStream("openai", 0)
    for delta in ({"reasoning_content": "21"}, {"content": "1"}, {"content": "21"}):
        stream.feed(b"data: " + json.dumps({"choices": [{"delta": delta}]}).encode() + b"\n\n")
    stream.feed(b"data: [DONE]\n\n")
    assert stream.healthy and stream.answer == "121"
    assert candy_answer(stream.answer) == ("failed", "121")
    stream.feed(b'data: {"choices":[{"delta":{"content":"' + b"x" * 600 + b'"}}]}\n\n')
    assert len(stream.answer) == 512 and stream.answer_truncated
