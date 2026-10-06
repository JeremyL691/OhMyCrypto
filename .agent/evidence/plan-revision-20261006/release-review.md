# OhMyCrypto release readiness review

Review date: October 6, 2026 (America/Los_Angeles).
Subject: clean local branch `codex/v1-refactor`, HEAD `35361de`, implementation candidate `11db10c`, specification 1.1.0.
Decision: **Do not publish as a completed 1.0.0 product.** Several promised production workflows fail or are absent. Apple credentials are not the only remaining blocker.

The review did not modify repository source, tests, documentation, Git state, or historical acceptance reports. Temporary databases, builds, browser tests and probes were isolated outside the repository. No push, tag, PR, publication, signing change or long soak was performed. The revised specification's cancellation of the 24-hour and fixed Intel-duration gates was respected.

## What is working

- The domain/adapters/services/storage/interfaces separation is useful and does not need a wholesale rewrite.
- Decimal arithmetic, explicit fill results, shared cost kernels, stable route keys, an OS-backed sidecar lock, a persistent engine I/O loop, SQLite WAL and capture archives are substantial foundations.
- TypeScript checking and a fresh frontend production build passed.
- Existing suites reran successfully: **71 Python tests, 7 UI unit tests, 8 browser fixture E2E tests**. Python local-server and app-data sandbox restrictions were resolved by using temporary data and an approved local-server test run; the initial restricted-environment errors were not counted as product defects.
- The actual production `MonitoringService._run_cycle` completed **10 public REST acquisition cycles for each of Coinbase and Kraken**, producing 10 stored decisions. This directly verifies recurring acquisition on the current host, not long-term reliability or live WebSocket recovery.
- All six existing manifest artifact hashes matched their files. Selected core files in the source archive matched the current candidate. The rebuilt frontend asset names matched those in the candidate app.
- The packaged sidecar runs without developer Python and exits on stdin EOF. Its real cost request nevertheless fails, as detailed below.
- Lucide, light/dark themes, semantic landmarks and compact styling are present. Both themes and 320/768/1024/1440 widths were exercised; a narrow-width defect was found.
- Read-only remote inspection showed `main` and remote HEAD at `1058083`; the current candidate branch was not returned by the remote query. No exact-candidate remote CI result was established.

## Required repairs

### A01 - P1: The shipped cost-comparison IPC response cannot be serialized

Locations: [cost.py:224](/Users/jeremyliu/Desktop/Projects/OhMyCrypto/src/ohmycrypto/services/cost.py:224), [sidecar.py:49](/Users/jeremyliu/Desktop/Projects/OhMyCrypto/src/ohmycrypto/interfaces/sidecar.py:49), [sidecar.py:361](/Users/jeremyliu/Desktop/Projects/OhMyCrypto/src/ohmycrypto/interfaces/sidecar.py:361).

`evaluate_split_order` puts `FillResult` dataclass objects into `child_results`. `DecimalJSONEncoder` only handles Decimal and cannot serialize these objects. When both venues supply books, the entire successful calculation becomes an IPC error. Both a deterministic production-action probe and the sidecar inside `release/candidate/OhMyCrypto.app` using real public books returned:

```json
{"status":"error","error":"Object of type FillResult is not JSON serializable"}
```

Repair: create an explicit, validated JSON response DTO for all nested fills and scenarios; preserve decimal strings. Test the complete serialized request/response across the packaged boundary with two usable venues. Domain-only cost tests do not cover this failure.

### A02 - P1: Stored real events lose their evidence at the UI boundary and opening replay crashes

Locations: [repository.py:160](/Users/jeremyliu/Desktop/Projects/OhMyCrypto/src/ohmycrypto/storage/repository.py:160), [sidecar.py:403](/Users/jeremyliu/Desktop/Projects/OhMyCrypto/src/ohmycrypto/interfaces/sidecar.py:403), [ReplayModal.tsx:46](/Users/jeremyliu/Desktop/Projects/OhMyCrypto/desktop/src/components/ReplayModal.tsx:46).

