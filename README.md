# Rider recruitment acceptance vertical slice

A runnable local demonstration for selected acceptance paths across ClawHunt tasks #1804-#1808. This is a **vertical slice, not a complete or production system**. Use synthetic data only.

## Quick start (PowerShell)

```powershell
python -m pip install -r requirements.txt
python serve.py
```

Open `http://127.0.0.1:8765`. The UI talks to the local FastAPI service; state is stored in SQLite. Default demo capacity is five and is local-only.

## Reproduce checks

In another terminal, run the deterministic suites:

```powershell
python verify.py
```

For the full browser pass, start `python serve.py` in one terminal and run in another:

```powershell
$env:RUN_BROWSER_E2E='1'
python verify.py
```

Playwright Chromium is required (`python -m playwright install chromium`). The browser check covers 375/390/414 widths, 150% text, consent, 7/7 registration, booking, revocation/deletion, and offline failure with input retention. Set `RIDER_DEMO_DB` to an isolated path before starting the server.

Expected results: core 9, workflow/dashboard 10, API 8; browser E2E prints `PASS`. Dashboard reconciliation uses a fixed seed and 12,000 synthetic events; SQL totals are checked against independent Python aggregation.

## Evidence by task

- #1804: persistent append-only audit rows have a hash-chain verification endpoint; tampering identifies the failing sequence. Demo lead rows store keyed tokens rather than raw phone/name. This is not an encryption vault or production key management.
- #1805: fixed-seed 12,000-event synthetic dataset; Python and independent SQL metrics reconcile exactly. 144 parameter combinations reject PII fields/grouping/filters and assert no data is returned for rejected requests. `/api/v1/metrics` remains aggregate-only.
- #1806: explicit status transition graph, normalized-phone lead deduplication, atomic 5-seat booking, and signed idempotent event outbox. Tests reject illegal transitions, duplicate events, and altered payload signatures.
- #1807: local H5 flow passes Playwright at 375/390/414 widths and 150% root text size; offline API action is blocked without losing input. Static shell is cached, not offline application data.
- #1808: consent gate, seven-slot parser, minor-stop path, and Unicode/zero-width phone masking variants are exercised.

## Explicit limits

- SQLite and in-memory core are a local mock, not PostgreSQL 16/pgvector/Redis/KMS or a production deployment.
- No authentication/RBAC, encryption vault, production retention service, real LLM, real policy corpus, or production integrations.
- The slot parser is a deterministic demo grammar, not natural-language extraction. No accuracy claim is made.
- The API persists a SHA-256 hash-linked audit chain and detects row edits, but the SQLite file is not immutable against a privileged database writer; this is tamper-evident, not a signed or externally anchored audit log.
- No CI, external load test, or security review is claimed.

Do not submit real applicant information to this demo.
