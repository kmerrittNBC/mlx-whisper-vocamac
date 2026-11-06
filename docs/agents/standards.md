# Working Standards

The philosophies every session in this repository works under. The
`## Agent skills` block in the agent instructions carries the one-line rules;
this document is the authority behind them and is safe to extend per repo.

## Documentation and tests are first-class artifacts

Code may be replaced, but durable decisions, behavior, and lessons must remain
recoverable from focused documentation and verification artifacts. A future
agent with no conversation history should be able to determine:

- what the system currently does;
- which behavior is only proposed, not implemented;
- why important architectural decisions were made, and which observations
  informed the foundational ones (`docs/evidence/`);
- how to verify implemented behavior;
- which earlier approaches are retained only for context (`docs/historical/`).

## Documents versus the issue tracker

The issue tracker is the queue for actionable work and holds the transient
working context of one change; repository documents are the durable memory. A
closed issue thread is not a supported reference for current behavior. When an
issue resolves a term or a decision, record it in `CONTEXT.md` or an ADR
rather than leaving it only in the thread; an idea too valuable to lose and
not actionable enough to be an issue belongs in the domain documents, not in
an issue comment.

Before addressing an issue, read the issue with its comments, every other
issue in its epic, and the issues in related epics. Confirm scope, boundaries,
and dependencies before planning.

## Writing current-truth documents

`CONTEXT.md` and the ADRs describe what the system does, in present tense, as
a contract — not a narrative of the change that produced them.

- Test every sentence carrying an issue reference by deleting the number: if
  the sentence stays true, the reference was decoration and goes; if it stops
  making sense, rewrite it as a statement of current behavior. ADRs keep
  their references — they are decision records.
- ADRs are immutable. Never rewrite a decided ADR; mark it superseded and
  record the replacement decision in a new ADR that links back.
- State uncertainty explicitly, and label proposed behavior as proposed.
- When verified behavior lands, reconcile `CONTEXT.md` and the ADRs in the
  same iteration. Never document behavior that does not exist yet.

## Historical records

`docs/historical/` holds superseded designs, archived handoffs, and
development records. Use it to understand how the project arrived at its
current state; never treat it as current behavior. When reconciling
documents after verified behavior lands, move superseded context that still
explains decisions or discarded alternatives to `docs/historical/` rather
than deleting it. Decisions themselves supersede through the ADR mechanism,
not by moving.

## Design evidence and issue history

Choose a record's destination by its purpose, not its format, rigor, or size:

- `docs/evidence/` holds only curated observations that materially inform a
  named foundational product-design decision and stay useful after the
  implementation issue is forgotten. Its `README.md` carries the admission
  rule, examples, and a lightweight record shape.
- `docs/historical/issue-notes/<issue-number>/` holds durable records of one
  issue's work — test runs, review findings, debugging chronology, shakedown
  or replay reports, handoffs — created only when worth retaining.
- The pull request or issue holds issue-specific verification that needs no
  repository archive.

The ADR or authoritative document keeps the decision and its concise
rationale and may link supporting evidence. Evidence never declares current
behavior, and issue notes are history, never current truth. A routine change
needs no new document, directory, or evidence record; an ADR link alone does
not make verification qualify as evidence.

## Documentation disposition

The implementing session records one documentation disposition on the issue
or pull request before completion — in an issue comment on trackers without a
pull-request template. On Gitea, `/cleanup` blocks the merge without one.

`CONTEXT.md` and ADRs are created lazily (see `docs/agents/domain.md`): a
change that resolves no new term or decision records `not_required` rather
than forcing a document into existence.

- **updated** — verified behavior was reconciled into `CONTEXT.md` and the
  ADRs as present-tense contracts;
- **not_required** — the change made no durable behavioral or architectural
  difference; say why in one line;
- **deferred** — documentation work remains; normal completion waits unless
  the owner explicitly accepts the deferral;
- **blocked** — documentation cannot be reconciled because implementation or
  verification evidence is insufficient.

## Build discipline

Tests are part of the specification. Write the failing test first at the
spec's pre-agreed seams and make it green with the minimal change — red
before green, one seam, one test per cycle. Test-after is reserved for glue
and wiring, UI verified by a manual test plan, and throwaway prototypes.

## Verification cadence

During implementation and review follow-ups, run the focused checks for the
changed areas and their immediate contracts or consumers, on the exact
current head. A later code, test, configuration, or documentation change
invalidates the affected evidence and requires those checks again.

Reserve the complete gate declared as the epic gate for the final integrated
epic commit, before epic acceptance and closure. Existing successful CI
satisfies it only when bound to that exact commit. Run a repository-wide
suite earlier only when explicitly requested, when a failure cannot be
localized, or when a change to shared test infrastructure, root
configuration, or a foundational contract has an unbounded blast radius — and
state the reason before starting it.

Do not delete, weaken, skip, or consolidate tests solely to reduce runtime.
Pruning is legitimate only with evidence that the coverage is obsolete or
redundant, the behavior preserved at the lowest faithful layer, and the
verification documentation updated.
When automated coverage is not practical for an enduring contract, record a
repeatable manual procedure and its expected result beside that contract.

## Merge evidence

Every pull request carries the evidence that caused it to be merged, recorded
before the merge: screenshots for a visible interface, brief command output
for command-line behavior, the focused checks that passed and the exact head
they ran against when the effect is not observable through any interface.
Attribute a reported observation to whoever made it rather than presenting it
as independently verified, and never attach evidence that was not examined.
An unrecorded verification did not happen. Merge evidence lives on the pull
request (or under `docs/historical/issue-notes/<issue-number>/` when worth
retaining); it is not a `docs/evidence/` record.

## Commands given to the user

A command presented as runnable must be ready to run as written — no
unresolved placeholder such as `/absolute/path/to/...`, `<your-token>`, or an
unassigned `$VALUE`. When a value cannot be known while drafting, give the
exact command that discovers it, then the command that consumes it, and say
how to substitute the result. Use the repository's documented shell where it
declares one; otherwise prefer POSIX-compatible syntax.
