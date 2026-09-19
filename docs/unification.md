# Perimetr unification work record

Authority: [Part 00](https://github.com/psewdon1m-exocortex/general/blob/8737b50f0aca4b84f4fa223272bdfb63ade05d33/PART_00_SYSTEM_UNIFICATION_SPECIFICATION.md)
and the applicable Parts listed below. Started 2026-09-19 against central
documentation commit `8737b50` and its current working tree. Perimetr baseline
is `5a4087d` plus the pre-existing uncommitted Register/Volt, Neptune, CI and
documentation changes. Those changes are part of the inspected input.

## Decision and scope

The operator requested that Perimetr be adapted to the updated central
documentation. Implement the central contracts directly, with an explicit
migration for retained state and no silent compatibility bypass. This is
authorization for local implementation and verification, not a claim that a
release is published or a production deployment has been qualified.

Perimetr remains the owner of Objects, Subjects, Properties/correlations, Pod
provisioning/identities, Agent Node assignments/jobs/approvals and controller
identity. Changes must preserve these functions and trust continuity.

## Applicability and baseline

| Part / sections | Applicability and evidence | Implementation / verification scope |
| --- | --- | --- |
| 00 §§1–6 | Applicable to all work | This record, divergence decisions, exposure inventory, checks and handoff |
| 01 §§1–6, 8–9, 10.1–10.8 | Applicable: browser operator shell, Settings, collections and correlation canvas in `app/core_ui.py` | Exact Access Key, theme/geometry, persisted presentation, accessible overlays/search/reorder, metrics, two-scroll-region Documentation, bounded graph, update UI |
| 01 terminal profile, §7 document/authoring nodes | N/A: Perimetr has neither a terminal UI nor an editable workflow/document-node engine; its correlation map is a derived projection | Preserve domain scope; do not add these unrelated products |
| 01 §10.9 | Conditional: consumed-component initialization only | Do not fabricate supported initialization for an unapproved service profile |
| 02 §§10–12 | Applicable: database audit, JSONL logs and ZIP export | Recursive redaction, event/count/age/byte limits, bounded pagination/tail/export, truthful outcomes |
| 02 §12.1.1 | N/A to routine inbound revision reads: Perimetr does not serve a Register revision API | Do not fabricate a revision recorder preference |
| 03 §§13–17 | Applicable: authoritative state and pre-update ZIP | Complete logical archive, encrypted recoverable fields, safe manifest/ZIP preflight, transaction and write barrier, no retained update ZIP, tested recovery key dependency |
| 04 §§18–23 | Applicable: Linux Docker deployment | Exact version bootstrap, embedded release trust, safe extraction, four-section environment, least privilege, health and host-owned Nginx |
| 05 §§24–31, 33–35 | Applicable: API head and local Updater | Qualified/validation tag separation, pinned dependencies, signed immutable release, protocol-2 saved-copy receipt, durable scoped jobs and recovery |
| 05 §32 | Controller artifact validation applicable; client self-replacement N/A to this repository | Preserve Pod signature/checksum/cache and pinning tests; Pod runtime owns its replacement algorithm |
| 06 §§35–41 | Applicable acceptance umbrella; exclusions inherit this matrix | Record actual commands and results; never equate mocks with deployment qualification |
| 07 §§42–52 | Applicable | Auth/CSRF/rotation, secret boundary, route/listener registry, CI permissions, publisher authentication, no-store/probe/bot policy |
| 08 discovery/public content | N/A: no intentionally indexable pages, publications, feeds, evidence API, public MCP or AI content generation | Do not introduce public discovery surfaces |
| 08 concealment/cache/client leakage and bot-policy sections | Applicable to protected operator data and private infrastructure | Anonymous negative tests, inherited asset authorization, coarse robots policy, no public topology |
| 09–10 shared-agent boundaries and Updater workflows | Applicable | Typed scoped requests, actual status and version, no root/Docker socket in API |
| 09–10 Neptune consumer profile | Not approved for Perimetr in current central profile | Existing local integration must not be an automatic installation prerequisite or claim supported enrollment; preserve data, require explicit profile extension before activation |
| 09–10 Gryphon / Wyvern | N/A: Perimetr is not a declared consumer and has no functional messaging/LLM binding | No dummy connection cards or broad agent-admin access |
| 11 coordinated Kernel/Volt/Saturn deployment | Topology-specific exercises N/A; shared trust, references and Updater compatibility apply where consumed | Use actual current Kernel and Updater wire contracts; do not alter sibling deployments |
| 12 all active IDs | Applicable release catalog classification | Pin full documentation revision and exact catalog digest; fail closed on missing/stale/unsupported evidence |

## Material divergences and convergence decisions

1. **Operator identity** — Parts 01 §4.1, 04 §20 and 07 §45.2.1 require one
   exact Access Key. The baseline requires username/password and imposes a
   password policy (`settings.py`, `security.py`, `schemas.py`, `services.py`).
   Converge on a salted verifier with an explicit legacy-verifier migration,
   exact-text input, CSRF, bounded sessions and authenticated rotation.
   Existing Pod login/password is a separate device contract and stays separate.
2. **Recovery** — Part 03 forbids plaintext connection credentials and retained
   update archives. The baseline decrypts Subject VLESS into ZIP, omits strict
   ZIP expansion validation and stores ZIPs in `.tmp/backups`. Converge on a
   versioned manifest, encrypted secret fields and an independently protected
   recovery key dependency, bounded preflight and transactional recovery.
   Legacy import must be explicit and validated; no silent weakening of exports.
3. **Updates** — Parts 03/05 require the operator's saved bytes and protocol-2
   receipt. Baseline downloads and immediately sends a separately retained host
   ZIP using the old helper contract. Implement the save gate and actual helper
   protocol, scoped request lookup, recovery upload and truthful live state.
4. **Settings / UI** — Part 01 requires server-persisted operator presentation,
   five canonical Settings sections, exact theme roles, accessible overlays and
   bounded Documentation. Baseline stores much presentation only in localStorage
   and embeds a legacy guide/UI. Migrate existing presentation once where possible;
   the server becomes authoritative, and settings join backup/restore.
5. **Release trust** — Parts 04/05/07/12 require signed exact-version bootstrap,
   build-once promotion and revision-bound release evidence. Baseline bootstrap
   selects latest and verifies only downloaded checksums; release rebuilds the
   image and has no known-problem evidence. Implement fail-closed packaging and
   gates, and distinguish local tests from protected CI/publication.
6. **Neptune** — Current Parts 09–11 exclude Perimetr, while uncommitted code
   introduces mandatory mounts/install control. Keep unsupported integration
   inactive and avoid silently expanding shared-agent authority. The former
   README rule assigning schedules only to Saturn is obsolete: approved
   consumers own their schedules. A future profile extension must implement
   that contract and its recovery tests before activation.

These choices apply the operator-requested central rules. They do not amend
central documentation or authorize production mutation. Rollback compatibility
and irreversible boundaries are documented with the implementation below.

## Implementation scope

1. Record baseline and applicable contracts; run the existing suite.
2. Identity, sessions, request/exposure policy and authoritative Settings.
3. Bounded audit/logs and safe complete backup/preflight/restore.
4. Actual Kernel/Volt and Updater wire contracts; saved-copy update/recovery.
5. Shared UI tokens, login, Dashboard, Settings, Documentation and accessibility.
6. Bootstrap, installer, release signatures, CI and known-problem gate.
7. Unit/integration/browser/container checks and operational handoff.

## Verification record

- Baseline: `.venv/Scripts/python.exe -m pytest -q`: **34 passed, 8 failed**.
  All eight failures traverse Pod cache `_atomic_json`: `os.fchmod` is absent
  on Windows and the exception leaves the temporary descriptor open. This is
  a baseline portability defect, not evidence of the unification changes.
- No production service, release, tag or remote state has been changed.
- Final local suite: **74 passed**, including an actual disposable PostgreSQL migration/recovery drill. Two warnings remain: upstream Starlette/AnyIO deprecation and the deliberately malformed duplicate-member ZIP fixture.
- Browser smoke: PASS in headless Edge at 1440×1000 and 390×844. Verified exact opaque Unicode/multiline pasted key, five Settings sections, modal focus/clearing/Escape, independent Documentation scrolling and full-text search, mobile navigation, 760×702 update view and centered 620px saved-copy warning. Updater discovery in this browser test is an explicit fixture, not a real host update.
- Docker image build and disposable smoke: PASS for reported version, UID 10001, read-only root, owned writable state and anonymous API rejection. The local image is not a publication candidate with qualified dependency inputs.
- Dependency integrity, shell/JavaScript syntax, workflow YAML parsing, Git whitespace and the seven-area working-tree pre-push gate: PASS.
- Part 12 structural gate: 97 catalog IDs inventoried; release qualification remains **false**. Missing qualification receipts are UNKNOWN, not PASS. Both signing and final promotion gates fail closed.
- The exact inspected central working-tree file hashes are in [unification-inputs.json](unification-inputs.json). The Part 12 gate separately pins its committed catalog bytes.

## Implemented contracts

Identity/settings code is split into operator_settings, kernel_connection,
request_policy and the explicit 0006 migration. Backup v3 covers every authoritative
model with encrypted streaming rows, bounded full preflight, a write barrier and
transactional replacement. Tests include wrong escrow and an insertion failure
after deletion to verify preservation of the previous state. The old plaintext
exporter/importer is removed; [recovery.md](recovery.md) explains the isolated
legacy-image migration and the data that old archives cannot reconstruct.

The static UI is split into local CSS/JavaScript, including locally licensed Space
Grotesk, explicit opaque-key paste handling and secret-field clearing. Presentation
is authoritative in the database. The derived graph displays at most 500 nodes
and 2,000 edges and reports truncation without truncating saved state or the score.
Hidden/reduced-motion views do not continue force animation.

Updater protocol 2 sends the same saved snapshot bytes, uses 15-minute scoped
receipts and durable request identities, looks up accepted work before retrying
and requires the original ZIP for rollback. Kernel connection changes are checked
before activation, with separate secret storage and an explicit root-owned host
synchronization step. Valid in-memory Register data survives a connection outage
without being reused across credentials.

Audit rows, paged views, diagnostic ZIPs and operational exception streams share
redaction. No raw log-file download bypasses it. Count, age and byte limits apply;
file-sink failure does not turn an already committed database operation into a
reported failure.

Bootstrap embeds public release trust and exact identity, verifies before trusting
artifact coordinates, and bounds extraction. Installer edits preserve literal
operator input. CI builds the candidate once, qualifies its digest at a protected
environment, signs with its derived public key, verifies anonymous staged assets,
and promotes only after the final catalog gate.

## External qualification boundary

The work is implemented and locally verified; it does **not** assert complete
production conformity. [RELEASING.md](../RELEASING.md) records the remaining release
prerequisites: independently verified published Updater protocol-2/Pod artifact
pins, protected signing-key provisioning and same-source/same-image qualification
proof for the full applicable catalog. Real shared-host update/rollback, external
DNS/TLS/firewall/concealment, boot/repair and actual device reconnection require
that isolated deployment qualification. Local mocks are not substituted for it.

No source commit, tag, push, remote release or production deployment was performed.
The operator's pre-existing edits were incorporated; central docs and sibling
projects were not modified.
