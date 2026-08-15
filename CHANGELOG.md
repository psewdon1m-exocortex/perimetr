# Changelog

## Unreleased

## 1.2.3 - 2026-08-15

- Replace the browser confirmation used for Perimetr updates with the standard
  in-app confirmation modal and explicit backup-first install action.

## 1.2.2 - 2026-08-15

- Restore detached Sigstore release bundles for compatibility with production
  hosts that still run Updater 0.1.x.
- Embed the signed Updater 0.2.1 transition release in new installations.

## 1.2.1 - 2026-08-15

- Replace the browser Project prompt with the Perimetr modal workflow.
- Make Object-to-Subject conversion idempotent and prevent duplicate UI requests.
- Automatically save Subject VLESS changes with success feedback.
- Add optional server-authorized Pod decoy passwords and clean Google-only sessions.
- Pin the factory Pod runtime to version 0.1.3.

## 1.2.0

- Add the one-command Perimetr bootstrap and `perimetr-install` production command.
- Generate database, Pod and updater secrets without generating operator credentials.
- Use checksummed release dependencies without Cosign/Sigstore bundles.

## 1.1.3

- Make the Redis `/data` tmpfs writable through a portable sticky mode instead
  of Docker Engine-specific tmpfs `uid` and `gid` mount options.

## 1.1.2

- Run the pinned production Redis cache as its non-root image user and assign
  the ephemeral `/data` tmpfs to that user, preserving `cap_drop: ALL` without
  blocking the Redis entrypoint.
- Smoke-test the hardened production Redis service in the release workflow.

## 1.1.1

- Resolve the newest signed stable Pod release from Kernel Register
  `repositories.pod.url` before provisioning.
- Persist verified Pod executables by SHA-256, retain a factory and
  last-known-good fallback, and pin every provisioning record to one exact
  artifact through database revision `0004`.
- Validate the published OCI digest before packaging a release.

## 1.1.0

- Perimetr core, Agent control plane, Pod lifecycle and correlation UI.
- Full ZIP backup and restore.
- Bounded Logger retention and operator-triggered release checks.
