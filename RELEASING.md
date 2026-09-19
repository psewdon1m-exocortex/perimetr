# Release procedure

Version authority is `VERSION` (currently **2.0.0**, unreleased). Only the exact
stable tag `perimetr-vX.Y.Z`, matching that file, can publish. `v*` tags run ordinary
validation. Zero, leading-zero and prerelease versions do not qualify.

## Outstanding external prerequisites

`.release/dependencies.json` deliberately has unresolved SHA-256 pins. The required
Updater protocol 2 is implemented by the inspected Updater 0.5.0 source, which was
still marked unreleased. A published compatible bundle and independently verified
archive digest are required, along with Pod 0.1.3 executable and public-key digests.
The pipeline fails before staging unpinned inputs. Never fill these from arbitrary
local binaries or accept a checksum solely because it accompanied a download.

Configure the protected GitHub environment `perimetr-release` with required
reviewers and `PERIMETR_RELEASE_SIGNING_KEY`, an existing RSA private key of at
least 3072 bits. The workflow derives public trust; it never generates a new
production signing key. Private keys do not enter the image, bundle or repository.
Changing existing bootstrap trust requires a separately planned trust transition.

## Candidate, qualification, publication

1. CI executes native, browser and contract checks with actions pinned to commit
   SHAs. The candidate job fetches reviewed immutable dependencies, builds once,
   pushes only a commit-scoped candidate and tests that exact image digest under
   the production process security restrictions.
2. While the release job waits at its protected environment, run deployment and
   recovery qualification against **that candidate digest and source revision**.
   Include every applicable pre-signing ID from the pinned Part 12 catalog;
   unit tests or mocked discovery alone cannot qualify external deployment.
3. Preserve a successful same-repository GitHub Actions run artifact named
   `perimetr-qualification-COMMIT_SHA`. Set environment variable
   `RELEASE_QUALIFICATION_RUN_ID` to that run. The artifact contains
   `qualification.json` with `revision`, `version`, `image_digest`,
   `catalog_sha256` and `checks`. Each check contains its exact `id`, `status:
   "PASS"`, a concrete `observation` and GitHub Actions evidence URLs. Every
   pre-signing ID not explicitly N/A is required exactly once. Metadata is
   re-fetched from GitHub; stale/failed/mismatched evidence fails closed.
4. After approval, release verifies this evidence and the pre-signing gate,
   packages the tested digest, signs `perimetr-release.json`, and generates the
   version-specific bootstrap with the derived public key embedded. Public-key
   export and signing use the same protected key.
5. Stage a prerelease. Anonymous verification compares the exact assets, embedded
   trust, signature, bundle checksum and tag commit. The final Part 12 gate must
   pass before the same image digest receives the version tag and the release is
   promoted. A failed staged release remains unqualified; investigate/reconcile
   it explicitly rather than overwriting an accepted release.

The required assets are `bootstrap.sh`, `perimetr-release.json`, its `.sig.json`
envelope, `perimetr.pem`, the versioned compose bundle, and the final
`known-problems-report.json` added after anonymous verification. GitHub provenance
attestations accompany the build. Older Updater 0.1.x Sigstore discovery is not a
supported route to this breaking protocol migration; upgrade the host helper
through its qualified transition procedure first.

The catalog is embedded at full documentation commit
`8737b50f0aca4b84f4fa223272bdfb63ade05d33`, digest
`a66eb1e6942874e506975a7708cec6a0bf6f1fe8969a04c341bcd271d2f1cacd`.
`known-problems-gate.py --phase structure` validates the inventory locally and
reports unknown evidence without asserting qualification. The pre-signing/final
phases fail on missing proof, dirty tracked source or tag mismatch. Receipts bind
source bytes (including untracked source), revision, catalog, run and log digest.
A structural pre-push PASS is not a release qualification PASS.

See [deployment](docs/deployment.md), [recovery](docs/recovery.md) and
[the applicability/verification record](docs/unification.md) for activation and
rollback boundaries. No release or production change is implied by local tests.
