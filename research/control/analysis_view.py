"""Analysis views: read ``analysis-output/v1`` folders and render the Analysis page and trust rows.

Reads files only (control imports control only). Every value passes through ``html.escape``;
missing numbers render as n/a, never zero.
"""
import html
import json
import re
from datetime import datetime, timezone
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


_SAFE_ID = re.compile(r"^[A-Za-z0-9._-]+$")


def safe_id(value):
    """True for an analysis id usable as one path segment."""
    return isinstance(value, str) and bool(_SAFE_ID.match(value)) and value not in (".", "..")


def _validate(doc):
    if not isinstance(doc, dict):
        raise ValueError("not an object")
    if doc.get("schema") != SCHEMA:
        raise ValueError(f"schema is {doc.get('schema')!r}, not {SCHEMA}")
    for key in ("spec_id", "analysis_id", "created_utc"):
        if not isinstance(doc.get(key), str):
            raise ValueError(f"missing {key}")
    for key, inner in (("runs", "summary"), ("waterfall", "delta")):
        items = doc.get(key)
        if not isinstance(items, list) or not all(isinstance(i, dict) and isinstance(i.get(inner), dict) for i in items):
            raise ValueError(f"{key} is malformed")
    notes = doc.get("notes", [])
    if not isinstance(notes, list) or not all(isinstance(n, str) for n in notes):
        raise ValueError("notes is malformed")
    for key in ("trust", "lookahead", "tearsheet"):
        if not isinstance(doc.get(key), dict):
            raise ValueError(f"{key} is malformed")
    if not all(isinstance(doc["trust"].get(n, {}), dict) for n in ("psr", "dsr", "pbo")):
        raise ValueError("trust is malformed")
    look = doc["lookahead"]
    if not isinstance(look.get("differences", []), list) or not isinstance(look.get("cutoffs", []), list):
        raise ValueError("lookahead is malformed")


def _when(doc):
    try:
        moment = datetime.fromisoformat(doc["created_utc"])
        if moment.tzinfo is None:
            moment = moment.replace(tzinfo=timezone.utc)
        return (1, moment.timestamp(), doc["analysis_id"])
    except ValueError:
        return (0, 0.0, doc["created_utc"] + doc["analysis_id"])


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
            _validate(doc)
        except (OSError, ValueError, AttributeError) as error:
            warnings.append(f"{path}: skipped ({error})")
            continue
        doc["_dir"] = str(path.parent)
        held = newest.get(doc["spec_id"])
        if held is None or _when(doc) > _when(held):
            newest[doc["spec_id"]] = doc
    return sorted(newest.values(), key=_when, reverse=True), warnings


FIXTURE_DATASET = "synthetic-fixture"


def is_fixture(doc):
    """True when the analysis ran on the synthetic engineering fixture (not evidence)."""
    datasets = doc.get("datasets") if isinstance(doc, dict) else None
    return isinstance(datasets, dict) and datasets.get("dataset_id") == FIXTURE_DATASET


def labels_of(doc):
    """Plain-text labels of an analysis (e.g. survivor-biased); malformed values are dropped."""
    labels = doc.get("labels") if isinstance(doc, dict) else None
    return [label for label in labels if isinstance(label, str)] if isinstance(labels, list) else []


def _label_badges(doc):
    return "".join(f'<span class="badge failed" data-label="{_e(label)}">{_e(label)}</span>' for label in labels_of(doc))


def _stat(block):
    block = block if isinstance(block, dict) else {}
    return _fmt(block.get("value")), block.get("reason") or ""


def _small(value):
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return "n/a"
    return f"{value:.6g}"


def stat_inputs(block):
    """Plain-text inputs of a PSR/DSR block (unescaped): trials, variance, records, period, warm-up."""
    block = block if isinstance(block, dict) else {}
    parts = []
    if block.get("n") is not None:
        parts.append(f"n {block['n']}")
    if block.get("n_trials") is not None:
        parts.append(f"n_trials {block['n_trials']}" + (f" ({block['code']})" if block.get("code") else ""))
    if "sr_variance" in block:
        parts.append(f"sr_variance {_small(block.get('sr_variance'))}")
    ids, sharpes = block.get("trial_record_ids"), block.get("trial_sharpes")
    if isinstance(ids, list):
        parts.append("trials " + (", ".join(map(str, ids)) or "none"))
    if isinstance(sharpes, list):
        parts.append("trial Sharpes " + ", ".join(_fmt(s) for s in sharpes))
    for key in ("period_note", "warmup_note"):
        if block.get(key):
            parts.append(str(block[key]))
    return "; ".join(parts)


