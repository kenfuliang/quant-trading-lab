"""Toy methods only; third-party files are never required or executed in CI."""
import hashlib
from pathlib import Path
import tempfile
import unittest
from research.studies.t11_reproduction.conformance import load_oracle

TOY='''class QuadEnsemble:
    @property
    def _t11_ready(self):
        return True
    def _t11_weights(self):
        return {}
    def _t11_bond_baller(self):
        return 'AAA'
    def _t11_feaver_bear(self):
        return 'BBB'
'''

class TestT11Conformance(unittest.TestCase):
    def test_ignores_module_side_effects_and_checks_source_hash(self):
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)/'toy.py';p.write_text("raise RuntimeError('module must not run')\n"+TOY)
            h=hashlib.sha256(p.read_bytes()).hexdigest();cls=load_oracle(p,h)
            self.assertEqual(cls()._t11_weights(),{})
            with self.assertRaisesRegex(ValueError,'identity'):load_oracle(p,'a'*64)
    def test_rejects_policy_side_effect_calls_and_dunders(self):
        for body in ["return open('/tmp/forbidden')","return self.__class__"]:
            with tempfile.TemporaryDirectory() as d:
                p=Path(d)/'toy.py';p.write_text(TOY.replace('return {}',body))
                with self.assertRaises(ValueError):load_oracle(p,hashlib.sha256(p.read_bytes()).hexdigest())
