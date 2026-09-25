# Architecture / v0.3.0

FrontierPlan = axiom_for_herdr's working structure + an Astra-owned planning phase,
on shared contracts, role profiles and two execution backends.

```
User ─ Main (relay) ─ Astra ─┬─ research requests ─> Main relay ─> Luna researchers
        ^                    ├─ user questions / Plan ─> Main relays verbatim
        └────────────────────┘  Plan + implementation authorization
                   │
          Main coordinates (axiom_for_herdr)
          /        |          \
      Worker     Design     Reviewer (same session, no round limit)
          \        |          /
        integrated result + evidence
                   │
        Astra final check (once per Plan) ─> Main adjudicates, finishes, reports
```

Main is the technical parent of every child, including Astra and the researchers;
nothing nests. Before execution Main performs only mechanical steps returned by the
helper (`relay`, `forward`, `start`, relaying `user_response`), so a Main with weaker
judgment (for example Devin SWE-2) does not dilute planning. After `start`, Main
judges as in axiom_for_herdr.

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
(`workflow`, `astra`, `roles`, `handoff`, `review`, `waiting`); `profiles/` holds
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
Native tool calls stay in Main; shell Python does not invoke Codex agent tools.

The ledger refuses executor dispatch before Astra records authorization for the
current Plan, planning decisions made before the newest user message reached Astra,
decisions that do not fit the turn (for example `final_check` during planning), a
second final check for the same Plan, finish without that check or with uncollected
executors, and early closes (Astra before finish; executors with unresolved blockers).
It does not verify the semantic truth of consent or evidence, and it is not a sandbox.
There is no candidate fingerprint gate or Astra acceptance state anymore.

The herdr layout keeps Main left 40% and Astra right 60%; researchers and executors
share the lower 60% of Astra's region. Completion reconciliation compares current
results with receipts instead of trusting notification delivery (added for a Devin
Main that missed reports). Neither a shell waiter nor a report file can guarantee
restarting a stopped Main.

Runs created by v0.1 (`schema_version` 1) are rejected; finish them with v0.1.
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
FrontierPlan validation. See validation.md for the boundary of automated coverage.
