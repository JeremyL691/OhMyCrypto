# OhMyCrypto Project Execution Guide

Specification version: 1.0.0

Prepared: October 5, 2026, America/Los_Angeles

Status: documentation handoff. Implementation under this guide has not started.

## 1. Authority, scope, and completion

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

- `IMPLEMENTED`: required code exists; acceptance incomplete.
- `PRODUCT_VALIDATED`: correctness, integration, recovery, UX and continuous-run gates pass.
- `ARTIFACT_BUILT`: files exist, but channel verification may remain.
- `PUBLIC_RELEASE_READY`: all R01-R15/T00-T11 and channel conditions proven.
- `PUBLISHED`: authorized upload confirmed and downloadable artifact hashes match verified files.

An unsigned DMG is intermediate. Missing signing, notarization, native architecture evidence, or a final soak report prevents release readiness. `PROJECT_COMPLETE` requires the entire original scope and every required gate, with independent review and candidate-bound evidence. No implementing agent may waive a required check, shrink scope to fit completed work, or replace native/live acceptance with a mock.

The current assignment is documentation only. Do not treat this guide or its schemas as authorization to change code in this chat.

## 2. Current evidence and where to start

Repository: `JeremyL691/OhMyCrypto`.

Observed local HEAD: `1058083ad92b23f4e16d7068f9aea1a665209d60`, branch `main`. GitHub main matched it in the October 5 audit; the remote then had one branch, no releases, and zero Actions runs. Recheck these observations at implementation start.

The starting tree contains pre-existing changes to README and all five Python modules, untracked tests, and a CodeGraph index. Preserve these before replacement. Resetting to the initial commit would discard the locally upgraded order book implementation.

### 2.1 Existing responsibilities and migration

| File | Current responsibility | Required migration |
|---|---|---|
| `src/main.py` | CLI, scan loop, logs, notification scheduling | Separate orchestration; add bounded runs and explicit lifecycle |
| `src/market.py` | Concurrent CCXT REST access and error counters | Preserve useful behavior; add provenance, capabilities, streaming and resynchronization |
| `src/strategy.py` | Quotes, spread scan, depth fills, alerts | Extract deterministic domain kernel; repair correctness first |
| `src/notifier.py` | `afplay` and `say` | Observable, bounded notification delivery and durable outbox |
| `src/config.py` | Defaults and voice/sound mappings | Versioned validated settings and per-venue fee profiles |
| `tests/` | Nine fake-exchange unit tests | Preserve baseline; add independent regression, integration and native coverage |
| `requirements.txt` | Flat environment pins with unused analytical dependencies | Declare direct dependencies; reproducible lock after import/packaging verification |

Prefer codebase-memory MCP discovery when available; index through it if needed. If unavailable, use the existing CodeGraph index before raw source searches. Use text search for docs/configuration. Do not initialize a separate CodeGraph index merely for this plan.

### 2.2 Observed checks and limits

This documentation session reran all nine existing tests successfully using `venv/bin/python`, Python 3.12. Earlier checks in this same chat observed:

- Thirty seconds of default public Coinbase/Kraken monitoring: nine successful cycles, no request errors and no qualifying alert.
- Two real public 20-level books and a completed fill/cost calculation, approximately -2.14 USDT for that sample.
- A synthetic profitable main-loop scenario: eight cycles, one stubbed notification and closed clients after cancellation.
- Installed `say` and `afplay`. Actual audible playback and desktop interaction were not tested.

These observations have no frozen-release artifact binding. They are baseline evidence, not final-gate results. Do not copy their counts into a future report as newly run validation.

### 2.3 Mandatory defect repairs and regression inputs

