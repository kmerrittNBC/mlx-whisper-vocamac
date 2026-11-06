# Triage Labels

The skills speak in terms of five canonical triage roles. This file maps those
roles to the label strings used in this repo's Gitea tracker. The strings match
the standard workflow vocabulary installed by `labels setup`.

| Label in mattpocock/skills | Label in our tracker | Meaning                                  |
| -------------------------- | -------------------- | ---------------------------------------- |
| `needs-triage`             | `status/needs-triage` | Maintainer needs to evaluate this issue |
| `needs-info`               | `status/needs-info`   | Waiting on reporter for more information |
| `ready-for-agent`          | `status/ready-for-agent` | Fully specified, ready for an AFK agent |
| `ready-for-human`          | `status/ready-for-human` | Requires human implementation          |
| `wontfix`                  | `status/wontfix`      | Will not be actioned                     |

When a skill mentions a role (e.g. "apply the AFK-ready triage label"), use the
corresponding label string from this table.

Edit the right-hand column to match whatever vocabulary you actually use, then
re-run `labels setup` so the tracker carries the strings.
