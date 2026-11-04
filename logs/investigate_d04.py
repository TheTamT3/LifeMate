"""D04 authored investigation, trace/code only; no replay."""
import json, hashlib, sqlite3, urllib.request
from pathlib import Path
from collections import Counter
from datetime import datetime, timezone
BASE='http://127.0.0.1:8765'
OUT=Path('review_data/d04_investigation_20261103')
NAMES={
 'repeat':'Truyền rõ repeat=once, trùng mặc định',
 'priority':'Truyền rõ priority=normal, trùng mặc định',
 'timestamp':'Thời gian ghi workout trùng current_time mặc định',
 'calendar_end':'Bỏ hoặc truyền end trùng start + 1 giờ',
 'route_mode':'Truyền rõ phương tiện mặc định của route',
 'robot_mode':'Mode robot tương đương trong state này, phụ thuộc state',
 'email_default':'unread_only=false tương đương không lọc',
 'date_scope':'Ngày xổ số là phạm vi truy vấn, không phải mặc định runtime',
}
FINDINGS={
 '0033':('repeat','repeatonce trùng Alarm.create default; alarm11:10 sai vì lấy current13:10 trừ2h thay giờ họp19:30. Không sửa giờ sai bằng bỏ repeat; label là metadata riêng.'),
 '0097':('repeat','Reminders.create defaults once, thời gian25/11 19:45 đúng. Viết hoa Uống thuốc là free text, không tạo lịch lặp khác; content bị canon bỏ khi hash.'),
 '0178':('repeat','Nhắc26/11 19:45 đúng; repeatonce tường minh bằng default. Giữ feedback agree đã chốt và nội dung review hiện tại.'),
 '0188':('repeat','05/11 13:10+45phút=13:55 đúng; repeatonce không đổi hành vi. Content khác chữ hoa là khác biệt riêng được canon bỏ.'),
 '0294':('repeat','Reminder21/11 07:00 đúng, repeatonce bằng default. Không tắt đèn đã bị rút lệnh; lọc phòng và climate24 đúng, đã có điều traD02 riêng.'),
 '0336':('repeat','Alarm repeatonce đúng default của alarm nhưng user cần reminder; đổi tool và SMS cho cảhaiLan là lỗi độc lập. Không coi repeatonce là nguyên nhân sai người/loại nhắc.'),
 '0437':('route_mode','Maps.get_route mode=None chọnmotorbike. Outputactual/reference cùng5.2km18phút; near/query/destination khác cần xét riêng. Giữ disagree=commentcũđúng theo quyết định reviewer, không tự sửa verdict dù có bằng chứng runtime này.'),
 '0511':('timestamp','Fitness.log_workout time=None lấysession.now, chính là25/09 09:00 current_time; explicit cùnggiờ không khác contract. Không chứng minh đây là giờ bắt đầu tập. Reminderonce cũng default; giữ agree và comment gốc.'),
 '0539':('email_default','Email.list chỉ lọc nếu unread_only truthy; false và None đều trả toàn bộ thư, cómail06 đãđọc. Thiếu draft saucancel làP01, khôngdo unreadfalse.'),
 '0573':('priority','Tasks.add defaults prioritynormal; task hạn26/09 10:00 đúng. news.save thêm saved01 ngoài yêu cầu là lỗi độc lập, không phải do priority.'),
 '0610':('priority','Prioritynormal bằng default; shopping quantity400 món thay1cuộn400cm và task due01/10 thay03/10 là lỗi riêng. Bỏ priority không chữa quantity/date.'),
 '0701':('priority','Tasks.add normal bằng default; ep12 đúng và due11/10 20:00 đúng. Title rút gọn thiếu liên kết tập cần xét content/call riêng, không thay ưu tiên task.'),
 '0703':('timestamp','time01/10 09:00 bằngcurrent_time/session.now mặc địnhlog_workout; yoga40 và nhạc đúng. Không suy thời điểm bắt đầu tập; giữ agree và comment gốc.'),
 '0706':('robot_mode','Mode không truyền được chọn state.mode rồi mới fallbackvacuum; initialstatevacuum nên explicitvacuum tương đương ở case này. Prioritynormal cũng default. rooms[] thực tếwhole_house=true và task sai ngày là hai lỗi độc lập, không phải mode.'),
 '0787':('repeat','repeatonce là default; ngày05/10 thay thứNăm08/10 là lỗi nối thứ/ngày. Phép trừ10:00-7phút đúng09:53, không sửa date bằng bỏrepeat.'),
 '0792':('calendar_end','Calendar.create_event bỏend sẽ parse start14:00 và cộng1h thành15:00, đúngreference. Flightfl06/passenger1/pickup21/10 đúng; title khác được xét riêng, không gây chênh end.'),
 '0803':('priority','prioritynormal đúngdefault; usage14>12 và task20:00 đúng. Title thêm diễn đạt thời gian không chứng minh ưu tiên sai.'),
 '0829':('calendar_end','Omitend cho start31/10 08:00 được runtime sinh09:00 đúngreference. Cancelsub05 đúng; titleparaphrase là riêng, không thiếu thời lượng.'),
 '0835':('calendar_end','Omitend cho start16/10 14:00 sinh15:00 đúngreference. Giữ địa chỉ đãsửa25LýThườngKiệt, không có lỗi thời lượng hoặc địa chỉ52.'),
 '1005':('date_scope','Actualcheck_ticket yêu cầu date04/11 vànumber95; toolnày so dateexact, không mặc địnhhômnay. Referenceget_results khôngdate trảmọingày; stateđãghi có đúng kết quả04/11 nên xác nhậntrúngeighth. Đây còn khácAPIvàreadcontactthêm, không phải chỉ dư mộtdefault.'),
 '1060':('robot_mode','Statuscho modevacuum,pin75; omitmode sẽ lấystate.mode=vacuum nên explicit cùnggiátrị. Roomsphòngkhách đúnghistory. Không suy vacuum luôndefault nếu state đangmop.'),
 '1202':('calendar_end','Explicitend18:30 bằngstart17:30+1h mà runtime tựsinh khiomitted. 300*25561=7668300>7600000 đúng; get_ratevsconvert vàlocation/title riêng, khôngcoiend làthờilượngbịa.'),
 '1236':('date_scope','Lottery.get_results(date14/10) lọcđúngngàyhômnay; omitdate khôngdefaulttoday mà đọcmọingày. Reminderrepeatonce bằngdefault, nhưng time18:00 sai so ridehistory17:30; sai giờ khôngdo datexổsố.'),
 '1295':('repeat','repeatonce bằngAlarmdefault. Không đọcgiádiesel và hiểu dưới20thànhlít là nguyên nhânbỏđiềukiện; labelthêm khôngphải mặcđịnh.'),
 '1349':('repeat','Alarm05:30 repeatonce trùngdefault. Labelthêm và wordingemail là khácbiệtcallriêng; free-textlabel bịcanonbỏ nên khôngđược mặcđịnh nói label gây state_hash mismatch.'),
 '1533':('repeat','Alarm12:30 repeatonce defaultđúng. Khônglist_meetings và giảđịnh14:00 để tạo13:00 là lỗi grounding dù trùnggiờreference; labeltitle cầnxétriêng.'),
 '1568':('repeat','Reservebook874 đúnghistory; reminder17/11 thứBa19:00 đúng. repeatonce mặcđịnh, thêm tênNhàgiảkim cócăn cứnhưng là text khácreference, khôngphải lặplịchsai.'),
 '1750':('repeat','Alarm01/12 06:00 vànewsentertainment đủtoolreference; repeatonce bằngdefault. Labelkhác ảnhhưởngcallmatching nhưng bịcanonbỏkhihash; thiếutextđọctin làtiêuchíUXriêng, giữđiềutraP01trước.'),
}
def get(path):
 with urllib.request.urlopen(BASE+path) as r:return json.load(r)
