# OhMyCrypto

OhMyCrypto is a local-first macOS application project for cryptocurrency opportunity verification, feed diagnostics and execution cost comparison. A Python engine, CLI and Tauri desktop candidate exist; the complete workflows are still being repaired and validated. It does not place orders.

The completion plan will deliver one local-first macOS application with three capabilities:

1. Opportunity verification and replay: inspect costs, data quality, and how long quoted conditions persist.
2. Market data quality diagnostics: measure collection problems and preserve reproducible incident evidence.
3. Personal execution cost comparison: compare estimated purchase or sale costs for a selected amount and venue set.

The full desktop workflows are still being completed and verified. The selected distribution channel is GitHub Releases.

## Current status

The completion review on October 5, 2026 found a Python engine, Tauri desktop shell and packaged candidate, with 57 Python tests, 7 UI unit tests and 8 browser fixture E2E tests passing. Additional checks reproduced defects in repeated acquisition, exact replay/hashes, native error handling, split-depth conservation, Kraken checksums, feature wiring and release verification. The product is not release ready.

The owner cancelled the fixed 24-hour task. The revised execution guide replaces long-duration gates with bounded real-product functional and recovery checks while retaining the complete three-capability scope and macOS distribution requirements. Existing artifacts and prior pass reports are historical until the repaired candidate is verified.

Python 3.12 is the development baseline. Native sound and speech require macOS. The commands below describe the retained prototype, not installation of the final desktop product.

## Run the existing prototype

From the repository root:

```sh
python3.12 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
.venv/bin/python src/main.py --quiet
```

The default pair is `BTC/USDT` on Coinbase and Kraken. `--quiet` disables sound and speech. Run `.venv/bin/python src/main.py --help` for the existing options. Freshness and cooldown have known limitations described in the execution guide.

```sh
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m unittest discover -s tests -v
```

## Refactor handoff

- [Project execution guide](PROJECT_EXECUTION_GUIDE.md): authoritative product scope, architecture, task order, acceptance requirements, autonomous execution protocol, and release gates.
- [Agent prompt](AGENT_PROMPT.md): copyable instruction for the agent that will implement the refactor.

The guide defines the intended release, not a claim that implementation or release validation has completed. No other roadmap or completion checklist should compete with it.
