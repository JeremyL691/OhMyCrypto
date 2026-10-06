# OhMyCrypto Project Execution Guide

Specification version: 1.2.0

Prepared: October 6, 2026, America/Los_Angeles

Status: **IN_PROGRESS / NOT RELEASE READY**. This is the authoritative goal-driven remediation and release plan. Writing this plan does not repair or validate the product.

## 1. Objective, authority and fixed decisions

Deliver an installable local-first macOS application whose three promised capabilities work through the actual packaged production path: opportunity inspection and original replay; feed diagnostics and offline incident reproduction; and personal buy/sell cost, inventory and split scenarios. Complete the code, integration, recovery, user journeys and distribution verification so that the remaining release step is an explicitly authorized upload of already verified assets.

This revision replaces specification 1.1.0's active N00-N08 plan following the October 6 audit. Sections 3-9 remain the product contract. Section 10 defines active goals G00-G12; Sections 11-12 define regression, user-journey and release gates. There is no second roadmap. State records progress; this guide defines completion.

| Fixed decision | Value |
|---|---|
| Product | All three capabilities in one app, pipeline, kernel and store |
| Channel | JeremyL691/OhMyCrypto GitHub Releases |
| Platforms | macOS 13+, separate arm64 and x86_64 assets and native evidence |
| Runtime | Python 3.12, React/TypeScript/Vite, Tauri 2 |
| UI | Dashboard: DESIGN_VARIANCE=3, MOTION_INTENSITY=2, VISUAL_DENSITY=8; preserve brand and both themes |
| License | GPL-3.0-only with exact corresponding source and notices |
| Scope limits | Public spot data, local storage, no trades/transfers/custody/keys/telemetry/hosted services or paid purchases |

Do not re-ask resolved design/channel/license choices. Do not restart from zero or expand scope. Preserve external development-environment symlinks rather than deleting/recreating them. Platform support cannot be narrowed just to make acceptance green; any indispensable support change needs an explicit owner decision after the limitation is established.

### 1.1 Owner cancellation remains binding

T18 / soak24h_gen13 is owner-cancelled. Preserve `.agent/evidence/plan-revision-20261005/owner-cancellation.json`, the existing cancellation guard, original reports and job history. Never restart it, schedule a replacement long soak, require the old Intel 60-minute window, or wait for a fixed-duration report. R12 uses completed bounded production scenarios, usable observations and measured resource assertions. A 100-cycle counter alone proves neither memory bounds nor recovery. No long-term reliability claim follows from this plan.

### 1.2 Completion states and authorization

- IN_PROGRESS: required repairs or prerequisites remain.
- IMPLEMENTED: code exists, acceptance is incomplete.
- PRODUCT_VALIDATED: required functional, integration, recovery, UX and bounded operational evidence passes.
- ARTIFACT_BUILT: distribution files exist; signing/channel checks may remain.
- PUBLIC_RELEASE_READY: every G00-G12 goal, R01-R15 row and applicable C/J/B scenario is directly proven for the frozen candidate, including genuine signing/notarization and native support checks.
- PUBLISHED: separately authorized remote upload exists and downloaded hashes match the accepted manifest.

Ad hoc signing, green existing tests, source filenames, a sidecar ping, documentation and old done/proven flags cannot advance readiness. An unavailable native host/signing credential/CI permission is an explicit unproven external gate, not a waived one. No claiming PUBLIC_RELEASE_READY while awaiting signing or minimum-OS/native evidence.

The current owner request authorizes this documentation/state revision and an implementation handoff. The successor prompt authorizes local implementation, tests and preparation. Preserve recorded authorization and budgets for remote branch/PR writes, signing/notarization submissions, publication and spending. Credential presence does not grant action permission. Complete independent work and prepare concrete reviewable outputs before requesting any indispensable external authorization. Publication is optional to the development endpoint, and must not be inferred from this plan.

## 2. Current baseline, findings and evidence limits

Review subject: clean `codex/v1-refactor` HEAD `35361dee0fb20d65e3045a007afecdd813ee2cb6`; implementation/artifact candidate `11db10ccb6f7060ed1793600b24e45fa22cdf182`. This planning revision changes documents/state after that baseline. Recheck Git and actual source on resume.

Current audit: [.agent/evidence/plan-revision-20261006/release-review.md](.agent/evidence/plan-revision-20261006/release-review.md). This is a historical review snapshot, not another plan or a passing gate. Prior guide/prompt/state/handoff are saved in that directory; preserve them without adopting their old completion claims.

### 2.1 Directly verified on the reviewed revision

71 Python tests, 7 UI unit tests, 8 browser fixture E2E tests, TypeScript checking and a fresh frontend build passed. Initial localhost/app-data sandbox restrictions were resolved with temporary data and an approved test run; those restrictions were not product defects. The actual MonitoringService completed 10 public REST cycles per connector and stored 10 events. These are scoped successes, not live-WebSocket/recovery/native acceptance.

The packaged sidecar launched without developer Python but its real two-venue cost response failed serialization. Real stored events produced null hashes/empty fills at the UI boundary, and a fresh browser production build crashed opening their replay. Independent original-fee and tampered-manifest probes contradicted exact replay. A stale-book fixture remained eligible; a bad Kraken CRC frame became clean without recovery. Existing artifact checksums matched; selected source files matched the candidate. The archive nevertheless included development environments/builds/nested release artifacts. App signing was ad hoc with no TeamIdentifier; native Intel/minimum-OS/quarantined clean-user evidence was not established.

Read-only remote inspection found main/HEAD at `1058083ad92b23f4e16d7068f9aea1a665209d60`, with no current candidate branch returned. No current-candidate remote CI pass was established. Recheck remote state before relying on this dated observation. Existing PUBLIC_RELEASE_READY was contradicted and is superseded.

### 2.2 Complete known repair inventory

P1 items block the promised product. P2 items also block this release where they violate the selected UX, lifecycle, packaging or retention contract. These groups cover the known audit findings; they do not imply that every possible future bug has been found. New findings discovered by the required scenarios must be added to the same active inventory and resolved before completion.

| Finding | Priority and concrete defect | Production anchors | Goals / regression IDs |
|---|---|---|---|
| A01 | P1: split child FillResult dataclasses make a successful cost request fail JSON serialization, including packaged sidecar | services/cost.py:evaluate_split_order; interfaces/sidecar.py:send_response | G01/G07/G08; C01 |
| A02 | P1: stored flat fills and row hashes disagree with event mapper; real detail/replay opens a blank crashed page | storage/repository.py:save_event; sidecar.py:_event_to_item; ReplayModal.tsx | G01/G04/G09; C02 |
| A03 | P1: original replay substitutes 0.25% fees/metadata; modified fill/config/result evidence can still be exact | opportunity.py:evaluate/replay_bundle; domain/kernel.py | G03/G04; C03-C06 |
| A04 | P1: grid amount keys, split fields and wrapped replay shape differ between Python and TypeScript; stale results/forced overrides/wrong asset labels | cost.py; sidecar.py; ipc.ts; CostComparisonView.tsx; ReplayModal.tsx | G01/G07/G09; C07-C08 |
| A05 | P1: invalid budgets, generic instruments/default fees, stale/misaligned books and permissive Kraken integrity allow misleading usable results | monitor.py:configure/_run_cycle; kernel.py; kraken.py | G01-G03/G07; C09-C14 |
| A06 | P1: follow-ups, episode restoration, durable notification delivery, effective settings, inventory/rebalancing, imports and real CLI/incident reproduction are disconnected or stubbed | opportunity.py; notifications/outbox.py; diagnostics.py; sidecar.py; cli.py; desktop views | G04-G09; C15-C22/C28 |
| A07 | P1: live report echoes duration after one request; native gate substitutes a ping; resource tests lack actual assertions; one arbitrary artifact passes release verification | scripts/verify.py; scripts/release.py:verify_release; test_bounded_scenarios.py | G00/G10-G12; C23/B01-B10 |
| A08 | P1: signing always ad hoc; workflow secret branch only logs; state incorrectly proves R14 and readiness | release.py:sign_and_verify_bundle; release.yml; EXECUTION_STATE.json | G00/G10/G12; C24 |
| A09 | P1: retired/retiring runners; fresh-build/browser prerequisites/order inconsistent; copied per-arch manifests/checksums overwrite each other | ci.yml; release.yml | G10/G12; C25 |
| A10 | P2: 320px navigation extends to x=506.83; clicking Settings scrolls hidden shell by 187px and clips main content despite document width passing | desktop/src/styles.css | G09; C26 |
| A11 | P2: prepare reuses unbound tracked generated binaries; source archive includes venv/build/cache/releases; Python hash locks missing | scripts/release.py; pyproject.toml; tracked build/dist outputs | G10/G12; C27 |
| A12 | P2: native exit has no reviewed respawn; synchronous 120-second requests; stale status and stuck action loading on failure | src-tauri/src/lib.rs; App.tsx; OverviewView.tsx | G01/G08/G09; C28-C29 |
| A13 | P1: diagnostic clean bool is passed as UTC time (closed_at_ms=1); grouped evidence updates are not persisted; active incidents are not restored | monitor.py:307; diagnostics.py:record_clean_observation; repository.py:save_incident | G06; C20 |
| A14 | P2: quota checks current size instead of incoming size (16-byte quota writes 114 bytes); pin quota/age pruning and duplicated database captures need integrated bounds | storage/archives.py:write_capture/prune_old_captures; repository.py:save_event | G04; C21/B07 |

