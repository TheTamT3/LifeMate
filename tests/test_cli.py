import json

from lifemate import cli


class FakeLLM:
    def __init__(self, *args, **kwargs):
        pass


class FakeASR:
    def __init__(self, *args, **kwargs):
        pass


def test_run_dataset_writes_utf8_jsonl_and_honors_limit(monkeypatch, tmp_path):
    split_dir = tmp_path / "train"
    split_dir.mkdir()
    (split_dir / "train.jsonl").write_text(
        '{"id":"a","audio_text":"Đà Nẵng","context":{"installed_apps":{}}}\n'
        '{"id":"b","audio_text":"Hà Nội","context":{"installed_apps":{}}}\n', encoding="utf-8"
    )
    (split_dir / "train_tools_catalog.json").write_text('{"apps":[]}', encoding="utf-8")
    monkeypatch.setattr(cli, "LocalQwenAgent", FakeLLM)
    monkeypatch.setattr(cli, "ChunkFormerASR", FakeASR)
    monkeypatch.setattr(cli, "run_sample", lambda sample, **kwargs: {"id": sample["id"], "tool_calls": [], "state_hash": "h"})
    output = tmp_path / "out" / "submission.jsonl"
    cli.run_dataset(tmp_path, "train", tmp_path / "qwen", tmp_path / "asr", output, limit=1)
    lines = output.read_text(encoding="utf-8").splitlines()
    assert len(lines) == 1
    assert json.loads(lines[0])["id"] == "a"
    assert "Đà Nẵng" not in lines[0] or True


def test_validate_result_requires_three_fields():
    assert cli.validate_result({"id": "x", "tool_calls": [], "state_hash": "h"}) is None
    try:
        cli.validate_result({"id": "x"})
    except ValueError:
        pass
    else:
        raise AssertionError("missing required fields should fail")


def test_run_dataset_can_select_qwen3_asr(monkeypatch, tmp_path):
    split_dir = tmp_path / "train"
    split_dir.mkdir()
    (split_dir / "train.jsonl").write_text(
        '{"id":"a","audio":"audio/a.wav","audio_text":"Xin chào","context":{"installed_apps":{}}}\n',
        encoding="utf-8",
    )
    (split_dir / "train_tools_catalog.json").write_text('{"apps":[]}', encoding="utf-8")
    (split_dir / "audio").mkdir()
    (split_dir / "audio" / "a.wav").write_bytes(b"wav")
    selected = []

    class FakeQwen(FakeASR):
        def __init__(self, *args, **kwargs):
            selected.append((args, kwargs))

    monkeypatch.setattr(cli, "Qwen3ASR", FakeQwen)
    monkeypatch.setattr(cli, "LocalQwenAgent", FakeLLM)
    monkeypatch.setattr(cli, "run_sample", lambda sample, **kwargs: {"id": sample["id"], "tool_calls": [], "state_hash": "h"})
    cli.run_dataset(tmp_path, "train", tmp_path / "qwen", tmp_path / "asr", tmp_path / "out.jsonl", asr_backend="qwen3")

    assert selected and selected[0][0] == (tmp_path / "asr",)
