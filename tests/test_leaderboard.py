"""Published leaderboard preserves aggregate evidence without executing research."""
import json
from pathlib import Path
import re
import unittest

ROOT = Path(__file__).resolve().parents[1]


class LeaderboardTests(unittest.TestCase):
    def rows(self):
        text = (ROOT / 'docs/leaderboard.md').read_text()
        lines = [line for line in text.splitlines() if line.startswith('|')]
        headers = [value.strip() for value in lines[0].strip('|').split('|')]
        return text, [dict(zip(headers, [v.strip() for v in line.strip('|').split('|')]))
                      for line in lines[2:]]

    def test_single_table_first_and_all_saved_metrics_preserved(self):
        text, rows = self.rows()
        self.assertTrue(text.split('# Research leaderboard\n\n', 1)[1].startswith('|'))
        self.assertEqual(len(re.findall(r'^\|\s*---', text, re.M)), 1)
        snapshot = json.loads((ROOT / 'docs/tasks/evidence/2026-10-28-leaderboard-source-catalog.json').read_text())
        keys = ['Algorithm / variant', 'Context', 'Period', 'Outcome', 'CAGR',
                'Max DD', 'Sharpe', 'Calmar', 'Longest underwater sessions / days', 'Lesson']
        self.assertEqual([[row[key] for key in keys] for row in rows],
                         [[row[key] for key in keys] for row in snapshot['entries']])
        identities = [(row['Algorithm / variant'], row['Context']) for row in rows]
        self.assertEqual(len(set(identities)), len(rows))

    def test_missing_metrics_stay_unranked_and_tags_do_not_invert_policy(self):
        _, rows = self.rows()
        missing = [row for row in rows if row['Calmar'] == '—']
        self.assertEqual(len(missing), 4)
        for row in missing:
            self.assertIn(row['Context'], ['GS', 'W1'])
            for key in ['CAGR', 'Max DD', 'Sharpe', 'Calmar', 'Longest underwater sessions / days']:
                self.assertEqual(row[key], '—')
        ungated = next(row for row in rows if row['Algorithm / variant'] == 'Ungated T11')
        self.assertNotIn('risk gate', ungated['Tags'])
        losing = next(row for row in rows if row['Algorithm / variant'] == 'CAPM +1% stop' and row['Context'] == 'F3')
        self.assertEqual(losing['CAGR'], '-51.08%')
        self.assertEqual(losing['Outcome'], 'Negative baseline')
        for row in rows:
            self.assertTrue(row['Tags'] and row['Outcome'] and row['Lesson'])
            links = re.findall(r'\]\(([^)]+)\)', row['Published evidence'])
            self.assertGreaterEqual(len(links), 2)
            for link in links:
                self.assertTrue((ROOT / 'docs' / link).is_file())
