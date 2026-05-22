# 0003 — Use `uv` for Python dependency management

- **Status:** Accepted
- **Date:** 2026-05-22
- **Deciders:** project owner

## Context

The local ingestion phase needs a Python toolchain: a virtual environment, dependency installation, a lockfile for reproducibility, and a way to pin the interpreter version. The Python ecosystem has accumulated half a dozen overlapping tools for this (`pip` + `venv`, `pipenv`, `poetry`, `pdm`, `hatch`, `rye`, `uv`). Picking the wrong one bakes in cost: switching later means regenerating the lockfile, rewriting CI, and updating docs.

Constraints in play: project is **application mode**, not a library — we don't publish to PyPI. We want a committed lockfile so CI and a reviewer's clone resolve to identical versions. We want fast installs (the dev loop matters for portfolio iteration). We want PEP 621-native `pyproject.toml` so the config is portable.

## Decision

We use **`uv`** (Astral) for the Python toolchain on this project. `uv init` creates the project; `uv add <pkg>` manages dependencies and updates `uv.lock`; `uv run <cmd>` executes inside the managed venv; `.python-version` pins the interpreter (currently `3.11`). The lockfile (`uv.lock`) is committed.

## Considered alternatives

- **`pip` + `venv` + `pip-tools`** — works, but requires assembling three tools and writing custom scripts for the lockfile workflow. No standard "compile + sync" verb.
- **Poetry** — mature and widely known, but slower resolver, non-PEP-621 config (its own `[tool.poetry]` table) until recently, and the publishing-focused workflow is overkill for an application.
- **Pipenv** — effectively abandoned in practice; slow resolver; the `Pipfile` format is non-standard.
- **PDM / Hatch / Rye** — all viable; `uv` wins on speed (Rust-based resolver, ~10-100x faster than pip in our tests) and on being a single binary that handles venv + deps + interpreter + script-runner.

## Consequences

- **Positive:** Sub-second dependency installs. Single tool to learn. PEP 621-native `[project]` table in `pyproject.toml` — portable if we ever switch. Lockfile is committed and deterministic across platforms (via `[[package.wheels]]` entries with per-platform hashes).
- **Negative / cost:** `uv` is young (first release 2024) — risk of breaking changes. Smaller community vs Poetry; some Stack Overflow answers don't apply. Reviewers unfamiliar with `uv` need to learn the verbs (`uv add` vs `pip install`, `uv run` vs `python -m`).
- **Follow-ups required:** Document `uv` install + `uv sync` as the onboarding step in the project README when we write it. Mention `uv` explicitly in any CI config so reviewers don't need to guess.

## References

- `uv` docs — https://docs.astral.sh/uv/
- PEP 621 (project metadata in `pyproject.toml`) — https://peps.python.org/pep-0621/
- Astral's positioning post — https://astral.sh/blog/uv
