"""Run the public split through real ASR + LLM concurrently and trace every row."""

from __future__ import annotations

import argparse
import json
import gc
import multiprocessing
import os
import sys
import time
from concurrent.futures import ProcessPoolExecutor
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

from dotenv import load_dotenv
from langsmith import Client

from smoke_e2e_langsmith import (
    _run_one_sample,
    _now,
    create_trace_client,
    prepare_experiment,
    require_langsmith_environment,
)

def _worker(task):
    sample, config, project, example_id, transcript, asr_seconds, attempt = task
    import argparse
    import lifemate.runner as runner
    from lifemate.data import load_catalog, split_paths
    from lifemate.pydantic_agent import agent_event_loop
    from lifemate.vllm import VLLMConfig, create_vllm_model

    args = argparse.Namespace(**config)
    args.example_ids = {str(sample['id']): example_id}
    args.evaluator = None
    args.references = {}
    sample_id = str(sample['id'])
    args.precomputed_asr = {sample_id: transcript}
    args.precomputed_asr_metadata = {sample_id: {
        'provider': 'CUDAExecutionProvider', 'inference_seconds': asr_seconds,
        'execution': 'precomputed_gpu_stage',
    }}

    client = create_trace_client(os.environ['LANGSMITH_API_KEY'])
    llm = create_vllm_model(VLLMConfig(args.llm_base_url, args.llm_model_name, args.max_steps))
    _, catalog_path = split_paths(args.root, args.split)
    catalog = load_catalog(catalog_path)
    try:
        with agent_event_loop() as loop:
            try:
                row = _run_one_sample(sample, args=args, catalog=catalog, runner=runner,
                                      llm=llm, asr=None, client=client, project=project)
            finally:
                loop.run(llm.client.close())
        row['attempt'] = attempt
        return row
    finally:
        client.flush()


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument('--root', type=Path, default=Path('/root'),
                        help='directory containing public_test/ (default: /root)')
    parser.add_argument('--asr-model', type=Path, required=True)
    parser.add_argument('--asr-provider', choices=['cuda'], default='cuda')
    parser.add_argument('--model', type=Path, required=True, help='compatibility argument for local model path')
    parser.add_argument('--llm-base-url', default='http://127.0.0.1:8000/v1')
    parser.add_argument('--llm-model-name', default='qwen3.5-4b')
    parser.add_argument('--max-steps', type=int, default=10)
    parser.add_argument('--seed', type=int, default=0)
    parser.add_argument('--concurrency', type=int, default=32)
    parser.add_argument('--limit', type=int, default=None,
                        help='optional smoke limit; omit to run the full 634-row split')
    parser.add_argument('--dataset-name', default='lifemate-public-test')
    parser.add_argument('--experiment-name', default=None)
    parser.add_argument('--output', type=Path, default=Path('result/public-test-batch32.json'))
    parser.add_argument('--submission-output', type=Path,
                        default=Path('result/public-test-submission.jsonl'))
    args = parser.parse_args(argv)
    if args.concurrency < 1:
        parser.error('--concurrency must be positive')

    load_dotenv(Path(__file__).resolve().parents[1] / '.env', override=False)
    api_key, default_project = require_langsmith_environment()
    sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'src'))
    from lifemate.config import seed_everything
    from lifemate.data import load_catalog, read_jsonl, split_paths

    args.split = 'public_test'
    args.asr_backend = 'gipformer'
    args.use_reference_text = False
    data_path, catalog_path = split_paths(args.root, args.split)
    samples = read_jsonl(data_path)
    if len(samples) != 634:
        raise SystemExit(f'Expected 634 public samples, found {len(samples)} at {data_path}')
    if args.limit is not None:
        if args.limit < 1:
            raise SystemExit('--limit must be positive')
        samples = samples[:args.limit]
    for sample in samples:
        audio = Path(sample['audio'])
        audio_path = audio if audio.is_absolute() else args.root / args.split / audio
        if not audio_path.is_file():
            raise SystemExit(f"Missing audio for {sample['id']}: {audio_path}")
    catalog = load_catalog(catalog_path)
    if not catalog:
        raise SystemExit(f'Empty tool catalog: {catalog_path}')
    seed_everything(args.seed)

    client = create_trace_client(api_key)
    dataset_name = args.dataset_name
    experiment_name = args.experiment_name or f'{default_project}-public-test-batch{args.concurrency}-{uuid4().hex[:8]}'
    metadata = {
        'split': 'public_test', 'input_mode': 'gipformer', 'asr_provider': args.asr_provider,
        'llm_model': args.llm_model_name, 'concurrency': args.concurrency,
        'sample_count': len(samples), 'seed': args.seed,
        'asr_execution': 'single_gpu_stage',
    }
    experiment, example_ids = prepare_experiment(
        client, samples, dataset_name, experiment_name, metadata,
    )
    project = experiment.name
    print(f'[LangSmith] dataset={dataset_name} experiment={project} '
          f'experiment_id={experiment.id} samples={len(samples)} concurrency={args.concurrency}',
          file=sys.stderr, flush=True)

    # Gipformer weights are small, but each CUDA execution session owns a separate
    # workspace. Run one shared GPU recognizer to avoid replicating that workspace
    # across all 32 LLM workers and exhausting VRAM reserved by vLLM.
    from lifemate.asr import GipformerASR
    asr = GipformerASR(args.asr_model, provider='cuda')
    transcripts = {}
    transcript_seconds = {}
    cache_path = args.output.with_suffix('.asr-cache.jsonl')
    cache_path.parent.mkdir(parents=True, exist_ok=True)
    with cache_path.open('w', encoding='utf-8') as cache:
        for index, sample in enumerate(samples, 1):
            audio = Path(sample['audio'])
            audio_path = audio if audio.is_absolute() else args.root / args.split / audio
            error = None
            for _ in range(3):
                started_asr = time.perf_counter()
                try:
                    text = asr.transcribe(audio_path)
                    error = None
                    break
                except Exception as exc:
                    error = f'{type(exc).__name__}: {exc}'
            if error:
                raise RuntimeError(f"GPU ASR failed for {sample['id']} after retries: {error}")
            elapsed_asr = time.perf_counter() - started_asr
            transcripts[str(sample['id'])] = text
            transcript_seconds[str(sample['id'])] = elapsed_asr
            cache.write(json.dumps({'id': sample['id'], 'transcript': text,
                                    'asr_provider': 'CUDAExecutionProvider',
                                    'inference_seconds': elapsed_asr}, ensure_ascii=False) + '\n')
            cache.flush()
            if index % 50 == 0 or index == len(samples):
                print(f'[ASR GPU] {index}/{len(samples)}', file=sys.stderr, flush=True)
    asr._recognizer = None
    del asr
    gc.collect()

    config = {key: value for key, value in vars(args).items()
              if key not in {'output', 'submission_output', 'experiment_name', 'dataset_name',
                             'concurrency', 'limit'}}
    tasks = [(sample, config, project, example_ids[str(sample['id'])],
              transcripts[str(sample['id'])], transcript_seconds[str(sample['id'])], 0)
             for sample in samples]
    result_by_id = {}
    started = time.perf_counter()
    try:
        with ProcessPoolExecutor(max_workers=args.concurrency,
                                 mp_context=multiprocessing.get_context('spawn')) as pool:
            pending = tasks
            for attempt in range(3):
                rows = list(pool.map(_worker, pending))
                for row in rows:
                    result_by_id[str(row['id'])] = row
                pending = [
                    (sample, config, project, example_ids[str(sample['id'])],
                     transcripts[str(sample['id'])], transcript_seconds[str(sample['id'])], attempt + 1)
                    for sample in samples
                    if result_by_id[str(sample['id'])].get('error')
                ]
                if not pending:
                    break
                print(f'[Retry] attempt={attempt + 1} samples={len(pending)}',
                      file=sys.stderr, flush=True)
        elapsed = time.perf_counter() - started
        rows = [result_by_id[str(sample['id'])] for sample in samples]
        print(f'[Benchmark] concurrency={args.concurrency} samples={len(rows)} '
              f'elapsed_seconds={elapsed:.3f}', file=sys.stderr, flush=True)
    finally:
        client.flush()
        client.update_project(experiment.id, end_time=datetime.now(timezone.utc))

    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps({'project': project, 'count': len(rows), 'rows': rows},
                                      ensure_ascii=False, indent=2), encoding='utf-8')
    errors = [row for row in rows if row.get('error') or row.get('evaluation_error')]
    if errors:
        raise SystemExit(f'{len(errors)} samples still failed after retries; no submission file written. '
                         f'See {args.output}')
    args.submission_output.parent.mkdir(parents=True, exist_ok=True)
    with args.submission_output.open('w', encoding='utf-8') as handle:
        for row in rows:
            submission = {key: row[key] for key in ('id', 'tool_calls', 'state_hash')}
            handle.write(json.dumps(submission, ensure_ascii=False) + '\n')
    print(f'[Submission] rows={len(rows)} path={args.submission_output}', file=sys.stderr, flush=True)


if __name__ == '__main__':
    main()
