import sys
import os
import json

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from tools.ai_client import _unstringify_nested_json, _unwrap_self_nesting


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
