"""Coordinator budget for the bounded CAPM/SPY hosted study."""
from pathlib import Path
import hashlib
import json
from datetime import datetime, timezone, timedelta
import argparse
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from research.studies.checkpoint_20261031.qc.capm_study import write_sources, ORIGINAL
ROOT = Path('.local/capm-spy-v1')
PLAN = Path('research/plans/capm-spy-v1.json')
LEDGER = ROOT / 'budget.json'


def save(path, value):
    temp = path.with_suffix(path.suffix + '.tmp')
    temp.write_text(json.dumps(value, indent=2) + '\n')
    temp.replace(path)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('action', choices=['freeze', 'reserve', 'record', 'close', 'reserve-extension', 'record-extension'])
    parser.add_argument('--case', choices=['probe', 'capm', 'spy'])
    parser.add_argument('--status')
    parser.add_argument('--url')
    args = parser.parse_args()
    now = datetime.now(timezone.utc)
    if args.action == 'freeze':
        if PLAN.exists() or LEDGER.exists():
            raise ValueError('Study already frozen')
        hashes = write_sources(ROOT)
        plan = dict(study_id='capm-spy-v1', status='frozen-before-probe', created_utc=now.isoformat(), deadline_utc=(now+timedelta(minutes=90)).isoformat(), cases=['probe', 'capm', 'spy'], max_total_attempts=5, max_financial_attempts=4, technical_repair_slots=2, project_id=38510582, source_repo='QuantConnect/Lean', source_commit='22404ea28b8d3f3c9eb74d6ed9f0444426f8e417', original_path=str(ORIGINAL), original_sha256=hashlib.sha256(ORIGINAL.read_bytes()).hexdigest(), source_hashes=hashes, start='2016-01-01', end='2025-12-31', capital_usd=300000, cash_buffer=0.01, slippage=0.0025, fees='Native InteractiveBrokersFeeModel, IB margin brokerage; extend initializer, assert actual model.', financing='6% annual fixed debit ACT/360 on prior close USD cash, charge at current close; zero credit; native per-security interest disabled. No accrual after last close.', candidate='Original 29 fixed legacy symbols, monthly source reverse-regression intercept top2, ConstantAlpha(one day up), EqualWeighting, ImmediateExecution, 1% per-security drawdown stop. No rank/threshold optimization.', baseline='SPY initial target100% with common1% cash buffer, hold without rebalancing or stop.', timing='Source monthly scheduled universe at first session market open; minute native execution. Closing NAV after final SPY minute before framework decisions; no forced final liquidation. Probe uses daily SPY clock and annual21daily/1minute source history checks.', data='Free hosted US equity price/corporate-action/map data only. Native source Symbol.create identities retained; no replacement with current constituents. No fundamentals/alternative data dependency.', source_caveats=['Official framework alternative, not exact hosted tutorial.', '29 names, fixed survivor/selection biases; legacy mapping needs probe.', 'Regression predicts benchmark from stock, not standard stock-on-market CAPM; retain source.', '1% per-security stop is not portfolio1% maximum drawdown.'], metrics='Full/annual total return, daily close maximum drawdown, sample daily Sharpe annualizedsqrt252 at zero RF, full CAGR/absDD Calmar, annual return/abs annualDD Calmar; underwater fraction, longest sessions and calendar days, terminal censoring. Annual peak resets, full path carries peak.', primary_estimand='Descriptive full-period Calmar difference vs SPY with return/drawdown/underwater tradeoffs. No pass threshold or post-result tuning.', history='Viewed development sample; no untouched OOS or forward result.', exports='Own aggregate metrics/counts/calendar hashes only. Raw bars, dense NAV/returns and corporate actions stay hosted.', stops=['Five total attempts including probe/technical failures; at most two technical-only repairs;90minute deadline.', 'Probe must complete before financial cases. If startup dependencies or required startup data fail, stop or documented technical repair within budget.', 'Nonfinite/nonpositive NAV, missing/misaligned history, invalid rejects, wrong fee/interest model or accounting residuals fail eligibility.', 'No paid resources/data, parameter tuning, broker/account operations, orders outside simulation, services, commits or publication.'])
        save(PLAN, plan)
        save(LEDGER, dict(study='capm-spy-v1', status='active', attempts=[]))
        print(json.dumps({'frozen':str(PLAN), 'deadline':plan['deadline_utc'], 'sources':hashes}))
        return
    if args.action in ['reserve-extension', 'record-extension']:
        ep = Path('research/plans/capm-spy-v1.accounting-retest.json')
        el = ROOT/'accounting-retest-budget.json'
        extension, receipt = json.loads(ep.read_text()), json.loads(el.read_text())
        if args.action == 'reserve-extension':
            if json.loads(LEDGER.read_text())['status'] != 'closed' or receipt['status'] != 'active' or receipt['attempts']:
                raise ValueError('Parent not closed or single extension attempt already used')
            if now > datetime.fromisoformat(extension['deadline_utc']):
                raise ValueError('Extension expired')
            digest = hashlib.sha256((ROOT/'capm-source.py').read_bytes()).hexdigest()
            if digest != extension['source_sha256']:
                raise ValueError('Extension source drift')
            receipt['attempts'].append(dict(id=1,case='capm',status='reserved',reserved_utc=now.isoformat(),source_sha256=digest,verified_build=extension['verified_saved_build']))
        else:
            row=receipt['attempts'][-1]
            if row['status'] != 'reserved':
                raise ValueError('Extension already recorded')
            row.update(status=args.status,url=args.url,recorded_utc=now.isoformat())
            receipt.update(status='closed',closed_utc=now.isoformat())
        save(el, receipt)
        print(json.dumps(receipt))
        return
    plan, ledger = json.loads(PLAN.read_text()), json.loads(LEDGER.read_text())
    if args.action == 'reserve':
        if ledger['status'] != 'active' or now > datetime.fromisoformat(plan['deadline_utc']):
            raise ValueError('Closed or expired study')
        if not args.case:
            raise ValueError('Case required')
        if ledger['attempts'] and ledger['attempts'][-1]['status'] == 'reserved':
            raise ValueError('Record prior attempt before reserving another')
        financial = sum(a['case'] != 'probe' for a in ledger['attempts'])
        repeats = sum(max(0, sum(a['case'] == c for a in ledger['attempts']) - 1) for c in plan['cases'])
        if args.case != 'probe' and financial >= plan['max_financial_attempts']:
            raise ValueError('Financial attempt cap')
        if any(a['case'] == args.case for a in ledger['attempts']) and repeats >= plan['technical_repair_slots']:
            raise ValueError('Technical repair cap')
        if len(ledger['attempts']) >= plan['max_total_attempts']:
            raise ValueError('Attempt limit')
        if args.case != 'probe' and not (ROOT/'probe-gate.json').exists():
            raise ValueError('Access probe gate absent')
        if args.case != 'probe' and not json.loads((ROOT/'probe-gate.json').read_text())['passed']:
            raise ValueError('Access probe did not pass')
        path = ROOT/f'{args.case}-source.py'
        digest = hashlib.sha256(path.read_bytes()).hexdigest()
        if digest != plan['source_hashes'][args.case]:
            raise ValueError('Source changed outside frozen protocol')
        ledger['attempts'].append(dict(id=len(ledger['attempts'])+1, case=args.case, reserved_utc=now.isoformat(), source_sha256=digest, status='reserved'))
        save(LEDGER, ledger)
        print(json.dumps(ledger['attempts'][-1]))
    elif args.action == 'record':
        row = ledger['attempts'][-1]
        if row['case'] != args.case:
            raise ValueError('Attempt case mismatch')
        row.update(status=args.status, url=args.url, recorded_utc=now.isoformat())
        save(LEDGER, ledger)
        print(json.dumps(row))
    else:
        ledger.update(status='closed', closed_utc=now.isoformat())
        save(LEDGER, ledger)
        print('Budget closed')

if __name__ == '__main__':
    main()
