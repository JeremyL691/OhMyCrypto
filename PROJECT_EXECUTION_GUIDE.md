# OhMyCrypto Project Execution Guide

Specification version: 1.1.0

Prepared: October 5, 2026, America/Los_Angeles

Status: completion and release remediation plan for the existing implementation. Revised after the October 5 code review and the owner's explicit cancellation of the 24-hour task. This document is not evidence of product completion.

## 1. Authority, scope, and completion

### Owner revision: October 5, 2026

The owner cancelled the running 24-hour task and requested a new detailed plan and successor prompt to finish the entire product and prepare it for release. This revision supersedes the previous fixed-duration reliability requirements and previous task completion claims.

- T18 / `soak24h_gen13` is cancelled by the owner. Its Python process and caffeinate helper were stopped and confirmed absent. Never restart it on resume.
- Neither a 24-hour soak nor the former fixed Intel 60-minute window is a release requirement. Do not replace them with another mandatory long run, wait for a day to elapse, or create an unattended soak automation.
- R12 now means bounded, scenario-based monitoring and recovery validation on the actual product, with repeated real acquisition and controlled fault checks. Completion of the scenarios determines success; elapsed time alone never does.
- Complete all three product capabilities, the real desktop/CLI workflows, and the selected macOS distribution checks. Cancellation of the soak does not waive calculation correctness, honest data states, functional completeness, or installation/signing checks.
- Reuse the existing implementation and repair it. A restart from zero, a second competing roadmap, new hosted infrastructure, or additional product scope is unnecessary.
- Previous evidence is historical. Reopen affected requirements and freeze a new candidate after remediation. Old `PROVEN`, `PASSED`, and `PUBLIC_RELEASE_READY` fields do not transfer to the new candidate.


This is the authoritative specification for the complete refactor. Deliver all three capabilities in one release:

1. Opportunity verification, evidence inspection, temporal follow-up, and deterministic replay.
2. Market data quality diagnostics and reproducible incident investigation.
3. Personal execution cost comparison, including amount sensitivity, inventory, and split-order scenarios.

They share one acquisition pipeline, calculation kernel, event store, and desktop application. Do not ship three isolated demos or defer one capability to an unspecified later release. The intended result is an installable local-first macOS application that launches without developer Python, Node, Rust, or a terminal. Retain a supported CLI for headless monitoring, export, replay, and diagnostics.

The product analyzes public data and delivers notifications. It does not place orders, transfer assets, hold funds, or collect trading credentials. Manually entered fee profiles and balances support scenarios; no trading API exists to activate accidentally.

The coding-agent goal and the application's monitoring loop are separate. The agent completes implementation and release readiness. The installed application monitors while its host is awake, with pause/resume, bounded resources and recovery. Host sleep causes a coverage gap; identify it and rebuild market state after wake.

### 1.1 Owner-selected decisions

| Decision | Selected value | Effect |
|---|---|---|
| Distribution | GitHub Releases, macOS application | Signed/notarized application and DMG; actual upload requires separate authorization |
| DESIGN_VARIANCE | 3 | Conservative, familiar interactions |
| MOTION_INTENSITY | 2 | Minimal transitions; reduced-motion support |
| VISUAL_DENSITY | 8 | Compact data dashboard, readable tables |
| Product scope | All three capabilities | Mandatory in the first complete release |
| Project license | GPL-3.0, SPDX `GPL-3.0-only` | Matching corresponding source, license and notices with binary releases |

The owner selected these decisions in this chat. Do not request them again before frontend work. Preserve any existing brand assets; no logo or visual system has been verified in the present repository.

Planning defaults: macOS 13+, separate Apple Silicon and Intel artifacts, Python 3.12 development baseline, no paid services or purchases. The owner selected GPL-3.0; use GPL-3.0-only without adding an unrequested later-version clause. Legal owner/signing credentials/native test-host availability are prerequisites, not facts established by the documentation author.

Remote candidate-branch pushes and draft PR creation require an explicit owner decision separate from publication. Until that decision is recorded, they are not authorized; R11 remote CI remains a prerequisite while local work proceeds. Check existing trusted authorization on resume rather than asking again for a permission already granted. Main-branch merge and public Release publication are not granted by a candidate-branch permission.

### 1.2 Release endpoint and states

The requested implementation endpoint is `PUBLIC_RELEASE_READY`: all product and selected-channel checks passed, with installable distribution artifacts and accurate release materials. Public upload is separate and requires authorization for destination, version and artifacts.

Use distinct states:

- `IN_PROGRESS`: implementation/remediation has unfinished required work.
- `IMPLEMENTED`: required code exists; acceptance incomplete.
- `PRODUCT_VALIDATED`: correctness, integration, recovery, UX and bounded product scenarios pass.
- `ARTIFACT_BUILT`: files exist, but channel verification may remain.
- `PUBLIC_RELEASE_READY`: all revised R01-R15/N00-N08 and channel conditions proven.
- `PUBLISHED`: authorized upload confirmed and downloadable artifact hashes match verified files.

An unsigned DMG is intermediate. Missing signing, notarization, native architecture evidence, or a required functional scenario prevents release readiness. `PROJECT_COMPLETE` requires the entire original scope and every required gate, with independent review and candidate-bound evidence. No implementing agent may waive a required check, shrink scope to fit completed work, or replace native/live acceptance with a mock.

This handoff defines authorized successor implementation and local release preparation. The current planning turn changes documentation/state and adds a narrow owner-cancellation guard to the old soak entry point; it does not implement the product repairs. Preserve recorded authorization for remote writes, signing submissions, spending and publication. The owner wants release after development completion; the known-broken candidate must not be published.

## 2. Current evidence and where to start

Repository: `JeremyL691/OhMyCrypto`; checkout: `/Users/jeremyliu/Desktop/Projects/OhMyCrypto`; branch: `codex/v1-refactor`.

Review baseline: local HEAD `561420d9465bb0b633c3f6944009ad3d08b589fb`. Existing release assets identify candidate `a8b868a8553f7a98ecb7375e31e4771e1813db3a`. The intervening changes include evidence and generated release assets; recheck the actual tree before implementation. Remote main was still `1058083ad92b23f4e16d7068f9aea1a665209d60` at this review and no remote candidate branch was found. No current candidate CI pass was established.

### 2.1 Verified baseline and its limits

- The guide's Python unit/integration/replay command passed 57 tests after removing sandbox restrictions that prevented localhost WebSocket tests and bundled execution. The initial sandbox failures were environmental, not established product defects.
- TypeScript typecheck passed; UI unit tests passed 7 cases; browser E2E passed 8 cases against the existing built fixture UI. These do not prove installed-app behavior.
- Browser checks at 320, 768, 1024 and 1440 pixels found no whole-page horizontal overflow across the five destinations. They are not full accessibility or native WebView acceptance.
- Existing artifact hashes matched the manifest. The application signature was ad hoc with no TeamIdentifier; the arm64 DMG had no stapled notarization ticket. Real Intel-host, minimum-OS and quarantined clean-user installation were not established by this review.
- The old `.agent/evidence/t11_final_audit.json` declares release readiness for an earlier candidate. Treat it as superseded evidence, not the current completion authority.
- The cancelled task's generated report is preserved as historical output. Its `passed` field cannot override the owner's cancellation or establish reliability.

### 2.2 Mandatory reproduced regressions