| Defect | Reproduction or source evidence | Required behavior |
|---|---|---|
| Receive time masks event age | A fake ticker one hour old receives current `fetched_at_ms` and passes current filtering | Preserve both clocks and timestamp semantics; receiving an old known quote does not make it fresh |
| Tiny price move resets cooldown | Midpoint 100000.0 to 100000.2 after one second creates a new fingerprint | Stable route/instrument/profile/amount key and persistent episode identity |
| Non-finite values accepted | NaN bid/ask/last pass current comparisons | Reject NaN, infinity, booleans and malformed numeric types before calculations/decisions |
| All-in budget exceeded | Quote budget 1000 at 0.1% buy fee becomes actual spend 1001 | Buy spend plus supported fees stays within the specified all-in budget |
| Wrong currency labels | Arbitrary BASE/QUOTE accepted; speech always says dollars | Preserve actual quote/base/fee units; no silent USD/USDT/USDC equivalence |
| Weak input/capability validation | NaN can pass numeric checks; only symbol syntax checked | Finite bounded arguments, real spot support, limits and precision |
| Ephemeral state | Health/cooldown dictionaries lost on restart | Persist relevant state, identify gaps, avoid duplicate alerts |
| Hidden notification failures | Subprocess errors swallowed; state recorded before delivery | Separate decision/enqueue/delivery times and bounded observed retries |
| Incorrect Python support | Old README said 3.9+; installed NumPy/Pandas require >=3.11 | Python 3.12 baseline and clean-install compatibility checks |

Ticker timestamps may describe last trade time, book update time, or be absent. Do not blindly require every ticker timestamp to be recent. Declare its meaning in connector metadata. Tickers discover candidates; coherent order books establish amount-specific quoted conditions. Unknown data remains explicitly uncertain.

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
| Packaging | PyInstaller onedir plus Tauri per-target resources/entry | Include interpreter/dependencies; clean-user native verification |
| Checks | pytest, independent oracles, IPC/replay tests, Playwright, native checks | Browser mocks supplement rather than replace installed-app acceptance |

Prototype sidecar packaging/start/quit in T01 before investing in UI. Use current locked-version documentation for sidecar naming and resources. Do not add hosted services, Redis, Kubernetes, user accounts, a trading bot framework or an LLM to satisfy this release. Reuse mature tools where appropriate without hiding project-specific correctness contracts.

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
scripts/         # verification, soak, build and release entry points
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

Allow finite zero-fee profiles and optional zero thresholds; enforce positive quantities and finite bounded intervals. Verify exchange capability through the supported registry/metadata, not arbitrary `hasattr`. Maintain exact endpoint/venue identity: do not mix Coinbase Advanced Trade metadata with Coinbase Exchange stream data without verified equivalence. The initial release supports two declared public spot connectors; register their current venue IDs and common supported symbols during T03. Additional unsupported venues get clear results, not fictional support.

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

## 10. Tasks and construction order

This table defines required tasks. State stores status/dependencies/evidence references, not conflicting acceptance prose.

| ID | Dependencies | Work | Exit evidence |
|---|---|---|---|
| T00 | None | Preserve tree; inspect rules/remote; record decisions, authorization, prerequisites/budget; initialize state | Baseline manifest, valid DAG, prerequisite register |
| T01 | T00 | Scaffold, contracts, independent kernel boundaries, IPC/native packaging spike | Clean install/import; bundled sidecar round-trip and owned-child quit |
| T02 | T01 | Repair input/time/cooldown/budget/units/fees/precision/delivery visibility | Early R01/R02 regression/oracle evidence; baseline failures; full persistence/restart gates wait for T04/T09 |
| T03 | T02 | Public metadata/REST/WS adapters, reconstruction and coherent books | R03 live/recorded conformance, gap/resync and symbol capabilities |
| T04 | T03 | SQLite, recovery, archives, stable events, retention/outbox/queues | Engine/storage subset of R04 and recovery checks; full installed-app R09 is later |
| T05 | T04 | Opportunity verification, follow-up and replay/import/export | R05 deterministic and temporal evidence |
| T06 | T04 | Diagnostics, distributions and incident reproduction | R06 induced-fault detection/reproduction |
| T07 | T04 | Buy/sell advisor, amount curves, inventory/rebalance/split scenarios | R07 arithmetic/inventory/depth oracles |
| T08 | T05,T06,T07 | All views, selected design, accessibility and native workflows | R08 responsive/theme/native UX and before/after |
| T09 | T08 | Freeze committed source/config; prepare immutable production bundle; run final product/security/recovery/CI and continuous checks | Complete R01-R12 on candidate, including signed production-bundle soak; record any early evidence replaced |
| T10 | T09 | Final both-architecture and distribution validation; corresponding source/notices/release materials | R13/R14 package/channel/source correspondence; preserve tested runtime inputs |
| T11 | T10 | Independent completion audit and release-ready handoff; publish only if authorized | R15 and every requirement proven; reviews resolved; release state justified |

T05-T07 may be delegated with isolated ownership after shared dependencies pass. T00-T02 and freeze/release remain coordinated. Early native/packaging probes should happen before formal final gates; early checks do not replace candidate-bound verification. Never reduce product scope because one feature passed first.