Supplementary inspection also requires protocol conformance cases for Coinbase snapshot/update/connection epochs, malformed frames and bounded retained depth; no production recovery proof was established. REST snapshots cannot simply anchor queued WS deltas without a documented compatible synchronization mechanism. Treat these as required verification gaps under A05/G02, not claims that every live book was corrupt.

Old F01-F08 remain historical regression obligations. Some narrow fixes now work: repeated REST acquisition, price-inclusive hashes, shared split-depth tests, official Kraken number formatting and removal of native fixture fallback. Preserve those improvements and tests. They do not establish the full current workflows or close A01-A14.

### 2.3 Evidence classification

Label assertions as DIRECTLY_REPRODUCED, SOURCE_CONFIRMED, VERIFICATION_GAP, or ENVIRONMENT_LIMIT. Keep synthetic/domain, production-service fixture, live-service, serialized sidecar, browser-contract, installed-native, CI and package evidence distinct. A controlled corrupt frame is not proof of corrupt live traffic. A browser fed real saved data is not a native-shell journey. No live profitable opportunity is required: rejected and unknown records still demonstrate useful truthful behavior.

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

Repair and validate the existing sidecar packaging/start/quit contract early in G01/G02/G08 before final UI acceptance. Use current locked-version documentation for sidecar naming and resources. Do not add hosted services, Redis, Kubernetes, user accounts, a trading bot framework or an LLM to satisfy this release. Reuse mature tools where appropriate without hiding project-specific correctness contracts.

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

Allow finite zero-fee profiles and optional zero thresholds; enforce positive quantities and finite bounded intervals. Verify exchange capability through the supported registry/metadata, not arbitrary `hasattr`. Maintain exact endpoint/venue identity: do not mix Coinbase Advanced Trade metadata with Coinbase Exchange stream data without verified equivalence. The initial release supports two declared public spot connectors; register their current venue IDs and common supported symbols during G02. Additional unsupported venues get clear results, not fictional support.

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

Check the testing routes actually supported by the locked Tauri/macOS versions early. Do not assume macOS support for tauri-driver or a test service without checking official documentation and running it. Instrumented native test builds supplement platform accessibility/automation checks on the exact signed production app. Production artifacts must contain no enabled test server or mock IPC. Test first launch -> configure -> start -> inspect -> change fee/profile -> replay original unchanged -> pause -> restart with saved settings.

## 9. Privacy, security and licensing

All state stays local; no telemetry or automatic upload in v1. Provide Complete Replay and Sanitized Share exports. Complete Replay keeps every decision input, including necessary inventory, while removing unrelated private metadata. Sanitized Share may omit inputs but declares omissions and affected reproduction claims in its manifest; affected results are UNKNOWN and original exact replay is unavailable. Never invent missing balances. Preview shows removed capabilities; preserve the original local event unchanged. Credentials never appear in logs, state, screenshots or fixtures.

Allowlist public exchange hosts and sidecar commands. Validate imported archives for size/expansion, traversal, schema and hashes. Exchange/import strings are data, not HTML or instructions. Reject unsafe paths and decompression bombs. Use CSP and minimum Tauri capabilities; no arbitrary remote navigation in the privileged view.

Choose a stable application identifier before signing; preserve data paths across upgrades. Add the official full GPL-3.0-only text, accurate copyright ownership, dependency notices and provenance during implementation. Check distribution compatibility for Python, native wheels, Tauri, UI dependencies and PyInstaller's bootloader exception. Do not invent legal/support identities.

Each binary release includes access to its exact corresponding source: application, build/configuration scripts, locks, patches and instructions. Include a source archive or verified matching tag with hash correspondence; unrelated current main is insufficient. Preserve applicable source/binary notices. Do not introduce incompatible bundled components and obscure their license obligations.

Signing credentials stay in keychain/CI secrets; state stores reference names/availability only. Enrollment, paid data, runners and hosting need explicit budgets. Public API access does not establish unrestricted raw-data redistribution rights. Check connector terms before sharing captured samples; use synthetic/sanitized fixtures when real samples are not shareable.


## 10. Goal-driven development plan

G00-G12 are the active goals. N00-N08/T00-T18 and their reports are historical; T18 stays cancelled. A goal is done only when its stated exit behavior is verified through the named production boundary. A source file, test name or checklist is not proof. Preparatory work can begin early, but dependencies must be proven before final acceptance.

### G00 - Make completion claims enforceable and reproduce the failures

Dependencies: none. Findings: A01-A14, especially A07/A08. Requirements: R11/R15.

**Outcome:** the successor starts from a truthful baseline and cannot mark a missing scenario green.

- Reconcile Git, guide hash, state generation, existing processes/jobs, cancellation, authorization/budgets and remote state. Preserve snapshots/retry history; supersede old readiness and N-task passes.
- Create an implementation inventory mapping every control/CLI action in Sections 3-9 to request schema, service, stored record and acceptance scenario. Identify missing callers and fake/stub outputs, including `pending_storage` and unconditional REPRODUCED. One active backlog includes newly discovered defects.
- Introduce a scenario result contract with PASS/FAIL/UNKNOWN/NOT_RUN, evidence class, applicability and source identity. Required UNKNOWN/NOT_RUN blocks completion. Begin verifier-negative tests here; do not postpone honesty until packaging.
- Reproduce C01-C29's applicable reviewed failures before fixing them, using production inputs and independent expectations. Preserve raw baseline outputs. Already repaired historical F cases must remain green rather than be deliberately broken.
- Check host/signing/remote/support prerequisites early and record accurate availability/references. Prepare blocked paths without stopping independent local work. Do not submit or request secrets in chat.

**Exit:** review baseline and coverage inventory saved; meaningful red regression evidence exists for current defects; cancellation preserved; status is IN_PROGRESS and every future acceptance claim has a named scenario.

### G01 - Make every financial request and response a validated contract

Dependencies: G00. Findings: A01/A02/A04/A05/A12. Requirements: R01/R08/R10/R11.

**Outcome:** valid real data survives Python -> JSONL -> Rust -> TypeScript -> rendered UI, and invalid requests make no partial state changes.

- Define versioned request/response/event schemas for lifecycle, configuration, event/detail, original replay, changed-config replay, diagnostics, cost/grid/split/inventory, settings and import/export. Use explicit nested DTOs rather than raw dataclasses or `any`. Prefer one schema source and generated/checked bindings over divergent handwritten shapes.
- Specify decimal-string normalization, actual currencies/units, optional/unknown fields, provenance, structured errors, request IDs and version negotiation. Use rows with explicit amount/units for grids or one canonical key format. Contract errors remain visible and bounded.
- Fix nested FillResult serialization, row-hash mapping, full filled-level/ledger DTOs, wrapped replay responses and split totals together. Existing incomplete records get explicit legacy/incomplete labels without fabricated fills/hashes.
- Validate types, enums, permitted venues/spot symbols, finite positive amounts, bounded split ratios/delays/limits, bool-as-number, settings keys and payload/response sizes. Validate the entire configuration/settings update before applying or persisting it transactionally. Failed changes leave active configuration unchanged.
- Keep mock data explicitly selected and visibly labeled. Real native errors never yield synthetic financial results. Track request/config generation so late results cannot replace newer data.