| ID | Observed behavior | Source anchor | Required repair |
|---|---|---|---|
| F01 | Repeated real Coinbase acquisition using the monitor's loop pattern: first fetch succeeds; second raises `Event loop is closed` | `services/monitor.py:_run_cycle`; persistent CCXT client | One persistent event loop and owned client lifecycle; repeated acquisition and recovery |
| F02 | Original profit `9.451371529250`, replay profit `9.1777431015331250`, yet `is_exact_match=true`; changing the sell price from 110 to 120 leaves input hash unchanged | `services/opportunity.py:replay_bundle`; `domain/kernel.py` input hash | Full capture/config/version replay; price/quantity-inclusive hashes and canonical-result equality |
| F03 | Native IPC comparison failure returns two fixture rows marked COMPLETE; no demo banner is visible at that point | `desktop/src/ipc.ts:compareCosts` | Fail visibly in native mode; explicit demo selection only; atomic data provenance |
| F04 | One available BTC at price 100 is reused by two 80-unit child budgets; output claims 1.6 BTC and all_complete | `services/cost.py:evaluate_split_order` | Consume shared depth per child and enforce conservation |
| F05 | Official Kraken example checksum is 3310070434; both implementations calculate 383156747; mismatch recovery is disabled by default | `adapters/stream.py`; `adapters/kraken.py` | Correct decimal formatting/parsing and subscribed-depth handling; isolate mismatches and resync |
| F06 | Latency and amount-grid outcomes are hardcoded; split slider does not compute; Quiet Mode resets on tab navigation; settings export buttons have no handler | Desktop diagnostics, cost and settings views | Real service wiring, durable settings and completed actions |
| F07 | Adversarial soak test: 86400-second target, all REST samples fail, terminate after 6.03 seconds; completed_target=false but exit 0 / passed=true | `scripts/soak.py` | Remove formal soak gating; verifiers must reject incomplete/no-data scenarios |
| F08 | Release workflow supplies `--arch x64`; release CLI rejects it; Tauri bundle.active=false conflicts with workflow bundle lookup; Developer ID branch only prints a message | Release workflow, release CLI and Tauri configuration | Coherent repeatable dual-architecture packaging and actual signing/notarization |

These observations identify repair targets, not permission to alter original evidence. Add independent regression cases and fix the implementation. Do not weaken assertions, relabel fixtures as live, or edit historical result fields to obtain a pass.

The original implementing agent continued running during planning and attempted to restart the cancelled task. It was stopped again. A narrow guard in scripts/soak.py rejects 24-hour-or-longer runs when the owner cancellation record says must_not_restart. Preserve concurrent implementation changes and re-read current source before acting on review-baseline findings.

### 2.3 Preserve useful work

Keep the Python/Decimal domain separation, SQLite/WAL foundation, versioned JSONL bridge, Tauri-owned sidecar, five UI destinations, themes and existing tests. Review their contracts and integration rather than replacing them for style. The development environments are symlinks outside the iCloud-synced checkout; do not move, delete or recreate them without need. The current release assets are historical intermediates and must be rebuilt from the repaired frozen source.

## 3. Final product behavior

Five primary destinations: Overview, Opportunities, Feed Diagnostics, Cost Comparison, Settings. Replay is an event/incident detail view. Every feature operates through the same kernel and store.

### 3.1 Opportunity verification and replay

Input: eligible venues, one spot instrument, all-in amount, fee profiles and alert rules. Retain candidates, including rejected/unknown ones, with bounded sampling and honest counts. Quiet days show coverage and rejection reasons rather than invented opportunities.

Each event exposes stable ID/episode/route; instrument and actual currencies; amount and fee profiles; discovery spread; consumed book levels/VWAP; fees and estimated net result; precision/minimum findings; inventory constraints; input/configuration/version hashes; capture clocks, timestamp meanings, alignment and gaps; decision/reason codes; and notification state.

Follow up at 500 ms, 1 s and 3 s. Use adequate recorded resolution and coverage, otherwise return `UNKNOWN`. Export a self-contained replay bundle containing initial snapshots, ordered updates, settings, schemas and hashes. Preserve the original decision separately from re-evaluations under changed settings or versions.

Keep three separate outputs: input verification (valid/invalid/unknown), economic result (positive/non-positive/unknown), and alert eligibility (eligible/ineligible/unknown). A valid non-positive net result is not an eligible opportunity. Eligibility requires valid coherent inputs, supported cost/inventory/limits, and both configured net-result and spread thresholds. Record the predicate and its version.

Every follow-up holds the initial route, amount, fee/inventory assumptions and configuration fixed. Record the result at the requested offset AND continuous quoted-condition persistence. Continuous persistence requires known coverage and uninterrupted eligibility across the full interval; any observed failure ends the segment, and any coverage gap yields UNKNOWN for the affected interval. A recovery starts a new segment. A candidate disappearing at 250 ms and returning at 750 ms may be positive at one second but did not persist continuously. Define permissible channel-specific coverage gaps before verification and record actual scheduled/observed offsets and scheduling delay.

Report quoted-condition persistence. The application observes no actual fills and cannot label a positive simulation as completed arbitrage. A recorded event is useful even if it was rejected.

### 3.2 Market data quality diagnostics

Measure per connector and channel: request/response distributions, connection liveness, meaningful source age, missing/invalid fields, sequence gaps, reconnects, rate limiting, snapshot recovery, coherent-book availability and archive coverage.

Display sample counts, periods, denominators, measurement location and clock uncertainty. Local retrieval latency is not matching-engine latency. Identical prices alone are not a fault; low-activity markets can publish no price changes. Distinguish observations from causal hypotheses about exchange/network/collector behavior.

An incident bundle includes the captured input window, adapter/capability profile, relevant settings, recovery events, metric definitions, hashes and offline reproduction command. It must work without account credentials or the original machine.

Use a versioned incident-rule registry: connector/channel/fault class, trigger, minimum samples/window, severity, grouping interval, recovery condition, and pre/post capture window. Initial defaults: malformed/non-finite or integrity-invalid book immediately creates a finding and invalidates decisions; three consecutive request failures create a retrieval incident; one related fault key groups within 60 seconds; recovery needs a valid rebuilt book and three consecutive clean observations. Capture at least 10 seconds before and 30 seconds after an incident where coverage exists, and disclose shorter/gapped windows. Rate-limit backoff follows connector policy. Threshold changes version the registry and reopen affected evidence.

Repeated violations update one incident; verified recovery closes it with coverage/recovery evidence. Incidents arise without profitable candidates. The full workflow is fault -> visible incident -> grouping -> recovery/closure -> pin/export -> offline reproduction.

### 3.3 Personal execution cost comparison

Input: buy/sell, spot instrument, amount and units, eligible venues, per-venue fees. Compare coherent book states and show all-in cost or proceeds, net base received, VWAP, quote/base fees, depth, limits, precision, quote age and unknowns.

Include an explicit amount grid, such as 100, 1000 and 10000 quote units where supported; keep ineligible sizes visible with reasons. Distinguish quote-denominated buy budgets from base-denominated sell amounts.

Support user-entered inventory. Cross-venue opportunities assume required assets are already on their respective venues. Show inventory consumption and separately configured later rebalancing scenarios. Do not assume instant transfers or deduct a withdrawal fee on each trade when no transfer occurs.

If balances are not entered, show unconstrained cost comparison separately from inventory feasibility, which remains UNKNOWN. Do not reject an otherwise measurable single-venue cost only because unrelated cross-venue inventory is unknown, and do not label unknown inventory as available.

Implement split-order scenario comparisons with explicit allocations and delays. Simultaneous child orders consume disjoint shared depth. Future delayed purchases are scenarios, not measured savings. Preserve residual assets, fees and uncertainty.

## 4. Architecture and construction method

| Layer | Choice | Constraint |
|---|---|---|
| Engine | Python 3.12, Decimal, typed immutable records | Deterministic calculations separated from I/O |
| Public adapters | CCXT REST metadata/snapshots and explicit venue WebSocket adapters | Verify native venue identity, public endpoint, limits and sequence semantics |
| Storage | SQLite migrations and bounded raw archives | One writer, atomic manifests, recoverable local state |
| UI | React/TypeScript/Vite, native CSS, Lucide | Compact Dashboard 3/2/8; no unnecessary animation library |
| Native shell | Tauri 2 with packaged Python sidecar | Parent owns child lifetime and allowlisted IPC |
| IPC | Versioned JSON Lines over child stdin/stdout | No unauthenticated local listener; stdout reserved for protocol |
| CLI | Installed `ohmycrypto` entry point | Same domain/services as desktop |
| Packaging | Verified PyInstaller bundle plus Tauri per-target resources/entry | Include interpreter/dependencies; clean-user native verification |
| Checks | pytest, independent oracles, IPC/replay tests, Playwright, native checks | Browser mocks supplement rather than replace installed-app acceptance |

Repair and validate the existing sidecar packaging/start/quit contract early in N00/N02/N06 before final UI acceptance. Use current locked-version documentation for sidecar naming and resources. Do not add hosted services, Redis, Kubernetes, user accounts, a trading bot framework or an LLM to satisfy this release. Reuse mature tools where appropriate without hiding project-specific correctness contracts.

Start with the current Python calculations as migration material, not as the sole correctness oracle. Write independent regression/oracle cases, define normalized contracts, migrate useful behavior behind those contracts, then connect adapters/storage/services/UI. Delete old paths only after replacements and compatibility checks pass.

