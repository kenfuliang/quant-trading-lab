"""Progress model and static page for the path to real money.

Pure: callers pass already-read inputs, so nothing here touches files, the network or a
broker. The structured source of gate status is `research/registry/gates.json`; the page
only reports it next to the experiment registry, the forward clock and ops health.
A gate item may be `met` only with evidence that exists. No percentage is invented:
bars show counts of items by status.
"""
from datetime import date
import html

from research.control.experiment_registry import CLASSES, DRAWDOWN_TOLERANCE
from research.control.registry_views import learning_curve

STATUSES = ("met", "partial", "blocked", "open")
OWNERS = ("user", "agent")


def validate_gates(data, exists):
    errors = []
    if not isinstance(data, dict) or data.get("schema") != "gates/v1" or not isinstance(data.get("gates"), list):
        return ["gates: expected schema gates/v1 with a gates list"]
    seen = set()
    for gate in data["gates"]:
        if not isinstance(gate, dict) or not gate.get("id") or not gate.get("items"):
            errors.append(f"gate {gate.get('id') if isinstance(gate, dict) else gate!r}: needs an id and items")
            continue
        for item in gate["items"]:
            label = item.get("id", "?") if isinstance(item, dict) else "?"
            if not isinstance(item, dict) or item.get("id") in seen or not str(item.get("id", "")).startswith(gate["id"] + "."):
                errors.append(f"{label}: id must be unique and start with {gate['id']}.")
                continue
            seen.add(item["id"])
            if item.get("status") not in STATUSES:
                errors.append(f"{label}: status must be one of {', '.join(STATUSES)}")
            if item.get("owner") not in OWNERS:
                errors.append(f"{label}: owner must be one of {', '.join(OWNERS)}")
            if not str(item.get("text", "")).strip():
                errors.append(f"{label}: text is empty")
            evidence = item.get("evidence")
            if not isinstance(evidence, list):
                errors.append(f"{label}: evidence must be a list")
                continue
            if item.get("status") == "met" and not evidence:
                errors.append(f"{label}: a met item needs evidence")
            for path in evidence:
                if not exists(path):
                    errors.append(f"{label}: evidence {path} does not exist")
    return errors


def forward_clock(forward, today):
    if not forward:
        return {"state": "none"}
    start, end = date.fromisoformat(forward["start"]), date.fromisoformat(forward["end"])
    total = (end - start).days + 1
    if today < start:
        return {"state": "pending", "days_until_start": (start - today).days, "total_days": total,
                "start": forward["start"], "end": forward["end"], "holdout_id": forward["holdout_id"]}
    day = min((today - start).days + 1, total)
    return {"state": "complete" if today > end else "running", "day": day, "total_days": total,
            "start": forward["start"], "end": forward["end"], "holdout_id": forward["holdout_id"]}


def build_model(gates, records, forward, shadow, health, ledger, today):
    rows = []
    for gate in gates["gates"]:
        counts = {s: sum(1 for i in gate["items"] if i["status"] == s) for s in STATUSES}
        rows.append({"id": gate["id"], "name": gate["name"], "counts": counts, "total": len(gate["items"]),
                     "items": gate["items"]})
    items = [i for g in gates["gates"] for i in g["items"]]
    waiting = [dict(i, gate=g["id"]) for g in gates["gates"] for i in g["items"]
               if i["owner"] == "user" and i["status"] != "met"]
    classes = {c: sum(1 for r in records if r["evidence_class"] == c) for c in CLASSES}
    dispositions = {}
    for r in records:
        dispositions[r["disposition"]] = dispositions.get(r["disposition"], 0) + 1
    curve = {}
    for c in CLASSES:
        count, steps = learning_curve(records, c)
        curve[c] = {"experiments": count, "best": steps[-1][3] if steps else None}
    return {"as_of": today.isoformat(), "gates": rows,
            "totals": {s: sum(1 for i in items if i["status"] == s) for s in STATUSES} | {"all": len(items)},
            "waiting": waiting, "records": len(records), "classes": classes, "dispositions": dispositions,
            "curve": curve, "forward": forward_clock(forward, today), "shadow": shadow, "health": health,
            "ledger": ledger}


