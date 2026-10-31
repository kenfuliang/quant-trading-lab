"""Read-only final checks and redacted receipt for the fixed stock risk study."""
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from build_stock_risk import assemble, ROOT, RAW, OUT
from stock_risk_evidence import decode


def digest(path):return hashlib.sha256(path.read_bytes()).hexdigest()


def audit():
    result=assemble()
    plan=json.loads((ROOT/'research/plans/stock-risk-v1.json').read_text())
    ledger=json.loads((RAW/'attempts.json').read_text())
    assert ledger['status']=='closed' and len(ledger['attempts'])<=7
    assert not any(a['status']=='reserved' for a in ledger['attempts'])
    assert len([a for a in ledger['attempts'] if a['status']=='completed-verified'])==5
    assert sum(a['retry'] for a in ledger['attempts'])<=2
    blocked=[a for a in ledger['attempts'] if a['status']=='failed-before-save']
    assert len(blocked)==1 and digest(RAW/'original-source-pre-plain-log.py')==blocked[0]['source_sha256']
    assert json.loads((RAW/'blocked-save-evidence.json').read_text())
    assert datetime.fromisoformat(ledger['closed_utc'])<=datetime.fromisoformat(plan['deadline_utc'])
    for name,h in plan['input_hashes'].items():assert digest(ROOT/name)==h,name
    for case in plan['cases']:
        decoded=decode(json.loads((RAW/f'{case}-terminal-fragments.json').read_text()),case)
        assert decoded==json.loads((RAW/f'{case}-packet.json').read_text())
        assert digest(RAW/f'{case}-source.py')==plan['source_hashes'][case]
    manifest=json.loads((OUT/'manifest.json').read_text())
    for name,h in manifest.items():assert digest(OUT/name)==h,name
    assert json.loads((OUT/'comparison.json').read_text())==result
    restore=json.loads((RAW/'source-restoration.json').read_text())
    assert restore['clipboard_matches'] and restore['sha256']==digest(RAW/'original-project-source.py')
    assert restore['build_verified']
    browser=json.loads((RAW/'browser-check.json').read_text())
    assert browser['status']=='passed' and browser['annual_years']==6 and browser['cases']==5 and browser['monthly_decisions']==360
    assert browser['comparison_sha256']==digest(OUT/'comparison.json')
    assert json.loads((RAW/'browser-verified-comparison.json').read_text())==result
    checks=(RAW/'final-check.log').read_text()
    assert 'Ran 321 tests' in checks and '\nOK\n' in checks
    files=list(RAW.glob('*-packet.json'))+list(RAW.glob('*-terminal-fragments.json'))+list(RAW.glob('*-engine-evidence.json'))+[RAW/'attempts.json',RAW/'source-restoration.json',RAW/'browser-check.json',RAW/'browser-verified-comparison.json',RAW/'blocked-save-evidence.json',RAW/'original-project-source.py',RAW/'original-source-pre-plain-log.py',RAW/'final-check.log']
    code=['scripts/prepare_stock_risk.py','scripts/stock_risk_evidence.py','scripts/build_stock_risk.py','scripts/audit_stock_risk.py','research/quantconnect/stock_risk_policy.py','research/plans/stock-risk-v1.json','tests/test_stock_risk.py','docs/tasks/2026-10-26-stock-risk-ablation.md']
    receipt=dict(study='stock-risk-v1',status='complete-scoped-development',verified_utc=datetime.now(timezone.utc).isoformat(),attempts=ledger['attempts'],validation=dict(offline='make check exit0;321 tests',browser=browser,restoration=restore,checks=result['checks']),limits=result['limits'],source_hashes=plan['source_hashes'],code_hashes={x:digest(ROOT/x) for x in code},raw_evidence_hashes={p.name:digest(p) for p in files},artifact_hashes=manifest)
    (ROOT/'docs/tasks/evidence/2026-10-26-stock-risk-ablation.json').write_text(json.dumps(receipt,indent=2)+'\n')
    print('PASS: five native cases, source/packet/control/calendar/PnL/annual/browser/restoration/artifact checks;321 tests')


if __name__=='__main__':audit()
