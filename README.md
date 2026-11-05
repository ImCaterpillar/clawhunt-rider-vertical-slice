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

Playwright Chromium is required (`python -m playwright install chromium`). The browser check covers 375/390/414 widths, 150% text, consent, 7/7 registration, booking, revocation/deletion, and a 10-second offline interval followed by page reload, session restoration, queued submission, and progress restoration. Set `RIDER_DEMO_DB` to an isolated path before starting the server.

Expected results: core 9, workflow/dashboard 10, acceptance fixtures 8, API 8; browser E2E prints `PASS`. Dashboard reconciliation uses a fixed seed and 12,000 synthetic events; SQL totals are checked against independent Python aggregation. Acceptance fixtures provide deterministic examples for the five task areas; they do not claim these mocked components meet production or full acceptance requirements.

## Evidence by task

- #1804: persistent hash-linked audit tamper check; demo lead rows store keyed tokens. A generated 240-positive-case phone masking fixture reports recall and explicitly states false-positive rate is unmeasured. It does not implement tokenize/detokenize vault, key rotation, name/address evaluation, RBAC, retention jobs, or OWASP evidence.
- #1805: fixed-seed 12,000-event synthetic dataset; Python and SQL metrics reconcile; query whitelist is exercised with PII fields/groups/filters. In-memory configuration fixture demonstrates second-person approval, version rollback, model-visibility export flags, and CSV watermark/audit receipt. No dashboard UI, five-way funnel suite, durable config service, or production export audit exists.
- #1806: status transition graph, normalized lead deduplication, atomic SQLite 5-seat booking (API concurrency test: 10 contenders), signed idempotent outbox, bounded mocked retry, and a separate 50-contender/5-seat lock fixture. Generated CSV fixture imports 100 rows to 90 unique keys. No retry worker, staff UI, detokenize flow, per-person watermark, or deployed load test exists.
- #1807: local H5 flow passes Playwright at 375/390/414 widths and 150% root text size. It now checks 10 seconds offline, reload, local session restoration, queued input retry, and restored server progress. Browser localStorage is demo-only and not a secure session-token design.
- #1808: consent gate, seven-slot parser, minor-stop path, and Unicode/zero-width phone masking; synthetic 300-case policy fixture demonstrates cited mock answers, unknown/injection handoff. It is template-based, not a real policy corpus, independent evaluation, secure prompt-injection control, or primary/backup LLM integration.

## Explicit limits

- SQLite and in-memory core are a local mock, not PostgreSQL 16/pgvector/Redis/KMS or a production deployment.
- No authentication/RBAC, encryption vault, production retention service, real LLM, real policy corpus, or production integrations.
- The slot parser is a deterministic demo grammar, not natural-language extraction. No accuracy claim is made.
- The API persists a SHA-256 hash-linked audit chain and detects row edits, but the SQLite file is not immutable against a privileged database writer; this is tamper-evident, not a signed or externally anchored audit log.
- No CI, external load test, or security review is claimed.

Do not submit real applicant information to this demo.
