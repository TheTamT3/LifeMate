import json, html, shutil
import sys
from pathlib import Path
from datetime import datetime

base = Path('.superpowers/brainstorm/1407-1793604678/content')
sample_id = sys.argv[1] if len(sys.argv) > 1 else 'train_1750'
data = json.loads(Path('logs/merge_experiments_snapshot.json').read_text(encoding='utf-8'))
root = next(r for r in data['selected'] if r['inputs']['sample_id'] == sample_id)
sample = next(json.loads(line) for line in Path('train+public_test/train+public_test/train/train.jsonl').read_text(encoding='utf-8').splitlines() if json.loads(line)['id'] == sample_id)
nodes = sorted([r for r in data['runs'] if r['trace_id'] == root['trace_id']], key=lambda r:r['start_time'])
llms = [r for r in nodes if r['run_type'] == 'llm']
def esc(v): return html.escape(str(v))
def pretty(v): return '<pre>'+esc(json.dumps(v,ensure_ascii=False,indent=2))+'</pre>'
def duration(r): return (datetime.fromisoformat(r['end_time'])-datetime.fromisoformat(r['start_time'])).total_seconds()
original=(base/'review-layout.html').read_text(encoding='utf-8')
style=original[original.index('<style>'):original.index('</style>')+8]
history=''.join('<div class="bubble '+('user' if m['role']=='user' else '')+'"><small>'+esc(m['role'].upper())+'</small><p>'+esc(m.get('audio_text',m.get('text','')))+'</p>'+('<details><summary>Tool calls / results trong history</summary>'+pretty({k:m[k] for k in ('tool_calls','tool_results') if k in m})+'</details>' if m.get('tool_calls') else '')+'</div>' for m in sample['history'])
timeline=''
llm_index=0
for n in nodes:
    if n['run_type']=='llm':
        llm_index+=1
        parts=n['outputs']['response']['parts']
        timeline+='<section class="card"><h2>LLM lượt '+str(llm_index)+' / '+str(len(llms))+' · '+f'{duration(n):.2f}s'+'</h2><p class="note">finish_reason: '+esc(n['outputs']['response'].get('finish_reason'))+'</p>'
        for p in parts:
            if p['part_kind']=='thinking': timeline+='<h3>REASONING THỰC TẾ</h3><pre>'+esc(p['content'])+'</pre>'
            elif p['part_kind']=='text': timeline+='<h3>'+('TEXT Ở LƯỢT LLM CUỐI' if llm_index==len(llms) else 'TEXT Ở LƯỢT NÀY · CHƯA PHẢI LƯỢT CUỐI')+'</h3><p>'+esc(p['content'])+'</p>'
            elif p['part_kind']=='tool-call':
                raw=p['args']
                try:
                    parsed=json.loads(raw) if isinstance(raw,str) else raw
                    rendered=pretty(parsed)
                except (ValueError,TypeError):
                    rendered='<p class="note">Tham số không phải JSON hợp lệ; hiển thị nguyên văn.</p><pre>'+esc(raw)+'</pre>'
                timeline+='<h3>TOOL CALL · '+esc(p['tool_name'])+'</h3>'+rendered
                if isinstance(raw,str):
                    timeline+='<details><summary>Xem chuỗi raw gốc</summary><pre>'+esc(raw)+'</pre></details>'
        timeline+='<p class="note">Reasoning tokens: '+esc(n['outputs']['response'].get('usage',{}).get('details',{}).get('reasoning_tokens','Không được ghi nhận'))+'. Tổng token trong snapshot là 0, không coi đó là lượng token thực tế.</p></section>'
    elif n['name'].startswith('tool.'):
        timeline+='<section class="card"><h2>'+esc(n['name'])+' · '+f'{duration(n):.3f}s'+'</h2>'+pretty(n['inputs'])+'<details><summary>Kết quả tool thực tế</summary>'+pretty(n['outputs'])+'</details></section>'
audio=Path('train+public_test/train+public_test/train')/sample['audio']
audiohtml='<p class="note">Không tìm thấy audio gốc tại máy này.</p>'
if audio.exists():
    shutil.copyfile(audio,base/'train_1750.wav')
    audiohtml='<audio controls preload="none" src="/files/train_1750.wav" style="width:100%"></audio>'