IPC has request IDs, schema versions, bounded size, status/error responses, and ordered events. Domain numbers are decimal strings. The shell validates payloads and exposes no arbitrary command/file operation. Logs go to stderr. High-rate feeds remain inside the engine; UI updates are coalesced with bounded queues and explicit display-drop counts. Decisions/incidents must not be silently dropped. A slow view cannot block feed validation.

Only one engine/database writer runs per user. Duplicate launches attach or exit clearly. Parent exit terminates its owned child; bounded crash recovery must not spawn duplicate collectors.

### 4.1 Target structure

Create incrementally; do not create empty wrappers just to match this tree.

```text
README.md
PROJECT_EXECUTION_GUIDE.md
AGENT_PROMPT.md
pyproject.toml
requirements-dev.lock and runtime lock
src/ohmycrypto/
  domain/        # instruments, books, fees, costs, decisions, findings
  adapters/      # public REST/WS, metadata, capabilities, normalization
  services/      # monitoring, verification, diagnostics, comparison, replay
  storage/       # migrations, SQLite repositories, raw archives
  interfaces/    # CLI and JSONL sidecar
  notifications/ # durable outbox and bounded macOS delivery
desktop/
  src/           # React views and typed IPC
  src-tauri/     # lifecycle, command scope, native resources
tests/
  unit/
  integration/
  fixtures/
  replay/
  acceptance/
scripts/         # bounded verification, build and release entry points
release/         # candidate manifests and channel configuration
.agent/
  EXECUTION_STATE.json
  HANDOFF.md
  actions.jsonl
  evidence/<verification-id>/
```

Dependency direction: interfaces -> services -> domain. Adapters/storage implement explicit boundaries. Domain functions do not fetch data, read clocks, launch processes or mutate storage. One component owns each responsibility.

## 5. Data contracts, time and persistence

Define JSON schemas and Python/TypeScript contract tests before consumers.

| Record | Required information |
|---|---|
| Instrument | Canonical base/quote, spot type, exact venue/native market, precision/limits, capability version |
| CaptureEnvelope | Session/connection epoch, monotonic capture sequence, adapter/channel, source time and meaning, local UTC/monotonic receipt, request interval, raw hash |
| BookState | Instrument, ordered levels, snapshot origin, applied sequence, source/receipt clocks, usable depth, quality/reconstruction status |
| FeeProfile | Venue, maker/taker, rate/fixed component, charged currency, source/as-of/expiry, override and known/unknown |
| CostScenario | Side, amount/units, budget semantics, fees/books, inventory, rounding/delay assumptions |
| DecisionEvent | Stable event/episode/route, scenario/input/config/version hashes, result/breakdown/reasons, follow-up and notification states |
| DiagnosticWindow | Channel, period, counts/denominators, distributions, coverage, gaps/clock uncertainty, findings |
| ReplayManifest | Schema/version, event, snapshots/update hashes/order, settings, coverage, original/result hashes |
| Notification | Outbox/event IDs, mode, decision/enqueue/delivery clocks, attempts, state, error, cooldown key |

Serialize finite financial values as decimal strings and include currency identifiers. No NaN/infinity JSON. Schema migrations retain inspectability of old events or provide an explicit converter.

Connector profiles declare their actual integrity mechanism: source sequence IDs if supplied, ordered channel behavior, checksums/covered depth, snapshot/delta application, and gaps that cannot be observed directly. A local capture sequence is not an exchange sequence. Parse raw decimal tokens without first losing precision through binary floats. For Kraken book v2, implement documented checksum rules and truncate to subscribed depth after each update; a top-ten checksum does not prove integrity of all deeper levels. Conformance fixtures include repeated-level updates, checksum failures, truncation and absent source sequence IDs.

### 5.1 Clock and book rules

- Monotonic time measures intervals within a process; UTC records provenance and persisted deadlines. Clock jumps are findings; restart recovery uses explicit wall-clock reconciliation, never persisted monotonic values as a new process clock.
- Exchange timestamps stay separate with semantics such as last trade, book update or unknown. Absence is not proof of freshness/staleness.
- Streaming books require correct baseline snapshots and ordered deltas. A gap invalidates the book until resynchronization; never evaluate a partial reconstruction.
- Distinguish last price/depth mutation, last integrity confirmation, channel liveness, and evaluation time. An unchanged book remains usable only when connector-specific evidence establishes uninterrupted synchronized state. Unrelated heartbeat traffic cannot refresh a stalled book. Record the validation interval and the evidence supporting it.
- Initial limits for latest validated book observations: age <=1000 ms and inter-venue observation difference <=250 ms. For a continuously synchronized stream, an observation at the evaluation time is supported by its integrity/liveness contract even without a new price mutation. REST uses the actual snapshot request/receipt interval. Record limits and uncertainty. Source age requires appropriate semantics/clock bounds; never compare arbitrary last-trade times as book ages.
- REST fallback results that cannot establish timing remain provisional/unknown. A two-second polling series cannot prove 500-ms persistence.
- Replay at t uses only input available at or before t in local receive order, tie-broken by capture sequence/connection epoch. Future messages cannot improve earlier decisions.
- Sleep, missing archives or disconnected feeds create explicit coverage gaps. Unknown follow-ups remain unknown. Keep the denominator and unknown count when calculating persistence summaries.

### 5.2 Storage and recovery

Use the normal macOS per-user application support directory, outside the checkout and signed bundle. One writer, transactions, foreign keys, bounded batches and WAL where appropriate. Raw archives are content-addressed; manifests commit atomically. Bound import size and archive expansion.

Defaults: seven days of diagnostic aggregates, 48 hours of rolling raw capture subject to a 2 GiB raw quota. Self-contained pinned event bundles have a separate visible quota. Prune eligible unpinned data only. If pinned quota or free-space limits are exhausted, expose the condition and stop new archive capture safely; do not delete pinned user evidence or claim complete coverage.

Persist settings, fee profiles, alert episodes, notification outbox, incidents, active monitoring configuration and migrations. On restart reconcile incomplete transactions/archive writes, mark interrupted intervals, validate database/schema and rebuild books before resuming decisions. Database corruption produces a recoverable error; never silently replace it with a blank database.

## 6. Calculation, eligibility and delivery

### 6.1 Inputs and instrument compatibility

Reject malformed types, bool-as-number, non-finite values, non-positive prices/quantities, crossed/unsorted normalized books, incompatible assets/quotes, unsupported spot markets and missing mandatory metadata. Aggregate exact duplicate levels only with an explicit normalization rule. Isolate invalid connectors/events instead of killing the monitor.

Allow finite zero-fee profiles and optional zero thresholds; enforce positive quantities and finite bounded intervals. Verify exchange capability through the supported registry/metadata, not arbitrary `hasattr`. Maintain exact endpoint/venue identity: do not mix Coinbase Advanced Trade metadata with Coinbase Exchange stream data without verified equivalence. The initial release supports two declared public spot connectors; register their current venue IDs and common supported symbols during N02. Additional unsupported venues get clear results, not fictional support.

### 6.2 All-in budgets, fees and rounding

For quote buy fee f and all-in budget B, require `book_spend + buy_fee <= B`; a proportional quote fee implies spend <= `B / (1 + f)`. Walk asks, apply documented conservative size rounding and market limits. Base-denominated fees reduce acquired base before sale. Third-token fees require supported conversion/provenance or unknown cost.

Depth-consuming estimates use taker fees. Maintain a per-venue/per-currency debit/credit ledger with fee rounding, residuals and balance checks. For a base-charged sell fee, require `sell_quantity + sell_base_fee <= available_base`; a proportional rate f without fixed fee bounds sale by available_base/(1+f), followed by venue rounding. Quote-charged sell fees reduce quote proceeds. Apply fixed minimum/per-order fees at the actual child-order level, including split scenarios. Never subtract a base quantity from a quote value.

Sell only available net base, rounded down to the sell venue's increment. Walk bids and deduct sell fees in their actual currencies. Keep residual base/unspent quote visible; P&L does not assume dust vanished. Unsupported cross-quote conversions are rejected with reasons. Budget and conservation invariants apply to buy, sell, split and inventory scenarios.

