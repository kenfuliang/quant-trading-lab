#!/usr/bin/env python3
"""Target-holdings log and view from saved T11 read-only preview runs. Offline; cannot trade.

Each run of scripts/t11_paper_preview.py saves one day's prototype target (gate state, cap and
target weights). This reads every completed run under the preview root and renders them as a
per-day log with the latest on top, plus a sizing helper for a chosen account size.

The target comes from a prototype that the repo records as UNQUALIFIED: no native indicator
parity, a gate bootstrap that differs from the original, and no reconciliation. It is not the
cloud backtest's signal and not an order instruction. The preview collector itself needs the
latest calendar date to be a completed trading session, so it only works after a trading day's
close (after 21:00 New York).

  --root PATH   preview runs folder (default .local/t11-paper-preview)
  --out PATH    default .local/progress/target.html
"""
import argparse
from datetime import datetime, timezone
import html
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
GOOD = "preview_complete_unqualified_not_for_orders"


def load_runs(root):
    runs, skipped = [], 0
    for folder in sorted(Path(root).glob("*/")):
        summary = folder / "summary.json"
        if not summary.exists():
            continue
        try:
            data = json.loads(summary.read_text())
            plan = json.loads((folder / "plan.json").read_text()) if (folder / "plan.json").exists() else {}
        except ValueError:
            skipped += 1
            continue
        if data.get("status") != GOOD or "policy" not in data or "gate" not in data:
            skipped += 1
            continue
        policy, gate = data["policy"], data["gate"]
        weights = {k: float(v) for k, v in (policy.get("gated_weights") or {}).items() if float(v) != 0}
        runs.append({"run": folder.name, "created_utc": plan.get("created_utc"), "asof": data["asof_session"],
                     "gate": {"state": gate.get("state"), "cap": float(gate.get("cap", 0)), "vol": gate.get("vol")},
                     "reason": policy.get("reason"), "weights": weights,
                     "base_weights": {k: float(v) for k, v in (policy.get("base_weights") or {}).items() if float(v) != 0},
                     "limitations": data.get("limitations", []),
                     "seed_parity": gate.get("original2004_seed_parity")})
    runs.sort(key=lambda r: (r["asof"], r["run"]))
    return runs, skipped


