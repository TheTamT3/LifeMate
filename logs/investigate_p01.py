"""Save authored trace-only investigations; never performs inference or replay."""
import argparse
from collections import Counter
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import sqlite3
import urllib.request

BASE = 'http://127.0.0.1:8765'
OUT = Path('review_data/p01_investigation_20261103')

# Manually assessed first divergence, separately from whether P01 contributes.
FINDINGS = {
 '0052': ('pipeline', 'Báo thức đã tạo; search trả hai Minh nhưng không có lượt xử lý kết quả để hỏi contact_id. Label thêm là sai lệch độc lập, không được giải thích bằng P01.'),
 '0071': ('pipeline', 'Alarm và search Bố cùng thực thi. Thiếu số tiền nên bước hợp lệ tiếp theo là sys.ask_missing_info(amount), không phải chuyển tiền ngay như cách diễn đạt trong comment cũ.'),
 '0103': ('pipeline', 'Search trả hai Minh, alarm cùng response đã tạo; không có lượt tiếp để hỏi contact_id. Label 6 giờ không khớp 6:30 là lỗi khác; thời gian báo thức vẫn 06:30.'),
 '0107': ('model', 'Sai đầu tiên: biết ví 170409 < hóa đơn 223000 nhưng vẫn pay(source=ewallet), done=false. P01 có thể chặn phục hồi sang bank và SMS sau đó; bỏ barrier không sửa được quyết định nguồn tiền đã sai.'),
 '0111': ('model', 'Sai đầu tiên: reminder 14:15 thay vì 13:30 (họp 14:30, xe 13:45). get_quotes chỉ báo giá, chưa đặt xe. Reminder write có thể chặn lượt book tiếp theo; không phải toàn bộ lỗi do pipeline.'),
 '0141': ('model', 'Ví 760779 < 854000 nhưng vẫn pay ewallet và định bù tiền thay vì chọn bank. Pay trả done=false; list_beneficiaries đã chạy sau chuẩn hóa nhưng không thay được thanh toán bill. P01 có thể chặn phục hồi/SMS.'),
 '0162': ('model', 'Chọn alarm.create thay reminders.create trước khi pipeline dừng. Hai Hương được trả về cùng response có alarm write; P01 có thể chặn hỏi người nhận SMS nhưng không gây lỗi chọn artifact.'),
 '0191': ('pipeline', 'Alarm đã tạo, Lan được tìm thấy, chưa có lượt tiếp để hỏi amount. Reasoning đề xuất 100000 không có căn cứ nhưng chưa có transfer thực thi; không ghi nhận đã chuyển sai tiền.'),
 '0214': ('pipeline', 'Đã biết Sếp Dũng c_01, pay bank trả bill paid=true rồi trace kết thúc. Không có sms.send trong raw hoặc execution; cần lượt sau kết quả thanh toán để báo thành công.'),
 '0362': ('model', 'Tạo reminder bán vàng khi chưa đọc giá và chưa kiểm tra điều kiện >121 triệu. Đây là chọn nhánh vô điều kiện trước barrier; P01 chỉ có thể góp phần ngăn các bước còn lại.'),
 '0539': ('pipeline', 'cancel_event thành công và email.list cùng response trả mail_06 từ team@example.test. Không có lượt model tiếp để tạo draft, trong khi reasoning đã dự định bước này. Không được gửi email thật.'),
 '0541': ('model', 'contacts.update lưu 0901234996, thiếu chữ số so với audio_text 09012349996. Không có Zalo xác nhận sau update; P01 có thể chặn bước này, không gây lỗi mã hóa số trước đó.'),
 '0672': ('pipeline', 'History xác định bác sĩ An c_01. Reasoning có gọi rồi tạo ghi chú; chỉ phone.call thực thi, output dialing, không có notes.create hay lượt model sau tool. Không coi dialing là đã hoàn tất cuộc gọi.'),
 '0704': ('model', 'Ngoài start_cycle đúng, model đã sinh list_chores với wrapper arguments không hợp schema rỗng, không có execution list_chores. Lỗi payload xảy ra trước barrier; write start có thể chặn retry/assign Thành. Thiếu validation log nên không khẳng định thông báo lỗi cụ thể.'),
 '0707': ('pipeline', 'create phòng họp 22/10 15:00 thành công; reasoning định tìm/dời lịch nhưng chưa có calendar read/update hay lượt tiếp. Không suy ra rằng model đã chọn sai event khi chưa có lựa chọn đó.'),
 '0782': ('model', 'User chỉ nhờ kiểm tra cửa rồi nhắn nếu mở; model tự set_lock(true). Output vẫn door=open. Hành động thêm là lỗi đầu tiên; P01 chỉ có thể chặn xử lý hai Mai/nhắn tiếp.'),
 '0794': ('pipeline', 'set_lock, acknowledge_alert và contacts.search cùng response đều chạy. Toàn trực ca c_01 đã được trả về, chưa phone.call; bằng chứng cho thấy barrier chặn lượt dùng kết quả search, không chặn các call cùng response.'),
 '0811': ('pipeline', 'music.play và get_status(light) cùng response chạy; đã có light_desk, history có track 42 phút, reasoning tính 20:42. Chưa create_rule và không có lượt sau music write.'),
 '0817': ('model', 'update_event không phục hồi status cancelled, khác yêu cầu tạo lại lịch. Raw list_chats cũng có wrapper sai và không thực thi ở trace cũ. P01 có thể chặn phục hồi/nhắn nhóm nhưng không phải lỗi đầu tiên.'),
 '0827': ('pipeline', 'set_lock(lock_06,true) đúng kho dụng cụ; reasoning định lấy đèn và tạo rule 19:30 nhưng trace dừng sau write. Chưa có get_status/create_rule; chưa chứng minh model sẽ chọn đúng đèn nếu được tiếp tục.'),
 '0830': ('pipeline', 'transfer c_01 6500000 thành công trả tx_01; không có lượt tiếp dùng mã giao dịch để gửi Zalo. Không thể gửi mã thật trước khi nhận kết quả transfer. Ý định giả mã trong reasoning chưa thành hành động thực thi.'),
 '0840': ('pipeline', 'History có Ngân pháp lý c_05 và email; phone.call trả dialing rồi dừng. Reasoning định soạn nháp NDA, chưa email.create_draft. Không còn thiếu địa chỉ để giải thích việc chưa bắt đầu draft.'),
 '0937': ('model', 'Raw subscriptions.list đã được sinh nhưng wrapper arguments sai schema rỗng, không execution; không phải model chưa định gọi. Alarm write có thể chặn retry rồi kiểm tra giá/cancel. Không kết luận phải hủy khi chưa có giá TalkAI.'),
 '0955': ('pipeline', 'Ba call tắt đèn/quạt cùng response đều thành công. Chưa có lượt tiếp tìm task gửi báo cáo và giải quyết trùng tên bằng hỏi thêm. P01 không dừng ngay sau write thứ nhất trong cùng response.'),
 '0957': ('model', 'User đã rút yêu cầu ghi chạy, model vẫn log running 30 phút và tự đặt 18:00. Lỗi hiểu rút lệnh/bịa dữ liệu xảy ra trước barrier; thiếu hỏi steps có thể là hệ quả phụ. Độ trễ 159.36s là vấn đề riêng.'),
 '0969': ('model', 'Raw recent_calls có wrapper sai (tool có optional missed_only nên không thuộc chuẩn hóa zero-arg), raw phone.call cũng thiếu đích. Chỉ delete_rule thực thi. P01 có thể chặn retry; nguyên nhân đầu không phải đơn thuần quên gọi lại.'),
 '0974': ('model', 'User rút yêu cầu nhắn vợ nhưng SMS OTT vẫn được gửi. news.search cùng response trả nhiều bài; P01 có thể chặn chọn/hỏi bài rồi save, không gây ra tin nhắn ngoài yêu cầu đã gửi.'),
 '0975': ('model', 'Đã check táo/dầu ăn nhưng list_events đọc 01/11 thay hôm nay 31/10. Sai ngày xảy ra trước barrier; chưa có lượt sau để phục hồi và tạo lịch đi chợ. Không thể chọn nhánh 08:00/15:00 dựa trên lịch sai ngày.'),
 '0984': ('pipeline', 'stop payload sai đã được chuẩn hóa thành {} và thực thi thành công ở 970920b. Trace dừng trước hỏi rooms/start. Bước hợp lệ tiếp theo là hỏi phòng ngủ cụ thể, không tự chạy cả hai phòng như ý định trong reasoning.'),
 '1011': ('pipeline', 'Hai news.save thành công cùng response đọc calendar không thấy thầy Phong; không có lượt tiếp để chuyển nguồn video_meeting rồi tạo alarm. Sai nguồn đọc là vấn đề đi kèm; chưa có alarm sai giờ thực thi.'),
 '1044': ('pipeline', 'join trả attendees c_188/c_903, search toàn danh bạ cùng response có Nhi c_188, Hằng c_5207, Thư c_741. Chưa lượt model đối chiếu để SMS Hằng/Thư, không cần nhắn Nhi đã có tên.'),
 '1085': ('model', 'Model bịa ride_id=ride_20261129191000; get_ride trả done=false không tìm ID. SMS đúng cùng response kích barrier, có thể chặn tra lại ID thật/cancel. Không quy ID bịa cho pipeline.'),
 '1123': ('pipeline', 'Đã phục hồi truy vấn room rỗng, đọc thấy AC tắt rồi bật cool. Trace dừng sau climate write, còn đổi alarm 06:00 và hỏi channel do hai trận. Tự thêm 26 độ là sai lệch riêng; chưa có hành động chọn sai kênh.'),
 '1158': ('pipeline', 'set_alert300 cùng response đọc steps6340/goal6000 và tasks có task_5521. Dữ liệu đủ xác định nhánh complete nhưng không có lượt dùng kết quả; không phải filter open làm mất task.'),
 '1178': ('insufficient', 'Giữ quyết định reviewer: disagree nghĩa là comment cũ đúng; không tự chốt lại nhánh Sapiens/Nhà giả kim. Comment cũ nói Sapiens đã mượn, nhưng tool result đang lưu có available=true. Cần đối chiếu nguồn trạng thái này. book và library.search cùng response, chưa reserve/lượt model tiếp, nên P01 vẫn là khả năng đóng góp chưa được chốt.'),
 '1200': ('pipeline', 'route walk trả duration_min=25 cùng response enroll(course_277) thành công. Chưa lượt tiếp dùng duration để log_progress25. Reasoning có ý định ghi; không kết luận bỏ barrier chắc chắn đủ để ghi đúng.'),
 '1369': ('model', 'Raw robot.stop có rooms="[]" sai schema rỗng và không execution, bike.reserve đúng. Trace 6db42f8 trước normalizer; không dùng làm bằng chứng fix hiện tại thất bại. P01 có thể chặn retry sau reserve nhưng không tạo ra payload sai ban đầu.'),
 '1595': ('pipeline', 'enroll(course_52) thành công cùng response search trả hai Trang c_949/c_3312. Chưa lượt model tiếp để hỏi contact_id; không được tự chọn một Trang rồi gọi.'),
 '1610': ('model', 'Raw ewallet.transfer(amount=854000,source=bank) sai API và thiếu người nhận, không execution. Chỉ schedule_autopay thực thi; bật autopay không thanh toán bill hiện tại. P01 có thể chặn sửa lời gọi bill_payment.pay, không gây lỗi chọn API ban đầu.'),
 '1638': ('model', 'Reference chỉ yêu cầu reminder và execution reminder đã đúng; giữ verdict cũ Agent đúng theo metric. Phần ngoài reference: model dùng list_restaurants(limit=10) để tìm công thức, sai khả năng tool và payload, không execution. P01 có thể chặn câu giải thích sau reminder nhưng không chứng minh tiếp tục sẽ có công thức. Đây không phải lỗi thiếu tool call chuẩn của benchmark.'),
 '1648': ('model', 'Raw list_meetings có attendees sai schema rỗng, không execution ở 6db42f8; SMS đã gửi dù chưa join. P01 có thể chặn retry/join nhưng lỗi payload có trước; chưa đủ log để xác định chi tiết validation.'),
 '1657': ('model', 'Model gửi lời nhắc tương đối mà chưa đọc notes để tính 08:00, chưa send_location. Thiếu lấy nguồn đã có trước write; barrier có thể ngăn phần share sau tin nhắn. Reasoning không nêu kế hoạch tool share riêng, nên không khẳng định model chắc chắn định gọi.'),
 '1683': ('model', 'save art_3814 đúng; raw list_chats wrapper sai schema rỗng không execution ở 6db42f8. Thiếu Zalo giá9000; P01 có thể chặn retry sau save, nhưng không phải thiếu raw read do pipeline chặn.'),
 '1697': ('model', 'User nói sắp call như bối cảnh, model tự phone.call Andrew; stop có lock_id/locked sai schema rỗng và không execution ở trace cũ. Hai lỗi model độc lập xảy ra trước barrier; P01 chỉ có thể chặn sửa stop.'),
 '1750': ('not_p01', 'Cả hai tool trong reference (alarm.create và news.headlines entertainment) đã thực thi. Chênh lệch tool/state là label thêm, không phải thiếu tool vì P01. Không có lượt sau để đọc nội dung tin là giới hạn trải nghiệm văn bản riêng, chưa chứng minh gây sai benchmark. Không đổi verdict cũ.'),
}

