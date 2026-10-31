"""Freeze five private same-signal adapters with a shared funded execution policy."""
import ast,hashlib,json,subprocess
from pathlib import Path
from datetime import datetime,timezone,timedelta
ROOT=Path(__file__).resolve().parents[1];RAW=ROOT/'.local/qc504-funded-v1'
CASES=('ensemble','t10','t11','s2','s3')

def adapt(source):
    tree=ast.parse(source);cls=next(n for n in tree.body if isinstance(n,ast.ClassDef))
    for n in ast.walk(tree):
        if isinstance(n,ast.Constant) and n.value=='qc504-ablation-v1':n.value='qc504-funded-v1'
    cls.body=[n for n in cls.body if not(isinstance(n,ast.FunctionDef) and n.name in ('_rebalance','on_data'))]
    cls.body+=ast.parse('''
def on_data(self,data):
    if self.is_warming_up or self._syms['SPY'] not in data.bars:
        return
    self._fund_accrue(data.bars[self._syms['SPY']].time.date())
    self._funded_rebalance()
    self._audit_record(data)
    self._fund_cash=float(self.portfolio.cash)
''').body
    init=next(n for n in cls.body if isinstance(n,ast.FunctionDef) and n.name=='initialize');init.body+=ast.parse('self._fund_initialize()').body
    add=ast.parse((ROOT/'research/quantconnect/qc504_funded_policy.py').read_text())
    for n in add.body:
        if isinstance(n,ast.FunctionDef):n.name='_'+n.name;cls.body.append(n)
    emit=next(n for n in cls.body if isinstance(n,ast.FunctionDef) and n.name=='_audit_emit')
    extra=ast.parse('''
if payload.get('kind')=='annual':
    payload=dict(payload,financing_usd=self._fund_interest_year.get(payload['year'],0.))
if payload.get('kind')=='overall':
    payload=dict(payload,financing_usd=self._fund_interest,debt_calendar_days=self._fund_debt_days,
        sell_batches=self._fund_sell_batches,buy_batches=self._fund_buy_batches,
        wait_sessions=self._fund_wait_sessions,margin_deferrals=self._fund_margin_deferrals,
        cash_clips=self._fund_cash_clipped,pending_orders=len(self.transactions.get_open_orders()),
        submitted_buys=self._fund_submitted_buys,submitted_sells=self._fund_submitted_sells,
        funding_debit_error=self._fund_max_post_debit_error)
if payload.get('kind')=='assets':
    payload=dict(payload,residual_usd=payload['residual_usd']+self._fund_interest)
''').body
    emit.body=extra+emit.body
    # Selected signal/readiness/helper functions must remain exact AST matches.
    old={n.name:ast.dump(n) for n in ast.walk(ast.parse(source)) if isinstance(n,ast.FunctionDef)}
    for n in cls.body:
        if isinstance(n,ast.FunctionDef) and n.name in old and not n.name.startswith('_audit') and n.name not in ('initialize','on_data','on_end_of_algorithm'):
            assert ast.dump(n)==old[n.name],n.name
    return ast.unparse(ast.fix_missing_locations(tree))+'\n'

def prepare():
    RAW.mkdir(parents=True,exist_ok=False);hashes={};inputs={}
    for case in CASES:
        p=ROOT/'.local/qc504-ablation-v1'/f'{case}-source.py';inputs[case]=hashlib.sha256(p.read_bytes()).hexdigest();out=RAW/f'{case}-source.py';out.write_text(adapt(p.read_text()));hashes[case]=hashlib.sha256(out.read_bytes()).hexdigest()
    now=datetime.now(timezone.utc)
    plan=dict(study_id='qc504-funded-v1',status='frozen-before-runs',created_utc=now.isoformat(),deadline_utc=(now+timedelta(minutes=45)).isoformat(),cases=list(CASES),max_financial_attempts=7,max_unique_cases=5,technical_repair_slots=2,source_hashes=hashes,input_hashes=inputs,start='2020-01-01',end='2025-12-31',capital_usd=10000,slippage=.0025,allocation_target=.90,fee_model='Original IB margin/default fees retained;2USD +.01USD/share reservation for fees in sizing, actual native fees unchanged',financing='6% fixed annual debit ACT/360 on previous closing USD cash for elapsed calendar days; charge at current close before order sizing. Zero credit interest, disable native per-security margin interest; no terminal accrual beyond final close.',execution='Per-sleeve signal-change intent preserved. MOO reductions first; after confirmed sales, re-evaluate current causal signals at next close and buy no earlier than subsequent open. At most one reduction batch per unchanged intent. No spending unfilled proceeds. Buy cash cap leaves10% NAV reserve,25bp slippage and fee reservation, sequential native initial-margin preflight, halve only until affordable. No daily target maintenance after intent completion. Pending order guard; every skipped/clipped/deferral counted.',hypothesis='Shared execution policy yields zero actual rejected orders in all five cases with explicit funding debit reconciliation. Failure is preserved, not used to tune allocation or timing.',metrics='Same full/annual return, DD, zero-RF daily Sharpe, Calmar and underwater metrics as ablation; financing, debt days, stage waits, clipping, margin deferrals and pending orders',baseline='Saved qc504-ablation-v1 cases reused as controls; combined execution/allocation/funding change, not pure financing attribution',sample='Previously inspected development history; not untouched OOS',stops=['Seven total attempts or45-minute deadline','Technical-only retries; no financial parameter tuning','Nonfinite/nonpositive NAV or source/case identity mismatch','Rejections retained as failed acceptance, no silent repair'],exports='Only aggregate results; raw prices/daily NAV remain hosted; third-party source remains ignored/private; no broker, paid data, publication or orders')
    (ROOT/'research/plans/qc504-funded-v1.json').write_text(json.dumps(plan,indent=2)+'\n')
    (RAW/'attempts.json').write_text(json.dumps(dict(study_id=plan['study_id'],git_sha=subprocess.check_output(['git','rev-parse','HEAD'],text=True).strip(),deadline_utc=plan['deadline_utc'],status='active',attempts=[]),indent=2)+'\n')
    print(json.dumps(dict(deadline=plan['deadline_utc'],hashes=hashes),indent=2))
if __name__=='__main__':prepare()
