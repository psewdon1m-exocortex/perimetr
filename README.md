# Perimetr

Perimetr owns Objects, Subjects, shared Properties and correlations, Pod identities,
Agent Node assignments, jobs, approvals and the controller identity. The API uses
FastAPI, SQLAlchemy and Alembic; production state is PostgreSQL. The browser shell
is served locally with no third-party assets.

The central specification is authoritative. The applicable contracts, decisions
and verification limits are recorded in [docs/unification.md](docs/unification.md).
This working tree implements the **2.0.0 migration**; it does not represent a
published or production-qualified release.

## Operator interface

Sign in with one exact, nonempty Access Key. There is no operator username or
composition policy. Whitespace, Unicode and punctuation are significant. The
initial `.env` seed becomes a salted database verifier; subsequent environment
changes do not reset it. Existing 1.x database password verifiers are migrated
without changing their accepted text. Pod usernames and passwords are separate.

Settings contains Appearance, Security, Backup, Updates and Logs. Accent, sidebar
mode and navigation/Dashboard/Settings order are saved on the server and included
in recovery. Alt+Up/Down reorders focused items; pointer dragging remains available.
Old browser presentation is imported once. Existing browser-only domain state is
retained for inspection, never silently deleted or merged into server data.

Access Key rotation requires the current key, rotates the current session's CSRF
credential and revokes other direct sessions. Logout revokes the server session.
Kernel URL is database-owned. A replacement Kernel service token is checked before
being written to separate restricted secret storage; APIs never return that token.
After changing this connection, run `sudo perimetr-install sync-kernel` on the
host before updating. This command changes only this service's Kernel fields.

Updates use host Updater protocol 2. The interface opens immediately, reports
Perimetr and Updater versions separately, saves a full ZIP and requires confirmed
local persistence before install. Request identity survives page reload; the UI
looks up the existing scoped job before retrying. Closing the dialog does not
cancel installation. Rollback requires the original saved ZIP.

## Recovery and logs

[Recovery procedure](docs/recovery.md) describes full replacement, external key
escrow, old-version migration and rollback. ZIP v3 encrypts every logical row and
includes all 25 authoritative tables: relationships, access policies, controller
identity, Pod configuration, deny-lists, settings/verifier and audit records.
Live leases, backup history, caches and deployment credentials are excluded.
No backup ZIP is retained on the server. Restore validates the entire archive
before replacement and revokes old sessions and launch authorizations.

Audit events are recursively redacted before storage and again during export.
Defaults: 10,000 events, 30 days, 64 MiB database audit budget; 16 KiB per serialized
event; 5 MiB per JSONL file and 64 MiB per log directory. The first reached limit
wins. Cursor pages default to 200 (maximum 1,000); the viewer keeps at most 1,000.
Diagnostic ZIPs stream bounded JSONL and select errors by explicit outcome.
They are not recovery archives.

Neptune is not an approved Perimetr consumer in the current central profile.
No Neptune installation, scheduling or secret mounts are required or exposed.
Unused Redis was also removed; no previous volume is deleted by this change.

## Run locally

Python 3.12 and Node 22+ (browser tests only) are used by CI. For a local SQLite
instance, create `.env` with `PERIMETR_ENV=development`, a nonempty
`PERIMETR_ACCESS_KEY`, `PERIMETR_PUBLIC_URL=http://localhost:18080`,
`PERIMETR_COOKIE_SECURE=false`, empty `KERNEL_URL`/`KERNEL_SERVICE_TOKEN`, and
`PERIMETR_DATABASE_URL=sqlite:///./.tmp/perimetr.sqlite`. Then:

```sh
python -m pip install -r requirements.txt
python -m uvicorn app.api_service.app:create_app --factory --host 127.0.0.1 --port 18080 --no-proxy-headers
```

For development Compose, use `PERIMETR_DATABASE_URL=postgresql://perimetr:perimetr@perimetr-db:5432/perimetr`
and `docker compose up -d --build`. Production uses the separately pinned image
and [deployment procedure](docs/deployment.md), not a source build.

## Integration and exposure

The operator shell and `/v1/*` operator data require an active direct session;
mutations additionally validate CSRF and same origin. Login, minimal reachability,
health and coarse robots policy are public/non-indexable. Protected assets inherit
authentication; all responses are private/no-store and noindex. A version-only
health response is intentional, not a concealed route. Device endpoints use
independent enrollment tokens, device signatures or Pod credentials; the internal
restore endpoint requires the scoped Updater credential.

Only the API's loopback port is published in production; PostgreSQL has no host
port. Host Nginx owns HTTPS/DNS/certificates. The application receives no Docker
socket or host root access. Trusted proxy addresses must match the actual ingress.

Register resolves typed Volt references for Perimetr/Pod repositories, public
Perimetr SNI/port and refresh interval. The public address never changes Uvicorn's
local listener. Preserve it during recovery so enrolled devices can reconnect.
Pod runtime downloads retain signature, checksum, version and identity pinning;
[Pod factory runtime](pod-runtime/README.md) and [Agent connector](agent-connector.md)
describe their separate contracts.

## Verification and release

```sh
python -m pytest -q
npm ci
npx playwright install chromium
npm run test:browser
python scripts/known-problems-gate.py --phase structure
python scripts/pre-push-gate.py --upstream-result success
```

Browser checks start an isolated local database and stop their own server. For
Windows Edge use `BROWSER_CHANNEL=msedge` and set `PYTHON` to the virtualenv Python.
`python scripts/container-smoke.py IMAGE` checks an isolated, read-only, nonroot
container. The [release procedure](RELEASING.md) separates these checks from
external deployment qualification. Unpinned dependency digests and unknown
catalog evidence fail closed; they are not treated as successful validation.
