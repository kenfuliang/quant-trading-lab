#!/usr/bin/env python3
"""Per-day holdings browser for saved strategy exports. Offline and read-only.

Inputs per strategy: a close-path JSON (session, nav_usd, export_sample_utc) and the full
QuantConnect export JSON (orders, closed trades, exposure and turnover charts). Share counts
are the cumulative sum of filled orders by fill date, so they are exact only as far as the
export's order list is complete. Timing, as measured on the saved paths: flat days earn exactly
0 and a day where a position is first opened earns that day's return, so fills happen at the
start of the fill date and the decision is made at the previous close (an order's created time); the repo's own audit says the export's cash and position ledger
was NOT reconciled, and no daily decision trace exists. Values use the last fill price per
symbol, which is stale between trades: they are approximate and not marked to market.
The page shows the export's own reported long exposure beside them.

  --strategy NAME=CLOSE_PATH,EXPORT   repeatable
  --out PATH                          default .local/progress/holdings.html (ignored; private data)

Descriptive history only. It is not a signal, a forecast or advice.
"""
import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]


def _epoch(stamp):
    return int(datetime.fromisoformat(stamp.replace("Z", "+00:00")).timestamp())


def build_dataset(name, close_path, export):
    sessions = [r["session"] for r in close_path]
    nav = [float(r["nav_usd"]) for r in close_path]
    known = set(sessions)
    series = {s["name"] if "name" in s else key: s for key, s in export["charts"]["Exposure"]["series"].items()}
    expo_raw = {int(t): v for t, v in (series.get("Equity - Long Ratio", {}).get("values") or [])}
    turn_raw = {int(t): v for t, v in (export["charts"].get("Portfolio Turnover", {}).get("series", {})
                                       .get("Portfolio Turnover", {}).get("values") or [])}
    expo, turn = [], []
    for r in close_path:
        epoch = _epoch(r["export_sample_utc"])
        expo.append(expo_raw.get(epoch))
        turn.append(turn_raw.get(epoch))
    orders, decided = {}, {}
    unmatched = 0
    for order in sorted(export["orders"].values(), key=lambda o: (o["lastFillTime"], o["id"])):
        if order.get("status") != 3:
            continue
        day = order["lastFillTime"][:10]
        if day not in known:
            unmatched += 1
            continue
        row = [order["symbol"]["value"], float(order["quantity"]), round(float(order["price"]), 4), order.get("tag", "")]
        orders.setdefault(day, []).append(row)
        if order["time"][:10] in known:
            decided.setdefault(order["time"][:10], []).append(row)
    trades = {}
    for trade in export.get("totalPerformance", {}).get("closedTrades", []):
        day = trade["exitTime"][:10]
        if day in known:
            trades.setdefault(day, []).append([trade["symbols"][0]["value"], trade["entryTime"][:10], float(trade["quantity"]),
                                               round(float(trade["entryPrice"]), 4), round(float(trade["exitPrice"]), 4),
                                               round(float(trade["profitLoss"]), 2), round(float(trade.get("totalFees", 0)), 2)])
    shares, last, pos = {}, {}, {}
    for day in sessions:
        if day in orders:
            for symbol, quantity, price, _ in orders[day]:
                shares[symbol] = round(shares.get(symbol, 0.0) + quantity, 6)
                last[symbol] = [price, day]
            pos[day] = {s: [shares[s], last[s][0], last[s][1]] for s in shares if abs(shares[s]) > 1e-9}
    return {"name": name, "dates": sessions, "nav": nav, "expo": expo, "turn": turn,
            "orders": orders, "decided": decided, "trades": trades, "pos": pos, "unmatched_orders": unmatched,
            "note": "Reconstructed from the cloud export's filled orders; the export's own position ledger was not reconciled."}


def positions_on(dataset, day):
    """Holdings after the close of `day`: the latest snapshot at or before it."""
    best = None
    for d in sorted(dataset["pos"]):
        if d <= day:
            best = d
    return dataset["pos"].get(best, {}) if best else {}


