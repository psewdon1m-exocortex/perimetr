# Perimetr database migrations

Production starts only after `alembic upgrade head` succeeds. The
`alembic_version` table is the authoritative current schema version. Every model
change must include one numbered revision, one upgrade strategy, one explicit
downgrade strategy and must pass:

```sh
python -m alembic -c alembic.ini heads
python -m alembic -c alembic.ini check
python -m pytest -q tests/test_migrations.py
```

The release manifest's numeric `database_schema` is derived from the actual
Alembic head by `scripts/build-release.sh`; it must never be edited separately.
Application startup serializes migrations with a PostgreSQL advisory lock, so
two replicas cannot migrate the same database concurrently.

## Mandatory backup and rollback

Production image changes are supported only through the VPS-local updater. It
receives and verifies a complete Perimetr ZIP before it replaces the container.
Therefore the pre-update backup exists before the new image can run any
migration. A direct `docker compose up` with a newer image bypasses this
guarantee and is not a supported production update procedure.

Prefer additive revisions that remain readable by the immediately previous
image. A revision that changes or removes data must either implement and test a
lossless `downgrade()` or deliberately raise an error from `downgrade()` and
declare backup restore as its rollback. For the latter case, rollback means:

1. restore the previous immutable image digest;
2. restore the updater's matching pre-update ZIP;
3. verify the previous image health and operator login.

An empty or lossy downgrade is forbidden.

## Release-candidate check against production data

Before publishing a migration release:

1. create a fresh production backup and database snapshot;
2. restore the snapshot into an isolated PostgreSQL instance with no route to
   production;
3. point a release-candidate Perimetr container at that copy;
4. run `alembic upgrade head`, `alembic check`, the complete pytest suite and
   API smoke tests;
5. test the declared rollback path on another restored copy;
6. record the source schema, target revision, duration and results in the
   release notes.

Never run migration verification directly against the production database.

## Revision 0004: Pod artifact pinning

Revision `0004` adds the non-null `artifact_sha256` field and its lookup index
to `pod_provisioning_records`. Existing records receive an empty value and are
resolved once through the verified current/factory artifact at their next
download. New records always store the selected SHA-256 at creation time. The
change is additive, so the `0003` image can still read a database upgraded to
`0004`; the explicit downgrade removes only the new index and column.
The existing `metadata_json` stores the signed immutable release manifest for
remote artifacts, allowing an exact checksum-verified re-download after a
system-backup restore where the local artifact cache is not present.

## Revision 0005: Pod decoy password hashes

Revision `0005` adds a non-null `decoy_password_hash` text column with an empty
default to both `pods` and `pod_provisioning_records`. Existing Pods therefore
retain primary-only authentication, while newly provisioned Pods may store a
separate salted decoy-password hash. The change is additive and contains no
plaintext credential migration. Downgrade removes only the two new columns, so
the `0004` image can read a database downgraded from `0005`.
