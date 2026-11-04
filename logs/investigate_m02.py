import json, sqlite3, urllib.request
from pathlib import Path
from collections import Counter
from datetime import datetime, timezone

BASE = 'http://127.0.0.1:8765'
OUT = Path('review_data/m02_investigation_20261103')
NAMES = {
 'relation': 'Tự chọn người theo quan hệ hoặc mức độ quen biết suy đoán',
 'first': 'Tự chọn người đầu tiên khi cùng tên',
 'chat': 'Tự gán người vào chat khi chưa có liên kết xác nhận',
 'preference': 'Tự đặt tiêu chí hủy: giá cao hoặc đơn mới nhất',
 'history': 'Chọn một khả năng trong history còn mơ hồ',
 'coverage': 'Bộ lọc tự đặt làm mất ứng viên trước khi lựa chọn',
 'placeholder': 'Dùng giá trị other thay thông tin chưa xác định',
 'wrong_api': 'Sai API trước, rồi tự chọn người nhận chuyển khoản',
 'tie_policy': 'Hai xe đồng giá: khác reference, cần chốt chính sách hòa giá',
}
FINDINGS = {
 '0025': ('relation', 'Search trả hai Minh: c_05 đồng nghiệp và c_08 khách hàng. Reasoning cuối nhận ra hai người nhưng tự bổ sung tiêu chí đồng nghiệp rồi phone.call(c_05) thực sự dialing. User chỉ nói bạn Minh, history rỗng; không có căn cứ loại c_08. Hủy evt_01 có căn cứ mưa, nhưng phần gọi cần sys.ask_missing_info(phone.call, contact_id). Bộ lọc thời tiết/lịch D02 là vấn đề độc lập.'),
 '0074': ('wrong_api', 'Ví 152498 < hóa đơn nước 215000. Sai lệch đầu tiên là đổi bill_payment.pay(source=bank, bill_03) thành banking.transfer. Sau đó reasoning nói chọn beneficiary đầu tiên ben_01, thực tế đây là chủ nhà Phạm Hùng, không phải nhà cung cấp nước. Chuyển khoản đã trừ tiền nhưng không chứng minh bill được thanh toán. Fix ưu tiên chọn đúng API và nhánh điều kiện, không hỏi beneficiary cho một thao tác chuyển khoản vốn không cần có. SMS ở nhánh thiếu ví cũng là lỗi độc lập.'),
 '0245': ('first', 'contacts.search trả c_07 và c_10 đều tên Minh, cùng quan hệ đồng nghiệp. Reasoning nói rõ gọi người đầu tiên; phone.call(c_07) đã dialing. History không xác định Minh nào. Thứ tự kết quả không phải độ tin cậy hay ý định người dùng. Cần ask_missing_info(phone.call, contact_id).'),
 '0265': ('relation', 'Hai Lan c_04 vợ/c_09 đồng nghiệp. Reasoning chọn vợ vì ngữ cảnh gửi file, nhưng gửi file không phân biệt duy nhất hai người. SMS c_04 đã gửi. Cần hỏi contact_id cho sms.send; đồng thời lỗi lọc phòng ngủ làm tắt light_bedroom thay light_bedroom2 là M09 riêng, hỏi người nhận không chữa lỗi thiết bị.'),
 '0350': ('relation', 'Không có history; search trả Lan vợ c_05 và đồng nghiệp c_10. Reasoning dùng giả định thường gọi Lan là vợ, thậm chí nói nếu sai có thể hỏi/gọi người khác sau. phone.call(c_05) đã dialing trước xác nhận. Cần hỏi contact_id trước tác động, không dùng xác suất quan hệ thay ý định user.'),
 '0414': ('relation', 'Hai Lan vợ c_05/đồng nghiệp c_09. Reasoning thừa nhận không có thông tin thêm rồi chọn vợ; sms.send(c_05) thực thi. History về xăng/pizza không định danh Lan. Tắt light_kitchen đúng là tác vụ độc lập; vẫn cần ask_missing_info(sms.send, contact_id) cho tác vụ còn mơ hồ.'),
 '0423': ('relation', 'Forecast rain=false, user nói không mưa thì thôi nên không cần gọi, nhắn hay hỏi Lan trong nhánh này. Agent vẫn tự chọn Lan vợ c_06 giữa hai Lan rồi gửi SMS. M02 là lỗi người nhận của hành động thừa; nguyên nhân sớm hơn M05 là không tôn trọng nhánh dừng, kèm đổi gọi sang SMS. Fix đầu tiên là không phát sinh tác vụ liên lạc khi điều kiện sai; không thêm hỏi Lan một cách máy móc.'),
 '0444': ('relation', 'Hai Bình: c_01 HR và c_02 nhà cung cấp. Không có history phân biệt; reasoning tự đoán HR là liên hệ công việc thường xuyên rồi phone.call(c_01) dialing. Quan hệ có trong kết quả không chứng minh tần suất liên lạc hoặc người user đang tới gặp. Cần hỏi contact_id.'),
 '0605': ('chat', 'Contacts có hai Minh, list_chats cũng có hai chat tên Minh. Reasoning giả sử chat_01 thuộc Minh nhóm Nội dung, trong khi user chỉ nói họp dự án, chưa xác định Nội dung hay Sự kiện. send_message(chat_01) đã thực thi. Cần hỏi chat_id theo reference; việc tìm được contact ID không tự tạo ánh xạ đúng sang chat ID.'),
 '1010': ('preference', 'Hai gói phim Xemflix sub_541 220000 và Vitech sub_3092 110000 đều phù hợp phạm vi. Model nhiều lần nhận ra cần hỏi, cuối cùng tự chọn hủy gói đắt hơn sub_541; không có tiêu chí giá từ user. Hai payload sai gửi subscriptions.list đã được zero-arg normalizer xử lý thành {}, không phải nguyên nhân chọn gói. Cần hỏi subscription_id; độ trễ 176.33s và vòng reasoning dài là vấn đề riêng.'),
 '1169': ('placeholder', 'User cho 40 phút nhưng không cho loại buổi tập. Agent không đọc calendar, nhận thiếu type rồi dùng enum hợp lệ other và ghi workout. Reference đọc lịch thấy yoga 06:30 và bơi 08:00 nên vẫn cần hỏi type. other có nghĩa một loại hoạt động, không phải dấu hiệu dữ liệu chưa biết. Cần đọc nguồn liên quan, còn nhiều khả năng thì ask_missing_info(fitness.log_workout, type), không tự lấp bằng enum.'),
 '1292': ('history', 'User nói cái nồi giao bữa đó; có Bộ nồi inox GST416061720 và Nồi cơm EV602905643 cùng ETA 05/11. Lần track mã GST583920174 không có nguồn trả rỗng; sau phục hồi đọc rộng, agent vẫn tự chọn bộ nồi inox và reschedule. Reference hỏi tracking_id. Ngoài mơ hồ đối tượng còn phải xác minh mốc hôm sau (history hẹn bệnh viện thứ Năm 05/11), không mặc định giữ ngày 05/11. Đừng sửa bằng chọn shipment đầu tiên có chữ nồi.'),
 '1386': ('chat', 'User muốn đặt khám cho Michael Chen; không có tool booking khám. Agent tìm được contact nhưng không tìm thấy chat xác nhận Michael, rồi suy chat_3829 Khách Hàn là nhóm phù hợp và gửi tin. Đây không phải booking thành công; M42 thiếu capability là nguyên nhân sớm, M02 gán người vào nhóm là lỗi tiếp. Cần nêu giới hạn công cụ; chỉ đề xuất phương án liên lạc và xác nhận người nhận nếu user muốn, không tự thay tác vụ. Không suy rằng reference rỗng có nghĩa phải hỏi một tool booking không tồn tại.'),
 '1437': ('history', 'History ghi rõ David Brennan c_7731 missed 09:05 và David Okafor c_2096 missed 11:30, đều sáng nay. User chỉ ông David gọi nhỡ, không họ/công ty/giờ. Model tự rút gọn thành Brennan rồi gọi c_7731. Cả hai đáp ứng mô tả; từ gấp không phân biệt. Cần ask_missing_info(phone.call, contact_id); có ID hợp lệ trong history chưa đủ xác định đúng ý định.'),
 '1449': ('coverage', 'History đón Kevin Park 08:00 và route 15 phút => rời nhà 07:45. Agent tự lọc appliances.list(type=washer), chỉ thấy appl_663 hẹn 07:50 rồi stop. Dữ liệu reference còn dishwasher appl_977 08:15 cũng sau lúc rời, rice cooker 07:30 không phù hợp. Một kết quả sau lọc không đồng nghĩa một ứng viên trên toàn phạm vi. Cần list không lọc loại, tính mốc đúng và hỏi appliance_id khi còn hai máy. M18 mốc thời gian là vấn đề liên quan.'),
 '1499': ('preference', 'Hai đơn về cùng địa chỉ nhà: ord_5813 20:05 và ord_2207 20:12; agent loại đơn trường là đúng, nhưng tự hủy ord_2207 vì mới nhất. User chưa đưa tiêu chí mới nhất. limit=5 của order_history bị runtime bỏ qua, kết quả vẫn chứa cả hai đơn; lỗi không do thiếu dữ liệu vì limit. Cần ask_missing_info(food_delivery.cancel_order, order_id).'),
 '1537': ('history', 'History có hai chuyến cùng Ryan Fordham tại Đà Nẵng 03/10 và 10/10; Ryan Ford ở Đồng Nai là người khác. Số 730561 có căn cứ nhưng ngày không duy nhất. Model tự chọn 10/10, còn dùng Ryan Fordham làm province, lặp payload hai lần và nhận done=false. Cần hỏi date; province phải lấy từ địa điểm có căn cứ, không tên người. Sai province và lặp no-op là lỗi độc lập, không được diễn giải ok=true thành dò thành công.'),
 '1585': ('relation', '795000/5=159000 đúng. Search Sarah trả Sarah Lâm c_63 và Sarah Phan c_7130, cả hai đồng nghiệp. Model chọn c_63 vì đồng nghiệp/cùng công ty nhưng relation không phân biệt và tool không xác nhận công ty cụ thể. ewallet.transfer(c_63,159000) đã trừ tiền. Cần hỏi contact_id, không sửa bằng thay note hoặc ép query rỗng; query Sarah vẫn giữ hai ứng viên.'),
 '1605': ('history', 'History có Sunrise Fresh Nhật/JPY và Sunrise Foods Đức/EUR; cả hai đã nói khoản cọc 30%. Bên Sunrise không phân biệt công ty nên from_currency chưa xác định. Model tự chọn Nhật, dùng JPN sai mã, thử nhiều cặp rỗng rồi nói không có JPY/VND dù chưa gọi đúng cặp này. Cần hỏi from_currency; sửa JPN thành JPY chỉ sửa mã, chưa giải quyết chọn sai khả năng.'),
 '1712': ('tie_policy', 'Hai xe available bike_953 và bike_377 cùng giá thấp nhất 10000/giờ; xe 8000 không available được loại đúng. Model nhận ra hòa giá rồi reserve bike_953 thành công. Reference đòi hỏi bike_id. Khác case trùng tên người: yêu cầu chiếc rẻ nhất có thể cho phép bất kỳ nghiệm đồng hạng tùy chính sách; chưa kết luận chắc sai nghiệp vụ chỉ từ reference. Cần chốt policy hỏi khi hòa hay cho phép chọn một xe đồng hạng; giữ nguyên comment/verdict và ghi rõ bất đồng này, chưa đổi gold.'),
}

