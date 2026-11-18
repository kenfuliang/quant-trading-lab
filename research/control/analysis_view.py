"""Analysis views: read ``analysis-output/v1`` folders and render the Analysis page and trust rows.

Reads files only (control imports control only). Every value passes through ``html.escape``;
missing numbers render as n/a, never zero.
"""
import html
import json
from pathlib import Path

SCHEMA = "analysis-output/v1"
_METRICS = ("net_cagr", "max_drawdown", "sharpe", "calmar", "turnover", "longest_underwater_sessions",
            "longest_underwater_days")

_CSS = """:root{--bg:#f6f7f9;--card:#fff;--ink:#14181f;--mute:#5b6573;--line:#dfe3e8;--acc:#2f6fdb;--bad:#b3261e}
@media (prefers-color-scheme:dark){:root{--bg:#0e1116;--card:#171b22;--ink:#e8ecf2;--mute:#9aa5b4;--line:#2a313c;--acc:#6aa0ff;--bad:#ff8a80}}
*{box-sizing:border-box}body{margin:0;padding:16px;background:var(--bg);color:var(--ink);font:14px/1.4 system-ui,-apple-system,sans-serif}
h1{margin:0 0 4px}h2{margin:24px 0 8px}h3{margin:14px 0 6px}.muted{color:var(--mute)}a{color:var(--acc)}
table{border-collapse:collapse;width:100%;background:var(--card);margin:6px 0 14px}
th,td{border:1px solid var(--line);padding:4px 8px;text-align:left;vertical-align:top}th{color:var(--mute);font-weight:600}
.badge{display:inline-block;border:1px solid var(--line);border-radius:10px;padding:0 8px;margin:2px 4px 2px 0;font-size:12px}
.failed{color:var(--bad);font-weight:600}section.analysis{background:var(--card);border:1px solid var(--line);border-radius:8px;padding:10px 14px;margin:14px 0}"""


def _e(value):
    return html.escape(str(value))


def _fmt(value, digits=4):
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return "n/a"
    return f"{value:.{digits}f}" if isinstance(value, float) else str(value)


def load_analyses(root):
    """``(analyses, warnings)``: valid ``analysis/*/analysis.json`` documents, newest per ``spec_id``.

    Each returned document gains ``_dir`` (its folder). Unreadable or wrong-schema files are
    skipped with a warning.
    """
    warnings, newest = [], {}
    base = Path(root) / "analysis"
    for path in sorted(base.glob("*/analysis.json")) if base.is_dir() else []:
        try:
            doc = json.loads(path.read_text(encoding="utf-8"))
            if doc.get("schema") != SCHEMA:
                raise ValueError(f"schema is {doc.get('schema')!r}, not {SCHEMA}")
            for key in ("spec_id", "analysis_id", "created_utc"):
                if not isinstance(doc.get(key), str):
                    raise ValueError(f"missing {key}")
        except (OSError, ValueError, AttributeError) as error:
            warnings.append(f"{path}: skipped ({error})")
            continue
        doc["_dir"] = str(path.parent)
        key = (doc["created_utc"], doc["analysis_id"])
        held = newest.get(doc["spec_id"])
        if held is None or key > (held["created_utc"], held["analysis_id"]):
            newest[doc["spec_id"]] = doc
    return sorted(newest.values(), key=lambda d: (d["created_utc"], d["analysis_id"]), reverse=True), warnings


def _stat(block):
    block = block if isinstance(block, dict) else {}
    return _fmt(block.get("value")), block.get("reason") or ""


def trust_rows(analyses):
    """Plain-text rows for the Pipeline trust panel (unescaped; the renderer escapes)."""
    rows = []
    for doc in analyses or []:
        trust = doc.get("trust") or {}
        look = doc.get("lookahead") or {}
        sheet = doc.get("tearsheet") or {}
        row = {"spec_id": doc.get("spec_id"), "analysis_id": doc.get("analysis_id"),
               "lookahead": look.get("status") or "n/a", "tearsheet": sheet.get("status") or "n/a"}
        for name in ("psr", "dsr", "pbo"):
            row[name], row[f"{name}_reason"] = _stat(trust.get(name))
        rows.append(row)
    return rows