**Exit:** C01/C02/C07-C09 pass through serialized production handlers; schema-invalid input is rejected with a useful error and no partial writes; production outputs render without shape exceptions. UI consumers cannot assume missing values are valid numbers/hashes.

### G02 - Establish trustworthy live books and connector recovery

Dependencies: G01. Findings: A05. Requirements: R01/R03/R06/R09.

**Outcome:** all three capabilities share one correctly owned acquisition pipeline and only synchronized, appropriately timed books can support eligibility.

- Maintain one persistent async I/O owner for REST/CCXT/WS clients. Route concurrent monitor/comparison work through it. Close/cancel futures and clients on that loop; join old workers before restarting. Prevent duplicate collectors and late results from prior configuration/session epochs.
- Load actual per-venue market identifiers, base/quote, precision modes/increments and minimums. Verify exact Coinbase/Kraken public endpoint equivalence and supported common markets; unsupported inputs produce per-venue reasons.
- Parse raw decimal tokens exactly; validate complete snapshots/updates, malformed types/non-finite/negative sizes, zero deletion, duplicates/order and subscribed depth. A skipped bad frame is a finding/coverage gap, not a clean observation.
- Enforce Kraken checksum for snapshots and deltas before publishing. Preserve official 3310070434 fixture. Bad CRC immediately invalidates the book, records degradation, and stops eligible use until a valid rebuilt stream baseline/recovery is proven. Clean publication must not erase an unresolved integrity failure. Top-ten CRC does not prove deeper levels.
- Specify and test Coinbase's actual channel/sequence semantics from current official schema. Require a snapshot per connection epoch before updates; detect applicable gaps/order violations. Manage heartbeat subscription/liveness without treating unrelated traffic as refreshed depth. Bound retained depth without silently losing needed state when previously truncated levels should re-enter; invalidate/rebuild if bounded storage prevents correct reconstruction.
- On reconnect/sleep/gap, clear invalid state and obtain a compatible baseline; do not mix an unanchored REST snapshot with queued WS deltas. REST fallback has its own timing bounds and remains provisional where coherence cannot be established.
- Record local receipt/request intervals, source-time meanings, monotonic/UTC clocks, epochs, coverage and actual usable counts. Enforce the Section 5 timing/250ms alignment/1000ms observation rules with an injected deterministic evaluation clock, not hidden wall-clock reads in the kernel.

**Exit:** C10-C14 plus relevant fault scenarios pass; 10 completed usable live production acquisitions per connector include separately identified REST and actual WS evidence, with recoverable disconnect/rebuild demonstrated. Missing/invalid data cannot produce verified eligibility; failures remain visible in denominators. No elapsed-duration gate.

### G03 - Make calculations, assumptions and identities independently correct

Dependencies: G01/G02; independent arithmetic preparation may begin after G01. Findings: A03/A05/A06. Requirements: R01/R02/R05/R07.

**Outcome:** every result has conserved venue/currency ledgers, known assumptions and complete reproducible identity.

- Apply actual instrument metadata and sourced/as-of fee profiles consistently across monitor, cost, split and replay. Public account-specific fees may be unknown; use clearly labeled user overrides or supported sourced tier scenarios. Never silently substitute 0.25%, 0.60% or another rate as the user's actual fee. Preserve fee currency/fixed component/rounding/provenance/expiry through storage.
- Separate input validation, economic result and alert eligibility. Invalid/unknown integrity, timing, fees, limits or required inventory cannot become eligible. A measurable unconstrained cost can still be shown with separately UNKNOWN inventory.
- Implement quote all-in buys, base sells, base/quote proportional and fixed fees, per-child fee rounding, dust/residuals and minimums. Unsupported third-token conversions/cross-quote scenarios remain explicit unknown/unsupported. No order simulation claims actual fills.
- Use immutable complete evaluation inputs: books/levels/epochs, relevant timing/quality evidence, metadata, fee/inventory/scenario assumptions, thresholds/predicate/schema/kernel version. Canonical input/config/result hashes cover each field affecting outcomes and every fill/fee/ledger/reason; exclude only defined runtime noise.
- Add hand-derived or independently implemented oracles for depth, precision modes, boundary budgets, zero fees, base sell fees, fixed fees per child, residual valuation and currency conservation. Never generate expected values by calling the tested kernel.

**Exit:** C03-C06/C10-C14 and independent conservation fixtures pass. Original example fees 0.006/0.004 preserve the original negative result; changing inputs/configuration/timing/metadata/canonical fill data affects the appropriate identity. No full-output tampering passes exactness.

### G04 - Preserve complete evidence safely across export, restart and upgrade

Dependencies: G02/G03. Findings: A02/A03/A06/A14. Requirements: R04/R05/R10/R13.

**Outcome:** original events can be reproduced from complete immutable stored inputs, with truthful legacy support and actual storage bounds.

- Migrate complete event/fill ledgers, original settings, fee provenance/limits/timing/predicate/version, capture manifests and ordered WS windows. Preserve existing data; incomplete older records stay inspectable and cannot be converted into fabricated exact evidence.
- Use a consistent writer owner/transaction model for monitor, IPC, notifications, incidents and settings. Make migrations atomic/recoverable; verify abrupt termination between record/archive commits, cleanup of partial files, simultaneous launch and corrupt DB behavior. Never replace a bad DB silently.
- Original replay uses stored original configuration and supported kernel; an override is a separate explicit re-evaluation. Validate recomputed input/config/version/result hashes and full canonical outputs. Preserve original result and imported provenance; reject corrupt evidence. Unsupported versions/incomplete/sanitized bundles declare exactness unavailable.
- Export/import complete replay and sanitized shares, with a preview of omitted data/capabilities. Validate all hashes, names, sizes/expansion, schemas and versions before durable writes; reject traversal, symlink escapes, arbitrary executable content and partial imports. Treat 64-character lowercase hex content IDs as data with verified paths.
- Apply retention/quota settings to running components and after restart. Reserve incoming bytes before writing; enforce separate raw/pinned quotas and free-space limits. Time-based pruning runs even when below quota. Preserve pinned bundles; expose capture gaps/full conditions and safely stop new capture rather than returning silent empty hashes.
- Bound event/incident/notification records and WAL/temporary files as well as archive JSON. Storing an entire raw capture in each DB row must not bypass raw quotas. Keep referenced capture availability/corruption explicit after pruning.

**Exit:** C02-C06/C17/C21/C22 pass; two original replay runs have the same canonical result; imports into a fresh offline store reproduce originals or show precise unavailable reasons. Restart/upgrade preserve settings and evidence; boundary/oversize/pinned/age/disk tests enforce actual byte and record limits.

### G05 - Complete opportunity persistence, episodes and notification delivery

Dependencies: G04. Findings: A06. Requirements: R01/R05/R09/R12.

**Outcome:** the production monitor creates inspectable eligible/rejected/unknown decisions, recorded temporal assessments and honest durable delivery outcomes.

- Persist decision/reason/coverage counts even when a venue is absent. Sample or aggregate bounded rejected records without losing denominators. Store actual route/amount/config assumptions and distinguish configured routes from discovered routes.
- Schedule 500ms/1s/3s assessments against sufficiently resolved production observations, holding initial scenario/config fixed. Record requested/actual offsets, delay, observed endpoint result, coverage gaps and continuous persistence separately. Empty observations or slow polling yield UNKNOWN, never continuous.
- Exercise disappear-at-250ms/return-at-750ms and gap cases. Returning positive at 1s does not prove uninterrupted eligibility. Replay temporal outcomes from the same recorded history using local receive order, with no future data leakage.
- Restore active episodes/cooldown on initialization, persist close/reopen and prospective config changes, and enforce absolute AND relative unit-aware escalation. Restart within 30 seconds cannot reset alert eligibility.
- Connect eligible intent to SQLite-backed outbox and one bounded worker. Persist pending/delivering/delivered/failed/suppressed/uncertain states, attempts, deadlines, queue limits and errors. Reconcile abrupt termination without asserting exactly-once playback. Quiet mode actually suppresses emission; unavailable resources/timeouts/nonzero subprocess exit become visible failures.
- Invoke real packaged sound/speech resources where enabled, and keep scheduled intent separate from successful macOS command outcome.

