"""Mock-only capture guards; actual bounded subprocess proof is run separately."""
from datetime import datetime,timezone,timedelta
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch
from research.studies.sector_rsi import capture as c

class Process:
    pid=4242;returncode=0
    def wait(self,timeout):return self.returncode
    def poll(self):return self.returncode
    def kill(self):self.returncode=-9

class TestSectorRSICapture(unittest.TestCase):
    def plan(self,base,name='proof-a'):
        p=base/(name+'.json');data={'mode':'synthetic','output_root':str(base/name),'journal_root':str(base/'shared-journal'),
            'program_id':name,'cases':['fixture'],'sources':{},'attempt_cap':6,'aggregate_seconds':120,'case_seconds':1,
            'deadline':(datetime.now(timezone.utc)+timedelta(seconds=60)).isoformat(),'shared_context':{'score_version':'fixture','identity':'same'}}
        p.write_text(json.dumps(data));return p,data

    def test_parent_failure_preserved_and_retry_denied(self):
        with tempfile.TemporaryDirectory() as d:
            p,data=self.plan(Path(d))
            with patch.object(c,'verify_plan',return_value=data),patch.object(c.subprocess,'Popen',side_effect=OSError('fixture failure')) as popen:
                result=c.execute(p);self.assertEqual(result['status'],'failed')
                with self.assertRaisesRegex(ValueError,'Failed program'):c.execute(p)
                self.assertEqual(popen.call_count,1)
            receipt=json.loads((Path(data['output_root'])/'final-receipt.json').read_text())
            self.assertEqual(receipt['records'][0]['capture_error_type'],'OSError')
            self.assertEqual(receipt['journal_usage_asof']['attempts'],1)

    def test_unsealed_output_never_relaunches(self):
        with tempfile.TemporaryDirectory() as d:
            p,data=self.plan(Path(d));Path(data['output_root']).mkdir()
            with patch.object(c,'verify_plan',return_value=data),patch.object(c.subprocess,'Popen') as popen:
                with self.assertRaisesRegex(ValueError,'ambiguous'):c.execute(p)
                popen.assert_not_called()

    def test_two_unique_exports_cache_read_only(self):
        with tempfile.TemporaryDirectory() as d:
            base=Path(d);original=c.verify_manifest
            def verify(path):return {} if Path(path).name=='fixture' else original(path)
            outputs=[]
            for name in ('proof-a','proof-b'):
                p,data=self.plan(base,name)
                with patch.object(c,'verify_plan',return_value=data),patch.object(c.subprocess,'Popen',return_value=Process()),patch.object(c,'verify_manifest',side_effect=verify):
                    self.assertEqual(c.execute(p)['status'],'completed')
                    before={str(x):c.sha(x) for x in Path(data['output_root']).rglob('*') if x.is_file()}
                    self.assertEqual(c.execute(p)['new_launches'],0)
                    self.assertEqual(before,{str(x):c.sha(x) for x in Path(data['output_root']).rglob('*') if x.is_file()})
                outputs.append(Path(data['output_root'])/'final-receipt.json')
            self.assertNotEqual(outputs[0],outputs[1]);self.assertNotEqual(c.sha(outputs[0]),c.sha(outputs[1]))

    def test_financial_bounds_cannot_change(self):
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)/'p.json';data={'mode':'financial','python':sys.executable,'python_sha256':c.sha(sys.executable),'sources':{},
                'output_root':str(c.EPOCH_ROOT/'c1/financial'),'journal_root':str(c.FINANCIAL_JOURNAL),'program_id':'calmar-epoch3-c1',
                'cases':c.REGISTERED_CASES['calmar-epoch3-c1'],'attempt_cap':9,'case_seconds':300,'aggregate_seconds':2400,'deadline':c.DEADLINE}
            p.write_text(json.dumps(data))
            with self.assertRaisesRegex(ValueError,'bounds changed'):c.verify_plan(p)

    def test_artifact_tamper_rejected(self):
        with tempfile.TemporaryDirectory() as d:
            p=Path(d);(p/'evidence.txt').write_text('original');c.seal(p,{'fixture':True});c.verify_manifest(p)
            (p/'evidence.txt').write_text('changed')
            with self.assertRaises(ValueError):c.verify_manifest(p)

    def test_both_cycles_share_twelve_slots_and_cannot_relaunch(self):
        with tempfile.TemporaryDirectory() as d:
            base=Path(d);original=c.verify_manifest
            def verify(path):
                return {} if Path(path).parent.name=='cases' else original(path)
            for cycle in ('c1','c2'):
                p,data=self.plan(base,cycle)
                data.update(mode='financial',program_id='calmar-epoch3-'+cycle,
                    cases=c.REGISTERED_CASES['calmar-epoch3-'+cycle],attempt_cap=12,
                    aggregate_seconds=1800,case_seconds=300)
                p.write_text(json.dumps(data))
                with patch.object(c,'verify_plan',return_value=data),patch.object(c.subprocess,'Popen',return_value=Process()) as popen,patch.object(c,'verify_manifest',side_effect=verify):
                    result=c.execute(p)
                    self.assertEqual(result['financial_slots'],6)
                    self.assertEqual(popen.call_count,6)
                    self.assertEqual(c.execute(p)['new_launches'],0)
                    self.assertEqual(popen.call_count,6)
            snapshot=json.loads((base/'shared-journal/snapshot.json').read_text())
            self.assertEqual(len(snapshot['state']['attempts']),12)
            self.assertTrue(all(a['outcome']['status']=='completed' for a in snapshot['state']['attempts'].values()))
