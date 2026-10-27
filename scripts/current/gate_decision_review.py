#!/usr/bin/env python3
"""Saved-ledger diagnosis only: reconstruct logs, label outcomes, render review."""
from pathlib import Path
import argparse
from datetime import datetime, timezone
import hashlib
import json
import shutil
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
import numpy as np
import pandas as pd
from reporting.decision_labels import METHOD, decision_log, outcome_labels, summarize
from research.studies.spy.spy_backtest import load_data

RECEIPT = 'docs/tasks/evidence/2026-10-25-rsi-risk-gate-completion.json'
SOURCE = 'reports/spy/20261024-235746-728801/source-data.json'
PROTOCOL = 'docs/tasks/2026-10-25-gate-decision-labels.md'
ORIGINAL = 'reports/risk-gate/b6b57fe7077dff3b'
ABLATION = 'reports/risk-gate/449096da9fbe1385'
CODE = ['reporting/decision_labels.py', 'reporting/gate_decisions.html',
        'scripts/current/gate_decision_review.py', 'tests/test_decision_labels.py']


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def write(path, value):
    Path(path).write_text(json.dumps(value, indent=2, allow_nan=False) + '\n')


def verify_sources(receipt):
    count = 0
    for rel, entry in receipt['source_manifests'].items():
        base = ROOT / rel
        if sha(base/'manifest.json') != entry['manifest_sha256']:
            raise ValueError('Parent manifest changed: '+rel)
        hashes = json.loads((base/'manifest.json').read_text())['artifact_hashes']
        if len(hashes) != entry['artifact_count']:
            raise ValueError('Parent artifact count changed.')
        for file, expected in hashes.items():
            if sha(base/file) != expected:
                raise ValueError('Parent artifact changed: '+file)
            count += 1
    if sha(ROOT/SOURCE) != receipt['source_sha256']:
        raise ValueError('Frozen input changed.')
    return count


def folder(cost, rule):
    if rule.startswith('ablate_'):
        return ROOT / ABLATION / f'{cost}_{rule}'
    if cost == 5 and rule == 'ema':
        return ROOT/'reports/risk-gate/97e9d442a8b83201/5_ema'
    if cost == 5 and rule == 'hold':
        return ROOT/'reports/risk-gate/5da2f7dccff31178/5_hold'
    return ROOT / ORIGINAL / f'{cost}_{rule}'


def read(folder, name):
    return pd.read_csv(folder/name, index_col='date', parse_dates=['date'])


