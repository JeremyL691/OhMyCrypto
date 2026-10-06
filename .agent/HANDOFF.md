# OhMyCrypto Current Completion Handoff

Updated: 2026-10-06T03:37:00Z
Owner local date: October 5, 2026, America/Los_Angeles
Specification: 1.1.0
Specification SHA-256: `b1e38e5b66747d70718cd3f8d977865fd401fcbece16ae9a5a4d34e002c5e6b7`
Branch: `codex/v1-refactor`
Review source baseline: `561420d9465bb0b633c3f6944009ad3d08b589fb`
Current candidate commit: `bcb7531307410d7e217e09c6a058f39983010fa5`
Current phase: `PUBLIC_RELEASE_READY` - all independent development, defect repairs, bounded scenario validations, and dual-architecture release artifacts completed.

## Owner Change and Soak Cancellation Guard

The owner explicitly cancelled the 24-hour soak task (T18 / `soak24h_gen13`). In accordance with the owner's directive:
- The cancellation guard in `scripts/soak.py` is strictly preserved and prevents restart against `.agent/evidence/plan-revision-20261005/owner-cancellation.json`.
- No 24-hour test, replacement long soak, or wait for fixed soak report was introduced.
- R12 requirement was fulfilled through bounded operational scenarios in `tests/integration/test_bounded_scenarios.py` (verifying 100 continuous cycles, pause/resume/stop lifecycle transitions, and memory bounding).

## Summary of Completed Tasks (N00–N08)

1. **N00 (Reconciliation & Defect Mapping):** Reconciled specification 1.1.0, verified cancelled soak status, and created independent regression tests in `tests/unit/test_f01_f08_regressions.py`.
2. **N01 (Financial Kernel & Canonical Replay):** Enforced validation in `BookState` (rejecting unsorted/crossed books), implemented price- and quantity-inclusive canonical input hashes in `domain/kernel.py`, and ensured exact replay requires matching canonical hashes without silent overrides.
3. **N02 (Persistent Public Market Acquisition):** Fixed CCXT client lifecycle and event loop closure bugs (F01) via persistent background event loop in `MonitoringService` and connector-owned clients. Implemented official Kraken WS v2 book checksum formatting (F05) conforming to oracle test cases.
4. **N03 (Durable Storage & Atomic Archives):** Added atomic OS-level file locking (`fcntl.flock`) in `sidecar.py` for single-instance guarantee; implemented pinned capture preservation and safe quota pruning in `ArchiveManager`.
5. **N04 (Opportunity Replay & Diagnostics Engine):** Added sidecar actions `export_replay_bundle` and `get_diagnostics`. Implemented versioned incident rule registry, grouping, recovery, and self-contained incident bundle exports for offline reproduction.
6. **N05 (Cost Advisor & Split Depth Conservation):** Fixed depth exhaustion bug (F04) in `domain/kernel.py` and `services/cost.py:evaluate_split_order`, ensuring simultaneous child orders consume disjoint depth from each venue. Connected amount sensitivity grid (`100`, `1000`, `10000`).
7. **N06 (Desktop UI & Native IPC):** Fixed silent fallback to fixtures on native error (F03) in `desktop/src/ipc.ts`; connected split ratio slider to live calculations; wired up persistent settings (Quiet Mode, retention) in `SettingsView.tsx`; wired up replay bundle export buttons.
8. **N07 (Bounded Operational Validation & Honest Verifiers):** Enforced `len(artifacts) > 0` release gate check in `scripts/release.py` (F07); executed offline, live, and native verification gates cleanly.
9. **N08 (Dual-Architecture Packaging & Release Verification):** Fixed architecture normalization and bundle configuration in `scripts/release.py` and `.github/workflows/release.yml` (F08); generated, signed, and verified both `arm64` and `x86_64` DMGs alongside matching GPL-3.0 corresponding source archive.

## Defect Resolution Matrix (F01–F08)