**Exit:** C15-C18 and J02/J08 pass through production service -> store -> IPC/native UI/CLI. Follow-up fields contain recorded results/reasons, no unexplained null placeholders; restarted cooldown/outbox works; quiet and failed delivery never become delivered.

### G06 - Complete diagnostic investigation and honest offline reproduction

Dependencies: G02/G04. Findings: A06/A13. Requirements: R06/R09/R12.

**Outcome:** actual connector/storage/time faults create retained incidents that group, recover and reproduce from their exported evidence.

- Wire malformed/integrity/sequence/liveness/latency/timeout/rate-limit/reconnect/clock/storage/sidecar faults into the versioned rule registry. Apply minimum sample/window thresholds rather than opening every failure unconditionally. Recovery requires a valid rebuilt book and the configured clean observations.
- Fix bool-as-UTC call and reject malformed timestamps. Persist grouped evidence/counts/last-seen/recovery state atomically, with bounded pre/post windows and disclosed gaps. Restore active incidents and collision-safe IDs after restart.
- Bound latency windows/evidence buffers and expose actual periods, sample sizes/denominators/quantile definitions and uncertainty. No samples means UNKNOWN, not zero latency. Keep source age, retrieval duration, channel liveness and validated-book availability distinct.
- Export sufficient original raw/control/time inputs, adapter/rule versions and recovery events for each supported fault class. Reproduction must rerun the actual detector against that evidence and compare its finding, with no network requirement.
- Empty/contradictory/tampered inputs return NOT_REPRODUCED, INCOMPLETE or UNSUPPORTED with non-success exit semantics; never unconditional REPRODUCED. Pin/export/reproduction commands work in both desktop and CLI.

**Exit:** C19/C20 and J03 pass; a two-fault grouped incident exports both bounded samples and correct counts, survives restart, closes at a plausible UTC after opening, and reproduces its rule offline. Every mandatory fault class has an applicable result and negative reproduction control.

### G07 - Complete the user's cost, balance and split decisions

Dependencies: G02/G03/G04. Findings: A01/A04/A05/A06. Requirements: R02/R07.

**Outcome:** buy/sell comparison, amount grid, inventory and split controls calculate the actual chosen scenario and expose limits/unknowns.

- Feed comparison from shared coherent book state and actual selected symbols, units, metadata/fees. Retain failed/unsupported venues as unknown/ineligible rows with reasons rather than silently dropping them. Rank comparable complete scenarios only.
- Implement amount rows using quote units for buys and base units for sells, including 100/1000/10000 where supported. Show incomplete depth/minimum/precision outcomes; no endless Calculating label after a completed response.
- Accept editable per-venue fee profiles and per-venue/per-currency balances through the request/store/service. Report unconstrained costs separately from feasibility; browser-local one-number checks do not satisfy inventory.
- Compute explicit later rebalancing scenarios with stated transfer/network/fixed/minimum/valuation assumptions; no instant transfer or unsupported cost invention. Preserve residual assets and disclose unknown conversion.
- For simultaneous split children on the same venue consume disjoint depth. Charge each child fixed fees and preserve aggregate ledgers/residuals/incomplete-child status. Delayed splits are future scenarios with uncertainty, not measured savings. Ratio/delay changes alter the actual request/result.
- Cancel/coalesce/debounce interactive requests with config/request generations. Stale replies/errors cannot retain old grid/split results as current. Use decimal-safe inputs and formatting; derive BTC/ETH/USD/USDT labels from metadata.

**Exit:** C01/C07/C08/C14 plus J04 pass with both venues available and failed-venue variants. One BTC at 100 cannot yield complete child purchases totaling 1.6 BTC. GUI and CLI agree on canonical scenario output and fees/inventory affect real rankings/feasibility.

### G08 - Make the native lifecycle, IPC and CLI reliable

Dependencies: G05/G06/G07; lifecycle/protocol preparation starts during G01. Findings: A06/A12. Requirements: R08-R10/R12/R13.

**Outcome:** users can start, stop, recover and inspect the same engine without hanging, duplicating processes or bypassing repaired contracts.

- Bound async pending requests, message bytes, concurrent operations and queues; reject unknown actions/versions. Timeouts/cancellation/late replies use documented safe semantics, cancel work where appropriate and never duplicate mutating operations. High-rate feed validation cannot be blocked by a view.
- Define sidecar exit recovery with bounded retries/backoff and explicit restart control. Acquire writer ownership before collecting, prevent duplicate processes, clear previous epoch's eligibility and surface disconnected/partial status atomically. Clean EOF/quit drains or reconciles writes and leaves no owned child.
- Verify pause/resume/stop acknowledgement, worker join, sleep/wake rebuild, timeout cancellation and store/I/O ownership under concurrent comparisons. Prior workers/futures cannot silently continue after stop.
- Replace CLI placeholder success with monitor/status/compare/export/import/original replay/changed-config replay/diagnostics reproduction actions using shared services and correct help/exit codes. Missing file/invalid input yields failure; only real successful work exits zero.
- Retire or explicitly redirect the prototype src/main.py to supported shared behavior after compatibility checks. No documented normal path bypasses validated fees/timing/cooldown/store rules.

**Exit:** C18/C19/C28/C29, CLI parity and J06-J09 pass. Sidecar death is visible/recoverable; app stays responsive; repeated requests/launches do not exceed limits or create duplicates; clean quit has no orphan process. Bundled sidecar tests and actual installed-shell evidence are recorded separately.

### G09 - Finish every visible action and responsive user journey

Dependencies: G08. Findings: A02/A04/A06/A10/A12. Requirements: R08/R09.

**Outcome:** the five destinations expose the complete truthful product, including errors, offline evidence and saved preferences.

- Connect every enabled control in the G00 inventory to acknowledged engine operation and durable state: Overview configuration/start/pause/resume/stop; event filters/detail/replay/compare/export; diagnostics lifecycle/pin/export/reproduce; cost fees/balances/rebalancing/grids/splits; settings quota/retention/audio/import/export/format/login opt-in.
- Initial native failure and later sidecar death show explicit unavailable/stale state. Aggregate loads use atomic provenance or independent section errors; no misleading LIVE/healthy badge attached to retained old data. Always clear action loading in catch/finally and provide retry/recovery.
- Original replay defaults to original configuration with no override. Show changed configuration separately and never overwrite original evidence. Add a graceful legacy-record state and an appropriate error boundary.
- Fix 320px navigation with responsive wrapping or an accessible dedicated scroll container; selecting any destination must not scroll the main app shell offscreen. Assert element visibility/bounds and actual usable controls, not merely document scrollWidth.
- Preserve Dashboard 3/2/8. Validate all five destinations and replay/dialog states at 320/768/1024/1440 in both themes, 200% zoom, keyboard/focus/labels, escape/focus-return, readable contrast and reduced motion. Before/after evidence should show functional changes and preserved branding.

**Exit:** C02/C07/C08/C26/C28 and J01-J09 pass using real serialized outputs, including missing/legacy/error states. All promised actions work and survive tab navigation/restart; synthetic fixtures are explicitly identified and never establish native completion.

### G10 - Repair clean builds, source provenance and the distribution pipeline

Dependencies: G00/G01; prepare external paths early. Findings: A07-A09/A11. Requirements: R10/R11/R13/R14.

**Outcome:** one repeatable pipeline builds the declared architecture from locked source, and failures cannot masquerade as verified distribution.

