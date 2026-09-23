# Interface reference implementation

The 2026-09-20 UI revision applies Part 01 and its normative PNG references
to Perimetr's existing screens. The inspected Part 01 SHA-256 is
`29abfba38d27e4ae63e7c538e405300870d659d465c26b6cb8121a6d85e30800`.
It supersedes the earlier compact sidebar, oversized metric cards and partial
Settings styling. The central specification remains authoritative.

## Reference mapping

| Reference | Perimetr implementation |
| --- | --- |
| Left Menu / shared shell | 250px sidebar, operator-provided transparent service icon, 42px service name, 42px navigation rows, 123px header, responsive 80px page title. Documentation and Logout are unnumbered text actions. |
| Dashboard / universal cards | CPU, RAM, Disk and service Uptime occupy 790×166px cards at 1920px. A 1610px service correlation card follows. Ordinals, four-dot handles, 9px progress tracks and 30px gaps use the measured ledger. |
| Settings main | 55px title bands, 401px baseline Appearance section, 40px controls, 326px action/hex fields, Kernel URL/status pair and full-width token action. Content grows for errors or narrow screens. |
| Backup / Updates / Logs | Existing recovery actions keep their validation. Perimetr and Updater checks are separate; no unapproved service agent is added. Logs use bounded TYPE/BODY/TIME rows, archive download and older-page loading. |
| Documentation | 220px navigation, 30px gap, 1120px article maximum, two bounded scroll owners, full-text search and synchronized current-section state. |
| Login | 560×268px panel, exact opaque key input, 100px service-icon box and independent reachability indicator. |
| Update dialogs | 760×702px main overlay, 710×203px discovery panel, 620px warning, 55px title bands, measured progress and a separate job panel. No release is installed by discovery. |

Product name, metric values and prose remain real Perimetr content. The supplied
blue doughnut is a placeholder; both login and sidebar use Perimetr's existing
concentric perimeter mark. No example credentials, services, metrics or release
versions are copied into runtime data.

## Interaction and ownership

- Only the accent is editable. Preview validates contrast; Apply commits it;
  leaving the view restores the saved accent. Sidebar and layout remain server-owned.
- Dashboard and Settings drag only from their handles and reflow a live
  placeholder. Alt+Up/Down exposes the same order changes. Failed persistence
  restores the confirmed order, including an initial default order.
- Kernel URL commits on Enter/blur. A failed validation preserves the prior URL
  and exposes the failure beside the control. Token and Access Key fields open empty.
- Collection search, count and Add commands share a sticky bar. Clear and Escape
  restore the current collection. Filtering disables ambiguous row reordering.
- Only the top overlay owns focus. Backdrop clicks preserve entered values;
  explicit dismissal clears secret fields. Closing update progress leaves its
  durable host operation alive.
- Documentation resets its article scroll on search and both scroll regions
  on reopening. The final visible section becomes current at the end of the article.
- Correlation controls include a textual relationship list, bounded to 500
  entries and labeled with the complete count, alongside the existing bounded graph.

## Verification

`npm run test:browser` starts an isolated development database. It runs the
reference assertions in `scripts/interface-contracts.cjs`, the retained domain
flows in `scripts/agent-removal-contracts.cjs`, and login/modal/recovery-save checks.
The removal checks cover Overview blocks, Object-to-Subject conversion, rename,
Pod settings, absence of retired screens and absence of agent API polling.
Screenshots and measured coordinates are written
to the ignored `.tmp/browser-<timestamp>/` directory and retained by CI.

The fixtures check 1920×1080 and 1919×1034 composition, intermediate widths,
360px mobile width, a short 640×360 viewport, hidden/fixed sidebar, reduced motion,
keyboard and pointer ordering, search, focus, protected backdrop dismissal,
separate component discovery and progress. Metrics and available/running/completed
update states are explicit browser fixtures. They do not certify a real host
update, installed dependency release or production deployment.

After removing server Agent Node management, the complete local backend suite
passed 68 tests, including populated SQLite/PostgreSQL migration and recovery.
The live Docker stand
uses the same source UI and its existing PostgreSQL volume and Access Key.
