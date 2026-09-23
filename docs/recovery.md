# Recovery and migration

## Full snapshot v4

Use Settings → Backup → Create and download snapshot. Save the ZIP and independently
escrow `PERIMETR_POD_SIGNING_SECRET` in protected storage outside this host. That
secret is intentionally absent from the ZIP. It decrypts archive rows, existing
Subject VLESS ciphertext and Pod enrollment tokens; replacing it makes old backups
unrecoverable. Losing the server and this secret cannot be repaired with a ZIP
alone. Test the escrow on an isolated instance before relying on it.

The supported budget is 128 MiB upload/archive, 256 MiB expanded total, 64 MiB per
member, 64 members and a maximum compression ratio of 200. Exact member names,
manifest authentication, SHA-256, sizes, row counts, schema, identifiers and
foreign-key references are checked before mutation. Duplicate paths/JSON keys,
links, extra files, traversal and wrong recovery secrets are rejected.

Run one API worker as supplied. A request barrier prevents overlapping mutations;
PostgreSQL transactions also acquire a common advisory lock. Restore performs a
single transactional replacement of the complete logical state. Deployment
variables, runtime caches and machine credentials remain external. Restored
operator sessions must sign in again with the key represented by the saved
verifier. Pending launch authorizations are revoked instead of replayed.

## Replacement-host drill

1. Prepare the same service version on an isolated host/database. Recreate the
   public service origin and independently provision deployment credentials.
2. Install the escrowed Pod recovery secret before starting the application.
   Seed a temporary operator key only to enter this empty instance.
3. Import the ZIP, review the preflight summary and explicitly confirm replacement.
   A validation failure must leave the previous database unchanged.
4. Sign in with the snapshot's Access Key. Verify entities, relations, policies,
   Pod identities and deny-lists. Verify actual Pod
   reconnection before routing production traffic to the restored host.
5. Re-provision Kernel's machine credential separately. Synchronize the saved
   Kernel connection to the host helper with `perimetr-install sync-kernel`.
6. Keep evidence of this exercise separately from the recovery archive.

## From 1.x

Back up the old database and retain the exact old image and deployment secret
before running Alembic revision `0006`. Existing salted operator password hashes
become Access Key verifiers unchanged; the username is removed and old direct
sessions are revoked. The migration does not change Pod login contracts.

Old ZIP v1/v2 archives are not full snapshots: some omit access policies,
relationships and identity state and can include decrypted VLESS credentials.
The v4 importer rejects them explicitly. To recover one, restore it with its
matching old image **in an isolated database**, inspect what that particular
archive actually contains, then upgrade that database and export a v4 ZIP.
An archive cannot reconstruct data omitted by its writer; use the original
complete database backup when those records are required. Protect/destroy the
legacy plaintext archive according to the operator's retention policy.

`0006` is forward-only. Rolling back to 1.x means selecting the saved old image
and restoring its matching pre-migration database; do not run the old application
against an upgraded database or feed a v4 archive into the old importer.

## Removing server Agent Node management (0007)

Before upgrading an existing installation, retain a full database backup and its
exact previous image. Revision `0007` permanently removes the 16 server-agent
tables (registry, assignments, endpoints, certificates, capabilities, heartbeats,
events, commands, jobs/results, approvals, revocations and controller identity).
It also deletes agent-bound sessions, removes their identity column and removes
the retired navigation item from saved preferences. Objects, Subjects, Properties,
Pods, policies, operator identity, other sessions and audit history remain intact.
No agent is contacted, revoked or uninstalled on its server.

Snapshot v4 uses database revision `0007` and contains only the nine current
authoritative tables. Old v3 snapshots are intentionally rejected before any
mutation. To recover retained data from v3, import it with the matching previous
image in an isolated database, apply migration `0007` and export v4. To roll back
the removal itself, restore the saved pre-migration database with its old image;
an empty-table downgrade cannot reconstruct deleted agent records.

## Updater recovery

The pre-update ZIP uses the full snapshot format of the installed source version.
Keep those original bytes for rollback through that matching image. Save completes only after the file
writer closes, or after a fallback download and explicit unchecked-by-default
acknowledgement. A 15-minute receipt binds request, head, version, filename, bytes,
size and checksum. The server keeps no durable ZIP copy. If acceptance is unclear,
look up the request before making another; never replay a different archive under
that identity. A later rollback uploads the original saved file with the recorded
filename/checksum. The helper reports the actual state; refresh installed runtime
versions after completion. A migration failure or failed rollback requires the
operator to retain the ZIP and inspect the same job, not manufacture success.
