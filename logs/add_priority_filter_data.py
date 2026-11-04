import json
from pathlib import Path

root = Path(__file__).resolve().parents[1]
directory = root / 'review_data/error_grouping_full_20261102'
ids = [row['sample_id'] for row in json.loads((directory / 'priority_review.json').read_text(encoding='utf-8'))]
assert len(ids) == len(set(ids)) == 13
for path in (directory / 'analysis.json', root / 'review_data/error_analysis.json'):
    data = json.loads(path.read_text(encoding='utf-8'))
    assert set(ids) <= {row['sample_id'] for row in data['records']}
    data['priority_review_ids'] = ids
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding='utf-8')
builder = directory / 'build_full_analysis.py'
text = builder.read_text(encoding='utf-8')
text = text.replace("groups=groups,records=records)", "groups=groups,records=records,priority_review_ids=[r['sample_id'] for r in json.loads((HERE/'priority_review.json').read_text(encoding='utf-8'))])")
builder.write_text(text, encoding='utf-8')
ui = root / 'review-ui/src/ErrorAnalysis.jsx'
text = ui.read_text(encoding='utf-8')
text = text.replace('data.records.filter(r => belongs(r, id)).length', 'scoped.filter(r => belongs(r, id)).length')
text = text.replace('group?.name || "Chưa có nhóm"', 'group?.name || "Tất cả nhóm trong phạm vi lọc"')
text = text.replace('r.primary_group === gid ?', '(!gid || r.primary_group === gid) ?')
ui.write_text(text, encoding='utf-8')
print('Added priority metadata for', len(ids), 'samples; reviews and snapshot untouched.')
