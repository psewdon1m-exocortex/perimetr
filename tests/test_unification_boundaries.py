import base64
import hashlib
import importlib.util
import io
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import tarfile

import pytest
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import padding, rsa
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import AuditEvent, SystemSetting
from app.redaction import bounded
from app.security import verify_password
from app.settings import Settings, get_settings
from test_operator_contract import operator_app, sign_in

ROOT = Path(__file__).resolve().parents[1]


def script_module(name):
    spec = importlib.util.spec_from_file_location(name, ROOT / 'scripts' / (name + '.py'))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_installer_preserves_exact_literal_seed_and_unrelated_multiline_data(tmp_path, monkeypatch):
    module = script_module('installer-env')
    path = tmp_path / '.env'
    key = "  雪 ${HOME} $abc\nPERIMETR_IMAGE=inside-the-key\t "
    path.write_text("PERIMETR_ACCESS_KEY='" + key + "'\nPERIMETR_IMAGE=old\n", encoding='utf-8')
    module.update(path, {'PERIMETR_IMAGE': 'new'})
    monkeypatch.setattr(sys, 'argv', ['installer-env.py', 'seed', str(path)])
    module.main()
    from dotenv import dotenv_values
    values = dotenv_values(path, interpolate=False)
    assert values['PERIMETR_ACCESS_KEY'] == key
    assert values['PERIMETR_IMAGE'] == 'new'
    assert verify_password(key, values['PERIMETR_ACCESS_KEY_HASH'])
    monkeypatch.delenv('PERIMETR_ACCESS_KEY', raising=False)
    monkeypatch.delenv('PERIMETR_ACCESS_KEY_HASH', raising=False)
    assert Settings(_env_file=path).perimetr_access_key == key


@pytest.mark.parametrize('attack', ['traversal', 'link', 'duplicate', 'oversize'])
def test_dependency_extraction_rejects_malicious_members_before_writing(tmp_path, attack):
    module = script_module('release-inputs')
    buffer = io.BytesIO()
    with tarfile.open(fileobj=buffer, mode='w:gz') as archive:
        member = tarfile.TarInfo('../outside' if attack == 'traversal' else 'updater/install.sh')
        if attack == 'link':
            member.type = tarfile.SYMTYPE; member.linkname = '/etc/passwd'
        elif attack == 'oversize':
            member.size = 129*1024*1024
            # A bounded sparse fixture: no payload is read during path/size preflight.
            class Zeros:
                def read(self, size): return b'\0' * size
            archive.addfile(member, Zeros())
        if attack != 'oversize': archive.addfile(member)
        if attack == 'duplicate': archive.addfile(member)
    with pytest.raises(ValueError):
        module.extract(buffer.getvalue(), tmp_path)
    assert not list(tmp_path.iterdir())


def test_release_signing_derives_public_trust_and_rejects_weak_key(tmp_path):
    key = rsa.generate_private_key(public_exponent=65537, key_size=3072)
    private = tmp_path / 'private.pem'
    private.write_bytes(key.private_bytes(serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8, serialization.NoEncryption()))
    manifest = tmp_path / 'release.json'; manifest.write_text('{"service":"perimetr","version":"2.0.0"}')
    public = tmp_path / 'public.pem'
    env = {**os.environ, 'RELEASE_SIGNING_KEY_FILE': str(private)}
    subprocess.run(['node', str(ROOT / 'scripts/sign-release.mjs'), '--export-public-key', str(public), str(manifest)], env=env, check=True, capture_output=True)
    envelope = json.loads(manifest.with_suffix('.json.sig.json').read_text())
    trusted = serialization.load_pem_public_key(public.read_bytes())
    trusted.verify(base64.b64decode(envelope['signature']), manifest.read_bytes(), padding.PSS(mgf=padding.MGF1(hashes.SHA256()), salt_length=32), hashes.SHA256())
    assert envelope['key_id'] == hashlib.sha256(trusted.public_bytes(serialization.Encoding.DER, serialization.PublicFormat.SubjectPublicKeyInfo)).hexdigest()
    output = tmp_path / 'bootstrap.sh'
    subprocess.run(['node', str(ROOT / 'scripts/build-bootstrap.mjs'), str(ROOT / 'bootstrap.sh'), str(public), str(output), '2.0.0'], check=True, capture_output=True)
    assert 'PRIVATE KEY' not in output.read_text() and '__PERIMETR_BOOTSTRAP_' not in output.read_text()
    for version in ['0.0.0', '02.0.0', '2.0.0-rc1', 'latest']:
        assert subprocess.run(['node', str(ROOT / 'scripts/build-bootstrap.mjs'), str(ROOT / 'bootstrap.sh'), str(public), str(output), version], capture_output=True).returncode != 0
    private.write_bytes(rsa.generate_private_key(public_exponent=65537, key_size=2048).private_bytes(serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8, serialization.NoEncryption()))
    assert subprocess.run(['node', str(ROOT / 'scripts/sign-release.mjs'), str(manifest)], env=env, capture_output=True).returncode != 0


