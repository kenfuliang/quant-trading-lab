"""Deterministic evidence navigation; original records retain all result authority."""
import hashlib
import json
from pathlib import Path, PurePosixPath
import re

REGISTRY = 'research/evidence-registry.json'
OUTPUTS = ('docs/research-evidence-index.json', 'docs/research-evidence-index.md')
ROLES = ('plans', 'results', 'failures', 'lessons')
STATES = {'present', 'unpublished', 'not_recorded', 'not_applicable'}
KINDS = {'plan', 'receipt', 'report', 'narrative', 'artifact'}


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def local_path(root, name):
    if not isinstance(name, str) or not re.fullmatch(r'[A-Za-z0-9_./-]+', name):
        raise ValueError('Reference needs a safe repository-relative path')
    parts = PurePosixPath(name).parts
    if not parts or name.startswith('/') or '..' in parts or name != str(PurePosixPath(name)):
        raise ValueError('Reference path escapes canonical repository layout')
    if not (name.startswith('research/plans/') or name == 'research/README.md' or name.startswith('docs/') or name.startswith('reports/')):
        raise ValueError('Reference is outside published research evidence roots')
    path = root / name
    if not path.resolve().is_relative_to(root.resolve()):
        raise ValueError('Reference symlink escapes repository')
    return path


def anchors(text):
    text = re.sub(r'^```.*?^```[^\n]*', '', text, flags=re.M | re.S)
    found, counts = set(), {}
    for heading in re.findall(r'^#{1,6}\s+(.+?)\s*#*\s*$', text, re.M):
        slug = re.sub(r'[^\w\s-]', '', heading.lower()).replace(' ', '-')
        number = counts.get(slug, 0)
        counts[slug] = number + 1
        found.add(slug if not number else f'{slug}-{number}')
    return found


def build(root):
    root = Path(root)
    registry_path = root / REGISTRY
    data = json.loads(registry_path.read_text())
    if set(data) != {'schema_version', 'updated', 'scope', 'studies'} or data['schema_version'] != 1:
        raise ValueError('Unsupported registry schema')
    if not re.fullmatch(r'\d{4}-\d{2}-\d{2}', data['updated']) or not data['scope'].strip():
        raise ValueError('Registry needs update date and explicit scope')
    studies = data['studies']
    if not isinstance(studies, list) or not studies:
        raise ValueError('Registry needs study entries')
    ids, owned_plans, output = set(), {}, []
    used = set()
    for study in sorted(studies, key=lambda s: s['id']):
        if set(study) != {'id', 'title', 'family', 'reported_state', 'note', *ROLES}:
            raise ValueError('Study fields must include all four evidence roles')
        identifier = study['id']
        if not re.fullmatch(r'[a-z0-9][a-z0-9-]*', identifier) or identifier in ids:
            raise ValueError('Duplicate or invalid study ID: ' + identifier)
        ids.add(identifier)
        for field in ('title', 'family', 'reported_state', 'note'):
            if not isinstance(study[field], str) or not study[field].strip():
                raise ValueError('Study needs nonempty ' + field)
        entry = {k: study[k] for k in ('id', 'title', 'family', 'reported_state', 'note')}
        for role in ROLES:
            refs = study[role]
            if not isinstance(refs, list) or not refs:
                raise ValueError(identifier + ': each role needs evidence or explicit unavailable reason')
            rendered, seen = [], set()
            for ref in refs:
                if not isinstance(ref, dict) or ref.get('state') not in STATES:
                    raise ValueError(identifier + ': invalid reference state')
                state = ref['state']
                fields = {'state', 'path', 'kind', 'note'} if state == 'present' else {'state', 'note'}
                if set(ref) != fields or not isinstance(ref['note'], str) or not ref['note'].strip():
                    raise ValueError(identifier + ': reference fields/reason invalid')
                result = dict(ref)
                if state == 'present':
                    if ref['kind'] not in KINDS:
                        raise ValueError('Invalid reference kind')
                    name, separator, anchor = ref['path'].partition('#')
                    if name in OUTPUTS:
                        raise ValueError('Derived index views cannot be evidence sources')
                    path = local_path(root, name)
                    if path.suffix not in {'.json', '.md', '.csv', '.png', '.svg', '.html', '.txt'}:
                        raise ValueError('Unsupported evidence file type')
                    if not path.is_file():
                        raise ValueError(identifier + ': missing referenced file: ' + name)
                    if separator and (path.suffix != '.md' or anchor not in anchors(path.read_text())):
                        raise ValueError(identifier + ': missing Markdown anchor: ' + ref['path'])
                    if ref['path'] in seen:
                        raise ValueError(identifier + ': duplicate role reference')
                    seen.add(ref['path'])
                    result['sha256'] = digest(path)
                    used.add(name)
                    if role == 'plans':
                        if ref['kind'] != 'plan' or not name.startswith('research/plans/') or path.suffix != '.json' or separator:
                            raise ValueError('Plans must name a published JSON plan')
                        json.loads(path.read_text())
                        if name in owned_plans:
                            raise ValueError('Plan has multiple study owners: ' + name)
                        owned_plans[name] = identifier
                rendered.append(result)
            entry[role] = rendered
        output.append(entry)
    plans = {str(p.relative_to(root)) for p in (root / 'research/plans').rglob('*.json')}
    if plans != set(owned_plans):
        raise ValueError('Plan coverage mismatch: unowned=' + str(sorted(plans-set(owned_plans))) +
                         '; unexpected=' + str(sorted(set(owned_plans)-plans)))
    supporting = sorted(str(p.relative_to(root)) for p in (root / 'docs/tasks').rglob('*')
                        if p.is_file() and p.suffix in {'.md', '.json', '.csv'} and str(p.relative_to(root)) not in used)
    return {'schema_version': 1, 'updated': data['updated'], 'scope': data['scope'],
            'authority': 'Navigation only; present means file available, not independently verified or reproduced.',
            'registry_sha256': digest(registry_path), 'generator_sha256': digest(Path(__file__)),
            'coverage': {'studies': len(output), 'published_plans': len(plans),
                         'unowned_plans': 0, 'supporting_records_unassigned': len(supporting)},
            'studies': output, 'supporting_records_unassigned': supporting}


