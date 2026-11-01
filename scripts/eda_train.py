"""Offline descriptive EDA; no inference, API calls, or subset selection.
Run: .venv/bin/python scripts/eda_train.py
"""
import csv
import hashlib
import json
import math
import sys
import wave
from collections import Counter, defaultdict
from pathlib import Path
from statistics import mean, median

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / 'data/train'
OUT = ROOT / 'result/train-eda'
OUT.mkdir(parents=True, exist_ok=True)
sys.path.insert(0, str(DATA))
from zaic_tools import ToolEnv

samples = [json.loads(s) for s in (DATA/'train.jsonl').read_text().splitlines() if s.strip()]
catalog = json.loads((DATA/'train_tools_catalog.json').read_text())
tools = {t['name']: t for a in catalog['apps'] for t in a['tools']}
counts = defaultdict(Counter)
rows, errors = [], []
texts, sequences, audio_hashes = defaultdict(list), defaultdict(list), defaultdict(list)
audio_issues = []

def duration(audio):
    path = DATA/audio
    try:
        with wave.open(str(path), 'rb') as f:
            seconds = f.getnframes()/f.getframerate()
            counts['audio_format'][(f.getframerate(), f.getnchannels(), f.getsampwidth())] += 1
        return seconds
    except Exception as e:
        audio_issues.append({'path': str(path), 'error': str(e)})
        return None

def bucket(n):
    return str(n) if n < 4 else '4-5' if n < 6 else '6+'

for s in samples:
    calls = s['label']['tool_calls']
    names = [c['name'] for c in calls]
    apps = sorted({n.split('.')[0] for n in names})
    kinds = {tools.get(n, {}).get('kind', 'unknown') for n in names}
    mode = 'no_call' if not calls else 'write' if 'write' in kinds else 'read_only' if kinds == {'read'} else 'meta_or_other'
    history = s.get('history', [])
    hist_users = [h for h in history if h.get('role') == 'user']
    current_seconds = duration(s['audio'])
    hist_durations = [duration(h['audio']) for h in hist_users if h.get('audio')]
    env = ToolEnv('train', s['id'], root=str(ROOT/'data'))
    initial_hash = env.get_state_hash()
    for i, c in enumerate(calls):
        result = env.call(c['name'], c['arguments'])
        if result.get('ok') is False:
            errors.append({'id': s['id'], 'call_index': i, 'error': result})
    state_changed = initial_hash != env.get_state_hash()
    text = ' '.join(s.get('audio_text', '').lower().split())
    signature = ' → '.join(names) or '(no call)'
    texts[text].append(s['id'])
    sequences[signature].append(s['id'])
    audio_path = DATA/s['audio']
    if audio_path.is_file():
        audio_hashes[hashlib.sha256(audio_path.read_bytes()).hexdigest()].append(s['id'])
    installed = s.get('context', {}).get('installed_apps', {})
    available = {n for a in installed.values() for n in a.get('tools', [])}
    r = dict(id=s['id'], n_calls=len(calls), n_apps=len(apps), apps='|'.join(apps), mode=mode,
             state_changed=state_changed, history_turns=len(history), history_users=len(hist_users),
             history_audio=len(hist_durations), audio_seconds=current_seconds,
             history_audio_seconds=sum(v for v in hist_durations if v is not None),
             query_words=len(text.split()), installed_apps=len(installed), available_tools=len(available),
             city=s.get('context', {}).get('user_profile', {}).get('city', '(missing)'),
             sequence=signature, ask_missing='sys.ask_missing_info' in names)
    rows.append(r)
    for key in ['mode', 'n_calls', 'n_apps', 'history_turns', 'history_users', 'installed_apps', 'city', 'state_changed']:
        counts[key][r[key]] += 1
    counts['joint_calls_history'][(bucket(len(calls)), bool(history))] += 1
    counts['app_samples'].update(apps)
    counts['tool_samples'].update(set(names))
    counts['tool_calls'].update(names)
    counts['kind_calls'].update(tools.get(n, {}).get('kind', 'unknown') for n in names)

with (OUT/'sample_features.csv').open('w') as f:
    writer = csv.DictWriter(f, fieldnames=list(rows[0])); writer.writeheader(); writer.writerows(rows)

def describe(values):
    a = sorted(v for v in values if v is not None)
    def quantile(q):
        pos = (len(a)-1)*q; lo = int(pos); hi = min(lo+1, len(a)-1)
        return a[lo]+(a[hi]-a[lo])*(pos-lo)
    return dict(n=len(a), min=min(a), p25=quantile(.25), median=median(a), p75=quantile(.75), p90=quantile(.9), p95=quantile(.95), max=max(a), mean=mean(a), total=sum(a)) if a else {}