Storage writes flat fields such as `buy_spent`, `buy_fee`, and `acquired_base`, while `_event_to_item` expects nested `buy_fill` and `sell_fill`. Hashes are SQL row columns, but the mapper reads them from `opportunity_json`. All 10 real stored decisions exposed `input_hash:null`, `config_hash:null`, `buy_fill:{}`, and `sell_fill:{}`.

Feeding the exact production response through the freshly built frontend's native IPC path in a Chromium test, then clicking Inspect / Replay, reproduced `Cannot read properties of null (reading 'slice')`; the page body became empty. This is a browser contract reproduction using real recorded data, not an installed Tauri-shell journey.

Repair: persist complete fill ledgers, map row hashes correctly, validate the response at the boundary and handle malformed/legacy records visibly. Add a storage -> IPC -> rendered detail/replay regression with actual repository output.

### A03 - P1: Replay substitutes original fees and can falsely certify modified evidence

Locations: [opportunity.py:115](/Users/jeremyliu/Desktop/Projects/OhMyCrypto/src/ohmycrypto/services/opportunity.py:115), [opportunity.py:254](/Users/jeremyliu/Desktop/Projects/OhMyCrypto/src/ohmycrypto/services/opportunity.py:254), [opportunity.py:334](/Users/jeremyliu/Desktop/Projects/OhMyCrypto/src/ohmycrypto/services/opportunity.py:334).

Capture/export does not preserve the original complete fee profiles, thresholds, instrument limits or timing/integrity configuration. No-override replay reconstructs generic instruments and uses 0.25% on both legs. Monitoring defaults are 0.60% and 0.40%.

An independent fixture using the monitor's fee rates produced original profit `-0.00397614312` and replay profit `+0.496259349425` without an override. A real stored decision changed from about `-9.904762` USDT to `-4.951990` USDT on replay. Original replay is therefore not reproducible for the actual monitor configuration.

Separately, changing exported `acquired_base` to `999999`, `buy_fee` to `12345`, and the manifest's config/result hashes still yielded `is_exact_match:true` for a default-fee event. Exactness compares only input hash, profit and eligibility, ignoring the full canonical result and configuration. These are controlled integrity counterexamples, not observed hostile input.

Repair: persist immutable complete inputs and original configuration; restore them for original replay; validate input, config, version and canonical result hashes and all ledgers. Keep overrides in a separate comparison result. Missing or sanitized inputs must be incomplete/unknown, never silently synthesized as exact.

### A04 - P1: Cost grid, split summary and replay response shapes disagree with the frontend

Locations: [cost.py:143](/Users/jeremyliu/Desktop/Projects/OhMyCrypto/src/ohmycrypto/services/cost.py:143), [cost.py:256](/Users/jeremyliu/Desktop/Projects/OhMyCrypto/src/ohmycrypto/services/cost.py:256), [CostComparisonView.tsx:140](/Users/jeremyliu/Desktop/Projects/OhMyCrypto/desktop/src/components/CostComparisonView.tsx:140), [CostComparisonView.tsx:211](/Users/jeremyliu/Desktop/Projects/OhMyCrypto/desktop/src/components/CostComparisonView.tsx:211), [sidecar.py:392](/Users/jeremyliu/Desktop/Projects/OhMyCrypto/src/ohmycrypto/interfaces/sidecar.py:392).

Production grid keys are `100`, `1000`, `10000`; the UI reads `100.00`, `1000.00`, `10000.00`, so every computed grid result is missed. Production split returns `total_quote` and `child_results`, whereas UI reads `total_spent_or_received`, `effective_avg_price` and `children`. Production replay wraps results under `replay`; ReplayModal reads top-level profits/exactness. Browser fixtures use the UI's desired shape and hide these disagreements.

Repair: define one typed/versioned schema shared by Python responses and TypeScript consumers, with contract tests using production outputs. Derive symbols and currencies from the result; ETH amounts currently display BTC in multiple views. Retain stale result provenance or clear all dependent results on error/config change; currently grid/split state can remain after a comparison error.

### A05 - P1: Invalid or incoherent market evidence can still appear usable

