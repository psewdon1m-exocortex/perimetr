# PERIMETR Core

This folder contains the active core application.

## Production installation

Prepare the latest stable release without starting it:

```bash
curl -fsSL https://raw.githubusercontent.com/psewdon1m-exocortex/perimetr/main/bootstrap.sh | sudo sh
```

Edit only the `OPERATOR INPUT` section in `/opt/exocortex/perimetr/.env`, then
run:

```bash
sudo perimetr-install
```

The bootstrap generates PostgreSQL, Pod and updater secrets, but never the
operator username or password. On a shared Kernel/Perimetr VPS it also copies
the local Kernel URL and service token when available. Nginx, certificates,
DNS and firewall policy remain separate Sindri operations.

## Run

```powershell
docker compose up -d --build perimetr-db perimetr-cache perimetr-api
```

Open:

```text
http://localhost:18080
```

`PERIMETR_LISTEN_PORT` is the private application port and is exposed only on
VPS loopback for local health and restore operations. One shared host-level
reverse proxy publishes the client-facing HTTP/HTTPS ports. PostgreSQL and Redis remain
private Compose services. Perimetr reads the client-facing Perimetr SNI/port,
the Kernel SNI/port, shared refresh interval and Perimetr/Pod repository
coordinates from Register. Pod lifecycle values, the factory Pod/Xray pins and
external Pod endpoints remain local `.env` settings and are injected into each
Pod by Perimetr. The Pod update-manifest URL is derived from
`repositories.pod.url`; it is not duplicated in `.env`.

Register never changes the running Uvicorn listener. To change the public
Perimetr port, publish the new `services.perimetr.port`, update the shared
host Nginx listener on the VPS, and reload Nginx. Agent Nodes do not read
Kernel: they keep using the stable public Perimetr SNI stored during
enrollment. When Perimetr moves, point that SNI to the new VPS and restore the
full backup.

Production Compose contains no reverse proxy. One shared host-level Nginx owns
TCP 80/443 for every head service on the VPS and routes the Perimetr SNI to
`127.0.0.1:PERIMETR_LISTEN_PORT`. Install, validate, start and reload that
Nginx through Sindri; keep certificate paths and public proxy ports out of
Perimetr `.env`. `services.perimetr.port` is the client-facing HTTPS port
(normally `443`), not the private listener port. The canonical proxy
configuration is documented in the infrastructure repository's
`NGINX_DEPLOYMENT.md`.

The release bundle also carries Perimetr's independent
`nginx.security.conf`. Include it inside the public HTTPS `server {}` block
(for example, `include /opt/exocortex/perimetr/nginx.security.conf;`) and run
`nginx -t` before reload. It does not enumerate UI elements, so adding tabs or
cards does not require a proxy policy update.

Agent communication is bidirectional but request-based. Agent opens periodic
outbound heartbeat requests to Perimetr. Perimetr opens a request to the
Agent's configured HTTPS endpoint only for enrollment, job dispatch,
approve/reject, cancel, and other explicit control operations. There is no
permanent socket between them.

The public Perimetr SNI is a stable Agent contract. If only the Perimetr IP/VPS
changes and the same SNI is repointed, communication resumes normally. If the
SNI itself changes, Perimetr can still call an Agent through the Agent URL
stored in its registry, and the Agent still accepts the unchanged controller
ID. However, that Agent continues sending heartbeats and asynchronous job
events to the old Perimetr URL stored during enrollment. The current protocol
has no authenticated endpoint-rebind operation, so a domain migration must
preserve the old SNI or explicitly re-enroll/reconfigure every Agent.

## Pod runtime selection

Published Perimetr images contain a tested factory `pod.exe` and the trusted
ECDSA P-256 Pod update public key under `/opt/perimetr/pod-runtime`. At startup,
every `PERIMETR_POD_REFRESH_SEC`, and immediately before provisioning,
Perimetr:

1. reads `repositories.pod.url` from the verified Kernel Register snapshot;
2. derives `<repository>/releases/download/pod-current/pod-update.json`;
3. validates the manifest schema, product, stable channel, compatibility,
   ECDSA signature, semantic version and anti-downgrade rules;
4. streams `pod.exe` through the configured size limit and verifies its exact
   SHA-256 and optional size;
5. atomically stores the executable in the persistent content-addressed cache
   `PERIMETR_POD_CACHE_DIR/artifacts/<sha256>/pod.exe`.

Creating a provisioning record pins both `bundle_version` and
`artifact_sha256`. Later downloads therefore use that exact verified artifact,
even if `pod-current` moves to a newer release in the meantime. Cached versions
referenced by pending records are retained. Remote provisioning records also
store the signed immutable artifact manifest in their metadata and system
backup. After a VPS restore, Perimetr can re-download that exact release and
verify it again if the local artifact cache is absent.

