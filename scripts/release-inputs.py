"""Stage exact dependencies from reviewed SHA-256 pins; never latest."""
import hashlib
import io
import json
from pathlib import Path, PurePosixPath
import re
import sys
import tarfile
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parents[1]
STABLE = r'(?:0|[1-9]\d*)\.(?:0|[1-9]\d*)\.(?:0|[1-9]\d*)'


def validate(lock):
    for name in ('updater', 'pod'):
        item = lock[name]
        if not re.fullmatch(STABLE, item['version']) or item['version'] == '0.0.0':
            raise ValueError('Invalid dependency version: ' + name)
        if (ROOT / '.release' / (name + '.version')).read_text().strip() != item['version']:
            raise ValueError('Version pin mismatch: ' + name)
        for field in ['sha256'] + (['public_key_sha256'] if name == 'pod' else []):
            if not re.fullmatch(r'[a-f0-9]{64}', item.get(field) or ''):
                raise ValueError('Release blocked: independently verify and pin ' + name + '.' + field)
    if tuple(map(int, lock['updater']['version'].split('.'))) < (0, 5, 0):
        raise ValueError('Updater protocol 2 is required')


def fetch(service, version, name, expected):
    url = f'https://github.com/psewdon1m-exocortex/{service}/releases/download/{service}-v{version}/{name}'
    with urlopen(Request(url, headers={'User-Agent': 'perimetr-release'}), timeout=120) as response:
        data = response.read(384 * 1024 * 1024 + 1)
    if len(data) > 384 * 1024 * 1024 or hashlib.sha256(data).hexdigest() != expected:
        raise ValueError('Pinned dependency checksum mismatch: ' + name)
    return data


def extract(data, destination):
    with tarfile.open(fileobj=io.BytesIO(data), mode='r:gz') as archive:
        members = archive.getmembers()
        total = 0
        seen = set()
        for entry in members:
            path = PurePosixPath(entry.name)
            if path.is_absolute() or '..' in path.parts or '\\' in entry.name or ':' in entry.name or entry.name in seen:
                raise ValueError('Unsafe dependency path')
            if not entry.isfile() and not entry.isdir():
                raise ValueError('Dependency links/devices are forbidden')
            total += entry.size
            if len(members) > 1024 or total > 384*1024*1024 or entry.size > 128*1024*1024:
                raise ValueError('Dependency expansion limit exceeded')
            seen.add(entry.name)
        for entry in members:
            target = destination.joinpath(*PurePosixPath(entry.name).parts)
            if entry.isdir():
                target.mkdir(parents=True, exist_ok=True)
            else:
                target.parent.mkdir(parents=True, exist_ok=True)
                with target.open('xb') as stream, archive.extractfile(entry) as source:
                    while chunk := source.read(65536):
                        stream.write(chunk)
                target.chmod(0o755 if entry.mode & 0o111 else 0o644)


def main():
    lock = json.loads((ROOT / '.release/dependencies.json').read_text())
    validate(lock)
    if '--validate-only' in sys.argv:
        return
    destination = ROOT / '.release-inputs'
    destination.mkdir(exist_ok=True)
    updater = lock['updater']
    extract(fetch('updater', updater['version'], f"updater-{updater['version']}-install.tar.gz", updater['sha256']), destination)
    for name, field in [('pod.exe', 'sha256'), ('pod-update-public-key.pem', 'public_key_sha256')]:
        (ROOT / 'pod-runtime' / name).write_bytes(fetch('pod', lock['pod']['version'], name, lock['pod'][field]))


if __name__ == '__main__':
    main()
