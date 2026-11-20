#!/usr/bin/env python3
"""Record experiments and regenerate the leaderboard, dead-ends and learning-curve views.

  log            append one validated record (optionally validate a receipt and count a trial)
  render         rewrite the three generated documents under docs/
  check          verify the registry chain, that generated documents are current, and that
                 every v1 experiment receipt has a record
  import-legacy  one-time import of the retired hand-edited leaderboard table

Offline only: no network, broker or order. Failed, blocked and inconclusive runs belong here too.
"""
import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import re
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from research.control import experiment_registry as registry
from research.control.experiment_registry import CLASSES, DISPOSITIONS, METRICS, RegistryError
from research.control.leaderboard_import import parse_leaderboard
from research.control import run_refs
from research.control.registry_views import VIEWS
from research.evaluation.engine_identity import engine_files_changed, run_git

REGISTRY = ROOT / "research/registry/experiments.jsonl"
DOCS = ROOT / "docs"
RECEIPTS = DOCS / "tasks/evidence"
EXEMPTIONS = ROOT / "research/registry/receipt-exemptions.json"
VALIDATION_RECEIPTS = ROOT / "research/registry/validation-receipts"


def link_ok(path):
    return bool(path) and not path.startswith("..") and (DOCS / path).is_file()


def render_all(records):
    return {name: fn(records, link_ok) if name != "learning-curve.md" else fn(records) for name, fn in VIEWS.items()}


def v1_receipts():
    found = []
    for path in sorted(RECEIPTS.glob("*.json")):
        try:
            if json.loads(path.read_text()).get("schema") == "experiment-receipt/v1":
                found.append(path)
        except ValueError:
            continue
    return found


def check(registry_path):
    errors = []
    try:
        records = registry.load(registry_path)
    except RegistryError as error:
        return [f"registry: {error}"]
    for name, text in render_all(records).items():
        target = DOCS / name
        if not target.exists() or target.read_text() != text:
            errors.append(f"docs/{name} is stale; run scripts/experiments.py render")
    exempt = json.loads(EXEMPTIONS.read_text()) if EXEMPTIONS.exists() else {}
    covered = {r.get("refs", {}).get("receipt") for r in records}
    for path in v1_receipts():
        relative = path.relative_to(DOCS).as_posix()
        if relative not in covered and relative not in exempt:
            errors.append(f"receipt {relative} has no registry record; run scripts/experiments.py log --receipt")
    errors += check_validation_refs(records)
    return errors


def check_validation_refs(records):
    """Structural check of tracked validation receipts a record points at (no local files)."""
    errors = []
    for record in records:
        refs = record.get("refs") or {}
        receipt_id = refs.get("validation_receipt")
        if not receipt_id:
            continue
        run_ids = [refs[k] for k in ("run_id", "nautilus_run_id") if refs.get(k)]
        if not run_refs.is_sha256(refs.get("validation_receipt_sha256")):
            errors.append(f"record {record.get('record_id')}: refs.validation_receipt_sha256 is missing or malformed")
            continue
        try:
            run_refs.read_validation_receipt(VALIDATION_RECEIPTS, receipt_id,
                                             refs.get("validation_receipt_sha256"), run_ids,
                                             parity_id=refs.get("parity_receipt_id"))
        except RegistryError as error:
            errors.append(f"record {record.get('record_id')}: {error}")
    return errors


def parse_metrics(value):
    if value is None:
        return {}
    text = Path(value[1:]).read_text() if value.startswith("@") else value
    data = json.loads(text)
    if not isinstance(data, dict) or set(data) - set(METRICS):
        raise SystemExit("--metrics must be a JSON object using only: " + ", ".join(METRICS))
    return data


def reverify_quality_gate(manifest, data_root):
    """Rule 2 at log time: do not trust the gate fields a manifest records; re-run the gate on the
    quality report folder the manifest names (inside the data root) and compare the result."""
    from research.evaluation.acceptance import verify_for_financial_use
    run_id = manifest.get("run_id")
    datasets = manifest.get("datasets") or {}
    cannot = f"cannot verify the quality gate at log time for run {run_id}"
    relative = datasets.get("quality_report")
    if not isinstance(relative, str) or not relative:
        raise RegistryError(f"{cannot}: the manifest names no quality_report")
    base = Path(data_root).resolve()
    path = (base / relative).resolve()
    if not path.is_relative_to(base):
        raise RegistryError(f"{cannot}: quality_report {relative!r} is outside the data root")
    try:
        report = json.loads(path.read_text(encoding="utf-8"))
        gate = verify_for_financial_use(base, path.parent, report)
    except (OSError, ValueError, KeyError, TypeError, AttributeError) as error:  # AcceptanceError is a ValueError
        raise RegistryError(f"{cannot}: {error}") from None
    if report.get("status") != datasets.get("quality_status"):
        raise RegistryError(f"run {run_id} claims quality status {datasets.get('quality_status')!r} but its "
                            f"report says {report.get('status')!r}")
    claimed = datasets.get("acceptance")
    claimed_sha = claimed.get("acceptance_sha256") if isinstance(claimed, dict) else None
    if gate["acceptance_sha256"] != claimed_sha:
        raise RegistryError(f"run {run_id} acceptance_sha256 {claimed_sha!r} does not match the acceptance "
                            f"on disk ({gate['acceptance_sha256']!r})")


