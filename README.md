# Rider recruitment acceptance vertical slice

A runnable local demonstration for selected acceptance paths across ClawHunt tasks #1804-#1808. This is a **vertical slice, not a complete or production system**. Use synthetic data only.

## Quick start (PowerShell)

```powershell
python -m pip install -r requirements.txt
python serve.py
```

Open `http://127.0.0.1:8765`. The UI talks to the local FastAPI service; state is stored in SQLite. Default demo capacity is five and is local-only.

## Reproduce checks

In another terminal:

```powershell
python run_tests.py
python -m unittest test_api -v
python e2e.py
```

`e2e.py` requires Playwright Chromium (`python -m playwright install chromium`) and the server running. It runs at 390x844 and verifies consent gate, registration through 7/7, booking, revocation/deletion, and no browser page errors. The server uses `RIDER_DEMO_DB` if set, allowing an isolated clean database.

Expected results: core 9/9; API 4/4 (including 10 concurrent booking attempts for 5 seats, exactly 5 success/5 conflict); browser E2E prints `PASS`.

## Evidence by task

- #1804: consent revocation removes session and related booking; an audit event is retained. PII masking is applied before returning downstream/model input.
- #1805: `/api/v1/metrics` returns aggregate counts only; response excludes personal fields.
- #1806: SQLite `BEGIN IMMEDIATE` protects allocation; uniqueness prevents duplicate session/station booking.
- #1807: actual local H5 UI runs the consent, 7-slot progress, appointment, and revoke flow in Playwright at mobile viewport.
- #1808: consent gate, seven slot parser, minor-stop path, and PII mask are exercised.

## Explicit limits

- SQLite and in-memory core are a local mock, not PostgreSQL 16/pgvector/Redis/KMS or a production deployment.
- No authentication/RBAC, encryption vault, production retention service, real LLM, real policy corpus, or production integrations.
- The slot parser is a deterministic demo grammar, not natural-language extraction. No accuracy claim is made.
- The audit endpoint path records event/subject token, but this API demo does not yet persist a cryptographic hash chain; the core in-memory test does detect tampering.
- No CI, external load test, or security review is claimed.

Do not submit real applicant information to this demo.
