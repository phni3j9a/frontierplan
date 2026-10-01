# Architecture / v0.5.2

FrontierPlan is an instructions-only plugin. It teaches a division of responsibility
and a preferred way to work, using Herdr's official CLI/SKILL or native host tools
for transport. It has no runtime Python, TOML role profiles or state machine.

```text
User <-> Main (relay) <-> Astra
                           | research requests
                      Main -> Researcher -> Main -> Astra

Plan ready + implementation authorized
                   |
       Main assigns, integrates and adjudicates
          Worker/Design <-> Main <-> Reviewer
                  (assigned task verification)
                   |
       Main assigns integration checks to Worker
            Reviewer verifies the checks
                   |
       Astra checks overall intent/Plan once
                   |
            Main finishes
```

The default role structure follows axiom_for_herdr. User instructions can change
the assignment; the plugin is guidance, not a mechanism for overriding them.
Independent review remains the default. This release does not introduce direct
Worker–Reviewer orchestration.

Reviewer verifies the implementation and evidence for Main's assigned Worker or
Design task, including regressions caused by it. Main owns integration verification
and finding adjudication. Astra checks the integrated result for overall goal
fulfillment and gaps between tasks, without repeating task-level implementation
review. Accepted fixes return to their implementer and the same Reviewer; Main
decides completion. The [shared workflow](../plugins/frontierplan/core/workflow.md)
defines these boundaries for all entry points.

v0.5.2 adds convergence guidance within that workflow: cover the assigned scope on
the first review, verify fixes and their impact on re-review, and carry decisions
forward unless new evidence changes them. Main ends review on fulfilled criteria
and verification, not exhausted suggestions. No runtime, ledger or review quota
is added; the role structure and Astra's once-per-Plan check are unchanged.

## Components

- `skills/`: three short explicit entry points.
- `core/workflow.md`: shared planning, execution, review and continuity guidance.
- `core/roles.md`: one model/effort/tier table.
- `backends/herdr.md`: the familiar layout and per-role CLI launch guidance;
  general control and lifecycle behavior come from installed `herdr --skill`.
- `backends/swe2.md`: only the Devin Researcher/Worker difference.
- `backends/subagent.md`: direct use of native host tools.
- `tools/` and `tests/`: development-time package checks, outside the plugin ZIP.

The Herdr layout retains Main left 40%, Astra right 60%, with execution in the
lower 60% of Astra's region. Additional participants split the widest execution
pane horizontally. The instructions teach these steps; manual resizing is not
an error and no custom geometry validator governs the task.

## What moved out of code

Main now reads ordinary replies and carries the Plan and participant identities
in conversation or a short handoff note. There are no decision JSON schemas,
message numbers for permission, request digests, receipts, begin/report commands,
fixed acceptance tables, close records or mandatory five-minute reconciliation.

Herdr already offers agent readiness, prompt submission, wait, read and live
names/IDs. Native tools supply their own equivalent capabilities. These systems
do not prove semantic success or that Main read the output. Guidance covers
reading results, same-session continuation and checking uncertain delivery;
there is no replacement ledger or promise of unattended resumption.

The user/environment controls authentication, permissions and settings. Codex
launch examples request workspace-write/never; native permissions depend on the
parent. The SWE-2 variant keeps its existing broader Devin permission mode, with
the distinction explained at its point of use.

## Migration and evidence

v0.5.0 replaces v0.3.0 on main; v0.4.0 was used by a reverted design and is not
reused. Finish old runs with their existing version, then start fresh with the
updated plugin. Old helper state is not migrated or read. Installed copies and
user settings are never automatically changed.

The previous implementation and smoke tools remain in Git history, for example
commit `b766d2a`. Saved historical evidence is retained and labeled with its
original versions; it is not a validation of the new instructions-only workflow.

See [validation](validation.md) for current tests and the separate target-host
checks. See [third-party notices](../plugins/frontierplan/THIRD_PARTY_NOTICES.md)
for retained attribution.
