# Issue tracker: Gitea

Issues, specs, and pull requests for this repo live on its Gitea host. Use the
deterministic helpers from the `gitea-issues` skill for every operation — never
hand-write API calls. Resolve `<gitea-issues>` from the installed skill path.

## Conventions

- **Read an issue**: `python <gitea-issues>/scripts/gitea.py issue read --issue <number> --comments`
- **List issues**: `python <gitea-issues>/scripts/gitea.py issue list --state open` (add `--label` / `--exclude-label` filters, `--output json` for structure)
- **Create an issue**: `issue create --title "..." --body-file - --label status/ready-for-agent` with the body on standard input, using the `## Problem` / `## Scope` / `## Acceptance Criteria` structure
- **Comment**: `issue comment --issue <number> --body "..."`
- **Change status**: `issue set-status --issue <number> --status status/<role>`
- **Edit classification**: `issue edit-labels --issue <number> --add <label> --remove <label>` (repeat either flag; omit either when unused)
- **Start implementation**: `issue start --issue <number>` — creates the `ISSUE-<number>` branch in a dedicated worktree and prints the path every later command must use
- **Close reviewed work**: `pr cleanup` merges the reviewed pull request and reconciles the issue; `issue close --status status/done` closes an explicitly authorized resolved decision, and `--status status/wontfix` closes declined non-implementation work with a short marker-backed explanation
- **Clean up a merged worktree**: `issue remove-worktree --issue <number> --pull <number>` — fast-forwards local `main` to the fetched remote tip (stopping with resolution commands before any deletion when it cannot) and removes the worktree and its branch

Repository identity comes from the `origin` remote or the resolved credentials;
the helpers never need a token pasted into chat.

Read-only commands (`issue list`, `queue goals|inspect|next`, `epic
next-ready`/`start-next` selection) reuse unchanged reads through a
conditional cache that never touches mutation preflights or read-after-write
verification. Disable it with `GITEA_READ_CACHE=off`, inspect it with
`read-cache status`, and clear it with `read-cache clear`; see the skill's
`references/read-cache.md` for the freshness contract.

## Label vocabulary

Status labels are the agent-writeable source of truth. When a status Project is
configured in `docs/agents/issue-board.toml`, successful lifecycle commands
request card reconciliation through `issue-project-board`. The board displays
status and prerequisites; the roadmap remains the priority source:

`status/needs-triage`, `status/needs-info`, `status/ready-for-agent`,
`status/ready-for-human`, `status/in-progress`, `status/review`,
`status/done`, `status/wontfix`, plus `priority/P0` as an exceptional interrupt
indicator. Type labels (`type/epic`, `type/feature`, `type/bug`, …) and area
labels classify work. Install missing names idempotently with
`labels setup --dry-run` then `labels setup`; existing labels are preserved.
`board/archived` is a non-status label for a closed `status/done` or
`status/wontfix` issue kept searchable outside the status board. Initial board
migration and later selected archival require reviewed previews in
`issue-project-board`; ordinary closure still adds a Done or Won't Fix card.
`board/finalizing` marks an in-progress epic whose listed children are closed
`status/done` while final gates are checked. Other in-progress epics appear in
Active Epics; individual work stays in In Progress. Existing eight-column
boards use the reviewed `issue-project-board` migration.
See `docs/agents/triage-labels.md` for the triage-role mapping and
`docs/agents/queue.md` for the placement and prerequisite contract.

`issue edit-labels` changes only named existing non-status labels, preserving
unrelated labels. It validates every requested name before writing, adds before
removing, and verifies the requested result with a fresh read. A satisfied
replay writes nothing. Use `issue set-status` for `status/*` transitions.
Writes are incremental: after a write or verification failure, reconcile with
`issue read` before retrying. Changing `type/epic` does not create child order,
prerequisite edges, or goal placement; use their separate helper operations.

## The repository work queue

`docs/agents/issue-workflow.toml` puts this repository in `independent`
relationship mode and names its one priority source: the open `type/roadmap`
issue whose `## Goals In Priority Order` section orders the top-level goals.
Goals and epic children use `- [ ] #123 Title` or `- [x] #123 Title`.
Physical order sets priority; checkboxes display confirmed closed
`status/done` progress. Use reviewed `checklist preview` and guarded
`checklist apply` to convert existing numbered lists.
Epic child lists record containment and child priority; native dependency
edges record prerequisites only; `status/*` labels record readiness.

