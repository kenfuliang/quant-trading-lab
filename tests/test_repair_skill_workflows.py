"""Discovery contract regression and saved-evidence desk-walkthrough checks.

These verify catalog discovery and the factual inputs used in the recorded skill
walkthroughs. They do not evaluate an LLM's advice or establish financial readiness.
"""
import hashlib
import json
from pathlib import Path
import re
import tempfile
import unittest
from urllib.parse import unquote, urlsplit

from scripts.check_docs import check_skill_catalog

ROOT = Path(__file__).resolve().parents[1]
SKILLS = ('ask-pm', 'trade-research-management', 'trade-stage-development')


class CatalogDiscoveryContractTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        (self.root / 'docs').mkdir()
        self.catalog = self.root / 'docs/skills.md'
        self.skill = self.root / '.agents/skills/ask-pm/SKILL.md'
        self.skill.parent.mkdir(parents=True)
        self.skill.write_text('---\nname: ask-pm\ndescription: PM adviser\n---\n')
        self.entry = '| [ask-pm](../.agents/skills/ask-pm/SKILL.md) | advisory |\n'
        self.catalog.write_text(self.entry)

    def test_installed_and_cataloged_is_discoverable(self):
        self.assertEqual(check_skill_catalog(self.root), [])

    def test_missing_instruction_cannot_be_claimed_installed(self):
        self.skill.unlink()
        self.assertEqual(check_skill_catalog(self.root),
                         ['skills catalog: listed skill is not installed: ask-pm'])

    def test_duplicate_entry_fails_single_owner_discovery(self):
        self.catalog.write_text(self.entry * 2)
        self.assertIn('skills catalog: duplicate entry ask-pm', check_skill_catalog(self.root))

    def test_unlisted_and_wrong_identity_are_detected(self):
        self.catalog.write_text('')
        self.skill.write_text('---\nname: ask-director\n---\n')
        self.assertEqual(set(check_skill_catalog(self.root)), {
            'skills catalog: installed skill is unlisted: ask-pm',
            'skills catalog: folder/frontmatter name mismatch: ask-pm'})


class RecoveredSkillWorkflowTests(unittest.TestCase):
    def test_recovered_skills_only_call_available_local_documents_and_anchors(self):
        for name in SKILLS:
            path = ROOT / '.agents/skills' / name / 'SKILL.md'
            for target in re.findall(r'\[[^\]]*\]\(([^)]+)\)', path.read_text()):
                parsed = urlsplit(target)
                if parsed.scheme or parsed.netloc:
                    continue
                owner = (path.parent / unquote(parsed.path)).resolve()
                with self.subTest(skill=name, target=target):
                    self.assertTrue(owner.is_file())
                    if parsed.fragment:
                        headings = re.findall(r'^#{1,6}\s+(.+)$', owner.read_text(), re.M)
                        anchors = {re.sub(r'[^\w\- ]', '', h.lower()).replace(' ', '-')
                                   for h in headings}
                        self.assertIn(parsed.fragment, anchors)

    def test_pm_closed_epoch_walkthrough_cannot_report_unspent_trials(self):
        receipt = json.loads((ROOT / 'docs/tasks/evidence/2026-10-28-rsi-epoch2-final.json').read_text())
        self.assertEqual(receipt['status'], 'closed-no-qualifying-improvement')
        self.assertFalse(receipt['incumbent_changed'])
        self.assertFalse(receipt['automatic_continuation'])
        self.assertEqual(len(receipt['attempts']), 12)
        self.assertEqual(sum(x['financial_slots'] for x in receipt['attempts']), 12)
        self.assertEqual(receipt['postseal_recovery']['driver_exit'], 1)
        self.assertEqual(receipt['postseal_recovery']['new_financial_launches'], 0)

    def test_management_t11_walkthrough_must_retain_readiness_gaps(self):
        path = ROOT / 'docs/tasks/evidence/2026-10-29-t11-export-validation.json'
        receipt = json.loads(path.read_text())
        for case in receipt['cases'].values():
            comparison = case['legacy_aggregate_comparison']
            self.assertTrue(comparison['aggregate_match'])
            self.assertFalse(comparison['daily_parity'])
            self.assertFalse(comparison['full_reproduction_eligible'])
        self.assertFalse(receipt['paper_ready'])
        self.assertFalse(receipt['cash_position_ledger_reconciled'])

    def test_stage_paper_prototype_walkthrough_not_order_ready(self):
        receipt = json.loads((ROOT / 'docs/tasks/evidence/2026-10-28-t11-paper-preparation.json').read_text())
        self.assertFalse(receipt['native_bridge_verified'])
        self.assertFalse(receipt['qualified_live_signal_producer'])
        self.assertFalse(receipt['order_bearing_cli'])
        self.assertEqual(receipt['paper_orders'], 0)
        self.assertEqual(receipt['financial_runs'], 0)

    def test_walkthrough_receipts_and_recovered_sources_match_provenance(self):
        evidence = json.loads((ROOT / 'docs/tasks/evidence/2026-10-30-skills-recovery.json').read_text())
        for item in evidence['recovered_skills']:
            for field, digest in [('source_path', 'source_sha256'), ('installed_path', 'installed_sha256')]:
                path = ROOT / item[field]
                if field == 'source_path' and not path.exists():
                    # Ignored isolated checkouts are provenance, not CI inputs.
                    continue
                self.assertEqual(hashlib.sha256(path.read_bytes()).hexdigest(), item[digest])
        for item in evidence['walkthroughs']:
            path = ROOT / item['evidence']
            self.assertEqual(hashlib.sha256(path.read_bytes()).hexdigest(), item['evidence_sha256'])


if __name__ == '__main__':
    unittest.main()
