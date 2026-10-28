import json
from pathlib import Path

import pytest

from lifemate.asr_eval.evaluator import evaluate_dataset


class FakeASR:
    def __init__(self, responses: dict[str, str] | None = None, failures: set[str] | None = None):
        self.responses = responses or {}
        self.failures = failures or set()
        self.paths: list[Path] = []

    def transcribe(self, audio_path: Path) -> str:
        self.paths.append(audio_path)
        if audio_path.name in self.failures:
            raise RuntimeError("decode failed")
        return self.responses.get(audio_path.name, "")


class FakeBatchASR(FakeASR):
    def __init__(self, responses: dict[str, str] | None = None):
        super().__init__(responses)
        self.batch_paths: list[list[Path]] = []

    def transcribe_batch(self, audio_paths: list[Path]) -> list[str]:
        self.batch_paths.append(audio_paths)
        return [self.responses.get(path.name, "") for path in audio_paths]


def write_dataset(root: Path, samples: list[dict]) -> None:
    split = root / "train"
    split.mkdir(parents=True)
    (split / "train.jsonl").write_text(
        "\n".join(json.dumps(sample, ensure_ascii=False) for sample in samples) + "\n",
        encoding="utf-8",
    )


def test_evaluate_dataset_resolves_audio_and_writes_utf8_outputs(tmp_path):
    sample = {"id": "train_0001", "audio": "audio/a.wav", "audio_text": "Xin chào"}
    write_dataset(tmp_path, [sample])
    audio = tmp_path / "train" / "audio" / "a.wav"
    audio.parent.mkdir()
    audio.write_bytes(b"wav")
    output = tmp_path / "result" / "predictions.jsonl"
    report = tmp_path / "result" / "report.json"
    asr = FakeASR({"a.wav": "Xin chào"})

    result = evaluate_dataset(tmp_path, "train", tmp_path / "model", output, report, asr=asr)

    assert asr.paths == [audio]
    row = json.loads(output.read_text(encoding="utf-8"))
    assert row["reference"] == "Xin chào"
    assert row["prediction"] == "Xin chào"
    assert row["exact_match"] is True
    saved_report = json.loads(report.read_text(encoding="utf-8"))
    assert saved_report["successful_samples"] == 1
    assert saved_report["average_relaxed_wer"] == 0.0
    assert saved_report["relaxed_exact_match_rate"] == 1.0
    assert saved_report["average_fuzzy_token_f1"] == 1.0
    assert saved_report["fuzzy_match_rate"] == 1.0
    assert result["exact_match_rate"] == 1.0


def test_evaluate_dataset_honors_limit_and_aggregates_report(tmp_path):
    samples = [
        {"id": "one", "audio": "audio/one.wav", "audio_text": "một"},
        {"id": "two", "audio": "audio/two.wav", "audio_text": "hai"},
    ]
    write_dataset(tmp_path, samples)
    for name in ("one.wav", "two.wav"):
        path = tmp_path / "train" / "audio" / name
        path.parent.mkdir(exist_ok=True)
        path.write_bytes(b"wav")
    asr = FakeASR({"one.wav": "sai", "two.wav": "đúng"})

    result = evaluate_dataset(
        tmp_path,
        "train",
        tmp_path / "model",
        tmp_path / "predictions.jsonl",
        tmp_path / "report.json",
        limit=1,
        asr=asr,
    )

    assert [path.name for path in asr.paths] == ["one.wav"]
    assert result["total_samples"] == 1
    assert result["successful_samples"] == 1


def test_evaluate_dataset_records_errors_and_continues(tmp_path):
    samples = [
        {"id": "bad", "audio": "audio/bad.wav", "audio_text": "một"},
        {"id": "good", "audio": "audio/good.wav", "audio_text": "hai"},
    ]
    write_dataset(tmp_path, samples)
    for name in ("bad.wav", "good.wav"):
        path = tmp_path / "train" / "audio" / name
        path.parent.mkdir(exist_ok=True)
        path.write_bytes(b"wav")
    asr = FakeASR({"good.wav": "hai"}, failures={"bad.wav"})

    with pytest.raises(RuntimeError):
        evaluate_dataset(
            tmp_path,
            "train",
            tmp_path / "model",
            tmp_path / "predictions.jsonl",
            tmp_path / "report.json",
            asr=asr,
        )

    rows = [json.loads(line) for line in (tmp_path / "predictions.jsonl").read_text(encoding="utf-8").splitlines()]
    assert rows[0]["error"] == "decode failed"
    assert rows[1]["prediction"] == "hai"