Report quote cash result separately from any explicitly priced residual-asset valuation. Cross-venue net result requires matching inventory obligations and a disclosed valuation/rebalancing scenario; unknown conversion or residual valuation cannot be hidden in one profit figure. Independent oracles include base sell fees, fixed fees for multiple children, fee rounding and venue/currency balance conservation.

Use independent hand-derived fixtures for depth, fees, precision, dust, limits, differing currencies, zero fees and exact rounding boundaries. Expected answers cannot call the implementation being tested. Unknown fees/limits/depth/timing prevent the label verified; retain the case with reasons. No silent universal 0.1% fee assumption.

### 6.3 Episodes, cooldown and notifications

Cooldown identity includes route, canonical instrument, amount/units and relevant fee/config profile. Ordinary price movement does not change identity. Persist episode IDs, update eligible episodes, and close after a documented disappearance interval or relevant settings change. Keep closure/reopen rules testable.

Default cooldown: 30 seconds. Escalation requires a material absolute improvement and a relative improvement from the last notified eligible result. Initial USD/USDT scenario defaults: >=2 quote units AND >=15% net-result improvement. Other quote units require explicitly unit-aware settings. Unknown/non-finite results cannot escalate.

Delivery lifecycle: pending -> delivering -> delivered, or failed/suppressed. One bounded worker, coalesced episode updates, visible queue backpressure, timeouts and bounded retries. Record decision separately from successful emission. Quiet mode records suppression, not playback. Inspect subprocess exit code and missing resources. Restart reconciliation avoids duplicate emission when delivery outcome is uncertain; preserve uncertainty instead of claiming exactly-once audio.

Native delivery checks verify installed-app invocation and output/resource behavior. A stub only proves scheduling. An emitted sound does not prove a human heard it.

## 7. Diagnostics and replay acceptance behavior

Diagnostic severity differs from opportunity eligibility; an incident can matter when no candidate is profitable. Required induced-fault fixtures: malformed JSON/types, NaN/infinity, missing fields, crossed books, delayed response, timeout, rate limit, reconnect, out-of-order/gapped deltas, clock jump, disk full and sidecar termination.

Define each metric's denominator/window. Retrieval success, usable book, coherent comparison, archive coverage and delivered notification are separate counts. Show distribution conventions, sample counts and unknowns. Hypothesized causes must be labeled as hypotheses.

Replay operations:

1. Reproduce the original decision with original stored settings/calculation version.
2. Evaluate the same capture under an explicitly changed version/configuration.
3. Compare and explain changed decisions without overwriting original evidence.

Two runs with identical input/config/version yield identical canonical result hashes. Specify which output fields are hashed; runtime durations are excluded. Real captures and synthetic fixtures are labeled separately. Corrupt/partial bundles fail or show explicit unknown sections; no live-profit claim comes from fixtures.

Maintain a versioned replay-kernel registry for calculation versions produced by this release. Imported data never supplies executable code, and replay never downloads/runs arbitrary version hashes. Declare supported versions and retain their independent fixtures. Unsupported versions remain inspectable with the original stored result/hash, but exact reproduction fails explicitly as UNSUPPORTED_VERSION. An upgrade fixture replays an event from a previous supported kernel with unchanged canonical result. Re-evaluation uses the current identified kernel and preserves the original.

## 8. UI, accessibility and native workflow

The owner has already selected Dashboard 3/2/8. Do not ask again. Before replacing the experience, audit the current terminal workflow, preserve useful commands and brand assets, and collect actual before/after evidence for final UX review.

Implement:

- Overview: select/validate venues, instrument, all-in amount/units, fee profiles and alert rules; show active assumptions/limits; start/pause/resume; display coverage, connectors and recent events. Changes apply prospectively and never rewrite stored events.
- Opportunities: verified/rejected/unknown filtering, details, evidence, follow-up/replay.
- Feed Diagnostics: definitions, distributions, incidents, raw evidence and bundle export.
- Cost Comparison: buy/sell, amount/units, venues, editable fees, depth sensitivity, inventory and split scenarios.
- Settings: retention/storage, notifications, import/export, formatting, start-at-login opt-in.

First launch requires no trading keys. Offline exploration uses an explicitly labeled fixture/demo dataset. Recorded evidence remains accessible during network failures. Implement empty, loading, error, disconnected and partial-data states.

Apply the owner's UI rules: semantic nav/main/section/article/aside where appropriate, dark/light themes, Lucide icons, no Unicode emoji icons, invented filler names, em dashes in UI copy, unnecessary wrappers or gradient buttons. Left-align long text. Light-mode text must meet contrast and the owner's #666 gray threshold. Use native CSS feedback and reduced-motion support.

Test widths 320, 768, 1024 and 1440 pixels in both themes, plus keyboard, focus, labels, zoom and text/table chart equivalents. Compact tables can scroll horizontally with labeled columns; critical controls and explanations stay usable. Units and uncertainty cannot be indicated by color alone.

Native installed-app checks cover cold launch, window/tray behavior, single instance, pause/resume, saved replay, export, notifications, sidecar recovery, sleep/wake and quit. Browser/Playwright checks with mocked Tauri supplement these checks but cannot establish native behavior. Verify actual macOS WebView behavior separately from Chromium.

Tauri's current macOS test route includes the WebdriverIO service with an embedded test server; direct tauri-driver support is different. Verify the locked-version route early. Instrumented native test builds supplement platform accessibility/automation checks on the exact signed production app. Production artifacts must contain no enabled test server or mock IPC. Test first launch -> configure -> start -> inspect -> change fee/profile -> replay original unchanged -> pause -> restart with saved settings.

## 9. Privacy, security and licensing

All state stays local; no telemetry or automatic upload in v1. Provide Complete Replay and Sanitized Share exports. Complete Replay keeps every decision input, including necessary inventory, while removing unrelated private metadata. Sanitized Share may omit inputs but declares omissions and affected reproduction claims in its manifest; affected results are UNKNOWN and original exact replay is unavailable. Never invent missing balances. Preview shows removed capabilities; preserve the original local event unchanged. Credentials never appear in logs, state, screenshots or fixtures.

Allowlist public exchange hosts and sidecar commands. Validate imported archives for size/expansion, traversal, schema and hashes. Exchange/import strings are data, not HTML or instructions. Reject unsafe paths and decompression bombs. Use CSP and minimum Tauri capabilities; no arbitrary remote navigation in the privileged view.

Choose a stable application identifier before signing; preserve data paths across upgrades. Add the official full GPL-3.0-only text, accurate copyright ownership, dependency notices and provenance during implementation. Check distribution compatibility for Python, native wheels, Tauri, UI dependencies and PyInstaller's bootloader exception. Do not invent legal/support identities.

Each binary release includes access to its exact corresponding source: application, build/configuration scripts, locks, patches and instructions. Include a source archive or verified matching tag with hash correspondence; unrelated current main is insufficient. Preserve applicable source/binary notices. Do not introduce incompatible bundled components and obscure their license obligations.

Signing credentials stay in keychain/CI secrets; state stores reference names/availability only. Enrollment, paid data, runners and hosting need explicit budgets. Public API access does not establish unrestricted raw-data redistribution rights. Check connector terms before sharing captured samples; use synthetic/sanitized fixtures when real samples are not shareable.

## 10. Detailed completion plan and construction order

N00-N08 are the active task IDs for this revision. T00-T18 are historical task records; old done flags are not acceptance for N tasks. The owner-cancelled T18 remains cancelled. The following phases preserve Sections 3-9 as the product contract.

### N00 - Reconcile scope, evidence and working state

Dependencies: none.

1. Read instructions, this revision, prompt, state and handoff; inspect Git changes and actual processes. Verify the cancelled task is absent and do not restart it.
2. Retain historical reports and budgets/authorization/retry lineage. Mark affected gates pending or incomplete, attach F01-F08 to the active work, and remove any automatic completion transition driven by the old soak.
3. Establish current tools and dependency inputs. Inspect the current remote default branch read-only. Make new work reviewable on the existing candidate branch; preserve unrelated changes.
4. Map the five destinations and CLI actions to service methods and persisted records. Enumerate stub buttons, fixture fallbacks, hardcoded financial/diagnostic values and uncalled service methods.
5. Turn the reproduced defects into meaningful regression tests with independent expected results. Do not use test counts as a correctness oracle.

Exit: baseline identity and scope revision recorded; actionable feature/defect map; cancelled job reconciled; old claims clearly historical. No readiness claim.

### N01 - Repair calculation contracts and evidence identity

