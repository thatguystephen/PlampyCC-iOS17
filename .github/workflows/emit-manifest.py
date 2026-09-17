import hashlib
import json
import os
from pathlib import Path

root = Path('dist')
def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()
def rel(path):
    return path.relative_to(root).as_posix()
packages = sorted((root / 'packages').glob('*.deb'))
symbols = sorted(path for path in (root / 'symbols').rglob('*') if path.is_file())
target_names = {'PlampyCC.dylib': 'tweak', 'PlampyCC': 'preferences'}
if len(packages) != 1:
    raise SystemExit(f'exactly one package is required, found {len(packages)}')
expected_symbols = {(arch, name) for arch in ('arm64', 'arm64e') for name in target_names}
actual_symbols = {(path.parent.name, path.name) for path in symbols}
if any(path.parent.parent != root / 'symbols' for path in symbols) or actual_symbols != expected_symbols:
    raise SystemExit('symbols must contain tweak and preferences targets for arm64 and arm64e')
manifest = {
    'schemaVersion': 1,
    'repository': os.environ['GITHUB_REPOSITORY'],
    'sourceCommit': (root / 'source-commit.txt').read_text().strip(),
    'workflowRun': {
        'url': f"{os.environ.get('GITHUB_SERVER_URL', 'https://github.com')}/{os.environ['GITHUB_REPOSITORY']}/actions/runs/{os.environ.get('GITHUB_RUN_ID', 'local')}",
        'id': os.environ.get('GITHUB_RUN_ID', 'local'),
    },
    'theos': {'commit': os.environ['THEOS_COMMIT']},
    'sdk': {'commit': os.environ['SDK_COMMIT'], 'selected': os.environ['SDK_NAME']},
    'xcodeVersion': (root / 'xcode-version.txt').read_text(),
    'target': 'iphone:clang:16.5:15.0',
    'scheme': 'rootless',
    'architectures': ['arm64', 'arm64e'],
    'packages': [{'filename': rel(path), 'sha256': digest(path)} for path in packages],
    'unstrippedBinaries': [
        {'filename': rel(path), 'target': target_names[path.name], 'architectures': [path.parent.name], 'sha256': digest(path)}
        for path in symbols
    ],
}
(root / 'build-manifest.json').write_text(json.dumps(manifest, indent=2, sort_keys=True) + '\n')