_PAGE = r"""<!doctype html><html lang=en><head><meta charset=utf-8><meta name=viewport content="width=device-width,initial-scale=1"><title>Target holdings log</title><style>
:root{--bg:#f6f7f9;--card:#fff;--ink:#14181f;--mute:#5b6573;--line:#dfe3e8;--bad:#c43d3d;--ok:#1f8a4c;--warn:#c98a00}
@media (prefers-color-scheme:dark){:root{--bg:#0e1116;--card:#171b22;--ink:#e8ecf2;--mute:#9aa5b4;--line:#2a313c;--bad:#e56b6b;--ok:#3cb371;--warn:#e0a526}}
*{box-sizing:border-box}body{margin:0;background:var(--bg);color:var(--ink);font:15px/1.5 system-ui,-apple-system,sans-serif}
main{max-width:980px;margin:0 auto;padding:20px 16px 60px}h1{font-size:22px;margin:0 0 4px}h2{font-size:15px;margin:0 0 8px}.n{color:var(--mute);font-size:13px}
.card{background:var(--card);border:1px solid var(--line);border-radius:10px;padding:14px 16px;margin:12px 0}.bad{border-left:4px solid var(--bad)}.stale{border-left:4px solid var(--warn)}
table{width:100%;border-collapse:collapse;font-size:14px}th,td{text-align:left;padding:6px 8px;border-bottom:1px solid var(--line)}th{color:var(--mute);font-weight:600;font-size:12px}td.r,th.r{text-align:right;font-variant-numeric:tabular-nums}
.row{display:flex;flex-wrap:wrap;gap:12px;align-items:end}label{font-size:13px;color:var(--mute);display:flex;flex-direction:column;gap:2px}input{font:inherit;color:var(--ink);background:var(--card);border:1px solid var(--line);border-radius:6px;padding:4px 8px;width:140px}
.tag{display:inline-block;padding:1px 8px;border-radius:9px;font-size:12px;color:#fff}.green{background:var(--ok)}.yellow{background:var(--warn)}.red{background:var(--bad)}.big{font-size:20px;font-weight:650}
</style></head><body><main><h1>Target holdings log</h1><p class=n>One row per saved preview day. Prototype output; not the backtest's signal; not an order.</p>
<section class="card bad"><b>Read this first.</b><ul class=n>
<li>The repo records this preview as <b>unqualified and not for orders</b>: no native indicator parity, a gate bootstrap that differs from the original, no reconciliation and no live quote.</li>
<li>It is not the cloud backtest's signal, which cannot be reproduced locally. The weights below are what a prototype of the policy would hold, and may differ from what the original strategy would have held.</li>
<li>The strategy trades 3x leveraged ETFs. Its backtest max drawdown was 36.9% gated and 51.3% ungated, and the backtest (which stops at 2025-12-31) ended in a drawdown with 2025 roughly flat. Nothing is known about 2026.</li>
<li>Nothing here is advice or an instruction. A bad day can be large, and decisions on your account are yours.</li></ul></section>
<div id=stale></div><div id=latest></div>
<section class=card><h2>Sizing helper</h2><div class=row><label>Account size ($)<input id=size type=number min=0 value=10000></label><label>Deployment (%)<input id=dep type=number min=0 max=100 value=90></label></div>
<p class=n>Notional = account size x deployment x gate cap x weight. The 90% default is the repo's pilot assumption, not a recommendation. Share counts need current prices, which the saved preview does not hold for these ETFs; read them from your broker. Leverage and margin are not modelled.</p><div id=size-out></div></section>
<section class=card><h2>Per-day log</h2><div id=log></div></section>
<section class=card><h2>What changed between days</h2><div id=chg></div></section>
</main><script>
const RUNS=__DATA__,SKIPPED=__SKIPPED__,BUILT="__BUILT__";const $=id=>document.getElementById(id);
const pct=(x,d=1)=>(x*100).toFixed(d)+"%",money=x=>"$"+Math.round(x).toLocaleString("en-US");
function days(a,b){return Math.round((new Date(b)-new Date(a))/864e5)}
function weights(r){return Object.entries(r.weights).sort((a,b)=>b[1]-a[1]).map(([k,v])=>`${k} ${pct(v)}`).join(", ")||"cash"}
function table(h,rows){return rows.length?"<table><tr>"+h.map((x,k)=>`<th class="${k>1?"r":""}">${x}</th>`).join("")+"</tr>"+rows.join("")+"</table>":"<p class=n>None.</p>"}
function size(){const L=RUNS[RUNS.length-1];if(!L){$("size-out").innerHTML="";return}const a=(+$("size").value||0)*(+$("dep").value||0)/100*L.gate.cap;
 $("size-out").innerHTML=table(["Symbol","Weight","Notional"],Object.entries(L.weights).map(([k,v])=>`<tr><td><b>${k}</b></td><td>${pct(v)}</td><td class=r>${money(a*v)}</td></tr>`))+`<p class=n>Cash left: ${money((+$("size").value||0)-a)} (as of session ${L.asof}).</p>`}
if(!RUNS.length){$("latest").innerHTML='<section class="card"><h2>No completed preview runs</h2><p class=n>Run scripts/t11_paper_preview.py after a trading day\'s close (after 21:00 New York). '+SKIPPED+' run(s) were skipped as failed or unreadable.</p></section>'}
else{const L=RUNS[RUNS.length-1],age=days(L.asof,BUILT);
 $("stale").innerHTML=age>3?`<section class="card stale"><b>Stale.</b> The latest saved target is for the ${L.asof} session, ${age} days before this page was built (${BUILT}). It says nothing about today. The collector fails on weekends and holidays; run it after the next trading day's close.</section>`:"";
 $("latest").innerHTML=`<section class=card><h2>Latest target, session ${L.asof}</h2><div class=row><div><div class=n>Gate</div><div class=big><span class="tag ${L.gate.state}">${L.gate.state}</span> cap ${pct(L.gate.cap,0)}</div></div><div><div class=n>Branch</div><div class=big>${L.reason}</div></div><div><div class=n>Target weights (of the deployed amount)</div><div class=big>${weights(L)}</div></div></div><p class=n>Gate volatility ${L.gate.vol==null?"n/a":(L.gate.vol*100).toFixed(1)+"%"}; original-seed parity: ${L.seed_parity===false?"no":"unknown"}. Known limits: ${L.limitations.join("; ")}.</p></section>`}
$("log").innerHTML=table(["Session","Gate","Cap","Branch","Target weights"],[...RUNS].reverse().map(r=>`<tr><td>${r.asof}</td><td><span class="tag ${r.gate.state}">${r.gate.state}</span></td><td class=r>${pct(r.gate.cap,0)}</td><td>${r.reason}</td><td class=r>${weights(r)}</td></tr>`));
$("chg").innerHTML=RUNS.length<2?"<p class=n>Needs at least two days. Each daily preview run adds one.</p>":table(["Session","From","To"],RUNS.slice(1).map((r,k)=>{const p=RUNS[k],same=weights(p)===weights(r)&&p.gate.cap===r.gate.cap;return same?"":`<tr><td>${r.asof}</td><td>${weights(p)} (cap ${pct(p.gate.cap,0)})</td><td class=r>${weights(r)} (cap ${pct(r.gate.cap,0)})</td></tr>`}).filter(Boolean));
$("size").oninput=$("dep").oninput=size;size();
</script></body></html>"""


def render(runs, skipped, built):
    payload = json.dumps(runs, allow_nan=False, separators=(",", ":")).replace("</", "<\\/")
    return _PAGE.replace("__DATA__", payload).replace("__SKIPPED__", str(int(skipped))).replace("__BUILT__", html.escape(built))


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--root", type=Path, default=ROOT / ".local/t11-paper-preview")
    parser.add_argument("--out", type=Path, default=ROOT / ".local/progress/target.html")
    parser.add_argument("--built", default=datetime.now(timezone.utc).date().isoformat(), help="date used for the staleness banner")
    args = parser.parse_args(argv)
    runs, skipped = load_runs(args.root)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(render(runs, skipped, args.built))
    latest = runs[-1]["asof"] if runs else "none"
    print(f"{len(runs)} completed run(s), {skipped} skipped; latest session {latest}. Wrote {args.out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
