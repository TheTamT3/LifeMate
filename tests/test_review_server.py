import importlib.util
import hashlib
import json
from pathlib import Path
import tempfile
import unittest

spec = importlib.util.spec_from_file_location('review_server', Path(__file__).parents[1] / 'scripts/review_server.py')
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


class ReviewTests(unittest.TestCase):
    def test_analysis_feedback_is_separate_versioned_and_conflict_safe(self):
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp)/'review.sqlite'
            store=module.ReviewStore(path)
            store.save('one', {'comment':'original','revision':0})
            before=store.all()
            saved=store.save_feedback('one','analysis-a',{'status':'agree','note':'checked evidence','revision':0})
            self.assertEqual(saved['revision'],1)
            self.assertEqual(module.ReviewStore(path).feedback('analysis-a')['one']['note'],'checked evidence')
            self.assertEqual(store.feedback('analysis-b'),{})
            self.assertEqual(store.all(),before)
            with self.assertRaises(module.Conflict):
                store.save_feedback('one','analysis-a',{'status':'disagree','revision':0})
            for value in ({'status':'invalid'},{'status':'agree','note':[]},{'status':'agree','note':'x'*100001}):
                with self.assertRaises(ValueError): store.save_feedback('one','analysis-b',value)
            saved=store.save_feedback('one','analysis-a',{'status':'unreviewed','note':'reopen','revision':1})
            self.assertEqual(saved['status'],'unreviewed')
            self.assertEqual(len(store.export_feedback()),1)

    def test_analysis_is_optional_and_bound_to_snapshot(self):
        snapshot=json.dumps({'experiment':'approved','samples':[{'id':'one'}]}).encode()
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp)/'error_analysis.json'
            self.assertIsNone(module.load_analysis(path,snapshot))
            value={'experiment':'approved','snapshot_sha256':hashlib.sha256(snapshot).hexdigest(),
                   'groups':{'M01':{'name':'Wrong tool','layer':'model','definition':'Example'}},
                   'records':[{'sample_id':'one','primary_group':'M01','secondary_groups':[]}]}
            path.write_text(json.dumps(value),encoding='utf-8')
            self.assertEqual(module.load_analysis(path,snapshot)['records'][0]['sample_id'],'one')
            original=path.read_bytes()
            self.assertEqual(path.read_bytes(),original)
            for patch in ({'experiment':'foreign'},{'snapshot_sha256':'stale'},
                          {'records':[dict(value['records'][0],sample_id='unknown')]},
                          {'records':value['records']*2},
                          {'records':[dict(value['records'][0],secondary_groups=['bad'])]},
                          {'records':[dict(value['records'][0],llm_evidence={})]},
                          {'records':[dict(value['records'][0],llm_evidence=[{'parts':{}}])]},
                          {'records':[dict(value['records'][0],llm_evidence=[{'parts':[{'content':{}}]}])]},
                          {'records':[dict(value['records'][0],history=[{'text':{}}])]},
                          {'records':[dict(value['records'][0],executed_tools={})]},
                          {'records':[dict(value['records'][0],existing_review={'comment':{}})]},
                          {'records':[dict(value['records'][0],assessment={})]},
                          {'groups':{'M01':None}}):
                path.write_text(json.dumps(value|patch),encoding='utf-8')
                with self.assertRaises(ValueError):module.load_analysis(path,snapshot)

    def test_persistence_and_conflict(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp)/'review.sqlite'
            store = module.ReviewStore(path)
            saved = store.save('one', {'status':'reviewed','verdict':'Agent sai','tags':['Sai tool'],'comment':'test','revision':0})
            self.assertEqual(module.ReviewStore(path).all()['one']['comment'], 'test')
            self.assertEqual(saved['revision'], 1)
            with self.assertRaises(module.Conflict):
                store.save('one', {'revision':0})

    def test_validation(self):
        with tempfile.TemporaryDirectory() as tmp:
            store=module.ReviewStore(Path(tmp)/'db')
            with self.assertRaises(ValueError):
                store.save('one',{'status':'invalid'})

    def test_audio_safety(self):
        with tempfile.TemporaryDirectory() as tmp:
            self.assertIsNone(module.safe_audio(Path(tmp),'../secret.wav'))
            self.assertIsNone(module.safe_audio(Path(tmp),'/secret.wav'))

    def test_reject_foreign_experiment_source(self):
        with self.assertRaises(ValueError):
            module.validate_source({'sources':['foreign-experiment']})
        module.validate_source({'sources':['018769bd-b6ea-465f-8a0d-3fd79d38a6b9','99bc0d7b-580d-4e24-889c-582c0662661b']})

    def test_import_reference_and_reasoning(self):
        with tempfile.TemporaryDirectory() as tmp:
            p=Path(tmp)
            (p/'train.jsonl').write_text(json.dumps({'id':'one','label':{'tool_calls':[]},'audio_text':'hello'})+'\n')
            source={'selected':[{'id':'r','trace_id':'r','inputs':{'sample_id':'one'},'outputs':{},'start_time':'2026-01-01T00:00:00','end_time':'2026-01-01T00:00:02'}], 'runs':[{'id':'a','trace_id':'r','name':'llm','run_type':'llm','outputs':{'response':{'parts':[{'part_kind':'thinking','content':'first'}]}}},{'id':'b','trace_id':'r','name':'llm','run_type':'llm','outputs':{'response':{'parts':[{'part_kind':'thinking','content':'second'}]}}}]}
            result=module.build_snapshot(source,p)
            self.assertEqual(len(result['samples'][0]['nodes']),2)
            self.assertEqual(result['samples'][0]['sample']['audio_text'],'hello')
            self.assertEqual(result['samples'][0]['duration'],2)

if __name__=='__main__': unittest.main()