numeric = {k: describe([r[k] for r in rows]) for k in ['audio_seconds', 'history_audio_seconds', 'query_words', 'available_tools', 'installed_apps', 'n_calls', 'history_turns']}
duplicates = {k: [ids for ids in mapping.values() if len(ids)>1] for k, mapping in [('normalized_query', texts), ('current_audio_sha256', audio_hashes)]}
summary = dict(n_samples=len(samples), source_sha256=hashlib.sha256((DATA/'train.jsonl').read_bytes()).hexdigest(),
               counts={k: {str(a): v for a,v in c.most_common()} for k,c in counts.items()}, numeric=numeric,
               catalog_apps=len(catalog['apps']), catalog_tools=len(tools), observed_tools=len(counts['tool_samples']),
               unused_tools=sorted(set(tools)-set(counts['tool_samples'])), unique_sequences=len(sequences),
               duplicates=duplicates, audio_issues=audio_issues, reference_schema_errors=errors)
(OUT/'summary.json').write_text(json.dumps(summary, ensure_ascii=False, indent=2))
N = len(samples)
rare_tools = {k:v for k,v in counts['tool_samples'].items() if v <= 5}
expected_missed = sum(math.exp(sum(math.log((N-v-i)/(N-i)) for i in range(300))) for v in counts['tool_samples'].values() if N-v >= 300)
assert len(rows) == len({r['id'] for r in rows}) == sum(counts['n_calls'].values())
assert sum(r['n_calls'] for r in rows) == sum(counts['tool_calls'].values())
report = ['# EDA tập train để chuẩn bị validation khoảng 300 mẫu', '',
          f'Nguồn: `data/train/train.jsonl`; **{N:,} mẫu**, {len(set(s["id"] for s in samples)):,} ID duy nhất. SHA256: `{summary["source_sha256"]}`.',
          '', 'Phân tích offline toàn bộ metadata, label, header WAV và replay ToolEnv. Không chạy ASR/LLM, không gửi API và chưa chọn subset.', '',
          '## Những điểm cần nhớ', '',
          f'- {sum(bool(r["history_turns"]) for r in rows):,} mẫu có history ({sum(bool(r["history_turns"]) for r in rows)/N:.1%}); {sum(r["history_turns"] >= 10 for r in rows)} mẫu có từ 10 lượt history trở lên.',
          f'- {sum(r["n_apps"] >= 2 for r in rows)} mẫu gọi ít nhất 2 app ({sum(r["n_apps"] >= 2 for r in rows)/N:.1%}); reference có tổng {sum(r["n_calls"] for r in rows):,} calls.',
          f'- {len(rare_tools)} tools chỉ xuất hiện ở 1–5 mẫu. Chọn ngẫu nhiên đều 300 mẫu dự kiến bỏ sót khoảng {expected_missed:.1f}/146 tool đang có trong train (kỳ vọng lý thuyết từ phân phối hiện tại, không chạy simulation).',
          '- Tool chỉ có 1 mẫu có xác suất bị bỏ sót 80.6%; tool có 5 mẫu vẫn có xác suất bị bỏ sót 33.9%. Cần ràng buộc coverage.',
          '- Không thể bao phủ toàn bộ 695 chuỗi tool khác nhau bằng 300 mẫu; nên ưu tiên đủ tool, các nhóm độ khó và chuỗi nghiệp vụ tiêu biểu.', '',
          '## Phân phối chính', '']
def table(title, counter, limit=None):
    report.extend([f'### {title}', '', '| Nhóm | Số mẫu | Tỷ lệ | Mốc tỷ lệ cho 300 mẫu |', '|---|---:|---:|---:|'])
    for k,v in counter.most_common(limit):
        report.append(f'| {k} | {v} | {v/N:.1%} | {300*v/N:.1f} |')
    report.append('')
for title,key in [('Số tool calls chuẩn', 'n_calls'), ('Số app được gọi trong yêu cầu hiện tại', 'n_apps'), ('Loại hành động (theo kind trong catalog)', 'mode'), ('Số lượt history (tất cả role)', 'history_turns'), ('State canonical có thay đổi sau replay?', 'state_changed'), ('Thành phố trong user_profile', 'city'), ('App xuất hiện trong reference calls', 'app_samples')]:
    table(title, counts[key])
report.extend(['Một mẫu có thể gọi nhiều app nên các tỷ lệ app không cộng thành 100%. `write` nghĩa là có ít nhất một write tool; `meta_or_other` gồm tool hệ thống hoặc kind khác. State không đổi không có nghĩa là mẫu không cần hành động.', '', '## Tool coverage', '',
               f'Catalog: {len(tools)} tools / {len(catalog["apps"])} apps. Reference hiện tại dùng {summary["observed_tools"]} tools. Có {len(sequences)} chuỗi tên tool khác nhau (giữ thứ tự, bỏ arguments).', '',
               '| Tool | Số mẫu chứa tool | Tổng lần gọi | Mốc tỷ lệ /300 |', '|---|---:|---:|---:|'])
