# Work Queue

How this repository decides what is next. The contract in one paragraph: exactly
one open issue labelled `type/roadmap` carries a `## Work Queue In Priority
Order` section; that order — with epic `## Child Issues In Priority Order`
sections beneath it — is repository priority. Dependency links gate execution;
status labels gate readiness. Neither ever overrides the written order. The
queue tree carries one invariant — every open issue except the roadmap itself
sits on exactly one priority list and blocks that parent — specified in full
in the gitea-issues `references/repository-queue.md` reference. Every open
direct child of the roadmap — epic or standalone entry — blocks the roadmap,
one edge per direct child and never edges to the whole backlog, so the Gitea
UI **Blocks** section links each level of the tree to the root.

Priority lists use `- [ ] #123 Title` and `- [x] #123 Title`. Physical order
sets priority; the checkbox is a progress display. A checked entry represents
a closed issue with `status/done`, including an epic accepted and closed
separately. `status/wontfix` and historical closed issues without
`status/done` stay unchecked. `queue inspect` reports disagreements; clicks
never change readiness, closure, or prerequisites. Convert numbered lists
through reviewed `checklist preview` and guarded `checklist apply`.

## Reading the queue

- **Health and explanations**: `queue inspect` — status counts, skipped
  entries, unqueued ready work, tree-invariant violations, structural
  anomalies.
- **Placement and reconciliation**: `queue roadmap` — targeted top-level order
  and current `content_version`, without dependency scans.
- **What is next**: `queue next` — read-only selection of the highest-priority
  executable leaf, with every higher-ranked skip explained.

Both are read-only. Inspecting never claims anything; claim separately with
`issue start --issue <number>`, which creates the `ISSUE-<number>` worktree and
moves the issue to `status/in-progress`.

## Changing the queue

Queue edits are explicit mutations, never side effects of other work:

- `queue init` — create the canonical roadmap if absent (idempotent).
- `queue insert --issue <n> --position <p> --expected-content-version <v>` —
  add a top-level epic, or a standalone issue with `--allow-standalone`.
  Inserting an open entry — epic or standalone — also links it as blocking
  the roadmap (reported separately from the body write).
- `queue reorder --issue <n> ... --expected-content-version <v>` — rewrite the
  top-level order, naming every current entry exactly once.
- `queue link-children preview` / `apply --confirm` — classify and repair the
  direct-child blocking edges to the roadmap (read-only preview; confirmed
  apply creates exactly the missing edges, streaming `[queue]` progress
  milestones with the terminal summary and exit status authoritative).

Mutations send the optimistic-locking `content_version` printed by `queue roadmap`.
On any ambiguous result, re-run `queue roadmap` and reconcile before retrying;
never blindly re-run a mutation.

## Adopting existing epics

Epics created before this contract may carry legacy child-order sections.
`epic migrate-children preview` inventories them read-only and classifies each
open epic; the owner confirms each proposed migration, and
`epic migrate-children apply --epic <n> --expected-content-version <v>`
rewrites one epic at a time under the queue contract's rules. Ambiguous epics
go back to the owner with their diagnostics. The gitea-issues
`references/repository-queue.md` reference documents the full contract.

## Moving to independent mode

In `legacy` mode, which this document describes, a native edge may mean
containment, navigation, or a prerequisite. A repository moves to
`independent` mode — edges mean prerequisites only — through a reviewed
migration, never a setup rerun: `migration preview --history --write-plan <file>` classifies every
edge read-only, the owner reviews the plan, `migration freeze` makes every
roadmap-driven helper fail closed, `migration apply --plan <file>` removes
only the projection edges the evidence proves and writes each placed
issue's `Parent:` line, `migration readiness` confirms nothing blocks, and a
reviewed commit of `relationship_mode = "independent"` activates it. The
gitea-issues `references/repository-queue.md` reference documents recovery
and rollback.

## Who enters the roadmap

Only two kinds of issue: a top-level delivery epic, and an explicitly
standalone actionable issue. Epic children never enter the roadmap — they stay
in the epic's child-priority list plus dependency links, under the
queue-tree invariant stated above.

## Default placement for new issues

Newly published work with no priority statement from the user enters at the
default position — the highest its dependencies allow, per the default rule
in the gitea-issues `references/create-and-organize.md` queue-placement
contract; an explicit statement from the user always wins. Creation and
placement remain two explicit, reconcilable operations either way, and
genuinely unresolved placement still publishes unqueued and stays visible
under "Unqueued ready work".

## After reviewed work merges

`pr cleanup` merges reviewed work and reconciles its issue. Continuation then
recommends exactly one follow-up, in order: newly unblocked dependents, the
current epic's next executable child, the roadmap's next executable leaf, or an
explicit blocked/empty result. Recommendations only — starting the next issue
needs its own authorization.