def trust_rows(analyses):
    """Plain-text rows for the Pipeline trust panel (unescaped; the renderer escapes).

    Analyses on the synthetic fixture are engineering checks, not evidence, and are left out.
    """
    rows = []
    for doc in analyses or []:
        if is_fixture(doc):
            continue
        trust = doc.get("trust") or {}
        look = doc.get("lookahead") or {}
        sheet = doc.get("tearsheet") or {}
        row = {"spec_id": doc.get("spec_id"), "analysis_id": doc.get("analysis_id"),
               "lookahead": look.get("status") or "n/a", "tearsheet": sheet.get("status") or "n/a",
               "labels": labels_of(doc)}
        for name in ("psr", "dsr", "pbo"):
            row[name], row[f"{name}_reason"] = _stat(trust.get(name))
            row[f"{name}_inputs"] = stat_inputs(trust.get(name)) if name != "pbo" else ""
        rows.append(row)
    return rows


def _tearsheet(doc, base, available):
    sheet = doc.get("tearsheet") or {}
    status = sheet.get("status") or "n/a"
    cls = ' class="failed"' if status == "failed" else ""
    detail = f' — {_e(sheet["error"])}' if sheet.get("error") else ""
    aid = doc.get("analysis_id")
    link = ""
    if safe_id(aid) and aid in available:
        link = f' <a href="{_e(base)}/{_e(aid)}/tearsheet.html">open tearsheet</a>'
    return f'<span{cls} data-tearsheet="{_e(status)}">{_e(status)}</span>{detail}{link}'


def _section(doc, base, available):
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
        inputs = stat_inputs(trust.get(name)) if name != "pbo" else ""
        trows += (f'<tr><td>{name.upper()}</td><td>{_e(value)}</td><td>{_e(reason)}</td>'
                  f'<td>{_e(inputs)}</td></tr>')
    look = doc.get("lookahead") or {}
    diffs = look.get("differences") or []
    diff_text = (f'{len(diffs)} difference(s): ' + _e("; ".join(str(d) for d in diffs[:5]))) if diffs else "no differences"
    notes = "".join(f"<li>{_e(n)}</li>" for n in doc.get("notes") or [])
    status = look.get("status") or "n/a"
    cutoffs = ", ".join(map(str, look.get("cutoffs") or [])) or "none"
    fixture = is_fixture(doc)
    tag = ' <span class="badge">fixture</span>' if fixture else ""
    return (
        f'<section class="analysis" data-spec="{_e(doc.get("spec_id"))}" data-fixture="{str(fixture).lower()}">'
        f'<h2>{_e(doc.get("title") or doc.get("spec_id"))}{tag}</h2>'
        f'{"<p>" + _label_badges(doc) + "</p>" if labels_of(doc) else ""}'
        f'<p class="muted">{_e(doc.get("analysis_id"))} · spec {_e(doc.get("spec_id"))} · created {_e(doc.get("created_utc"))}'
        f' · code {_e(doc.get("code_commit"))}</p><p>Tearsheet: {_tearsheet(doc, base, available)}</p>'
        f'<h3>Runs</h3><table><thead><tr><th>Rung</th><th>Run</th>{head}</tr></thead><tbody>{runs}</tbody></table>'
        f'<h3>Waterfall (to minus from)</h3><table><thead><tr><th>From</th><th>To</th>{head}</tr></thead>'
        f'<tbody>{waterfall}</tbody></table>'
        f'<h3>Trust</h3><table><thead><tr><th>Statistic</th><th>Value</th><th>Reason</th><th>Inputs</th></tr></thead>'
        f'<tbody>{trows}</tbody></table>'
        f'<h3>Lookahead</h3><p><span class="badge" data-lookahead="{_e(status)}">{_e(status)}</span> '
        f'{diff_text} · cutoffs {_e(cutoffs)}</p>'
        f'{"<h3>Notes</h3><ul>" + notes + "</ul>" if notes else ""}</section>')


def render_analysis_page(analyses, built, tearsheet_base="analysis", available=frozenset()):
    """``available``: analysis ids whose tearsheet copy exists at ``<tearsheet_base>/<id>/tearsheet.html``."""
    body = "".join(_section(d, tearsheet_base, available) for d in analyses) or '<p class="muted">No analyses yet. Run scripts/analysis.py run.</p>'
    return (f'<!doctype html><html lang="en"><head><meta charset="utf-8">'
            f'<meta name="viewport" content="width=device-width,initial-scale=1"><title>Analysis</title>'
            f'<style>{_CSS}</style></head><body><h1>Analysis</h1>'
            f'<p class="muted">Built {_e(built)} · development evidence only; metrics are fractions, '
            f'Sharpe at a zero risk-free rate.</p>{body}</body></html>')