def main():
 OUT.mkdir(exist_ok=True)
 data=get('/api/analysis');before=get('/api/export');reviews=get('/api/reviews')
 rows=[r for r in data['records'] if r['primary_group']=='D04' or 'D04'in r['secondary_groups']]
 assert {r['sample_id'] for r in rows}=={'train_'+sid for sid in FINDINGS}
 paths=['review_data/error_analysis.json','review_data/snapshot.json','review_data/group_causes.json']
 original={p:Path(p).read_bytes() for p in paths}
 (OUT/'group_causes_before.json').write_bytes(original[paths[2]])
 (OUT/'export_before.json').write_text(json.dumps(before,ensure_ascii=False,indent=2),encoding='utf-8')
 with sqlite3.connect('review_data/reviews.sqlite') as src,sqlite3.connect(OUT/'before.sqlite') as dst:src.backup(dst)
 prepared=[]
 for r in rows:
  sid=r['sample_id'];group,finding=FINDINGS[sid.split('_')[1]];old=data['investigations'].get(sid,{})
  assert '[D04 · Điều tra' not in old.get('evidence',''),'Already investigated: '+sid
  block='\n\n'.join(['[D04 · Điều tra từ trace/schema/runtime, chưa replay]','Nhóm nguyên nhân D04: '+NAMES[group],finding,
    'Câu hỏi: '+r['question'],'Comment hiện tại đã đọc, giữ nguyên: '+reviews.get(sid,r['existing_review']).get('comment',''),
    'Execution: '+json.dumps([{'tool':t['name'],'inputs':t['inputs'],'output':t['outputs'],'node':t['id']}for t in r['executed_tools']],ensure_ascii=False),
    'Reference calls/results: '+json.dumps({'calls':r['reference_calls'],'results':r['reference_results']},ensure_ascii=False),
    'Context current_time: '+str(r['context'].get('current_time'))+'; node LLM: '+', '.join(n['id']for n in r['llm_evidence']),
    'Code: zaic_tools/apps/alarm.py:create và reminders.py:create default repeatonce; tasks.py:add defaultnormal; fitness.py:log_workout lấysession.now; calendar.py:create_event tựcộng1h; maps.py:get_route defaultmotorbike; robot_vacuum.py:start chọn mode or state.mode or vacuum; email.py:list falsekhônglọc; lottery.py:get_results date=None bỏlọcngày, check_ticket soexactdate.',
    'Metric: src/lifemate/agent_evaluation.py:_matches đòitậpkhóaargumentsgiốngreference. Giátrịmặcđịnhtươngđươngvẫn cóthể kháccall. zaic_tools/utils.py:canon bỏfree-textcontent/title/label/note/location; khácrawstate hoặcwording khôngtựchứngminh state_hashkhác. Khôngsửa metric,gold,comment hayverdict.',
    'Giới hạn: chỉ điều tra trace/code, không replay hay ngheaudio. Kếtluận chỉphầnD04, khôngxóalỗichínhhoặcphụkhác. Dropdown chungchưacóloại mặcđịnhtươngđương; dùngnhómnguyênnhânD04đểlọc, khôngdiễngiải insufficientlàchưađọctrace.'])
  payload={'analysis_key':data['feedback_key'],'conclusion':old.get('conclusion')or('model'if r['primary_group'].startswith('M')else'insufficient'),
   'evidence':old.get('evidence','')+('\n\n'if old else'')+block,'replay':old.get('replay','not_run'),
   'replay_notes':old.get('replay_notes','')+('\n\n'if old else'')+'D04: chưa replay. Không cần LLM server để đối chiếu default trong code; mọi thử nghiệm hành vi sau sửa phải có kế hoạch riêng.', 'revision':old.get('revision',0)}
  prepared.append({'sample_id':sid,'cause_group':group,'finding':finding,'prior_investigation':old,'block':block,'payload':payload})
 (OUT/'prepared.json').write_text(json.dumps(prepared,ensure_ascii=False,indent=2),encoding='utf-8')
 saved=[]
 for p in prepared:
  req=urllib.request.Request(BASE+'/api/investigation/'+p['sample_id'],data=json.dumps(p['payload'],ensure_ascii=False).encode(),headers={'Content-Type':'application/json','Origin':BASE},method='PUT')
  with urllib.request.urlopen(req)as response:saved.append({'sample_id':p['sample_id'],**json.load(response)})
  (OUT/'saved.json').write_text(json.dumps(saved,ensure_ascii=False,indent=2),encoding='utf-8')
 causes=json.loads(original[paths[2]]);assert causes['analysis_key']==data['feedback_key'];assert'D04'not in causes['groups']
 causes['groups']['D04']={'names':NAMES,'samples':{p['sample_id']:p['cause_group']for p in prepared}}
 target=Path(paths[2]);tmp=target.with_suffix('.tmp');tmp.write_text(json.dumps(causes,ensure_ascii=False,indent=2),encoding='utf-8');tmp.replace(target)
 after=get('/api/analysis');exported=get('/api/export')
 assert get('/api/reviews')==reviews and exported['analysis_feedback']==before['analysis_feedback']
 for path in paths[:2]:assert Path(path).read_bytes()==original[path]
 assert after['feedback_key']==data['feedback_key']
 assert after['group_causes']['D02']==data['group_causes']['D02']
 for p in prepared:
  a=after['investigations'][p['sample_id']];assert a['evidence']==p['payload']['evidence']and a['conclusion']==p['payload']['conclusion']and a['replay']==p['payload']['replay']
  if p['prior_investigation']:assert a['evidence'].startswith(p['prior_investigation']['evidence']+'\n\n')
 ids={p['sample_id']for p in prepared}
 for sid,old in data['investigations'].items():
  if sid not in ids:assert after['investigations'][sid]==old
 counts=Counter(p['cause_group']for p in prepared)
 check={'saved':len(saved),'primary':sum(r['primary_group']=='D04'for r in rows),'causes':dict(counts),'reviews_unchanged':True,'feedback_unchanged':True,'source_analysis_unchanged':True,'snapshot_unchanged':True,'prior_investigations_preserved':True,'D02_taxonomy_unchanged':True,'replay_run':False,'verified_at':datetime.now(timezone.utc).isoformat()}
 (OUT/'verification.json').write_text(json.dumps(check,indent=2),encoding='utf-8')
 report=['# Điều tra D04 · 2026-11-03','','28 sample liên quan: 14 nhóm chính, 14 nhóm phụ. Không replay, không sửa pipeline/metric/gold; giữ nguyên review, feedback và nội dung điều tra trước.','',
  '## Kết luận','','Mặc định cố định hoặc phụ thuộc state cần phân biệt. Repeatonce/prioritynormal và end+1h có cơ chế rõ. Robot giữ mode trong state trước khi fallbackvacuum. Ngày xổ số không phải mặc địnhtoday: get_results bỏdate là không lọc, check_ticket dùngexactdate. Vì vậy hai case date được tách riêng, chưa sửa phân nhóm gốc.','',
  'Canon bỏ free text (label/title/content/note/location), nên khác wording không tự gây lệchstatehash. Các phát biểu cũ về đổi rawstate được bổ sung giới hạn trong evidence, giữ nguyên quyết định reviewer.','', '## Nhóm nguyên nhân D04','']
 for k,n in counts.most_common():report.append(f'- {NAMES[k]}: {n}.')
 report+=['','## Hướng xử lý, chưa triển khai','','Phân biệt tham số optional hợp lệ với sai nghiệp vụ; không xóa default hàngloạt để khớp reference. Nếu muốn giảm sinh dư có thể bổ sung hướng dẫn bỏ giátrịdefault, nhưng lỗi giờ/người/API/phạmvi phải sửa riêng. Mode phụ thuộcstate không được chuẩn hóa như hằngsố. Date xổsố cần chínhsáchphạmvingày, không gọi làdefault.','','## Từng sample','']
 for p in prepared:report+=['### '+p['sample_id']+' · '+NAMES[p['cause_group']],'',p['block'],'']
 (OUT/'REPORT.md').write_text('\n'.join(report),encoding='utf-8');print(json.dumps(check,ensure_ascii=False))
if __name__=='__main__':main()