_HTML = r"""<!doctype html><html lang=en><head><meta charset=utf-8><meta name=viewport content="width=device-width,initial-scale=1">
<title>Per-day holdings</title><style>
:root{--bg:#f6f7f9;--card:#fff;--ink:#14181f;--mute:#5b6573;--line:#dfe3e8;--up:#1f8a4c;--down:#c43d3d;--accent:#2457d6}
@media (prefers-color-scheme:dark){:root{--bg:#0e1116;--card:#171b22;--ink:#e8ecf2;--mute:#9aa5b4;--line:#2a313c;--up:#3cb371;--down:#e56b6b;--accent:#7aa2ff}}
*{box-sizing:border-box}body{margin:0;background:var(--bg);color:var(--ink);font:15px/1.5 system-ui,-apple-system,sans-serif}
main{max-width:1100px;margin:0 auto;padding:20px 16px 60px}h1{font-size:22px;margin:0 0 4px}h2{font-size:15px;margin:0 0 8px}
.n{color:var(--mute);font-size:13px}.card{background:var(--card);border:1px solid var(--line);border-radius:10px;padding:14px 16px;margin:12px 0}
.warn{border-left:4px solid var(--down)}.row{display:flex;flex-wrap:wrap;gap:10px;align-items:center}
.grid{display:grid;gap:10px;grid-template-columns:repeat(auto-fit,minmax(150px,1fr))}.k{color:var(--mute);font-size:12px;text-transform:uppercase;letter-spacing:.04em}.v{font-size:20px;font-weight:650}
table{width:100%;border-collapse:collapse;font-size:14px}th,td{text-align:left;padding:5px 8px;border-bottom:1px solid var(--line)}th{color:var(--mute);font-weight:600;font-size:12px}td.r,th.r{text-align:right;font-variant-numeric:tabular-nums}
.pos{color:var(--up)}.neg{color:var(--down)}input,select,button{font:inherit;color:var(--ink);background:var(--card);border:1px solid var(--line);border-radius:6px;padding:4px 8px}
button{cursor:pointer}input[type=range]{flex:1;min-width:200px;padding:0}canvas{width:100%;display:block;border-radius:6px;cursor:crosshair}
.chg{background:color-mix(in srgb,var(--accent) 14%,transparent)}tr.sel{background:color-mix(in srgb,var(--accent) 22%,transparent);outline:1px solid var(--accent)}
</style></head><body><main>
<h1>Per-day holdings</h1><p class=n>Pick any session. Descriptive history from saved exports; not a signal, a forecast or advice.</p>
<section class="card warn"><b>How far to trust the holdings.</b><ul class=n>
<li>Timing seen in the data: days with no holdings earn exactly 0, and the day a position is first opened earns that day's return. So an order is <b>decided at the previous close and filled near the start of the next session</b>, and "held through this session" includes that session's fills.</li>
<li>Shares are rebuilt from the export's filled orders. The repo's audit found the export's cash and position ledger <b>not reconciled</b> and no official daily decision trace, so treat them as reconstructed.</li>
<li>Values use each symbol's <b>last fill price</b>, stale between trades. They are approximate and not marked to market; compare with the export's own long exposure shown above.</li>
<li>This is a past backtest from a cloud run that cannot be reproduced locally. It does not tell you what to hold today.</li></ul></section>
<section class=card><h2>Period <span class=n id=pinfo></span></h2><div class=row id=presets></div>
<div class=row style="margin-top:8px"><label>From <input type=date id=from></label><label>To <input type=date id=to></label></div></section>
<section class=card><div class=row><label>Strategy <select id=sel></select></label><span class=n id=snote style="flex-basis:100%"></span><label>Date <input type=date id=date></label>
<button id=prev>&larr; Prev</button><button id=next>Next &rarr;</button><input type=range id=slide min=0 value=0></div></section>
<div class=grid id=kpis></div>
<section class=card><h2>Days in this period <span class=n>(click a row)</span></h2><div class=row style="margin-bottom:6px"><label style="flex-direction:row;align-items:center;gap:6px"><input type=checkbox id=onlytrades style="width:auto"> only days with fills or decisions</label><label>Symbol<input id=symf placeholder="e.g. SQQQ" style="width:110px"></label></div><div id=days style="max-height:300px;overflow:auto"></div></section>
<section class=card><h2>Equity and the selected day</h2><canvas id=eq height=170></canvas><p class=n>Log scale, zoomed to the period. Click a chart to jump to that day; arrow keys also step.</p></section>
<section class=card><h2>Holdings timeline <span class=n>(every session; a coloured cell means held after that close)</span></h2><canvas id=tl></canvas><div class=n id=tllegend></div></section>
<section class=card><h2>Held through this session <span class=n>(after the fills below)</span></h2><div id=hold></div></section>
<section class=card><h2>Decided at this close <span class=n>(filled at the next session's start)</span></h2><div id=dec></div></section>
<section class=card><h2>Filled at the start of this session <span class=n>(decided at the previous close)</span></h2><div id=ord></div></section>
<section class=card><h2>Trades closed today</h2><div id=trd></div></section>
<section class=card><h2>Best and worst days in this period</h2><div class=row id=bw style="align-items:flex-start"></div></section>
</main><script>
const DATA=__DATA__;
const LONGS=new Set(["TQQQ","SOXL","TECL","SPXL","QLD","QQQ","UPRO","TNA"]),INV=new Set(["SQQQ","SOXS","TECS","PSQ","UVXY","SPXS"]);
const $=id=>document.getElementById(id);let S=null,i=0;
const fmt=(x,d=0)=>x==null?"n/a":x.toLocaleString("en-US",{minimumFractionDigits:d,maximumFractionDigits:d});
const pct=(x,d=2)=>x==null?"n/a":(x*100).toFixed(d)+"%",cls=x=>x>0?"pos":x<0?"neg":"";
function prep(s){const n=s.nav.length;s.ret=s.nav.map((v,k)=>k?v/s.nav[k-1]-1:0);let pk=-1,peak=0;s.dd=[];s.since=[];
 s.nav.forEach((v,k)=>{if(v>=peak){peak=v;pk=k}s.dd.push(v/peak-1);s.since.push(k-pk)});
 s.rank=[...s.ret.keys()].slice(1).sort((a,b)=>s.ret[a]-s.ret[b]);s.rk={};s.rank.forEach((k,r)=>s.rk[k]=r+1);
 s.snap=[];let cur={};s.dates.forEach((d,k)=>{if(s.pos[d])cur=s.pos[d];s.snap.push(cur)});
 const tot={};s.snap.forEach(c=>Object.keys(c).forEach(sym=>{if(Math.abs(c[sym][0])>1e-9)tot[sym]=(tot[sym]||0)+1}));
 s.syms=Object.keys(tot).sort((a,b)=>(LONGS.has(b)-LONGS.has(a))||(INV.has(b)-INV.has(a))||tot[b]-tot[a]);return s}
DATA.forEach(prep);
function tag(sym){return LONGS.has(sym)?"#1f8a4c":INV.has(sym)?"#c43d3d":"#7a8696"}
function table(h,rows,cls2){return rows.length?"<table><tr>"+h.map((x,k)=>`<th class="${k?"r":""}">${x}</th>`).join("")+"</tr>"+rows.join("")+"</table>":"<p class=n>None.</p>"}
function draw(){const s=S,d=s.dates[i],snap=s.snap[i],prev=i?s.snap[i-1]:{};
 $("date").value=d;$("slide").value=i;
 const k=(a,b,c)=>`<div class=card><div class=k>${a}</div><div class="v ${c||""}">${b}</div></div>`;
 const r=s.ret[i],tr=(n)=>i>=n?s.nav[i]/s.nav[i-n]-1:null;
 $("kpis").innerHTML=k("Equity",`$${fmt(s.nav[i])}`)+k("Day return",pct(r),cls(r))+(i?k("Day rank",`${s.rk[i]} of ${s.dates.length-1}`):"")
  +k("Drawdown",pct(s.dd[i]),cls(s.dd[i]))+k("Days since peak",s.since[i])+k("21-session return",pct(tr(21)),cls(tr(21)))+k("63-session return",pct(tr(63)),cls(tr(63)))
  +k("Reported long exposure",s.expo[i]==null?"n/a":pct(s.expo[i],1))+k("Turnover",s.turn[i]==null?"n/a":pct(s.turn[i],1));
 const syms=[...new Set([...Object.keys(snap),...Object.keys(prev)])].filter(x=>Math.abs((snap[x]||[0])[0])>1e-9||Math.abs((prev[x]||[0])[0])>1e-9);
 const val=x=>snap[x]?snap[x][0]*snap[x][1]:0,total=syms.reduce((a,x)=>a+Math.max(val(x),0),0);
 syms.sort((a,b)=>val(b)-val(a));
 $("hold").innerHTML=(syms.length?"":"<p class=n>No positions (cash) after this close.</p>")+table(["Symbol","Shares","Change today","Last fill price","Priced on","Approx. value","Share of approx. value"],syms.map(x=>{
  const sh=snap[x]?snap[x][0]:0,ch=sh-(prev[x]?prev[x][0]:0);
  return `<tr class="${ch?"chg":""}"><td><b style="color:${tag(x)}">${x}</b></td><td class=r>${fmt(sh)}</td><td class="r ${cls(ch)}">${ch?(ch>0?"+":"")+fmt(ch):"-"}</td><td class=r>${snap[x]?fmt(snap[x][1],2):"-"}</td><td class=r>${snap[x]?snap[x][2]:"-"}</td><td class=r>${snap[x]?"$"+fmt(val(x)):"-"}</td><td class=r>${total>0&&val(x)>0?pct(val(x)/total,1):"-"}</td></tr>`}));
 $("hold").innerHTML+=`<p class=n>Approx. total in positions $${fmt(total)} vs equity $${fmt(s.nav[i])}; the export reports long exposure of ${s.expo[i]==null?"n/a":pct(s.expo[i],1)}.</p>`;
 const ordRow=o=>`<tr><td><b style="color:${tag(o[0])}">${o[0]}</b></td><td class="r ${cls(o[1])}">${o[1]>0?"+":""}${fmt(o[1])}</td><td class=r>${fmt(o[2],2)}</td><td>${o[3]}</td></tr>`;
 $("dec").innerHTML=table(["Symbol","Quantity","Expected fill price","Tag"],(s.decided[d]||[]).map(ordRow));
 $("ord").innerHTML=table(["Symbol","Quantity","Fill price","Tag"],(s.orders[d]||[]).map(o=>`<tr><td><b style="color:${tag(o[0])}">${o[0]}</b></td><td class="r ${cls(o[1])}">${o[1]>0?"+":""}${fmt(o[1])}</td><td class=r>${fmt(o[2],2)}</td><td>${o[3]}</td></tr>`));
 $("trd").innerHTML=table(["Symbol","Opened","Quantity","Entry","Exit","P&L","Fees"],(s.trades[d]||[]).map(t=>`<tr><td><b style="color:${tag(t[0])}">${t[0]}</b></td><td>${t[1]}</td><td class=r>${fmt(t[2])}</td><td class=r>${fmt(t[3],2)}</td><td class=r>${fmt(t[4],2)}</td><td class="r ${cls(t[5])}">${fmt(t[5],2)}</td><td class=r>${fmt(t[6],2)}</td></tr>`));
 markRow();paint()}
function setup(c,h){const w=c.clientWidth,r=window.devicePixelRatio||1;c.width=w*r;c.height=h*r;c.style.height=h+"px";const x=c.getContext("2d");x.scale(r,r);return [x,w,h]}
const css=n=>getComputedStyle(document.documentElement).getPropertyValue(n).trim();
let lo=0,hi=0,preset="All";
function paint(){const s=S,m=hi-lo+1;
 let [x,w,h]=setup($("eq"),170),mn=Infinity,mx=-Infinity;for(let k=lo;k<=hi;k++){mn=Math.min(mn,s.nav[k]);mx=Math.max(mx,s.nav[k])}
 const a=Math.log10(mn),b=Math.log10(mx)||1,rng=(b-a)||1,L=8,B=8,den=Math.max(m-1,1);
 x.clearRect(0,0,w,h);x.strokeStyle=css("--line");x.beginPath();x.moveTo(L,h-B);x.lineTo(w,h-B);x.stroke();
 x.strokeStyle=css("--accent");x.lineWidth=1.5;x.beginPath();for(let k=lo;k<=hi;k++){const px=L+(k-lo)/den*(w-L),py=B+(b-Math.log10(s.nav[k]))/rng*(h-2*B);k===lo?x.moveTo(px,py):x.lineTo(px,py)}x.stroke();
 const sx=L+(i-lo)/den*(w-L);x.strokeStyle=css("--down");x.lineWidth=1;x.beginPath();x.moveTo(sx,0);x.lineTo(sx,h);x.stroke();
 x.fillStyle=css("--mute");x.font="11px system-ui";x.fillText("$"+fmt(mn),L+2,h-12);x.fillText("$"+fmt(mx),L+2,12);
 const n2=s.syms.length,rh=Math.max(10,Math.min(16,220/n2)),tc=$("tl");[x,w,h]=setup(tc,n2*rh+16);x.clearRect(0,0,w,h);const lab=64,cw=(w-lab)/m;
 x.font="11px system-ui";s.syms.forEach((sym,row)=>{x.fillStyle=css("--mute");x.fillText(sym,2,row*rh+rh-3);x.fillStyle=tag(sym);
  for(let k=lo;k<=hi;k++){const c=s.snap[k];if(c[sym]&&Math.abs(c[sym][0])>1e-9)x.fillRect(lab+(k-lo)*cw,row*rh+1,Math.max(cw,1),rh-2)}});
 x.strokeStyle=css("--ink");x.beginPath();x.moveTo(lab+(i-lo)*cw,0);x.lineTo(lab+(i-lo)*cw,n2*rh);x.stroke();
 const mark={};for(let k=lo;k<=hi;k++){const key=m>400?s.dates[k].slice(0,4):s.dates[k].slice(0,7);if(!(key in mark))mark[key]=k}
 x.fillStyle=css("--mute");let lastx=-99;Object.entries(mark).forEach(([key,k])=>{const px=lab+(k-lo)*cw;if(px-lastx>46){x.fillText(key,px,n2*rh+12);lastx=px}});
 $("tllegend").innerHTML='<span style="color:#1f8a4c">■</span> leveraged long &nbsp;<span style="color:#c43d3d">■</span> inverse or volatility &nbsp;<span style="color:#7a8696">■</span> defensive or other'}
function jump(e,el,lab){const r=el.getBoundingClientRect(),f=(e.clientX-r.left-lab)/(r.width-lab);i=Math.max(lo,Math.min(hi,lo+Math.round(f*(hi-lo))));draw()}
$("eq").onclick=e=>jump(e,$("eq"),8);$("tl").onclick=e=>jump(e,$("tl"),64);
function held(k){return Object.entries(S.snap[k]).filter(([a,b])=>Math.abs(b[0])>1e-9).map(([a])=>a)}
function rowsFor(){const s=S,only=$("onlytrades").checked,f=$("symf").value.trim().toUpperCase(),out=[];
 for(let k=lo;k<=hi;k++){const act=(s.orders[s.dates[k]]||[]).length+(s.decided[s.dates[k]]||[]).length;if(only&&!act)continue;
  const hs=held(k);if(f&&!hs.includes(f)&&!(s.orders[s.dates[k]]||[]).some(o=>o[0]===f)&&!(s.decided[s.dates[k]]||[]).some(o=>o[0]===f))continue;out.push(k)}return out}
function days(){const s=S,ks=rowsFor();$("days").innerHTML=table(["Date","Return","Equity","Drawdown","Held through the session","Fills / decisions"],ks.map(k=>`<tr data-k="${k}" style="cursor:pointer" onclick="i=${k};draw()"><td>${s.dates[k]}</td><td class="r ${cls(s.ret[k])}">${pct(s.ret[k])}</td><td class=r>$${fmt(s.nav[k])}</td><td class="r ${cls(s.dd[k])}">${pct(s.dd[k],1)}</td><td class=r>${held(k).map(x=>`<b style="color:${tag(x)}">${x}</b>`).join(" ")||"cash"}</td><td class=r>${(s.orders[s.dates[k]]||[]).length} / ${(s.decided[s.dates[k]]||[]).length}</td></tr>`))}
function markRow(){document.querySelectorAll("#days tr.sel").forEach(r=>r.classList.remove("sel"));const r=document.querySelector(`#days tr[data-k="${i}"]`);if(r){r.classList.add("sel");const box=$("days");const top=r.offsetTop-box.offsetTop;if(top<box.scrollTop||top>box.scrollTop+box.clientHeight-30)box.scrollTop=top-60}}
function lists(){const s=S,ks=[];for(let k=Math.max(lo,1);k<=hi;k++)ks.push(k);ks.sort((a,b)=>s.ret[a]-s.ret[b]);
 const mk=(arr)=>table(["Date","Return","Equity"],arr.map(k=>`<tr style="cursor:pointer" onclick="i=${k};draw()"><td>${s.dates[k]}</td><td class="r ${cls(s.ret[k])}">${pct(s.ret[k])}</td><td class=r>$${fmt(s.nav[k])}</td></tr>`));
 $("bw").innerHTML=`<div style="flex:1;min-width:260px"><b>Best 10</b>${mk(ks.slice(-10).reverse())}</div><div style="flex:1;min-width:260px"><b>Worst 10</b>${mk(ks.slice(0,10))}</div>`}
function setPeriod(a,b,name){const s=S,n=s.dates.length;lo=Math.max(0,Math.min(a,n-1));hi=Math.max(lo,Math.min(b,n-1));preset=name||"Custom";
 i=Math.max(lo,Math.min(hi,i));$("from").min=$("to").min=s.dates[0];$("from").max=$("to").max=s.dates[n-1];$("from").value=s.dates[lo];$("to").value=s.dates[hi];
 $("slide").min=lo;$("slide").max=hi;let mdd=0;for(let k=lo;k<=hi;k++){mdd=Math.min(mdd,s.nav[k]/Math.max(...s.nav.slice(lo,k+1))-1)}
 $("pinfo").textContent=`${hi-lo+1} sessions, ${s.dates[lo]} to ${s.dates[hi]}; equity ${pct(s.nav[hi]/s.nav[lo]-1,1)}; worst drawdown inside the period ${pct(mdd,1)}`;
 $("presets").innerHTML="";presetsList().forEach(([label,x,y])=>{const bt=document.createElement("button");bt.textContent=label;bt.style.fontWeight=label===preset?"700":"400";bt.onclick=()=>setPeriod(x,y,label);$("presets").appendChild(bt)});
 lists();days();draw()}
function presetsList(){const s=S,n=s.dates.length,out=[["All",0,n-1]],years=[...new Set(s.dates.map(d=>d.slice(0,4)))];
 years.forEach(y=>{const a=s.dates.findIndex(d=>d.startsWith(y)),b=s.dates.length-1-[...s.dates].reverse().findIndex(d=>d.startsWith(y));out.push([y,a,b])});
 [["Last 12 months",252],["Last 6 months",126],["Last 3 months",63],["Last month",21]].forEach(([l,c])=>out.push([l,Math.max(0,n-1-c),n-1]));
 let mi=0;for(let k=0;k<n;k++)if(s.dd[k]<s.dd[mi])mi=k;let rec=n-1;for(let k=mi+1;k<n;k++)if(s.dd[k]>=0){rec=k;break}
 out.push(["Deepest drawdown",mi-s.since[mi],rec]);return out}
function choose(k){S=DATA[k];$("snote").textContent=S.note||"";i=S.dates.length-1;setPeriod(0,S.dates.length-1,"All")}
DATA.forEach((d,k)=>$("sel").add(new Option(d.name,k)));$("sel").onchange=e=>choose(+e.target.value);
function nearest(v,up){const n=S.dates.length;if(up){let k=S.dates.length-1;while(k>=0&&S.dates[k]>v)k--;return Math.max(k,0)}const k=S.dates.findIndex(d=>d>=v);return k<0?n-1:k}
$("from").onchange=e=>setPeriod(nearest(e.target.value,false),hi,"Custom");$("to").onchange=e=>setPeriod(lo,nearest(e.target.value,true),"Custom");
$("date").onchange=e=>{const k=nearest(e.target.value,false);if(k<lo||k>hi)setPeriod(Math.min(lo,k),Math.max(hi,k),"Custom");i=k;draw()};
$("slide").oninput=e=>{i=+e.target.value;draw()};$("prev").onclick=()=>{i=Math.max(lo,i-1);draw()};$("next").onclick=()=>{i=Math.min(hi,i+1);draw()};
$("onlytrades").onchange=days;$("symf").oninput=()=>{days();markRow()};
addEventListener("keydown",e=>{if(e.target.tagName==="INPUT"&&e.target.type!=="range"&&e.target.type!=="checkbox")return;if(e.key==="ArrowLeft"){i=Math.max(lo,i-1);draw()}if(e.key==="ArrowRight"){i=Math.min(hi,i+1);draw()}});
addEventListener("resize",()=>paint());choose(0);
</script></body></html>"""