Dependencies: N00.

1. Validate every financial entry point: reject bool-as-number, non-finite/negative values, malformed or crossed/unsorted books, unsupported symbols/currencies and incomplete metadata. Zero fees and zero thresholds remain valid where specified.
2. Use actual venue instruments, increments, minimum sizes/notionals and currency-aware fees. Remove universal hardcoded taker rates from monitor/sidecar paths. User overrides carry explicit provenance and apply prospectively.
3. Implement all-in quote buys, base sells, base/quote fees, supported third-token costs, per-child fixed fees, rounding and residuals using Decimal and per-venue/per-currency ledgers. Unknown conversion/fees/limits must remain unknown.
4. Define immutable evaluation inputs and separate input validity, economic result and alert eligibility. Enforce freshness, observation alignment and stream integrity before eligibility.
5. Hash canonical complete prices, quantities, sequence/epoch, instrument metadata, timing needed for decisions, fees, thresholds, inventory/scenario inputs, schema/kernel version and canonical output. Exclude runtime timing noise. Change the kernel/schema version when the recorded semantics change.
6. Write hand-derived or independently implemented cases for multi-level depth, zero fees, base fees, fixed fees, boundary rounding, dust, insufficient liquidity, incompatible units, invalid/unknown timing and hash sensitivity. Never derive expected output by invoking the same kernel.

Exit: independent arithmetic and conservation checks pass; changed prices/quantities/configurations change the relevant identity; rejected and unknown inputs cannot produce verified eligible results.

### N02 - Repair the shared live acquisition pipeline

Dependencies: N01.

1. Run one persistent async loop for engine I/O. Create, use, reconnect and close each HTTP/CCXT/WebSocket client on its owning loop. Avoid per-fetch asyncio.run and simultaneous cross-loop use from comparison actions.
2. Declare exact Coinbase and Kraken venue identities, endpoints, supported common spot symbols and metadata. Verify REST/stream equivalence; unsupported markets get clear per-venue results.
3. Parse numeric JSON fields with Decimal/string precision. Implement Kraken's documented CRC32 formatting and truncate to subscribed depth after every update. Test the official snapshot expected checksum 3310070434 independently of the implementation.
4. Validate snapshots and deltas before publishing. Check applicable sequence/connection-epoch rules, checksum mismatch, missing snapshot, duplicate/out-of-order messages and reset/reconnect behavior. Do not invent a sequence rule absent from the venue protocol.
5. On integrity loss, invalidate the book, emit an incident/gap, rebuild from a valid source and only then resume decisions. Record mismatch/failure counts without using corrupted books.
6. Feed opportunities, diagnostics and comparisons from one coherent acquisition/state pipeline. WebSocket helpers must actually drive the production monitor and temporal observations. Disclose provisional REST fallback and its timing limits.
7. Bound queues, reconnect backoff and retained depth. Expose real health/coverage and uncertainty; record failures without leaving the UI in a false healthy state. Rebuild after sleep/wake.

Exit: repeated live acquisitions succeed on both supported connectors using production paths; deterministic reconnect, checksum, depth and liveness fixtures pass; no closed-loop errors, duplicate collectors or stale eligible books. Use bounded scenarios, not a long soak.

### N03 - Complete durable storage, archive and replay contracts

Dependencies: N01 and N02.

1. Audit migrations, WAL/transactions and single-writer ownership. Use an atomic OS-backed writer lock and deterministic ownership/release behavior for simultaneous starts and stale-lock recovery.
2. Persist monitor configuration, fee profiles, alert rules, episodes, incidents, delivery outbox and storage preferences. Recover interrupted intervals explicitly, without deleting or silently replacing existing data.
3. Persist complete initial books, ordered deltas/epochs, instrument metadata and original decision configuration. Commit content-addressed capture manifests atomically and handle missing/corrupt captures honestly.
4. Implement real complete replay export/import from preserved inputs, not reconstructed average fill prices. Exact replay requires input/config/kernel and canonical result equality. Re-evaluation keeps the original event immutable.
5. Retain supported versioned kernels/fixtures. Old incomplete bundles remain inspectable but cannot be relabelled as exact. Unsupported kernels return UNSUPPORTED_VERSION; missing inputs return an explicit incomplete/unknown outcome. No imported executable code.
6. Implement sanitized sharing with declared omitted inputs and affected capabilities. Prevent traversal, excessive size/expansion, secret leakage and corrupt manifests; validate hashes before use.
7. Enforce 7-day diagnostic aggregates, 48-hour rolling raw capture and the default 2 GiB raw quota, with separate pinned quota, safe pruning and visible low-space/full conditions. Quotas and retention settings must affect behavior.

Exit: round-trip replay equals the original canonical result; changed captures/configuration cannot falsely match; migration/restart/crash/import/retention fixtures pass; pinned evidence survives pruning.

### N04 - Complete opportunities, diagnostics and notifications

Dependencies: N02 and N03.

1. Persist eligible, rejected, non-positive and unknown decisions with stable IDs, full reason codes, actual currencies, evidence and bounded retention. Coverage gaps must not disappear from denominators.
2. Drive 500 ms / 1 s / 3 s follow-ups from recorded production observations with sufficient resolution. Hold the original route/amount/settings/scenario fixed. Distinguish continuous, sampled, interrupted and unknown persistence; an empty observation list is not proof of continuity.
3. Bind the assessment and its evidence to stored events and expose it through IPC/CLI. Verify the disappearance-at-250-ms/recovery-at-750-ms case; restored endpoint quotes do not prove uninterrupted persistence.
4. Restore episode/cooldown state on restart. Test ordinary price drift, prospective fee/profile changes, disappearance/closure/reopen, repeated launch and unit-aware escalation against Section 6.3.
5. Connect all specified feed/time/disk/sidecar faults to bounded incident grouping, clean-observation recovery, closure, pin/export and actual offline reproduction. Expose measured distributions, windows, sample counts and unknowns.
6. Implement the durable notification worker: pending/delivering/delivered/failed/suppressed, bounded retries/backpressure, quiet-mode suppression and uncertain restart reconciliation. Distinguish alert intent from actual successful output.
7. Verify actual packaged macOS sound/speech resources and command outcomes; report unavailable/failed delivery visibly. Mocked playback only supplements native checks.

Exit: opportunities and incidents originate in real production services; temporal/cooldown/recovery/outbox scenarios pass; recorded exports reproduce actual findings; quiet mode is persistent and changes delivery behavior.

### N05 - Complete the personal cost advisor

Dependencies: N02 and N03.

1. Compare buy quote budgets and sell base quantities with actual symbols/units, venue metadata/fees, coherent depth, precision, limits, VWAP, residuals and rejection/unknown reasons.
2. Compute amount sensitivity grids using the kernel for every supported amount. Keep ineligible entries visible; no hardcoded cheapest venue or USABLE badge.
3. Support per-venue/per-currency user-entered balances and fee overrides. Separate unconstrained estimates from feasible/insufficient/unknown inventory. Model explicitly configured later rebalancing costs without assuming instant transfers.
4. Consume disjoint remaining depth for simultaneous child orders, including repeated children on the same venue; charge each child's fixed fees. Calculate the allocation selected by the slider and expose totals, ledgers and residuals.
5. Describe delayed child orders as future scenarios with uncertainty, not measured savings. Prevent impossible aggregate acquired/sold quantity and incomplete-child totals masquerading as complete.
6. Check buy/sell grids, rounding/fee boundaries, shared-depth exhaustion, multi-venue balances and rebalancing with independent fixtures. The one-BTC / two-80-unit counterexample must reject over-consumption.

Exit: ranking/grid/inventory/split outputs are real, unit-correct, reproducible and conserved; GUI and CLI consume the same advisor results.

### N06 - Finish desktop, CLI, IPC and native lifecycle

Dependencies: N04 and N05.

