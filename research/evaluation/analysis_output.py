"""``analysis-output/v1``: the analysis document, its Markdown report and an exclusive writer.

A folder ``<root>/analysis/<analysis_id>/`` holds ``analysis.json``, ``report.md`` and,
when rendered, ``tearsheet.html``. Folders are created exclusively and never overwritten.
"""
from __future__ import annotations

import json
import re
from datetime import datetime
from pathlib import Path

from research.evaluation.ladder import waterfall
from research.evaluation.metrics import METRIC_KEYS
from research.evaluation.universe import LABELS, STOCK_UNIVERSE_KIND, stock_labels  # noqa: F401

SCHEMA = "analysis-output/v1"


def _safe(text: str) -> str:
    return re.sub(r"[^A-Za-z0-9._-]+", "-", str(text)).strip("-") or "analysis"


def build_analysis(spec: dict, steps: list[dict], trust: dict, lookahead: dict, comparison: dict | None,
                   provenance: dict, created_utc: str, tearsheet: dict | None = None,
                   universe: dict | None = None) -> dict:
    """Assemble the document; ``steps`` are ladder results, ``provenance`` has ``code_commit`` and ``datasets``.

    ``trust`` is ``{psr, dsr, pbo}``; ``comparison`` is registry context for the report, or ``None``.
    ``labels`` come from the dataset provenance ``universe_kind`` (never from coverage). ``universe`` is
    ``{membership_id, identity_id, coverage_summary}`` when point-in-time masking was applied, else ``None``.
    """
    stamp = datetime.fromisoformat(created_utc).strftime("%Y%m%dT%H%M%SZ")
    return {
        "schema": SCHEMA,
        "analysis_id": f"{stamp}-{_safe(spec['spec_id'])}",
        "spec_id": spec["spec_id"],
        "title": spec.get("title", spec["spec_id"]),
        "created_utc": created_utc,
        "code_commit": provenance["code_commit"],
        "datasets": provenance["datasets"],
        "labels": stock_labels(provenance["datasets"], bool((universe or {}).get("membership_id"))),
        "membership_id": (universe or {}).get("membership_id"),
        "identity_id": (universe or {}).get("identity_id"),
        "coverage_summary": (universe or {}).get("coverage_summary"),
        "universe": None if not universe else {
            **{k: universe.get(k) for k in ("membership_id", "identity_id", "membership_sha256", "identity_sha256",
                                            "membership_manifest_verified", "names", "late_or_never_count")},
            "excluded": (provenance["datasets"] or {}).get("universe_excluded")},
        "runs": [dict(step) for step in steps],
        "waterfall": waterfall(steps),
        "trust": {key: trust[key] for key in ("psr", "dsr", "pbo")},
        "lookahead": lookahead,
        "comparison": comparison,
        "tearsheet": tearsheet or {"status": "skipped", "error": None},
        "notes": list(spec.get("notes", [])),
    }


def write_analysis(root: Path, doc: dict, tearsheet_html: str | None, report_md: str) -> Path:
    """Create ``<root>/analysis/<analysis_id>/`` exclusively (``FileExistsError`` if present)."""
    folder = Path(root) / "analysis" / doc["analysis_id"]
    folder.parent.mkdir(parents=True, exist_ok=True)
    folder.mkdir()
    with open(folder / "analysis.json", "x", encoding="utf-8") as stream:
        stream.write(json.dumps(doc, indent=2, sort_keys=True, allow_nan=False) + "\n")
    with open(folder / "report.md", "x", encoding="utf-8") as stream:
        stream.write(report_md)
    if tearsheet_html is not None:
        with open(folder / "tearsheet.html", "x", encoding="utf-8") as stream:
            stream.write(tearsheet_html)
    return folder


def _fmt(value) -> str:
    if value is None:
        return "n/a"
    return f"{value:.4f}" if isinstance(value, float) else str(value)


def _trust_line(label: str, item: dict) -> str:
    if item.get("value") is None:
        return f"- {label}: n/a ({item.get('reason', 'no reason recorded')})"
    return f"- {label}: {item['value']:.4f}"


def _dsr_input_lines(item: dict) -> list[str]:
    lines = []
    if item.get("n_trials") is not None:
        lines.append(f"- DSR trials: {item['n_trials']} (context {item.get('code', 'n/a')})")
    if "sr_variance" in item:
        lines.append(f"- DSR sr_variance (per period): {_fmt_small(item['sr_variance'])}")
    if item.get("trial_record_ids") is not None:
        lines.append(f"- DSR trial records: {', '.join(item['trial_record_ids']) or 'none'}")
    if item.get("trial_sharpes") is not None:
        lines.append(f"- DSR trial Sharpes (registry, annualised): {', '.join(_fmt(s) for s in item['trial_sharpes'])}")
    if item.get("period_note"):
        lines.append(f"- DSR period: {item['period_note']}")
    return lines


