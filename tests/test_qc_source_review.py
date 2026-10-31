import unittest
from research.qc_source_review import inspect_html, code_identity, duplicate_groups, rights


class SourceReviewTests(unittest.TestCase):
    def test_embedded_backtest_is_not_code(self):
        result = inspect_html('<iframe src="https://invalid.test/backtest"></iframe>')
        self.assertEqual(result['blocks'], [])
        self.assertEqual(result['iframes'], 1)

    def test_nested_code_preserves_whitespace_once(self):
        result = inspect_html('<pre class="python"><code>def f():\n    return 1\n</code></pre>')
        self.assertEqual(len(result['blocks']), 1)
        self.assertIn('\n    return', result['blocks'][0]['text'])

    def test_constants_and_names_are_not_normalized_away(self):
        self.assertNotEqual(code_identity('x = 1')['ast_sha256'], code_identity('x = 2')['ast_sha256'])
        self.assertNotEqual(code_identity('x = 1')['ast_sha256'], code_identity('y = 1')['ast_sha256'])
        self.assertEqual(code_identity('x = 1 # comment')['ast_sha256'], code_identity('x=1')['ast_sha256'])

    def test_full_class_does_not_prove_complete_package(self):
        result = code_identity('class A(QCAlgorithm):\n def Initialize(self):\n  pass')
        self.assertTrue(result['algorithm_class_candidate'])
        self.assertFalse(result['package_complete'])

    def test_bad_syntax_has_no_ast_identity(self):
        self.assertIsNone(code_identity('if:')['ast_sha256'])

    def test_shared_fragment_is_not_package_duplicate(self):
        block = inspect_html('<pre class="python">def f():\n a = [1,2,3,4,5,6,7,8,9,10]\n b = [1,2,3,4,5,6,7,8,9,10]\n c = a + b\n return c</pre>')['blocks'][0]
        groups = duplicate_groups([{**block, 'id': name, 'path': 'x', 'line': 1} for name in ['a', 'b']])
        self.assertTrue(groups)
        self.assertTrue(all(g['package_equivalence'] == 'unverified' for g in groups))

    def test_code_license_never_confers_data_rights(self):
        self.assertIn('Apache', rights('tutorial')['modification'])
        self.assertIn('separate_license', rights('tutorial')['data_download'])
        self.assertTrue(rights('tutorial')['source_package_export'].startswith('blocked'))
        self.assertEqual(rights('community')['redistribution'], 'unknown')

    def test_margin_declaration_does_not_claim_realized_leverage(self):
        observed = inspect_html('<pre>self.SetBrokerageModel(x, AccountType.Margin)</pre>')['observations']
        self.assertEqual([x['field'] for x in observed], ['margin_account_declaration'])


if __name__ == '__main__':
    unittest.main()