A task can finish its specified implementation slice while related final requirement status remains unproven. Early checks contribute evidence but cannot mark an entire final R-row passed. Before T09, commit/freeze source/settings/locks and record app, sidecar, native dependency and resource identities. Packaging/signing pipeline implementation must be ready before final checks; T10 verifies/reuses outputs rather than introducing untested runtime changes. Any relevant source/resource/layout change reopens affected gates and the soak. Signature/notarization metadata-only changes require documented runtime-content equivalence and repeated channel checks; do not assume equivalence from matching source commit alone.

## 11. Mandatory acceptance matrix

Each claim maps to actual verification IDs/artifacts. Infrastructure absence creates a prerequisite/blocker; no required skip passes.

| ID | Requirement | Minimum proof |
|---|---|---|
| R01 | Input/time/config/cooldown correctness | Section 2.3 regressions, invalid books, timestamp semantics, restarted cooldown, quiet mode, finite CLI arguments |
| R02 | Calculation kernel | Hand-derived buy/sell/fee/precision fixtures, base sell and per-child fixed fees; budget and per-venue/currency conservation; depth/limits/residuals/units |
| R03 | Two real public spot connectors | Metadata/markets and live ticker/book/stream; identity, connector-specific sequence/checksum/depth integrity, gap/resync, unchanged-live vs stalled channel, honest fallback |
| R04 | Durable capture/replay foundation | Kill/restart transaction tests, migration restore, atomic archives, two identical replay hashes, corruption/gap handling |
| R05 | Complete opportunity capability | Positive/negative/rejected/unknown; every delay; continuous vs sampled persistence including 250-ms disappearance/750-ms recovery, threshold/profile/gap fixtures; complete replay vs sanitized limits; versioned replay |
| R06 | Complete diagnostics | Every fault detected with declared rules/counts/windows; visible incident grouping/recovery/closure/pin/export; offline bundle reproduces expected findings |
| R07 | Complete cost advisor | Buy/sell grid, fees/units/limits, ineligible reasons, inventory/rebalance and split-depth conservation |
| R08 | Complete consumer UI | All destinations/states/themes/widths, accessibility/dials/before-after; installed first-launch configuration/change/original replay/pause/restart journey |
| R09 | Native lifecycle/recovery | Installed start/quit/single-instance; sidecar/feed/disk/notification errors; restart/pause/sleep-wake |
| R10 | Privacy/security | No unexpected egress/trading/telemetry; CSP/capabilities; unsafe import and secret/export checks; dependency/license review |
| R11 | Clean reproducible automated gates | Fresh install/locks, lint/type/unit/integration/replay/IPC/UI/build checks, CI at candidate identity; required skips fail |
| R12 | Continuous-run reliability | One uninterrupted 24-hour awake-host live profile, final bound report, resources/coverage and separate induced-fault recovery |
| R13 | Installable compatibility | macOS 13+ evidence, arm64 and x86_64 builds and native checks on both; no developer runtime required |
| R14 | GitHub distribution readiness | Developer ID signing, accepted notarization, stapling, Gatekeeper, quarantined clean-user install; GPL/notices/matching source |
| R15 | Final evidence and audit | Candidate/config/artifact bindings, every row proven, three review roles resolved/revalidated, truthful materials, no required prerequisite missing |

Positive-profit events need not occur in real markets. Synthetic positive fixtures independently validate behavior and remain labeled synthetic. No actual-fill profitability claim is an acceptance condition.

## 12. Commands, evidence and continuous run

Current commands run now. TARGET commands must be implemented/documented by the future agent; they do not exist yet. Resolve invocation paths and record actual commands in evidence.

Current baseline:

```sh
git status --short --branch
git diff
git diff --cached
git log -5 --oneline
PYTHONDONTWRITEBYTECODE=1 venv/bin/python -m unittest discover -s tests -v
```

TARGET setup from repository root:

```sh
python3.12 -m venv .venv
.venv/bin/python -m pip install --require-hashes -r requirements-dev.lock
.venv/bin/python -m pip install --no-deps -e .
npm --prefix desktop ci
```

TARGET verification/release contracts:

```sh
.venv/bin/python -m pytest tests/unit tests/integration tests/replay -q
npm --prefix desktop run typecheck
npm --prefix desktop run test
npm --prefix desktop run test:e2e
.venv/bin/python scripts/verify.py --gate offline --output .agent/evidence/offline
.venv/bin/python scripts/verify.py --gate live --duration 600 --output .agent/evidence/live
.venv/bin/python scripts/verify.py --gate native --app /path/to/OhMyCrypto.app --output .agent/evidence/native
.venv/bin/python scripts/soak.py --duration 86400 --profile release-v1 --output .agent/evidence/soak24
.venv/bin/python scripts/release.py prepare --version 1.0.0 --channel github --output release/candidate
.venv/bin/python scripts/release.py verify --manifest release/candidate/manifest.json
```

The native verifier drives the actual installed application with supported platform automation and collects process/filesystem outputs. Missing automation permission is a prerequisite, not permission to substitute mocked browser results. Implement script help, architecture selection, setup and all lint/type/build checks.

Verifiers return nonzero for failures, required skips, missing checks, unsupported environment or insufficient coverage. Reports enumerate inputs/checks/outcomes/failures/skips/reasons/artifacts; passed=true alone is insufficient.

Each evidence record includes verification/requirement/task IDs, subject commit, pre-freeze dirty manifest if any, relevant source/input/config hashes, tools/runtime, platform/architecture, command, timestamps, exit status, check outcomes, coverage and artifact hashes. Preserve stdout/stderr and actual reports. Never manually edit result fields to manufacture a pass.

Reopen dependent checks when source/dependencies/config/schema/fixtures change. Keep a dependency map; preserve old runs with explicit applicability. Final evidence binds a committed clean candidate and frozen locks/settings. Signing changes reopen package/channel checks even if domain tests stay applicable.

### 12.1 Uninterrupted 24-hour gate

Run 86400 seconds on the arm64 release candidate with both public venues, an agreed common spot pair, frozen release configuration and all three services enabled. Intel requires the full native install/lifecycle/compatibility suite and a 60-minute live run on its installed signed/notarized production x86_64 candidate, with instrumentation disabled, the same applicable coverage/resource/error criteria, and a final bound report. Record shell/sidecar/resources/dependencies hashes in addition to commit/config, process/session identity, monotonic duration, heartbeats, sleep/wake, gaps, metrics, queues/storage/events and resources. The formal runs use production candidates with test instrumentation disabled; missing signing/host access blocks these final gates while independent work continues.

The host must stay awake on power/network. Use scoped wake prevention only when permitted; never alter permanent power settings. Sleep, application restart, process crash or missing recorder invalidates the continuous window. Preserve failure evidence and begin a new full window after recovery. Separate windows cannot be added together.

Pass conditions: no unhandled crash, invalid financial output, silent decision/incident loss, corrupt archive/database, unintended duplicate notification or unbounded resources. Default engine RSS <=512 MiB; combined app <=1 GiB; no sustained >25% unexplained growth between comparable post-warmup windows. Record CPU/input rate/hardware. Version justified threshold changes before rerunning, not after failure to obtain green results.

Venue outages may be safely recovered without product failure, but coverage remains explicit. Require >=95% usable observation time per venue; define usable time/gaps, not just request counts. Lower coverage is insufficient external-data evidence requiring another full window. Profitable events are unnecessary. Deliberate failures and sleep/wake tests run separately.

The completed final report with actual metrics/hashes is mandatory. RUNNING, a PID or partial heartbeats cannot pass R12. Relevant source/config changes invalidate the window's binding. Unchanged files alone do not prove continuous liveness.

## 13. Autonomous execution and continuity

### 13.1 Preflight

Read rules/guide/prompt/state, Git branch/status/diffs/untracked work. Preserve the upgraded tree via recoverable snapshot or authorized WIP commit before replacement. Default branch prefix codex/. Do not reset/clean/overwrite unrelated work or conceal pre-existing changes in the release candidate.

Channel, style and GPL choices are resolved. Bundle remaining indispensable prerequisites: accurate owner/support identity, both native architecture/test hosts, public network access, signing/notarization secret references and any necessary spending budget. Ask for availability/references, not secret values. Continue independent work while dependent paths wait. Do not ask whether to continue ordinary authorized development, fixes, tests or packaging.

Check Python/Node/Rust/tools, using project-local environments and pinned versions. Do not alter system security, install privileged services, enroll accounts or purchase resources as a workaround. Verify blockers from current state, not old handoff prose.

### 13.2 Canonical state