for k,v in counts['tool_samples'].most_common():
    report.append(f'| {k} | {v} | {counts["tool_calls"][k]} | {300*v/N:.1f} |')
report.extend(['', 'Tools trong catalog không có reference call: '+(', '.join(summary['unused_tools']) or 'không có')+'.', '', '## Độ dài và lượng context', '', '| Đại lượng | Min | P50 | P90 | P95 | Max |', '|---|---:|---:|---:|---:|---:|'])
for k,d in numeric.items():
    report.append(f'| {k} | {d["min"]:.2f} | {d["median"]:.2f} | {d["p90"]:.2f} | {d["p95"]:.2f} | {d["max"]:.2f} |')
report.extend(['', f'Tổng audio query hiện tại: {numeric["audio_seconds"]["total"]/60:.1f} phút; audio history: {numeric["history_audio_seconds"]["total"]/60:.1f} phút. Đây là thời lượng nguồn, không phải thời gian inference.', '', '## Tool hiếm cần chú ý', '', '| Tool | Số mẫu |', '|---|---:|', *[f'| {k} | {v} |' for k,v in sorted(rare_tools.items(), key=lambda x:(x[1], x[0]))], '', '## Chất lượng và giới hạn', '',
               f'- Lỗi đọc WAV: {len(audio_issues)}; reference calls trả `ok=false`: {len(errors)}.',
               f'- Query trùng sau lowercase/collapse whitespace: {len(duplicates["normalized_query"])} nhóm, {sum(len(x)-1 for x in duplicates["normalized_query"])} bản lặp thêm.',
               f'- Audio query giống hệt byte: {len(duplicates["current_audio_sha256"])} nhóm.',
               '- Query giống nhau có thể đi kèm state/context khác; không tự động loại trùng.',
               '- `available_tools` trong bảng chỉ đếm tool do installed_apps quảng bá; agent còn bổ sung sys.ask_missing_info nếu chưa có. Đây không phải số token prompt.',
               '- Chưa đánh giá giọng vùng miền, giới tính, nhiễu hay độ chính xác transcript. Không suy diễn các thuộc tính này từ city.',
               '- Không có nhãn intent/scenario chính thức. Các nhóm hành vi ở đây suy ra từ reference calls/catalog, không phải phân loại ngữ nghĩa đầy đủ.',
               '- Replay chỉ dùng để xem state thay đổi và phát hiện lỗi schema; không chứng minh mọi label đúng ngữ nghĩa hoặc thay thế scorer BTC.', '', '## Hướng lấy khoảng 300 mẫu', '',
               '- Dùng mẫu cố định, seed cố định và lưu manifest ID + checksum nguồn để các experiment so sánh cùng tập.',
               '- Giữ gần phân phối đồng thời theo số calls (0/1/2/3/4–5/6+), có/không history, số app, read/write/meta và audio ngắn/vừa/dài.',
               '- Thêm ràng buộc coverage tool hiếm và chuỗi thao tác hiếm. Báo cáo rõ phần nào bị lấy nhiều hơn tỷ lệ gốc; không thể vừa giữ mọi tỷ lệ tuyệt đối vừa bảo đảm mọi nhóm hiếm.',
               '- Tránh dùng một intent/app chính duy nhất để chia tầng vì nhiều mẫu gọi nhiều app. Dùng lấy mẫu nhiều nhãn và kiểm tra độ lệch từng phân phối sau chọn.',
               '- Không dùng kết quả đúng/sai của baseline để chọn mẫu, tránh thiên lệch về giải pháp hiện tại.',
               '- 300/1545 = 19.4% tập gốc. Nếu điểm là tỷ lệ nhị phân, sai số lấy mẫu ở vùng 50% khoảng ±5.1 điểm phần trăm (95%, lấy mẫu ngẫu nhiên không hoàn lại); đây là mốc tham khảo, không áp dụng trực tiếp cho F1 hay thiết kế cố ý tăng nhóm hiếm.',
               '- Chưa chọn 300 ID ở bước EDA này. Tập nhỏ dùng để iterate; vẫn cần kiểm tra trên tập train đầy đủ khi chốt giải pháp.', '', '## Tái lập', '', '` .venv/bin/python scripts/eda_train.py `', '', 'Chi tiết: `result/train-eda/summary.json`, `sample_features.csv`.'])
(OUT/'report.md').write_text('\n'.join(report)+'\n')
print(json.dumps(summary, ensure_ascii=False, indent=2))
