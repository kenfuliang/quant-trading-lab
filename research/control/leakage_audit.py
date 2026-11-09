"""Offline leakage audit of an experiment receipt against its trial ledger.

Fails when a case window overlaps a sealed holdout without a matching, ledgered
read; when the receipt's declared attempts disagree with the ledger's trial count
for its cycle; or when the receipt declares a holdout read (``holdout_seal_hash``)
that the ledger never logged. A receipt with no ledger reference, or whose ledger
does not exist yet, passes so receipts written before the ledger keep validating,
except that a declared ``holdout_seal_hash`` cannot be verified without a ledger.
Checks bind receipt text to ledger bytes; they do not prove the holdout data itself
was unread.
"""
from datetime import date
from pathlib import Path

from research.control.trial_ledger import LedgerError, read_ledger


def _confined(root, ref):
    if not isinstance(ref, str) or not ref.strip() or Path(ref).is_absolute() or ':' in ref:
        return None
    path = (Path(root).resolve() / ref).resolve()
    return path if path.is_relative_to(Path(root).resolve()) else None


def _window(case):
    dates = case.get('date_range') if isinstance(case, dict) else None
    try:
        return date.fromisoformat(dates['start']), date.fromisoformat(dates['end'])
    except (TypeError, KeyError, ValueError):
        return None


def audit_receipt(receipt, root, ledger_dir=None):
    """Return leakage errors. ``ledger_dir`` overrides the receipt's ``trial_ledger_ref``."""
    if not isinstance(receipt, dict):
        return ['receipt: expected object']
    seal_ref = receipt.get('holdout_seal_hash')
    if ledger_dir is None:
        ref = receipt.get('trial_ledger_ref')
        if ref is not None:
            ledger_dir = _confined(root, ref)
            if ledger_dir is None:
                return ['trial_ledger_ref: expected relative path inside the artifact root']
    if ledger_dir is None or not (Path(ledger_dir) / 'ledger.jsonl').is_file():
        if seal_ref is not None:
            return ['holdout_seal_hash: no trial ledger found to verify the declared holdout read']
        return []
    try:
        view = read_ledger(ledger_dir)
    except LedgerError as exc:
        return [f'trial_ledger: {exc}']
    errors = []
    declared = None
    if seal_ref is not None:
        declared = view.holdout_for_hash(seal_ref)
        if declared is None:
            errors.append('holdout_seal_hash: no seal with this hash in the ledger')
    cycle = receipt.get('cycle_id')
    if declared is not None and not view.opens(declared, cycle):
        errors.append(f'holdout_seal_hash: protected read of {declared} has no ledger open event for cycle {cycle}')
    for holdout, seal in view.seals().items():
        start, end = date.fromisoformat(seal['start']), date.fromisoformat(seal['end'])
        for index, case in enumerate(receipt.get('cases') or []):
            window = _window(case)
            if window and window[0] <= end and start <= window[1] and holdout != declared:
                errors.append(f'cases.{index}.date_range: overlaps sealed holdout {holdout} '
                              f'({seal["start"]}..{seal["end"]}) without a declared, ledgered read')
    if isinstance(cycle, str):
        used = [c.get('attempts', {}).get('used') for c in receipt.get('cases') or []
                if isinstance(c, dict) and isinstance(c.get('attempts'), dict)]
        if all(type(u) is int for u in used) and sum(used) != view.trial_count(cycle):
            errors.append(f'attempts: receipt declares {sum(used)} attempt(s) but the ledger '
                          f'records {view.trial_count(cycle)} trial(s) for cycle {cycle}')
    return errors
