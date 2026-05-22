# 0005 — LEARNING MODE: the user types every line of project source code

- **Status:** Accepted
- **Date:** 2026-05-22 (originally locked 2026-05-14)
- **Deciders:** project owner

## Context

This is a portfolio project. The artifact a reviewer cares about is *not just the code* — it's the user's ability to explain every architectural and implementation decision in a job interview. Code an AI generated that the user can't defend on whiteboard is worse than no code at all: it signals reliance on tooling rather than understanding.

At the same time, Claude Code is genuinely useful for this kind of build — it can explain library quirks, verify syntax, suggest production-grade patterns, and catch bugs. The question isn't whether to use it; it's how to use it without short-circuiting the learning loop.

## Decision

Claude **does not** write or create any project source files directly. Project source includes `*.py`, `*.toml`, `*.yml`, `.gitignore`, `.env*`, SQL models, and any file that ships as part of the deliverable. The user types every line of those files themselves.

Claude's role is bounded to: explaining a concept, showing reference shapes (≤30 lines for algorithmic code, up to ~80 lines for pure data/config), annotating decisions in the reference shape, running verification commands, and reading output. Work proceeds in small phases — a 30-line file is built in ~5 checkpoints with verification between each, not pasted in one shot.

**Exceptions** (Claude edits these directly): plan files at `~/.claude/plans/`, `CLAUDE.md`, and `docs/adr/*.md` (because ADRs are documentation about decisions, not the deliverable itself, and the user reviews and edits to voice).

## Considered alternatives

- **Claude writes code; user reviews diffs** — rejected. Review-only comprehension is shallow; you don't notice idioms you didn't have to invent. The user explicitly tested this on PR #1 (dbt scaffold, mostly Claude-generated) and reported that they couldn't explain key choices a week later.
- **Pair-programming free-form (no formal mode)** — rejected. Without a written rule, Claude defaults to "write the code when asked" and the loop degrades silently. The rule has to be explicit so it survives across sessions and worktrees.
- **No AI assistance at all** — rejected. The verification, doc-walk, and pattern-explanation tasks are where Claude adds the most value per minute, and skipping them would slow the project to a halt for no portfolio benefit.

## Consequences

- **Positive:** Every line in the repo is something the user can explain. Discovery of subtle issues (e.g., the `git check-ignore` exit-code misunderstanding, the `outputsize=full` premium policy change, the FMP 85-ticker allowlist) happened *because* the user typed and re-ran rather than copy-pasting.
- **Negative / cost:** Build velocity is ~3-5x slower than an AI-write-everything workflow. A 30-line file takes a 90-minute session, not 5 minutes. Tradeoff accepted because the velocity isn't the bottleneck; *durable understanding* is.
- **Follow-ups required:** Response-style rules in `CLAUDE.md` (locked 2026-05-20) enforce reference-shape size limits, mandatory annotation tables, API-cost discipline, and verification-first cadence. Those are the operationalization of this ADR.

## References

- `CLAUDE.md` — "Working Style for This Project — LEARNING MODE"
- `CLAUDE.md` — "Response Style for LEARNING MODE Teaching"
- Plan file `~/.claude/plans/resuming-feat-ingest-scaffold-work-on-shimmering-kazoo.md` — concrete evidence of the checkpoint cadence
