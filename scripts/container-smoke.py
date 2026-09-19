"""Exercise a disposable image under the production process security boundary."""
import json
import secrets
import subprocess
import sys
import time

image = sys.argv[1]
name = 'perimetr-smoke-' + secrets.token_hex(6)
def docker(*args):
    return subprocess.check_output(['docker', *args], text=True).strip()
try:
    docker('run', '-d', '--name', name, '--read-only', '--cap-drop=ALL', '--security-opt=no-new-privileges',
           '--tmpfs', '/app/.tmp:uid=10001,gid=10001,size=64m', '--tmpfs', '/tmp:size=64m',
           '-e', 'PERIMETR_ENV=development', '-e', 'PERIMETR_ACCESS_KEY=smoke fixture',
           '-e', 'PERIMETR_DATABASE_URL=sqlite:////app/.tmp/smoke.sqlite', '-e', 'KERNEL_URL=', '-e', 'KERNEL_SERVICE_TOKEN=', image)
    for _ in range(45):
        result = subprocess.run(['docker', 'exec', name, 'python', '-c',
            "import urllib.request; print(urllib.request.urlopen('http://127.0.0.1:18080/v1/health',timeout=2).read().decode())"], capture_output=True, text=True)
        if result.returncode == 0:
            break
        time.sleep(2)
    assert result.returncode == 0, 'Image did not become ready'
    assert json.loads(result.stdout)['version'] == open('VERSION').read().strip()
    checks = """import os, urllib.request, urllib.error
assert os.getuid() == 10001
assert os.stat('/app/.tmp').st_uid == 10001
try:
    open('/app/write-probe', 'w')
    raise AssertionError('Image root is writable')
except OSError:
    pass
try:
    urllib.request.urlopen('http://127.0.0.1:18080/v1/objects')
    raise AssertionError('Anonymous topology disclosure')
except urllib.error.HTTPError as error:
    assert error.code == 403
print('health/version, nonroot, readonly root, writable state, private API: PASS')
"""
    print(docker('exec', name, 'python', '-c', checks))
finally:
    subprocess.run(['docker', 'rm', '-f', name], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
