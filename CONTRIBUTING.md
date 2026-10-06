# Contributing to OhMyCrypto

Thank you for your interest in contributing to **OhMyCrypto**! We welcome contributions that maintain the mathematical rigor, local-first privacy, and fail-closed integrity of the project.

---

## Code of Conduct & Principles

1. **Zero-Trust & Local-First**: No code that introduces external telemetry, hosted servers, or attempts trade execution will be accepted. OhMyCrypto is strictly an analytical and verification tool.
2. **Exact Mathematical Conservation**: All financial arithmetic must utilize Python's `Decimal` type. Floating-point conversions in domain or kernel code are prohibited.
3. **Fail-Closed Verification**: All new features or bug fixes must include unit or integration tests, maintain strict protocol integrity, and pass all verification gates.
4. **License**: OhMyCrypto is licensed under the **GNU General Public License v3.0 (GPL-3.0-only)**. All contributions must be compatible with this license.

---

## Development Setup

### Prerequisites

- macOS 13.0 or later
- Python 3.12
- Node.js 22 (LTS) & npm
- Rust 1.80+ (`cargo`)
- Xcode Command Line Tools (`xcode-select --install`)

### Getting Started

1. **Fork and Clone**:
   ```bash
   git clone https://github.com/<your-username>/OhMyCrypto.git
   cd OhMyCrypto
   ```

2. **Python Environment Setup**:
   ```bash
   python3.12 -m venv .venv
   source .venv/bin/activate
   pip install --upgrade pip
   pip install -e ".[dev]"
   ```

3. **Frontend & Desktop Setup**:
   ```bash
   cd desktop
   npm install
   npx playwright install chromium --with-deps
   cd ..
   ```

4. **Running in Development**:
   ```bash
   cd desktop
   npm run tauri dev
   ```

---

## Testing & Verification

Before submitting a pull request, ensure all verification gates pass locally:

### 1. Offline Verification Gate
Runs all Python unit/integration tests, type checking, Vitest UI unit tests, Playwright E2E browser journeys, and kernel budget invariants:
```bash
.venv/bin/python scripts/verify.py --gate offline --output .agent/evidence/offline
```

### 2. Live Connector Gate
Validates public REST and WebSocket connectivity against Coinbase and Kraken:
```bash
.venv/bin/python scripts/verify.py --gate live --output .agent/evidence/live
```

### 3. Native Bundle Gate
Validates macOS bundle structure, codesigning, and sidecar IPC execution:
```bash
.venv/bin/python scripts/verify.py --gate native --app release/candidate/OhMyCrypto.app --output .agent/evidence/native
```

### 4. Running Individual Test Suites
- **Python Tests**:
  ```bash
  .venv/bin/pytest tests/
  ```
- **Desktop Component Tests**:
  ```bash
  cd desktop && npm test
  ```
- **Desktop E2E Tests**:
  ```bash
  cd desktop && npx playwright test
  ```

---

## Pull Request Guidelines

1. **Branch Naming**: Use descriptive branch names like `feat/new-indicator`, `fix/kraken-resync`, or `docs/cli-examples`.
2. **Commit Messages**: Use Conventional Commits (`feat:`, `fix:`, `refactor:`, `test:`, `docs:`, `chore:`).
3. **Documentation**: Update `README.md` or applicable documentation if you modify CLI options or user workflows.
4. **Clean PRs**: Ensure no temporary build outputs, virtual environments, or credentials are committed.
