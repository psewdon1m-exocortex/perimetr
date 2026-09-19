"""Verify the protected qualification run's source, candidate and catalog binding.

The qualification run must execute the exercises described by each catalog ID.
A native test-suite result alone is not a substitute for those observations.
"""
import json
import os
from pathlib import Path
import subprocess
import sys

root = Path(__file__).resolve().parents[1]
directory = Path(sys.argv[1])
run = json.loads((directory / 'run.json').read_text(encoding='utf-8'))
qualification = json.loads((directory / 'qualification.json').read_text(encoding='utf-8'))
policy = json.loads((root / '.release/known-problems-policy.json').read_text(encoding='utf-8'))
catalog = json.loads((root / '.release/known-problems-catalog.json').read_text(encoding='utf-8'))
revision = subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=root, text=True).strip()
assert run['headSha'] == revision and run['conclusion'] == 'success', 'Qualification run did not succeed on this commit'
assert qualification['revision'] == revision
assert qualification['catalog_sha256'] == policy['catalog_sha256']
assert qualification['version'] == (root / 'VERSION').read_text(encoding='utf-8').strip()
assert os.environ.get('CANDIDATE_DIGEST') and qualification['image_digest'] == os.environ['CANDIDATE_DIGEST']
required = {line.split('**')[1] for line in catalog['text'].splitlines() if line.startswith('| **')}
required -= set(policy['not_applicable']) | set(policy['final_checks'])
checks = qualification['checks']
assert len({item['id'] for item in checks}) == len(checks)
assert {item['id'] for item in checks} == required, 'Missing or unexpected qualification IDs'
for item in checks:
    assert item['status'] == 'PASS' and len(item['observation']) >= 40
    assert item['evidence'] and all(isinstance(link, str) and link.startswith('https://github.com/psewdon1m-exocortex/perimetr/actions/runs/') for link in item['evidence'])
print(f'Qualified {len(checks)} pre-signing IDs against source, catalog and candidate digest')
