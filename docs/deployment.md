# Deployment

Use only a qualified `perimetr-vX.Y.Z` release. Version 2.0.0 is currently a local
candidate: see [release prerequisites](../RELEASING.md). The source bootstrap is a
template; only the generated release asset embeds public trust and exact version.

On a prepared Debian/Ubuntu host with Docker/Compose:

```sh
curl -fsSL https://github.com/psewdon1m-exocortex/perimetr/releases/download/perimetr-vX.Y.Z/bootstrap.sh -o /tmp/perimetr-bootstrap.sh
sudo sh /tmp/perimetr-bootstrap.sh
sudoedit /opt/exocortex/perimetr/.env
sudo perimetr-install
sudo perimetr-install status
```

The immutable bootstrap verifies RSA-PSS-SHA256 (RSA ≥3072) before trusting
manifest URLs, verifies the bundle digest, validates tar paths/types/budgets and
prepares only this service. A conflicting installed trust key or an existing
installation fails closed. It never replaces another service's environment or
installs Nginx. Machine secrets are generated once; Access Key is operator input.

`.env` has four sections: operator input, generated secrets, release identity,
operational defaults. It must be root-owned mode 0600. Quote the initial key with
single quotes; whitespace, literal dollars and multiline content are preserved
by the installer and converted to a verifier before Compose interpolation. Never
source `.env` as a shell script or paste it into diagnostics. The database verifier
is authoritative after initialization; do not use reseeding as key rotation.

Configure `KERNEL_URL`, its dedicated service credential and the public Perimetr
origin. Register supplies typed Volt references for repositories and public
Perimetr SNI/port. The dedicated listener remains 127.0.0.1:18080 on the host.
Escrow the generated Pod recovery secret independently before creating backups.

Production Compose uses UID/GID 10001, dropped capabilities, read-only application
root, bounded tmpfs, private state/database volumes and bounded Docker logs. A
one-shot volume initializer only changes the owned state volume. PostgreSQL is
private; its read-only volume mount lets Disk report the actual data filesystem's
available capacity. The shared Updater Unix socket uses its assigned group; there
is no Docker socket in the API. Run a single API worker.

After local health reports the exact installed version, configure host Nginx with
TLS and the stable public origin. Include `nginx.security.conf`, run `nginx -t`,
then reload. Configure canonical Host validation and real proxy addresses; Uvicorn
does not trust arbitrary forwarded headers. DNS, certificate SANs, firewall and
other heads' listeners remain host-owned. Do not restrict the operator UI to an
invented CIDR/VPN allow-list; Access Key and sessions control its data.

For a saved Kernel URL/token change, use `sudo perimetr-install sync-kernel`.
The root helper reads only this running head's validated connection and atomically
updates only its two Kernel environment fields. It never reads a sibling `.env`.
The application gates new updates until synchronization succeeds.

## Activation evidence

Before production activation, record externally observed DNS/TLS/HTTPS, canonical
host rejection, login/logout and rotation, anonymous list/detail/image/JS denial,
no-store/robots headers, blocked probes and no publicly reachable database/helper.
Verify host reboot, writable state/volume ownership, bounded storage, the real
Kernel/Volt credential scope, the installed Updater protocol and a saved-copy
update/rollback. Exercise PostgreSQL recovery and device reconnection with escrow.
These host-specific observations are not implied by unit or browser mocks.

Perimetr has no indexable publication, public content search/feed/MCP or workflow
authoring engine. Its login/minimal health are deliberately public/non-indexable;
operator topology and child assets are private. Device enrollment and signed
heartbeat endpoints have independent scoped authentication, not browser CSRF.