stats=root['feedback_stats']
reviewmain='<main><div class="row"><h1>train_1750</h1><span class="badge bad">Tool call ≠ label</span></div><p>Tổng thời gian '+f'{duration(root):.2f}s'+' · '+str(len(llms))+' LLM call · '+str(len(root['outputs']['tool_calls']))+' tool calls</p><section class="card"><h2>Audio text</h2><p>'+esc(sample['audio_text'])+'</p>'+audiohtml+'<details><summary>Context tại thời điểm yêu cầu</summary>'+pretty(sample['context'])+'</details><details><summary>Conversation · '+str(len(sample['history']))+' lượt lịch sử</summary>'+history+'</details></section><section class="card"><h2>Dự đoán và reference</h2><div class="compare"><div><h3>TOOL CALLS ĐÃ THỰC THI</h3>'+pretty(root['outputs']['tool_calls'])+'</div><div><h3>LABEL GỐC</h3>'+pretty(sample['label']['tool_calls'])+'</div></div><p class="note">Khác biệt nhìn thấy: alarm.create có thêm label và repeat. Đây là đối chiếu dữ liệu, chưa phải kết luận của reviewer.</p><span class="badge bad">Tool call accuracy: '+str(stats['tool_call_accuracy']['avg'])+'</span> <span class="badge good">State hash match: '+str(stats['state_hash_match']['avg'])+'</span><details><summary>Reference output đầy đủ</summary>'+pretty(sample['label'])+'</details><details><summary>Output root và ghi chú evaluator</summary>'+pretty(root['outputs'])+pretty({k:v['comments'] for k,v in stats.items()})+'</details></section><h2>Trace theo thời gian bắt đầu</h2>'+timeline+'<p class="note">Snapshot gốc: '+esc(root['session_id'])+' · run '+esc(root['id'])+'</p><a target="_blank" rel="noopener" href="https://smith.langchain.com'+esc(root['app_path'])+'">Mở trace nguồn ↗</a></main>'
right=original[original.index('<aside class="right">'):original.index('</aside></div></html>')+8]
right=right.replace(' checked','').replace('Model thêm wrapper arguments cho tool không nhận tham số. Cần phân biệt payload gốc với payload đã chuẩn hóa.','').replace('Mockup chưa lưu bền vững. Bản chính sẽ lưu SQLite trên máy.','Bản thử lưu review sample này trong trình duyệt (localStorage), chưa ghi SQLite hoặc LangSmith.')
start=right.index('onclick="document.getElementById')
end=right.index('">Lưu',start)
right=right[:start]+'onclick="saveReview()"'+right[end+1:]
durations=sorted(duration(r) for r in data['selected'])
metric=lambda key:sum(r['feedback_stats'][key]['avg'] for r in data['selected'])/300*100
overall=f'''<main style="max-width:1200px"><h1>Tổng quan experiment</h1><p>300 sample thật · Snapshot experiment đã merge · Một sample có chi tiết trong mockup</p><div class="compare"><section class="card"><h2>Điểm tự động · toàn bộ 300 sample</h2><p>State hash match <b>{metric('state_hash_match'):.2f}%</b></p><p>Tool call accuracy <b>{metric('tool_call_accuracy'):.2f}%</b></p><p>Root runtime errors <b>{sum(bool(r.get('error')) for r in data['selected'])}</b></p></section><section class="card"><h2>Review thủ công · dữ liệu thử trên trình duyệt</h2><p id="progress"></p><p id="result"></p><button class="primary" onclick="showTab('review')">Review train_1750 →</button></section><section class="card"><h2>Thời gian · root trace thật</h2><p>Trung vị <b>{(durations[149]+durations[150])/2:.2f}s</b></p><p>p95 (nearest rank) <b>{durations[284]:.2f}s</b></p><p>Vượt 30 giây <b>{sum(t>30 for t in durations)} / 300</b></p><p class="note">Gồm thời gian pipeline được root trace ghi nhận; nguồn gồm hai lần chạy khác nhau.</p></section><section class="card"><h2>Nguyên nhân theo reviewer</h2><div id="causes"></div><p class="note">Chỉ tổng hợp đánh dấu của bạn trên sample thử, chưa tự suy diễn nguyên nhân cho 299 sample còn lại.</p></section></div></main>'''
script='''<script>
const key='lifemate-mockup-review-train1750-v1';
function stored(){try{return JSON.parse(localStorage.getItem(key)||'null')}catch{return null}}
function updateOverall(){const r=stored();document.getElementById('progress').textContent=r?'Đã review: 1 / 300 · Chưa review: 299':'Đã review: 0 / 300 · Chưa review: 300';document.getElementById('result').textContent=r?'Kết luận train_1750: '+r.verdict:'Chưa có kết luận thủ công';document.getElementById('causes').textContent=r&&r.tags.length?r.tags.join(' · '):'Chưa có nhãn nguyên nhân';}
function showTab(tab){document.getElementById('review').hidden=tab!=='review';document.getElementById('overall').hidden=tab!=='overall';updateOverall();document.querySelectorAll('[data-tab]').forEach(b=>b.classList.toggle('active',b.dataset.tab===tab));}
function saveReview(){document.getElementById('status').value='Đã review';const r={verdict:document.getElementById('verdict').value,comment:document.getElementById('comment').value,tags:[...document.querySelectorAll('.tags input:checked')].map(x=>x.parentElement.textContent.trim())};try{localStorage.setItem(key,JSON.stringify(r));document.getElementById('saved').textContent='Đã lưu thử trên trình duyệt ✓';updateOverall()}catch{document.getElementById('saved').textContent='Không lưu được: trình duyệt chặn localStorage.'}}
const r=stored();if(r){document.getElementById('verdict').value=r.verdict;document.getElementById('comment').value=r.comment;document.getElementById('status').value='Đã review';document.querySelectorAll('.tags input').forEach(x=>x.checked=r.tags.includes(x.parentElement.textContent.trim()))}showTab('review');
</script>'''
page='<!DOCTYPE html><html lang="vi"><meta charset="utf-8"><title>LifeMate · Real sample review</title>'+style+'<div class="prototype">MOCKUP THỬ NGHIỆM · train_1750 dùng dữ liệu thật · Nhận xét chỉ lưu trong trình duyệt này</div><header><div><b>LifeMate / Experiment review</b><br><small>Snapshot merged · 300 samples · Local</small></div><div class="tabs"><button data-tab="overall" onclick="showTab(\'overall\')">Tổng quan</button><button data-tab="review" onclick="showTab(\'review\')">Review sample</button></div></header><div id="overall" hidden>'+overall+'</div><div id="review"><div class="shell"><aside><h2>Sample thật</h2><div class="sample active"><b>train_1750</b><small>alarm.create · news.headlines</small></div><p class="note">Mockup chỉ nạp chi tiết một sample. Tổng quan tính điểm và thời gian từ 300 root trace thật.</p></aside>'+reviewmain+right+'</div></div>'+script+'</html>'
page=page.replace('train_1750',sample_id).replace('train1750',sample_id.replace('_','')).replace('alarm.create · news.headlines',' · '.join(dict.fromkeys(c['name'] for c in root['outputs']['tool_calls'])))
page=page.replace('Khác biệt nhìn thấy: alarm.create có thêm label và repeat. Đây là đối chiếu dữ liệu, chưa phải kết luận của reviewer.','So sánh tên tool, tham số và số lần gọi giữa hai cột; điểm tự động không thay thế kết luận reviewer.')
page=page.replace('Output root và ghi chú evaluator','Kết quả tổng hợp pipeline & giải thích điểm tự động')
page=page.replace('</style>','.shell{grid-template-columns:190px minmax(650px,1fr) 290px;align-items:start}.compare{grid-template-columns:minmax(0,1fr) minmax(0,1fr)}main{max-width:none}.right{grid-column:auto;position:sticky;top:12px;max-height:calc(100vh - 24px);overflow-y:auto;align-self:start}.right>button{position:sticky;bottom:0;box-shadow:0 -5px 12px white}.step-note{float:right;font-size:12px;margin-bottom:10px}.end-review{padding:20px;background:#e6f2ee;border-radius:10px;margin:20px 0}.end-review p{line-height:1.6}body{min-width:1150px}</style>')
for n in nodes:
    if n['run_type']=='llm':
        i=llms.index(n)+1
        heading='LLM lượt '+str(i)+' / '+str(len(llms))
        label='LLM lượt '+str(i)
    elif n['name'].startswith('tool.'):
        heading=esc(n['name'])+' · '
        label=n['name']+' ('+n['id'][:8]+')'
    else:
        continue
    # Attach the note button to the specific node's heading, rather than its JSON payload.
    target='<section class="card"><h2>'+heading
    button='<button class="step-note" onclick="noteStep(this)" data-step="'+esc(label)+'">＋ Ghi chú bước này</button>'
    page=page.replace(target,'<section class="card">'+button+'<h2>'+heading,1)