COMMON = '''Cơ chế code: src/lifemate/pydantic_agent.py:validate_catalog_arguments kiểm tra Pydantic, x-one-of và format; x-ref được đưa vào schema nhưng không kiểm chứng ID duy nhất theo ý định người dùng. build_tool_definitions.invoke gọi env ngay sau validate. zaic_tools/executor.py:Simulator.call chỉ chặn lỗi schema; một ID tồn tại có thể được thực thi dù chọn sai người/đối tượng. sys.ask_missing_info đã có trong tool schema của trace và runtime trả waiting_for_user, không phải thiếu tool. Barrier sau write trong run_agent có thể cắt tác vụ tiếp theo, nhưng không phải nguồn sinh ID đoán trước write trong các case này. Đây là lỗ hổng kiểm soát ngữ nghĩa trong pipeline hiện tại, không phải bằng chứng một guard tổng quát có thể tự suy ra đúng mọi ứng viên.

Hướng xử lý đề xuất, chưa triển khai: hướng dẫn rõ khi nào đọc thêm, khi nào cần hỏi; sau các tiêu chí có căn cứ mà còn nhiều ứng viên thì gọi sys.ask_missing_info đúng tool/param, không tự thêm tiêu chí quan hệ/thứ tự/giá/mới nhất. Guard trước write chỉ nên áp dụng theo từng miền với tập ứng viên và nguồn bằng chứng rõ; không dùng quy tắc số kết quả >1 một cách toàn cục. Cho phép context phân biệt duy nhất hợp lệ, không ép hỏi khi tác vụ không được phép xảy ra, không tự thay API hoặc capability thiếu. Giá trị other và ID hợp schema không chứng minh đủ thông tin. Cần replay riêng để xác nhận hiệu quả sau thay đổi; chưa đoán nguyên nhân từ weight/training hay parser khi chưa có bằng chứng.'''