def _fmt_small(value) -> str:
    return "n/a" if value is None else f"{value:.6g}"


def _universe_lines(doc: dict) -> list[str]:
    summary = doc.get("coverage_summary") or {}
    worst = (summary.get("worst_dates") or [{}])[0]
    block = doc.get("universe") or {}
    parts = []
    if block.get("names") is not None:
        parts.append(f"{block['names']} names")
    excluded = block.get("excluded")
    if excluded:
        shown = ", ".join(excluded["names"][:5]) + ("..." if len(excluded["names"]) > 5 else "")
        parts.append(f"{excluded['count']} excluded incl. {shown} (see manifest notes)")
        parts.append("dividends credited on the ex-date (pay date unknown)")
    late = block.get("late_or_never_count")
    if late is not None:
        parts.append(f"{late} dataset names first join the index when an unresolved rename candidate starts "
                     "(late or never members)")
    head = "; ".join(parts) + "; " if parts else ""
    return [f"Universe: {head}point-in-time membership `{doc['membership_id']}` (identity `{doc.get('identity_id')}`); "
            f"non-members are held at zero on each decision date. Index members with data: min "
            f"{_fmt(summary.get('min_share'))}, median {_fmt(summary.get('median_share'))}, worst date "
            f"{worst.get('date', 'n/a')}.", ""]


def render_report(doc: dict) -> str:
    lines = [f"# Analysis: {doc.get('title', doc['spec_id'])}", "",
             f"- Spec: `{doc['spec_id']}`", f"- Created (UTC): {doc['created_utc']}",
             f"- Code commit: `{doc['code_commit']}`", "",
             "Sharpe is at a zero risk-free rate; fractions, 252 sessions a year; "
             "max drawdown is a positive magnitude.", ""]
    if doc.get("labels"):
        lines += ["**Labels: " + ", ".join(doc["labels"]) + ".** Stock results use today's index holdings "
                  "(a survivor-biased proxy): discovery only, they cannot clear G2.", ""]
    if doc.get("membership_id"):
        lines += _universe_lines(doc)
    lines += ["## Runs", "",
             "| Rung | Run | " + " | ".join(METRIC_KEYS) + " |",
             "|---|---|" + "---|" * len(METRIC_KEYS)]
    for run in doc["runs"]:
        lines.append(f"| {run['rung']} | `{run['run_id']}` | "
                     + " | ".join(_fmt(run["summary"].get(k)) for k in METRIC_KEYS) + " |")
    lines += ["", "## Waterfall", "", "Metric change from each rung to the next.", "",
              "| Step | " + " | ".join(METRIC_KEYS) + " |", "|---|" + "---|" * len(METRIC_KEYS)]
    for step in doc["waterfall"]:
        lines.append(f"| {step['from']} -> {step['to']} | "
                     + " | ".join(_fmt(step["delta"].get(k)) for k in METRIC_KEYS) + " |")
    trust = doc["trust"]
    lines += ["", "## Trust", "",
              _trust_line("PSR (last rung, benchmark 0)", trust["psr"]),
              _trust_line("DSR", trust["dsr"]),
              _trust_line("PBO (illustrative grid; not registry trials)", trust["pbo"])]
    lines += _dsr_input_lines(trust["dsr"])
    warmup = trust["psr"].get("warmup_note")
    if warmup:
        lines.append(f"- PSR/DSR warm-up: {warmup}")
    look = doc["lookahead"]
    lines += ["", "## Lookahead", "", f"- Status: {look['status']}", f"- Cutoffs: {', '.join(look['cutoffs'])}"]
    for item in look.get("compared", []):
        lines.append(f"- {item['cutoff']}: compared_signals {item['compared_signals']}")
    for diff in look["differences"]:
        lines.append(f"- difference: {json.dumps(diff, sort_keys=True)}")
    if doc["comparison"]:
        lines += ["", "## Registry comparison", ""]
        for record in doc["comparison"].get("records", []):
            metrics = ", ".join(f"{k} {_fmt(v)}" for k, v in sorted(record["metrics"].items()))
            lines.append(f"- {record['record_id']} ({record['context']['code']}, {record['context']['period']}): {metrics}")
        for missing in doc["comparison"].get("missing", []):
            lines.append(f"- missing record: {missing}")
    sheet = doc.get("tearsheet") or {"status": "skipped", "error": None}
    lines += ["", "## Tearsheet", "", f"- Status: {sheet['status']}"]
    if sheet.get("error"):
        lines.append(f"- Error: {sheet['error']}")
    if doc["notes"]:
        lines += ["", "## Notes", ""] + [f"- {note}" for note in doc["notes"]]
    return "\n".join(lines) + "\n"
