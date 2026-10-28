from pathlib import Path

from lifemate.asr_eval import cli


def test_cli_forwards_local_evaluation_arguments(monkeypatch, tmp_path):
    captured: dict[str, object] = {}

    def fake_evaluate_dataset(**kwargs):
        captured.update(kwargs)
        return {
            "successful_samples": 1,
            "total_samples": 1,
            "average_wer": 0.0,
            "average_cer": 0.0,
        }

    monkeypatch.setattr(cli, "evaluate_dataset", fake_evaluate_dataset)
    result = cli.main(
        [
            "--root",
            str(tmp_path),
            "--split",
            "train",
            "--asr-model",
            str(tmp_path / "model"),
            "--output",
            str(tmp_path / "predictions.jsonl"),
            "--report",
            str(tmp_path / "report.json"),
            "--limit",
            "2",
            "--device",
            "cpu",
            "--batch-size",
            "3",
            "--seed",
            "7",
        ]
    )

    assert result == 0
    assert captured == {
        "root": Path(tmp_path),
        "split": "train",
        "asr_model": Path(tmp_path / "model"),
        "output": Path(tmp_path / "predictions.jsonl"),
        "report": Path(tmp_path / "report.json"),
        "limit": 2,
        "device": "cpu",
        "batch_size": 3,
        "seed": 7,
    }


def test_cli_returns_nonzero_when_evaluation_has_failures(monkeypatch, tmp_path):
    def failing_evaluate_dataset(**kwargs):
        raise RuntimeError("one failed sample")

    monkeypatch.setattr(cli, "evaluate_dataset", failing_evaluate_dataset)
    result = cli.main(
        [
            "--root",
            str(tmp_path),
            "--asr-model",
            str(tmp_path / "model"),
            "--output",
            str(tmp_path / "predictions.jsonl"),
            "--report",
            str(tmp_path / "report.json"),
        ]
    )

    assert result == 1
