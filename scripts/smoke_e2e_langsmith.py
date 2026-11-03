"""Run real LifeMate samples and send one complete trace per sample to LangSmith."""

from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from uuid import uuid4, uuid5, NAMESPACE_URL

from dotenv import load_dotenv
from langsmith import Client
from langsmith.utils import LangSmithNotFoundError

ROOT = Path(__file__).resolve().parents[1]


def create_trace_client(api_key):
    # Debug experiments must surface ingestion errors and retain every sample.
    return Client(api_url=os.getenv('LANGSMITH_ENDPOINT', 'https://api.smith.langchain.com'),
                  api_key=api_key, auto_batch_tracing=False, tracing_sampling_rate=1.0)


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _dotted_order(run_id: str, start_time: datetime | None = None) -> str:
    return f"{(start_time or _now()).strftime('%Y%m%dT%H%M%S%fZ')}{run_id}"


def require_langsmith_environment() -> tuple[str, str]:
    missing = [name for name in ("LANGSMITH_API_KEY", "LANGSMITH_PROJECT") if not os.getenv(name)]
    if missing:
        raise SystemExit(f"Missing environment variables: {', '.join(missing)}")
    return os.environ["LANGSMITH_API_KEY"], os.environ["LANGSMITH_PROJECT"]


def select_samples(samples: list[dict[str, Any]], *, sample_id: str | None = None, limit: int | None = None, sample_ids_file: Path | None = None) -> list[dict[str, Any]]:
    if sum(value is not None for value in (sample_id, limit, sample_ids_file)) > 1:
        raise ValueError("use only one of sample_id, limit or sample_ids_file")
    if sample_ids_file is not None:
        requested = set(sample_ids_file.read_text(encoding='utf-8-sig').split())
        if not requested:
            raise SystemExit("Sample ID file is empty")
        missing = requested - {str(sample.get('id')) for sample in samples}
        if missing:
            raise SystemExit(f"Samples not found: {', '.join(sorted(missing))}")
        return [sample for sample in samples if str(sample.get('id')) in requested]
    if sample_id is not None:
        selected = [sample for sample in samples if sample.get("id") == sample_id]
        if not selected:
            raise SystemExit(f"Sample not found: {sample_id}")
        return selected
    if limit is None or limit < 1:
        raise ValueError("limit must be a positive integer")
    selected = samples[:limit]
    if not selected:
        raise SystemExit("No samples selected")
    return selected


def prepare_asr(samples, split, use_reference_text, model_path):
    if use_reference_text:
        if split != 'train':
            raise ValueError('--use-reference-text requires the train split')
        for sample in samples:
            if not isinstance(sample.get('audio_text'), str) or not sample['audio_text'].strip():
                raise ValueError(f"Sample {sample.get('id')} requires non-empty audio_text")
        return None
    if model_path is None:
        raise ValueError('--asr-model is required unless --use-reference-text is set')
    from lifemate.asr import GipformerASR
    return GipformerASR(model_path, device='cuda')


def prepare_experiment(client, samples, dataset_name, experiment_name, metadata, references=None):
    try:
        dataset = client.read_dataset(dataset_name=dataset_name)
    except LangSmithNotFoundError:
        dataset = client.create_dataset(dataset_name=dataset_name)
    example_ids = {}
    for sample in samples:
        # Content-addressed IDs reuse unchanged examples, without overwriting labels.
        identity = json.dumps(sample, sort_keys=True, ensure_ascii=False)
        example_id = uuid5(NAMESPACE_URL, f'{dataset.id}:reference-v2:{identity}')
        try:
            client.read_example(example_id)
        except LangSmithNotFoundError:
            client.create_example(
                dataset_id=dataset.id, example_id=example_id,
                inputs={k: v for k, v in sample.items() if k not in {'label', 'tool_calls', 'state_hash'}},
                outputs=(references or {}).get(str(sample['id']), {}),
                metadata={'sample_id': sample['id']},
            )
        example_ids[str(sample['id'])] = example_id
    project = client.create_project(
        project_name=experiment_name, reference_dataset_id=dataset.id, metadata=metadata,
    )
    return project, example_ids


