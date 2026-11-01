"""Build a fixed, tool-covered 300-sample validation dataset without inference.
Requires scipy (available in .venv). Source train data is never changed.
"""
from __future__ import annotations
import csv
import hashlib
import json
import random
import shutil
import sys
from collections import Counter
from pathlib import Path

import numpy as np
from scipy.optimize import Bounds, LinearConstraint, milp
from scipy.sparse import csr_matrix, eye, hstack, vstack

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / 'data/train'
DEST = ROOT / 'data/validation_300'
SEED = 20261029
SIZE = 300

def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()

def main():
    if DEST.exists():
        raise SystemExit(f'{DEST} already exists; keep the fixed dataset intact.')
    source_hash = sha(SOURCE/'train.jsonl')
    samples = [json.loads(line) for line in (SOURCE/'train.jsonl').read_text().splitlines() if line.strip()]
    eda_path = ROOT/'result/train-eda'
    eda = json.loads((eda_path/'summary.json').read_text())
    if eda['source_sha256'] != source_hash:
        raise SystemExit('EDA source differs; rerun scripts/eda_train.py first.')
    features = {r['id']: r for r in csv.DictReader((eda_path/'sample_features.csv').open())}
    assert len(samples) == len(features) == len({s['id'] for s in samples})
    names = [set(c['name'] for c in s['label']['tool_calls']) for s in samples]
    observed = sorted(set().union(*names))
    n = len(samples)
    dimensions = {}
    for s, ns in zip(samples, names):
        f = features[s['id']]
        def binned(value, cuts):
            return str(sum(float(value) > cut for cut in cuts))
        dimensions[s['id']] = {
            'n_calls': f['n_calls'], 'n_apps': f['n_apps'], 'mode': f['mode'],
            'history': str(int(f['history_turns']) > 0),
            'history_length': binned(f['history_turns'], [0,4,8,12,20]),
            'state_changed': f['state_changed'], 'city': f['city'],
            'audio_length': binned(f['audio_seconds'], [eda['numeric']['audio_seconds'][k] for k in ['p25','median','p75','p90']]),
            'history_audio_length': binned(f['history_audio_seconds'], [0,6,12,24]),
            'available_tools': binned(f['available_tools'], [25,31,39,46]),
            'ask_missing': str('sys.ask_missing_info' in ns),
        }
    labels = [set((k,v) for k,v in dimensions[s['id']].items()) |
              {('tool', t) for t in ns} | {('app', t.split('.')[0]) for t in ns}
              for s,ns in zip(samples,names)]
    keys = sorted(set().union(*labels))
    a = csr_matrix(np.array([[int(k in ls) for ls in labels] for k in keys], dtype=float))
    targets = np.asarray(a.sum(axis=1)).ravel()*SIZE/n
    m = len(keys)
    # Minimise weighted absolute deviations from full-data marginal proportions.
    # Tool frequencies remain soft; every observed tool has a hard minimum of one.
    importance = {'tool': .35, 'app': .7}
    weights = np.array([importance.get(k[0], 2.) / max(2., t)**.5 for k,t in zip(keys,targets)])
    rng = random.Random(SEED)
    objective = np.r_[np.array([rng.random()*1e-6 for _ in samples]), weights, weights]
    equality = hstack([a, -eye(m), eye(m)], format='csr')
    hard_rows, low, high = [np.ones(n)], [SIZE], [SIZE]
    for tool in observed:
        hard_rows.append(np.array([int(tool in ns) for ns in names])); low.append(1); high.append(np.inf)
    call_counts = Counter(len(s['label']['tool_calls']) for s in samples)
    exact = {k: int(v*SIZE/n) for k,v in call_counts.items()}
    for k in sorted(exact, key=lambda k: (-(call_counts[k]*SIZE/n-exact[k]), k))[:SIZE-sum(exact.values())]:
        exact[k] += 1
    for k in sorted(exact):
        hard_rows.append(np.array([int(len(s['label']['tool_calls']) == k) for s in samples]))
        low.append(exact[k]); high.append(exact[k])
    hard = hstack([csr_matrix(np.array(hard_rows)), csr_matrix((len(hard_rows),2*m))], format='csr')
    constraint = LinearConstraint(vstack([equality,hard], format='csr'), np.r_[targets,low], np.r_[targets,high])
    result = milp(objective, integrality=np.r_[np.ones(n),np.zeros(2*m)],
                  bounds=Bounds(np.zeros(n+2*m), np.r_[np.ones(n),np.full(2*m,np.inf)]),
                  constraints=constraint, options={'time_limit': 40., 'mip_rel_gap': .01})
    if result.x is None:
        raise RuntimeError(f'No feasible subset: {result.message}')
    indices = [i for i in range(n) if result.x[i] > .5]
    selected = [samples[i] for i in indices]
    chosen_tools = set().union(*(names[i] for i in indices))
    assert len(selected) == SIZE and chosen_tools == set(observed)
    assert Counter(len(s['label']['tool_calls']) for s in selected) == exact
    target = DEST/'train'
    target.mkdir(parents=True)
    (target/'train.jsonl').write_text(''.join(json.dumps(s,ensure_ascii=False)+'\n' for s in selected))
    shutil.copy2(SOURCE/'train_tools_catalog.json', target/'train_tools_catalog.json')
    shutil.copytree(SOURCE/'zaic_tools', target/'zaic_tools', ignore=shutil.ignore_patterns('__pycache__','*.pyc'))
    for s in selected:
        shutil.copytree(SOURCE/'audio'/s['id'], target/'audio'/s['id'])
        shutil.copytree(SOURCE/'train_environment'/s['id'], target/'train_environment'/s['id'])
    comparisons = []
    chosen_labels = [labels[i] for i in indices]
    for key,t in zip(keys,targets):
        full = sum(key in ls for ls in labels)
        actual = sum(key in ls for ls in chosen_labels)
        comparisons.append(dict(dimension=key[0],group=key[1],full_count=full,subset_count=actual,
                                target_count=t,full_percent=100*full/n,subset_percent=100*actual/SIZE,
                                delta_percentage_points=100*(actual/SIZE-full/n)))
    with (DEST/'distribution.csv').open('w') as f:
        w=csv.DictWriter(f,fieldnames=list(comparisons[0])); w.writeheader(); w.writerows(comparisons)
    # Verify copied data byte-for-byte, including every history audio reference.
    file_hashes = {}
    for p in sorted(target.rglob('*')):
        if not p.is_file(): continue
        relative = p.relative_to(target)
        if str(relative) == 'train.jsonl': continue
        assert sha(p) == sha(SOURCE/relative), relative
        file_hashes[str(p.relative_to(DEST))] = sha(p)
    assert [json.loads(x) for x in (target/'train.jsonl').read_text().splitlines()] == selected
    for s in selected:
        for item in [s,*s.get('history',[])]:
            if item.get('audio'): assert (target/item['audio']).is_file(), item['audio']
    # Replay isolated copied ToolEnv: no ASR, LLM or network calls.
    sys.path.insert(0,str(target))
    from zaic_tools import ToolEnv
    for s in selected:
        env = ToolEnv('train',s['id'],root=str(DEST))
        for c in s['label']['tool_calls']:
            response=env.call(c['name'],c['arguments'])
            assert response.get('ok') is not False, (s['id'],response)
    rare = [t for t in observed if sum(t in ns for ns in names)<=5]
    manifest = dict(version=1,seed=SEED,size=SIZE,source_size=n,source_sha256=source_hash,
                    subset_sha256=sha(target/'train.jsonl'),sample_ids=[s['id'] for s in selected],
                    method='MILP: all observed tools covered; exact largest-remainder call-count quotas; weighted marginal absolute deviation; seeded tie-break',
                    solver_status=int(result.status),solver_message=result.message,
                    solver_gap=float(result.mip_gap),tool_coverage=len(chosen_tools),observed_source_tools=len(observed),
                    rare_tools_covered=len(set(rare)&chosen_tools),rare_tools_total=len(rare),
                    unique_sequences=len({features[s['id']]['sequence'] for s in selected}),
                    verified_files=len(file_hashes),file_sha256=file_hashes)
    (DEST/'manifest.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2)+'\n')
    lines=['# Fixed validation: 300 train samples','',
           '300 mẫu được chọn từ 1.545 mẫu train. Dữ liệu, label, ID, audio và state giữ nguyên. Seed: 20261029.', '',
           f'Coverage: **{len(chosen_tools)}/146 tools**, **46/46 apps**, **{len(rare)}/30 tools hiếm** (xuất hiện ở ≤5 mẫu gốc).',
           f'Chuỗi tool khác nhau: {manifest["unique_sequences"]}/695. Không thể bao phủ toàn bộ chuỗi bằng 300 mẫu.', '',
           'Phương pháp: tối ưu sai lệch các phân phối cùng lúc; bắt buộc đủ tool; số mẫu từng nhóm số calls theo phân bổ tỷ lệ largest-remainder. Có seed để phá hòa. Không dùng kết quả baseline để chọn mẫu.',
           f'Solver status: {result.status}; gap: {result.mip_gap:.3%}. Status 1 nghĩa là dừng tại giới hạn thời gian với nghiệm khả thi, không khẳng định tối ưu toàn cục.', '',
           '| Chiều | Nhóm | Gốc | Subset | Lệch (điểm %) |', '|---|---|---:|---:|---:|']
    for c in comparisons:
        if c['dimension'] not in ('tool','app'):
            lines.append(f'| {c["dimension"]} | {c["group"]} | {c["full_percent"]:.1f}% | {c["subset_count"]} ({c["subset_percent"]:.1f}%) | {c["delta_percentage_points"]:+.2f} |')
    lines += ['', '## Sử dụng', '',
              'Cấu trúc giữ split `train` để tương thích ToolEnv và experiment CLI hiện tại. Đường dẫn root mới là `data/validation_300`.', '',
              '```bash', 'PYTHONPATH=src .venv/bin/python -m lifemate.experiments \\', '  --root data/validation_300 \\', '  --dataset lifemate-train-validation-300-v1 \\', '  --experiment qwen3-4b-validation-300 \\', '  --limit 1', '```', '',
              'Lệnh trên chỉ chạy 1 mẫu khi người dùng chủ động chạy; đổi `--limit 300` để chạy cả subset. Chưa tạo dataset trên LangSmith ở bước này.', '',
              '`train/train.jsonl`: 300 mẫu cùng label; `train/audio/`: audio query + history; `train/train_environment/`: môi trường của 300 mẫu; `train/zaic_tools/` và catalog: bản sao nguyên gốc.', '',
              '`manifest.json`: danh sách ID, seed, SHA256 và checksum tài nguyên. `distribution.csv`: so sánh toàn bộ phân phối, bao gồm từng app/tool.', '',
              'Các nhóm hiếm được ưu tiên coverage nên có thể lệch tỷ lệ. Điểm subset là mốc validation nội bộ, không phải ước lượng không thiên lệch của điểm thi; cần xác nhận trên full train khi chốt giải pháp.', '',
              'Đã kiểm tra đủ 300 ID duy nhất, coverage, quota, toàn bộ tài nguyên copy, đường dẫn audio và replay reference calls của 300 mẫu. Không chạy ASR/LLM.', '',
              'Tạo lại trong thư mục chưa tồn tại: `.venv/bin/python scripts/build_validation_subset.py`. Giữ manifest hiện tại làm chuẩn; solver/version/time limit có thể ảnh hưởng lựa chọn khi tạo lại.']
    (DEST/'README.md').write_text('\n'.join(lines)+'\n')
    print(json.dumps({k:v for k,v in manifest.items() if k not in ('sample_ids','file_sha256')},ensure_ascii=False,indent=2))

if __name__ == '__main__': main()
