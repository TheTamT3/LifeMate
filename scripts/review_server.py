"""Offline trace review: python scripts/review_server.py --import-snapshot logs/merge_experiments_snapshot.json."""
import argparse
from contextlib import contextmanager
from datetime import datetime, timezone
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
import io
import hashlib
import json
from pathlib import Path
import sqlite3
import tempfile
from urllib.parse import unquote, urlsplit

ROOT = Path(__file__).resolve().parents[1]
EXPERIMENT = '5d88ade9-1411-4032-9252-81b441078d5c'

class Conflict(Exception): pass

def _analysis_text_fields(value, fields):
    if not isinstance(value,dict): raise ValueError('Invalid analysis object')
    for key in fields:
        if key in value and value[key] is not None and not isinstance(value[key],str):
            raise ValueError('Invalid analysis text field: '+key)

def _analysis_rows(value, key):
    rows=value.get(key,[])
    if not isinstance(rows,list) or any(not isinstance(row,dict) for row in rows):
        raise ValueError('Invalid analysis list: '+key)
    return rows

def load_analysis(path, snapshot_bytes):
    """Read optional local analysis without opening or updating the review store."""
    if not path.exists(): return None
    try:
        value=json.loads(path.read_text(encoding='utf-8'))
        snapshot=json.loads(snapshot_bytes)
        if not isinstance(value,dict): raise ValueError('Expected analysis object')
        if value.get('experiment')!=snapshot['experiment']:
            raise ValueError('Analysis belongs to another experiment')
        if value.get('snapshot_sha256')!=hashlib.sha256(snapshot_bytes).hexdigest():
            raise ValueError('Analysis snapshot differs from the active snapshot')
        groups=value.get('groups')
        if not isinstance(groups,dict) or not groups: raise ValueError('Analysis groups are missing')
        for group in groups.values():
            if not isinstance(group,dict) or any(not isinstance(group.get(k),str) for k in ('name','layer','definition')):
                raise ValueError('Invalid analysis group')
        records=value.get('records')
        if not isinstance(records,list): raise ValueError('Analysis records must be a list')
        known={s['id'] for s in snapshot['samples']}
        seen=set()
        for record in records:
            if not isinstance(record,dict): raise ValueError('Invalid analysis record')
            sid=record.get('sample_id')
            if not isinstance(sid,str) or sid not in known or sid in seen:
                raise ValueError('Unknown or duplicate analysis sample')
            seen.add(sid)
            primary=record.get('primary_group')
            secondary=record.get('secondary_groups')
            if not isinstance(primary,str) or primary not in groups or not isinstance(secondary,list):
                raise ValueError('Invalid analysis group reference')
            if any(not isinstance(g,str) or g not in groups or g==primary for g in secondary) or len(set(secondary))!=len(secondary):
                raise ValueError('Invalid secondary analysis groups')
            # Validate everything rendered as React children or mapped as a list.
            # Invalid local files must report an error, never unmount a dirty review.
            _analysis_text_fields(record,('question','subtype','assessment','confidence',
                'comparison_with_existing_comment','evidence_summary','cause_and_limits',
                'trace_revision','root_id'))
            if record.get('existing_review') is not None:
                _analysis_text_fields(record['existing_review'],('comment','verdict'))
            for node in _analysis_rows(record,'llm_evidence'):
                _analysis_text_fields(node,('id',))
                for part in _analysis_rows(node,'parts'):
                    _analysis_text_fields(part,('part_kind','content','tool_name'))
            for tool in _analysis_rows(record,'executed_tools'):
                _analysis_text_fields(tool,('id','name'))
            for turn in _analysis_rows(record,'history'):
                _analysis_text_fields(turn,('role','audio_text','text'))
        return value
    except (OSError,UnicodeError,TypeError,KeyError,json.JSONDecodeError) as exc:
        raise ValueError('Cannot read analysis data: '+str(exc)) from exc

def validate_source(source):
    expected={'018769bd-b6ea-465f-8a0d-3fd79d38a6b9','99bc0d7b-580d-4e24-889c-582c0662661b'}
    if set(source.get('sources',[]))!=expected:
        raise ValueError('This review workspace is scoped to the approved merged experiment. Use a separate workspace for another experiment.')

