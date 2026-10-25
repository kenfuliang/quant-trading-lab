"""A review page must preserve evidence boundaries and escape supplied content."""
import json
import hashlib
from pathlib import Path
import tempfile
import unittest

from reporting.recursive_research import render, safe_link, register_local_review, restore_review_link


class RecursiveReportingTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.output = Path(self.temporary.name) / 'review'

    def test_empty_bundle_is_explicit_unknown_and_self_contained(self):
        page = render({'schema_version': 1}, self.output).read_text()
        self.assertIn('Unknown — no evidence supplied', page)
        self.assertNotIn('<script src=', page)
        self.assertNotIn('<link ', page)
        self.assertIn('Bounded experiment', page)
        self.assertEqual(sorted(x.name for x in self.output.iterdir()), ['index.html', 'review-bundle.json'])

    def test_escapes_titles_cells_svg_attributes_and_rejects_active_links(self):
        attack = '</script><img src=x onerror=alert(1)>'
        page = render({'schema_version': 1, 'title': attack, 'summary': [attack],
                       'goals': [{'name': attack, 'value': '<b>unsafe</b>'}],
                       'candidates': [{'candidate_id': attack, 'return_pct': 5., 'drawdown_pct': -10.}],
                       'annual': [{'year': '2020" onmouseover="alert(1)', 'candidate_id': attack, 'return_pct': 2.}],
                       'evidence': [{'label': attack, 'url': 'javascript:alert(1)'},
                                    {'label': 'Source', 'url': 'https://example.com/?a="bad"&b=1'}]}, self.output).read_text()
        self.assertNotIn('<img src=x', page)
        self.assertNotIn('href="javascript:', page)
        self.assertIn('&lt;/script&gt;&lt;img', page)
        self.assertIn('a=&quot;bad&quot;&amp;b=1', page)
        self.assertNotIn('data-year="2020" onmouseover=', page)
        self.assertIn('link unavailable or unsupported', page)

    def test_missing_and_nonfinite_ratios_are_unknown_not_zero(self):
        bundle = {'candidates': [{'candidate_id': 'flat', 'return_pct': 0., 'drawdown_pct': 0.,
                                  'calmar': None, 'sharpe': float('nan')}],
                  'annual': [{'year': 2020, 'candidate_id': 'flat', 'return_pct': 0.}]}
        page = render(bundle, self.output).read_text()
        self.assertGreaterEqual(page.count('class="unknown">Unknown'), 2)
        saved = json.loads((self.output / 'review-bundle.json').read_text())
        self.assertIsNone(saved['candidates'][0]['sharpe'])
        self.assertEqual(saved['candidates'][0]['return_pct'], 0.)
        self.assertIn('id="year-filter"', page)
        self.assertIn('data-year="2020"', page)

    def test_nested_metrics_and_annual_are_displayed_without_computation(self):
        bundle = {'candidates': [{'candidate_id': 'ema', 'metrics': {'return_pct': 8.013, 'calmar': .2757},
                                  'annual': [{'year': 2020, 'return_pct': 5.5}]}],
                  'pareto': [{'candidate_id': 'ema', 'status': 'unknown'}],
                  'budgets': {'attempts_used': 4, 'attempts_limit': 12},
                  'decisions': [{'cycle': 'one', 'decision': 'retain tradeoff'}]}
        page = render(bundle, self.output).read_text()
        self.assertIn('8.013', page)
        self.assertIn('5.5', page)
        self.assertIn('retain tradeoff', page)
        self.assertIn('attempts used', page.replace('_', ' '))
        self.assertNotIn('<circle ', page)  # No drawdown supplied; do not invent it.

    def test_cost_contexts_have_separate_plots(self):
        bundle = {'candidates': [{'candidate_id': 'base', 'context': '5bp base', 'return_pct': 5., 'drawdown_pct': -20.},
                                  {'candidate_id': 'stress', 'context': '10bp stress', 'return_pct': 3., 'drawdown_pct': -21.}]}
        page = render(bundle, self.output).read_text()
        self.assertEqual(page.count('<svg '), 2)
        self.assertIn('5bp base', page)
        self.assertIn('10bp stress', page)

    def test_invalid_schema_does_not_create_output(self):
        for bundle in ({'schema_version': 2}, {'candidates': ['bad']}, {'summary': 'not a list'}, {'budgets': []}):
            with self.assertRaises(ValueError):
                render(bundle, self.output)
        self.assertFalse(self.output.exists())

    def test_link_scheme_normalization(self):
        for url in ('javascript:alert(1)', 'data:text/html,evil', '//evil.com', '\\evil.com', 'https:\\evil.com', 'http:\n//evil.com', 'https://['):
            self.assertIsNone(safe_link(url))
        self.assertEqual(safe_link('../evidence/receipt.json'), '../evidence/receipt.json')
        self.assertEqual(safe_link('https://example.com/paper'), 'https://example.com/paper')

    def test_temporal_link_and_gate_content_do_not_execute_supplied_markup(self):
        page=render({'temporal_url':'javascript:alert(1)',
                     'temporal':[{'candidate':'<img src=x onerror=alert(1)>','longest_underwater_sessions':12}],
                     'risk_gates':[{'red':'<script>bad()</script>'}]},self.output).read_text()
        self.assertNotIn('href="javascript:',page)
        self.assertNotIn('<img src=x',page)
        self.assertNotIn('<script>bad()',page)
        self.assertIn('Longest underwater (sessions)',page)

    def _saved_review(self):
        root=Path(self.temporary.name)/'performance';root.mkdir()
        (root/'index.html').write_text('<html><body>Existing reports</body></html>')
        directory=root/'recursive-research'/'fixture';directory.mkdir(parents=True)
        for name in ('index.html','temporal.html','review-bundle.json'):
            (directory/name).write_text('{}' if name.endswith('.json') else '<html>Fixture</html>')
        hashes={p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in directory.iterdir()}
        (directory/'manifest.json').write_text(json.dumps({'artifact_hashes':hashes}))
        return root,directory

    def test_verified_link_survives_home_regeneration_without_duplicates(self):
        root,directory=self._saved_review();register_local_review(root,directory)
        restore_review_link(root)
        self.assertEqual((root/'index.html').read_text().count('id="recursive-research-link"'),1)
        (root/'index.html').write_text('<html><body>Regenerated home</body></html>')
        restore_review_link(root)
        self.assertIn('recursive-research/fixture/index.html',(root/'index.html').read_text())

    def test_tampered_artifact_or_outside_pointer_is_rejected_before_home_change(self):
        root,directory=self._saved_review();register_local_review(root,directory)
        prior=(root/'index.html').read_text()
        (directory/'temporal.html').write_text('Changed')
        with self.assertRaisesRegex(ValueError,'identity changed'):restore_review_link(root)
        self.assertEqual((root/'index.html').read_text(),prior)
        pointer=root/'recursive-research-latest.json';data=json.loads(pointer.read_text());data['directory']='../outside';pointer.write_text(json.dumps(data))
        with self.assertRaisesRegex(ValueError,'inside'):restore_review_link(root)


if __name__ == '__main__':
    unittest.main()
