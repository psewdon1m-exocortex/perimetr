# Embedded Pod runtime

Production Perimetr images contain the release-built Windows portable runtime
at `pod.exe` and its trusted long-lived ECDSA P-256 update public key at
`pod-update-public-key.pem` in this directory. Perimetr uses these as its
cold-start factory fallback. The release workflow downloads both from one
immutable Pod release, verifies their Sigstore identities, and adds them to the
Perimetr image build context.

The source checkout intentionally does not store the generated executable.
For local development, download the pinned `pod.exe` and public key release
assets from the `exocortex-pod` repository into this directory. Development
Compose mounts this directory at `/opt/perimetr/pod-runtime`; it never reads a
sibling source tree. Runtime releases downloaded through
`repositories.pod.url` are stored separately in the persistent
`PERIMETR_POD_CACHE_DIR` and never overwrite these factory files.