Locations: [monitor.py:136](/Users/jeremyliu/Desktop/Projects/OhMyCrypto/src/ohmycrypto/services/monitor.py:136), [monitor.py:322](/Users/jeremyliu/Desktop/Projects/OhMyCrypto/src/ohmycrypto/services/monitor.py:322), [kernel.py:434](/Users/jeremyliu/Desktop/Projects/OhMyCrypto/src/ohmycrypto/domain/kernel.py:434), [kraken.py:224](/Users/jeremyliu/Desktop/Projects/OhMyCrypto/src/ohmycrypto/adapters/kraken.py:224), [kraken.py:276](/Users/jeremyliu/Desktop/Projects/OhMyCrypto/src/ohmycrypto/adapters/kraken.py:276).

`configure` accepts `NaN`, `Infinity`, `-1` and `0` budgets because constructing Decimal is not finite/positive validation. Freshness, acquisition alignment and quality are not enforced by opportunity eligibility or represented in the relevant input identity. A controlled 10-minute-old `quality_status='stale'` book still produced `is_eligible:true` and the same input hash as its clean counterpart.

Kraken defaults to `strict_checksum=False`. A controlled mismatched-CRC update incremented checksum failures, then `_publish_book` emitted `quality_status:'clean'` and reset `health.is_degraded` to false without resync. The monitor can consume that book. This is a controlled frame reproduction; it does not assert that live books were corrupt. Kraken's [official checksum guide](https://docs.kraken.com/exchange/guides/websockets/book-checksum-v2) describes checksum verification as confirmation that the local book remains synchronized; the project's own specification requires integrity enforcement before eligibility.

Monitor and comparison also construct generic Instrument objects instead of using connectors' fetched venue increments/minimums. Comparison hardcodes 0.25% fees and drops failed venues instead of preserving unknown entries. Thus COMPLETE does not reliably mean executable under the user's venue settings.

Repair: validate every entry point; use actual venue metadata and explicitly sourced/overridden fee profiles; enforce coherent fresh observations and integrity before eligibility. Invalidate corrupt books, obtain a synchronized recovery snapshot/session and require clean recovery before reuse. Keep missing venue coverage visible.

### A06 - P1: Several claimed features are disconnected or stubbed

Locations: [opportunity.py:106](/Users/jeremyliu/Desktop/Projects/OhMyCrypto/src/ohmycrypto/services/opportunity.py:106), [opportunity.py:150](/Users/jeremyliu/Desktop/Projects/OhMyCrypto/src/ohmycrypto/services/opportunity.py:150), [sidecar.py:257](/Users/jeremyliu/Desktop/Projects/OhMyCrypto/src/ohmycrypto/interfaces/sidecar.py:257), [notifications/outbox.py:24](/Users/jeremyliu/Desktop/Projects/OhMyCrypto/src/ohmycrypto/notifications/outbox.py:24), [cli.py:130](/Users/jeremyliu/Desktop/Projects/OhMyCrypto/src/ohmycrypto/interfaces/cli.py:130), [diagnostics.py:219](/Users/jeremyliu/Desktop/Projects/OhMyCrypto/src/ohmycrypto/services/diagnostics.py:219).

- Production evaluation does not schedule/persist 500ms/1s/3s follow-ups. Real stored decisions had all follow-up and continuous-persistence fields null; the assessment helper is exercised directly by fixtures.
- OpportunityService initializes a new in-memory cooldown manager rather than restoring persisted episodes. Re-instantiating the service against the same database re-alerted within milliseconds inside the cooldown interval.
- The production monitor/opportunity path does not enqueue or deliver through NotificationOutbox. Its outbox is in memory, despite the durability description. Quiet/audio/speech settings are saved but not connected to a durable delivery worker.
- Changing raw quota to 1 GiB persisted the setting, but the live ArchiveManager stayed at `2147483648` bytes. Retention settings likewise have no integration in the observed engine path.
- Inventory is a single browser-local balance comparison, never passed to the advisor by venue/currency. Editable fees/rebalancing and import workflows are not implemented end to end.
- CLI `compare --amount 1000` and `replay --bundle /does/not/exist.json` both return `pending_storage` with exit code 0. Monitor/export/import/diagnostics parity is absent.
- `reproduce_incident` unconditionally assigns `reproduced=True`. An empty-evidence checksum bundle returned REPRODUCED; its advertised `ohmycrypto diagnostics reproduce` CLI command does not exist.

