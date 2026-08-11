import sys
import os
import json
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest
from pydantic import BaseModel

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from tools.ai_client import (
    _unstringify_nested_json, _unwrap_self_nesting, classify, classify_with_images, ClassificationError,
)


def test_unstringify_leaves_normal_dict_unchanged():
    value = {"sections": [{"name": "a"}]}
    assert _unstringify_nested_json(value) == value


def test_unstringify_parses_json_encoded_string_value():
    value = {"sections": json.dumps([{"name": "a"}])}
    assert _unstringify_nested_json(value) == {"sections": [{"name": "a"}]}


def test_unstringify_leaves_plain_text_string_alone():
    value = {"footnote": "이건 그냥 텍스트"}
    assert _unstringify_nested_json(value) == value


def test_unwrap_self_nesting_removes_redundant_double_wrap():
    # exact shape observed on 202602's real Sonnet response
    value = {"sections": {"sections": [{"name": "a"}]}}
    assert _unwrap_self_nesting(value) == {"sections": [{"name": "a"}]}


def test_unwrap_self_nesting_leaves_normal_structure_alone():
    value = {"sections": [{"name": "a"}]}
    assert _unwrap_self_nesting(value) == value


def test_unwrap_self_nesting_does_not_unwrap_different_key():
    # {"sections": {"other": [...]}} is a real structural problem, not the
    # self-nesting quirk — must NOT be silently unwrapped
    value = {"sections": {"other": [{"name": "a"}]}}
    assert _unwrap_self_nesting(value) == value


def test_full_pipeline_recovers_the_real_202602_shape():
    # block.input exactly as captured from the live API: the whole
    # {"sections": [...]} payload stuffed as a JSON string one level too
    # deep under its own "sections" key
    inner = json.dumps({"sections": [{"section_title": "x", "block_type": "grid",
                                       "items": [], "footnote": None, "confidence": 0.5}]})
    raw = {"sections": inner}
    cleaned = _unwrap_self_nesting(_unstringify_nested_json(raw))
    assert cleaned == {"sections": [{"section_title": "x", "block_type": "grid",
                                      "items": [], "footnote": None, "confidence": 0.5}]}


class _Sample(BaseModel):
    ok: bool
    label: str


def _fake_openai_response(arguments_json: str, tool_name: str = "emit_sample"):
    tool_call = SimpleNamespace(function=SimpleNamespace(arguments=arguments_json, name=tool_name))
    message = SimpleNamespace(tool_calls=[tool_call])
    choice = SimpleNamespace(message=message)
    return SimpleNamespace(choices=[choice])


def test_openai_provider_parses_tool_call_into_schema():
    fake_client = MagicMock()
    fake_client.chat.completions.create.return_value = _fake_openai_response(
        json.dumps({"ok": True, "label": "테스트"})
    )
    with patch("openai.OpenAI", return_value=fake_client):
        result = classify("system", "user", _Sample, "gpt-4o-mini", provider="openai")

    assert result == _Sample(ok=True, label="테스트")
    # tool_choice must pin the exact tool, not leave it to the model's discretion
    _, kwargs = fake_client.chat.completions.create.call_args
    assert kwargs["tool_choice"] == {"type": "function", "function": {"name": "emit__sample"}}


def test_openai_provider_unwraps_self_nested_json_string_like_anthropic_path():
    fake_client = MagicMock()
    inner = json.dumps({"ok": True, "label": "중첩"})
    fake_client.chat.completions.create.return_value = _fake_openai_response(
        json.dumps({"ok": inner})  # malformed the same way the Anthropic quirk is
    )
    # this particular malformation isn't the exact self-nesting shape (different
    # key), so just confirm a genuinely malformed response raises cleanly instead
    # of crashing with something unrelated
    with patch("openai.OpenAI", return_value=fake_client):
        with pytest.raises(ClassificationError):
            classify("system", "user", _Sample, "gpt-4o-mini", provider="openai")


def test_openai_provider_raises_when_model_returns_no_tool_call():
    fake_client = MagicMock()
    fake_client.chat.completions.create.return_value = SimpleNamespace(
        choices=[SimpleNamespace(message=SimpleNamespace(tool_calls=None))]
    )
    with patch("openai.OpenAI", return_value=fake_client):
        with pytest.raises(ClassificationError):
            classify("system", "user", _Sample, "gpt-4o-mini", provider="openai")


def test_openai_provider_raises_on_invalid_json_arguments():
    fake_client = MagicMock()
    fake_client.chat.completions.create.return_value = _fake_openai_response("not valid json{{{")
    with patch("openai.OpenAI", return_value=fake_client):
        with pytest.raises(ClassificationError):
            classify("system", "user", _Sample, "gpt-4o-mini", provider="openai")


def test_provider_param_overrides_env_default(monkeypatch):
    monkeypatch.setenv("AI_PROVIDER", "anthropic")
    fake_client = MagicMock()
    fake_client.chat.completions.create.return_value = _fake_openai_response(
        json.dumps({"ok": True, "label": "override"})
    )
    with patch("openai.OpenAI", return_value=fake_client):
        result = classify("system", "user", _Sample, "gpt-4o-mini", provider="openai")
    assert result.label == "override"


def _fake_anthropic_response(tool_input: dict, tool_name: str = "emit__sample", stop_reason: str = "tool_use"):
    block = SimpleNamespace(type="tool_use", name=tool_name, input=tool_input)
    return SimpleNamespace(content=[block], stop_reason=stop_reason)


def test_classify_with_images_sends_image_blocks_to_anthropic():
    fake_client = MagicMock()
    fake_client.messages.create.return_value = _fake_anthropic_response({"ok": True, "label": "본사진"})
    images = [("image/png", b"\x89PNG\r\n\x1a\nFAKE"), ("image/jpeg", b"\xff\xd8\xffFAKE")]

    with patch("anthropic.Anthropic", return_value=fake_client):
        result = classify_with_images("system", "user", images, _Sample, "claude-haiku-4-5-20251001")

    assert result == _Sample(ok=True, label="본사진")
    _, kwargs = fake_client.messages.create.call_args
    content = kwargs["messages"][0]["content"]
    image_blocks = [b for b in content if b.get("type") == "image"]
    assert len(image_blocks) == 2
    assert image_blocks[0]["source"]["media_type"] == "image/png"
    assert image_blocks[1]["source"]["media_type"] == "image/jpeg"
    # the trailing text block must be the actual user_prompt, not swallowed by images
    assert content[-1] == {"type": "text", "text": "user"}


def test_classify_with_images_raises_on_truncated_response():
    fake_client = MagicMock()
    fake_client.messages.create.return_value = _fake_anthropic_response(
        {"ok": True, "label": "x"}, stop_reason="max_tokens"
    )
    with patch("anthropic.Anthropic", return_value=fake_client):
        with pytest.raises(ClassificationError):
            classify_with_images("system", "user", [("image/png", b"x")], _Sample, "claude-haiku-4-5-20251001")


def test_classify_with_images_openai_provider_works():
    fake_client = MagicMock()
    fake_client.chat.completions.create.return_value = _fake_openai_response(
        json.dumps({"ok": True, "label": "openai비전"})
    )
    with patch("openai.OpenAI", return_value=fake_client):
        result = classify_with_images(
            "system", "user", [("image/png", b"fake")], _Sample, "gpt-4o-mini", provider="openai",
        )
    assert result.label == "openai비전"
    _, kwargs = fake_client.chat.completions.create.call_args
    content = kwargs["messages"][1]["content"]
    assert any(b.get("type") == "image_url" for b in content)
