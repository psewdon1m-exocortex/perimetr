import hashlib
import io
import json
from zipfile import ZipFile

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

from app.backup_service.snapshot import InvalidBackup, build_snapshot, preflight, restore_snapshot
from app.database import Base
from app.models import AccessPolicy, PerimetrObject, Subject, SystemSetting, SessionLease
from app.operator_settings import ensure_preferences
from app.pod_service import encrypt_secret, decrypt_secret
from app.settings import Settings, get_settings
from test_operator_contract import operator_app, sign_in


@pytest.fixture
def snapshot_database(tmp_path):
    engine = create_engine('sqlite://')
    Base.metadata.create_all(engine)
    settings = Settings(_env_file=None, perimetr_access_key='  exact key  ', perimetr_pod_signing_secret='independent-recovery-key', perimetr_logs_dir=str(tmp_path))
    with Session(engine) as db:
        ensure_preferences(db, settings)
        policy = AccessPolicy(scope_type='subject', scope_id='root', rules={'allowed': True})
        obj = PerimetrObject(name='Recover me', kind='workspace')
        db.add_all([obj, policy]); db.flush()
        subject = Subject(object_id=obj.id, access_policy_id=policy.id, name='Private', runtime_type='pod',
                          vless_uri_encrypted=encrypt_secret('vless://sensitive@example.test', settings))
        db.add(subject); db.commit()
        yield db, settings
    engine.dispose()


def test_full_recovery_preserves_policies_verifier_and_ciphertext(snapshot_database):
    db, settings = snapshot_database
    before = db.scalar(select(Subject)).vless_uri_encrypted
    verifier = db.scalar(select(SystemSetting)).value['auth']['access_key_hash']
    data = build_snapshot(db, settings).getvalue()
    info = preflight(data, settings)
    assert info['members']['data/access_policies.jsonl']['rows'] == 1
    assert b'sensitive' not in data and b'exact key' not in data and b'independent-recovery-key' not in data
    db.scalar(select(PerimetrObject)).name = 'Changed'
    db.add(SessionLease(status='active', session_key_hash='old', access_scope='perimetr', transport='direct'))
    db.commit()
    restore_snapshot(data, db, settings); db.commit()
    assert db.scalar(select(PerimetrObject)).name == 'Recover me'
    assert db.scalar(select(Subject)).vless_uri_encrypted == before
    assert decrypt_secret(before, settings) == 'vless://sensitive@example.test'
    assert db.scalar(select(SystemSetting)).value['auth']['access_key_hash'] == verifier
    assert db.scalar(select(SessionLease)) is None


def test_insert_failure_rolls_back_the_entire_replacement(snapshot_database, monkeypatch):
    from sqlalchemy.exc import SQLAlchemyError
    from sqlalchemy.sql.dml import Insert
    db, settings = snapshot_database
    data = build_snapshot(db, settings).getvalue()
    db.scalar(select(PerimetrObject)).name = 'Preserve current state'; db.commit()
    original = db.execute
    def fail_insert(statement, *args, **kwargs):
        if isinstance(statement, Insert): raise SQLAlchemyError('Simulated storage failure')
        return original(statement, *args, **kwargs)
    monkeypatch.setattr(db, 'execute', fail_insert)
    with pytest.raises(InvalidBackup, match='existing data retained'):
        restore_snapshot(data, db, settings)
    db.expire_all()
    assert db.scalar(select(PerimetrObject)).name == 'Preserve current state'


@pytest.mark.parametrize('attack', ['traversal', 'duplicate', 'unknown', 'tamper', 'wrong_key', 'oversize'])
def test_archive_rejected_before_mutation(snapshot_database, attack):
    db, settings = snapshot_database
    data = build_snapshot(db, settings).getvalue()
    if attack == 'wrong_key':
        settings = settings.model_copy(update={'perimetr_pod_signing_secret': 'wrong'})
    elif attack == 'oversize':
        settings = settings.model_copy(update={'perimetr_max_backup_upload_bytes': 10})
    else:
        output = io.BytesIO()
        with ZipFile(io.BytesIO(data)) as original, ZipFile(output, 'w') as archive:
            for name in original.namelist():
                value = original.read(name)
                if attack == 'tamper' and name == 'data/objects.jsonl': value = b'x' + value[1:]
                archive.writestr(name, value)
            if attack != 'tamper':
                archive.writestr({'traversal': '../escape', 'duplicate': 'manifest.json', 'unknown': 'extra.txt'}[attack], b'{}')
        data = output.getvalue()
    with pytest.raises(InvalidBackup):
        restore_snapshot(data, db, settings)
    assert db.scalar(select(PerimetrObject)).name == 'Recover me'


def test_update_requires_saved_exact_archive_and_scoped_receipt(operator_app, monkeypatch):
    application, _ = operator_app
    monkeypatch.setenv('UPDATER_CONTROL_TOKEN', 'fixture-control-secret')
    get_settings.cache_clear()
    captured = []
    def helper(method, path, payload=None, timeout=35):
        if path == '/v2/check': return {'update_available': True, 'available_version': '2.0.0'}
        if path.startswith('/v1/jobs?'): return {'jobs': []}
        captured.append(payload)
        return {'id': 'job1', 'state': 'REQUESTED'}
    monkeypatch.setattr('app.operations_api.call_helper', helper)
    client = TestClient(application)
    sign_in(client, 'perimetr-entry-password')
    prepared = client.post('/v1/updater/prepare', json={'request_id': 'unique-request-id-001', 'version': '2.0.0'})
    assert prepared.status_code == 200, prepared.text
    headers = {'Content-Type': 'application/zip', 'X-Backup-Receipt': prepared.headers['x-backup-receipt'], 'X-Operator-Saved': 'false'}
    url = '/v1/updater/install?request_id=unique-request-id-001&version=2.0.0'
    assert client.post(url, content=prepared.content, headers=headers).status_code == 409
    headers['X-Operator-Saved'] = 'true'
    assert client.post(url, content=prepared.content + b'x', headers=headers).status_code == 409
    assert client.post(url.replace('2.0.0', '3.0.0'), content=prepared.content, headers=headers).status_code == 409
    assert not captured
    assert client.post(url, content=prepared.content, headers=headers).status_code == 202
    assert captured[0]['operator_saved'] is True
    assert captured[0]['backup']['sha256'] == hashlib.sha256(prepared.content).hexdigest()
    get_settings.cache_clear()
