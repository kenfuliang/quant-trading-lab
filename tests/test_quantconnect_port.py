"""Offline state/feature parity only; no AlgorithmImports or cloud calls."""
import ast
from collections import deque
from pathlib import Path
import math
import statistics
import unittest
import pandas as pd
from research.risk_gate import timeline

class QuantConnectPortTests(unittest.TestCase):
    def test_gate_state_and_ema_match_frozen_implementation(self):
        source=Path('research/quantconnect/spy_comparison.py').read_text()
        tree=ast.parse(source)
        core_ast=ast.Module(body=[n for n in tree.body if isinstance(n,ast.ClassDef) and n.name=='GateCore'],type_ignores=[])
        scope=dict(deque=deque,math=math,statistics=statistics)
        exec(compile(core_ast,'gate_core','exec'),scope)
        core=scope['GateCore']()
        # Structural episodes, drawdown, recovery, high vol, and finite warm-up.
        values=[100+i*.03 for i in range(260)]+[110-i*.7 for i in range(60)]+[68+i*.4 for i in range(190)]+[130*(1.07 if i%2 else .93) for i in range(45)]+[135+i*.1 for i in range(220)]
        raw=pd.DataFrame({k:values for k in ('open','high','low','close')},index=pd.bdate_range('2010-01-01',periods=len(values)))
        expected=timeline(raw).shift(-1)
        for i,v in enumerate(values[:-1]):
            core.update(v)
            row=expected.iloc[i]
            self.assertEqual(core.state,row.state)
            self.assertEqual(core.cap,row.cap)
            self.assertEqual(core.red_count,row.red_count)
            self.assertEqual(core.green_count,row.green_count)
            if i>=199:
                self.assertAlmostEqual(core.fast,row.fast,places=10)
                self.assertAlmostEqual(core.slow,row.slow,places=10)
