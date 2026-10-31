"""Read-only re-audit of closed robustness evidence; never starts a simulation."""
from pathlib import Path
from datetime import datetime,timezone
import argparse
import json
import sys
import numpy as np
import pandas as pd
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from research.studies.checkpoint_20261031 import gate_robustness as saved
from reporting.risk_gate_review import verify_temporal_details

OUT=Path('.local/grs-r001')
FIGURE=Path('docs/diagrams/ema-volatility-experience.png')


def main():
    if OUT.exists() or FIGURE.exists():raise FileExistsError('Preserve previous audit/report figure')
    p=json.loads(saved.PLAN.read_text());frames,dividends=saved.preflight(p)
    root=Path('.local/gate-robustness')/saved.old.digest(saved.PLAN)[:16]
    proof=saved.verify_artifacts(root);state=json.loads((root/'state.json').read_text())
    if state['status']!='completed' or state['actual_attempts']!=9 or any(a['status']!='completed' for a in state['attempts']):raise ValueError('Original completion gate')
    before=saved.old.digest(root/'manifest.json');OUT.mkdir(parents=True,exist_ok=False)
    rows=[];checks={};max_difference=0.
    for c in saved.CASES:
        folder=root/c['id'];frame=frames[c['id']]
        curve=pd.read_csv(folder/'ledger.csv',index_col='date');trades=pd.read_csv(folder/'trades.csv')
        model=saved.old.FinancingModel(**(p['model']|dict(cost_bps=c['cost_bps'])))
        mode='buy_hold' if c['rule']=='buy_hold_entry_only' else 'trend'
        # Replay recorded fills/account arithmetic; no target/portfolio simulation.
        book=saved.old.reconcile(frame,dividends,curve,trades,mode,1,model)
        review=saved.old.inspect(folder)
        temporal=json.loads((folder/'temporal.json').read_text());table=pd.read_csv(folder/'temporal.csv',index_col='date',parse_dates=True)
        eq=pd.Series(np.r_[model.capital,curve.equity_usd],index=pd.to_datetime(['2004-12-31',*curve.index]))
        temporal_check=saved.old.independent_temporal(eq,temporal,table)
        detail=verify_temporal_details(eq,temporal)
        max_difference=max(max_difference,book['maximum_difference_usd'])
        row=dict(case=c['id'],context=c['context'],rule=c['rule'],cost_bps=c['cost_bps'],signal_delay=c['signal_delay'],**review['overall'],duration=temporal['longest_underwater_duration_sessions'],duration_days=temporal['longest_underwater_duration_calendar_days'],censored=temporal['longest_underwater_right_censored'])
        rows.append(row);checks[c['id']]=dict(accounting=book,metric_checks=len(review['metric_checks']),temporal=temporal_check,details=detail)
    pairs={}
    for context,_,_ in saved.CONTEXTS:
        a={r['rule']:r for r in rows if r['context']==context};pairs[context]=saved.joint_claim(a['gate_ema'],a['ema'])
    old_decision=json.loads((root/'decision.json').read_text())
    if pairs!=old_decision['comparisons'] or not all(x['passed'] for x in pairs.values()):raise ValueError('Recomputed primary comparison differs')
    # Original saved full and annual summaries are independently checked above; copy only own aggregate results.
    pd.DataFrame([{k:v for k,v in r.items() if k not in ['metric_checks','worst_drawdown_episode']} for r in rows]).to_csv(OUT/'overall.csv',index=False)
    (OUT/'annual.csv').write_bytes((root/'annual.csv').read_bytes())
    # Keep the known block helper's nonannualized Calmar column out of the new report.
    blocks=pd.read_csv(root/'blocks.csv').drop(columns=['calmar']);blocks.to_csv(OUT/'blocks-qualified.csv',index=False)
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    plt.rcParams.update({'font.size':10,'axes.spines.top':False,'axes.spines.right':False})
    fig,axes=plt.subplots(2,1,figsize=(11,6.5),sharex=True,gridspec_kw={'height_ratios':[2,1]},layout='constrained')
    names={'gate_ema':'EMA + volatility gate','ema':'EMA50/200','buy_hold_entry_only':'Entry-only SPY holding'}
    colors={'gate_ema':'#507d55','ema':'#487da4','buy_hold_entry_only':'#7d7770'}
    for rule in names:
        q=pd.read_csv(root/('base_'+rule)/'ledger.csv',index_col='date',parse_dates=True).equity_usd
        q=pd.concat([pd.Series([300000.],index=pd.to_datetime(['2004-12-31'])),q])
        axes[0].plot(q.index,q/300000,label=names[rule],color=colors[rule],linewidth=1.35)
        axes[1].plot(q.index,100*(q/q.cummax()-1),color=colors[rule],linewidth=1.)
    axes[0].set_yscale('log');axes[0].set_ylabel('Portfolio / initial capital (log scale)');axes[0].legend(loc='upper left',frameon=False)
    axes[0].set_title('Saved SPY development study: gate improves on EMA, holding ends wealthier',loc='left',weight='bold')
    axes[1].set_ylabel('Closing drawdown (%)');axes[1].set_xlabel('2005–2025 · 5 bp per side + USD1 per trade · USD300,000 initial')
    for ax in axes:ax.grid(alpha=.2)
    fig.savefig(FIGURE,dpi=170);plt.close(fig)
    if saved.old.digest(root/'manifest.json')!=before:raise ValueError('Original evidence changed')
    receipt=dict(report='GRS-R001',kind='retrospective_read_only_evidence_audit_and_experience_report',status='audited-development-evidence',checked_utc=datetime.now(timezone.utc).isoformat(),
        new_financial_attempts=0,original_financial_attempts=9,source_directory=str(root),source_manifest=proof,source_plan_sha256=saved.old.digest(saved.PLAN),
        source_sha256=p['source']['sha256'],reviewer_sha256=saved.old.digest(__file__),checks=checks,comparisons=pairs,
        audited_sessions=sum(c['accounting']['sessions'] for c in checks.values()),metric_checks=sum(c['metric_checks'] for c in checks.values()),
        max_account_difference_usd=max_difference,independent_validation=False,new_algorithm=False,source_unchanged=True,
        positive_claim='Frozen gate passes joint development criteria versus EMA in three cost/timing contexts.',
        counterevidence=['Entry-only holding grows faster in all contexts.','Gate loses2012–2018cumulative return to EMA in all contexts.','Exposure-matched timing benefit and future advantage remain unverified.','Known block cumulative-return/DD ratio excluded from annualized Calmar rankings.'],
        figure={'path':str(FIGURE),'sha256':saved.old.digest(FIGURE)},limits='Viewed retail-data fixture; ex-date dividend cash; synthetic execution; no native broker parity or publication.')
    saved.old.write(OUT/'audit.json',receipt)
    saved.old.write(OUT/'manifest.json',dict(artifact_hashes={str(f.relative_to(OUT)):saved.old.digest(f) for f in sorted(OUT.rglob('*')) if f.is_file()}))
    saved.old.write('docs/tasks/evidence/2026-10-27-grs-r001.json',receipt)
    print(json.dumps({k:receipt[k] for k in ['status','new_financial_attempts','audited_sessions','metric_checks','max_account_difference_usd']}))


if __name__=='__main__':main()