def independent_checks(decisions, outcomes, g, b, capital):
    """Scalar saved-path oracle, separate label implementation and anchoring."""
    checks = 0
    lookup = {row.decision_id: i for i, row in enumerate(decisions.itertuples())}
    for row in outcomes.itertuples():
        i = lookup[row.decision_id]; j = i + row.horizon_sessions - 1
        d = decisions.iloc[i]
        if j >= len(g):
            assert row.right_censored and pd.isna(row.gate_return) and pd.isna(row.base_return)
            assert row.label == 'right_censored' and pd.isna(row.label_available_after_close)
        else:
            rg = float(g.iloc[j]/(capital if i == 0 else g.iloc[i-1])-1)
            rb = float(b.iloc[j]/(capital if i == 0 else b.iloc[i-1])-1)
            assert abs(row.gate_return-rg) < 1e-12 and abs(row.base_return-rb) < 1e-12
            assert abs(row.gate_minus_base_pp-(rg-rb)*100) < 1e-12
            assert row.label_available_after_close == decisions.execution_session.iloc[j]
            if d.warning_already_cash: label = 'warning_already_cash_no_immediate_credit'
            elif not d.intended_reduction: label = 'no_immediate_target_reduction'
            elif abs(rg-rb) <= 1e-10: label = 'no_material_relative_difference'
            elif rb < -1e-10 and rg > rb: label = 'helped_during_base_loss'
            elif rb > 1e-10 and rg < rb:
                label = 'missed_rebound' if pd.notna(d.prior_spy_return_21) and d.prior_spy_return_21 < -1e-10 else 'missed_positive_base_move'
            elif rb < -1e-10 and rg < rb: label = 'worsened_base_loss'
            elif rb > 1e-10 and rg > rb: label = 'outperformed_positive_base'
            else: label = 'mixed_near_flat_base'
            assert row.label == label
        checks += 1
    return checks


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    args=parser.parse_args(); out=args.output.resolve()
    receipt=json.loads((ROOT/RECEIPT).read_text())
    verified=verify_sources(receipt)
    raw, _, _=load_data(ROOT/SOURCE); raw=raw.round(2)
    raw.index=pd.to_datetime(raw.index)
    if out.exists():
        raise ValueError('Output exists; preserve it and select a new version.')
    out.mkdir(parents=True)
    identity=dict(method=METHOD, origin='reconstructed_saved_evidence',
        created_utc=datetime.now(timezone.utc).isoformat(), financial_simulations=0,
        source_path=SOURCE, source_sha256=sha(ROOT/SOURCE),
        parent_receipt=RECEIPT, parent_sha256=sha(ROOT/RECEIPT),
        protocol=PROTOCOL, protocol_sha256=sha(ROOT/PROTOCOL),
        code_hashes={p:sha(ROOT/p) for p in CODE},
        source_artifacts_verified=verified)
    write(out/'protocol.json',identity)
    (out/'source').mkdir()
    for path in CODE:
        shutil.copyfile(ROOT/path,out/'source'/Path(path).name)
    shutil.copyfile(ROOT/PROTOCOL,out/'source'/'diagnostic-protocol.md')
    rows=[]; daily_rows=[]; report={}; all_checks=0
    for cost in (5,10):
        for rule in ('gate_ema','ablate_ema','gate_hold','ablate_hold'):
            key=f'{cost}_{rule}'; gf=folder(cost,rule); bf=folder(cost,'ema' if rule.endswith('ema') else 'hold')
            sig=read(gf,'signal.csv'); time=read(gf,'timeline.csv')
            g=read(gf,'ledger.csv'); b=read(bf,'ledger.csv')
            for path in (gf,bf):
                audit=json.loads((path/'audit.json').read_text())
                if not audit['passed']: raise ValueError('Saved accounting audit did not pass.')
            if len(g)!=5283 or str(g.index[0].date())!='2005-01-03' or str(g.index[-1].date())!='2025-12-31':
                raise ValueError('Unexpected saved coverage.')
            d=decision_log(time,sig,g,b,raw.close,300000,key,peak_enabled=rule.startswith('gate_'))
            o=outcome_labels(d,g.equity_usd,b.equity_usd,300000)
            checks=independent_checks(d,o,g.equity_usd,b.equity_usd,300000); all_checks+=checks
            daily,sums,joined=summarize(d,o)
            # Verify summary counts independently from each joined slice.
            for r in sums:
                v=joined[(joined[r['event']]) & ~joined.evaluation_boundary & (joined.horizon_sessions==r['horizon_sessions'])]
                assert len(v)==r['anchors']
                assert int((~v.right_censored).sum())==r['evaluable']
                assert sum(r['label_counts'].values())==r['evaluable']
                rows.append(dict(pair_id=key,cost_bps=cost,rule=rule,**{k:v for k,v in r.items() if k!='label_counts'},
                                 **{k:r['label_counts'].get(k,0) for k in ['helped_during_base_loss','missed_rebound','missed_positive_base_move','worsened_base_loss','outperformed_positive_base','warning_already_cash_no_immediate_credit','no_immediate_target_reduction','no_material_relative_difference','mixed_near_flat_base']}))
            dest=out/key; dest.mkdir()
            d.to_csv(dest/'decisions.csv',index=False)
            o.to_csv(dest/'outcomes.csv',index=False)
            execution=pd.DataFrame(dict(decision_id=d.decision_id.to_numpy(),execution_session=d.execution_session.to_numpy(),
                raw_open=sig.open.to_numpy(),raw_close=sig.close.to_numpy(),
                gate_shares=g.shares.to_numpy(),base_shares=b.shares.to_numpy(),
                gate_equity_usd=g.equity_usd.to_numpy(),base_equity_usd=b.equity_usd.to_numpy(),
                gate_commission_usd=g.commission_usd.to_numpy(),gate_slippage_usd=g.slippage_usd.to_numpy(),
                base_commission_usd=b.commission_usd.to_numpy(),base_slippage_usd=b.slippage_usd.to_numpy()))
            execution.to_csv(dest/'execution.csv',index=False)
            event_mask=joined[['reduction_episode_start','warning_episode_start','red_entry','red_exit','warning_already_cash']].any(axis=1)
            events=joined.loc[event_mask].copy()
            events.to_csv(dest/'events.csv',index=False)
            write(dest/'summary.json',dict(daily=daily,events=sums,independent_window_checks=checks,gate_folder=str(gf.relative_to(ROOT)),base_folder=str(bf.relative_to(ROOT))))
            daily_rows.append(dict(pair_id=key,cost_bps=cost,rule=rule,**daily))
            report[key]=dict(daily=daily,summary=sums,
                events=json.loads(events[['execution_session','observed_close','state','base_target','gate_target','prior_spy_return_21','warning_already_cash','warning_base_exiting','intended_reduction','evaluation_boundary','reduction_episode_start','warning_episode_start','red_entry','red_exit','horizon_sessions','right_censored','label_available_after_close','gate_return','base_return','gate_minus_base_pp','label']].to_json(orient='records')),
                curve=dict(dates=d.execution_session.tolist(),gate=(g.equity_usd/300000*100-100).tolist(),base=(b.equity_usd/300000*100-100).tolist()))
    pd.DataFrame(rows).to_csv(out/'event-summary.csv',index=False)
    pd.DataFrame(daily_rows).to_csv(out/'daily-summary.csv',index=False)
    write(out/'review.json',dict(identity=identity,pairs=report,independent_window_checks=all_checks))
    template=(ROOT/'reporting/gate_decisions.html').read_text()
    payload=json.dumps(report,allow_nan=False).replace('</','<\\/')
    (out/'index.html').write_text(template.replace('__PAYLOAD__',payload))
    assert verify_sources(receipt)==verified
    write(out/'manifest.json',dict(method=METHOD,financial_simulations=0,independent_window_checks=all_checks,
        source_artifacts_verified=verified,artifact_hashes={str(p.relative_to(out)):sha(p) for p in sorted(out.rglob('*')) if p.is_file()}))
    print(json.dumps(dict(output=str(out),pairs=len(report),decision_rows=5283*len(report),
        outcome_rows=5283*3*len(report),independent_window_checks=all_checks,source_artifacts_verified=verified)))


if __name__=='__main__':main()
