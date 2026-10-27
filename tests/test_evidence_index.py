"""Evidence navigation, completeness and stale-output checks; no financial runs."""
import copy
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

from research.control.evidence_index import REGISTRY, OUTPUTS, build, generate

ROOT = Path(__file__).resolve().parents[1]


class EvidenceIndexTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.source('research/plans/example.json', '{}')
        self.source('docs/tasks/example.md', '# Example\n\n## Lesson\n\nA scoped observation.\n')
        self.source('docs/tasks/evidence/example.json', '{}')
        present = lambda path, kind: dict(state='present', path=path, kind=kind, note='Explicit fixture evidence.')
        self.registry = dict(schema_version=1, updated='2026-10-27', scope='Synthetic index test only.', studies=[
            dict(id='example', title='Example', family='fixture', reported_state='reported only', note='No financial conclusion.',
                 plans=[present('research/plans/example.json', 'plan')],
                 results=[present('docs/tasks/evidence/example.json', 'receipt')],
                 failures=[dict(state='unpublished', note='Raw failures not published; not zero attempts.')],
                 lessons=[present('docs/tasks/example.md#lesson', 'narrative')])])
        self.save_registry()

    def source(self, path, text):
        target = self.root / path
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(text)
        return target

    def save_registry(self):
        self.source(REGISTRY, json.dumps(self.registry))

    def test_actual_repository_generated_views_are_current(self):
        coverage = generate(ROOT)
        self.assertEqual(coverage['unowned_plans'], 0)

    def test_deterministic_generation_and_check_are_read_only(self):
        before = {str(p): hashlib.sha256(p.read_bytes()).hexdigest() for p in self.root.rglob('*') if p.is_file()}
        generate(self.root, write=True)
        first = {name: (self.root / name).read_bytes() for name in OUTPUTS}
        generate(self.root, write=True)
        self.assertEqual(first, {name: (self.root / name).read_bytes() for name in OUTPUTS})
        generate(self.root)
        for path, sha in before.items():
            self.assertEqual(hashlib.sha256(Path(path).read_bytes()).hexdigest(), sha)
        for name in OUTPUTS:
            (self.root / name).unlink()
        with self.assertRaisesRegex(ValueError, 'stale'):
            generate(self.root)
        self.assertFalse(any((self.root / name).exists() for name in OUTPUTS))

    def test_changed_reference_and_generated_tampering_fail_check(self):
        generate(self.root, write=True)
        self.source('docs/tasks/example.md', '# Example\n## Lesson\nChanged source.\n')
        with self.assertRaisesRegex(ValueError, 'stale'):
            generate(self.root)
        generate(self.root, write=True)
        with (self.root / OUTPUTS[1]).open('a') as output:
            output.write('tampered\n')
        with self.assertRaisesRegex(ValueError, 'stale'):
            generate(self.root)

    def test_missing_file_anchor_and_duplicate_reference_reject_before_writes(self):
        for path in ('docs/tasks/missing.md', 'docs/tasks/example.md#missing'):
            self.registry['studies'][0]['lessons'][0]['path'] = path
            self.save_registry()
            with self.assertRaisesRegex(ValueError, 'missing'):
                generate(self.root, write=True)
            self.assertFalse(any((self.root / name).exists() for name in OUTPUTS))
        self.registry['studies'][0]['lessons'] = [dict(state='present', path='docs/tasks/example.md#lesson', kind='narrative', note='Reason.')] * 2
        self.save_registry()
        with self.assertRaisesRegex(ValueError, 'duplicate role reference'):
            build(self.root)

    def test_generated_views_cannot_become_evidence_sources(self):
        generate(self.root, write=True)
        self.registry['studies'][0]['lessons'][0]['path'] = OUTPUTS[1]
        self.save_registry()
        with self.assertRaisesRegex(ValueError, 'cannot be evidence sources'):
            generate(self.root, write=True)

    def test_new_plan_requires_exactly_one_explicit_owner(self):
        self.source('research/plans/new.json', '{}')
        with self.assertRaisesRegex(ValueError, 'unowned'):
            build(self.root)
        (self.root / 'research/plans/new.json').unlink()
        other = copy.deepcopy(self.registry['studies'][0])
        other['id'] = 'other'
        self.registry['studies'].append(other)
        self.save_registry()
        with self.assertRaisesRegex(ValueError, 'multiple study owners'):
            build(self.root)

    def test_duplicate_ids_missing_roles_and_unavailable_reason_fail(self):
        baseline = copy.deepcopy(self.registry)
        mutations = [lambda d: d['studies'].append(copy.deepcopy(d['studies'][0])),
                     lambda d: d['studies'][0].pop('lessons'),
                     lambda d: d['studies'][0].update(failures=[]),
                     lambda d: d['studies'][0]['failures'][0].update(note=''),
                     lambda d: d['studies'][0]['failures'][0].update(path='.local/private.json')]
        for mutate in mutations:
            self.registry = copy.deepcopy(baseline)
            mutate(self.registry)
            self.save_registry()
            with self.assertRaises(ValueError):
                build(self.root)

    def test_private_absolute_external_traversal_and_symlink_paths_rejected(self):
        for path in ('/tmp/file', '../secret', 'docs/../../secret', '.local/secret.json',
                     'https://example.com', 'docs/./tasks/example.md', 'docs/tasks/secret.env'):
            with self.subTest(path=path):
                self.registry['studies'][0]['lessons'][0]['path'] = path
                self.save_registry()
                with self.assertRaises(ValueError):
                    build(self.root)
        with tempfile.TemporaryDirectory() as outside:
            target = Path(outside) / 'outside.md'
            target.write_text('outside')
            (self.root / 'docs/tasks/link.md').symlink_to(target)
            self.registry['studies'][0]['lessons'][0]['path'] = 'docs/tasks/link.md'
            self.save_registry()
            with self.assertRaisesRegex(ValueError, 'symlink'):
                build(self.root)

    def test_local_only_references_do_not_depend_on_local_file_presence(self):
        first = build(self.root)
        self.source('.local/private.json', 'Do not ingest this file.')
        self.assertEqual(first, build(self.root))
        self.assertNotIn('Do not ingest', json.dumps(first))
        self.assertEqual(first['studies'][0]['failures'][0]['state'], 'unpublished')

    def test_new_supporting_record_is_visible_but_not_inferred_as_a_study(self):
        first = build(self.root)
        self.source('docs/tasks/new-infrastructure.md', '# Supporting task\n')
        second = build(self.root)
        self.assertEqual(first['studies'], second['studies'])
        self.assertIn('docs/tasks/new-infrastructure.md', second['supporting_records_unassigned'])

    def test_cli_and_make_check_fail_for_stale_generated_output(self):
        command = self.source('scripts/current/research_index.py', (ROOT / 'scripts/current/research_index.py').read_text())
        self.source('research/control/evidence_index.py', (ROOT / 'research/control/evidence_index.py').read_text())
        self.source('research/__init__.py', '')
        self.source('research/control/__init__.py', '')
        generate(self.root, write=True)
        # A copied generator has identical bytes, and thus the same source identity.
        result = subprocess.run([sys.executable, str(command), '--check'], cwd=self.root,
                                capture_output=True, text=True, timeout=15)
        self.assertEqual(result.returncode, 0, result.stderr)
        with (self.root / OUTPUTS[0]).open('a') as output:
            output.write('tampered')
        result = subprocess.run(['make', '-f', str(ROOT / 'Makefile'), 'evidence-index-check',
                                 'PYTHON=' + sys.executable], cwd=self.root,
                                capture_output=True, text=True, timeout=15)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn('index is stale', result.stderr)


if __name__ == '__main__':
    unittest.main()
