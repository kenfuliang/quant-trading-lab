#!/usr/bin/env python3
"""Check current Python dependency layers and frozen source bytes without imports.

This is static architecture enforcement, not a sandbox or full runtime dependency
resolver. Dependencies inside functions and type-checking blocks are included.
"""
import ast
import hashlib
import importlib.util
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
PROJECT_ROOTS = frozenset({'research', 'reporting', 'paper_trading', 'scripts', 'tests'})
RESEARCH_LAYERS = frozenset({'features', 'policies', 'evaluation', 'control', 'studies'})
ALLOWED = {
    'features': {'features'},
    'policies': {'features', 'policies'},
    'evaluation': {'features', 'policies', 'evaluation', 'reporting'},
    'control': {'control'},
    'studies': set(RESEARCH_LAYERS) | {'reporting'},
    'reporting': {'reporting'},
    'paper_trading': {'paper_trading'},
    'commands': set(RESEARCH_LAYERS) | {'reporting', 'paper_trading', 'commands'},
}


def layer(module):
    parts = module.split('.')
    if parts[0] == 'research':
        return parts[1] if len(parts) > 1 and parts[1] in RESEARCH_LAYERS else None
    return {'reporting': 'reporting', 'paper_trading': 'paper_trading',
            'scripts': 'commands'}.get(parts[0])


def module_name(path):
    parts = list(path.with_suffix('').parts)
    if parts[-1] == '__init__':
        parts.pop()
    return '.'.join(parts)


def dependencies(tree, module, is_package):
    """Resolve static/relative imports and recognizable literal dynamic imports."""
    aliases = {}
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for item in node.names:
                aliases[item.asname or item.name.split('.')[0]] = item.name if item.asname else item.name.split('.')[0]
        elif isinstance(node, ast.ImportFrom) and not node.level and node.module:
            for item in node.names:
                aliases[item.asname or item.name] = node.module + '.' + item.name

    def qualified(node):
        if isinstance(node, ast.Name):
            return aliases.get(node.id, node.id)
        if isinstance(node, ast.Attribute):
            return qualified(node.value) + '.' + node.attr
        return ''

    package = module if is_package else module.rpartition('.')[0]
    edges, errors = [], []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            edges.extend((node.lineno, item.name) for item in node.names)
            if any(item.name == 'research' for item in node.names):
                errors.append((node.lineno, 'import an explicit research layer rather than the root namespace'))
        elif isinstance(node, ast.ImportFrom):
            if node.module == 'research' and not node.level and any(item.name == '*' for item in node.names):
                errors.append((node.lineno, 'import an explicit research layer rather than a root wildcard'))
            base = node.module or ''
            if node.level:
                try:
                    base = importlib.util.resolve_name('.' * node.level + base, package)
                except (ImportError, ValueError) as error:
                    errors.append((node.lineno, 'invalid relative import: ' + str(error)))
                    continue
            # Include the base and member: `from scripts import helper` is an edge.
            edges.append((node.lineno, base))
            edges.extend((node.lineno, base + '.' + item.name) for item in node.names if item.name != '*')
        elif isinstance(node, ast.Call):
            name = qualified(node.func)
            if name in {'importlib.util.spec_from_file_location', 'runpy.run_path',
                        'runpy.run_module', 'exec', 'eval'}:
                errors.append((node.lineno, 'opaque code loading is outside the checked import contract: ' + name))
            elif name in {'importlib.import_module', '__import__', 'builtins.__import__'}:
                if not node.args or not isinstance(node.args[0], ast.Constant) or not isinstance(node.args[0].value, str):
                    errors.append((node.lineno, 'dynamic import must use a literal module name'))
                    continue
                target = node.args[0].value
                if target.startswith('.'):
                    argument = node.args[1] if len(node.args) > 1 else next((k.value for k in node.keywords if k.arg == 'package'), None)
                    if not isinstance(argument, ast.Constant) or not isinstance(argument.value, str):
                        errors.append((node.lineno, 'relative dynamic import needs a literal package'))
                        continue
                    try:
                        target = importlib.util.resolve_name(target, argument.value)
                    except (ImportError, ValueError) as error:
                        errors.append((node.lineno, 'invalid dynamic relative import: ' + str(error)))
                        continue
                if name in {'__import__', 'builtins.__import__'} and (len(node.args) > 4 or any(k.arg == 'level' for k in node.keywords)):
                    errors.append((node.lineno, 'use a static relative import instead of __import__ level'))
                edges.append((node.lineno, target))
    return edges, errors


