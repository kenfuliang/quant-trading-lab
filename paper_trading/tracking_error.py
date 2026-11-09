"""Join shadow decisions to a replayed target series and report tracking error."""
from __future__ import annotations


def validate_replay(rows):
    dates = [r["date"] for r in rows]
    if not dates or dates != sorted(set(dates)):
        raise ValueError("Replay needs unique ordered dates.")
    if any(r["target_position"] not in (0, 1) for r in rows):
        raise ValueError("Replay targets must be 0 or 1.")
    return {r["date"]: r["target_position"] for r in rows}


def tracking_error(decisions, replay_rows):
    """Position-day disagreement over the shadow window; any gap flags the report.

    Shadow sessions are those with a resolved `session`. Replay days inside the
    shadow window that shadow lacks, and shadow days the replay lacks, are
    reported as missing rather than silently dropped.
    """
    replay = validate_replay(replay_rows)
    shadow = {}
    for d in decisions:
        if d["session"] is None:
            continue
        if d["session"] in shadow:
            raise ValueError("Duplicate shadow session.")
        shadow[d["session"]] = d["hypothetical_position"]
    if not shadow:
        raise ValueError("No resolved shadow sessions to compare.")
    first, last = min(shadow), max(shadow)
    window = {d for d in replay if first <= d <= last}
    compared = sorted(set(shadow) & set(replay))
    mismatches = [d for d in compared if shadow[d] != replay[d]]
    missing_in_shadow = sorted(window - set(shadow))
    missing_in_replay = sorted(set(shadow) - set(replay))
    error = len(mismatches) / len(compared) if compared else None
    clean = error == 0 and not missing_in_shadow and not missing_in_replay
    return {"status": "ok" if clean else "flagged", "window": [first, last],
            "compared_days": len(compared), "mismatch_days": mismatches,
            "tracking_error": error, "missing_in_shadow": missing_in_shadow,
            "missing_in_replay": missing_in_replay}