1. Keep the existing Dashboard 3/2/8 and brand assets. Wire all five destinations to the shared engine; remove hardcoded production metrics, conclusions, stub buttons and fake success states.
2. Overview configures venues, market, budget/units, fee profiles and alert rules; start/pause/resume/stop and prospective updates use actual acknowledged engine state. Show real coverage and errors.
3. Opportunities support filter/detail/original replay/config comparison and export. Diagnostics show live measurements, incident lifecycle, pin/export/reproduction. Cost Comparison connects editable fees, real grid/inventory/rebalancing/split scenarios.
4. Settings persist retention/quota, notification/quiet options, formatting, import/export and opt-in login startup. Every enabled action performs its promised operation and survives tab changes and app restart.
5. Native mode must never switch automatically to fixtures on an error. Separate explicitly selected demo state from disconnected/error/partial states, and make status/data provenance atomic. Keep recorded real evidence available offline. Reject invalid configuration rather than returning invented results.
6. Define and validate typed/versioned/bounded IPC requests, responses and events. Preserve decimal strings. Handle timeouts, late results, cancellation and recovery without freezing the WebView or leaking pending requests. Concurrent comparisons and monitor updates use safe storage/I/O ownership.
7. Complete supported headless monitor/export/import/replay/diagnostics/cost CLI actions with help, exit codes and identical domain behavior. Do not retain competing prototype paths that bypass repaired contracts.
8. Test both themes and 320/768/1024/1440 widths, keyboard/focus/labels/zoom/reduced motion. Use Lucide, semantic HTML, readable contrast, proper units and the owner's supplied UI rules.
9. Verify native cold launch, single instance, pause/resume, settings reload, sidecar failure/recovery, sleep/wake, actual notifications, upgrade/data migration and clean quit with no orphan process. Use the installed app, not a direct sidecar invocation as a substitute.

Exit: complete first-launch -> configure -> real monitor -> inspect -> change profile -> replay original -> compare/split -> export/import -> pause -> quit/relaunch journey on the actual desktop app; CLI parity and explicit demo/error behavior proven.

### N07 - Repair automated gates and perform bounded product validation

Dependencies: N06.

1. Pin Python runtime/dev dependencies with hashes and transitive/native inputs; preserve npm/Cargo locks and architecture-specific build provenance. Verify fresh environment setup outside the synced development venv as needed.
2. Fix offline/live/native/release verifiers. Fail on missing checks, required skips, unsupported environment, incomplete scenarios, zero usable live data, signature/notarization failures and source mismatch. A manifest with no required artifacts must fail.
3. The live verifier must execute its declared scenarios using production services, not issue one request and echo a requested duration. Keep fixture, live, browser, native and package evidence distinct.
4. The native verifier must drive the real installed shell and user actions, not substitute a bundled sidecar ping. Collect version/process/state/error and artifact identity without relying on screenshots alone.
5. Replace R12 formal soak gating with bounded scenario checks: multiple live cycles per venue, start/pause/resume/stop, recoverable disconnect/reconnect, sidecar stop/recovery, persisted restart, safe invalid data, archive/queue/resource bounds and clean shutdown. Exercise at least 10 completed live acquisition cycles per connector and 100 deterministic production-service cycles for leak/queue/retention boundaries. Scenario results and valid data determine acceptance, not a mandatory elapsed duration.
6. Missing network or a venue outage is an explicit environmental limitation, not a green result. Continue independent deterministic work; verify live scenarios when usable data is available. Profitable real opportunities are not required.
7. Include adversarial tests for the verifier itself: all venue samples failing, prematurely terminated scenarios, disabled required paths, empty manifests, mismatched artifacts and synthetic data offered as native/live evidence must return nonzero.
8. Run clean type/lint/unit/integration/replay/IPC/UI/build checks, then authorized candidate CI at the same source identity. Repair workflow input/architecture/build order, runner compatibility and Tauri bundling. Do not use existing generated binaries to hide a failed rebuild.

Exit: all required deterministic and bounded real-product scenarios have applicable evidence; faulty or missing prerequisites cannot pass a gate; no 24-hour or fixed long-duration run is required.

### N08 - Build, sign, install and audit the release

Dependencies: N07; signing/host/remote prerequisites may be prepared earlier without blocking independent coding.

1. Freeze one clean committed source, runtime/config/locks/schema/kernel/app ID/version and manifest after functional repairs. Build separate arm64 and x86_64 app/DMG assets from that source with matching Python/native wheels and Rust target.
2. Select one coherent packaging path. Reuse PyInstaller onefile if it meets the runtime contract; do not force a rewrite solely because earlier documentation mentioned onedir. Tauri configuration, resource paths, CLI architecture names and release workflow must agree.
3. Implement actual Developer ID nested signing and hardened-runtime options, accepted notarization, stapling and Gatekeeper checks. The presence of a certificate secret or a log message is not signing. Ad hoc artifacts remain development intermediates.
4. Use existing securely stored, owner-designated credentials only within recorded authorization. Do not ask for secret values in chat or purchase/enroll accounts. Finish all independent preparation before presenting an external prerequisite.
5. Test quarantined clean-user installation and the native functional journey without developer Python/Node/Rust. Validate both declared architectures and minimum supported macOS; cross-compilation/Rosetta/newer-host checks are scoped evidence, not proof of unavailable native hosts. No Intel hour-long run is needed.
6. Verify upgrade/settings/events preservation, manual installation/update/uninstallation, resources/CA certificates and offline recorded evidence. Runtime artifacts must have no enabled test server or fake IPC.
7. Deliver exact corresponding source, dependency/license notices, checksums, aggregate manifest, accurate privacy/support/install documentation and truthful release notes. Update README to delivered behavior and remove obsolete readiness claims after preserving history.
8. Complete the R01-R15 matrix with current candidate/config/artifact bindings and all F01-F08 resolutions. Use independent review when explicitly authorized and available; never invent reviewer results. Otherwise record a separate critical review pass and its limits.
9. Set PUBLIC_RELEASE_READY only after all required rows and channel checks are proven. If trusted user authorization covers publication, journal/reconcile existing tags/releases, publish verified assets once and check remote download hashes; otherwise present the concrete target/version/assets/hashes and any final authorization needed. Never publish the old known-broken candidate or silently replace an existing version.

Exit: complete implemented product and installable, signed/notarized distribution with verified source correspondence and native results. PUBLISHED additionally requires real authorized remote assets and matching downloaded hashes.

### Task dependency summary

| Task | Dependencies | Primary output |
|---|---|---|
| N00 | None | Reconciled baseline, cancellation, defect/feature map |
| N01 | N00 | Correct kernel, validity states, complete hashes |
| N02 | N01 | Persistent production acquisition and integrity |
| N03 | N01, N02 | Durable state, captures, complete replay/import |
| N04 | N02, N03 | Opportunity/follow-up/diagnostics/notification workflows |
| N05 | N02, N03 | Real cost/grid/inventory/rebalancing/split advisor |
| N06 | N04, N05 | Complete GUI/CLI/IPC/native journeys |
| N07 | N06 | Honest automated and bounded product validation |
| N08 | N07 | Frozen distribution, installation and final audit |

## 11. Revised mandatory acceptance matrix

Only evidence applicable to the repaired candidate can prove a row. The numerical counts from the review are baseline evidence, not required counts to manufacture or a substitute for coverage.

| ID | Requirement | Minimum direct proof |
|---|---|---|
| R01 | Input/time/config/cooldown correctness | Invalid/non-finite/unit/time fixtures; prospective settings; restart-restored cooldown/quiet behavior |
| R02 | Calculation and conservation | Independent buy/sell/base/quote/fixed-fee/depth/rounding/residual ledgers; repeated-child depth exhaustion |
| R03 | Two real public spot connectors | Actual metadata and repeated production REST/WS acquisition; exact venue identity, subscribed depth, official checksum and reconnect/invalidation |
| R04 | Durable capture/recovery | Atomic writes, migration/kill/restart/lock/retention/disk fixtures; original inputs survive |
| R05 | Complete opportunities and replay | Real event capture; fixed-scenario 500 ms/1 s/3 s assessments with unknown coverage; exact canonical replay; config comparison, complete/sanitized imports and version limits |
| R06 | Complete diagnostics | Measured distributions/counts/windows; induced fault -> grouping -> recovery/closure -> pin/export -> real offline reproduction |
| R07 | Complete cost advisor | Real buy/sell grid, editable fees, venue/currency balances, inventory/rebalancing and split conservation |
| R08 | Complete consumer UI | Every enabled control works; themes/widths/accessibility; atomic real/demo/error provenance; persistent settings and native full journey |
| R09 | Native lifecycle | Installed shell start/quit/single-instance, sidecar recovery, repeated acquisition, pause/resume, sleep/wake, real notification outcomes |
| R10 | Privacy/security | Minimal CSP/capabilities, command and public-host scope, bounded safe imports/exports, no telemetry/trading/secret leakage, dependency/license review |
| R11 | Reproducible automated checks | Locked fresh setup, lint/type/unit/integration/replay/IPC/UI/build, verifier-negative cases and authorized exact-candidate CI; no required skip |
| R12 | Bounded operational correctness | Completed N07 real repeated-acquisition and deterministic resource/recovery scenarios; no fixed-duration soak or long wait |
| R13 | Installable compatibility | Declared minimum macOS and arm64/x86_64 native install/journey evidence; no developer runtime; upgrade preservation |
| R14 | GitHub distribution readiness | Developer ID, accepted notarization, stapling/Gatekeeper, quarantined clean-user install; verified required assets and exact matching source/notices |
| R15 | Final current audit | Every active N task and R row justified; F01-F08 resolved; candidate/config/runtime/assets bound; honest docs and no unresolved release blocker |

