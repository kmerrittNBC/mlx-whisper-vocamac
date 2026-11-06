# Work Queue

How this repository decides what is next. The contract in one paragraph:
`docs/agents/issue-workflow.toml` names this repository's relationship mode
(`independent`) and its one priority source — the open `type/roadmap` issue
whose `## Goals In Priority Order` section orders the top-level goals. Each
relationship has exactly one authority: an epic's
`## Child Issues In Priority Order` list records **containment**, the goal
order and then each epic's child order record **priority**, a native Gitea
dependency edge records a **prerequisite** ("this must finish before that can
proceed"), and `status/*` labels record **readiness**. Placement never writes
an edge and a prerequisite never changes placement. The gitea-issues
`references/repository-queue.md` reference specifies the full contract.

Goals and epic children use `- [ ] #123 Title` or `- [x] #123 Title`.
Physical order sets priority. A checked entry represents a closed issue with
`status/done`; clicks change only the display and inspection reports any
state disagreement. Numbered lists remain readable until reviewed conversion
through `checklist preview` and guarded `checklist apply`.

## Reading the queue

- **Goals**: `queue goals` — the configured source's ordered goals and its
  version token, without dependency scans.
- **Health and explanations**: `queue inspect` — the relationship model's
  structural, prerequisite, navigation, and ordering findings, and the
  selection.
- **What is next**: `queue next` — read-only goal-first selection: goals in
  priority order, detouring into whatever prerequisite work a goal needs,
  wherever that work is placed. It reports the selected issue's own
  placement apart from the requesting goal and the prerequisite chain.

All three are read-only. Claim separately with `issue start --issue <number>`,
which re-checks the issue's effective prerequisites (its own and every
containing epic's) before creating the `ISSUE-<number>` worktree.

## Changing placement

Placement edits are explicit mutations, never side effects of other work.
Each writes the owning list or lists first, guarded by their
`content_version`, then rewrites the placed issue's derived first-line
`Parent: #<n> <title>` link; a failed line write is reported with its repair
and never retried.

- `queue insert --issue <n> [--position <p>] --expected-content-version <v>` —
  place a top-level epic (or a standalone issue with `--allow-standalone`)
  among the goals; the default position is the top.
- `queue reorder --issue <n> ... --expected-content-version <v>` — rewrite the
  goal order, naming every goal exactly once; no issue body changes.
- `placement set --issue <n> --epic <e> [--position <p>]` — place an issue in
  an epic's child list (the default position is the top), moving it from its
  current list when it has one.
- `placement remove --issue <n> --epic <e>` (or `--top-level`) — leave it
  unplaced; `placement reorder --epic <e> --issue <n> ...` — reorder one
  child list.
- `placement sync-parent --issue <n>` — regenerate a stale `Parent:` line from
  placement; it never moves the issue.

On a stale version or an ambiguous result, re-read (`queue goals` or
`issue read`) and reconcile before issuing a new command; never blindly
re-run a mutation. Replaying a completed or half-completed placement writes
only what is still missing.

## Changing prerequisites

- `prerequisite add --issue <x> --requires <y>` — `x` cannot proceed until
  `y` closes. The edge implies no ownership, placement, or priority.
- `prerequisite remove --issue <x> --requires <y>` — remove that one edge.

Both change edges only and verify the result with a fresh read. A
prerequisite on an epic gates its whole subtree; to gate one child, put the
edge on that child. `epic add-dependency --parent <x> --child <y>` is the
legacy alias of `prerequisite add --issue <x> --requires <y>`, and it refuses
an edge from an epic to its own listed child. `queue link-children` is a
legacy-mode repair and refuses here.

## Who is placed where

Every open work issue has exactly one placement: a top-level goal (a delivery
epic, or a standalone issue admitted explicitly) or one entry in one open
epic's child list. Unplaced work stays visible as an `unplaced-open-issue`
finding with no implicit rank.

## Default placement for new issues

New work with no priority statement from the user enters at position 1 of the
list it belongs to — the goals for an epic or standalone issue, its epic's
child list for a child. There is no dependency ceiling: a dependent may rank
above its own prerequisite, and selection honours the prerequisite by detour.
An explicit statement of priority always wins; genuinely unresolved placement
publishes the issue unplaced.

## After reviewed work merges

`pr cleanup` merges reviewed work and reconciles its issue, then recommends
exactly the `queue next` selection. Dependents the merge unblocked are listed
as information and never outrank goal priority; an epic whose last child
closed is reported as awaiting acceptance, never closed automatically.
Recommendations only — starting the next issue needs its own authorization.
