# 0001 — Record architecture decisions in MADR format

- **Status:** Accepted
- **Date:** 2026-05-22
- **Deciders:** project owner

## Context

This is a portfolio project intended to demonstrate MAANG-grade data engineering practice on a free-tier stack. A reviewer reading the repo cold needs to see *why* we made specific choices (uv over poetry, DLT for Silver, FMP as primary daily-price source, etc.) — not just the resulting code. Several non-obvious decisions have already been made during the `feat/ingest-scaffold` phase (free-tier policy changes, ticker substitutions forced by FMP's 85-ticker allowlist, AV downgraded to cross-validation, atomic writes, JSONL audit logs). Without a durable record, that reasoning will be lost the moment the conversation transcript falls out of context.

Architectural Decision Records (ADRs) are the industry-standard answer: short, append-only, version-controlled markdown files that capture one decision each.

## Decision

We record every significant architectural decision in this repo as an ADR under `docs/adr/`, using the MADR (Markdown Any Decision Records) 4.0 format. Files are named `NNNN-kebab-case-title.md` with a four-digit zero-padded sequence. The template lives at `docs/adr/0000-template.md`. ADRs are **immutable once accepted** — corrections happen by writing a new ADR that supersedes the old one, never by editing history.

## Considered alternatives

- **No formal record** — relied on commit messages and `CLAUDE.md`. Rejected: commit messages explain *what changed*, not *why we chose X over Y*; `CLAUDE.md` is a single growing file with no version-aware structure.
- **Y-Statements / Nygard's original ADR format** — simpler but less prescriptive about alternatives and consequences. MADR's "Considered alternatives" section is the part that most rewards portfolio review.
- **Confluence / Notion / external wiki** — kills the "read the repo cold" property. ADRs belong next to the code they justify.

## Consequences

- **Positive:** Reviewers can audit the reasoning behind every non-obvious choice. Future-me has a paper trail when revisiting decisions in a year. The `docs/adr/` directory itself signals engineering maturity.
- **Negative / cost:** Every meaningful architectural choice now incurs ~15 minutes of writing overhead. Risk of stale ADRs if we forget to supersede when reversing a decision.
- **Follow-ups required:** Backfill retroactive ADRs for decisions already made during `feat/ingest-scaffold` (this branch — ADRs 0002 through 0007). Add a "Decision Log" link from `CLAUDE.md` to `docs/adr/`. CI should fail PRs that change architecture without touching `docs/adr/` (deferred to `feat/ci-cd`).

## References

- MADR 4.0 specification — https://adr.github.io/madr/
- Michael Nygard's original ADR essay — https://cognitect.com/blog/2011/11/15/documenting-architecture-decisions
- Per-branch plan files at `~/.claude/plans/` for finer-grained operational state
