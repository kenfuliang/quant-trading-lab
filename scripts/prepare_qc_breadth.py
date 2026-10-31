"""Freeze five matched adapters and one order-free access probe."""
import ast,json,hashlib,subprocess
from pathlib import Path
from datetime import datetime,timezone,timedelta
ROOT=Path(__file__).resolve().parents[1];STUDY='qc-breadth-v1';RAW=ROOT/'.local'/STUDY
CASES=('asset','momentum','lowvol','spy','t11')
def generate(mode):
 source=(RAW.parent/'qc504-funded-v1/t11-source.py').read_text()
 if mode=='t11':return source.replace('qc504-funded-v1',STUDY)
 base=ast.parse((ROOT/'research/quantconnect/selection_candidates.py').read_text());cls=next(n for n in base.body if isinstance(n,ast.ClassDef))
 next(n for n in base.body if isinstance(n,ast.Assign) and n.targets[0].id=='MODE').value=ast.Constant(mode)
 metric=ast.parse((ROOT/'research/quantconnect/sector_metrics.py').read_text())
 base.body[:0]=metric.body+ast.parse('AUDIT_CASE='+repr(mode)+'\nAUDIT_START_YEAR=2020').body
 template=next(n for n in ast.parse(source.replace('qc504-funded-v1',STUDY)).body if isinstance(n,ast.ClassDef))
 for n in template.body:
  if isinstance(n,ast.FunctionDef) and (n.name.startswith('_audit_') or n.name.startswith('_fund')):
   if n.name=='_audit_emit':
    n.body=ast.parse("""
if payload.get('kind')=='overall':
    payload=dict(payload,universe_calls=self._universe_calls,fundamental_valid=self._fundamental_valid,selection_events=self._selection_events,history_seeded=self._history_seeded,history_short=self._history_short,min_ready=min(self._ready_counts) if self._ready_counts else 0,membership_sha256=self._membership_hash.hexdigest())
""").body+n.body
   cls.body.append(n)
 return ast.unparse(ast.fix_missing_locations(base))+'\n'
def main():
 hashes={}
 for case in CASES:
  p=RAW/f'{case}-source.py';assert not p.exists();p.write_text(generate(case));hashes[case]=hashlib.sha256(p.read_bytes()).hexdigest();assert p.stat().st_size<32768
 p=RAW/'access-source.py';p.write_text((ROOT/'research/quantconnect/selection_access_probe.py').read_text());hashes['access']=hashlib.sha256(p.read_bytes()).hexdigest()
 now=datetime.now(timezone.utc);plan=json.loads((ROOT/'research/plans/qc504-funded-v1.json').read_text())
 plan.update(study_id=STUDY,cases=['access']+list(CASES),source_hashes=hashes,created_utc=now.isoformat(),deadline_utc=(now+timedelta(minutes=60)).isoformat(),max_financial_attempts=8,max_unique_cases=6,technical_repair_slots=2,status='frozen-before-access-probe',hypothesis='Inspect and test three declared source-informed adaptations against SPY and unchanged funded T11; no performance threshold tuning.',baseline='Five fresh financial cases plus one order-free access probe. T11 must reproduce funded-v1; same2020–2025 dates and cash/cost/funding model.',sample='Viewed development sample, not untouched OOS.',exports='Aggregate metrics/counts/hashes only; raw price/fundamental data remain hosted. Legacy strategy copies private; no broker, paid data or publication.',selection=dict(asset='SPY/EFA/BND/VNQ/GSG;252-session percentage momentum;top3 equal monthly',momentum='Monthly point-in-time fundamentals:price>5,hasfundamentals,top100 dollarvolume,positive finite marketcap top50;252-session pctmomentum top5',lowvol='Daily same fundamental screen;monthly top5 lowest sample stdev of252 daily returns',normalization='Monthly253-close typed SCALED_RAW history, completed current session only; rebuild feature window in one basis',timing='First observed SPY session close each month, then common staged MOO executor. Monthly rebalance intent resets even if names unchanged. Same fixed90% base budget.',short_history='Only253-close current-session histories eligible; missing slots stay cash; counts reported',deviations='Modern intended-rule adaptations, not exact legacy examples: percentage rather than dollar momentum, return rather than price-level volatility, true market_cap rather than PE*EPS*shares proxy; ETF equal targets fix added-holdings sizing; uniform staged next-open execution.'),metrics='Full/annual return, closingDD,zeroRFsampledailySharpe,Calmar,underwaterfraction/longest sessions/calendar days/censoring;execution/funding/access counts',stops=['Eight total attempts including access probe and technical failures,60-minute deadline','Access must pass before allocation runs; no paid upgrade','At most2 technical-only retries, no signal/threshold changes after results','Nonfinite/nonpositiveNAV, missing source/calendar or future data fail closed; preserve failed artifacts'])
 (ROOT/f'research/plans/{STUDY}.json').write_text(json.dumps(plan,indent=2)+'\n')
 (RAW/'attempts.json').write_text(json.dumps(dict(study_id=STUDY,git_sha=subprocess.check_output(['git','rev-parse','HEAD'],text=True).strip(),deadline_utc=plan['deadline_utc'],status='active',attempts=[]),indent=2)+'\n')
 print(plan['deadline_utc'],hashes)
if __name__=='__main__':main()
