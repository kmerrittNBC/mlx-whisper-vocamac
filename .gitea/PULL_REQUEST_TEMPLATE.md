## Summary

<!-- Keep prose brief. Add the smallest useful diagram, diff-sketch, tree,
pseudocode, or code block when it makes the change faster to understand. Use
the project's domain language. -->

## Evidence

- **Before:** the screenshot, output, symptom, or failing test run.
- **After:** the screenshot, output, corrected behavior, or passing test run.

<!-- For a bug fix, name the confirmed root cause or successful hypothesis.
Merge evidence stays here; it is not a docs/evidence/ record (see
docs/agents/standards.md). -->

### Checks run

- `the exact command already run` — observed result.

## Documentation disposition

updated / not_required / deferred / blocked — which one, and why in one line.

<!-- Definitions and the recording rule live in docs/agents/standards.md;
/cleanup blocks the merge without one. -->

## Merge Danger

**Door:** one-way or two-way — why the change is or is not cheap to reverse.

**Blast Radius:** the affected subsystem, consumers, or behavior.

**Rollback:** the exact rollback path, including any state it cannot restore.

## Reviewer prerequisites

- Required runtime, services, credentials or profiles, operating system,
  fixtures, clean-state conditions, duration, and meaningful cost; or `None`.

## Manual Test Plan

<!-- Include only behavior that automated evidence cannot prove. -->

1. [ ] **Action:** the exact reviewer action, command, route, control label,
   field value, or UI interaction. Put every command in a copyable fenced block.

   **Expected:** the observable evidence that the step passed, and any
   condition that requires the reviewer to stop.

## Post-Merge Cleanup

```sh
git switch main
git pull --ff-only origin main
git branch -d ISSUE-<number>
git push origin --delete ISSUE-<number>
```