- Lock runtime and dev Python transitive/native build inputs with hashes for both architectures; preserve npm/Cargo locks and record Python/Rust/Node/tool versions. Verify a fresh environment outside existing symlinked environments. Review actual shipped dependencies/licenses and actionable advisories, without wholesale unneeded upgrades.
- Remove generated binary/build/cache files from the versioned source/build input set safely, preserving needed local work outside tracked paths. Rebuild from clean frozen source or reuse only hash-bound provenance matching source/locks/runtime/target. Architecture detection must fail unknown/mismatch rather than accept it.
- Select one coherent PyInstaller/Tauri packaging path and argument/resource/version naming. Clean checkout builds sidecar before sidecar-dependent tests, installs Playwright browsers where needed, and runs real Rust/frontend/build gates.
- Replace retired macos-13 and retiring macos-14 labels with current explicitly selected native architectures. As verified October 6, start with macos-15 for arm64 and macos-15-intel for Intel, then recheck official availability/image architecture and deployment targets. Runner availability does not prove macOS 13 compatibility. No paid runner without budget.
- Replace CI fixed-duration soak dependency with named bounded scenarios and actual RSS/queue/retention assertions. No inherited `passed` flag can override missing scenarios.
- Preserve per-architecture staging. Aggregate two distinct manifests into one validated final manifest/checksum list referencing both DMGs, one corresponding source and required notices; copying same-named manifests/checksums is not aggregation. Verify artifact-relative paths after CI download, including legal files omitted from old per-arch uploads.
- Produce deterministic corresponding source from an explicit frozen tracked source set: app, build/config scripts, locks, patches, notices and instructions; exclude venvs/build/dist/target/cache/.codegraph/agent private state/releases/raw data. Ensure any required vendored source is retained. Compare exported source tree to the declared source identity and build it in a clean location.
- Implement genuine nested Developer ID signing/hardened runtime, secure credential references, notarization/stapling/Gatekeeper and production artifact policy. Ad hoc development build is a separate labeled mode and cannot pass a production channel gate. Do not re-sign approved code ad hoc during prepare; verify final post-sign/post-staple bytes.
- Repair verifier predicates and negative controls B01-B10. Missing required asset/architecture/source/notices/signature/notary/native evidence must block. Test release and evidence aggregation without remote writes; remote CI remains unproven until authorized and run.

**Exit:** C23-C25/C27 and build/verifier negatives pass; clean per-arch builds and aggregate source/assets have correct provenance. Signing implementation exists and fails honestly without prerequisites. External credential/host/CI gates stay pending until G12 proves them.

### G11 - Validate the integrated product with bounded scenarios

Dependencies: G05-G10. Findings: A01-A14. Requirements: R01-R13.

**Outcome:** complete user behavior and recovery/resource limits are measured on the integrated candidate, with evidence categories that prevent false completion.

- Run meaningful lint/type/unit/integration/replay/serialized IPC/UI/build checks after repairs; collect every scenario, skip and failure. Counts are reporting context only. Keep historical F cases plus C regressions. Repair verifier-negative failures before relying on positive summaries.
- Execute J01-J10 and the Section 12 fault/resource matrix, with isolated temporary data for destructive injections. Use actual production service paths; fixtures carry fixture labels and cannot replace actual public feed/native output checks.
- Complete at least 10 usable live acquisition cycles per connector and actual WS subscription/reconnect/rebuild evidence. Complete at least 100 deterministic production-service cycles with measured/asserted bounds, plus bounded start/pause/resume/stop/restart and concurrent request scenarios. No minimum elapsed duration or profitable quote requirement.
- Measure real process RSS after warmup and scenario batches, pending/worker/thread/FD/queue counts, archive/database/WAL bytes, retention and flush/shutdown outcomes. Set explicit limits before running; verify failure paths at tiny configured quotas/queues. Record actual platform-specific method/units. A missing measurement blocks the corresponding assertion.
- Drive the actual installed shell, not only Playwright fixtures/direct sidecar. Save step outcomes, state/process/event IDs and errors with screenshots as supporting evidence. Instrumented test builds are labeled separately; final signed production journey repeats in G12.
- Keep environment outage/permissions/host absence explicit. Use bounded retry/attempt budgets and continue independent work; do not manufacture data, mark skipped checks passed or start a long soak.

**Exit:** all functional C/J/B obligations have applicable passing evidence with explicit boundaries; no unresolved P1/P2 release-contract issue; R01-R12 supported for the tested source. Platform/signing/current-candidate CI final evidence remains subject to G12.

### G12 - Freeze, sign, install and independently assess release readiness

Dependencies: G11. Findings: A07-A09/A11 and final review. Requirements: R11/R13-R15.

**Outcome:** exact versioned files are ready for authorized public release, with a clean source identity and no hidden installation or evidence prerequisites.

- Reconcile existing tags/releases read-only, choose the intended 1.0.0 only if unpublished, and preserve old known-broken artifacts as historical. Do not silently replace a released version. Freeze a clean committed source/config/locks/schema/kernel/app ID/runtime; generated evidence may live in later commits only when its subject remains the identical frozen product tree.
- Rerun affected checks/builds for the freeze and obtain authorized exact-source CI. No reusing unrelated main or edited reports. Verify rebuilt sidecar/embedded frontend and lock/runtime hashes rather than manually rebinding existing binaries to a new commit.
- Build per-arch assets via G10; perform owner-authorized Developer ID signing/notarization with accepted result, stapling validation, codesign identity/team/hardened-runtime verification and Gatekeeper assessment. Journal/reconcile submissions; preserve credential secrecy.
- Install downloaded/quarantined DMGs under clean non-developer users with no Python/Node/Rust dependencies. Do not strip quarantine/disable Gatekeeper as acceptance. Execute J01-J10 on actual native arm64 and Intel hosts, including minimum supported macOS evidence, migration/manual upgrade/settings/saved events, public access/CA resources and offline inspection.
- If a host/credential/remote gate is unavailable, finish all preparation and label exactly which R/J proof remains blocked. Do not mark the goal done, claim release-ready or weaken support scope without an owner decision.
- Audit CSP/capabilities/command-host/path scope, imports/export privacy, resource/test-server absence and actual license/source correspondence. Deliver accurate install/update/uninstall/privacy/support/security/release notes, aggregate manifest, checksums and one source archive. Source/help examples must execute real supported commands.
- Perform a separate critical review of the final production paths and evidence, reopening findings. Use independent agents/reviewers only when explicitly authorized; otherwise label self-review accurately. Old or same-implementation expected outputs are not independent proof.
- Produce `.agent/evidence/<candidate-id>/FINAL_ACCEPTANCE.md` and structured final acceptance: G/R/C/J/B mapping, exact candidate/config/runtime/assets/hashes, actual platforms/hosts, commands/CI URLs, direct/indirect limits, open findings and prerequisite status. Missing/contradicted rows prevent PUBLIC_RELEASE_READY.
- Publication is separately authorized: present the reviewed destination/version/assets/hashes, or if already authorized journal/reconcile and upload once, verify actual remote download hashes, then report PUBLISHED. Do not merge/publish just because a workflow ran.

**Exit:** all G/R and applicable C/J/B obligations proven for the frozen signed/notarized installed production files; no functional, host, signing, CI or distribution prerequisite remains. Only explicit publication authorization/upload may remain. Anything less has a precise incomplete state.

### 10.1 Dependency and milestone map

| Goal | Dependencies | Completed behavior |
|---|---|---|
| G00 | None | Truthful baseline, coverage inventory and red regressions |
| G01 | G00 | Validated cross-language contracts and atomic input/settings validation |
| G02 | G01 | Synchronized shared live feed, metadata and recovery |
| G03 | G01, G02 | Correct conserved calculations and complete identities |
| G04 | G02, G03 | Durable complete original evidence, replay/import/migration and bounds |
| G05 | G04 | Recorded follow-ups, restart-safe episodes and real outbox |
| G06 | G02, G04 | Fault/group/recovery/evidence/reproduction workflow |
| G07 | G02, G03, G04 | Real cost/grid/balance/rebalancing/split decisions |
| G08 | G05, G06, G07 | Native IPC/lifecycle and CLI parity |
| G09 | G08 | Complete responsive, truthful desktop workflows |
| G10 | G00, G01 | Reproducible builds, honest CI/release gates and signing implementation |
| G11 | G05, G06, G07, G08, G09, G10 | Integrated bounded functional/native/resource evidence |
| G12 | G11 | Frozen signed/notarized native installation and release audit |