def get(path):
    with urllib.request.urlopen(BASE+path) as response:
        return json.load(response)

def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--save',action='store_true')
    args=parser.parse_args()
    OUT.mkdir(exist_ok=True)
    data=get('/api/analysis')
    records=[r for r in data['records'] if r['primary_group']=='P01' or 'P01' in r['secondary_groups']]
    assert {r['sample_id'] for r in records}=={'train_'+s for s in FINDINGS}
    reviews=get('/api/reviews')
    before_export=get('/api/export')
    source_bytes=Path('review_data/error_analysis.json').read_bytes()
    snapshot_bytes=Path('review_data/snapshot.json').read_bytes()
    prepared=[]
    for r in records:
        sid=r['sample_id']
        conclusion, finding=FINDINGS[sid.split('_')[1]]
        tools=[t['name'].removeprefix('tool.') for t in r.get('executed_tools',[])]
        raw=[[{'tool':p.get('tool_name'),'arguments':p.get('args')} for p in n.get('parts',[]) if p.get('part_kind')=='tool-call'] for n in r.get('llm_evidence',[])]
        lines=['[Codex · Điều tra từ trace, chưa replay]',finding,
            'Bằng chứng đã ghi: '+r['evidence_summary'],
            'Chuỗi execution: '+' → '.join(tools),
            'Các node LLM: '+', '.join(n['id'] for n in r.get('llm_evidence',[])),
            'Code: src/lifemate/pydantic_agent.py:368–373; invoke:235–242. Sau agent_run.next, có call kind != read thì break; không kiểm tra toàn bộ tác vụ hoàn thành hoặc done=false. Các call cùng response vẫn có thể chạy. Điều kiện này có ở cả 6db42f8 và 970920b; trace này ở '+str(r.get('trace_revision'))+'.',
            'Giới hạn: trace không có lượt model sau nhóm tool cuối. Không có stop_reason riêng để chứng minh mọi trường hợp; chưa replay nên không khẳng định model chạy tiếp sẽ hoàn thành đúng. Không dùng reasoning như bằng chứng hành động đã thực thi.']
        if conclusion=='model':
            lines.append('Kết luận dropdown ưu tiên lỗi model đã quan sát trước điểm dừng; không loại trừ P01 là nguyên nhân góp phần thiếu bước/phục hồi.')
        if sid=='train_1178':
            assert data['analysis_feedback'][sid]['status']=='disagree'
            lines.append('Giữ nguyên feedback disagree và comment cũ; mâu thuẫn available được ghi để điều tra, không ghi đè quyết định reviewer.')
        replay='Chưa chạy theo yêu cầu. Cần kiểm chứng giả thuyết và các bước còn thiếu ở trên; chỉ tiếp tục trong simulator, theo dõi hành động lặp/thừa và không suy ra kết quả từ reasoning.'
        if conclusion=='model': replay+=' Khi kiểm tra P01 sau này phải tách lỗi model có trước khỏi tác động của barrier.'
        if conclusion=='not_p01': replay='Chưa chạy. Không ưu tiên replay P01 cho sai lệch benchmark này; nếu đánh giá trải nghiệm đọc tin, cần kiểm tra lượt trả lời sau tool riêng.'
        if conclusion=='insufficient': replay='Chưa chạy. Trước hết đối chiếu trạng thái sách với comment reviewer; không tự đảo quyết định disagree đã chốt.'
        old=data.get('investigations',{}).get(sid)
        # Never overwrite a human investigation implicitly.
        if old: raise RuntimeError('Existing investigation: '+sid)
        prepared.append({'sample_id':sid,'primary_group':r['primary_group'],'analysis_key':data['feedback_key'],
             'conclusion':conclusion,'evidence':'\n\n'.join(lines),'replay':'not_run','replay_notes':replay,'revision':0,
             'raw_calls':raw,'original_review':reviews.get(sid),'original_feedback':data['analysis_feedback'].get(sid)})
    (OUT/'prepared.json').write_text(json.dumps(prepared,ensure_ascii=False,indent=2),encoding='utf-8')
    print('Prepared',len(prepared),dict(Counter(p['conclusion'] for p in prepared)))
    if not args.save: return
    # Backup is completed before the first authorized API write.
    with sqlite3.connect('review_data/reviews.sqlite') as source, sqlite3.connect(OUT/'before.sqlite') as dest:
        source.backup(dest)
    results=[]
    for p in prepared:
        payload={k:p[k] for k in ('analysis_key','conclusion','evidence','replay','replay_notes','revision')}
        request=urllib.request.Request(BASE+'/api/investigation/'+p['sample_id'],data=json.dumps(payload,ensure_ascii=False).encode(),headers={'Content-Type':'application/json'},method='PUT')
        with urllib.request.urlopen(request) as response:
            results.append({'sample_id':p['sample_id'],**json.load(response)})
        (OUT/'saved.json').write_text(json.dumps(results,ensure_ascii=False,indent=2),encoding='utf-8')
    after=get('/api/analysis'); exported=get('/api/export')
    assert get('/api/reviews')==reviews
    assert exported['analysis_feedback']==before_export['analysis_feedback']
    assert Path('review_data/error_analysis.json').read_bytes()==source_bytes
    assert Path('review_data/snapshot.json').read_bytes()==snapshot_bytes
    for p in prepared:
        actual=after['investigations'][p['sample_id']]
        assert actual['evidence']==p['evidence'] and actual['replay']=='not_run'
    check={'saved':len(results),'replay_run':False,'counts':dict(Counter(p['conclusion'] for p in prepared)),
        'reviews_unchanged':True,'feedback_unchanged':True,'source_analysis_unchanged':True,'snapshot_unchanged':True,
        'analysis_key':after['feedback_key'],'snapshot_sha256':hashlib.sha256(snapshot_bytes).hexdigest(),
        'verified_at':datetime.now(timezone.utc).isoformat()}
    (OUT/'verification.json').write_text(json.dumps(check,indent=2),encoding='utf-8')
    report=['# Điều tra P01 từ trace · 2026-11-03','',
        'Phạm vi: 45 sample liên quan (22 nhóm chính, 23 nhóm phụ). Chưa replay, không chạy inference, không sửa pipeline.',
        'Đã lưu riêng qua API investigation; giữ nguyên review, feedback, snapshot và phân nhóm gốc.',
        '', '## Kết quả','',
        '21 nghi do pipeline; 22 ưu tiên lỗi model có trước (có thể kèm P01); 1 không phải nguyên nhân sai benchmark; 1 cần đối chiếu thêm.',
        '', '## Cơ chế chung','',
        '`run_agent` kiểm tra các call mới sau mỗi lần advance node; chỉ cần một kind khác read thì thoát. Điều kiện không dựa vào số ý đã hoàn thành hay done=false. `invoke` ghi call sau env.call, ngay cả khi kết quả nghiệp vụ done=false. Các call cùng response vẫn chạy; model không được lượt tiếp để xử lý kết quả mới. Cả hai revision trace đều có điều kiện này.',
        'Đây là bằng chứng code và trace phù hợp giả thuyết; chưa chứng minh bỏ điều kiện dừng sẽ tạo đúng toàn bộ hành động còn lại. Không có stop_reason chi tiết ở từng trace.',
        '', '## Ngoại lệ cần giữ rõ','',
        '- train_1178: giữ feedback disagree, không đảo comment cũ; ghi rõ mâu thuẫn available=true với mô tả Sapiens đã mượn để đối chiếu.',
        '- train_1638: reference reminder đã đúng; lỗi tìm công thức nằm ngoài bộ tool call chuẩn. Giữ verdict Agent đúng cũ.',
        '- train_1750: đủ tool reference; label là nguyên nhân lệch state/tool, chưa phải P01. Thiếu lời đọc tin là tiêu chí trải nghiệm riêng.',
        '- Dropdown chỉ chứa một kết luận; các case nhiều nguyên nhân được mô tả trong bằng chứng, không hiểu model là loại trừ P01.',
        '', '## Từng sample','']
    for p in prepared:
        report.extend(['### '+p['sample_id']+' · '+p['conclusion'], '',p['evidence'],'','Replay: '+p['replay_notes'],''])
    (OUT/'REPORT.md').write_text('\n'.join(report),encoding='utf-8')
    print(json.dumps(check,ensure_ascii=False))

if __name__=='__main__': main()
