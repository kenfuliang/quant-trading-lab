import copy
import json
from pathlib import Path
import tempfile
import unittest

from research.catalogue import load_catalogue, validate_catalogue
from research.daily_signals import DEFINITIONS as DAILY
from research.allocation_overlays import DEFINITIONS as ALLOCATION
from research.model_signals import DEFINITIONS as MODEL
from research.overnight_signal import DEFINITIONS as OVERNIGHT
DEFINITIONS = DAILY | ALLOCATION | MODEL | OVERNIGHT


class CatalogueTests(unittest.TestCase):
    def setUp(self):
        self.catalogue = load_catalogue()
        self.entries = {entry['id']: entry for entry in self.catalogue['strategies']}

    def test_preserves_all_100_ideas_and_20_families(self):
        self.assertEqual(set(self.entries), set(range(1, 101)))
        counts = {}
        for entry in self.entries.values():
            counts[entry['family']] = counts.get(entry['family'], 0) + 1
        self.assertEqual(len(counts), 20)
        self.assertEqual(set(counts.values()), {5})
        self.assertEqual(self.entries[100]['name'], 'Machine-learning cross-sectional stock ranking')

    def test_daily_candidates_match_signal_definitions_without_claiming_results(self):
        candidates = {i for i, entry in self.entries.items() if entry['status'] == 'daily_spy_candidate'}
        self.assertEqual(candidates, set(DEFINITIONS))
        for i in candidates:
            self.assertEqual(self.entries[i]['default_parameters'], DEFINITIONS[i][1])
            self.assertTrue(self.entries[i]['implementable_with_saved_spy'])
        self.assertTrue(all(entry['status'] in {'daily_spy_candidate', 'definition_required', 'blocked'} for entry in self.entries.values()))

    def test_non_spy_data_blockers_and_spy_definition_gaps_are_distinct(self):
        for i in (9, 20, 22, 35, 41, 51, 56, 61, 67, 71, 86, 91, 100):
            self.assertEqual(self.entries[i]['status'], 'blocked')
            self.assertFalse(self.entries[i]['implementable_with_saved_spy'])
            self.assertTrue(self.entries[i]['blockers'])
            self.assertTrue(self.entries[i]['required_data'])
        self.assertEqual(self.entries[19]['status'], 'daily_spy_candidate')
        self.assertTrue(self.entries[19]['implementable_with_saved_spy'])
        for i in (31, 32, 33, 34, 98, 99):
            self.assertEqual(self.entries[i]['status'], 'daily_spy_candidate')
            self.assertTrue(self.entries[i]['implementable_with_saved_spy'])

    def test_bad_ids_readiness_and_unresolved_sources_fail_closed(self):
        mutations = [lambda c: c['strategies'][0].update(id=2),
                     lambda c: c['strategies'][0].update(status='deployed'),
                     lambda c: c['strategies'][0].update(source_refs=['missing']),
                     lambda c: c['strategies'][0].update(blockers=[]),
                     lambda c: c['strategies'][90].update(implementable_with_saved_spy=True)]
        for mutate in mutations:
            with self.subTest(mutation=mutate):
                changed = copy.deepcopy(self.catalogue)
                mutate(changed)
                with self.assertRaises(ValueError):
                    validate_catalogue(changed)

    def test_explicit_path_loader_validates(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'catalogue.json'
            path.write_text(json.dumps(self.catalogue))
            self.assertEqual(load_catalogue(path), self.catalogue)
            path.write_text('{"schema_version": 1, "strategies": []}')
            with self.assertRaises(ValueError):
                load_catalogue(path)
