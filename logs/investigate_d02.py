"""Authored D02 trace audit. No inference, simulator calls or pipeline edits."""
import json
import hashlib
import sqlite3
import urllib.request
from pathlib import Path
from collections import Counter
from datetime import datetime, timezone

BASE = 'http://127.0.0.1:8765'
OUT = Path('review_data/d02_investigation_20261103')
APP = 'train+public_test/train+public_test/train/zaic_tools/apps/'
# Each entry is an individual assessment of the additional read arguments.
# These groups describe D02 only, not a replacement for the sample's primary error.
FINDINGS = {
 '0002': ('context', 'location=TP.HCM lấy từ profile.city; forecast đúng 21/11. Text cuối ghi nhầm ngày là lỗi độc lập, không do bộ lọc.'),
 '0017': ('scope', 'channel=S+ Sport đúng yêu cầu. Tv.guide luôn trả channels đầy đủ dù programs bị lọc và rỗng; tune thành công. Không phải zero-argument tool.'),
 '0025': ('scope', 'Ngày 28/11 và Hà Nội đúng phạm vi, evt_01 vẫn được trả về. Sai là tự gọi c_05 khi có hai Minh, không phải bộ lọc lịch/thời tiết.'),
 '0028': ('scope', 'Range 19/11 giữ đúng lịch họp 10:30; alarm 09:30 đúng. Label thêm là khác biệt write độc lập.'),
 '0032': ('scope', 'type=tv giữ bill_03=146000 đúng tiền truyền hình. Note transfer và read contacts thêm phải xét riêng; không quy chúng cho lọc bill.'),
 '0035': ('scope', 'room=phòng khách giữ light_living; tắt đúng đèn. Phòng khác không cần để xử lý yêu cầu này.'),
 '0074': ('scope', 'type=water giữ bill_03=215000. Chuyển khoản cho chủ nhà thay pay bill và SMS sai nhánh xảy ra sau khi đã có đúng dữ liệu.'),
 '0110': ('scope', 'type=electricity giữ bill_02=849000; chuyển đúng mẹ. Note thêm là vấn đề riêng của tham số write.'),
 '0111': ('scope', 'Range hôm nay giữ evt_01 họp 14:30. Reminder14:15 thay13:30 là sai mốc sau read; thiếu book còn liên quan barrier P01.'),
 '0112': ('scope', 'type=internet giữ bill_03=224000, ví613865 đủ và pay thành công. Zeroarg balance được chuẩn hóa không phải filter thất bại.'),
 '0128': ('context', 'Location TP.HCM và range ngày07/11 vẫn cho đủ forecast/lịch đúng. Pickup literal nhà so địa chỉ profile là vấn đề runtime/write riêng.'),
 '0141': ('scope', 'type=electricity trả đúng bill_03=854000; agent biết ví760779 thiếu nhưng vẫn pay ví. Không do filter mất hóa đơn.'),
 '0154': ('context', 'Forecast Hà Nội ngày05/11 và lịch họp15:00 đúng. Pickup nhà và bước SMS còn thiếu không phải hệ quả lọc sai dữ liệu.'),
 '0158': ('scope', 'floor=2 giữ cả quạt và đèn để ghép ngoại lệ theo room, cũng giữ ac_bedroom; thao tác đủ và đúng.'),
 '0159': ('scope', 'floor=2 giữ dữ liệu room phân biệt phòng ngủ/phòng ngủ nhỏ. Agent gộp ngoại lệ sai dù đã thấy hai room khác nhau.'),
 '0184': ('coverage', 'Chia list theo electricity/water/internet/phone thay đọc tất cả. Reference có bill tv nhưng hạn18/11 ngoài5 ngày nên không bỏ khoản hợp lệ ở state này; không bảo đảm bao phủ các state khác.'),
 '0201': ('scope', 'Range10/11 trả họp08:00 đầy đủ. Sau update08:45, alarm07:15 thay07:45 là tính sai, không do read lọc ngày.'),
 '0214': ('scope', 'type=internet giữ bill_01=220000; pay bank thành công. Thiếu SMS sau pay phù hợp P01, bộ lọc không ngăn contact Sếp Dũng.'),
 '0227': ('scope', 'room=phòng khách giữ đèn/AC/quạt off; bật đèn50 và AC26, giữ quạt off đúng yêu cầu.'),
 '0233': ('scope', 'room=phòng ngủ,type=light giữ đúng đèn cần tắt; không cần climate vì không có điều kiện ngoại lệ AC. Sai riêng là gửi cho cả hai Hương.'),
 '0252': ('scope', 'room=phòng khách trả đủ light/ac/fan; đèn30,AC26,quạt off đúng. Không cần đọc phòng khác.'),
 '0264': ('scope', 'room=phòng khách giữ đủ ba thiết bị; đèn40,AC26,quạt giữ off đúng.'),
 '0294': ('scope', 'room=Phòng ngủ được so không phân biệt hoa thường, trả đúng ac_bedroom và đèn. Agent không tắt đèn đã bị user rút yêu cầu; repeat once xét riêng.'),
 '0303': ('scope', 'type=internet giữ bill_01=218000; ví đủ, pay và SMS đúng Sếp Dũng. Cách diễn đạt SMS là khác biệt riêng.'),
 '0319': ('scope', 'floor=2 giữ cả AC và room; nhận đúng ac_bedroom đang cool, giữ light_bedroom và tắt office/bedroom2.'),
 '0326': ('scope', 'Range23/11 giữ evt_02 cà phê14:30; update15:00/end16:00 đúng. Contacts.search là read thêm, không phải read lịch thiếu dữ liệu.'),
 '0329': ('scope', 'room=phòng khách giữ đủ trạng thái; đèn50,AC26,quạt không bật đúng.'),
 '0332': ('scope', 'type=internet giữ bill225000; ví114896 thiếu, cuối cùng pay bank đúng. Bank read thêm và raw zeroarg chuẩn hóa tách riêng.'),
 '0349': ('scope', 'room=phòng khách giữ đủ trạng thái; đèn30,AC26,quạt off đúng.'),
 '0361': ('scope', 'Hai list electricity/internet khớp hai loại user chỉ rõ. Lỗi sau read là đổi chuyển cho beneficiary thành pay trực tiếp và không chọn nguồn tiết kiệm như yêu cầu.'),
 '0381': ('scope', 'Range19/11 giữ đá bóng09:00. Đổi thành08:00 thay10:00 là đảo hướng dịch sau khi đã có dữ liệu đúng.'),
 '0402': ('scope', 'Range21/11 giữ đúng evt_01. Thiếu forecast kiểm điều kiện mưa là thiếu nguồn riêng, không phải list_events mất lịch.'),
 '0405': ('scope', 'floor=2 giữ AC và đèn các phòng, đủ xét ngoại lệ phòng có AC chạy. Hai đèn tắt đúng.'),
 '0414': ('scope', 'type=light giữ light_kitchen đúng. Contacts.search Lan vẫn trả hai người; chọn vợ là lỗi phân giải sau read.'),
 '0423': ('context', 'Location Đà Nẵng đúng profile, forecast rain=false. SMS dù không mưa và tự chọn Lan là lỗi nhánh/người, không phải thêm location.'),
 '0437': ('scope', 'near=Hồ Gươm đúng user nói; search trả thư viện31Tràng Thi. Giữ feedback disagree/comment cũ; motorbike default là bằng chứng kỹ thuật riêng, không tự đổi verdict.'),
 '0503': ('scope', 'query=Dung vẫn trả đủ Dung Mua hàng/Yoga, user đã chỉ phòng. Agent chọn đúng email/chat; không dùng mọi khác biệt lời chào làm lỗi D02.'),
 '0533': ('scope', 'room=phòng khách,type=climate giữ ac_living. Bật heat dù weather31>=20 là sai nhánh model trước write, không thiếu trạng thái do filter.'),
 '0534': ('scope', 'query=Lan trả duy nhấtc_06 có đủ phone/email, final chép đúng. Không bắt buộc get khi search đã đủ.'),
 '0539': ('default', 'email.list(unread_only=false) bằng không lọc trong runtime; mail_06 vẫn trả. Thiếu draft sau cancel phù hợp P01, không do false loại thư.'),
 '0545': ('scope', 'type=dishwasher giữ appl_02 đúng rửa normal; chore_05 giao Khoa đúng. Payload zeroarg chores đã normalize riêng.'),
 '0570': ('scope', 'query=Phượng vẫn trả đủ ops/em họ; user chỉ Vận hành nên chọn chat01/emailops có căn cứ. Wording draft xét riêng.'),
 '0597': ('scope', 'type=tuition đúng history học phí tháng10; bill_04 có đúng tên/khoản2400000, paybank thành công.'),
 '0619': ('broad', 'since30/09 rộng hơn sáng01/10, vẫn giữ alert_02 kho08:47 và chép đúng nguyên văn. Thêm dữ liệu dư, không mất cảnh báo đích trong trace.'),
 '0637': ('scope', 'get_status(room=phòng khách) giữ plug_living; usage72.2>70, ruleoff18:00 đúng. Title khác chữ hoa không là lỗi filter.'),
 '0678': ('window', 'read_chat limit5 thực sự cắt còn5 tin thay default20, nhưng tin nước vào phòng máy chủ vẫn có và gọi đúng số history. Chỉ xác nhận state này, không bảo đảm tin quan trọng luôn trong5tin.'),
 '0692': ('window', 'limit5 không chứng minh là nguyên nhân: sai chat_05 nhóm thay chat_01 Mai Anh xảy ra trước đọc tin. Không chữa nhầm entity bằng tăng limit.'),
 '0704': ('scope', 'appliances.list(type=dishwasher) giữ đúngappl_02. Wrapper list_chores invalid ở6db42f8 và barrier sau start là vấn đề khác, không do list máy bị lọc.'),
 '0789': ('context', 'location=Hồ Tây từ history, Weather fallback về dữ liệu Hà Nội khi địa điểm nhỏ không khớp; rainfalse và không cancel đúng. Không kết luận có dự báo vi khí hậu riêng Hồ Tây.'),
 '0811': ('scope', 'type=light giữ light_desk để tạo rule, output có ID. Thiếu lượt sau music.write phù hợp P01, không phải filter mất đèn.'),
 '0837': ('scope', 'type=electricity trả cả bill kho600000 và nhà847000, còn đủ ứng viên; agent chọn bill kho đúng. Note title rỗng là khác biệt riêng.'),
 '0878': ('scope', 'query=Lan giữ Chị Lan c_04 cùng số điện thoại; ghi chú đủ ba ý. Không có bằng chứng filter loại người cần tìm.'),
 '0943': ('scope', 'query=Lộc bỏ kính ngữ vẫn trả duy nhất Anh Lộc c_821; transfer342000 đúng15lítRON95. Không mất target do query ngắn.'),
 '1044': ('default', 'contacts.search(query="") là không lọc theo App.read contains; trả đủ Nhi/Hằng/Thư. Thiếu SMS saujoin thuộcP01, không phải search rỗng không trả dữ liệu.'),
 '1058': ('scope', 'merchant=VivuFood giữ cả voucher40000hạn04/12 và50000hạn09/12. Chọn đúng voucher nhưng calendar11/12 là sai ngày sau read.'),
 '1122': ('coverage', 'Sáu list theotype thay một list toàn bộ; reference và execution chỉ có washer đang chạy, stop đúngappl_3815. Tốn bước và có rủi ro bỏ loại ngoài danh sách ở state khác.'),
 '1158': ('scope', 'tasks.list(status=open) vẫn trả task_5521 Đi bộ; steps6340>=goal6000. Thiếu complete sau set_alert làP01, không phải lọc mất task.'),
 '1330': ('context', 'location=Cần Thơ đúngprofile, forecast11/12rainfalse; hủy đúngride01 raVựa, không hủyride02. Không thấy lỗi do location.'),
 '1349': ('scope', 'query=Tom Baker giữ đúngc_7714/email. Gửi Gavin và ccTom đúng; alarm label/repeat là khác biệt write riêng.'),
 '1371': ('scope', 'date06/12 bằng hôm nay; get_activity trảgoal8500, set_goal10500 đúng tăng2000. Khi bỏdate runtime lấy ngày mới nhất có record, không mặc định hôm nay; goal_steps lấy từ state toàn cục nên phép tăng mục tiêu không đổi ở case này.'),
 '1373': ('window', 'location Hà Nội đúngprofile; read_chat4417limit5 vẫn có tin NathanReed17:00 đúng, không lẫnReid. Cửa sổ5 chỉ đủ trong dữ liệu này.'),
 '1431': ('scope', 'query=Thảo giữ đúngc_8875; historyKualaLumpur19:30 nên meeting18:30 đúng. Title thêm online xét riêng.'),
 '1499': ('ignored', 'order_history(limit5) không thực sự giới hạn ở runtime: FoodDelivery.order_history nhận **_ rồi đọc toàn bộorders. Hai đơn home vẫn còn; tự hủy mới nhất là lỗi lựa chọn riêng.'),
 '1547': ('ignored', 'order_history(limit10) được schema chấp nhận nhưng runtime bỏ qua, trả toàn bộorders. Thiếu mappingLuminaKitchen cầnlist_restaurants, không do limit cắt mất mapping.'),
 '1556': ('unjustified', 'unread_only=true không được user yêu cầu: mới nhất không đồng nghĩa chưa đọc. Reference toàn bộemail xác nhậnLuckyDrawtuần50mail812 là mới nhất và vẫn được giữ; chưa gây sai vé ở case này nhưng là chiến lược lọc thiếu căn cứ.'),
 '1585': ('scope', 'query=Sarah vẫn trả cảc_63 vàc_7130, đều đồngnghiệp. Tự chọnc_63 vàtransfer là lỗi phân giải, không phải filter giấu ứng viên.'),
 '1629': ('scope', 'program=Sen Air được Loyalty._program hỗ trợ qua merchant duy nhất; get_points và redeem trảprog_5281/rw_07_1 đúngTaipei. Giữ feedbackdisagree/comment cũ, không tự đảo verdict.'),
 '1679': ('context', 'location=Huế đúngprofile, weather trả mưa. Bất đồng về note05 đã có history so haiworkshop toànstate là vấn đề ưu tiên ngữ cảnh, không do lọc thời tiết.'),
}
NAMES = {
 'scope':'Lọc đúng phạm vi, giữ dữ liệu cần thiết',
 'context':'Địa điểm lấy từ profile/history hoặc fallback runtime',
 'default':'Truyền rõ giá trị mặc định hoặc tương đương không lọc',
 'coverage':'Chia nhiều truy vấn, đủ state này nhưng có rủi ro bao phủ',
 'broad':'Mốc lọc rộng hơn yêu cầu, chưa làm sai kết quả',
 'window':'Giới hạn cửa sổ đọc: cần xét tin còn giữ và lỗi độc lập',
 'ignored':'Tham số limit hợp schema nhưng runtime bỏ qua',
 'unjustified':'Bộ lọc thiếu căn cứ dù kết quả case hiện tại vẫn đúng',
}