Milestones: M1 trustworthy contract/feed/calculation (G01-G03); M2 complete retained user capabilities (G04-G07); M3 usable native product (G08-G09); M4 product validated (G10-G11); M5 public release ready (G12). These are observations, not separate task databases. Request budgets/host availability if truly needed, not speculative elapsed-time estimates.

## 11. Mandatory regressions, journeys and requirement matrix

### 11.1 Concrete regression obligations

These IDs specify behavior, not manufactured test counts. Combine related cases sensibly, but report individual outcomes. Include supported malformed/legacy/partial variants and direct production-boundary checks.

| ID | Required assertion |
|---|---|
| C01 | Both real usable venues -> compare/split nested fills serializable as finite decimal strings; packaged JSONL request succeeds |
| C02 | Production repository event -> correct row hashes/full fill DTO -> real detail/replay renders; legacy/malformed event yields useful incomplete state, no blank page |
| C03 | Original no-override capture with buy 0.006/sell 0.004, asks 100/bids 101/budget 100 preserves original negative result and canonical ledger; no substituted 0.0025 fees |
| C04 | Changes to captured price/quantity/timing/quality/epoch/metadata or fees/thresholds/inventory affect appropriate hash/validity; tampering cannot be exact |
| C05 | Modified acquired_base=999999, buy_fee=12345 or arbitrary config/result hashes reject exactness; compare full canonical fields |
| C06 | Two offline round trips reproduce complete originals; incomplete/sanitized/unsupported-version records stay inspectable and explicitly unavailable for exact replay |
| C07 | Production grid/split/replay shapes actually display results, no permanent Calculating/undefined fields; original and override modes separate |
| C08 | ETH/BTC and USD/USDT labels/units correct; a slower old request/error cannot overwrite current cost/grid/split/config state |
| C09 | NaN/Infinity/negative/zero amount/bool/wrong types/unsupported market/out-of-range ratios rejected through every entry point without partial setting/config writes; permitted zero fees/thresholds retained |
| C10 | Stale, incoherent, invalid or missing book/metadata/fees/timing cannot be eligible; required unknown counts/reasons remain visible |
| C11 | Kraken official 3310070434 snapshot plus bad snapshot/update CRC, repeated levels, deletes/truncation -> invalidation/incident -> valid synchronized recovery before reuse |
| C12 | Coinbase update-before-snapshot, supported sequence/gap/order rules, reconnect epoch, malformed frames, zero deletion and retained-depth re-entry never publish an unsupported clean book |
| C13 | Repeated actual REST/WS acquisition, stalled depth/heartbeat, reconnect/sleep/config-change and concurrent cost requests preserve I/O ownership and timing semantics |
| C14 | Actual venue increments/minimums/fee currency/rate/fixed fee/provenance apply consistently to monitor/cost/replay; independent ledgers and shared-depth/per-child fees conserved |
| C15 | 500ms/1s/3s observed follow-ups saved; disappear at 250ms/return at 750ms is not continuous; gaps/empty inputs UNKNOWN; initial scenario fixed |
| C16 | Restart inside cooldown does not re-alert; ordinary price drift stable episode; close/reopen/config changes and absolute AND relative escalation correct |
| C17 | Crash/restart durable outbox, retry exhaustion/backpressure/uncertain outcome; quiet persists and emits nothing; no false delivered state |
| C18 | Packaged sound/speech invocation/resource/exit failure visible; pause/stop/quit cancel/join old work, no orphan or duplicate writer |
| C19 | CLI monitor/status/cost/export/import/replay/diagnostics performs real service work; missing bundle/empty incident evidence cannot exit zero as success |
| C20 | Grouped faults persist both bounded samples/counts; recovery UTC is after opening, not 1; restart restores active incident; empty/contradictory/tampered evidence cannot REPRODUCE |
| C21 | Quota16/incoming114 rejects before exceeding capacity; boundary/multiple writes/pins/low-space/age settings and database/WAL bounds actually enforced, preserve pinned evidence |
| C22 | Migration/kill-between-commits/corrupt DB/import traversal/symlink/oversize/hash/schema faults preserve prior data and fail visibly, with no arbitrary executable imports |
| C23 | Empty or README-only manifest, zero usable live data, incomplete scenarios, skipped native checks and reused unbound binary all fail required verifier |
| C24 | Ad hoc/no-team/unnotarized production files fail readiness; actual authorized Developer ID/hardened-runtime/accepted-notary/staple/Gatekeeper chain passes |
| C25 | Clean native-arch CI build ordering/browser setup/target/resource names correct; downloaded per-arch artifacts aggregate without overwriting manifests or losing source/notices |
| C26 | At 320/768/1024/1440 both themes, selecting every destination keeps main and critical controls visible; Settings does not move shell/main to x=-187; focus/zoom/reduced motion work |
| C27 | Fresh locked build from exact corresponding source matches source/lock/runtime/architecture provenance; source archive contains no venv/build/cache/private state/nested release artifacts |
| C28 | Initial/ongoing native errors show unavailable/stale state and clear loading; sidecar death/version mismatch/timeout/late reply produces bounded recoverable behavior, no synthetic LIVE output |
| C29 | Simultaneous starts, repeated restarts, concurrent requests, cancellation, pending saturation and sleep/wake do not leak requests/workers/writer locks or silently reuse old epochs |

### 11.2 End-to-end user journeys

J01-J10 require actual service/store results. Browser contract checks supplement the installed app; final G12 native evidence identifies exact signed production app/DMG and each host/OS/architecture. Offline deterministic fixtures can establish controlled economics/faults, while J01/J06 also require actual public data. No real profitable opportunity is necessary.

| ID | Journey and required result |
|---|---|
| J01 | Clean first launch -> choose supported market/venues/amount/profile -> real acquisition -> inspect accepted/rejected/unknown coverage and actual currencies; no developer tools/keys/fake LIVE state |
| J02 | Stored real event -> fills/hash/reasons/temporal evidence -> original replay unchanged -> explicit fee/config re-evaluation separate -> export -> fresh offline import/replay |
| J03 | Controlled feed fault through production adapter -> visible incident/grouped evidence -> valid recovery/closure -> pin/export -> real offline reproduction; negative bundle fails |
| J04 | Buy and sell -> different amounts/grid -> editable venue fees/balances -> infeasible/unknown inventory -> rebalancing -> split slider/delay -> conserved results, failed venue stays visible |
| J05 | Change quiet/audio/retention/raw+pinned quotas/format -> actual behavior changes -> navigate/restart -> settings remain; import/export/login opt-in behaves as advertised |
| J06 | Start -> pause -> resume -> stop; concurrent cost request and feed disconnect/reconnect -> honest state -> rebuilt coherent books; no stuck controls |
| J07 | Kill sidecar -> immediate unavailable state -> safe bounded recovery/manual restart -> one writer -> no old eligibility; request timeout/late result saturation bounded |
| J08 | Eligible controlled scenario via production pipeline -> durable outbox -> packaged macOS output; quiet/failure/retry/restart uncertainty correctly visible |
| J09 | Quit/relaunch + duplicate launch + sleep/wake -> no orphan/duplicate -> restore state and explicit gaps; offline saved evidence usable; error states keyboard accessible |
| J10 | Quarantined clean-user install and manual upgrade on native arm64/Intel and minimum supported macOS -> no tool dependency -> preserve settings/events/pins/migrations; Gatekeeper/signature/notary valid |

### 11.3 Release requirement matrix

All fifteen remain mandatory. This revision reopens previous PROVEN rows because acceptance was contradicted or indirect; useful historical output is retained without transferring its status.

