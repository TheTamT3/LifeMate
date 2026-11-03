import importlib.util
import json
from pathlib import Path
import tempfile
import unittest

spec = importlib.util.spec_from_file_location('review_server', Path(__file__).parents[1] / 'scripts/review_server.py')
server = importlib.util.module_from_spec(spec)
spec.loader.exec_module(server)

class GroupCausesTests(unittest.TestCase):
    def test_scoped_causes_validate_identity_membership_and_taxonomy(self):
        analysis = {'groups': {'D02': {}, 'P01': {}}, 'records': [
            {'sample_id': 'one', 'primary_group': 'D02', 'secondary_groups': []},
            {'sample_id': 'two', 'primary_group': 'P01', 'secondary_groups': []}]}
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / 'group_causes.json'
            self.assertEqual(server.load_group_causes(path, 'key', analysis), {})
            value = {'analysis_key': 'key', 'groups': {'D02': {
                'names': {'scope': 'Scoped read'}, 'samples': {'one': 'scope'}}}}
            path.write_text(json.dumps(value), encoding='utf-8')
            self.assertEqual(server.load_group_causes(path, 'key', analysis), value['groups'])
            for patch in [dict(value, analysis_key='stale'),
                          dict(value, groups={'D02': {'names': {'scope': 'Scoped'}, 'samples': {'two': 'scope'}}}),
                          dict(value, groups={'D02': {'names': {'scope': 'Scoped'}, 'samples': {'one': 'unknown'}}})]:
                path.write_text(json.dumps(patch), encoding='utf-8')
                with self.assertRaises(ValueError): server.load_group_causes(path, 'key', analysis)