def test_evaluate_dataset_uses_batch_adapter_and_preserves_order(tmp_path):
    samples = [
        {"id": "one", "audio": "audio/one.wav", "audio_text": "một"},
        {"id": "two", "audio": "audio/two.wav", "audio_text": "hai"},
        {"id": "three", "audio": "audio/three.wav", "audio_text": "ba"},
    ]
    write_dataset(tmp_path, samples)
    for name in ("one.wav", "two.wav", "three.wav"):
        path = tmp_path / "train" / "audio" / name
        path.parent.mkdir(exist_ok=True)
        path.write_bytes(b"wav")
    asr = FakeBatchASR({"one.wav": "một", "two.wav": "hai", "three.wav": "ba"})

    evaluate_dataset(
        tmp_path,
        "train",
        tmp_path / "model",
        tmp_path / "predictions.jsonl",
        tmp_path / "report.json",
        batch_size=2,
        asr=asr,
    )

    assert [[path.name for path in batch] for batch in asr.batch_paths] == [
        ["one.wav", "two.wav"],
        ["three.wav"],
    ]
    rows = [json.loads(line) for line in (tmp_path / "predictions.jsonl").read_text(encoding="utf-8").splitlines()]
    assert [row["id"] for row in rows] == ["one", "two", "three"]


def test_evaluate_dataset_falls_back_to_single_transcribe_without_batch_api(tmp_path):
    samples = [
        {"id": "one", "audio": "audio/one.wav", "audio_text": "một"},
        {"id": "two", "audio": "audio/two.wav", "audio_text": "hai"},
    ]
    write_dataset(tmp_path, samples)
    for name in ("one.wav", "two.wav"):
        path = tmp_path / "train" / "audio" / name
        path.parent.mkdir(exist_ok=True)
        path.write_bytes(b"wav")
    asr = FakeASR({"one.wav": "một", "two.wav": "hai"})

    evaluate_dataset(
        tmp_path,
        "train",
        tmp_path / "model",
        tmp_path / "predictions.jsonl",
        tmp_path / "report.json",
        batch_size=2,
        asr=asr,
    )

    assert [path.name for path in asr.paths] == ["one.wav", "two.wav"]


def test_evaluate_dataset_preserves_order_when_batch_contains_invalid_sample(tmp_path):
    samples = [
        {"id": "good", "audio": "audio/good.wav", "audio_text": "hai"},
        {"id": "bad", "audio_text": "một"},
    ]
    write_dataset(tmp_path, samples)
    audio = tmp_path / "train" / "audio" / "good.wav"
    audio.parent.mkdir(exist_ok=True)
    audio.write_bytes(b"wav")
    asr = FakeASR({"good.wav": "hai"})

    with pytest.raises(RuntimeError):
        evaluate_dataset(
            tmp_path,
            "train",
            tmp_path / "model",
            tmp_path / "predictions.jsonl",
            tmp_path / "report.json",
            batch_size=2,
            asr=asr,
        )

    rows = [json.loads(line) for line in (tmp_path / "predictions.jsonl").read_text(encoding="utf-8").splitlines()]
    assert [row["id"] for row in rows] == ["good", "bad"]


def test_evaluate_dataset_rejects_missing_audio_before_adapter_call(tmp_path):
    write_dataset(
        tmp_path,
        [{"id": "missing", "audio": "audio/missing.wav", "audio_text": "xin chào"}],
    )

    class SilentASR:
        def transcribe(self, audio_path: Path) -> str:
            return "xin chào"

    with pytest.raises(RuntimeError):
        evaluate_dataset(
            tmp_path,
            "train",
            tmp_path / "model",
            tmp_path / "predictions.jsonl",
            tmp_path / "report.json",
            asr=SilentASR(),
        )

    row = json.loads((tmp_path / "predictions.jsonl").read_text(encoding="utf-8"))
    assert "audio file does not exist" in row["error"]