Real profitable events are unnecessary. Label synthetic positive fixtures explicitly; estimates and replay do not prove fills or trading profitability. R12's original 24-hour requirement was removed by the owner, not completed or passed. Historical extra R16-R19 rows may be retained with scope/applicability notes, but they do not create new fixed-duration release gates or override R01-R15.

## 12. Commands, evidence and validation workflow

Inspect help/options and actual prerequisites before running a command. Implement missing contracts; do not report them as already available. Preserve output under a new verification ID rather than overwriting a historical report.

### 12.1 Setup and development checks

Target reproducible setup (create the missing locks during N07):

```sh
python3.12 -m venv .venv
.venv/bin/python -m pip install --require-hashes -r requirements-dev.lock
.venv/bin/python -m pip install --no-deps -e .
npm --prefix desktop ci
```

The current .venv symlink is an existing working environment; do not blindly recreate it. Use a fresh isolated environment for reproducibility verification and record its path/tool inputs.

Representative validation:

```sh
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m pytest tests/unit tests/integration tests/replay -q
npm --prefix desktop run typecheck
npm --prefix desktop run test
npm --prefix desktop run test:e2e
npm --prefix desktop run build
.venv/bin/python scripts/verify.py --gate offline --output .agent/evidence/<new-id>/offline
.venv/bin/python scripts/verify.py --gate live --output .agent/evidence/<new-id>/live
.venv/bin/python scripts/verify.py --gate native --app /path/to/installed/OhMyCrypto.app --output .agent/evidence/<new-id>/native
.venv/bin/python scripts/release.py prepare --version 1.0.0 --channel github --arch arm64 --output release/candidate
.venv/bin/python scripts/release.py prepare --version 1.0.0 --channel github --arch x86_64 --output release/candidate
.venv/bin/python scripts/release.py aggregate --version 1.0.0 --channel github --output release/candidate
.venv/bin/python scripts/release.py verify --manifest release/candidate/manifest.json
```

Add lint and scenario-selection commands as implemented, document actual supported options and retain original valid interfaces where possible. Do not blindly run prepare twice into a location that destroys the other architecture's files; stage per architecture and aggregate verified assets.

### 12.2 Bounded operational scenarios, replacing the cancelled soak

Run the actual production service/app through repeated public-market acquisitions and the N07 lifecycle/recovery/resource scenarios. Use explicit scenario completion, bounded attempt budgets and usable observations. At least 10 completed live cycles per supported connector and 100 deterministic service cycles cover recurrence and bounded-resource behavior; these counts do not establish long-term reliability. Retry an environmental failure explicitly, without silently stretching it into a long job or counting failed/unknown data as usable.

No 86400-second command, fixed 24-hour report, fixed Intel 60-minute run or long-duration standby is required. Do not start one. `scripts/soak.py` may be retained as an optional development utility with truthful exit conditions, but it is excluded from required release dependencies and automation. CI may run bounded scenarios; it must not require the owner to wait for a soak.

Keep fault injection deterministic and isolated where possible. Native/browser instrumentation supplements production checks and must be disabled in distributed artifacts. Clock jumps, sleep/wake, disconnect, malformed frames, disk limits and process death need actual appropriate evidence; a test of a parser alone is not an installed-app lifecycle test.

### 12.3 Honest reports and candidate binding

Verifiers return nonzero for failures, required skips, missing checks, invalid artifacts, unsupported environment or incomplete/zero-data scenarios. `passed=true`, a PID, existing files, minimum test counts and unchanged prices alone are insufficient proof.

Each record includes verification/requirement/task IDs, subject commit and dirty manifest if any, source/input/config/runtime/artifact hashes, command/tools/platform/architecture, timestamps/exit status, individual outcomes and explicit coverage/failures/skips/reasons. Keep fixture/live/browser/native/package categories visible. Never manually edit a report's outcome.

Reopen affected gates when source/locks/config/schema/kernel/fixtures/artifacts change. Final acceptance uses a clean frozen candidate. Signing alters artifacts and reopens package/channel checks. The cancelled report remains cancelled regardless of a buggy passed flag; its applicability is superseded by the owner change and cancellation record.

## 13. Autonomous execution and continuity

### 13.1 Preflight

Read rules/guide/prompt/state, Git branch/status/diffs/untracked work. Preserve the upgraded tree via recoverable snapshot or authorized WIP commit before replacement. Default branch prefix codex/. Do not reset/clean/overwrite unrelated work or conceal pre-existing changes in the release candidate.

Channel, style and GPL choices are resolved. Bundle remaining indispensable prerequisites: accurate owner/support identity, both native architecture/test hosts, public network access, signing/notarization secret references and any necessary spending budget. Ask for availability/references, not secret values. Continue independent work while dependent paths wait. Do not ask whether to continue ordinary authorized development, fixes, tests or packaging.

Check Python/Node/Rust/tools, using project-local environments and pinned versions. Do not alter system security, install privileged services, enroll accounts or purchase resources as a workaround. Verify blockers from current state, not old handoff prose.

### 13.2 Canonical state

Reconcile the existing `.agent/EXECUTION_STATE.json`; preserve history and do not initialize over it. This guide owns requirements/task definitions. State owns progress, applicability, budgets, decisions, authorization, jobs and retries. HANDOFF.md is a replaceable generated summary, not a second task database.

Initialization schema example:

```json
{
  "schema_version": 1,
  "project_id": "OhMyCrypto",
  "spec_version": "1.1.0",
  "spec_hash": "sha256-of-guide",
  "run_id": "uuid",
  "generation": 0,
  "candidate": {"commit": null, "tree_hash": null, "config_hash": null},
  "decisions": {
    "channel": "github_macos",
    "design_dials": {"variance": 3, "motion": 2, "density": 8},
    "license": "GPL-3.0-only"
  },
  "authorization": {"local_implementation": false, "remote_candidate_writes": false, "signing_notarization": null, "publish": null, "paid_spend_limit": 0},
  "budget": {"project_token_limit": null, "tokens_used": null, "money_spent": 0},
  "tasks": [],
  "requirements": {},
  "prerequisites": [],
  "active_jobs": [],
  "retry_lineage": [],
  "evidence_index": [],
  "completion": "NOT_STARTED"
}
```

This is an example, not current state or an authorization grant. On the implementation session, record the source instruction before setting local implementation true. Publication/spending are separate.

The remote_candidate_writes field defaults false. If the owner explicitly authorizes a dedicated codex/ branch and draft PR in JeremyL691/OhMyCrypto, record that source and enable only those operations; never infer merge/public-release permission. R11 must either use that authorized candidate CI or remain unproven until remote access is authorized and exercised.

Populate active N00-N08 with section 10 dependencies and the revised R01-R15 with evidence references. Preserve T00-T18 in task history, with T18 owner-cancelled. No historical done flag can dispatch completion of a new task. Lifecycle: pending -> in_progress -> verifying -> done, plus blocked and owner-approved cancelled. Required cancelled tasks still block completion until a specification change reconciles scope. done needs applicable proof.

Atomic writes with generation checks; only lead updates shared status. Require one active lead lease with owner/session, expiry and verified liveness; stale leases need reconciliation before takeover. Atomically reserve task/logical invocation before dispatch and immediately recheck candidate, prerequisites, authorization and budgets. A lead restart must reconcile reserved work and real handles before new dispatch. Delegates submit artifacts/findings with subject hashes and isolated ownership. Reject stale updates. Checkpoint at milestones, dispatch/completion, external actions and every 15 minutes. Keep backups and validate schema/DAG.