_CSS = """
:root{--bg:#f6f7f9;--card:#fff;--ink:#14181f;--mute:#5b6573;--line:#dfe3e8;--met:#1f8a4c;--partial:#c98a00;--blocked:#c43d3d;--open:#aeb6c2;--accent:#2457d6}
@media (prefers-color-scheme:dark){:root:not([data-theme=light]){--bg:#0e1116;--card:#171b22;--ink:#e8ecf2;--mute:#9aa5b4;--line:#2a313c;--met:#3cb371;--partial:#e0a526;--blocked:#e56b6b;--open:#4a5361;--accent:#7aa2ff}}
*{box-sizing:border-box}body{margin:0;background:var(--bg);color:var(--ink);font:15px/1.5 system-ui,-apple-system,Segoe UI,sans-serif}
main{max-width:1080px;margin:0 auto;padding:24px 16px 64px}h1{font-size:22px;margin:0 0 4px}h2{font-size:16px;margin:28px 0 10px}
.sub{color:var(--mute);margin:0 0 20px}.grid{display:grid;gap:12px;grid-template-columns:repeat(auto-fit,minmax(200px,1fr))}
.card{background:var(--card);border:1px solid var(--line);border-radius:10px;padding:14px 16px}
.k{color:var(--mute);font-size:12px;text-transform:uppercase;letter-spacing:.04em}.v{font-size:26px;font-weight:650;line-height:1.2}.n{color:var(--mute);font-size:13px}
.bar{display:flex;height:14px;border-radius:7px;overflow:hidden;background:var(--line);gap:2px}.bar span{display:block;min-width:4px}
.met{background:var(--met)}.partial{background:var(--partial)}.blocked{background:var(--blocked)}.open{background:var(--open)}
.gate{display:grid;grid-template-columns:minmax(150px,230px) 1fr 170px;gap:12px;align-items:center;padding:8px 0;border-bottom:1px solid var(--line)}
.gate:last-child{border-bottom:0}.cnt{color:var(--mute);font-size:13px;text-align:right}
.legend{display:flex;flex-wrap:wrap;gap:14px;font-size:13px;color:var(--mute);margin:6px 0 0}.legend i{display:inline-block;width:10px;height:10px;border-radius:3px;margin-right:5px}
table{width:100%;border-collapse:collapse;font-size:14px}th,td{text-align:left;padding:7px 8px;border-bottom:1px solid var(--line);vertical-align:top}th{color:var(--mute);font-weight:600;font-size:12px}
.tag{display:inline-block;padding:1px 8px;border-radius:9px;font-size:12px;color:#fff}.tag.open{color:var(--ink)}
details{margin:6px 0}summary{cursor:pointer;font-weight:600;padding:4px 0}code{font-size:13px}
@media (max-width:640px){.gate{grid-template-columns:1fr}.cnt{text-align:left}}
"""


def _e(value):
    return html.escape(str(value))


def _bar(counts, total):
    spans = "".join(f'<span class="{s}" style="flex:{counts[s]}" title="{counts[s]} {s}"></span>' for s in STATUSES if counts[s])
    return f'<div class="bar" role="img" aria-label="{_e(", ".join(f"{counts[s]} {s}" for s in STATUSES))} of {total}">{spans}</div>'


def _pct(value):
    return "none yet" if value is None else f"{value * 100:.1f}%"