Kernel/GitHub failure does not block provisioning while a verified
last-known-good artifact exists. A fresh installation can fall back to the
factory runtime embedded in the image. Signature failure, checksum mismatch,
version reuse with a different checksum and downgrade attempts are logged and
cannot replace the last-known-good cache. If neither cache nor factory runtime
is valid, creation returns `503 pod_runtime_unavailable` instead of producing a
non-runnable archive.

Pod provisioning accepts an optional decoy password distinct from the primary
password. Perimetr authorizes the resulting access mode with a signed in-memory
grant: primary access receives the Subject configuration, while decoy access
receives no Subject identity or System Tabs and opens Google in a disposable
partition. The locked screen never exposes or pre-fills the Pod login.

VLESS changes on a Subject save automatically after typing stops and are
confirmed by a green top-right notice. Account sessions that need continuity
belong in System Tabs because Temporary Tabs intentionally clear browser state
when closed. OAuth providers can still challenge or reject embedded Electron
user agents independently of proxy routing, and proxy IP reputation or rapid
geography changes can cause additional verification.

The first operator login is read from `PERIMETR_DIRECT_USERNAME` and
`PERIMETR_ENTRY_PASSWORD`. Production refuses example/placeholder credentials,
passwords shorter than 12 characters, insecure cookies, non-HTTPS public
service URLs and a non-PostgreSQL database URL.

## Runtime

- `perimetr-api` - FastAPI app, UI and REST API.
- `perimetr-db` - PostgreSQL state store.
- `perimetr-cache` - Redis service for the current runtime boundary.

The installer runs as host root because it installs the updater and Compose
services. The application container itself runs as the
unprivileged fixed UID/GID `10001`, with a read-only root filesystem, dropped
capabilities and only its state volume writable.

## Main API

- `/v1/auth/direct`
- `/v1/status`
- `/v1/system/metrics`
- `/v1/topology`
- `/v1/objects`
- `/v1/subjects`
- `/v1/subjects/{subject_id}/pod-config`
- `/v1/subjects/{subject_id}/pods`
- `/v1/pods/enroll`
- `/v1/pods/{pod_id}/verify`
- `/v1/pods/{pod_id}/password`
- `/v1/pods/{pod_id}/heartbeat`
- `/subjects/{subject_id}/web`
- `/v1/backups`
- `/v1/backups/import`
- `/v1/correlation`

System backups include Agent Control Plane records: Agent Nodes, assignments, endpoint data, certificate history, heartbeat/state history, jobs, approvals, commands, denylist, and encrypted controller identity. After a full restore, the public Perimetr address must remain stable so enrolled nodes can resume heartbeat delivery. Restoring controller identity is required for command trust continuity.

Registering an Agent from the UI performs the remote `/v1/enroll` handshake
with the one-time token printed by `agent-node registration`, verifies the
reported certificate fingerprint and imports the capability catalog exposed by
the installed Sindri version. Creating a job dispatches it immediately to the
Agent `/v1/jobs` endpoint. Approval, rejection and cancellation are forwarded
to the matching Agent job; heartbeat and job events flow back to Perimetr.
Capability fields marked as secrets are forwarded for execution but stored in
Perimetr job history and audit only as `[redacted]`.

System backups also include Subject Pod configuration, provisioning records, Pod identities, per-Pod login and salted password hash, heartbeat state and every Pod denylist identifier. The archive contains the Subject VLESS connection so it can be re-encrypted under the restored node key; treat backup ZIP files as secrets.

Object and Subject images are stored with their entities, included in system backups, shown on Overview cards and reused as Pod branding assets.

The Correlation Map visualizes shared properties and their undirected relationships with core blocks, objects and subjects. Its authoritative state is persisted in PostgreSQL and included in system backups.
- `/v1/settings/password`
- `/v1/logs/audit`
- `/v1/logs/download`
- `/v1/audit`
- `/v1/agents`

## Tests

```powershell
docker compose exec -T perimetr-api python -m pytest tests -q
```

The operator welcome guide is available in the application under `Documentation` and in [`.docs/user-guide.md`](.docs/user-guide.md).

Logger retention is bounded by `PERIMETR_AUDIT_MAX_ENTRIES`, `PERIMETR_AUDIT_RETENTION_DAYS`, `PERIMETR_LOG_MAX_FILE_BYTES`, and `PERIMETR_LOGS_MAX_TOTAL_BYTES`.

Settings also contains an operator-triggered Updater check. It refreshes the
last-known-good Kernel Register, resolves `repositories.perimetr.url`, and
selects only `perimetr-v*` GitHub releases. Release application remains outside
the application container so Perimetr never receives the Docker socket.

See [RELEASING.md](RELEASING.md) for packaging, publication, data safety and
rollback.