| ID | Requirement | Goals | Minimum direct proof |
|---|---|---|---|
| R01 | Input/time/config/cooldown correctness | G01-G03/G05 | C09-C16; atomic updates, real validity/timing, restored episodes |
| R02 | Calculation and conservation | G03/G07 | Independent full buy/sell/base/quote/fixed-fee/rounding/dust/shared-depth ledgers |
| R03 | Two real public spot connectors | G02 | Actual metadata and REST/WS acquisition, protocol fixtures, integrity/gap/reconnect recovery |
| R04 | Durable capture/recovery | G04 | Complete originals, atomic migrations/locks/kill/import/quota/retention/disk tests |
| R05 | Complete opportunities/replay | G04/G05 | J02, C03-C06/C15-C17; fixed-scenario temporal coverage and canonical exactness |
| R06 | Complete diagnostics | G06 | J03, C19-C20; measured windows/denominators and real negative-controlled reproduction |
| R07 | Complete cost advisor | G07 | J04; real fees/grid/balances/inventory/rebalancing/split and uncertainty |
| R08 | Complete consumer UI | G09 | J01-J09/C26/C28; all actions, settings, responsive/accessibility/error/provenance |
| R09 | Native lifecycle/delivery | G08/G11/G12 | Actual installed shell lifecycle, process ownership, recovery/sleep and packaged output |
| R10 | Privacy/security/license | G01/G04/G08/G10/G12 | Public-host/command/CSP/capability scope, safe import/export, no secret/telemetry/trading/test server, actual notices |
| R11 | Reproducible automated checks | G00/G10-G12 | Fresh locked setup, meaningful C/B suites/builds, no required skip, authorized exact-source CI |
| R12 | Bounded operational correctness | G11 | Completed live and deterministic scenarios plus actual RSS/queue/process/retention/recovery measurements |
| R13 | Installable compatibility | G10-G12 | J10; actual native arm64/Intel/minimum-OS, clean-user and preserved upgrades |
| R14 | GitHub distribution readiness | G10/G12 | Signed/notarized/stapled/Gatekeeper-accepted exact assets, clean install, aggregate manifest/source/checksums/notices |
| R15 | Final current audit | G12 | Final G/R/C/J/B matrix, frozen bindings, no unresolved release defect, truthful docs/prerequisites |

## 12. Verification contract and bounded fault/resource coverage

### 12.1 Fail-closed verifier obligations

Keep verifiers useful and small; test the predicates they actually use. Required evidence missing/failed/unknown/skipped/unsupported must return nonzero for its gate and cannot become PASS by artifact existence/test-count thresholds. Record incomplete environment separately from product failure.

| Negative ID | Supplied condition | Required result |
|---|---|---|
| B01 | All venue samples fail, zero usable data, unavailable metadata or fake data offered as live | Live gate nonzero; counts/reasons expose missing usable observations |
| B02 | Scenario interrupted before completed acquisitions/recovery/actions | Incomplete nonzero; timestamps report actual execution, not requested duration |
| B03 | Required native app missing or only direct sidecar/browser fixture supplied | Native gate nonzero; no ping fallback for a required installed-shell journey |
| B04 | Empty/README-only/missing-arch/missing-source/missing-notices manifest | Release gate nonzero with required asset-set failures |
| B05 | Wrong source/lock/runtime/artifact hash, unknown/wrong architecture or unbound cached binary | Provenance/build gate nonzero |
| B06 | Ad hoc/no TeamIdentifier/no hardened runtime/rejected or missing notary/staple/Gatekeeper failure | Production distribution gate nonzero |
| B07 | Quota/queue/RSS/record limit exceeded or measurement absent | Resource scenario fails/unknown, cannot pass on cycle count |
| B08 | Required skipped/disabled test path, absent scenario or old report for changed product | Relevant evidence invalidated; final acceptance nonzero |
| B09 | Empty/tampered/partial replay or incident evidence | No exact/reproduced claim; relevant command non-success with honest reason |
| B10 | Contract/output/native action intentionally broken in an isolated test build | Its named scenario and aggregate gate fail, proving the gate reaches that behavior |

### 12.2 Fault and resource matrix

Each row records trigger, actual production observer, invalidation/UI effect, retained evidence, recovery criterion and scope. Use deterministic fault fixtures where external induction is unsafe/unreliable, label them accurately and additionally exercise appropriate installed-native lifecycle faults. Destructive disk/DB tests use temporary data.

| Fault/scenario | Required behavior |
|---|---|
| Malformed JSON/types/NaN/infinity/negative quantity/missing fields/crossed book | Reject/quarantine, finding and coverage count, no eligible calculation |
| Checksum/gap/out-of-order/duplicate/delete/depth truncation/connection epoch | Protocol-aware handling, invalidate on integrity loss, synchronized rebuild before reuse |
| Slow response/timeout/rate limit/disconnect/stalled book/heartbeats | Measured timing/denominators, bounded backoff/cancel, distinguish liveness from usable depth |
| UTC jump/sleep/wake/missing capture/slow follow-up | Explicit gaps/clock uncertainty; no stale eligible/continuous label; fixed original scenario preserved |
| Disk full/quota/low free space/pin quota/retention | Incoming bytes reserved, pinned evidence preserved, capture gap and safe failure visible; DB/WAL/temp cleanup bound |
| Sidecar kill/EOF/restart/duplicate launch/cancel/request storm | One writer, bounded pending/queue/workers, responsive errors/recovery, no lost claimed delivery/no orphan |
| Migration interruption/corrupt DB/import fault | Recoverable explicit state and preserved previous data; no silent reset or partial successful import |
| 100 deterministic production-service cycles | Actual resource samples/assertions before/after warmup/batches; ≤512MiB steady engine RSS default ceiling with measured units, bounded queues/tasks/FDs/records/archives and clean flush |
| 10 usable live acquisitions per connector plus actual WS/recovery | Named completed observations and real protocol/quality state; failed attempts remain denominator, no time-based success |

Define finite configured pending/notification/feed/display queue/depth/record limits before measuring; make them visible in scenario reports. The 512MiB ceiling applies to the steady engine after packaging startup, with shell/WebView and PyInstaller extraction measured separately. If legitimate platform startup/transient use needs a different bound, document data and request a narrowly justified specification change; do not remove assertions to pass. These bounds establish the named scenarios, not long-duration leak freedom.

### 12.3 Commands and evidence layout

Retain supported verification/release entry points while repairing their meaning; add named scenario selection and real CLI commands/help as needed. Current verifiers are known incomplete and running them unchanged cannot prove this plan. Do not document nonexistent options as available.

Use new output directories per subject/run, for example `.agent/evidence/<candidate-id>/<verification-id>/`. Record commands/exit codes/raw reports, fixture hashes, scenario IDs/outcomes, config/runtime/source and artifact hashes, actual OS/architecture/tool versions, times and explicit skipped/unknown limits. Store an inventory and FINAL_ACCEPTANCE.md only after their actual checks.

Reopen affected requirements whenever source/locks/schema/kernel/fixtures/config/assets change. Final product tests bind the frozen product tree/commit; later evidence-only commits record that subject explicitly. Signing/notarization/stapling reopens package/native/channel checks on the resulting bytes. Never edit historical outcomes or manually relabel outputs to match a commit.

Use the existing offline/live/native and prepare/aggregate/verify commands only after G00/G10 repair. Stage per architecture before aggregation. Pure-browser mock E2E remains useful for interactions, but regression payloads must come from actual serialized production outputs; separately drive the installed shell for J acceptance.

Do not execute 86400-second or fixed Intel-hour commands. No soak job/automation is a dependency of this revision. Bounded tests have finite attempt/timeouts for termination, but elapsed time alone never counts as completion.

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
  "spec_version": "1.2.0",
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

Populate active G00-G12 with section 10 dependencies and the revised R01-R15 with evidence references. Preserve T00-T18 and N00-N08 in task history, with T18 owner-cancelled. No historical done flag can dispatch completion of a new task. Lifecycle: pending -> in_progress -> verifying -> done, plus blocked and owner-approved cancelled. Required cancelled tasks still block completion until a specification change reconciles scope. done needs applicable proof.

Atomic writes with generation checks; only lead updates shared status. Require one active lead lease with owner/session, expiry and verified liveness; stale leases need reconciliation before takeover. Atomically reserve task/logical invocation before dispatch and immediately recheck candidate, prerequisites, authorization and budgets. A lead restart must reconcile reserved work and real handles before new dispatch. When delegation is explicitly authorized, delegates submit artifacts/findings with subject hashes and isolated ownership. Reject stale updates. Checkpoint at milestones, dispatch/completion, external actions and every 15 minutes. Keep backups and validate schema/DAG.

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


