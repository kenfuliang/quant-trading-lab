"""Negative architecture fixtures; no importing or executing fixture code."""
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

from scripts.check_boundaries import check

ROOT = Path(__file__).resolve().parents[1]


class DependencyBoundaryTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        (self.root / 'research').mkdir()
        self.manifest = {'protected_files': {}}
        self.write_manifest()

    def write_manifest(self):
        (self.root / 'research/compatibility.json').write_text(json.dumps(self.manifest))

    def source(self, name, text, frozen=False):
        path = self.root / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text)
        if frozen:
            self.manifest['protected_files'][name] = hashlib.sha256(path.read_bytes()).hexdigest()
            self.write_manifest()
        return path

    def messages(self):
        return '\n'.join(check(self.root)[0])

    def test_actual_repository_passes_without_importing_implementation(self):
        self.assertEqual(check(ROOT)[0], [])

    def test_command_to_study_to_policy_to_feature_direction_passes(self):
        self.source('scripts/current/run.py', 'from research.studies.spy import run\n')
        self.source('research/studies/spy/run.py', 'from research.policies import gate\n')
        self.source('research/policies/gate.py', 'from research.features import price\n')
        self.source('research/features/price.py', 'import pandas\n')
        self.assertEqual(self.messages(), '')

    def test_reverse_layer_and_broker_edges_fail(self):
        for target in ('research.evaluation.audit', 'research.control.controller',
                       'research.studies.spy.run', 'paper_trading.node', 'scripts.current.run'):
            with self.subTest(target=target):
                self.source('research/policies/gate.py', f'import {target}\n')
                self.assertIn('policies cannot import', self.messages())

    def test_relative_member_and_function_local_imports_are_checked(self):
        self.source('research/features/price.py', 'def f():\n    from ..evaluation import audit\n')
        self.assertIn('features cannot import research.evaluation', self.messages())
        self.source('research/features/price.py', 'from scripts import helper\n')
        self.assertIn('features cannot import scripts', self.messages())

    def test_literal_dynamic_import_alias_and_nonliteral_loader_fail(self):
        sources = [
            "import importlib as loader\nloader.import_module('scripts.current.run')\n",
            "from importlib import import_module as load\nload('scripts.current.run')\n",
            "__import__('scripts.current.run')\n",
            "from builtins import __import__ as load\nload('scripts.current.run')\n",
            "import importlib\nimportlib.import_module(name)\n",
            "import importlib.util as u\nu.spec_from_file_location('x', path)\n",
            "import runpy\nrunpy.run_path(path)\n",
        ]
        for text in sources:
            with self.subTest(source=text):
                self.source('research/features/price.py', text)
                self.assertTrue(self.messages())

    def test_static_and_literal_dynamic_relative_imports_pass_within_layer(self):
        self.source('research/features/__init__.py', '')
        self.source('research/features/price.py', '')
        self.source('research/features/other.py', "from . import price\nimport importlib\nimportlib.import_module('.price', 'research.features')\n")
        self.assertEqual(self.messages(), '')

    def test_frozen_legacy_edges_are_exempt_but_bytes_are_checked(self):
        path = self.source('research/legacy.py', 'from scripts import old_helper\n', frozen=True)
        self.assertEqual(self.messages(), '')
        path.write_text('changed')
        self.assertIn('frozen source/evidence changed', self.messages())
        path.unlink()
        self.assertIn('frozen source/evidence changed or missing', self.messages())

    def test_current_cannot_import_frozen_code_but_shared_reporting_is_allowed(self):
        self.source('research/legacy.py', 'VALUE = 1\n', frozen=True)
        for text in ('from research import legacy\n', 'import research.legacy\n',
                     "import importlib\nimportlib.import_module('research.legacy')\n"):
            self.source('research/evaluation/audit.py', text)
            self.assertIn('imports frozen implementation research.legacy', self.messages())
        self.source('reporting/annual.py', 'VALUE = 1\n', frozen=True)
        self.source('research/evaluation/audit.py', 'from reporting.annual import VALUE\n')
        self.assertEqual(self.messages(), '')
        self.source('reporting/annual.py', 'from research.evaluation import audit\n', frozen=True)
        self.assertIn('reporting cannot import', self.messages())

    def test_unknown_root_namespace_and_current_flat_module_fail(self):
        self.source('research/new_flat.py', 'VALUE = 1\n')
        self.assertIn('explicit package layer', self.messages())
        (self.root / 'research/new_flat.py').unlink()
        self.source('research/features/price.py', 'import research\n')
        self.assertIn('explicit research layer', self.messages())
        self.source('research/features/price.py', 'from research import *\n')
        self.assertIn('root wildcard', self.messages())

    def test_cycle_and_syntax_error_fail(self):
        self.source('research/policies/a.py', 'from . import b\n')
        self.source('research/policies/b.py', 'from . import a\n')
        self.assertIn('dependency cycle:', self.messages())
        self.source('research/policies/b.py', 'not valid python !\n')
        self.assertIn('invalid Python', self.messages())

    def test_missing_manifest_fails(self):
        (self.root / 'research/compatibility.json').unlink()
        self.assertIn('missing frozen-source manifest', self.messages())

    def test_make_ci_target_exits_nonzero_for_injected_reverse_import(self):
        self.source('scripts/check_boundaries.py', (ROOT / 'scripts/check_boundaries.py').read_text())
        self.source('research/features/price.py', 'from scripts import forbidden\n')
        result = subprocess.run(['make', '-f', str(ROOT / 'Makefile'), 'boundaries-check',
                                 'PYTHON=' + sys.executable], cwd=self.root,
                                capture_output=True, text=True, timeout=15)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn('features cannot import scripts', result.stderr)

    def test_checker_cli_works_outside_repository(self):
        result = subprocess.run([sys.executable, str(ROOT / 'scripts/check_boundaries.py')],
                                cwd=self.root, capture_output=True, text=True, timeout=15)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn('Dependency boundary check passed', result.stdout)


if __name__ == '__main__':
    unittest.main()
