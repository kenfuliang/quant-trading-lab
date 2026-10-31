"""Read-only artifact/budget checks, separate from financial qualification."""
from pathlib import Path
import hashlib
import json
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from research.studies.checkpoint_20261031.capm_review import audit_metrics


def main():
    web=Path('.local/performance/capm-spy-v1')
    root=Path('.local/capm-spy-v1')
    manifest=json.loads((web/'manifest.json').read_text())
    for item in manifest['files']:
        path=Path(item['path'])
        if path.stat().st_size != item['bytes'] or hashlib.sha256(path.read_bytes()).hexdigest() != item['sha256']:
            raise ValueError('Artifact changed: '+str(path))
    report=json.loads((web/'review.json').read_text())
    plan=report['plan']
    original=Path('research/quantconnect/sources/capm_framework_original.py')
    if hashlib.sha256(original.read_bytes()).hexdigest()!=plan['original_sha256']:
        raise ValueError('Upstream fixture changed')
    parent=json.loads((root/'budget.json').read_text())
    if parent['status']!='closed' or len(parent['attempts'])>5:
        raise ValueError('Parent budget not closed/in bounds')
    extension_path=root/'accounting-retest-budget.json'
    if extension_path.exists():
        ext=json.loads(extension_path.read_text())
        if ext['status']!='closed' or len(ext['attempts'])>1:
            raise ValueError('Authorized extension not closed/in bounds')
    gate=json.loads((root/'probe-gate.json').read_text())
    if not gate['passed']:
        raise ValueError('Probe did not pass')
    for case in ['probe','capm','spy']:
        source=root/f'{case}-source.py'
        if hashlib.sha256(source.read_bytes()).hexdigest()!=plan['source_hashes'][case]:
            raise ValueError('Frozen case source drift')
    passed=[]
    for case in ['capm','spy']:
        try:
            audit_metrics(report['results'][case]);passed.append(case)
        except ValueError:
            if report['comparison_eligible']:
                raise
    if report['comparison_eligible'] and (passed!=['capm','spy'] or not report['accounting_only_retest_reproduced']):
        raise ValueError('Invalid qualified verdict')
    print(json.dumps(dict(artifact_integrity=True,files=len(manifest['files']),parent_attempts=len(parent['attempts']),extension_attempts=len(ext['attempts']) if extension_path.exists() else 0,financial_cases_passed=passed,comparison_eligible=report['comparison_eligible'],limits='No independent vendor-data or cash/dividend replay; exact hosted tutorial identity remains unverified.')))

if __name__=='__main__':
    main()
