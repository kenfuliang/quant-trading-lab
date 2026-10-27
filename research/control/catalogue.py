"""Validated inventory of research ideas, not a registry of deployed strategies.

Data compatibility and implementation evidence are separate: definition_required
entries may have sufficient saved SPY data while lacking a frozen method. Suite
manifests own actual simulation evidence. No catalogue entry implies alpha.
"""
from pathlib import Path
import json

DEFAULT_PATH = Path(__file__).resolve().parents[1] / 'strategy_catalogue.json'
STATUSES = frozenset({'daily_spy_candidate', 'definition_required', 'blocked'})
FIELDS = frozenset({'id', 'slug', 'name', 'family', 'status',
                    'implementable_with_saved_spy', 'required_data',
                    'instrument_scope', 'proposed_rule', 'default_parameters',
                    'blockers', 'next_acceptance', 'source_refs', 'source_review',
                    'rule_provenance'})


def validate_catalogue(catalogue: dict) -> None:
    """Fail closed on incomplete IDs, unjustified readiness or unresolved sources."""
    if not isinstance(catalogue, dict) or catalogue.get('schema_version') != 1:
        raise ValueError('Catalogue schema_version must be 1.')
    strategies = catalogue.get('strategies')
    if not isinstance(strategies, list) or len(strategies) != 100:
        raise ValueError('Catalogue must contain exactly 100 entries.')
    ids = [entry.get('id') for entry in strategies if isinstance(entry, dict)]
    if len(ids) != 100 or any(type(i) is not int for i in ids) or set(ids) != set(range(1, 101)):
        raise ValueError('Catalogue IDs must be unique integers 1 through 100.')
    if len({entry.get('slug') for entry in strategies}) != 100:
        raise ValueError('Catalogue slugs must be unique.')
    if len({entry.get('family') for entry in strategies}) != 20:
        raise ValueError('Catalogue must preserve 20 named strategy families.')
    sources = catalogue.get('sources')
    if not isinstance(sources, dict):
        raise ValueError('Catalogue source registry must be a mapping.')
    for entry in strategies:
        if not FIELDS <= set(entry):
            raise ValueError(f"Entry {entry['id']} lacks required metadata.")
        if entry['status'] not in STATUSES:
            raise ValueError('Catalogue status cannot claim simulation or deployment readiness.')
        if type(entry['implementable_with_saved_spy']) is not bool:
            raise ValueError('SPY compatibility must be boolean.')
        for field in ('required_data', 'instrument_scope', 'blockers'):
            if not isinstance(entry[field], list) or not entry[field] or not all(isinstance(x, str) and x.strip() for x in entry[field]):
                raise ValueError(f'Entry {entry["id"]} requires explicit {field}.')
        for field in ('slug', 'name', 'family', 'proposed_rule', 'next_acceptance', 'rule_provenance'):
            if not isinstance(entry[field], str) or not entry[field].strip():
                raise ValueError(f'Entry {entry["id"]} requires {field}.')
        if not isinstance(entry['default_parameters'], dict) or not entry['default_parameters']:
            raise ValueError('Parameters must declare values or definition_required.')
        if entry['status'] == 'daily_spy_candidate' and not entry['implementable_with_saved_spy']:
            raise ValueError('Daily SPY candidate cannot require missing non-SPY inputs.')
        if entry['status'] == 'blocked' and entry['implementable_with_saved_spy']:
            raise ValueError('Data-compatible unresolved definitions use definition_required status.')
        if entry['source_review'] not in {'family_reference_only', 'unreviewed_exact_rule'}:
            raise ValueError('Catalogue cannot imply an exact published replication.')
        if not isinstance(entry['source_refs'], list) or any(ref not in sources for ref in entry['source_refs']):
            raise ValueError('Source references must resolve to the source registry.')


def load_catalogue(path: str | Path | None = None) -> dict:
    """Load the source catalogue and validate without changing readiness states."""
    with Path(path or DEFAULT_PATH).open(encoding='utf-8') as stream:
        catalogue = json.load(stream)
    validate_catalogue(catalogue)
    return catalogue