class ReviewStore:
    def __init__(self, path):
        self.path=Path(path)
        self.path.parent.mkdir(parents=True,exist_ok=True)
        with self.connect() as db:
            db.execute('CREATE TABLE IF NOT EXISTS reviews (sample TEXT PRIMARY KEY, payload TEXT NOT NULL)')
            db.execute('CREATE TABLE IF NOT EXISTS analysis_feedback (sample TEXT, analysis_key TEXT, payload TEXT NOT NULL, PRIMARY KEY(sample,analysis_key))')

    @contextmanager
    def connect(self):
        db=sqlite3.connect(self.path, timeout=15)
        try:
            with db: yield db
        finally: db.close()

    def all(self):
        with self.connect() as db:
            return {key:json.loads(value) for key,value in db.execute('SELECT sample,payload FROM reviews')}

    def feedback(self, analysis_key):
        with self.connect() as db:
            return {sid:json.loads(payload) for sid,payload in db.execute('SELECT sample,payload FROM analysis_feedback WHERE analysis_key=?',(analysis_key,))}

    def export_feedback(self):
        with self.connect() as db:
            return [{'sample_id':sid,'analysis_key':key,**json.loads(payload)} for sid,key,payload in db.execute('SELECT sample,analysis_key,payload FROM analysis_feedback')]

    def save_feedback(self, sample, analysis_key, value):
        if value.get('status') not in ('unreviewed','agree','disagree','needs_check'): raise ValueError('Invalid feedback status')
        if not isinstance(value.get('note',''),str) or len(value.get('note',''))>100000: raise ValueError('Invalid feedback note')
        with self.connect() as db:
            db.execute('BEGIN IMMEDIATE')
            row=db.execute('SELECT payload FROM analysis_feedback WHERE sample=? AND analysis_key=?',(sample,analysis_key)).fetchone()
            revision=json.loads(row[0])['revision'] if row else 0
            if value.get('revision',0)!=revision: raise Conflict('Đối chiếu đã thay đổi ở tab khác. Tải lại trang trước khi lưu; hãy sao chép ghi chú đang sửa.')
            payload={'status':value['status'],'note':value.get('note',''),'revision':revision+1,'updated_at':datetime.now(timezone.utc).isoformat()}
            db.execute('INSERT OR REPLACE INTO analysis_feedback VALUES (?,?,?)',(sample,analysis_key,json.dumps(payload,ensure_ascii=False)))
            return payload

    def save(self, sample, value):
        if value.get('status','unreviewed') not in ('unreviewed','reviewing','reviewed'): raise ValueError('Invalid status')
        if not isinstance(value.get('comment',''),str) or len(value.get('comment',''))>100000: raise ValueError('Invalid comment')
        if not isinstance(value.get('tags',[]),list) or any(not isinstance(t,str) for t in value.get('tags',[])): raise ValueError('Invalid tags')
        if value.get('verdict','Chưa kết luận') not in ('Chưa kết luận','Agent đúng','Agent sai','Label có vấn đề','Chưa đủ dữ liệu'): raise ValueError('Invalid verdict')
        with self.connect() as db:
            db.execute('BEGIN IMMEDIATE')
            row=db.execute('SELECT payload FROM reviews WHERE sample=?',(sample,)).fetchone()
            revision=json.loads(row[0])['revision'] if row else 0
            if value.get('revision',0)!=revision: raise Conflict('Review changed in another tab. Reload before saving.')
            payload={k:value.get(k,default) for k,default in [('status','unreviewed'),('verdict','Chưa kết luận'),('tags',[]),('comment','')]}
            payload.update(revision=revision+1,updated_at=datetime.now(timezone.utc).isoformat())
            db.execute('INSERT OR REPLACE INTO reviews VALUES (?,?)',(sample,json.dumps(payload,ensure_ascii=False)))
            return payload

def safe_audio(dataset, relative):
    audio=(dataset/'audio').resolve()
    target=(dataset/relative).resolve()
    return target if target.is_relative_to(audio) and target.is_file() else None

def build_snapshot(source, dataset):
    labels={s['id']:s for line in (dataset/'train.jsonl').read_text(encoding='utf-8').splitlines() if line.strip() for s in [json.loads(line)]}
    samples=[]
    for root in source['selected']:
        sid=root['inputs']['sample_id']
        if sid not in labels: raise ValueError('Missing dataset sample '+sid)
        nodes=sorted([n for n in source['runs'] if n.get('trace_id')==root.get('trace_id',root['id']) and n['id']!=root['id']],key=lambda n:n.get('start_time',''))
        try: duration=(datetime.fromisoformat(root['end_time'])-datetime.fromisoformat(root['start_time'])).total_seconds()
        except (KeyError,ValueError,TypeError): duration=None
        samples.append({'id':sid,'sample':labels[sid],'root':root,'nodes':nodes,'duration':duration})
    if len({s['id'] for s in samples})!=len(samples): raise ValueError('Duplicate sample IDs')
    return {'experiment':EXPERIMENT,'samples':sorted(samples,key=lambda s:s['id'])}