def _create_root_run(client: Client, project: str, sample: dict[str, Any], split: str, asr_backend: str, llm_model_name: str, reference_example_id=None) -> tuple[str, str]:
    root_run_id = str(uuid4())
    start_time = _now()
    root_dotted_order = _dotted_order(root_run_id, start_time)
    client.create_run(
        name="lifemate.e2e.sample",
        run_type="chain",
        inputs={"sample_id": sample["id"], "audio": sample.get("audio")},
        project_name=project,
        reference_example_id=reference_example_id,
        id=root_run_id,
        run_id=root_run_id,
        trace_id=root_run_id,
        dotted_order=root_dotted_order,
        start_time=start_time,
        extra={"metadata": {"split": split, "asr_backend": asr_backend, "llm_model": llm_model_name}},
    )
    return root_run_id, root_dotted_order


def _run_one_sample(sample: dict[str, Any], *, args: argparse.Namespace, catalog: dict[str, dict[str, Any]], runner: Any, llm: Any, asr: Any, client: Client, project: str) -> dict[str, Any]:
    from lifemate.langsmith_e2e import LangSmithE2ETracer, TracingToolEnv, tracing_model, _safe_output

    input_mode = 'reference_text' if args.use_reference_text else args.asr_backend
    root_run_id, root_dotted_order = _create_root_run(client, project, sample, args.split, input_mode, args.llm_model_name, args.example_ids[str(sample['id'])])
    print(f"[LangSmith] sample={sample['id']} project={project} run_id={root_run_id}", file=sys.stderr, flush=True)
    tracer = LangSmithE2ETracer(client, project, root_run_id, root_dotted_order)
    original_tool_env = runner._tool_env
    original_transcript = runner.transcript
    original_run_agent = runner.run_agent

    def traced_tool_env(split: str, sample_id: str, root: Path):
        return TracingToolEnv(original_tool_env(split, sample_id, root), tracer)

    def traced_transcript(sample_data, asr_model):
        name = 'input.reference_text' if args.use_reference_text else 'asr.gipformer.transcribe'
        return tracer.trace(name, "chain", {"audio": sample_data.get("audio"), "backend": input_mode}, lambda: original_transcript(sample_data, asr_model))

    def traced_run_agent(agent, deps, prompt, **kwargs):
        def invoke():
            result = original_run_agent(agent, deps, prompt, **kwargs)
            if deps.argument_normalizations:
                tracer.trace(
                    "agent.argument_normalizations", "chain",
                    {"normalizations": deps.argument_normalizations},
                    lambda: {"count": len(deps.argument_normalizations)},
                )
            if getattr(deps, 'error', None):
                raise RuntimeError(deps.error)
            return result
        return tracer.trace(
            "agent.pydantic_ai",
            "chain",
            {"prompt": prompt, "message_history": _safe_output(kwargs.get("message_history") or []),
             'instructions': kwargs.get('instructions')},
            invoke,
            metadata={"model": args.llm_model_name},
        )

    runner._tool_env = traced_tool_env
    runner.transcript = traced_transcript
    runner.run_agent = traced_run_agent
    sample_for_run = dict(sample)
    sample_for_run.pop('label', None)
    if not args.use_reference_text:
        sample_for_run.pop("audio_text", None)
    try:
        traced_llm = tracing_model(llm, tracer) if llm is not None else None
        result = runner.run_sample(sample_for_run, split=args.split, root=args.root, catalog=catalog, llm_model=traced_llm, asr=asr, max_steps=args.max_steps, seed=args.seed)
    except Exception as exc:
        error = {"id": str(sample["id"]), "run_id": root_run_id, "error": f"{type(exc).__name__}: {exc}"}
        client.update_run(root_run_id, trace_id=root_run_id, dotted_order=root_dotted_order,
                          error=error["error"], end_time=_now())
        return error
    finally:
        runner._tool_env = original_tool_env
        runner.transcript = original_transcript
        runner.run_agent = original_run_agent

    client.update_run(root_run_id, trace_id=root_run_id, dotted_order=root_dotted_order,
                      outputs=result, end_time=_now(), extra={"metadata": {"tool_call_count": len(result["tool_calls"])}})
    if getattr(args, 'evaluator', None) is not None:
        try:
            # Ensure the run is ingested before attaching feedback to it.
            client.flush()
            args.evaluator.publish(client, root_run_id, sample, result,
                                   args.references[str(sample['id'])], catalog)
        except Exception as exc:
            error = f'{type(exc).__name__}: {exc}'
            client.update_run(root_run_id, trace_id=root_run_id, dotted_order=root_dotted_order,
                              error=f'Evaluation upload failed: {error}')
            return {'project': project, 'run_id': root_run_id, **result, 'evaluation_error': error}
    return {"project": project, "run_id": root_run_id, **result}


