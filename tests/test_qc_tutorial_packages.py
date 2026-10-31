import unittest
from research.qc_tutorial_packages import inspect_python, license_gate, make_archive, archive_inventory

APACHE = b'Apache License\nVersion 2.0'


class TutorialPackageTests(unittest.TestCase):
    def test_repository_visibility_is_not_permission(self):
        self.assertFalse(license_gate(b'class Alpha: pass', b'MIT wrapper license')['permitted'])
        with self.assertRaises(ValueError):
            make_archive({'main.py': b'pass'}, {'permitted': False})

    def test_file_grant_does_not_require_repository_grant(self):
        body = b'# Copyright 2020 QuantConnect\n# Licensed under the Apache License, Version 2.0\nclass A: pass'
        allowed = license_gate(body, APACHE)
        self.assertTrue(allowed['permitted'])
        self.assertEqual(allowed['basis'], 'explicit_file_header')
        self.assertEqual(allowed['data_rights'], 'not_conferred')

    def test_static_inspection_never_executes_top_level_effects(self):
        result = inspect_python(b'import os\nos.chdir("/nonexistent")\nraise RuntimeError("must not run")')
        self.assertEqual(result['syntax'], 'valid')
        self.assertEqual(result['side_effect_or_input_calls'][0]['call'], 'os.chdir')
        self.assertFalse(result['runtime_verified'])

    def test_syntax_and_dependency_unknowns_are_not_runtime_success(self):
        self.assertEqual(inspect_python(b'def f(:')['syntax'], 'invalid')
        result = inspect_python(b'from AlgorithmImports import *\nimport numpy as np\nclass A: ...')
        self.assertIn('AlgorithmImports', result['external_imports'])
        self.assertEqual(result['ellipsis_lines'], [3])
        self.assertFalse(result['runtime_verified'])

    def test_zip_is_reproducible_and_sources_unmodified(self):
        files = {'source/main.py': b'original\r\n', 'LICENSE': APACHE}
        a = make_archive(files, {'permitted': True})
        self.assertEqual(a, make_archive(dict(reversed(list(files.items()))), {'permitted': True}))
        self.assertEqual(next(x['bytes'] for x in archive_inventory(a) if x['path'] == 'source/main.py'), 10)

    def test_archive_rejects_traversal_and_absolute_paths(self):
        for path in ['../main.py', '/main.py', 'source/../../main.py', 'C:/x.py', 'source\\x.py']:
            with self.assertRaises(ValueError):
                make_archive({path: b'pass'}, {'permitted': True})


if __name__ == '__main__':
    unittest.main()