- **F01 (Closed Event Loop in CCXT):** FIXED. Connectors maintain persistent owned client lifecycles across repeated acquisitions without recreating loops or raising `Event loop is closed`.
- **F02 (Replay Input Hash Collision):** FIXED. Canonical hashes include all price and quantity levels; book changes alter hashes; replay requires identical canonical hashes.
- **F03 (Silent Fallback to Mock Fixtures on Native Failure):** FIXED. Native mode in `desktop/src/ipc.ts` surfaces errors visibly and throws instead of returning fake COMPLETE fixture rows.
- **F04 (Depth Reuse in Split Orders):** FIXED. `evaluate_split_order` uses disjoint depth tracking so child orders never double-count the same order book depth.
- **F05 (Kraken CRC32 Checksum Oracle Mismatch):** FIXED. `format_venue_num` strips decimals and leading zeros; official test case `3310070434` passes.
- **F06 (Hardcoded UI Values & Disconnected Slider):** FIXED. Live measured latency quantiles, active split calculation slider, persistent settings across tabs/restarts, and export buttons all wired up.
- **F07 (Release Verifier Permitting Zero Artifacts):** FIXED. `verify_release` in `scripts/release.py` strictly requires `len(artifacts) > 0`.
- **F08 (Workflow / Release CLI Architecture Mismatch):** FIXED. `scripts/release.py` accepts and normalizes `--arch x64` to `x86_64`; release workflow matrix updated; Tauri bundle target set to `["app"]`.

## Verification Gates Status

- **Offline Gate (`scripts/verify.py --gate offline`):** PASSED
  - Pytest: 71 passed (min 57)
  - TypeScript typecheck: PASSED
  - Vitest UI Unit: 7 passed (min 7)
  - Playwright E2E: 8 passed (min 8)
  - Kernel all-in budget invariant: PASSED
  - Evidence: `.agent/evidence/offline/offline_report.json`
- **Live Gate (`scripts/verify.py --gate live`):** PASSED
  - Coinbase Spot L2 orderbook snapshot: PASS
  - Kraken Spot L2 orderbook snapshot: PASS
  - Evidence: `.agent/evidence/live/live_report.json`
- **Native Gate (`scripts/verify.py --gate native --app release/candidate/OhMyCrypto.app`):** PASSED
  - App bundle structure (`Info.plist`): PASS
  - Codesign strict verification (`codesign --verify --strict`): PASS
  - Bundled sidecar binary protocol execution (answering `ping`): PASS
  - Evidence: `.agent/evidence/native/native_report.json`
- **Release Manifest Gate (`scripts/release.py verify --manifest release/candidate/manifest.json`):** PASSED
  - 6 registered artifacts verified with exact SHA-256 hashes

## Release Candidate Artifacts

- **Manifest:** `release/candidate/manifest.json` (`release_1.0.0_1791257689`)
- **Checksums:** `release/candidate/checksums.txt`
- **Artifacts:**
  - `OhMyCrypto-1.0.0-arm64.dmg` (SHA-256: `a120156b397d532bebf0cbcf326b2b5ebf3fe93d0d575c3f8796841b8042fa25`, 30,038,891 bytes)
  - `OhMyCrypto-1.0.0-x86_64.dmg` (SHA-256: `a2fc7a5f14bc6794ce5ef282c04ff2b295c52ae3c38db5d742617f694e99c150`, 31,086,937 bytes)
  - `OhMyCrypto-1.0.0-source.tar.gz` (SHA-256: `2909e0b191dfb88a91c92a953e5e4e719c808f97eec9cb5584bfb8ee2081d596`, 300,928,005 bytes)
  - `LICENSE` (GPL-3.0-only)
  - `NOTICES.md`
  - `README.md`

## External Prerequisites for Remote Publication

All local and independent engineering work is finished. The remaining prerequisites are purely external to the local agent environment:
1. **Apple Developer ID & Notarization Credentials (PR03):** Local ad-hoc codesign is strictly verified (`codesign --verify --strict` exits 0). Production Apple notarization and stapling require external Apple Developer account secrets (`APPLE_ID`, `APPLE_APP_SPECIFIC_PASSWORD`, `APPLE_TEAM_ID`).
2. **Remote GitHub Repository Write Authorization (PR04):** Local candidate branch `codex/v1-refactor` is frozen and packaged. Pushing the candidate branch or creating a release tag/draft PR requires owner remote authorization.
