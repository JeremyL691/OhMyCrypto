# Security Policy

## Security & Privacy Commitments

**OhMyCrypto** is designed from the ground up with a zero-trust, privacy-first security posture:

- **No Private Keys**: OhMyCrypto does not request, store, or manage exchange API keys, private wallet keys, or withdrawal passwords.
- **No Order Execution**: OhMyCrypto is strictly an analytical and verification engine. It cannot place trades or move funds.
- **Zero Telemetry**: OhMyCrypto connects only to unauthenticated public WebSocket and REST endpoints for market data (Coinbase and Kraken). No user activity, system metrics, or diagnostic data is transmitted to external servers.
- **Local Storage**: All order book captures, evaluated opportunities, diagnostic logs, and user preferences reside entirely in your local user directory (`~/.ohmycrypto/`).

---

## Supported Versions

| Version | Supported          |
| ------- | ------------------ |
| 1.0.x   | :white_check_mark: |

---

## Reporting a Vulnerability

If you discover a security vulnerability or potential privacy issue in OhMyCrypto, please report it responsibly:

1. **Email**: Send details of the issue to the repository maintainers.
2. **Details to Include**:
   - Description of the vulnerability and its potential impact.
   - Steps to reproduce or proof-of-concept code.
   - Affected version(s) and operating system environment.
3. **Response Timeline**:
   - Maintainers will acknowledge receipt within 48 hours.
   - We will provide a status update and estimated fix timeline within 7 days.

Please do not open public GitHub issues for undisclosed security vulnerabilities.