def main(argv: list[str] | None = None) -> None:
    sys.stdout.reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--split", choices=["train", "public_test", "private_test"], default="train")
    selector = parser.add_mutually_exclusive_group(required=True)
    selector.add_argument("--sample-id")
    selector.add_argument("--sample-ids-file", type=Path, help="file containing sample IDs separated by whitespace")
    selector.add_argument("--limit", type=int, help="number of sequential samples to trace")
    parser.add_argument("--model", type=Path, required=True)
    parser.add_argument("--asr-model", type=Path)
    parser.add_argument('--dataset-name', help='LangSmith dataset name; defaults to root name and split')
    parser.add_argument('--experiment-name', help='Unique experiment name; defaults to project plus UUID')
    parser.add_argument("--asr-backend", choices=["gipformer"], default="gipformer")
    parser.add_argument("--llm-base-url", default="http://127.0.0.1:8000/v1")
    parser.add_argument("--llm-model-name", default="qwen3-4b")
    parser.add_argument("--max-steps", type=int, default=10)
    parser.add_argument("--seed", type=int, default=0)
    parser.add_argument("--project", default=None)
    parser.add_argument("--use-reference-text", action="store_true", help="use train audio_text instead of running ASR")
    args = parser.parse_args(argv)

    load_dotenv(ROOT / ".env", override=False)
    if args.project:
        os.environ["LANGSMITH_PROJECT"] = args.project
    api_key, project = require_langsmith_environment()

    sys.path.insert(0, str(ROOT / "src"))
    import lifemate.runner as runner
    from lifemate.config import seed_everything
    from lifemate.data import load_catalog, read_jsonl, split_paths
    from lifemate.vllm import VLLMConfig, create_vllm_model

    data_path, catalog_path = split_paths(args.root, args.split)
    samples = select_samples(read_jsonl(data_path), sample_id=args.sample_id, limit=args.limit, sample_ids_file=args.sample_ids_file)
    from lifemate.agent_evaluation import TrainEvaluator
    args.evaluator = TrainEvaluator(args.root) if args.split == 'train' else None
    args.references = ({str(sample['id']): args.evaluator.reference(sample) for sample in samples}
                       if args.evaluator else {})
    asr = prepare_asr(samples, args.split, args.use_reference_text, args.asr_model)
    catalog = load_catalog(catalog_path)
    seed_everything(args.seed)
    client = create_trace_client(api_key)

    llm = create_vllm_model(VLLMConfig(args.llm_base_url, args.llm_model_name, args.max_steps))
    dataset_name = args.dataset_name or f'lifemate-{args.root.resolve().name}-{args.split}'
    experiment_name = args.experiment_name or f'{project}-{uuid4().hex[:12]}'
    from lifemate.pydantic_agent import qwen_thinking_settings
    experiment, args.example_ids = prepare_experiment(
        client, samples, dataset_name, experiment_name,
        {'input_mode': 'reference_text' if args.use_reference_text else 'gipformer',
         'llm_model': args.llm_model_name, 'seed': args.seed, 'max_steps': args.max_steps,
         'model_settings': qwen_thinking_settings(args.seed), 'reasoning_language': 'vi',
         'thinking_in_history': False, 'prompt_version': 'vi-qwen-thinking-v1'},
        references=args.references,
    )
    project = experiment.name
    print(f'[LangSmith] dataset={dataset_name} experiment={project} experiment_id={experiment.id}',
          file=sys.stderr, flush=True)
    from lifemate.pydantic_agent import agent_event_loop
    try:
        with agent_event_loop() as batch_loop:
            try:
                rows = [_run_one_sample(sample, args=args, catalog=catalog, runner=runner, llm=llm, asr=asr, client=client, project=project) for sample in samples]
            finally:
                # Close the provider's HTTP pool while its owning loop is alive.
                batch_loop.run(llm.client.close())
    finally:
        client.flush()
        client.update_project(experiment.id, end_time=_now())

    print(json.dumps({"project": project, "count": len(rows), "rows": rows}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