def render_html(model, link=lambda path: None):
    t, fw, sh, hl, led = model["totals"], model["forward"], model["shadow"], model["health"], model["ledger"]
    if fw["state"] == "none":
        clock = ("No window", "")
    elif fw["state"] == "pending":
        days = fw["days_until_start"]
        clock = (f"Starts in {days} day{'s' if days != 1 else ''}", f"{fw['holdout_id']} · {fw['start']} to {fw['end']} · {fw['total_days']} days")
    else:
        clock = (f"Day {fw['day']} of {fw['total_days']}", f"{fw['holdout_id']} · {fw['start']} to {fw['end']} · {fw['state']}")
    health = ("No status yet", "run scripts/ops_status.py") if not hl else (
        "Healthy" if hl.get("healthy") else "Needs attention",
        " · ".join(f"{c['name']} {c['state']}" for c in hl.get("checks", [])))
    best_dev = model["curve"]["development"]["best"]
    out = [f"<!doctype html><html lang=en><head><meta charset=utf-8><meta name=viewport content='width=device-width,initial-scale=1'>"
           f"<title>Path to real money</title><style>{_CSS}</style></head><body><main>",
           f"<h1>Path to real money</h1><p class=sub>As of {_e(model['as_of'])} · generated from the gates file, the experiment registry, "
           "the trial ledger and ops status. Nothing here authorizes an order.</p><div class=grid>",
           f'<div class=card><div class=k>Gate items met</div><div class=v>{t["met"]} / {t["all"]}</div><div class=n>{t["partial"]} partial · {t["blocked"]} blocked · {t["open"]} open</div></div>',
           f'<div class=card><div class=k>Forward clock</div><div class=v>{_e(clock[0])}</div><div class=n>{_e(clock[1])}</div></div>',
           f'<div class=card><div class=k>Shadow runs</div><div class=v>{sh["runs"]}</div><div class=n>{sh["decisions"]} decisions recorded · last {_e(sh["last_run"] or "never")}</div></div>',
           f'<div class=card><div class=k>Experiments</div><div class=v>{model["records"]}</div><div class=n>{model["dispositions"].get("retire", 0)} retired · {model["dispositions"].get("blocked", 0)} blocked · {led["trials"]} ledger trials</div></div>',
           f'<div class=card><div class=k>Ops health</div><div class=v>{_e(health[0])}</div><div class=n>{_e(health[1])}</div></div>',
           f'<div class=card><div class=k>Waiting on you</div><div class=v>{len(model["waiting"])}</div><div class=n>open decisions and approvals</div></div>',
           "</div><h2>Gates</h2><div class=card>"]
    for g in model["gates"]:
        c = g["counts"]
        out.append(f'<div class=gate><div><b>{_e(g["id"])}</b> {_e(g["name"])}</div>{_bar(c, g["total"])}'
                   f'<div class=cnt>{c["met"]} met · {c["partial"]} partial · {c["blocked"]} blocked · {c["open"]} open</div></div>')
    out.append('<div class=legend><span><i class=met></i>met</span><span><i class=partial></i>partial</span>'
               '<span><i class=blocked></i>blocked</span><span><i class=open></i>open</span></div></div>')
    out.append("<h2>Learning</h2><div class=card><table><tr><th>Evidence class</th><th>Experiments</th><th>Best net CAGR within "
               f"{DRAWDOWN_TOLERANCE:.0%} drawdown</th></tr>")
    for cls in CLASSES:
        c = model["curve"][cls]
        note = " (viewed history, partly hindsight)" if cls == "development" else ""
        out.append(f"<tr><td>{_e(cls.replace('_', ' '))}{note}</td><td>{c['experiments']}</td><td>{_pct(c['best'])}</td></tr>")
    out.append("</table><p class=n>Only forward, shadow, paper and live rows can show learning that is not hindsight. "
               f"Development best: {_pct(best_dev)}.</p></div>")
    out.append("<h2>Waiting on you</h2><div class=card>")
    if model["waiting"]:
        out.append("<table><tr><th>Item</th><th>What</th><th>Status</th></tr>")
        for w in model["waiting"]:
            note = f"<br><span class=n>{_e(w['note'])}</span>" if w.get("note") else ""
            out.append(f'<tr><td>{_e(w["id"])}</td><td>{_e(w["text"])}{note}</td><td><span class="tag {w["status"]}">{_e(w["status"])}</span></td></tr>')
        out.append("</table>")
    else:
        out.append("<p class=n>Nothing is waiting on you.</p>")
    out.append("</div><h2>Gate detail</h2>")
    for g in model["gates"]:
        out.append(f'<details><summary>{_e(g["id"])} {_e(g["name"])} · {g["counts"]["met"]}/{g["total"]} met</summary><div class=card><table>'
                   "<tr><th>Item</th><th>What</th><th>Status</th><th>Owner</th><th>Evidence</th></tr>")
        for i in g["items"]:
            ev = " ".join((f'<a href="{_e(link(p))}">{_e(p)}</a>' if link(p) else f"<code>{_e(p)}</code>") for p in i["evidence"]) or "-"
            note = f"<br><span class=n>{_e(i['note'])}</span>" if i.get("note") else ""
            out.append(f'<tr><td>{_e(i["id"])}</td><td>{_e(i["text"])}{note}</td><td><span class="tag {i["status"]}">{_e(i["status"])}</span></td>'
                       f"<td>{_e(i['owner'])}</td><td>{ev}</td></tr>")
        out.append("</table></div></details>")
    out.append("</main></body></html>")
    return "".join(out)
