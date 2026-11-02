import importlib.util
import json
from pathlib import Path
import tempfile
import unittest

spec = importlib.util.spec_from_file_location('review_server', Path(__file__).parents[1] / 'scripts/review_server.py')
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


class ReviewTests(unittest.TestCase):
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