page=page.replace('</main><aside class="right">','<section class="end-review"><b>Đã đọc hết trace</b><p>Lưu nhận xét tại đây hoặc tiếp tục chỉnh trong panel bên phải.</p><button class="primary" onclick="saveReview()">Lưu review</button> <button onclick="saveReview();showTab(\'overall\')">Lưu & về Tổng quan</button><p class="note">Bản chính sẽ có “Lưu & sang sample tiếp theo”. Mockup hiện chỉ có một sample thật.</p></section></main><aside class="right">')
page=page.replace('function stored(){','function noteStep(button){const field=document.getElementById("comment");field.value+=(field.value?"\\n\\n":"")+"["+button.dataset.step+"] ";field.focus({preventScroll:true});field.setSelectionRange(field.value.length,field.value.length);field.scrollTop=field.scrollHeight;document.getElementById("saved").textContent="Đang ghi chú · chưa lưu";}\nfunction stored(){')
comments='''<div id="comments" hidden><main style="max-width:1200px"><h1>Nhận xét</h1><p class="note">Nhận xét đã lưu trong trình duyệt cho sample thử. Chưa có dữ liệu review cho 299 sample còn lại.</p><div class="card"><div class="compare"><input id="comment-search" type="search" placeholder="Tìm sample hoặc nội dung comment…" oninput="renderComments()"><select id="comment-verdict" onchange="renderComments()"><option value="">Tất cả kết luận</option><option>Chưa kết luận</option><option>Agent đúng</option><option>Agent sai</option><option>Label có vấn đề</option><option>Chưa đủ dữ liệu</option></select></div><select id="comment-tag" onchange="renderComments()"><option value="">Tất cả nhãn lỗi</option><option>Hiểu sai yêu cầu</option><option>Chọn sai tool</option><option>Sai / bịa tham số</option><option>Thiếu / thừa bước</option><option>Lỗi thực thi</option><option>Label / evaluator</option><option>Vượt 30 giây</option></select><p id="comment-empty" class="note"></p><div style="overflow-x:auto"><table id="comment-table" style="width:100%;border-collapse:collapse;text-align:left"><thead><tr><th>Sample</th><th>Kết luận</th><th>Nhãn lỗi</th><th>Comment</th><th>Cập nhật</th><th></th></tr></thead><tbody id="comment-rows"></tbody></table></div></div></main></div>'''
page=page.replace('<button data-tab="review"', '<button data-tab="comments" onclick="showTab(\'comments\')">Nhận xét</button><button data-tab="review"',1)
page=page.replace('<div id="review">',comments+'<div id="review">',1)
page=page.replace("function showTab(tab){", "function showTab(tab){document.getElementById('comments').hidden=tab!=='comments';renderComments();")
page=page.replace("const r={verdict:","const r={updatedAt:new Date().toISOString(),verdict:")
page=page.replace("function stored(){",'''function renderComments(){
const r=stored(), body=document.getElementById('comment-rows');body.replaceChildren();
const query=document.getElementById('comment-search').value.trim().toLocaleLowerCase();
const verdict=document.getElementById('comment-verdict').value,tag=document.getElementById('comment-tag').value;
const visible=r&&(!query||('train_1475 '+r.comment).toLocaleLowerCase().includes(query))&&(!verdict||r.verdict===verdict)&&(!tag||r.tags.includes(tag));
document.getElementById('comment-table').hidden=!visible;
document.getElementById('comment-empty').textContent=visible?'1 sample có review đã lưu':r?'Không có nhận xét phù hợp bộ lọc.':'Chưa có review đã lưu. Mở tab Review sample, nhập nhận xét rồi bấm Lưu.';
if(!visible)return;
const tr=document.createElement('tr');
for(const value of ['train_1475',r.verdict,r.tags.join(' · '),r.comment||'Chưa có comment',r.updatedAt?new Date(r.updatedAt).toLocaleString('vi-VN'):'Chưa ghi nhận thời gian']){const td=document.createElement('td');td.textContent=value;td.style.cssText='padding:16px 12px;border-top:1px solid #dfe4e8;vertical-align:top;white-space:pre-wrap;max-width:420px;overflow-wrap:anywhere';tr.append(td)}
const td=document.createElement('td'),btn=document.createElement('button');btn.textContent='Mở sample →';btn.onclick=()=>{showTab('review');document.getElementById('comment').focus({preventScroll:true})};td.append(btn);tr.append(td);body.append(tr);
}
function stored(){''')
page=page.replace('updateOverall()}catch','updateOverall();renderComments()}catch')
page=page.replace('</style>','header .tabs button{background:#294b55;color:#f1f7f8;border:1px solid #527680;font-weight:600}header .tabs button:hover{background:#386471;color:white}header .tabs button.active{background:#8ce0c4;color:#103f35;border-color:#8ce0c4;box-shadow:0 0 0 2px #142c32,0 0 0 3px #8ce0c4}header .tabs button:focus-visible{outline:3px solid #f5cc78;outline-offset:3px}</style>')
(base/'review-tab-colors-v7.html').write_text(page,encoding='utf-8')
print(json.dumps({'sample':sample['id'],'nodes':len(nodes),'audio_available':audio.exists(),'duration_s':duration(root),'size':len(page)}))