- **Read the goals**: `queue goals` (goal order and version token)
- **Inspect**: `queue inspect` (relationship findings and the selection)
- **Select read-only**: `queue next` (goal-first, detouring into prerequisites)
- **Place**: `queue insert --issue <n> [--position <p>] --expected-content-version <v>` and `queue reorder` for goals; `placement set --issue <n> --epic <e> [--position <p>]`, `placement remove`, and `placement reorder` for child lists; `placement sync-parent --issue <n>` regenerates a stale `Parent:` line
- **Prerequisites**: `prerequisite add --issue <x> --requires <y>` and `prerequisite remove` (edges only, verified by a fresh read); `epic add-dependency --parent <x> --child <y>` is the legacy alias of `prerequisite add --issue <x> --requires <y>` and refuses an epic's edge to its own listed child

Only top-level delivery epics and explicitly standalone issues
(`--allow-standalone`) are goals. When the user has not stated a priority, new
work enters at position 1 of its list, with no dependency ceiling; an explicit
statement always wins. Placement writes the owning list, then the issue's
derived `Parent: #<n>` first line, and never an edge; a prerequisite write
never changes placement. `queue link-children` is a legacy-mode repair and
refuses here. The gitea-issues `references/repository-queue.md` reference
specifies the full contract.

## Pull requests as a triage surface

**PRs as a request surface: no.** _(Set to `yes` if this repo treats external
PRs as feature requests; `/triage` reads this flag.)_

When set to `yes`, external PRs run through the same status labels as issues:
read them with `issue read --issue <number> --comments`, label with
`issue set-status`, and triage contributor PRs (not owner/maintainer work)
through `/triage`.

## When a skill says "publish to the issue tracker"

Create a Gitea issue with `issue create`, then place it explicitly: group
implementation work under a delivery epic — place each child with
`placement set --issue <child> --epic <epic>`, which writes the epic's
`## Child Issues In Priority Order` list and the child's `Parent:` line — and
place only the epic, or an explicitly standalone issue, among the goals with
`queue insert`. Add a `prerequisite add` edge only where one issue genuinely
must finish before another can proceed; containment needs no edge. Creation
and placement stay two separate, reconcilable operations; when the user gave
no priority, place at position 1 and say so with the proposal, and publish
unplaced only when placement is genuinely unresolved.

## When a skill says "fetch the relevant ticket"

Run `issue read --issue <number> --comments`.

## Wayfinding operations

Used by `/wayfinder`. The **map** is a single issue labelled `wayfinder:map`;
its **child tickets** are plain issues that name it with a `Part of #<map>`
body link. Membership is that link alone — no edge joins a ticket to its map.
Maps and tickets are decision work outside the delivery queue: they stay
unplaced (reported as `unplaced-open-issue`, never selected by `queue next`)
unless the owner places them.

- **Map**: `issue create --title "..." --label wayfinder:map` holding the Notes / Decisions-so-far / Fog body.
- **Child ticket**: an issue labelled `wayfinder:<type>` (`research`/`prototype`/`grilling`/`task`) with `Part of #<map>` at the top of its body.
- **Blocking**: Gitea dependency links between tickets only — `prerequisite add --issue <ticket> --requires <blocker>` when one ticket's decision genuinely waits for another's. `issue read` reports open blockers, which are the live gate.
- **Frontier query**: `issue list --state open --label wayfinder:map`-scoped children (list open issues, keep those mentioning `Part of #<map>`), drop any with an open blocker or `status/in-progress`; first in map order wins.
- **Claim**: move the ticket to `status/in-progress` with `issue set-status`.
- **Resolve**: `issue comment --issue <n> --body "<answer>"`, then use `issue close --issue <n> --status status/done --comment "Decision accepted; see the resolution comment."` for an explicitly authorized accepted decision; use `status/wontfix` for declined work and `pr cleanup` for PR-backed implementation. Gist the decision into the map's Decisions-so-far.
