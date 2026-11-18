"""The Pipeline page: stage view, compare, trust and cycle log as one static HTML page.

A pure render over registry records, the stage view model and the incumbents declaration. It
shows no verdict: effects are per matched pair on net CAGR versus max drawdown, tradeoffs stay
visible, and eligibility is `unassessed` for every run because no per-run eligibility record
exists. All text is HTML-escaped; missing metrics render as n/a, never zero.
"""
import html

from research.control.analysis_view import trust_rows
from research.control.registry_views import _num, _pct, _underwater
from research.control.stage_map import STAGES

_CSS = """:root{--bg:#f6f7f9;--card:#fff;--ink:#14181f;--mute:#5b6573;--line:#dfe3e8;--acc:#2f6fdb}
@media (prefers-color-scheme:dark){:root{--bg:#0e1116;--card:#171b22;--ink:#e8ecf2;--mute:#9aa5b4;--line:#2a313c;--acc:#6aa0ff}}
*{box-sizing:border-box}body{margin:0;padding:16px;background:var(--bg);color:var(--ink);font:14px/1.4 system-ui,-apple-system,sans-serif}
h1{margin:0 0 4px}h2{margin:28px 0 8px}.muted{color:var(--mute)}nav a{margin-right:12px;color:var(--acc)}
.cards{display:grid;grid-template-columns:repeat(auto-fill,minmax(230px,1fr));gap:10px}
.card{background:var(--card);border:1px solid var(--line);border-radius:8px;padding:10px}
.card h3{margin:0 0 4px;font-size:15px}.badge{display:inline-block;border:1px solid var(--line);border-radius:10px;padding:0 8px;margin:2px 4px 2px 0;font-size:12px}
table{border-collapse:collapse;width:100%;background:var(--card);margin:6px 0 14px}
th,td{border:1px solid var(--line);padding:4px 8px;text-align:left;vertical-align:top}th{color:var(--mute);font-weight:600}
tr.incumbent td{outline:2px solid var(--acc);outline-offset:-2px}"""

_SCRIPT = """document.querySelectorAll("section.context").forEach(function(sec){
 var sel=sec.querySelector("select"),rows=[].slice.call(sec.querySelectorAll("tbody tr"));
 if(!sel)return;
 function num(v){return v===""?null:parseFloat(v)}
 function pts(a,b){return a===null||b===null?"n/a":((a-b)*100).toFixed(2)}
 function update(){var base=rows.filter(function(r){return r.dataset.id===sel.value})[0];if(!base)return;
  var bc=num(base.dataset.cagr),bd=num(base.dataset.dd);
  rows.forEach(function(r){r.classList.toggle("incumbent",r===base);
   r.querySelector(".dcagr").textContent=r===base?"incumbent":pts(num(r.dataset.cagr),bc);
   r.querySelector(".ddd").textContent=r===base?"incumbent":pts(num(r.dataset.dd),bd)})}
 sel.onchange=update;update()})"""


def _e(value):
    return html.escape(str(value))


def _attr(value):
    return "" if value is None else repr(value)


def _places(model):
    place = {}
    for stage, cell in model["stages"].items():
        for rid in cell["records"]:
            place[rid] = stage
    place.update({rid: "unclassified" for rid in model["unclassified"]})
    place.update({rid: "unattributable" for rid in model["unattributable"]})
    return place


def _badges(counts, kind):
    return "".join(f'<span class="badge" data-{kind}="{_e(key)}">{_e(key)} ×{n}</span>'
                   for key, n in sorted(counts.items()))


def _points(value):
    return "n/a" if value is None else f"{value * 100:+.2f}"


def _pair_line(pair, by_id):
    challenger = by_id[pair["challenger"]]["name"]
    control = by_id[pair["control"]]["name"] if pair["control"] in by_id else "no control named"
    head = (f'<b>{_e(challenger)}</b> vs <b>{_e(control)}</b> '
            f'<span class="badge" data-disposition="{_e(pair["disposition"])}">{_e(pair["disposition"])}</span>')
    if pair["status"] != "matched":
        return f'<div class="pair">{head} <span class="badge" data-effect="ambiguous control">ambiguous control</span></div>'
    delta = pair["delta"]
    return (f'<div class="pair">{head} <span class="badge" data-effect="{_e(pair["effect"])}">{_e(pair["effect"])}</span><br>'
            f'net CAGR {_points(delta["net_cagr"])} pt, max DD {_points(delta["max_drawdown"])} pt</div>')