def render(datasets):
    payload = json.dumps(datasets, allow_nan=False, separators=(",", ":")).replace("</", "<\\/")
    return _HTML.replace("__DATA__", payload)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--strategy", action="append", default=[], metavar="NAME=CLOSE_PATH,EXPORT")
    parser.add_argument("--dataset", action="append", default=[], metavar="NAME=PATH", help="prebuilt dataset JSON (e.g. a replay)")
    parser.add_argument("--out", type=Path, default=ROOT / ".local/progress/holdings.html")
    args = parser.parse_args(argv)
    datasets = []
    for item in args.strategy:
        name, sep, rest = item.partition("=")
        close_path, comma, export = rest.partition(",")
        if not sep or not comma:
            parser.error("--strategy needs NAME=CLOSE_PATH,EXPORT")
        datasets.append(build_dataset(name, json.loads(Path(close_path).read_text()), json.loads(Path(export).read_text())))
    for item in args.dataset:
        name, sep, path = item.partition("=")
        if not sep:
            parser.error("--dataset needs NAME=PATH")
        data = json.loads(Path(path).read_text())
        data["name"] = name
        datasets.append(data)
    if not datasets:
        parser.error("Give at least one --strategy or --dataset.")
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(render(datasets))
    for d in datasets:
        print(f"{d['name']}: {len(d['dates'])} sessions, {sum(len(v) for v in d['orders'].values())} orders mapped, {d['unmatched_orders']} unmatched")
    print(f"Wrote {args.out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
