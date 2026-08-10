"""Provider-agnostic AI classification client. classify(prompt, schema) -> dict.

Default provider is anthropic (AI_PROVIDER env var, default "anthropic").
openai is not implemented yet — the interface is kept thin on purpose
(design doc: don't build unused abstraction) but the seam exists so the
existing Codex-project OpenAI assets aren't a dead end if ever needed.

Structured output uses Claude's tool-use forcing (tool_choice pinned to
one tool whose input_schema is the pydantic model's JSON schema) rather
than asking the model to emit JSON in prose and hoping it parses.
"""
import os
import json
from typing import Type, TypeVar

from dotenv import load_dotenv
from pydantic import BaseModel

load_dotenv()

T = TypeVar("T", bound=BaseModel)

HAIKU_MODEL = "claude-haiku-4-5-20251001"
SONNET_MODEL = "claude-sonnet-5"


class ClassificationError(Exception):
    """Raised when the model's output doesn't validate against the schema."""


def _unstringify_nested_json(value):
    """Occasionally (observed on 202602/202603) the model stuffs a nested
    array/object as a JSON-encoded string instead of real nested JSON, even
    with tool-use forcing — e.g. {"sections": "[{...}]"} instead of
    {"sections": [{...}]}. Recursively un-stringify anything that looks
    like it, so a real structural problem still fails validation instead
    of being masked, but this formatting quirk doesn't."""
    if isinstance(value, dict):
        return {k: _unstringify_nested_json(v) for k, v in value.items()}
    if isinstance(value, list):
        return [_unstringify_nested_json(v) for v in value]
    if isinstance(value, str) and value.strip()[:1] in "[{":
        try:
            return _unstringify_nested_json(json.loads(value))
        except (json.JSONDecodeError, ValueError):
            return value
    return value


def _unwrap_self_nesting(value):
    """Confirmed directly on 202602's raw Sonnet response: the stringified
    value from _unstringify_nested_json can itself be a dict that redundantly
    re-wraps the very same key one level deeper — the tool call came back
    as {"sections": "{\\"sections\\": [...]}"} (a JSON string, itself an
    object with a "sections" key holding the real array), so after
    unstringifying you're left with {"sections": {"sections": [...]}}, still
    one level too deep for the schema. If a dict's value is itself a dict
    whose only key is that same key name, unwrap it — recurse first so this
    also catches it nested deeper than the top level."""
    if isinstance(value, dict):
        unwrapped = {k: _unwrap_self_nesting(v) for k, v in value.items()}
        return {
            k: (v[k] if isinstance(v, dict) and set(v.keys()) == {k} else v)
            for k, v in unwrapped.items()
        }
    if isinstance(value, list):
        return [_unwrap_self_nesting(v) for v in value]
    return value


def _anthropic_classify(system_prompt: str, user_prompt: str, schema_model: Type[T], model: str) -> T:
    import anthropic

    client = anthropic.Anthropic()  # reads ANTHROPIC_API_KEY from env
    tool_name = "emit_" + schema_model.__name__.lower()
    tool = {
        "name": tool_name,
        "description": f"Emit the classification result as {schema_model.__name__}.",
        "input_schema": schema_model.model_json_schema(),
    }

    response = client.messages.create(
        model=model,
        max_tokens=4096,
        # No temperature override: claude-sonnet-5 rejects it outright
        # ("temperature is deprecated for this model"), and Haiku accepts
        # but only one of the two models actually needs it pinned. Run-to-
        # run variance on borderline sections is handled by the existing
        # confidence-threshold escalation instead (design principle 4).
        system=system_prompt,
        tools=[tool],
        tool_choice={"type": "tool", "name": tool_name},
        messages=[{"role": "user", "content": user_prompt}],
    )

    for block in response.content:
        if block.type == "tool_use" and block.name == tool_name:
            if response.stop_reason == "max_tokens":
                raise ClassificationError(
                    "response truncated at max_tokens — output was too large to finish "
                    "(likely too many items in one section), not a real schema mismatch"
                )
            if not isinstance(block.input, dict):
                raise ClassificationError(
                    f"tool_use input was not a JSON object (got {type(block.input).__name__}), "
                    "likely a truncated/malformed response"
                )
            try:
                cleaned = _unwrap_self_nesting(_unstringify_nested_json(block.input))
                return schema_model.model_validate(cleaned)
            except Exception as e:
                raise ClassificationError(f"schema validation failed: {e}") from e

    raise ClassificationError("model did not return a tool_use block")


def _openai_classify(system_prompt: str, user_prompt: str, schema_model: Type[T], model: str) -> T:
    import openai

    client = openai.OpenAI()  # reads OPENAI_API_KEY from env
    tool_name = "emit_" + schema_model.__name__.lower()
    tool = {
        "type": "function",
        "function": {
            "name": tool_name,
            "description": f"Emit the classification result as {schema_model.__name__}.",
            "parameters": schema_model.model_json_schema(),
        },
    }

    response = client.chat.completions.create(
        model=model,
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
        tools=[tool],
        tool_choice={"type": "function", "function": {"name": tool_name}},
    )

    message = response.choices[0].message
    if not message.tool_calls:
        raise ClassificationError("model did not return a tool call")

    call = message.tool_calls[0]
    try:
        raw = json.loads(call.function.arguments)
    except json.JSONDecodeError as e:
        raise ClassificationError(f"tool call arguments were not valid JSON: {e}") from e

    try:
        # same defensive cleanup as the Anthropic path — a model stuffing
        # nested JSON as a string instead of a real object isn't unique to
        # one provider
        cleaned = _unwrap_self_nesting(_unstringify_nested_json(raw))
        return schema_model.model_validate(cleaned)
    except Exception as e:
        raise ClassificationError(f"schema validation failed: {e}") from e


def classify(
    system_prompt: str, user_prompt: str, schema_model: Type[T], model: str, provider: str | None = None,
) -> T:
    """provider defaults to the AI_PROVIDER env var (unchanged behavior for
    existing callers, e.g. tools/classify_month.py) — pass it explicitly to
    pin a specific call to a provider regardless of that global default,
    which is how web/backend/app/industry_brief/classifier.py uses OpenAI
    without touching the PPT pipeline's Anthropic setup."""
    provider = provider or os.environ.get("AI_PROVIDER", "anthropic")
    if provider == "anthropic":
        return _anthropic_classify(system_prompt, user_prompt, schema_model, model)
    if provider == "openai":
        return _openai_classify(system_prompt, user_prompt, schema_model, model)
    raise ValueError(f"unknown AI_PROVIDER: {provider!r}")