Repair: complete each production workflow through the shared service/IPC/UI/CLI path and persisted records. Add actual expected behavior assertions, including restart, suppression/delivery outcomes, real follow-up coverage, enforced quotas, and negative incident reproduction. Disable or truthfully label unfinished controls until implemented; disabling promised capabilities alone would not satisfy the existing full-scope specification.

### A07 - P1: Acceptance verifiers still permit false release readiness

Locations: [verify.py:223](/Users/jeremyliu/Desktop/Projects/OhMyCrypto/scripts/verify.py:223), [verify.py:300](/Users/jeremyliu/Desktop/Projects/OhMyCrypto/scripts/verify.py:300), [release.py:497](/Users/jeremyliu/Desktop/Projects/OhMyCrypto/scripts/release.py:497), [test_bounded_scenarios.py:64](/Users/jeremyliu/Desktop/Projects/OhMyCrypto/tests/integration/test_bounded_scenarios.py:64).

The saved live report says `duration_sec:600`, while timestamps span about 5.54 seconds and the verifier performs one REST request per venue. It does not execute repeated production/WS/recovery scenarios. The native gate substitutes an app structure/signature check and sidecar ping for the installed shell journey. The 100-cycle test checks cycle counts, transitions and event existence, but does not actually assert RSS, queue/retention bounds, disk failures or recovery scenarios.

The release verifier rejects zero artifacts, but any nonempty checksummed list passes. A fabricated commit manifest containing only README.md returned exit 0. Required DMGs, source/notices, architecture, provenance, Developer ID, notarization and Gatekeeper are not verified.

Repair: replace test-count thresholds with named scenario completion and valid-data evidence; reject missing/failed/skipped required checks. Add verifier negative cases for document-only manifests, wrong architectures, synthetic native evidence, zero valid live observations and source mismatch. Run the installed native user journey and reopen affected acceptance rows.

### A08 - P1: Production signing/distribution is not implemented

Locations: [release.py:151](/Users/jeremyliu/Desktop/Projects/OhMyCrypto/scripts/release.py:151), [release.yml:104](/Users/jeremyliu/Desktop/Projects/OhMyCrypto/.github/workflows/release.yml:104), [EXECUTION_STATE.json:432](/Users/jeremyliu/Desktop/Projects/OhMyCrypto/.agent/EXECUTION_STATE.json:432).

Current app signature metadata is `Signature=adhoc`, `TeamIdentifier=not set`. `sign_and_verify_bundle` always uses `codesign -s -`. The workflow's certificate-present branch only prints a message, and prepare still applies ad-hoc signing. No Developer ID import/signing, accepted notarization, stapling or Gatekeeper release verification path was found in the reviewed packaging workflow. Supplying credentials alone would not complete this implementation.

Nevertheless R14 is marked proven and completion is PUBLIC_RELEASE_READY. This contradicts specification 1.1.0, which explicitly treats ad-hoc artifacts as development intermediates.

Repair: implement nested Developer ID signing and hardened runtime, notarization submission/result checks, stapling and Gatekeeper checks; exercise quarantined installation with both declared architectures and supported macOS versions. Mark release readiness accurately until those gates and core functionality pass. No new 24-hour/Intel-duration gate is needed.

### A09 - P1: The Intel release workflow targets a retired GitHub runner

Location: [release.yml:39](/Users/jeremyliu/Desktop/Projects/OhMyCrypto/.github/workflows/release.yml:39).

The workflow still selects macos-13. GitHub's [runner-images retirement notice](https://github.com/actions/runner-images/issues/13046) confirms that this image became unsupported in December 2025. This is a current remote-service prerequisite failure, not an observed run from this unpublished candidate.

Repair: select supported, explicit arm64 and Intel runner labels and prove architecture-matched Python wheels/sidecar/native shell. Rebuild on a clean checkout and run exact-candidate CI. Install the Playwright browser explicitly in the release job; it currently runs browser-dependent offline checks without that setup step.

### A10 - P2: Narrow-width navigation is clipped and can move the entire content offscreen

