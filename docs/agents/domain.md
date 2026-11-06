# Domain Docs

How the engineering skills should consume this repo's domain documentation when exploring the codebase.

## Before exploring, read these

- **`CONTEXT.md`** at the repo root, or
- **`CONTEXT-MAP.md`** at the repo root if it exists: it points at one `CONTEXT.md` per context. Read each one relevant to the topic.
- **`docs/authoritative/adr/`**: read ADRs that touch the area you're about to work in. In multi-context repos, also check `src/<context>/docs/authoritative/adr/` for context-scoped decisions. The rest of `docs/authoritative/` holds current product design, contracts, and constraints.
- **`docs/evidence/`**: curated observations that inform a foundational design decision. Read a record when you need to understand or challenge the decision it supports; it informs that decision but never overrides the authoritative document. Its `README.md` sets what qualifies.
- **`docs/historical/`**: superseded designs, archived handoffs, and development records, including one issue's retained work under `docs/historical/issue-notes/<issue-number>/`. Read these to understand how the project arrived at its current state — never as current behavior.

If any of these files don't exist, **proceed silently**. Don't flag their absence; don't suggest creating them upfront. The `/domain-modeling` skill (reached via `/grill-with-docs` and `/improve-codebase-architecture`) creates them lazily when terms or decisions actually get resolved; `/cleanup`-bound work moves superseded context into `docs/historical/` per `docs/agents/standards.md`.

## File structure

Single-context repo (most repos):

```
/
├── CONTEXT.md
├── docs/
│   ├── authoritative/adr/
│   │   ├── 0001-event-sourced-orders.md
│   │   └── 0002-postgres-for-write-model.md
│   ├── evidence/                      ← foundational design evidence
│   └── historical/issue-notes/186/    ← one issue's retained records
└── src/
```

Multi-context repo (presence of `CONTEXT-MAP.md` at the root):

```
/
├── CONTEXT-MAP.md
├── docs/authoritative/adr/            ← system-wide decisions
└── src/
    ├── ordering/
    │   ├── CONTEXT.md
    │   └── docs/authoritative/adr/    ← context-specific decisions
    └── billing/
        ├── CONTEXT.md
        └── docs/authoritative/adr/
```

## Use the glossary's vocabulary

When your output names a domain concept (in an issue title, a refactor proposal, a hypothesis, a test name), use the term as defined in `CONTEXT.md`. Don't drift to synonyms the glossary explicitly avoids.

If the concept you need isn't in the glossary yet, that's a signal: either you're inventing language the project doesn't use (reconsider) or there's a real gap (note it for `/domain-modeling`).

## Flag ADR conflicts

If your output contradicts an existing ADR, surface it explicitly rather than silently overriding:

> _Contradicts ADR-0007 (event-sourced orders), but worth reopening because…_
