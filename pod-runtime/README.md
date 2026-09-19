# Embedded Pod runtime

This service-specific note specializes [Part 09 — service agents deployment
and lifecycle](https://github.com/psewdon1m-exocortex/general/blob/8737b50f0aca4b84f4fa223272bdfb63ade05d33/PART_09_SERVICE_AGENTS_DEPLOYMENT_AND_LIFECYCLE.md).
Part 09 remains authoritative.

Production Perimetr images contain the release-built Windows portable runtime
at `pod.exe` and its trusted long-lived ECDSA P-256 update public key at
`pod-update-public-key.pem` in this directory. Perimetr uses these as its
cold-start factory fallback. The release workflow downloads both from one
immutable Pod release, verifies the executable checksum, and adds them to the
Perimetr image build context.

The source checkout intentionally does not store the generated executable.
For local development, download the pinned `pod.exe` and public-key release
assets from the [Pod repository](https://github.com/psewdon1m-exocortex/pod)
into this directory. Development
Compose mounts this directory at `/opt/perimetr/pod-runtime`; it never reads a
sibling source tree. Runtime releases downloaded through
`repositories.pod.url` are stored separately in the persistent
`PERIMETR_POD_CACHE_DIR` and never overwrite these factory files.