def markdown(index):
    lines = ['---', 'status: active', 'updated: ' + index['updated'], 'owner: research-maintainers', '---', '',
             '# Generated research evidence index', '',
             'Generated by `scripts/current/research_index.py --write`; edit the registry, not this view.', '',
             index['scope'], '', index['authority'], '',
             'Reported states are registry annotations. Receipts/narratives do not imply raw artifacts are published.',
             'Unavailable failure evidence does not mean zero failed attempts. No trial budget is reopened.', '',
             '[Machine-readable view](research-evidence-index.json) · [Index contract](architecture.md#research-evidence-index)', '',
             f"Coverage: {index['coverage']['studies']} studies; {index['coverage']['published_plans']} published plans; no unowned plans.", '',
             '| Study | Family | Reported state |', '| --- | --- | --- |']
    def safe(text):
        return text.replace('|', '&#124;').replace('\n', ' ')
    for study in index['studies']:
        lines.append(f"| [{safe(study['title'])}](#{study['id']}) | {safe(study['family'])} | {safe(study['reported_state'])} |")
    for study in index['studies']:
        lines += ['', '## ' + study['id'], '', '**' + safe(study['title']) + '** — ' + safe(study['note']), '']
        for role in ROLES:
            lines += ['### ' + role.capitalize(), '']
            for ref in study[role]:
                if ref['state'] == 'present':
                    lines.append(f"- [{safe(ref['path'])}](../{ref['path']}) ({ref['kind']}): {safe(ref['note'])}")
                else:
                    lines.append(f"- **{ref['state']}**: {safe(ref['note'])}")
            lines.append('')
    lines += ['## Other supporting records', '',
              'Discovered task/receipt files not assigned to a study above. Their presence is not a study classification or execution claim.', '']
    lines.extend(f'- [{name}](../{name})' for name in index['supporting_records_unassigned'])
    return '\n'.join(lines).rstrip() + '\n'


def expected_outputs(root):
    index = build(root)
    return {OUTPUTS[0]: json.dumps(index, indent=2, ensure_ascii=False) + '\n', OUTPUTS[1]: markdown(index)}


def generate(root, write=False):
    root = Path(root)
    expected = expected_outputs(root)  # Validate everything before creating outputs.
    stale = [name for name, content in expected.items() if not (root / name).is_file() or (root / name).read_text() != content]
    if write:
        for name, content in expected.items():
            path = root / name
            path.parent.mkdir(parents=True, exist_ok=True)
            temporary = path.with_suffix(path.suffix + '.tmp')
            temporary.write_text(content)
            temporary.replace(path)
    elif stale:
        raise ValueError('Generated research evidence index is stale: ' + ', '.join(stale))
    return build(root)['coverage']
