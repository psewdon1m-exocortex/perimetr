# Perimetr releases

Perimetr releases use tags in the form `perimetr-vMAJOR.MINOR.PATCH`.

## Create a release

1. Update `PERIMETR_VERSION`, API migration notes and `CHANGELOG.md`.
2. Run `python -m alembic -c alembic.ini check` and `python -m pytest -q`
   from `perimetr/`.
3. When the Alembic head changed, complete the isolated production-copy and
   rollback exercise in `migrations/README.md`.
4. Set `.release/pod.version` and `.release/updater.version` to releases that
   already exist in their independent repositories. The selected Pod release
   supplies both the factory `pod.exe` and the trusted
   `pod-update-public-key.pem`.
5. Commit the release state and push `perimetr-vX.Y.Z` to the Perimetr
   repository.
6. `.github/workflows/release.yml` verifies those external artifacts before it
   publishes the OCI image, SBOM, provenance, Compose bundle, release manifest
   and checksums.

The Settings updater refreshes Kernel Register, reads
`repositories.perimetr.url`, and considers only `perimetr-v*` releases in that
repository. Perimetr CI never checks out Pod or Updater source code.

At runtime this factory pin is not the normal release selector. Perimetr reads
`repositories.pod.url` from Kernel Register, derives the `pod-current`
discovery URL, verifies the signed manifest, and keeps verified artifacts in a
persistent content-addressed cache. Each provisioning record stores the exact
Pod version and SHA-256 it received. Keep the ECDSA signing key stable; key
rotation requires publishing a Perimetr release carrying the new trusted
public key before moving `pod-current` to manifests signed by it.

For public dependency repositories, GitHub's repository token can download the
release assets. For private repositories, configure `RELEASE_READ_TOKEN` with
read-only access. Optional repository variables `POD_REPOSITORY` and
`UPDATER_REPOSITORY` override the documented defaults.

## Data safety and rollback

Perimetr creates a full ZIP, starts its browser download and hands the verified
server copy to the VPS-local updater before applying the release. PostgreSQL,
Redis and local backup volumes are preserved. Pulling happens before
replacement. A single Compose replica has a short connection interruption;
zero downtime requires two API replicas behind a reverse proxy and
backward-compatible migrations. Failed health checks automatically restore the
previous image digest and import the pre-update ZIP.
