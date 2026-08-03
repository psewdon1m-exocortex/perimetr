# Changelog

## Unreleased

- Resolve the newest signed stable Pod release from Kernel Register
  `repositories.pod.url` before provisioning.
- Persist verified Pod executables by SHA-256, retain a factory and
  last-known-good fallback, and pin every provisioning record to one exact
  artifact through database revision `0004`.

## 1.1.0

- Perimetr core, Agent control plane, Pod lifecycle and correlation UI.
- Full ZIP backup and restore.
- Bounded Logger retention and operator-triggered release checks.
