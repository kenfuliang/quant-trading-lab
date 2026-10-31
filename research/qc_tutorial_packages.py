"""Static source-package qualification. Never execute downloaded strategies."""
import ast
import hashlib
import io
import json
from pathlib import PurePosixPath
import re
import sys
import zipfile


def digest(body):
    return hashlib.sha256(body).hexdigest()


def inspect_python(body):
    """Syntax/import checks are not dependency installation or runtime verification."""
    text = body.decode('utf-8-sig')
    try:
        tree = ast.parse(text)
    except (SyntaxError, ValueError) as exc:
        return {'syntax': 'invalid', 'error': str(exc), 'imports': [], 'external_imports': [], 'dependency_extraction_complete': False, 'runtime_verified': False}
    imports = []
    hazards = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imports.extend({'module': n.name, 'line': node.lineno} for n in node.names)
        elif isinstance(node, ast.ImportFrom):
            imports.append({'module': '.' * node.level + (node.module or ''), 'line': node.lineno})
        elif isinstance(node, ast.Call):
            name = ast.unparse(node.func)
            if any(x in name for x in ('chdir', 'download', 'read_csv', 'read_pickle', 'pickle.loads', 'ObjectStore', 'exec', 'eval', 'subprocess')):
                hazards.append({'call': name, 'line': node.lineno})
    names = sorted({x['module'] for x in imports})
    classes = [n.name for n in tree.body if isinstance(n, ast.ClassDef)]
    functions = [n.name for n in tree.body if isinstance(n, ast.FunctionDef)]
    placeholders = [n.lineno for n in ast.walk(tree) if isinstance(n, ast.Constant) and n.value is Ellipsis]
    return {'syntax': 'valid', 'imports': imports,
            'stdlib_imports': sorted(n for n in names if n.split('.')[0] in sys.stdlib_module_names),
            'external_imports': sorted(n for n in names if n.split('.')[0] not in sys.stdlib_module_names),
            'classes': classes, 'functions': functions, 'dependency_extraction_complete': False, 'ellipsis_lines': placeholders,
            'side_effect_or_input_calls': hazards, 'runtime_verified': False}


def license_gate(body, license_body, root_apache_verified=False):
    """A file-level grant can apply without a repo grant; wrapper licenses cannot."""
    header = body[:2000].decode('utf-8-sig', errors='replace')
    apache_text = b'Apache License' in license_body and b'Version 2.0' in license_body
    per_file = bool(re.search(r'Licensed under the Apache License, Version 2\.0', header) and re.search(r'Copyright', header, re.I))
    if apache_text and (per_file or root_apache_verified):
        return {'permitted': True, 'license': 'Apache-2.0',
                'basis': 'explicit_file_header' if per_file else 'reviewed_pinned_repository_license',
                'conditions': ['retain original source headers', 'include Apache-2.0 text', 'preserve applicable notices', 'mark any changes'],
                'data_rights': 'not_conferred'}
    return {'permitted': False, 'license': 'unestablished', 'basis': 'no_verified_applicable_grant', 'data_rights': 'not_conferred'}


def make_archive(files, permission):
    """Return deterministic source-only ZIP bytes; reject unsafe paths or no grant."""
    if not permission.get('permitted'):
        raise ValueError('Source export blocked: no applicable permission')
    stream = io.BytesIO()
    with zipfile.ZipFile(stream, 'w', compression=zipfile.ZIP_DEFLATED) as archive:
        for name, body in sorted(files.items()):
            p = PurePosixPath(name)
            if p.is_absolute() or '..' in p.parts or '\\' in name or ':' in name or not p.parts:
                raise ValueError('Unsafe archive path')
            info = zipfile.ZipInfo(name, date_time=(2026, 10, 26, 0, 0, 0))
            info.compress_type = zipfile.ZIP_DEFLATED
            info.external_attr = 0o100644 << 16
            archive.writestr(info, body)
    return stream.getvalue()


def archive_inventory(body):
    with zipfile.ZipFile(io.BytesIO(body)) as archive:
        return [{'path': n, 'sha256': digest(archive.read(n)), 'bytes': len(archive.read(n))} for n in archive.namelist()]
