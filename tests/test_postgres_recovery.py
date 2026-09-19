"""Run against a disposable database, never an operator/production database."""
import os

import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

from app.backup_service.snapshot import build_snapshot, restore_snapshot, InvalidBackup
from app.database_migrations import upgrade_database
from app.models import AccessPolicy, PerimetrObject, Subject, SessionLease
from app.operator_settings import ensure_preferences
from app.pod_service import encrypt_secret, decrypt_secret
from app.settings import Settings


@pytest.mark.skipif(not os.getenv('PERIMETR_TEST_POSTGRES_URL'), reason='Dedicated disposable PostgreSQL not configured')
def test_postgresql_migration_and_complete_recovery():
    url = os.environ['PERIMETR_TEST_POSTGRES_URL']
    assert url.rsplit('/',1)[-1] == 'perimetr_test', 'Refusing a non-test database'
    upgrade_database(url)
    engine = create_engine(url.replace('postgresql://','postgresql+psycopg://',1))
    settings = Settings(_env_file=None, perimetr_access_key='pg fixture', perimetr_pod_signing_secret='pg isolated escrow secret')
    try:
        with Session(engine) as db:
            ensure_preferences(db, settings)
            policy = AccessPolicy(scope_type='subject',scope_id='pg',rules={'allowed':True})
            obj = PerimetrObject(name='PostgreSQL original',kind='workspace')
            db.add_all([policy,obj]);db.flush()
            subject = Subject(object_id=obj.id, access_policy_id=policy.id, name='Subject', runtime_type='pod',vless_uri_encrypted=encrypt_secret('vless://pg-secret@example.test', settings))
            db.add(subject);db.commit()
            object_id, subject_id = obj.id, subject.id
            data = build_snapshot(db, settings).getvalue()
            obj.name='Mutated';db.commit()
            with pytest.raises(InvalidBackup): restore_snapshot(data, db, settings.model_copy(update={'perimetr_pod_signing_secret':'wrong'}))
            assert db.get(PerimetrObject,object_id).name == 'Mutated'
            db.add(SessionLease(status='active',session_key_hash='test',access_scope='perimetr',transport='direct'));db.commit()
            restore_snapshot(data,db,settings);db.commit()
            assert db.get(PerimetrObject,object_id).name == 'PostgreSQL original'
            assert decrypt_secret(db.get(Subject,subject_id).vless_uri_encrypted, settings) == 'vless://pg-secret@example.test'
            assert db.scalar(select(SessionLease)) is None
    finally:
        engine.dispose()
