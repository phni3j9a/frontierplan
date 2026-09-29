# Architecture / v0.4.0

FrontierPlan keeps Astra-owned planning and one-time final checking. Ordinary
execution now belongs to bounded Worker/Design–Reviewer pairs.

```
User -> Main relay -> Astra -> research / user dialogue / Plan + authorization
Main -> [Worker <-> Reviewer] -> current PASS -> collect and close pair
Main -> reviewed integration -> Astra checks once -> Main finish/rework/replan
Repair -> new bounded pair -> PASS -> Main finish (no Astra re-acceptance)
```

Main remains the technical parent of every child: there is no nested spawning.
Research remains mechanically relayed by Main. Ordinary task review is different:
registered peers exchange candidates/findings directly. Main receives completed
reviewed work or escalation and owns integration, exceptions and overall completion.
The change moves existing convergence rules into the pair; direct communication
alone is not evidence of better convergence, latency or cost.

## Why v0.2 changed

v0.1 made Astra the final acceptance gate and forbade extra user checkpoints. In
real runs (meeterm #27, meeshogi #17) Plans grew beyond the issue, each acceptance
request triggered a new Astra audit, and review escalations went back to Astra, so
work did not converge until the user stopped it. v0.2 keeps Astra's strength where
it matters (research, design, Plan, one final look), returns execution judgment to
Main, restores axiom_for_herdr's review rules (including unnecessary-complexity
findings and no round quota), and limits user returns to planning dialogue,
completion, and scope/cost-changing branches. See
[Issue #11](https://github.com/phni3j9a/frontierplan/issues/11).

## Components

`skills/` holds the three explicit entry points; `core/` defines common behavior
(`workflow`, `astra`, `roles`, `handoff`, `review`, `pairs`, `waiting`); `profiles/` holds
role runtime data; `backends/` defines the real transport steps.

`astraplan-herdr-swe2` is a variant of the herdr backend, not a third backend. The
run records `variant: swe2` at init; Researcher and Worker then load
`profiles/swe2/*.toml` (`agent = "devin"`, `swe-2-max`) and start as Devin CLI
sessions in Devin's bypass mode (no OS sandbox, every tool auto-approved), while
every other role, the ledger and the layout are shared. Each child's agent kind comes
from its own profile, so identity checks compare Codex tasks with Codex panes and
Devin tasks with Devin panes. See [herdr backend](../plugins/frontierplan/backends/herdr.md).

`scripts/frontierplan.py` is a cooperative ledger: run state, verbatim user
messages, packets, Astra decision validation with a mechanical `next` step, the
research relay state, the once-per-Plan final check, and finish/close records.
`scripts/herdr.py` implements visible CLI sessions, identity-aware continuation,
the relay/forward/consult/final-check deliveries, wait/check and safe close.
`scripts/pairs.py` adds one pair record using existing task packets/reports. It
binds current contract/candidate/Reviewer identity, restricts peer handoffs, records
collection and supports bounded blocker recovery. Herdr resumes the registered
peer through its actual prompt operation, preserving existing idle/terminal checks.
Native management calls stay with Main, but peer continuations belong to the child;
shell Python never invokes native tools. Missing reciprocal host capability is
reported, not hidden behind a Main relay.

The ledger refuses executor dispatch before Astra records authorization for the
current Plan, planning decisions made before the newest user message reached Astra,
decisions that do not fit the turn (for example `final_check` during planning), a
second final check for the same Plan, finish without that check or with uncollected
executors, and early closes (Astra before finish; executors with unresolved blockers).
It does not verify the semantic truth of consent or evidence, and it is not a sandbox.
There is still no Astra acceptance state. Task-local PASS is now bound to a content
manifest (tracked/untracked owned files, modes, symlinks and deletions), not merely
HEAD. Collection checks live bytes and seals the delivered result; later edits are
new tasks. Finish validates collected pair evidence, not a perpetual rehash/review
of completed worktrees. Main must integrate the exact reviewed artifact; a manifest
of hashes is not a source archive or an automatic integration verifier.

The herdr layout keeps Main left 40% and Astra right 60%; researchers and executors
share the lower 60% of Astra's region. Completion reconciliation compares current
results with receipts instead of trusting notification delivery (added for a Devin
Main that missed reports). Neither a shell waiter nor a report file can guarantee
restarting a stopped Main.

Runs created by v0.1 (`schema_version` 1) are rejected; finish them with v0.1.
In-flight unpaired runs from earlier schema-2 releases must also finish with their
original helper version; do not implicitly mix orchestration protocols. Raw task
preparation remains available for staging/recovery, but unpaired executors cannot
pass the new final completion checks.
Fable is not shipped. Add a verified Director profile plus a supported launcher and
contract tests before registering it. Keep vendor connection details out of core.

## Public references used for package/compatibility design

- [Plugin packaging](https://developers.openai.com/plugins/build/plugins): portable
  root manifest and optional Codex compatibility manifest; all referenced data ships.
- [Skills](https://developers.openai.com/codex/skills): skill packaging. Explicit-only
  agents/openai.yaml follows the existing repository's tested configuration.
- [Native subagents](https://learn.chatgpt.com/docs/agent-configuration/subagents):
  effective permissions may inherit the parent's live runtime overrides; nesting is
  limited by `agents.max_depth`, which is why research is relayed through Main.

Public APIs and host versions vary; exact native argument names and effective
permissions must be checked on the target host. Historical upstream tests are not
FrontierPlan validation. See [validation](validation.md) and the
[Issue #17 local Codex handoff](issue-17-validation.md); real peer round trips remain
pending separately from simulated tests.
