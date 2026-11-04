
const key='lifemate-mockup-review-train1475-v1';
function noteStep(button){const field=document.getElementById("comment");field.value+=(field.value?"\n\n":"")+"["+button.dataset.step+"] ";field.focus({preventScroll:true});field.setSelectionRange(field.value.length,field.value.length);field.scrollTop=field.scrollHeight;document.getElementById("saved").textContent="Đang ghi chú · chưa lưu";}
function renderComments(){
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
function stored(){try{return JSON.parse(localStorage.getItem(key)||'null')}catch{return null}}
function updateOverall(){const r=stored();document.getElementById('progress').textContent=r?'Đã review: 1 / 300 · Chưa review: 299':'Đã review: 0 / 300 · Chưa review: 300';document.getElementById('result').textContent=r?'Kết luận train_1475: '+r.verdict:'Chưa có kết luận thủ công';document.getElementById('causes').textContent=r&&r.tags.length?r.tags.join(' · '):'Chưa có nhãn nguyên nhân';}
function showTab(tab){document.getElementById('comments').hidden=tab!=='comments';renderComments();document.getElementById('review').hidden=tab!=='review';document.getElementById('overall').hidden=tab!=='overall';updateOverall();document.querySelectorAll('[data-tab]').forEach(b=>b.classList.toggle('active',b.dataset.tab===tab));}
function saveReview(){document.getElementById('status').value='Đã review';const r={updatedAt:new Date().toISOString(),verdict:document.getElementById('verdict').value,comment:document.getElementById('comment').value,tags:[...document.querySelectorAll('.tags input:checked')].map(x=>x.parentElement.textContent.trim())};try{localStorage.setItem(key,JSON.stringify(r));document.getElementById('saved').textContent='Đã lưu thử trên trình duyệt ✓';updateOverall();renderComments()}catch{document.getElementById('saved').textContent='Không lưu được: trình duyệt chặn localStorage.'}}
const r=stored();if(r){document.getElementById('verdict').value=r.verdict;document.getElementById('comment').value=r.comment;document.getElementById('status').value='Đã review';document.querySelectorAll('.tags input').forEach(x=>x.checked=r.tags.includes(x.parentElement.textContent.trim()))}showTab('review');