def get(path):
    with urllib.request.urlopen(BASE+path) as response:
        return json.load(response)

def main():
    OUT.mkdir(exist_ok=True)
    data=get('/api/analysis'); before=get('/api/export'); reviews=get('/api/reviews')
    rows=[r for r in data['records'] if r['primary_group']=='D02' or 'D02' in r['secondary_groups']]
    assert {r['sample_id'] for r in rows}=={'train_'+k for k in FINDINGS}
    source={p:Path(p).read_bytes() for p in ['review_data/error_analysis.json','review_data/snapshot.json']}
    with sqlite3.connect('review_data/reviews.sqlite') as src, sqlite3.connect(OUT/'before.sqlite') as dst:
        src.backup(dst)
    prepared=[]
    for r in rows:
        sid=r['sample_id']; group,finding=FINDINGS[sid.split('_')[1]]
        old=data.get('investigations',{}).get(sid,{})
        assert '[D02 · Điều tra' not in old.get('evidence',''), 'Already audited: '+sid
        # Do not reinterpret prior reviewer disagreement or overwrite P01 attribution.
        conclusion=old.get('conclusion') or ('model' if r['primary_group'].startswith('M') else 'insufficient')
        lines=['[D02 · Điều tra từ trace và code, chưa replay]', 'Nhóm nguyên nhân D02: '+NAMES[group], finding,
          'Đối chiếu sample: '+r['evidence_summary'], 'Nguyên nhân khác và giới hạn: '+r['cause_and_limits'],
          'Comment hiện tại đã đọc: '+reviews.get(sid,r['existing_review']).get('comment',''),
          'Reference: '+json.dumps(r['reference_calls'],ensure_ascii=False),
          'Execution thực tế: '+json.dumps([{'tool':t['name'],'arguments':t['inputs'].get('arguments'),'output':t['outputs'],'node':t['id']} for t in r['executed_tools']],ensure_ascii=False),
          'Node LLM đã đối chiếu: '+', '.join(n['id'] for n in r['llm_evidence']),
          'Code: src/lifemate/agent_evaluation.py:_matches yêu cầu actual.keys()==expected.keys(); tool_call_accuracy là binary full-call-set match local. Thêm khóa optional làm khác call dù schema hợp lệ; không đồng nhất metric local này với F1 của BTC. State hash là kiểm tra riêng, không suy state sai từ tool-call mismatch.',
          'Runtime: '+APP+'base.py:App.read; smart_home.py:get_status; calendar.py:list_events; contacts.py:search; bill_payment.py:list_bills; weather.py:get_current/get_forecast; tv.py:guide. Đã đối chiếu contract của read tương ứng với inputs/outputs và reference_results từng sample.',
          'Giới hạn: không nghe audio, không inference hoặc simulator replay. Bộ lọc đủ ở state đã ghi không chứng minh chiến lược tổng quát an toàn. Không xóa tham số để sửa điểm vì có thể thay đổi dữ liệu trả về và logic chọn đối tượng.']
        if not old and conclusion=='insufficient':
            lines.append('Dropdown hiện tại chưa có giá trị khác reference/không có lỗi bộ lọc. Giữ Chưa đủ bằng chứng theo nghĩa chưa có căn cứ quy lỗi model/pipeline; kết luận D02 cụ thể nằm ở Nhóm nguyên nhân phía trên, không phải chưa đọc trace.')
        if data.get('analysis_feedback',{}).get(sid,{}).get('status')=='disagree':
            lines.append('Giữ nguyên feedback disagree = comment cũ đúng theo quyết định reviewer; bằng chứng kỹ thuật bổ sung không tự đổi comment, verdict hay feedback.')
        block='\n\n'.join(lines)
        payload={'analysis_key':data['feedback_key'],'conclusion':conclusion,
           'evidence':(old.get('evidence','')+'\n\n' if old else '')+block,
           'replay':old.get('replay','not_run'),
           'replay_notes':old.get('replay_notes','')+('\n\n' if old else '')+'D02: chưa replay. Cần chốt chính sách đối chiếu call tương đương và tách lỗi độc lập; chỉ thử đối chứng filter khi có kế hoạch riêng.',
           'revision':old.get('revision',0)}
        prepared.append({'sample_id':sid,'cause_group':group,'finding':finding,'prior_investigation':old,'payload':payload})
    (OUT/'prepared.json').write_text(json.dumps(prepared,ensure_ascii=False,indent=2),encoding='utf-8')
    saved=[]
    for p in prepared:
        req=urllib.request.Request(BASE+'/api/investigation/'+p['sample_id'],data=json.dumps(p['payload'],ensure_ascii=False).encode(),headers={'Content-Type':'application/json','Origin':BASE},method='PUT')
        with urllib.request.urlopen(req) as response:
            saved.append({'sample_id':p['sample_id'],**json.load(response)})
        (OUT/'saved.json').write_text(json.dumps(saved,ensure_ascii=False,indent=2),encoding='utf-8')
    after=get('/api/analysis'); exported=get('/api/export')
    assert get('/api/reviews')==reviews
    assert exported['analysis_feedback']==before['analysis_feedback']
    for path,content in source.items(): assert Path(path).read_bytes()==content
    for p in prepared:
        actual=after['investigations'][p['sample_id']]
        assert actual['evidence']==p['payload']['evidence']
        assert actual['conclusion']==p['payload']['conclusion']
        assert actual['replay']==p['payload']['replay']
        if p['prior_investigation']:
            assert actual['evidence'].startswith(p['prior_investigation']['evidence']+'\n\n')
    ids={p['sample_id'] for p in prepared}
    for sid,old in data.get('investigations',{}).items():
        if sid not in ids: assert after['investigations'][sid]==old
    counts=Counter(p['cause_group'] for p in prepared)
    check={'saved':len(saved),'primary':sum(r['primary_group']=='D02' for r in rows),'causes':dict(counts),
       'appended_to_existing':sum(bool(p['prior_investigation']) for p in prepared),
       'reviews_unchanged':True,'feedback_unchanged':True,'source_analysis_unchanged':True,'snapshot_unchanged':True,
       'previous_investigations_preserved':True,'replay_run':False,'analysis_key':after['feedback_key'],
       'snapshot_sha256':hashlib.sha256(source['review_data/snapshot.json']).hexdigest(),
       'verified_at':datetime.now(timezone.utc).isoformat()}
    (OUT/'verification.json').write_text(json.dumps(check,indent=2),encoding='utf-8')
    report=['# Điều tra D02 · 2026-11-03','','68 sample liên quan: 25 nhóm chính, 43 nhóm phụ. Đọc trace, comment, context/history, raw calls, execution, reference_results và code. Không chạy replay, không sửa pipeline.','',
      '## Cơ chế chung','','Evaluator local so tập khóa arguments, vì vậy bộ lọc optional hợp lệ vẫn có thể làm tool_call_accuracy=0. Đây không tự chứng minh sai nghiệp vụ hoặc sai state. README BTC mô tả F1; báo cáo không gán binary metric local cho scorer BTC.','',
      'Không có một root cause model chung cho cả68case. Các lỗi người/nhánh/API/thời gian/P01 được tách khỏi chênh lệch read. Đặc biệt order_history(limit) bị runtime bỏ qua; unread_only=true không tương đương yêu cầu mới nhất; limit5 có thể cắt lịch sử chat.','',
      '## Phân loại D02','']
    for k,n in counts.most_common(): report.append(f'- {NAMES[k]}: {n} sample.')
    report+=['','## Lưu UI và giới hạn','','Đã bổ sung vào mục Điều tra nguyên nhân. Với sample có P01, append đoạn D02 và giữ nguyên kết luận/replay cũ. Không thay comment/verdict/feedback/phân nhóm. Dropdown hiện chưa có loại chênh reference nên các case không có attribution model/pipeline được giữ insufficient, kèm giải thích rõ trong evidence; bảng trên là phân nhóm D02 chi tiết, không phải số lượng dropdown.','',
      '## Hướng xử lý đề xuất, chưa triển khai','','1. Tách đánh giá semantic/state khỏi call-match local; không sửa gold hoặc xóa tham số hợp lệ hàng loạt.','2. Filter theo scope rõ: giữ room/floor/type/date/query có căn cứ và kiểm đủ dữ liệu ngoại lệ.','3. Không đồng nhất latest với unread; dùng truy vấn đủ rộng cho yêu cầu mới nhất.','4. Hạn chế chia list tùy ý và limit thiếu căn cứ; nếu không tìm được phải mở rộng đọc.','5. Sửa riêng các lỗi model/P01; bỏ filter không sửa tự chọn người, sai nhánh hay sai thời gian.','','## Từng sample','']
    for p in prepared:
        report+=['### '+p['sample_id']+' · '+NAMES[p['cause_group']],'','[D02 · Điều tra'+p['payload']['evidence'].split('[D02 · Điều tra')[-1],'']
    (OUT/'REPORT.md').write_text('\n'.join(report),encoding='utf-8')
    print(json.dumps(check,ensure_ascii=False))

if __name__=='__main__': main()