def get(path):
 with urllib.request.urlopen(BASE+path) as r: return json.load(r)

def main():
 OUT.mkdir(exist_ok=True)
 data=get('/api/analysis'); before=get('/api/export'); reviews=get('/api/reviews')
 rows=[r for r in data['records'] if r['primary_group']=='M02' or 'M02' in r['secondary_groups']]
 assert {r['sample_id'] for r in rows} == {'train_'+s for s in FINDINGS}
 paths=[Path('review_data/error_analysis.json'),Path('review_data/snapshot.json'),Path('review_data/group_causes.json')]
 original={str(p):p.read_bytes() for p in paths}
 causes=json.loads(original[str(paths[2])]); assert 'M02' not in causes['groups']
 (OUT/'group_causes_before.json').write_bytes(original[str(paths[2])])
 (OUT/'export_before.json').write_text(json.dumps(before,ensure_ascii=False,indent=2),encoding='utf-8')
 with sqlite3.connect('review_data/reviews.sqlite') as src,sqlite3.connect(OUT/'before.sqlite') as dst: src.backup(dst)
 prepared=[]
 for r in rows:
  sid=r['sample_id']; cause,finding=FINDINGS[sid.split('_')[1]]; old=data['investigations'].get(sid,{})
  assert '[M02 · Điều tra' not in old.get('evidence','')
  review=reviews.get(sid,r['existing_review'])
  block='\n\n'.join(['[M02 · Điều tra từ trace/history/schema/runtime, chưa replay]','Nhóm nguyên nhân M02: '+NAMES[cause],finding,
   'Câu hỏi: '+r['question'],'Comment hiện tại đã đọc, giữ nguyên: '+review.get('comment',''),
   'Execution và node bằng chứng: '+json.dumps(r['executed_tools'],ensure_ascii=False),
   'Reference: '+json.dumps({'calls':r['reference_calls'],'results':r['reference_results']},ensure_ascii=False),
   'History đối chiếu: '+json.dumps(r['history'],ensure_ascii=False),
   'LLM nodes: '+', '.join(n['id'] for n in r['llm_evidence']),COMMON,
   'Giới hạn: kết luận cơ chế quan sát từ trace và code hiện tại; chưa replay, chưa nghe audio. Không thay review, feedback, gold hoặc phân nhóm gốc. Kết luận M02 không xóa các lỗi độc lập trong sample.'])
  payload={'analysis_key':data['feedback_key'],'conclusion':old.get('conclusion') or ('insufficient' if cause=='tie_policy' else 'model'),
   'evidence':old.get('evidence','')+('\n\n' if old else '')+block,'replay':old.get('replay','not_run'),
   'replay_notes':old.get('replay_notes','')+('\n\n' if old else '')+'M02: chưa replay; hướng fix mới là đề xuất, chưa xác nhận bằng chạy model.', 'revision':old.get('revision',0)}
  assert len(payload['evidence'])<=100000
  prepared.append({'sample_id':sid,'cause_group':cause,'finding':finding,'prior_investigation':old,'block':block,'payload':payload})
 (OUT/'prepared.json').write_text(json.dumps(prepared,ensure_ascii=False,indent=2),encoding='utf-8')
 saved=[]
 for p in prepared:
  req=urllib.request.Request(BASE+'/api/investigation/'+p['sample_id'],data=json.dumps(p['payload'],ensure_ascii=False).encode(),headers={'Content-Type':'application/json','Origin':BASE},method='PUT')
  with urllib.request.urlopen(req) as response: saved.append({'sample_id':p['sample_id'],**json.load(response)})
  (OUT/'saved.json').write_text(json.dumps(saved,ensure_ascii=False,indent=2),encoding='utf-8')
 causes['groups']['M02']={'names':NAMES,'samples':{p['sample_id']:p['cause_group'] for p in prepared}}
 tmp=paths[2].with_suffix('.tmp');tmp.write_text(json.dumps(causes,ensure_ascii=False,indent=2),encoding='utf-8');tmp.replace(paths[2])
 after=get('/api/analysis'); exported=get('/api/export')
 assert get('/api/reviews')==reviews and exported['analysis_feedback']==before['analysis_feedback']
 assert after['feedback_key']==data['feedback_key']
 for p in paths[:2]: assert p.read_bytes()==original[str(p)]
 for group,taxonomy in data['group_causes'].items(): assert after['group_causes'][group]==taxonomy
 ids={p['sample_id'] for p in prepared}
 for sid,old in data['investigations'].items():
  if sid not in ids: assert after['investigations'][sid]==old
 for p in prepared:
  actual=after['investigations'][p['sample_id']]
  for field in ['conclusion','evidence','replay','replay_notes']: assert actual[field]==p['payload'][field]
  if p['prior_investigation']: assert actual['evidence'].startswith(p['prior_investigation']['evidence']+'\n\n')
 counts=Counter(p['cause_group'] for p in prepared)
 check={'saved':len(saved),'primary':sum(r['primary_group']=='M02' for r in rows),'causes':dict(counts),'reviews_unchanged':True,'feedback_unchanged':True,'source_analysis_unchanged':True,'snapshot_unchanged':True,'prior_investigations_preserved':True,'prior_taxonomies_unchanged':True,'replay_run':False,'verified_at':datetime.now(timezone.utc).isoformat()}
 (OUT/'verification.json').write_text(json.dumps(check,indent=2),encoding='utf-8')
 report=['# Điều tra M02 · 2026-11-03','',f"20 sample liên quan: {check['primary']} nhóm chính, {20-check['primary']} nhóm phụ. Đọc comment hiện tại, history, reasoning, execution và reference. Chưa replay; giữ nguyên review/feedback và điều tra cũ.",'','## Kết luận','',COMMON,'','Phần lớn model nhận ra mơ hồ nhưng vẫn tự chọn. Không cùng một nguyên nhân duy nhất: có sai API trước lựa chọn, lọc thiếu ứng viên, enum thay thông tin thiếu và hai xe đồng hạng cần chính sách riêng. Không coi mọi ID hợp schema là đã có căn cứ nghiệp vụ.','','## Các nhóm nguyên nhân','']
 for cause,count in counts.most_common(): report.append(f'- {NAMES[cause]}: {count}.')
 report+=['','## Từng sample','']
 for p in prepared: report+=['### '+p['sample_id'],'',p['block'],'']
 (OUT/'REPORT.md').write_text('\n'.join(report),encoding='utf-8')
 print(json.dumps(check,ensure_ascii=False))

if __name__=='__main__':main()
