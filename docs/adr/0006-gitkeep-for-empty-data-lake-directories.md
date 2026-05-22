# 0006 — Use `.gitkeep` to commit empty data-lake directories

- **Status:** Accepted
- **Date:** 2026-05-22
- **Deciders:** project owner

## Context

Git tracks files, not directories. Empty directories are invisible to commits, but the data lake structure (`fintech_datalake/bronze/{alpha_vantage,fmp}/`, `silver/`, `gold/`, `logs/`) is meaningful to a reviewer cloning the repo — it advertises the layered architecture before any data has been ingested. We also need every file inside those data directories to be **gitignored** (Bronze JSON blobs, Silver Delta files, ingestion logs — none of that belongs in source control).

Two patterns can preserve an empty directory in git while ignoring its contents:

1. Place a sentinel file (`.gitkeep`) inside each directory and commit it.
2. Use `.gitignore` rules with negation: ignore everything under the directory except itself.

Option 2 has a well-known gotcha: git's directory-exclusion rule. A pattern like `fintech_datalake/bronze/**` excludes the directory itself from traversal, so even `!.gitkeep` won't recover it. The workaround is `**` plus `!**/` (un-ignore directories) plus `!.gitkeep`, which is fragile and surprises reviewers reading the `.gitignore`.

## Decision

We use **`.gitkeep` sentinel files**, one per empty data-lake directory. The root `.gitignore` ignores actual data files via simple patterns (`fintech_datalake/bronze/**/*.json`, `fintech_datalake/logs/*.jsonl`, etc.). The `.gitkeep` files are explicitly named with no negation rules required.

`.gitkeep` is a convention, not a git feature — the filename has no special meaning. We picked it over `.keep` or `.placeholder` because it's the de-facto standard in the Python and data-engineering ecosystems.

## Considered alternatives

- **`.gitignore` with negation patterns (`**`, `!**/`, `!.gitkeep`)** — rejected. Initially attempted; produced confusing behavior during `feat/ingest-scaffold` (the `git check-ignore` exit code misled the user into thinking `.env` was tracked when it wasn't). The pattern is correct but hard to reason about; `.gitkeep` is correct and easy.
- **Generate the directory structure at runtime from a script** — rejected. Removes the visible-on-clone signal that the medallion architecture exists. A reviewer browsing the repo on GitHub wouldn't see the layout without running code.
- **README.md in each directory** — rejected. Mixes documentation with structural intent; we'd then need rules about what those READMEs should say. `.gitkeep` is zero-content and unambiguous.

## Consequences

- **Positive:** `git status` is clean and predictable. Reviewers see the medallion layout immediately on clone. The `.gitignore` reads as a flat list of "what files we don't want," with no negation gymnastics.
- **Negative / cost:** Five extra zero-byte files in the repo (one per data-lake directory). Reviewers occasionally ask "what is `.gitkeep`?" — answered in a single sentence.
- **Follow-ups required:** None. The pattern is enacted by the existing `.gitkeep` files and the simple `.gitignore` rules.

## References

- Git's directory-exclusion rule — https://git-scm.com/docs/gitignore (search for "directory")
- `.gitkeep` is a convention, not a git feature — https://stackoverflow.com/q/7229885
- Plan file 2026-05-17 entry documenting the negation-pattern dead end
