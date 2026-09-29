# Shared workflow

Astra plans. Main assigns and integrates. Worker implements. Reviewer closes the
bounded task. Astra checks the integrated Plan once. Main finishes.

```
Planning   Astra -> research / user dialogue (Main relays) -> Plan + authorization
Execution  Main -> [Worker <-> Reviewer] -> collected current PASS -> close pair
Final      Main integrates -> Astra checks once -> Main finishes or assigns repairs
Repair     New bounded pair -> collected PASS -> Main finishes (no Astra reacceptance)
```

## 1. Planning: Astra decides, Main relays

Initialize one run with the user's exact words and start Astra. Main may add a
short file of transport facts (repository/worktree paths, available environments,
known permissions). It must not add hypotheses, a researched approach or a Plan.

Astra follows [astra.md](astra.md). Each Astra turn returns one decision
([handoff.md](handoff.md)). Main runs the helper's `decision` command and performs
the returned `next` step mechanically:

| `next` | Main does |
|---|---|
| `relay` | run the backend's research relay: start Astra's researchers with her exact requests, then return their unedited reports to her |
| `relay_to_user` | show `relay_to_user` to the user exactly as written, then wait for the user |
| `start` / `relay_to_user_then_start` | (show the text, then) run `start` and begin execution |
| `main_decides` | execution-phase advice or final-check results for Main's own judgment |

A new user message during planning is stored with `message` and given to Astra
unchanged with `forward`. Main never summarizes, reinterprets, answers for Astra
or researches on its own before execution. It may resolve transport problems
(permissions, unavailable tools, a stuck pane) under its existing rules.

Implementation authorization is Astra's call: her Plan or `authorize` decision
names the user message that authorizes implementation. When the Plan needs the
user's agreement first, she presents it and waits. Any new user message before
`start` voids a recorded authorization, because it may withdraw consent; Astra
records it again if it still holds. A consultation-only request ends
with Astra's reply; `finish --discussion` closes it.

## 2. Execution: Main coordinates; pairs verify

Main turns the Plan into short tasks: objective, owned scope, completion conditions,
existing contracts and required focused verification. Create each implementation
and its Reviewer together using [pairs.md](pairs.md). Worker/Design implements;
Reviewer verifies the assigned task. Routine fixes and counter-evidence travel
between the same two sessions without Main brokering or judging them.

Launch independent tasks when useful; do not split small work artificially. Use
disjoint ownership or worktrees and serialize overlapping writes. The fingerprint
scope must contain the candidate's actual owned changes, not just convenient files.
Settled UI work may use Worker; unsettled UI realization may use Design, always
with a separate Sol Reviewer. Profiles and existing permissions do not change.

Main receives PASS or a blocker/escalation. It resolves task boundaries, environment,
capability and same-cause stagnation, consulting Astra only for Plan-level judgment.
It may resume a stopped pair or replace a lost/stopped participant, not direct each
ordinary review round. Scope-changing user input goes to Main, then Astra as needed.

## 3. Collection, integration and pair cleanup

Follow [review.md](review.md) and the backend's actual idle/identity checks. Main
collects a pair only after the latest candidate's PASS is recorded; old reports or
an unreviewed follow-up are not completion. Collection captures the reviewed
candidate and both reports, then Main closes both idle participants. Unresolved
BLOCKED/ESCALATE work remains open unless safely captured and reassigned.
When a revised Plan drops stopped old work, Main records `pairs.py abandon` with
the scope decision, preserved artifacts and observed idle identities, then closes
both sessions. This is not PASS; current-Plan work still requires review, and
abandoned changes must not enter integration. See [pairs.md](pairs.md).

Main integrates the exact reviewed work, preserving the worktree/diff and evidence.
Closing a pane does not delete its reports, files or branch. Integration that
changes product behavior (including substantive conflict resolution) is itself a
bounded reviewed task. Do not silently add unreviewed Main edits. New work after
collection uses a follow-up pair; do not retain all old sessions just in case.

## 4. Final check: Astra looks once, not an acceptance gate

After current tasks are reviewed, collected and integrated, Main sends Astra the
criteria mapping, diff/worktree references, real verification, resolved findings
and known gaps. Astra returns criteria status, material findings and Plan divergence
**once per Plan**, with no veto. It is not another local design/style review.

Main chooses finish, bounded rework, replan or escalation. A concrete implementation
defect goes to a follow-up Worker–Reviewer pair; ordinary technical findings are
resolved there, not by Main. Plan/scope divergence is a Main/Astra concern and may
require user choice. Repairs are verified by their Reviewer, not resubmitted to
Astra. A materially revised Plan is explicit, not a renamed excuse for reacceptance.

## 5. User communication

Relay Astra's planning dialogue verbatim. During execution return the completion
report or a genuine scope/cost/permission decision with concrete options. Review
rounds, elapsed time or routine findings are not user checkpoints; do not ask
"should I continue?". Higher-priority host communication requirements still apply.

## 6. Finish

`finish --file <report>` requires the one-time final check for the current Plan,
a collected current PASS for every execution pair, and collected current reports
from live executors. Main reports results, Astra's criteria table, real validation
and remaining limitations. Document accepted conclusions within the authorized
scope, then close Astra and any remaining participants. No publishing permission
is inferred from a Plan or PASS.

## Waiting and recovery

Follow [Completion reconciliation](waiting.md). Main reconciles pair-level PASS,
blockers and transport failures, not internal candidate/finding reports. Children
end their turn after handoff instead of waiting on each other indefinitely.

Do not substitute models, efforts or backends. Record actual lost-session evidence
before replacement; idle or slow is not lost. Pair replacement preserves its
contract, current candidate and findings. Astra's planning replacement receives
prior user messages and decisions; Main never takes over planning. Preserve handles
through compaction. The temporary run directory is not a durable project archive.
No daemon, dashboard, generic message bus or automatic config mutation is needed.
