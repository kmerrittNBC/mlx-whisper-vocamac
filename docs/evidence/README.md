# Design Evidence

This directory holds curated observations and analyses that materially inform
a named, **foundational** product-design decision: a durable choice about
product behavior, architecture, boundaries, core methodology, or a constraint
that shapes the product across individual implementation issues.

It is not an archive. Most changes add nothing here, and completing an issue
never requires an entry.

## Admission

Ask: **would a future maintainer need this record to understand, challenge, or
revisit a foundational product choice after forgetting the implementation
issue?** If the record's value is only establishing that one change passed its
checks, or describing how work proceeded, it belongs with the issue instead.

A qualifying record explains:

- which foundational decision or documented design question it informs;
- what observations bear on the alternatives or constraints, and how;
- why those observations stay useful beyond the issue that produced them.

Purpose decides, not format, rigor, or size. A rigorous measurement, a passing
test suite, or a link to an ADR does not qualify a record on its own, and an
ADR is never created just to give routine verification somewhere to point.

## Where material goes

| Material | Destination |
| --- | --- |
| Current product design, contracts, and constraints | `docs/authoritative/`, per `docs/agents/domain.md` |
| A decision and its concise rationale, including meaningful trade-offs | `docs/authoritative/adr/` |
| Curated observations materially informing a foundational design choice | `docs/evidence/` |
| Durable records of one issue's work: test runs, review findings, debugging chronology, shakedown or replay reports, handoffs | `docs/historical/issue-notes/<issue-number>/` |
| Issue-specific verification that needs no repository archive | the pull request or issue body and comments |

`<issue-number>` is the tracker's issue number: issue 186's retained records
live below `docs/historical/issue-notes/186/`. Create that directory only when
something is worth retaining.

The ADR or authoritative document keeps the "why"; it links here when a
supporting record helps. Evidence informs a decision — it never declares
current behavior or silently overrides the authoritative document. Issue notes
are history, never current truth.

## Examples

Qualifies:

- An evaluation of methodology alternatives behind the product's durable
  grading contract or experimental design.
- A data-quality study that establishes a foundational dataset-selection or
  exclusion policy.
- Accuracy, latency, and resource measurements that explain a core
  model-serving architecture choice.
- A failed experiment or contradictory observation that materially informs such
  a decision, or explains why a serious alternative was rejected.

Does not qualify:

- "Issue 186 passed 260 tests", CI output, coverage summaries, or merge receipts.
- One patch's replay results, admission or qualification receipts, debugging
  logs, an implementation chronology, or an agent handoff.
- A benchmark run, literature collection, or research note with no demonstrated
  connection to a foundational product-design decision.

Mixed purpose: when issue work reveals a foundational insight, leave the
original verification and history where they are, and write a focused
synthesis here that states the design implication and links to those sources.
Do not promote the whole issue diary or duplicate its raw artifacts.

## Record shape

Keep only the provenance that helps someone assess the design implication.
Name files by topic or decision (`serving-latency-trade-offs.md`), not by issue
or test run. There is no required schema; a record usually covers:

```md
# Serving latency trade-offs

Informs: the model-serving architecture (link the ADR or design document).
Date and identities: 2026-03-02; code a1b2c3d, dataset v4, model m-7.

## Observations

What was measured or seen, how, and from which source. Keep large raw
artifacts in their artifact store and reference them by stable location and
hash.

## Interpretation

What the observations suggest for the alternatives, kept separate from the
observations themselves. Include counterevidence.

## Limitations and implications

What the evidence cannot show, and what it means for the design.
```

When a later decision changes the picture, add a linked correction or
superseding analysis rather than rewriting the old result, so its historical
qualifications stay visible. Records need not endorse the currently accepted
choice, but each must stay meaningfully connected to a foundational decision.