def _tearsheet(doc):
    sheet = doc.get("tearsheet") or {}
    status = sheet.get("status") or "n/a"
    cls = ' class="failed"' if status == "failed" else ""
    detail = f' — {_e(sheet["error"])}' if sheet.get("error") else ""
    target = Path(doc.get("_dir") or "") / "tearsheet.html"
    link = ""
    if doc.get("_dir") and target.is_file():
        link = f' <a href="{_e(target.resolve().as_uri())}">open tearsheet</a>'
    return f'<span{cls} data-tearsheet="{_e(status)}">{_e(status)}</span>{detail}{link}'


def _section(doc):
    runs = "".join(
        f'<tr><td>{_e(r.get("rung"))}</td><td>{_e(r.get("run_id"))}</td>'
        + "".join(f'<td>{_fmt((r.get("summary") or {}).get(k))}</td>' for k in _METRICS) + '</tr>'
        for r in doc.get("runs") or [])
    waterfall = "".join(
        f'<tr><td>{_e(w.get("from"))}</td><td>{_e(w.get("to"))}</td>'
        + "".join(f'<td>{_fmt((w.get("delta") or {}).get(k))}</td>' for k in _METRICS) + '</tr>'
        for w in doc.get("waterfall") or [])
    head = "".join(f"<th>{_e(k)}</th>" for k in _METRICS)
    trust = doc.get("trust") or {}
    trows = ""
    for name in ("psr", "dsr", "pbo"):
        value, reason = _stat(trust.get(name))
        trows += f'<tr><td>{name.upper()}</td><td>{_e(value)}</td><td>{_e(reason)}</td></tr>'
    look = doc.get("lookahead") or {}
    diffs = look.get("differences") or []
    diff_text = (f'{len(diffs)} difference(s): ' + _e("; ".join(str(d) for d in diffs[:5]))) if diffs else "no differences"
    notes = "".join(f"<li>{_e(n)}</li>" for n in doc.get("notes") or [])
    status = look.get("status") or "n/a"
    cutoffs = ", ".join(map(str, look.get("cutoffs") or [])) or "none"
    return (
        f'<section class="analysis" data-spec="{_e(doc.get("spec_id"))}"><h2>{_e(doc.get("title") or doc.get("spec_id"))}</h2>'
        f'<p class="muted">{_e(doc.get("analysis_id"))} · spec {_e(doc.get("spec_id"))} · created {_e(doc.get("created_utc"))}'
        f' · code {_e(doc.get("code_commit"))}</p><p>Tearsheet: {_tearsheet(doc)}</p>'
        f'<h3>Runs</h3><table><thead><tr><th>Rung</th><th>Run</th>{head}</tr></thead><tbody>{runs}</tbody></table>'
        f'<h3>Waterfall (to minus from)</h3><table><thead><tr><th>From</th><th>To</th>{head}</tr></thead>'
        f'<tbody>{waterfall}</tbody></table>'
        f'<h3>Trust</h3><table><thead><tr><th>Statistic</th><th>Value</th><th>Reason</th></tr></thead><tbody>{trows}</tbody></table>'
        f'<h3>Lookahead</h3><p><span class="badge" data-lookahead="{_e(status)}">{_e(status)}</span> '
        f'{diff_text} · cutoffs {_e(cutoffs)}</p>'
        f'{"<h3>Notes</h3><ul>" + notes + "</ul>" if notes else ""}</section>')


def render_analysis_page(analyses, built):
    body = "".join(_section(d) for d in analyses) or '<p class="muted">No analyses yet. Run scripts/analysis.py run.</p>'
    return (f'<!doctype html><html lang="en"><head><meta charset="utf-8">'
            f'<meta name="viewport" content="width=device-width,initial-scale=1"><title>Analysis</title>'
            f'<style>{_CSS}</style></head><body><h1>Analysis</h1>'
            f'<p class="muted">Built {_e(built)} · development evidence only; metrics are fractions, '
            f'Sharpe at a zero risk-free rate.</p>{body}</body></html>')