def _records_detail(cell, by_id):
    if not cell["records"]:
        return ""
    items = "".join(f'<li><b>{_e(by_id[i]["name"])}</b> ({_e(by_id[i]["disposition"])}): {_e(by_id[i]["lesson"])}</li>'
                    for i in cell["records"])
    return f'<details><summary>records and lessons</summary><ul>{items}</ul></details>'


def _stage_view(model, incumbents, by_id):
    cards = []
    for stage in STAGES:
        cell, declared = model["stages"][stage], incumbents.get(stage)
        cards.append(
            f'<div class="card" data-stage="{_e(stage)}"><h3>{_e(stage)}</h3>'
            f'<div>{_e(declared["algorithm"]) if declared else "undeclared"}'
            f'{" · " + _e(declared["availability"]) if declared else ""}</div>'
            f'<div class="muted">{len(cell["records"])} records · {len(cell["pairs"])} pairs</div>'
            f'<div>{_badges(cell["effects"], "effect") or ("no matched control" if cell["records"] else "no evidence")}</div>'
            f'<div>{_badges(cell["dispositions"], "disposition")}</div>'
            f'{"".join(_pair_line(p, by_id) for p in cell["pairs"])}{_records_detail(cell, by_id)}</div>')
    summary = (f'{len(model["unclassified"])} unclassified · {len(model["unattributable"])} unattributable'
               f' · {sum(len(v) for v in model["contexts"].values())} records in total')
    return (f'<h2 id="stage-view">Stage view</h2><p class="muted">Counts are records. Effects are per matched '
            f'pair on net CAGR versus max drawdown; a cell is never rolled up to one label. {summary}</p>'
            f'<div class="cards">{"".join(cards)}</div>')


def _compare(model, by_id):
    sections = []
    for context, ids in model["contexts"].items():
        rows = [by_id[i] for i in ids]
        controls = [r for r in rows if r["disposition"] == "control"]
        picker = ("" if not controls else '<label>Incumbent <select>' + "".join(
            f'<option value="{_e(r["record_id"])}"{" selected" if n == 0 else ""}>{_e(r["name"])}</option>'
            for n, r in enumerate(controls)) + "</select></label>")
        body = "".join(
            f'<tr data-id="{_e(r["record_id"])}" data-cagr="{_attr(r["metrics"].get("net_cagr"))}" '
            f'data-dd="{_attr(r["metrics"].get("max_drawdown"))}"><td>{_e(r["name"])}</td><td>{_e(r["disposition"])}</td>'
            f'<td>{_pct(r["metrics"].get("net_cagr"))}</td><td>{_pct(r["metrics"].get("max_drawdown"))}</td>'
            f'<td class="dcagr">—</td><td class="ddd">—</td><td>{_underwater(r["metrics"])}</td>'
            f'<td>{_num(r["metrics"].get("calmar"))}</td><td>{_num(r["metrics"].get("sharpe"), 3)}</td>'
            f'<td class="trust">unassessed</td></tr>' for r in rows)
        sections.append(
            f'<section class="context" data-context="{_e(context)}"><h3>{_e(context)}</h3>'
            f'{picker or "<p class=muted>No control recorded in this context.</p>"}'
            '<table><thead><tr><th>Variant</th><th>Disposition</th><th>Net CAGR</th><th>Max DD</th>'
            '<th>Δ CAGR (pt)</th><th>Δ max DD (pt)</th><th>Underwater (sessions / days)</th>'
            f'<th>Calmar</th><th>Sharpe</th><th>Trust</th></tr></thead><tbody>{body}</tbody></table></section>')
    return ('<h2 id="compare">Compare</h2><p class="muted">Compare only inside one context. Deltas are against the '
            'selected control, in percentage points; Calmar and Sharpe are diagnostics.</p>'
            + ("".join(sections) or '<p class="muted">No records.</p>'))


