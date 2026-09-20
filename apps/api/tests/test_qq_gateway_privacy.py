from pathlib import Path


def test_qq_gateway_does_not_log_private_message_bodies():
    source = (
        Path(__file__).resolve().parents[3] / "extensions" / "bots" / "qq_gateway.py"
    ).read_text(encoding="utf-8")
    assert "Inbound message: '{raw_content}'" not in source
    assert "raw_content[:20]" not in source
    assert "reply_text[:30]" not in source
    assert "'{cleaned_content}'" not in source