Locations: [styles.css:84](/Users/jeremyliu/Desktop/Projects/OhMyCrypto/desktop/src/styles.css:84), [styles.css:120](/Users/jeremyliu/Desktop/Projects/OhMyCrypto/desktop/src/styles.css:120), [styles.css:381](/Users/jeremyliu/Desktop/Projects/OhMyCrypto/desktop/src/styles.css:381).

At 320px, nav links extend to x=506.83 inside an overflow-hidden application shell. Clicking Settings in the browser test auto-scrolls that hidden shell to scrollLeft=187; main content moves to x=-187 and ends at x=133, leaving most content clipped. Document scrollWidth still equals 320, so an overflow-width-only check would miss the problem.

Repair: use a genuinely responsive navigation layout or a dedicated accessible scrolling navigation container. Keep main content fixed within the viewport; assert actual control visibility and element bounds at all four requested widths. Preserve Dashboard 3/2/8 and existing branding.

Evidence: [320px screenshot](/Users/jeremyliu/.codex/visualizations/2026/10/06/01a1100c-2105-7172-b825-a53bb166b532/settings-320.png), [1440px screenshot](/Users/jeremyliu/.codex/visualizations/2026/10/06/01a1100c-2105-7172-b825-a53bb166b532/settings-1440.png). Screenshots are copied beside this report.

### A11 - P2: Build/source provenance and dependency reproducibility need repair

Locations: [release.py:251](/Users/jeremyliu/Desktop/Projects/OhMyCrypto/scripts/release.py:251), [release.py:206](/Users/jeremyliu/Desktop/Projects/OhMyCrypto/scripts/release.py:206), [pyproject.toml:17](/Users/jeremyliu/Desktop/Projects/OhMyCrypto/pyproject.toml:17).

Prepare reuses an existing sidecar whenever its file exists, checking architecture without proving source/lock correspondence. `dist` binaries and build output are tracked, allowing stale generated binaries to conceal an incomplete clean build. This review reproduced current binary defects; it did not establish that every binary is stale.

The 327,841,209-byte source archive contains 5,735 entries, including `venv`, `.venv-x86_64`, `build`, `.codegraph`, `.agent` and nested release DMGs. Its filter excludes exact `.venv` but not those other generated roots. Selected important code files matched the current candidate, so do not incorrectly label the entire source archive as an old-code mismatch.

The specified hash-pinned runtime/dev Python lock files are absent; pyproject ranges and `pip install -e .[dev]` remain floating build inputs. npm/Cargo locks exist.

Repair: rebuild binaries from a frozen clean source using architecture-specific locked inputs; record source/lock/runtime/build hashes and reject unbound reused artifacts. Produce corresponding source from an explicit reproducible file set, excluding build outputs, environments, caches and release artifacts. Verify dependency notices against actual shipped components.

### A12 - P2: Native lifecycle and error recovery remain insufficient

Locations: [lib.rs:106](/Users/jeremyliu/Desktop/Projects/OhMyCrypto/desktop/src-tauri/src/lib.rs:106), [lib.rs:155](/Users/jeremyliu/Desktop/Projects/OhMyCrypto/desktop/src-tauri/src/lib.rs:155), [App.tsx:40](/Users/jeremyliu/Desktop/Projects/OhMyCrypto/desktop/src/App.tsx:40), [OverviewView.tsx:17](/Users/jeremyliu/Desktop/Projects/OhMyCrypto/desktop/src/components/OverviewView.tsx:17).

The native shell emits a sidecar-exited event but contains no reviewed respawn path. Requests synchronously wait up to 120 seconds; timeout cancellation does not cancel the Python operation. App-level load failure logs to console while retaining old status/data, and overview start/pause handlers have no catch/finally, leaving loading stuck on failure. Native errors no longer fabricate fixture rows, but visible and recoverable failure behavior is still incomplete.

Repair: explicit disconnected/error state, bounded asynchronous request handling, safe late-result/cancellation semantics, sidecar recovery policy and acknowledged lifecycle state. Validate the installed app under sidecar death, cold launch, pause/resume, relaunch, sleep/wake and clean quit. Installed-shell recovery, both native architectures, clean-user/minimum-macOS installs and migration/upgrade preservation were not proven by this review.

