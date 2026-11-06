## Agent skills

### Issue tracker

Gitea issues, driven by the `gitea-issues` helpers.
See `docs/agents/issue-tracker.md`.

### Triage labels

Canonical role names mapped to this tracker's label strings.
See `docs/agents/triage-labels.md`.

### Domain docs

single layout: CONTEXT.md and ADRs live per `docs/agents/domain.md`.

### Work queue

Priority lives in the `type/roadmap` issue's ordered queue; see `docs/agents/queue.md`.

### Working standards

Docs and tests are first-class artifacts; the tracker is the queue, repository
documents the durable memory. Read the issue's epic and related issues
before planning; build test-first at the spec's pre-agreed seams; record each
change's documentation disposition and the evidence behind its merge; commands
presented as runnable must be ready to run as written. See
`docs/agents/standards.md`.

### Focused checks

`make check`

Run on the exact current head during implementation and review follow-ups;
any later change makes this evidence stale.

### Epic gate

`make check`

The complete gate, reserved for final epic acceptance — run once on the exact
integrated commit.