## 14. Distribution deliverables and external prerequisites

### 14.1 Release package

Prepare one versioned release folder containing two architecture DMGs/apps as declared in the manifest, one exact corresponding source archive, LICENSE, NOTICES.md, aggregate manifest, checksums and concise release/install/update/uninstall/privacy/support/security information. One stable app ID and user-data path survive upgrade. Manual verified update is sufficient for v1; no automatic updater/hosted infrastructure is required.

The aggregate manifest includes source commit and product-tree identity, schema/kernel/app/runtime/lock/build versions, architecture and minimum-OS targets, asset type/path/hash/size, per-architecture provenance, evidence references, signing team/identity, notarization submission/result, stapling/Gatekeeper/native outcomes and source-export identity. Secret values never appear. Validate required fields/asset sets and exact final paths after CI download and packaging.

A checksum match is integrity of the declared file, not proof of correct source, functioning application, Developer ID trust or notarization. A signed app requires trusted identity and post-signature checks; an ad hoc signature is intermediate. Sign/staple before hashing final assets and verify Gatekeeper/quarantine installation on unchanged distributed bytes. Never remove quarantine or disable system security to manufacture a consumer pass.

### 14.2 Prerequisite ownership

| Prerequisite | Agent-owned preparation | External proof/action if unavailable |
|---|---|---|
| Legal owner/support identity | Validate existing LICENSE/NOTICES/support contents and consistency; draft missing materials | Accurate owner-designated identity/contact, without invented facts |
| Native hosts/minimum OS | Working per-arch build/installer/test instructions and scripts; perform available host checks | Actual Intel and arm64/minimum-macOS/clean-user native execution evidence; Rosetta/cross-build/newer OS has narrower scope |
| Public network/venue availability | Bounded retries, deterministic fault cases, visible unknown state, actual public feeds where available | Working connectivity for named live checks; outage is not product success |
| Developer ID/notarization | Implement secure referenced-credential path, nested signing, hardening, submissions and verification; dry-run negative cases | Owner-designated credential references and signing/submission authorization; no secrets in chat/account purchase |
| Current-candidate remote CI | Correct workflows, local clean builds/gates and concrete candidate diff | Explicit candidate-branch/PR authorization and access if absent; do not infer merge/publish rights |
| Public upload | Final source/assets/notes/hashes and destination/version check | Separate explicit publication authorization; only this step may remain after PUBLIC_RELEASE_READY |

Check prerequisites early, consolidate indispensable requests, and continue independent work. Do not treat the inability to physically access another architecture as a code defect or silently waive it. No precise calendar estimate is promised without host/credential availability. Current planning work neither signs nor publishes.

## 15. Final acceptance and evidence review

The final reviewer examines actual frozen source, public/fixture production flows, retained records, serialized boundaries, installed signed app, current-candidate CI and final package. A checklist with file paths is insufficient.

1. Confirm all Sections 3-9 behaviors and G00-G12 outcomes without scope reduction.
2. Enumerate A01-A14, newly discovered findings, old F regression obligations and C01-C29/J01-J10/B01-B10 with results, source identity and evidence category.
3. For each R01-R15 classify DIRECTLY_PROVEN, CONTRADICTED, INCOMPLETE, INDIRECT or MISSING. Only directly applicable proof completes the row; no required unknown/skip/environment gap can pass.
4. Audit the negative controls and a critical production path separately from implementation, with independent reviewers only when permitted. Self-review must be labeled self-review.
5. Resolve findings and rerun affected gates; no manually edited outcomes, fake native evidence or rebound old assets.
6. Confirm raw DB/archive/pinned/queue/resource constraints, settings/episode/outbox/incident recovery, schemas and platform/upgrade support. Inspect final binaries for real source/assets and absent enabled test facilities.
7. Reconcile exact signed/notarized/stapled final files against source/locks/runtime, aggregate manifest and final native checks. Confirm documentation/help commands match delivered behavior.
8. Produce truthful FINAL_ACCEPTANCE.md and structured matrix with all evidence and limitations. Set PUBLIC_RELEASE_READY only when nothing required remains except authorized upload. If not ready, list exact remaining agent work versus external proof and leave resumable state.
9. If publication is already authorized, reconcile tag/release/upload journal and verify downloadable hashes before PUBLISHED. No silent release replacement or main merge.

Goal completion is a demonstrated product result, not the count of tasks/tests or absence of errors in logs. Bounded scenario acceptance makes no 24-hour reliability claim.

## 16. Documentation, state and handoff hygiene

README describes actual delivered/development behavior. This guide is the sole active scope/task/acceptance specification. AGENT_PROMPT is the complete copyable execution instruction. `.agent/EXECUTION_STATE.json` owns progress/evidence applicability/authorization/budget/jobs/retries; `.agent/HANDOFF.md` is a replaceable summary. Audit snapshots and regression inventories record evidence, not competing requirements.

The October 6 planning revision changes only those documents/state and adds immutable prior snapshots/review evidence. Business code, tests, dependencies, cancellation guard, old reports and existing release assets are preserved. Active G goals begin incomplete; G00 reconciliation is partially documented but its regression/verifier work is not complete. Every active R row is reopened. Preserve original T/N history, retry lineage, cancelled jobs, budgets and existing authorization.

Use atomic generation-checked state updates and record the guide SHA-256. Do not reset progress or spend when switching agents. Existing candidate files remain known-broken historical intermediates; their filenames do not make them the new frozen candidate. A report emitted after owner cancellation cannot revive the cancelled task.

At each completed goal checkpoint source identity, actual outcomes, new findings, active jobs, next eligible goal and blockers. Provide meaningful concise updates; preserve an executable handoff on host/context limits. A prompt does not itself wake an exited agent, keep collecting through sleep or bypass external approvals.

## 17. Primary references

These sources inform implementation; they do not prove this project's gates. Recheck relevant current locked-version documentation when changing dependencies/protocol/builds. Never blindly execute examples or reveal credentials.

- [CCXT manual](https://github.com/ccxt/ccxt/wiki/manual): actual market/precision/limits/fee/timestamp semantics.
- [Kraken book checksum](https://docs.kraken.com/exchange/guides/websockets/book-checksum-v2): exact decimal formatting, subscribed-depth truncation and integrity coverage.
- [Coinbase public WebSocket endpoints](https://docs.cdp.coinbase.com/coinbase-app/advanced-trade-apis/websocket/websocket-endpoints): public level2/heartbeat endpoint and no-JWT access; verify exact market identity.
- [Coinbase level2 protocol](https://docs.cdp.coinbase.com/api-reference/advanced-trade-api/websocket/level2): snapshots/updates and replacement quantity semantics; retrieve full current schema for protocol conformance.
- [Tauri external binaries](https://v2.tauri.app/develop/sidecar/): resource/target naming and process integration.
- [Tauri macOS signing](https://v2.tauri.app/distribute/sign/macos/): identity, notarization and distribution setup.
- [Tauri testing documentation](https://v2.tauri.app/develop/tests/): verify locked-version macOS test support rather than assume it.
- [PyInstaller operating model](https://pyinstaller.org/en/stable/operating-mode.html): native runtime bundling and clean platform builds.
- [GitHub runner images](https://github.com/actions/runner-images): currently macos-15 arm64 and macos-15-intel x64 labels; verify the actual runner image/build architecture.
- [GitHub macOS 13 retirement](https://github.blog/changelog/2025-09-19-github-actions-macos-13-runner-image-is-closing-down/): the old Intel label is retired.
- [GitHub macOS 14 retirement](https://github.blog/changelog/2026-10-01-github-actions-macos-14-runner-image-retirement/): will retire November 2, 2026; do not migrate a new pipeline to this retiring label.
- [GNU GPL version 3](https://www.gnu.org/licenses/gpl-3.0.html) and [licensing guidance](https://www.gnu.org/licenses/gpl-howto.en.html): full license, notices and corresponding source.

The product reports inspectable estimates and data evidence. It never promises actual fills, guaranteed profit or complete long-duration reliability from these bounded checks.
