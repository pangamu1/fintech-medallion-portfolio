# 0004 — Initialize the Python project in application mode, not package mode

- **Status:** Accepted
- **Date:** 2026-05-22
- **Deciders:** project owner

## Context

`uv init` supports two layouts:

- **Application mode** (`uv init`, default) — flat layout. No `src/` directory, no `[build-system]` table, no `[project.scripts]` entry points. `pyproject.toml` has only `[project]` and `[tool.uv]`.
- **Package mode** (`uv init --package`) — produces a publishable layout: `src/<package_name>/__init__.py`, a `[build-system]` table backed by hatchling, optional entry points.

The two are not interchangeable after the fact — switching from application to package mode (or back) means restructuring the source tree and `pyproject.toml`. We picked at `uv init` time and we live with it.

The ingestion scripts in this project are **never installed into another project** and **never published to PyPI**. They're run via `uv run python fintech_datalake/scripts/ingest_alpha_vantage.py` directly from the repo. The artifact is the *data lake on disk*, not a Python wheel.

## Decision

We initialized the project with plain `uv init` — application mode. No `src/` directory; the package layout is `fintech_datalake/scripts/*.py` directly under the repo root. The `pyproject.toml` deliberately has no `[build-system]` table and no `[project.scripts]` entry points.

## Considered alternatives

- **`uv init --package`** — rejected. Would force a `src/fintech_datalake/scripts/` layout, add a `[build-system]` table referring to hatchling, and require us to either install the package into the venv (`uv pip install -e .`) before running, or invoke modules via `python -m`. None of that buys us anything because we don't publish.
- **Bare `pip install -r requirements.txt` workflow with no `pyproject.toml`** — rejected. Loses the lockfile (see [ADR 0003](0003-uv-for-python-dependency-management.md)) and the structured project metadata.

## Consequences

- **Positive:** Simpler `pyproject.toml` (fewer lines a reviewer needs to read). Scripts run from the repo root with no install step. `import fintech_datalake.scripts.config` works directly because Python adds the CWD to `sys.path`.
- **Negative / cost:** If we ever want to publish or vendor this as a library into another project, we'll need to restructure. Mitigation: that's not on the roadmap; if it happens, it's worth the cost at that point.
- **Follow-ups required:** None. The decision is enacted by the existing `pyproject.toml` shape.

## References

- `uv init` docs — https://docs.astral.sh/uv/concepts/projects/init/
- Difference between application and library projects — https://docs.astral.sh/uv/concepts/projects/init/#applications
- [ADR 0003](0003-uv-for-python-dependency-management.md) — uv choice
