## Description

Please include a summary of the change, which problem it addresses, or which feature it adds.

Fixes # (issue)

## Type of Change

- [ ] Bug fix (non-breaking change which fixes an issue)
- [ ] New feature (non-breaking change which adds functionality)
- [ ] Documentation update
- [ ] Refactor / Performance enhancement

## Testing & Verification

Please describe how you verified your changes:

- [ ] Ran `.venv/bin/python scripts/verify.py --gate offline` (all tests passed)
- [ ] Ran `.venv/bin/pytest tests/`
- [ ] Desktop typecheck and Vitest passed (`npm test` in `desktop/`)
- [ ] Playwright E2E passed (`npx playwright test` in `desktop/`)

## Checklist

- [ ] My code adheres to the project's code style and Decimal financial arithmetic guidelines.
- [ ] I have added tests that prove my fix is effective or that my feature works.
- [ ] I have updated corresponding documentation if appropriate.
- [ ] No private keys, trading functionality, or telemetry are introduced.
