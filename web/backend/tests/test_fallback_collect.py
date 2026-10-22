import json
import sys
from dataclasses import dataclass
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import fallback_collect


@dataclass
class _Item:
    title: str


def _point_at(tmp_path, monkeypatch, collectors):
    output = tmp_path / "fallback_events.json"
    monkeypatch.setattr(fallback_collect, "OUTPUT_PATH", output)
    monkeypatch.setattr(fallback_collect, "STATUS_PATH", tmp_path / "fallback_status.json")
    monkeypatch.setattr(fallback_collect, "COLLECTORS", collectors)
    return output


def test_success_is_recorded_with_timestamp(tmp_path, monkeypatch):
    output = _point_at(tmp_path, monkeypatch, {"게임A": lambda: [_Item("e1")]})
    fallback_collect.main()

    status = json.loads((tmp_path / "fallback_status.json").read_text(encoding="utf-8"))["게임A"]
    assert status["ok"] is True and status["count"] == 1 and status["consecutiveFailures"] == 0
    assert status["lastSuccessAt"] == status["checkedAt"]
    assert json.loads(output.read_text(encoding="utf-8"))["게임A"] == [{"title": "e1"}]


def test_failure_keeps_previous_data_and_records_why(tmp_path, monkeypatch, capsys):
    output = _point_at(tmp_path, monkeypatch, {"게임A": lambda: [_Item("e1")]})
    fallback_collect.main()
    first_success = json.loads((tmp_path / "fallback_status.json").read_text(encoding="utf-8"))["게임A"]["lastSuccessAt"]

    def blocked():
        raise RuntimeError("HTTP Error 403: Forbidden")

    monkeypatch.setattr(fallback_collect, "COLLECTORS", {"게임A": blocked})
    fallback_collect.main()
    fallback_collect.main()

    status = json.loads((tmp_path / "fallback_status.json").read_text(encoding="utf-8"))["게임A"]
    assert status["ok"] is False
    assert "403" in status["error"]
    assert status["consecutiveFailures"] == 2
    assert status["lastSuccessAt"] == first_success
    assert json.loads(output.read_text(encoding="utf-8"))["게임A"] == [{"title": "e1"}]
    assert "::warning" in capsys.readouterr().out


def test_empty_result_counts_as_failure(tmp_path, monkeypatch):
    _point_at(tmp_path, monkeypatch, {"게임A": lambda: []})
    fallback_collect.main()
    status = json.loads((tmp_path / "fallback_status.json").read_text(encoding="utf-8"))["게임A"]
    assert status["ok"] is False and "no candidates" in status["error"]