### 13.3 Work loop

1. Reconcile source/state/authorization/evidence and actual live jobs.
2. Resume reconciled in_progress/verifying work before selecting new pending tasks with done dependencies. Reopen a blocked task only after verifying its prerequisite changed; continue independent eligible work around remaining blockers.
3. Implement a coherent slice advancing the full task.
4. Run checks with independent expectations, preserve output, fix failures and rerun affected checks.
5. Perform critical integration/release review, using independent reviewers when the host/user authorizes delegation; resolve and verify findings. Do not describe self-review as independent.
6. Checkpoint state/handoff and continue without routine approval requests.
7. Audit every original requirement before completing the goal.

Persist failure signature/hypothesis/remedy/result/next step. After three equivalent failures change approach or isolate the external condition; agent changes never reset retries. Stop only dependent work. When nothing eligible remains request the smallest indispensable input and preserve the full objective.

Separate host_limit from persistent project_budget. Runtime switches do not reset spend, retries, authorization, pauses or evidence. No token limit is assumed here; unknown telemetry stays unknown. Honor explicit limits supplied later.

### 13.4 Long jobs and recovery

Job records require task ID, stable logical invocation ID, candidate/config, command, PID/tool/session, process-start identity, state, last verified liveness time, output location, retry/failure class, next eligible retry time and final artifact reference. Register reservation before invocation, then actual handle. Marker files and commentary are not liveness evidence. On observation timeout inspect the same handle; never restart a possibly active build/notarization merely because polling timed out.

Use bounded waits and meaningful updates. Supported goal continuation may keep the agent working, but a prompt cannot wake an exited process, collect through host sleep or bypass limits. Cross-session continuation needs a real supported scheduler/supervisor plus shared files/Git. Create automation only with explicit authorization; otherwise record the missing host capability and retain resumable state.

Resume from state/handoff plus actual Git/source/job/external-action inspection. Revalidate spec/config, reopen invalid evidence and continue the next eligible action. Never trust handoff prose alone.

### 13.5 External-action journal

Before non-idempotent operations append unique action ID, operation/destination, subject hashes, authorization reference, expected result and prepared state to actions.jsonl. Store request/result IDs. Uncertain outcomes require reconciliation at the original destination before retry. Apply to notarization, tags, releases and uploads.

Journal states are prepared -> submitted -> confirmed, with failed/uncertain outcomes. Preserve the same logical action ID for retry/reconciliation; record attempt IDs separately. A new ID cannot hide an unresolved prior submission. Credential presence alone is not action authorization: owner-designated signing/notarization use must be recorded for the frozen candidate before submission. Publication and main-branch merge remain separately scoped.

Local checks/build retries need no repeated approval. Publication/credentials/spend stay within supplied authorization. No unsolicited email or external messaging is part of implementation.

## 14. GitHub macOS release

Build separate aarch64-apple-darwin and x86_64-apple-darwin artifacts. Shell/interpreter/sidecar/native wheels must match; Rust target selection alone cannot convert Python architecture. Use native compatible builders/test hosts and record minimum OS/library compatibility. A newer host does not prove macOS 13 support.

Freeze source commit, settings/locks, schemas, app ID/version and input manifest. Bundle the verified Python sidecar resources/entry using current Tauri contracts, retaining onefile if it satisfies the installed runtime and signing requirements. Verify hidden imports, CA certificates, paths, permissions and process lifecycle. Sign nested code with correct identity/hardened-runtime configuration; changes to signed contents require verification again.

Implement repeatable prepare/build/sign/notarize/staple/verify. Keep credential references secure. Require signatures, accepted notarization, stapled ticket, Gatekeeper and quarantined clean-user installation without developer tools. Disabling Gatekeeper is not the consumer installation path.

Deliver app/DMG per architecture, checksums, source/version manifest, GPL corresponding source, notices, actual owner privacy/support information, truthful release notes, installation/uninstallation and migration instructions. Pinned inputs/provenance support reproducibility; signing can change bytes, so do not claim bit-identical signed outputs without evidence.

Installed app opens offline for saved/demo evidence with network limitations visible. Verify upgrade preserves settings/events. Automatic updater is not required in v1; verified manual replacement and schema migration are required. Start-at-login is opt-in; uninstall explains retained data.

Publication requires explicit destination/version/artifact authorization; local preparation continues without it. If authorized later, journal/reconcile existing tags/releases, upload verified assets once, inspect remote version/links and verify hashes. Never silently replace a published version. Attach any created implementation PR when required by host tools.

## 15. Completion review and final audit

Review actual source, runtime, installed app and reports rather than trusting the implementing agent's checklist. Where authorized tools allow independent agents, use reviewers for product coverage, technical correctness and release/evidence. A separate self-review is useful but must not be described as independent review. No review is already passed for the repaired candidate.

Final audit:

1. Re-read the owner's revised scope: full product completion; cancelled T18; no fixed-duration soak.
2. Enumerate N00-N08, R01-R15 and F01-F08 with source/tests/scenarios/artifact evidence.
3. Inspect the frozen source, dependencies/settings, production runtime, native journeys, CI and exact signed/notarized files.
4. Classify each requirement as proven, contradicted, incomplete, indirect or missing. Only directly applicable evidence proves completion.
5. Resolve findings, reopen dependent checks and rerun them. Preserve historical reports; do not replace evidence with documentation claims.
6. Confirm that all enabled UI/CLI actions work, demo data never masquerades as real, scenarios finish honestly, and the cancelled task cannot be resumed by an automatic completion rule.
7. Produce a final feature/requirement matrix, candidate/runtime/assets/checksums, platforms/install outcomes and remaining limits. No long-run reliability claim follows from bounded scenarios.
8. Set PUBLIC_RELEASE_READY only after complete product and selected-channel checks. PUBLISHED requires authorized actual remote release verification. If a real external prerequisite remains, report it precisely and keep the work resumable; finish all independent work first.

## 16. Documentation and handoff hygiene

Keep three entry documents: README for delivered behavior and user installation; this guide for the active specification and development order; AGENT_PROMPT for copyable execution instructions. Execution state owns progress, jobs, authorization, budget, retry lineage and evidence applicability. HANDOFF is a generated current summary, not another specification.

Update README when the repaired behavior is proven; until then describe the development state honestly. Include necessary license/privacy/support/security/install material for the actual distribution. Remove stale zero-defect/release-ready claims from current summaries without deleting original historical records. Do not create a second conflicting completion roadmap.

The current state must keep T18 cancelled and the owner change recorded across restarts. Preserve original task/evidence history and existing authorization/budgets. A report emitted after cancellation cannot turn a cancelled task into a passed release gate.

## 17. Primary references

Recheck current locked-version documentation at N00/N02/N08 and packaging. References inform design, not this project's gate results. Never blindly execute examples or expose credentials.

- [CCXT manual](https://github.com/ccxt/ccxt/wiki/manual): markets, timestamp caveats, fees, precision, limits and rates.
- [Tauri external binaries](https://v2.tauri.app/develop/sidecar/): naming/configuration/process integration.
- [Tauri macOS signing](https://v2.tauri.app/distribute/sign/macos/): identity, notarization and distribution constraints.
- [Tauri WebDriver](https://v2.tauri.app/develop/tests/webdriver/): current native/service vs browser mock testing routes.
- [Kraken book checksum](https://docs.kraken.com/exchange/guides/websockets/book-checksum-v2): exact decimal parsing, subscribed depth and checksum coverage.
- [PyInstaller operating model](https://pyinstaller.org/en/stable/operating-mode.html): runtime bundling, platform builds and hidden imports.
- [GNU GPL version 3](https://www.gnu.org/licenses/gpl-3.0.html): full license and distribution requirements.
- [GNU licensing how-to](https://www.gnu.org/licenses/gpl-howto.en.html): copyright and license notices.
- [Hummingbot arbitrage executor](https://hummingbot.org/strategies/v2-strategies/executors/arbitrage-executor/): mature existing functionality; execution alone is not validated differentiation.
- [HftBacktest fill limitations](https://hftbacktest.readthedocs.io/en/v1.8.4/order_fill.html): historical replay does not alter markets or prove fills.

The product hypothesis combines inspectable opportunities, reproducible feed diagnostics and user-specific costs. Validate usefulness through actual workflows and records; never market a unique algorithm or guaranteed profit without proof.