def receipts_dir_for(args):
    """The validation-receipts directory for a real log: only the tracked one, unless the explicit
    test-only flag is given (then it prints a warning and the tracked-file check is skipped)."""
    if not args.receipts_dir:
        return VALIDATION_RECEIPTS
    chosen = Path(args.receipts_dir)
    if chosen.resolve() == VALIDATION_RECEIPTS.resolve():
        return chosen
    if not args.allow_untracked_receipts:
        raise RegistryError(f"--receipts-dir {chosen} is not the tracked {VALIDATION_RECEIPTS}; a real log "
                            "must use a committed receipt (--allow-untracked-receipts is for tests only)")
    return chosen


def require_tracked(path):
    code, _ = run_git(["ls-files", "--error-unmatch", "--", str(path)])
    if code != 0:
        raise RegistryError(f"validation receipt {path} is not tracked by git; commit it before logging")


def verify_run_refs(record, args):
    """Log-time file checks for rules 2 and 3; fills the sha256 refs from the files read.

    Order matters: files are read and hashed first (so the shape rules in `validate` see the
    refs), then the content rules run. Any problem raises `RegistryError`.
    """
    refs = record["refs"]
    runs = Path(args.runs_root) if args.runs_root else default_root("runs_root")
    parity = Path(args.parity_root) if args.parity_root else default_root("parity_root")
    run = nautilus = receipt = None
    if record["disposition"] == "keep" and record.get("attempt") in registry.NO_RUN_ATTEMPTS:
        raise RegistryError(f"a keep record cannot have attempt {record['attempt']!r}")
    receipts = receipts_dir_for(args)
    untracked_ok = bool(args.receipts_dir) and receipts.resolve() != VALIDATION_RECEIPTS.resolve()
    if untracked_ok:
        print("warning: --allow-untracked-receipts: the validation receipt is not the tracked one; "
              "test use only", file=sys.stderr)
    if args.run_id:
        run, sha = run_refs.read_run_manifest(runs, args.run_id)
        refs.update(run_id=args.run_id, run_manifest_sha256=sha)
    if args.nautilus_run_id:
        nautilus, sha = run_refs.read_run_manifest(runs, args.nautilus_run_id)
        refs.update(nautilus_run_id=args.nautilus_run_id, nautilus_run_manifest_sha256=sha)
    if args.parity_receipt:
        receipt, sha = run_refs.read_parity_receipt(parity, args.parity_receipt)
        refs.update(parity_receipt_id=args.parity_receipt, parity_receipt_sha256=sha)
    if args.validation_receipt:
        covered = [i for i in (args.run_id, args.nautilus_run_id) if i]
        _, sha = run_refs.read_validation_receipt(receipts, args.validation_receipt, None, covered,
                                                  parity_id=args.parity_receipt)
        if not untracked_ok:
            require_tracked(receipts / f"{args.validation_receipt}.json")
        refs.update(validation_receipt=args.validation_receipt, validation_receipt_sha256=sha)
    registry.validate(record)  # shape first: names every missing ref
    if run is not None and record["disposition"] != "blocked" and record.get("attempt") not in registry.NO_RUN_ATTEMPTS:
        run_refs.require_financial_run(run)
        reverify_quality_gate(run, runs.parent)
    if record["disposition"] != "keep":
        return
    run_refs.require_nautilus_run(nautilus, candidate=run)
    reverify_quality_gate(nautilus, runs.parent)
    run_refs.require_passed_parity(receipt)
    run_refs.require_confirmation(receipt, refs["run_id"], refs["run_manifest_sha256"],
                                  refs["nautilus_run_id"], refs["nautilus_run_manifest_sha256"])
    changed = engine_files_changed(run_git, receipt["code_commit"], nautilus.get("code_commit") or "")
    if changed:
        raise RegistryError("engine files changed between the parity receipt commit and the run commit: "
                            + ", ".join(changed))


def default_root(name):
    from research.data import root
    return getattr(root, name)()