## Recommended repair sequence

1. Reopen false proven/done rows and remove PUBLIC_RELEASE_READY. Keep history, owner cancellation and authorization intact.
2. Fix A01-A04 as one data-contract/storage/replay workstream; add tests through the actual serialized production boundaries.
3. Fix A05 and the fee/metadata/inventory portion of A06 before trusting any financial or eligibility claim.
4. Complete remaining A06 workflows plus A10/A12; validate the full real user journey.
5. Repair A07, require named bounded scenarios and verifier-negative cases, then run clean current-candidate checks. Reuse the owner's revised bounded policy; do not reintroduce a duration gate.
6. Repair A08/A09/A11, build both architectures, verify clean installs and exact source correspondence, then ask only for genuinely remaining external prerequisites/publication authorization.

The agent should report completed scenarios, concrete failures and remaining external prerequisites. Passing existing test counts, checksum files or a ping must not automatically restore release readiness.

## October 6 planning supplement

This copy preserves the original read-only audit above. The subsequent owner-authorized planning turn added documentation/state and retained snapshots; it did not fix business code. Specification 1.2.0 in PROJECT_EXECUTION_GUIDE.md is the only active plan.

### A13 - P1: Incorrect diagnostic recovery timestamp and lost grouped evidence

SOURCE_CONFIRMED and DIRECTLY_REPRODUCED in isolated temporary storage. MonitoringService._run_cycle passes bool(book.bids and book.asks) as the third positional parameter of DiagnosticService.record_clean_observation, whose parameter is now_utc_ms. After three True observations an incident closed_at_ms is 1. StorageRepository.save_incident's conflict update only changes closed_at_ms/is_recovered; grouped evidence is not updated. Two related faults retained two in-memory samples but exported persisted samples_count=1 and only the first sample. Active incidents also start as an empty in-memory registry on initialization.

Repair: keyword-typed real UTC timestamps, validity-aware recovery, atomic bounded grouped evidence/count persistence and restart restoration, with real export/reproduction tests.

### A14 - P2: Incoming capture can exceed the configured quota

DIRECTLY_REPRODUCED in an isolated ArchiveManager with quota_bytes=16: a capture containing 100 x characters returned a hash and wrote 114 bytes. write_capture checks current total, not current total plus incoming size. Pinned writes bypass this check; there is no separate pinned quota in that class. Pruning occurs only on quota pressure and ignores retention settings unless explicitly called. Complete capture_data also lives inside opportunity_json; database growth must be covered rather than treating archive bytes as total evidence size.

Repair: incoming-byte reservation, separate pinned/free-space limits, effective time-based retention/settings, bounded database/WAL/temporary state and explicit missing-coverage outcomes. Preserve pinned user evidence.

### Additional source-confirmed CI and connector gaps

release.yml uses macos-13 (retired) and macos-14 (retiring November 2, 2026). Official current alternatives and runner architectures were checked during planning: macos-15 arm64 and macos-15-intel x64. CI source at this revision also contains a fixed 300-second soak dependency. Replace it with completed bounded scenarios. The release workflow copies same-named manifests/checksums from both artifact directories into release/final, overwriting one rather than aggregating; per-architecture artifact uploads omit legal files referenced by those manifests. Clean downloaded-artifact verification must exercise these paths.

Coinbase protocol recovery/sequence/snapshot/depth behavior needs explicit production conformance proof. The reviewed handler discards top-level frame context and publishes updates without a per-connection snapshot check. Neither this inspection nor existing fixtures establishes actual safe reconnect recovery; current official schemas and compatible baseline synchronization must be verified. This is a verification gap, not proof of corrupt live traffic.

References: [GitHub runner images](https://github.com/actions/runner-images), [macOS 14 retirement](https://github.blog/changelog/2026-10-01-github-actions-macos-14-runner-image-retirement/), [Coinbase public endpoints](https://docs.cdp.coinbase.com/coinbase-app/advanced-trade-apis/websocket/websocket-endpoints), [Coinbase level2](https://docs.cdp.coinbase.com/api-reference/advanced-trade-api/websocket/level2).