The future agent creates `.agent/EXECUTION_STATE.json`. This guide owns requirements/task definitions. State owns progress, applicability, budgets, decisions, authorization, jobs and retries. HANDOFF.md is a replaceable generated summary, not a second task database.

Initialization schema example:

```json
{
  "schema_version": 1,
  "project_id": "OhMyCrypto",
  "spec_version": "1.0.0",
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

Populate T00-T11 with section 10 dependencies and R01-R15 with evidence references. Lifecycle: pending -> in_progress -> verifying -> done, plus blocked and owner-approved cancelled. Required cancelled tasks still block completion until a specification change reconciles scope. done needs applicable proof.

Atomic writes with generation checks; only lead updates shared status. Require one active lead lease with owner/session, expiry and verified liveness; stale leases need reconciliation before takeover. Atomically reserve task/logical invocation before dispatch and immediately recheck candidate, prerequisites, authorization and budgets. A lead restart must reconcile reserved work and real handles before new dispatch. Delegates submit artifacts/findings with subject hashes and isolated ownership. Reject stale updates. Checkpoint at milestones, dispatch/completion, external actions and every 15 minutes. Keep backups and validate schema/DAG.

### 13.3 Work loop

1. Reconcile source/state/authorization/evidence and actual live jobs.
2. Resume reconciled in_progress/verifying work before selecting new pending tasks with done dependencies. Reopen a blocked task only after verifying its prerequisite changed; continue independent eligible work around remaining blockers.
3. Implement a coherent slice advancing the full task.
4. Run checks with independent expectations, preserve output, fix failures and rerun affected checks.
5. Obtain independent integration/release review, resolve and verify findings.
6. Checkpoint state/handoff and continue without routine approval requests.
7. Audit every original requirement before completing the goal.

Persist failure signature/hypothesis/remedy/result/next step. After three equivalent failures change approach or isolate the external condition; agent changes never reset retries. Stop only dependent work. When nothing eligible remains request the smallest indispensable input and preserve the full objective.

Separate host_limit from persistent project_budget. Runtime switches do not reset spend, retries, authorization, pauses or evidence. No token limit is assumed here; unknown telemetry stays unknown. Honor explicit limits supplied later.

### 13.4 Long jobs and recovery

Job records require task ID, stable logical invocation ID, candidate/config, command, PID/tool/session, process-start identity, state, last verified liveness time, output location, retry/failure class, next eligible retry time and final artifact reference. Register reservation before invocation, then actual handle. Marker files and commentary are not liveness evidence. On observation timeout inspect the same handle; never restart a possibly active soak/build/notarization merely because polling timed out.

Use bounded waits and meaningful updates. Supported goal continuation may keep the agent working, but a prompt cannot wake an exited process, collect through host sleep or bypass limits. Cross-session continuation needs a real supported scheduler/supervisor plus shared files/Git. Create automation only with explicit authorization; otherwise record the missing host capability and retain resumable state.

Resume from state/handoff plus actual Git/source/job/external-action inspection. Revalidate spec/config, reopen invalid evidence and continue the next eligible action. Never trust handoff prose alone.

### 13.5 External-action journal

Before non-idempotent operations append unique action ID, operation/destination, subject hashes, authorization reference, expected result and prepared state to actions.jsonl. Store request/result IDs. Uncertain outcomes require reconciliation at the original destination before retry. Apply to notarization, tags, releases and uploads.

Journal states are prepared -> submitted -> confirmed, with failed/uncertain outcomes. Preserve the same logical action ID for retry/reconciliation; record attempt IDs separately. A new ID cannot hide an unresolved prior submission. Credential presence alone is not action authorization: owner-designated signing/notarization use must be recorded for the frozen candidate before submission. Publication and main-branch merge remain separately scoped.

Local checks/build retries need no repeated approval. Publication/credentials/spend stay within supplied authorization. No unsolicited email or external messaging is part of implementation.

## 14. GitHub macOS release

Build separate aarch64-apple-darwin and x86_64-apple-darwin artifacts. Shell/interpreter/sidecar/native wheels must match; Rust target selection alone cannot convert Python architecture. Use native compatible builders/test hosts and record minimum OS/library compatibility. A newer host does not prove macOS 13 support.

Freeze source commit, settings/locks, schemas, app ID/version and input manifest. Bundle onedir Python resources/entry using current Tauri contracts. Verify hidden imports, CA certificates, paths, permissions and process lifecycle. Sign nested code with correct identity/hardened-runtime configuration; changes to signed contents require verification again.

Implement repeatable prepare/build/sign/notarize/staple/verify. Keep credential references secure. Require signatures, accepted notarization, stapled ticket, Gatekeeper and quarantined clean-user installation without developer tools. Disabling Gatekeeper is not the consumer installation path.

Deliver app/DMG per architecture, checksums, source/version manifest, GPL corresponding source, notices, actual owner privacy/support information, truthful release notes, installation/uninstallation and migration instructions. Pinned inputs/provenance support reproducibility; signing can change bytes, so do not claim bit-identical signed outputs without evidence.

Installed app opens offline for saved/demo evidence with network limitations visible. Verify upgrade preserves settings/events. Automatic updater is not required in v1; verified manual replacement and schema migration are required. Start-at-login is opt-in; uninstall explains retained data.

Publication requires explicit destination/version/artifact authorization; local preparation continues without it. If authorized later, journal/reconcile existing tags/releases, upload verified assets once, inspect remote version/links and verify hashes. Never silently replace a published version. Attach any created implementation PR when required by host tools.

## 15. Reviews and completion audit

For this documentation assignment, write the guide/prompt first, then request three independent sub-agent roles: product/full scope; technical calculations/data/replay/packaging; autonomy/evidence/release. Incorporate valid findings and recheck affected sections. Those reviews prove plan quality, not implementation.

Future implementation repeats these roles on actual code and frozen candidate. Reviewers inspect current sources/actual reports, not only the lead's summary. Resolve blocking findings and rerun impacted checks.

### 15.1 Documentation review record

Three independent reviewers inspected the written files on October 5, 2026, then rechecked revisions. Their scope was documentation only.

| Role | Findings incorporated | Recheck |
|---|---|---|
| Product scope | Fixed-scenario continuous vs sampled persistence; incident lifecycle; complete vs sanitized exports; desktop monitor configuration journey | All reported scope/acceptance findings resolved |
| Technical plan | Per-currency fee ledgers; connector integrity/decimal/checksum depth; liveness clocks; supported replay kernels; runtime binding | All five technical findings resolved |
| Autonomy/release | Non-circular task gates; pre-verification freeze; lead lease/reservations; job/action identity; resumed task handling; Intel production-run evidence | Major findings resolved; final minor wording/permission synchronization incorporated |

No review result establishes implemented-product completion. The remote candidate-write decision is recorded separately from publication and must match the owner's response, never reviewer preference.

### 15.2 Final implementation audit

Final audit:

1. Re-read original objective, owner decisions, instructions and guide.
2. Enumerate R01-R15/T00-T11, all named commands/artifacts/invariants/channel conditions.
3. Inspect authoritative source/runtime/installed app/CI/reports and candidate/input/config bindings.
4. Classify each proven, contradicted, incomplete, indirect or missing; only proven counts.
5. Resolve/reopen and continue until all required items are proven, preserving scope.
6. Ensure no required skip, missing prerequisite, unresolved review, unfinished gate or unrelated dirty candidate change remains.
7. Produce final matrix, candidate/artifact identity, platforms, coverage/resources and limits.
8. Set PUBLIC_RELEASE_READY and complete the implementing goal only after all readiness gates pass; if separately authorized, verify publication and set PUBLISHED.

Follow the host goal-blocking threshold for real external conditions. Never complete because usage/turn ends or a partial handoff exists. Document review cannot establish actual unattended execution/recovery; those claims need live host evidence.

## 16. Documentation cleanup

Keep three entry docs: README for actual status/install, this guide for specification/execution, AGENT_PROMPT for handoff. State/evidence are records, not competing roadmaps.

README was the only existing project document at preparation. It was rewritten in place to remove stale Python support and overconfident freshness/cooldown claims, distinguish prototype from intended release and link guidance. No redundant project docs existed to delete. Do not remove code/tests/environments/dependencies/CodeGraph/user evidence to produce a cleanup count.

During implementation update README to delivered behavior; add essential GPL/privacy/user/security notices for concrete distribution requirements. Remove superseded plans after migrating unique requirements and fixing links. Keep acceptance definitions here rather than divergent checklists.

## 17. Primary references

Recheck current locked-version documentation at T00/T01 and packaging. References inform design, not this project's gate results. Never blindly execute examples or expose credentials.

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