def cmd_log(args):
    refs = {}
    if args.study:
        refs["study"] = args.study
    if args.receipt:
        from research.control.experiment_receipts import validate_receipt
        from research.control.leakage_audit import audit_receipt
        path = Path(args.receipt)
        receipt = json.loads(path.read_text())
        root = Path(args.root) if args.root else path.parent
        problems = validate_receipt(receipt, root) or audit_receipt(receipt, root)
        if problems:
            print("\n".join(problems), file=sys.stderr)
            return 1
        refs["receipt"] = path.resolve().relative_to(DOCS).as_posix() if path.resolve().is_relative_to(DOCS) else str(path)
        args.cycle_id = args.cycle_id or receipt.get("cycle_id")
    record_id = args.id or (f"{args.cycle_id}:{re.sub(r'[^a-z0-9]+', '-', args.name.lower()).strip('-')}"[:120] if args.cycle_id else None)
    if not record_id:
        raise SystemExit("Give --id, or --cycle-id/--receipt so one can be derived.")
    record = {
        "schema": registry.SCHEMA, "record_id": record_id,
        "logged_at": datetime.now(timezone.utc).replace(microsecond=0).isoformat(),
        "name": args.name, "change": args.change, "parent_id": args.parent,
        "context": {"code": args.context, "period": args.period,
                    **({"costs_bp": args.costs_bp} if args.costs_bp is not None else {})},
        "evidence_class": args.evidence_class, "evidence_status": args.status,
        "disposition": args.disposition, "attempt": args.attempt, "outcome": args.outcome, "lesson": args.lesson,
        "metrics": parse_metrics(args.metrics), "refs": refs,
        "tags": [t.strip() for t in (args.tags or "").split(",") if t.strip()], "imported": False}
    record = {k: v for k, v in record.items() if v is not None}
    verify_run_refs(record, args)
    registry.validate(record)
    if args.dry_run:
        print(json.dumps(record, indent=2))
        return 0
    if args.ledger:
        from research.control.trial_ledger import TrialLedger
        if not args.cycle_id:
            raise SystemExit("--ledger needs --cycle-id")
        with TrialLedger(args.ledger) as ledger:
            number = ledger.trial(args.cycle_id, args.trial_description or args.name)
        record["refs"]["ledger_trial"] = {"cycle_id": args.cycle_id, "trial_number": number}
    registry.append(args.registry, record)
    print(f"Logged {record_id}. Run: scripts/experiments.py render")
    return 0


def cmd_render(args):
    records = registry.load(args.registry)
    for name, text in render_all(records).items():
        (DOCS / name).write_text(text)
    print(f"Rendered {len(VIEWS)} documents from {len(records)} records.")
    return 0


def cmd_check(args):
    errors = check(args.registry)
    if errors:
        print("\n".join(errors), file=sys.stderr)
        return 1
    print(f"Experiment registry passed: {len(registry.load(args.registry))} records; views current; receipts covered.")
    return 0


def cmd_import(args):
    if Path(args.registry).exists() and registry.load(args.registry):
        raise SystemExit("Registry already has records; the legacy import is one-time.")
    records = parse_leaderboard(Path(args.source).read_text(), "2026-10-31T00:00:00+00:00")
    for record in records:
        registry.append(args.registry, record)
    print(f"Imported {len(records)} legacy rows.")
    return 0


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--registry", type=Path, default=REGISTRY)
    sub = parser.add_subparsers(dest="command", required=True)
    log = sub.add_parser("log")
    log.add_argument("--id")
    log.add_argument("--name", required=True)
    log.add_argument("--change")
    log.add_argument("--parent")
    log.add_argument("--context", required=True, help="comparison context code")
    log.add_argument("--period", required=True)
    log.add_argument("--costs-bp", type=float)
    log.add_argument("--evidence-class", choices=CLASSES, default="development")
    log.add_argument("--status", help="evidence status wording, e.g. 'Audited ledger'")
    log.add_argument("--disposition", choices=DISPOSITIONS, required=True)
    log.add_argument("--outcome")
    log.add_argument("--lesson", required=True)
    log.add_argument("--metrics", help="JSON object or @file; fractions, drawdown positive")
    log.add_argument("--tags", help="comma-separated")
    log.add_argument("--study", help="path relative to docs/")
    log.add_argument("--receipt", help="experiment-receipt/v1 file; validated before logging")
    log.add_argument("--root", help="artifact root for the receipt (default: its directory)")
    log.add_argument("--cycle-id")
    log.add_argument("--ledger", help="trial-ledger directory; counts one trial for --cycle-id")
    log.add_argument("--trial-description")
    log.add_argument("--attempt", choices=registry.ATTEMPTS, help="failed/abandoned need no run output")
    log.add_argument("--run-id", help="financial-use run (rule 2); its manifest is read and hashed")
    log.add_argument("--nautilus-run-id", help="NautilusTrader run (keep records)")
    log.add_argument("--parity-receipt", help="parity id of a passing engine-parity receipt (keep records)")
    log.add_argument("--validation-receipt", help="id of a tracked validation receipt (keep records)")
    log.add_argument("--runs-root", help="override the runs root (default: the data root's runs/)")
    log.add_argument("--parity-root", help="override the parity root (default: the data root's parity/)")
    log.add_argument("--receipts-dir", help="override research/registry/validation-receipts (tests only)")
    log.add_argument("--allow-untracked-receipts", action="store_true",
                     help="TEST ONLY: accept a --receipts-dir outside the tracked directory, untracked files")
    log.add_argument("--dry-run", action="store_true")
    log.set_defaults(fn=cmd_log)
    sub.add_parser("render").set_defaults(fn=cmd_render)
    sub.add_parser("check").set_defaults(fn=cmd_check)
    legacy = sub.add_parser("import-legacy")
    legacy.add_argument("--source", type=Path, required=True, help="the original hand-edited leaderboard.md")
    legacy.set_defaults(fn=cmd_import)
    args = parser.parse_args(argv)
    try:
        return args.fn(args)
    except (RegistryError, ValueError, OSError) as error:
        print(f"error: {error}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