def test_kernel_rejects_bad_proof_and_blocks_updates_until_host_sync(operator_app, monkeypatch, tmp_path):
    application, database = operator_app
    monkeypatch.setattr('app.settings.apply_register', lambda settings: settings)
    monkeypatch.setattr('app.settings.kernel_url_override', 'https://kernel.fixture.test')
    monkeypatch.setenv('PERIMETR_STATE_DIR', str(tmp_path)); get_settings.cache_clear()
    monkeypatch.setattr('app.kernel_connection.probe', lambda *_: 'revision-1')
    client = TestClient(application); sign_in(client, 'perimetr-entry-password')
    payload = {'current_key': 'wrong', 'token': 'dedicated-machine-credential'}
    assert client.post('/v1/settings/kernel/token', json=payload).status_code == 403
    assert not list(tmp_path.iterdir())
    payload['current_key'] = 'perimetr-entry-password'
    assert client.post('/v1/settings/kernel/token', json=payload).status_code == 200
    assert (tmp_path / 'secrets/kernel-service-token').read_text() == payload['token']
    response = client.get('/v1/settings/kernel')
    assert payload['token'] not in response.text and response.json()['helper_sync_required']
    assert client.post('/v1/updater/check').status_code == 409
    with Session(database) as db:
        settings = db.scalar(select(SystemSetting).where(SystemSetting.key == 'perimetr.kernel'))
        assert 'token' not in settings.value
    get_settings.cache_clear()


def test_redaction_cursor_ties_and_file_sink_failure(operator_app, monkeypatch):
    application, database = operator_app
    def broken(*args): raise OSError('disk full')
    monkeypatch.setattr('app.logs_service.service.write_audit_log', broken)
    client = TestClient(application); sign_in(client, 'perimetr-entry-password')
    for number in range(5):
        response = client.post('/v1/audit/ui', json={'action': 'test.redaction', 'payload': {'nested': [{'token': 'secret-value'}], 'url': 'https://u:p@example.test/path?token=sensitive'}, 'result': {'outcome': 'denied', 'number': number}})
        assert response.status_code == 200
    first = client.get('/v1/logs/audit?limit=2').json()
    second = client.get('/v1/logs/audit', params={'limit': 2, 'before': first['older_cursor']}).json()
    assert not ({item['id'] for item in first['entries']} & {item['id'] for item in second['entries']})
    content = json.dumps(first) + json.dumps(second)
    assert 'secret-value' not in content and 'sensitive' not in content and 'u:p' not in content
    assert len(json.dumps(bounded({'data': ['雪'*4096]*128})).encode()) <= 16384


def test_release_workflows_pin_actions_and_build_once():
    for file in (ROOT / '.github/workflows').glob('*.yml'):
        for action in re.findall(r'uses:\s*([^\s]+)', file.read_text()):
            assert action.startswith('./') or re.fullmatch(r'[^@]+@[a-f0-9]{40}', action), action
    release = (ROOT / '.github/workflows/release.yml').read_text()
    assert release.count('docker buildx build ') == 1
    assert 'environment: perimetr-release' in release
    assert '--phase pre-signing' in release and '--phase final' in release


def test_last_valid_register_survives_outage_without_crossing_credentials(monkeypatch, tmp_path):
    from app.kernel_register import KernelRegisterError
    monkeypatch.setenv('PERIMETR_STATE_DIR', str(tmp_path))
    monkeypatch.setenv('KERNEL_SERVICE_TOKEN', 'dedicated-token-one')
    monkeypatch.setattr('app.settings.kernel_url_override', 'https://kernel.fixture.test')
    monkeypatch.setattr('app.settings._last_register', None)
    def valid(settings):
        return settings.model_copy(update={'kernel_register_revision':'register-known','perimetr_sni':'known.example.test'})
    monkeypatch.setattr('app.settings.apply_register', valid)
    get_settings.cache_clear(); assert get_settings().kernel_register_revision == 'register-known'
    def unavailable(settings): raise KernelRegisterError('unavailable')
    monkeypatch.setattr('app.settings.apply_register', unavailable)
    get_settings.cache_clear()
    assert get_settings().kernel_register_stale and get_settings().perimetr_sni == 'known.example.test'
    monkeypatch.setenv('KERNEL_SERVICE_TOKEN', 'different-token')
    get_settings.cache_clear()
    with pytest.raises(KernelRegisterError): get_settings()
    get_settings.cache_clear()


def test_operational_log_filter_omits_exception_parameters():
    import logging
    from app.redaction import SafeLogFilter
    record = logging.LogRecord('uvicorn.error', logging.ERROR, __file__, 1, 'Upstream %s', ('https://user:pass@example.test?token=private',), (ValueError, ValueError('secret SQL parameter'), None))
    SafeLogFilter().filter(record)
    formatted = logging.Formatter().format(record)
    assert 'secret SQL parameter' not in formatted and 'private' not in formatted and 'user:pass' not in formatted
    assert 'ValueError' in formatted
