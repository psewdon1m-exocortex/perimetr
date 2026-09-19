"""Root installer pipe: update only the two Kernel fields in this service's env."""
import json
import os
from pathlib import Path
import re
import sys
from dotenv import dotenv_values, set_key

path = Path(sys.argv[1])
if os.geteuid() != 0 or not path.is_file() or path.is_symlink() or path.stat().st_uid != 0:
    raise SystemExit("Expected this service's root-owned regular .env")
payload = json.load(sys.stdin)
if set(payload) != {"KERNEL_URL", "KERNEL_SERVICE_TOKEN"}:
    raise SystemExit("Unexpected connection fields")
for value in payload.values():
    if not isinstance(value, str) or not value or not re.fullmatch(r"[A-Za-z0-9:/._~@%+?=&!-]+", value):
        raise SystemExit("Unsupported machine connection encoding")
before = dotenv_values(path, interpolate=False)
temporary = path.with_name('.kernel-sync-' + str(os.getpid()))
descriptor = os.open(temporary, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
with os.fdopen(descriptor, 'wb') as stream:
    stream.write(path.read_bytes())
try:
    for key, value in payload.items():
        set_key(temporary, key, value, quote_mode='never')
    after = dotenv_values(temporary, interpolate=False)
    if any(after.get(key) != value for key, value in before.items() if key not in payload):
        raise SystemExit('Unrelated operator input changed; refusing the update')
    os.chmod(temporary, 0o600)
    with temporary.open('rb+') as stream:
        os.fsync(stream.fileno())
    os.replace(temporary, path)
finally:
    temporary.unlink(missing_ok=True)
