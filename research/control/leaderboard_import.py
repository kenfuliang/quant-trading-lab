"""One-time import of the retired hand-edited leaderboard table into registry records.

Best effort and honest about it: every record keeps its original row text, is marked
`imported`, stays `development` evidence, and keeps the table's own evidence-status
and outcome wording. Percent strings become fractions; text that is not a number
becomes null rather than a guess.
"""
import re

from research.control.experiment_registry import SCHEMA

COLUMNS = ("Algorithm / variant", "Calmar (headline)", "Evidence status", "CAGR", "Max DD",
           "Longest underwater sessions / days", "Sharpe", "Tags", "Context", "Period",
           "Outcome", "Evidence", "Lesson")
_NUM = re.compile(r"-?\d+(?:\.\d+)?")
_LINK = re.compile(r"\[[^\]]*\]\(([^)]+)\)")


def _number(text):
    match = _NUM.search(text.replace(",", ""))
    return float(match.group()) if match else None


def _fraction(text):
    value = _number(text)
    return None if value is None else round(value / 100, 10) if "%" in text else value


def _pair(text):
    found = re.findall(r"\d+", text)
    return (int(found[0]), int(found[1])) if len(found) >= 2 else (None, None)


def _disposition(outcome, tags):
    lowered = outcome.lower()
    if "reject" in lowered or "negative result" in tags:
        return "retire"
    if any(word in lowered for word in ("control", "reference", "benchmark")) or "control" in tags or "benchmark" in tags:
        return "control"
    return "inconclusive"


def _slug(text):
    return re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")[:40] or "row"


def parse_leaderboard(text, logged_at):
    lines = [line for line in text.splitlines() if line.startswith("|")]
    header = [c.strip() for c in lines[0].strip().strip("|").split("|")]
    if tuple(header) != COLUMNS:
        raise ValueError("leaderboard columns changed; update the importer before importing")
    records = []
    for index, line in enumerate(lines[2:], 1):
        cells = [c.strip() for c in line.strip().strip("|").split("|")]
        if len(cells) != len(COLUMNS):
            raise ValueError(f"row {index} has {len(cells)} cells")
        row = dict(zip(COLUMNS, cells))
        tags = [t.strip() for t in row["Tags"].split("·") if t.strip()]
        sessions, days = _pair(row["Longest underwater sessions / days"])
        bps = re.search(r"(\d+)\s?bp", row["Tags"] + " " + row["Context"])
        links = _LINK.findall(row["Evidence"])
        receipt = next((link for link in links if "/evidence/" in link and link.endswith(".json")), None)
        study = next((link for link in links if link.endswith(".md")), None)
        records.append({
            "schema": SCHEMA, "record_id": f"legacy-{index:03d}-{_slug(row['Algorithm / variant'])}",
            "logged_at": logged_at, "name": row["Algorithm / variant"],
            "context": {"code": row["Context"], "period": row["Period"],
                        **({"costs_bp": float(bps.group(1))} if bps else {})},
            "evidence_class": "development", "evidence_status": row["Evidence status"],
            "disposition": _disposition(row["Outcome"], tags), "outcome": row["Outcome"],
            "lesson": row["Lesson"] or "No lesson recorded in the retired table.",
            "metrics": {"net_cagr": _fraction(row["CAGR"]), "max_drawdown": _fraction(row["Max DD"]),
                        "longest_underwater_sessions": sessions, "longest_underwater_days": days,
                        "calmar": _number(row["Calmar (headline)"]), "sharpe": _number(row["Sharpe"])},
            "refs": {k: v for k, v in (("receipt", receipt), ("study", study)) if v},
            "tags": tags, "imported": True, "legacy_row": line})
    return records