def _analysis_trust(analyses):
    rows = "".join(
        f'<tr data-analysis="{_e(r["analysis_id"])}"><td>{_e(r["spec_id"])}</td><td>{_e(r["analysis_id"])}</td>'
        f'<td>{_e(r["psr"])}<br><span class="muted">{_e(r["psr_reason"])}</span></td>'
        f'<td>{_e(r["dsr"])}<br><span class="muted">{_e(r["dsr_reason"])}</span></td>'
        f'<td>{_e(r["pbo"])}<br><span class="muted">{_e(r["pbo_reason"])}</span></td>'
        f'<td>{_e(r["lookahead"])}</td><td>{_e(r["tearsheet"])}</td></tr>' for r in trust_rows(analyses))
    return ('<h3>Analysis trust statistics</h3><p class="muted">From the latest analysis per spec; a null statistic '
            'shows its reason. These describe an analysis, not a registry run, so run eligibility stays unassessed.</p>'
            '<table><thead><tr><th>Spec</th><th>Analysis</th><th>PSR</th><th>DSR</th><th>PBO</th><th>Lookahead</th>'
            f'<th>Tearsheet</th></tr></thead><tbody>{rows}</tbody></table>')


def _trust(records, analyses=None):
    rows = "".join(
        f'<tr><td>{_e(r["name"])}</td><td>{_e(r["evidence_class"])}</td>'
        f'<td>{_e(r.get("evidence_status") or "-")}</td><td>{_e((r.get("refs") or {}).get("receipt") or "none")}</td>'
        f'<td data-eligibility="unassessed">unassessed</td></tr>' for r in records)
    return ('<h2 id="trust">Trust</h2><p class="muted">No per-run eligibility record exists yet, so every run is '
            'unassessed; evidence status is shown verbatim and is not mapped to pass or fail.</p>'
            '<table><thead><tr><th>Run</th><th>Evidence class</th><th>Evidence status</th><th>Receipt</th>'
            f'<th>Eligibility</th></tr></thead><tbody>{rows}</tbody></table>'
            + (_analysis_trust(analyses) if analyses else ""))


def _cycle_log(records, place):
    ordered = sorted(records, key=lambda r: (r["logged_at"], r["record_id"]), reverse=True)
    rows = "".join(
        f'<tr><td>{_e(r["logged_at"][:10])}</td><td>{_e(r["record_id"])}</td><td>{_e(place[r["record_id"]])}</td>'
        f'<td>{_e(r["disposition"])}</td><td>{_e(r.get("outcome") or "-")}</td><td>{_e(r["lesson"])}</td></tr>'
        for r in ordered)
    return ('<h2 id="cycle-log">Cycle log</h2><table><thead><tr><th>Logged</th><th>Record</th><th>Stage</th>'
            f'<th>Disposition</th><th>Outcome</th><th>Lesson</th></tr></thead><tbody>{rows}</tbody></table>')


def render_page(model, records, incumbents, built, analyses=None):
    by_id = {r["record_id"]: r for r in records}
    place = _places(model)
    for r in records:
        place.setdefault(r["record_id"], "unclassified")
    return (f'<!doctype html><html lang="en"><head><meta charset="utf-8">'
            f'<meta name="viewport" content="width=device-width,initial-scale=1"><title>Pipeline</title>'
            f'<style>{_CSS}</style></head><body><h1>Pipeline</h1>'
            f'<p class="muted">Built {_e(built)} · development evidence only · derived from the registry, '
            f'the stage map and the incumbents file; nothing here is an adoption verdict.</p>'
            '<nav><a href="#stage-view">Stage view</a><a href="#compare">Compare</a><a href="#trust">Trust</a>'
            '<a href="#cycle-log">Cycle log</a></nav>'
            f'{_stage_view(model, incumbents, by_id)}{_compare(model, by_id)}{_trust(records, analyses)}{_cycle_log(records, place)}'
            f'<script>{_SCRIPT}</script></body></html>')
