# Rider recruitment vertical slice (local mock)

A small, runnable cross-task acceptance slice for ClawHunt tasks #1804-#1808.
This is **not** a production service and does not claim full task completion.

## Run

```powershell
python run_tests.py
python demo.py
```

Tests exercise consent gating, PII masking before processing, seven-slot progress,
minor termination, local-data clearing on consent revocation, 50 concurrent
bookings for five seats, duplicate-booking rejection, audit-chain tamper detection,
and aggregate-only output.

Expected: `Ran 9 tests ... OK`; demo shows `progress: 7/7`, valid audit chain,
and aggregate fields only.

## Scope and limitations

- Uses in-memory mocks; no FastAPI, PostgreSQL, Redis, React/H5, pgvector, KMS,
  persistent audit storage, or real external integrations.
- AES encryption, production authorization, retention jobs, network security,
  model evaluation, CI, and production load tests are not implemented here.
- The phone token is deterministic HMAC with a demo-only secret; it is not a
  production vault. The session grammar is a test harness, not an NLP engine.
- Synthetic values only; never put real applicant information in this demo.

This package demonstrates a few cross-task invariants that run locally and is
intended as evidence of a vertical slice, not a substitute for the full contract.
