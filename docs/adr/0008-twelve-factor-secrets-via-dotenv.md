# 0008 — 12-factor secrets via `python-dotenv` and fail-fast env loading

- **Status:** Accepted
- **Date:** 2026-05-22
- **Deciders:** project owner

## Context

The ingestion scripts need two API keys (Alpha Vantage, Financial Modeling Prep). The handoff doc this project was scaffolded against hardcodes them in `config.py` — the classic anti-pattern that leaks keys into git history the first time someone commits without re-reading the diff. We need a secrets-handling approach that (a) keeps keys out of source control, (b) gives a clear "missing key" error rather than silently using `None`, and (c) doesn't require running a vault service on the developer laptop (free-tier constraint).

The 12-factor app methodology's "Config in environment variables" pattern is the standard answer for this exact problem.

## Decision

API keys live in environment variables. A gitignored `.env` file at the repo root holds the real values; a committed `.env.example` with angle-bracket placeholders (`<your-alpha-vantage-key>`) advertises the schema. `python-dotenv` loads `.env` into `os.environ` at module-import time in `fintech_datalake/scripts/config.py`. A `_required_env(name)` helper reads each required key via `os.environ[name]` (KeyError on missing) and raises a clear error if the value is empty.

## Considered alternatives

- **Hardcoded keys in `config.py`** (handoff doc pattern) — rejected. One missed `.gitignore` entry and the key is in public history forever; rotating it is the only remediation.
- **Bare `os.environ` with no `.env` loader** — rejected for developer ergonomics. Would force every shell session to `export ALPHA_VANTAGE_API_KEY=...` before running scripts; easy to forget.
- **`os.environ.get(name)` (silent default to `None`)** — rejected. Silent misconfiguration shows up later as a confusing 401 from the API instead of a clear "missing key" error at startup.
- **HashiCorp Vault / AWS Secrets Manager** — rejected. Free-tier project; running a vault locally for two keys is wildly disproportionate.
- **Direnv** — viable but adds an external tool dependency; `python-dotenv` is one `uv add` and works cross-platform identically.

## Consequences

- **Positive:** Keys never touch source control. New contributors copy `.env.example` to `.env`, fill in values, and the scripts work. Missing or empty keys fail at startup with an actionable error, not mid-run.
- **Negative / cost:** `python-dotenv` is one extra dependency. The `.env` file is machine-local — backing up the dev environment requires remembering to grab it.
- **Follow-ups required:** When CI/CD lands (`feat/ci-cd`), GitHub Actions reads keys from `secrets.*` and exposes them as env vars to the workflow — same `os.environ[...]` call sites work unchanged. Terraform (`feat/terraform-bootstrap`) injects the Databricks PAT into GitHub Actions secrets the same way.

## References

- 12-factor methodology, factor III "Config" — https://12factor.net/config
- `python-dotenv` — https://pypi.org/project/python-dotenv/
- `fintech_datalake/scripts/config.py` `_required_env` helper
