import copy
import hashlib
import json
from pathlib import Path
import tempfile
import unittest

from research.control.research_management import reconcile


class ResearchManagementTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.reservation = dict(number=1, actor='agent', command=['never-execute'],
                                source_sha256={'policy.py': 'a' * 64},
                                contract_sha256='b' * 64, reserved_utc='2026-10-28T00:00:00Z',
                                financial_launches=0)
        self.result = {**self.reservation, 'status': 'passed', 'exit_code': 0}
        self.write('reservations.jsonl', json.dumps(self.reservation) + '\n')
        self.write('result.json', json.dumps(self.result))
        self.write('lesson.txt', 'Tradeoff retained; no promotion.')
        self.manifest = dict(schema_version=1, program='fixture', items=[dict(
            id='stage', owner='stage-owner', max_commands=1,
            reservations='reservations.jsonl', checks=['result.json'], artifacts={})])
        self.bind()

    def write(self, name, text):
        (self.root / name).write_text(text)

    def bind(self):
        self.manifest['items'][0]['artifacts'] = {
            name: hashlib.sha256((self.root / name).read_bytes()).hexdigest()
            for name in ['reservations.jsonl', 'result.json', 'lesson.txt']}

    def status(self):
        return reconcile(self.root, self.manifest)['items'][0]

    def test_verified_inventory_does_not_execute_or_modify(self):
        before = {p.name: p.read_bytes() for p in self.root.iterdir()}
        result = self.status()
        self.assertEqual(result['evidence_status'], 'verified_declared_evidence')
        self.assertEqual(result['promotion'], 'not assessed')
        self.assertEqual(result['commands_reserved'], 1)
        self.assertEqual(before, {p.name: p.read_bytes() for p in self.root.iterdir()})

    def test_missing_evidence_is_unavailable(self):
        (self.root / 'lesson.txt').unlink()
        self.assertEqual(self.status()['evidence_status'], 'unavailable')

    def test_changed_evidence_fails(self):
        self.write('lesson.txt', 'invented success')
        self.assertEqual(self.status()['evidence_status'], 'failed')

    def test_failed_check_retained_despite_valid_hash(self):
        self.result.update(status='failed', exit_code=1)
        self.write('result.json', json.dumps(self.result)); self.bind()
        self.assertEqual(self.status()['evidence_status'], 'failed')

    def test_unsealed_and_exhausted_reservations_fail(self):
        self.write('reservations.jsonl', '\n'.join(json.dumps(x) for x in
                   [self.reservation, {**self.reservation, 'number': 2}]))
        self.bind()
        self.assertIn('command budget exceeded', self.status()['failures'])
        self.manifest['items'][0]['max_commands'] = 2
        self.assertIn('unsealed or missing launch result', self.status()['failures'])

    def test_context_drift_and_financial_launch_fail(self):
        for change in [{'actor': 'other'}, {'financial_launches': 1}, {'financial_launches': False}]:
            self.write('result.json', json.dumps({**self.result, **change})); self.bind()
            self.assertEqual(self.status()['evidence_status'], 'failed')

    def test_duplicate_work_missing_owner_and_undeclared_check_rejected(self):
        for mutation in ['duplicate', 'owner', 'undeclared']:
            manifest = copy.deepcopy(self.manifest)
            if mutation == 'duplicate': manifest['items'].append(manifest['items'][0])
            elif mutation == 'owner': manifest['items'][0]['owner'] = ''
            else: manifest['items'][0]['checks'] = ['not-declared.json']
            with self.assertRaises(ValueError): reconcile(self.root, manifest)

    def test_path_escape_and_symlink_rejected(self):
        for name in ['../outside', '/tmp/outside', 'link']:
            if name == 'link': (self.root / name).symlink_to(self.root / 'lesson.txt')
            manifest = copy.deepcopy(self.manifest)
            manifest['items'][0]['artifacts'][name] = 'a' * 64
            with self.assertRaises(ValueError): reconcile(self.root, manifest)

    def test_incomplete_or_malformed_context_fails(self):
        for row in [{**self.reservation, 'actor': None}, {'number': 1, 'financial_launches': 0}]:
            self.write('reservations.jsonl', json.dumps(row))
            self.write('result.json', json.dumps({**row, 'status': 'passed', 'exit_code': 0}))
            self.bind()
            self.assertEqual(self.status()['evidence_status'], 'failed')


    def test_boolean_and_float_result_numbers_fail(self):
        for number in [True, 1.0]:
            self.write('result.json', json.dumps({**self.result, 'number': number}))
            self.bind()
            self.assertEqual(self.status()['evidence_status'], 'failed')
