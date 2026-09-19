"""Literal dotenv edits: never source operator text as shell or interpolate it."""
import base64
import hashlib
import os
from pathlib import Path
import secrets
import sys
from dotenv import dotenv_values, set_key


def update(path, changes):
    if path.is_symlink() or not path.is_file():
        raise ValueError("Expected a regular service environment file")
    before = dotenv_values(path, interpolate=False)
    temp = path.with_name('.env-edit-' + secrets.token_hex(8))
    try:
        fd = os.open(temp, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        with os.fdopen(fd, 'wb') as stream:
            stream.write(path.read_bytes())
        for key, value in changes.items():
            set_key(temp, key, value, quote_mode='always')
        after = dotenv_values(temp, interpolate=False)
        if any(after.get(key) != value for key, value in before.items() if key not in changes):
            raise ValueError("Refusing to change unrelated operator input")
        with temp.open('rb+') as stream:
            os.fsync(stream.fileno())
        os.chmod(temp, 0o600)
        os.replace(temp, path)
    finally:
        temp.unlink(missing_ok=True)


def main():
    action, filename, *args = sys.argv[1:]
    path = Path(filename)
    values = dotenv_values(path, interpolate=False)
    if action == 'get':
        sys.stdout.write(values.get(args[0]) or '')
    elif action == 'set':
        update(path, {args[0]: args[1]})
    elif action == 'seed':
        value = values.get('PERIMETR_ACCESS_KEY')
        if value is None or value == '':
            raise SystemExit('Enter the initial Access Key; it is never generated automatically')
        salt = secrets.token_bytes(16)
        derived = hashlib.scrypt(value.encode(), salt=salt, n=16384, r=8, p=1, dklen=64, maxmem=64*1024*1024)
        encode = lambda data: base64.urlsafe_b64encode(data).rstrip(b'=').decode()
        update(path, {'PERIMETR_ACCESS_KEY_HASH': 'scrypt$' + encode(salt) + '$' + encode(derived)})
    else:
        raise SystemExit('Unsupported environment operation')


if __name__ == '__main__':
    main()