def check(root):
    root = Path(root)
    manifest_path = root / 'research/compatibility.json'
    if not manifest_path.is_file():
        return ['research/compatibility.json: missing frozen-source manifest'], 0
    manifest = json.loads(manifest_path.read_text())
    frozen = manifest['protected_files']
    errors = []
    for name, expected in sorted(frozen.items()):
        path = root / name
        if not path.is_file() or hashlib.sha256(path.read_bytes()).hexdigest() != expected:
            errors.append(f'{name}: frozen source/evidence changed or missing')
    frozen_modules = {module_name(Path(name)) for name in frozen
                      if name.endswith('.py') and Path(name).parts[0] in {'research', 'scripts', 'tests'}
                      and Path(name).name != '__init__.py'}
    paths = sorted(p for folder in ('research', 'reporting', 'paper_trading', 'scripts')
                   for p in (root / folder).rglob('*.py') if '__pycache__' not in p.parts)
    active = {module_name(p.relative_to(root)): p for p in paths if str(p.relative_to(root)) not in frozen
              or p.relative_to(root).parts[0] in {'reporting', 'paper_trading'}}
    graph = {name: set() for name in active}
    for module, path in active.items():
        relative = path.relative_to(root)
        source_layer = layer(module)
        if source_layer is None:
            errors.append(f'{relative}: current implementation needs an explicit package layer')
            continue
        try:
            tree = ast.parse(path.read_text(), filename=str(relative))
        except SyntaxError as error:
            errors.append(f'{relative}:{error.lineno}: invalid Python: {error.msg}')
            continue
        edges, problems = dependencies(tree, module, path.name == '__init__.py')
        exception = manifest.get('reviewed_opaque_loaders', {}).get(str(relative), {})
        pinned_loader = (exception.get('reason') and exception.get('sha256') == hashlib.sha256(path.read_bytes()).hexdigest())
        errors.extend(f'{relative}:{line}: {message}' for line, message in problems
                      if not (pinned_loader and message.startswith('opaque code loading') and 'runpy.run_path' in message))
        for line, target in edges:
            if target.split('.')[0] not in PROJECT_ROOTS:
                continue
            # Imported members are attributes unless they match a known module.
            resolved = target
            while resolved and resolved not in active and resolved not in frozen_modules:
                resolved = resolved.rpartition('.')[0]
            if resolved in frozen_modules:
                errors.append(f'{relative}:{line}: current code imports frozen implementation {resolved}')
                continue
            approved_paper_seam = (source_layer == 'paper_trading' and any(
                resolved == seam
                for seam in manifest.get('paper_research_seams', [])))
            target_layer = layer(target)
            # Allow package namespaces when their member edge carries the layer.
            if target in {'research', 'scripts', 'tests'}:
                if target == 'research':
                    continue
            if target_layer not in ALLOWED[source_layer] and not approved_paper_seam:
                errors.append(f'{relative}:{line}: {source_layer} cannot import {target} ({target_layer or "unclassified"})')
            if resolved in active:
                graph[module].add(resolved)
    visiting, visited = [], set()

    def visit(name):
        if name in visiting:
            errors.append('dependency cycle: ' + ' -> '.join(visiting[visiting.index(name):] + [name]))
            return
        if name in visited:
            return
        visiting.append(name)
        for target in sorted(graph[name]):
            visit(target)
        visiting.pop()
        visited.add(name)

    for name in sorted(graph):
        visit(name)
    return sorted(set(errors)), len(active)


def main():
    errors, count = check(ROOT)
    if errors:
        print('\n'.join(errors), file=sys.stderr)
        return 1
    print(f'Dependency boundary check passed: {count} current modules; frozen hashes, layer direction and static cycles.')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
