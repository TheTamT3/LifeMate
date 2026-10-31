"""Send one mocked end-to-end LifeMate run to LangSmith.

The model and ASR are mocked; zaic_tools.ToolEnv is real so the trace includes
the actual tool calls and resulting state hash. This script is intentionally
opt-in and is not part of the offline competition runner.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

from dotenv import load_dotenv
from langsmith import Client


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_DATA_ROOT = ROOT / "train+public_test" / "train+public_test"


class MockASR:
    def transcribe(self, audio_path: Path) -> str:
        raise AssertionError("train sample already contains audio_text; ASR should not run")


class MockAgent:
    def __init__(self, calls: list[dict], client: Client, parent_run_id: str, parent_dotted_order: str) -> None:
        self.calls = calls
        self.client = client
        self.parent_run_id = parent_run_id
        self.parent_dotted_order = parent_dotted_order

    def run_sync(self, prompt: str, *, deps, message_history, instructions, usage_limits, model_settings):
        for index, call in enumerate(self.calls):
            run_id = str(uuid4())
            self.client.create_run(
                name=call["name"],
                run_type="tool",
                inputs=call["arguments"],
                project_name=os.environ["LANGSMITH_PROJECT"],
                id=run_id,
                run_id=run_id,
                parent_run_id=self.parent_run_id,
                trace_id=self.parent_run_id,
                dotted_order=f"{self.parent_dotted_order}.{_dotted_order(run_id)}",
                extra={"metadata": {"mock": True, "step": index}},
            )
            output = deps.env.call(call["name"], call["arguments"])
            self.client.update_run(run_id, outputs=output, end_time=_now())
        return None


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _dotted_order(run_id: str) -> str:
    return f"{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%fZ')}{run_id}"


def main() -> None:
    sys.stdout.reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser()
    parser.add_argument("--data-root", type=Path, default=DEFAULT_DATA_ROOT)
    parser.add_argument("--sample-id", default="train_0001")
    parser.add_argument("--project", default=None)
    args = parser.parse_args()

    load_dotenv(ROOT / ".env", override=False)
    if args.project:
        os.environ["LANGSMITH_PROJECT"] = args.project
    required = ["LANGSMITH_API_KEY", "LANGSMITH_PROJECT"]
    missing = [name for name in required if not os.getenv(name)]
    if missing:
        raise SystemExit(f"Missing environment variables: {', '.join(missing)}")

    sys.path.insert(0, str(ROOT / "src"))
    import lifemate.runner as runner
    from lifemate.data import load_catalog, read_jsonl

    split = "train"
    samples = read_jsonl(args.data_root / split / "train.jsonl")
    sample = next((item for item in samples if item["id"] == args.sample_id), None)
    if sample is None:
        raise SystemExit(f"Sample not found: {args.sample_id}")
    catalog = load_catalog(args.data_root / split / "train_tools_catalog.json")
    expected_calls = sample.get("label", {}).get("tool_calls", [])

    client = Client(
        api_url=os.getenv("LANGSMITH_ENDPOINT", "https://api.smith.langchain.com"),
        api_key=os.environ["LANGSMITH_API_KEY"],
    )
    project = os.environ["LANGSMITH_PROJECT"]
    root_run_id = str(uuid4())
    root_dotted_order = _dotted_order(root_run_id)
    client.create_run(
        name="lifemate.smoke.end_to_end",
        run_type="chain",
        inputs={"sample_id": sample["id"], "request": sample.get("audio_text", "")},
        project_name=project,
        id=root_run_id,
        run_id=root_run_id,
        trace_id=root_run_id,
        dotted_order=root_dotted_order,
        extra={"metadata": {"mock_model": True, "mock_asr": True, "split": split}},
    )

    asr_run_id = str(uuid4())
    client.create_run(
        name="asr.transcribe.mock",
        run_type="llm",
        inputs={"audio": sample.get("audio")},
        outputs={"text": sample.get("audio_text", "")},
        project_name=project,
        id=asr_run_id,
        run_id=asr_run_id,
        parent_run_id=root_run_id,
        trace_id=root_run_id,
        dotted_order=f"{root_dotted_order}.{_dotted_order(asr_run_id)}",
    )

    original_build_agent = runner.build_agent
    runner.build_agent = lambda model, deps: MockAgent(expected_calls, client, root_run_id, root_dotted_order)
    try:
        result = runner.run_sample(
            sample,
            split,
            args.data_root,
            catalog,
            llm_model=object(),
            asr=MockASR(),
        )
    finally:
        runner.build_agent = original_build_agent

    client.update_run(
        root_run_id,
        outputs=result,
        end_time=_now(),
        extra={"metadata": {"tool_call_count": len(result["tool_calls"])}},
    )
    client.flush()
    print(json.dumps({"project": project, "run_id": root_run_id, **result}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
