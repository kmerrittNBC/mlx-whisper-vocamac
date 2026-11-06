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

Read-only commands (`issue list`, `queue roadmap|inspect|next`, `epic
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
`docs/agents/queue.md` for the roadmap contract.

`issue edit-labels` changes only named existing non-status labels, preserving
unrelated labels. It validates every requested name before writing, adds before
removing, and verifies the requested result with a fresh read. A satisfied
replay writes nothing. Use `issue set-status` for `status/*` transitions.
Writes are incremental: after a write or verification failure, reconcile with
`issue read` before retrying. Changing `type/epic` does not create child order,
blocking edges, or roadmap placement; use their separate helper operations.

## The repository work queue

Exactly one open issue labelled `type/roadmap` holds the
`## Work Queue In Priority Order` section that defines repository priority;
epics order children the same way. Each list entry uses `- [ ] #123 Title` or
`- [x] #123 Title`; checkboxes display closed `status/done` progress and do
not change workflow state. `queue inspect` reports disagreements. Convert
numbered lists only through reviewed `checklist preview` and guarded
`checklist apply`. Dependencies gate execution; they never define priority.

- **Inspect**: `queue inspect` (health, skipped entries, tree-invariant violations, selected leaf)
- **Read placement state**: `queue roadmap` (top-level order and content version)
- **Select read-only**: `queue next`
- **Maintain**: `queue init` (idempotent), `queue insert --issue <n> --position <p> --expected-content-version <v>`, `queue reorder`, `queue link-children preview` / `apply --confirm` (direct-child blocking edges)
- **Move to `independent` mode**: the reviewed edge migration — `migration preview --history --write-plan <file>`, `migration freeze`, `migration apply --plan <file>`, `migration readiness`, then a reviewed configuration commit (see the gitea-issues `references/repository-queue.md`)

Only top-level delivery epics and explicitly standalone issues
(`--allow-standalone`) enter the roadmap. When the user has not stated a
priority, new work enters at the default position from the gitea-issues
queue-placement contract — the highest its dependencies allow — and an
explicit statement always wins. The queue tree carries one
invariant — every open issue except the roadmap itself sits on exactly one
priority list and blocks that parent — specified in full in the gitea-issues
`references/repository-queue.md` reference. Inserting an open entry — epic or
standalone — links it as blocking the roadmap, so the Gitea UI **Blocks**
section links each level to the root; the roadmap never takes dependency
edges beyond its direct children (its queue entries). `queue link-children`
repairs missing direct-child edges.

## Pull requests as a triage surface

**PRs as a request surface: no.** _(Set to `yes` if this repo treats external
PRs as feature requests; `/triage` reads this flag.)_

When set to `yes`, external PRs run through the same status labels as issues:
read them with `issue read --issue <number> --comments`, label with
`issue set-status`, and triage contributor PRs (not owner/maintainer work)
through `/triage`.

## When a skill says "publish to the issue tracker"

Create a Gitea issue with `issue create`, then place it explicitly: group
implementation work under a delivery epic (children linked with
`epic add-dependency --parent <epic> --child <child>`, the legacy alias of
`prerequisite add --issue <epic> --requires <child>`, and ordered in the epic's
`## Child Issues In Priority Order` section) and insert only the epic — or an
explicitly standalone issue — into the roadmap with `queue insert`. Creation
and placement stay two separate, reconcilable operations; when the user gave
no priority, apply the default-placement rule from that contract and say so
with the proposal, and publish unqueued only when placement is genuinely
unresolved.

## When a skill says "fetch the relevant ticket"

Run `issue read --issue <number> --comments`.

## Wayfinding operations

Used by `/wayfinder`. The **map** is a single issue labelled `wayfinder:map`;
its **child tickets** are plain issues that block the map.

- **Map**: `issue create --title "..." --label wayfinder:map` holding the Notes / Decisions-so-far / Fog body.
- **Child ticket**: an issue labelled `wayfinder:<type>` (`research`/`prototype`/`grilling`/`task`) with `Part of #<map>` at the top of its body, linked to the map with `prerequisite add --issue <map> --requires <n>` (the map waits for each ticket).
- **Blocking**: Gitea dependency links — the map is blocked by every child. `issue read` reports open blockers, which are the live gate.
- **Frontier query**: `issue list --state open --label wayfinder:map`-scoped children (list open issues, keep those mentioning `Part of #<map>`), drop any with an open blocker or `status/in-progress`; first in map order wins.
- **Claim**: move the ticket to `status/in-progress` with `issue set-status`.
- **Resolve**: `issue comment --issue <n> --body "<answer>"`, then use `issue close --issue <n> --status status/done --comment "Decision accepted; see the resolution comment."` for an explicitly authorized accepted decision; use `status/wontfix` for declined work and `pr cleanup` for PR-backed implementation. Gist the decision into the map's Decisions-so-far.