def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--import-snapshot',type=Path)
    parser.add_argument('--dataset',type=Path,default=ROOT/'train+public_test/train+public_test/train')
    parser.add_argument('--data',type=Path,default=ROOT/'review_data')
    parser.add_argument('--port',type=int,default=8765)
    args=parser.parse_args()
    args.data.mkdir(parents=True,exist_ok=True)
    snapshot=args.data/'snapshot.json'
    if args.import_snapshot:
        source=json.loads(args.import_snapshot.read_text(encoding='utf-8'))
        validate_source(source)
        payload=build_snapshot(source,args.dataset)
        temporary=snapshot.with_suffix('.tmp')
        temporary.write_text(json.dumps(payload,ensure_ascii=False),encoding='utf-8')
        temporary.replace(snapshot)
    if not snapshot.exists(): parser.error('Import a snapshot first with --import-snapshot')
    snapshot_bytes=snapshot.read_bytes()
    data=json.loads(snapshot_bytes)
    samples={s['id']:s for s in data['samples']}
    store=ReviewStore(args.data/'reviews.sqlite')
    dist=ROOT/'review-ui/dist'

    def active_analysis():
        value=load_analysis(args.data/'error_analysis.json',snapshot_bytes)
        if value is not None:
            # Bind feedback to the exact analysis, including its snapshot identity.
            key=hashlib.sha256(json.dumps(value,sort_keys=True,ensure_ascii=False).encode()).hexdigest()
            value['feedback_key']=key
            value['analysis_feedback']=store.feedback(key)
        return value

    class Handler(SimpleHTTPRequestHandler):
        def __init__(self,*a,**kw): super().__init__(*a,directory=str(dist),**kw)
        def log_message(self,*a): pass
        def reply(self,value,status=200):
            body=json.dumps(value,ensure_ascii=False).encode()
            self.send_response(status);self.send_header('Content-Type','application/json; charset=utf-8');self.send_header('Cache-Control','no-store');self.send_header('Content-Length',str(len(body)));self.end_headers();self.wfile.write(body)
        def do_GET(self):
            path=unquote(urlsplit(self.path).path)
            if path=='/api/samples':
                return self.reply({'experiment':data['experiment'],'samples':[{'id':s['id'],'text':s['sample'].get('audio_text',''),'duration':s['duration'],'scores':{k:v.get('avg') for k,v in (s['root'].get('feedback_stats') or {}).items()},'tools':[c['name'] for c in (s['root'].get('outputs') or {}).get('tool_calls',[])],'error':s['root'].get('error')} for s in samples.values()]})
            if path=='/api/reviews': return self.reply(store.all())
            if path=='/api/analysis':
                try: return self.reply(active_analysis())
                except ValueError as exc: return self.reply({'error':str(exc)},422)
            if path=='/api/export': return self.reply({'experiment':data['experiment'],'reviews':store.all(),'analysis_feedback':store.export_feedback()})
            if path=='/api/backup':
                with tempfile.TemporaryDirectory() as tmp:
                    p=Path(tmp)/'backup.sqlite'
                    with store.connect() as src:
                        dst=sqlite3.connect(p)
                        try: src.backup(dst)
                        finally: dst.close()
                    body=p.read_bytes()
                self.send_response(200);self.send_header('Content-Type','application/octet-stream');self.send_header('Content-Disposition','attachment; filename=reviews-backup.sqlite');self.send_header('Content-Length',str(len(body)));self.end_headers();self.wfile.write(body);return
            if path.startswith('/api/sample/'):
                s=samples.get(path.rsplit('/',1)[1])
                return self.reply(s if s else {'error':'Sample not found'},200 if s else 404)
            if path.startswith('/api/audio/'):
                s=samples.get(path.rsplit('/',1)[1]); audio=safe_audio(args.dataset,s['sample'].get('audio','')) if s else None
                if not audio: return self.reply({'error':'Audio unavailable'},404)
                self.send_response(200);self.send_header('Content-Type','audio/wav');self.send_header('Content-Length',str(audio.stat().st_size));self.end_headers()
                with audio.open('rb') as f:
                    import shutil
                    shutil.copyfileobj(f,self.wfile)
                return
            if path.startswith('/api/'): return self.reply({'error':'Not found'},404)
            return super().do_GET()
        def do_PUT(self):
            # Reject browser requests from other origins, even on loopback.
            origin=self.headers.get('Origin')
            if origin and origin not in (f'http://127.0.0.1:{args.port}',f'http://localhost:{args.port}'): return self.reply({'error':'Origin rejected'},403)
            path=unquote(urlsplit(self.path).path)
            feedback=path.startswith('/api/analysis-feedback/')
            sid=path.removeprefix('/api/analysis-feedback/' if feedback else '/api/review/')
            if (not feedback and not path.startswith('/api/review/')) or sid not in samples: return self.reply({'error':'Unknown sample'},404)
            try:
                size=int(self.headers.get('Content-Length','0'))
                if size<1 or size>200000: raise ValueError('Invalid request size')
                value=json.loads(self.rfile.read(size))
                if not isinstance(value,dict): raise ValueError('Expected object')
                if feedback:
                    analysis=active_analysis()
                    if analysis is None or sid not in {r['sample_id'] for r in analysis['records']}: raise ValueError('Sample has no active analysis')
                    if value.get('analysis_key')!=analysis['feedback_key']: raise Conflict('Analysis changed. Reload before saving feedback.')
                    self.reply(store.save_feedback(sid,analysis['feedback_key'],value))
                else:
                    self.reply(store.save(sid,value))
            except Conflict as exc: self.reply({'error':str(exc)},409)
            except (ValueError,TypeError) as exc: self.reply({'error':str(exc)},400)
    print(f'Review ready: http://127.0.0.1:{args.port} · {len(samples)} samples',flush=True)
    ThreadingHTTPServer(('127.0.0.1',args.port),Handler).serve_forever()

if __name__=='__main__': main()
