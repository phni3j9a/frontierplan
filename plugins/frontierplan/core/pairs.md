# Worker–Reviewer pair protocol

One bounded task, one implementer (Worker or Design), one Reviewer. Main owns
registration, launch/bind, collection, recovery, integration and closure. Only the
registered children exchange ordinary candidates/findings. Role text and the
local ledger are cooperative controls, not a hostile-agent sandbox.

## Contract and setup

Use a short Markdown contract: objective, owned scope, observable completion,
relevant supported contracts and focused verification. Keep Plan references and
non-goals where useful; do not specify every implementation step.

```
pp=<plugin-root>/scripts/pairs.py
hd=<plugin-root>/scripts/herdr.py
```

Main on Herdr:
```
python3 "$hd" pair-spawn --run "$run" --file "$contract" [--cwd "$worktree"] [--scope src/component] [--role design]
```
This prepares both participants, launches the Reviewer first (an idle bootstrap),
then launches the implementer. Save both task paths. Profiles and launch permissions
are unchanged. Failed/partial launch prints prepared handles: inspect those before
starting another pair.

Native Main uses `pairs.py create` with the same arguments plus
`--capability-file <actual-host-evidence.json>`. Spawn each new child with its
`bootstrap_packet`, which only observes its native thread identity and ends idle.
Bind both returned identities, then use real native follow-ups to send the actual
`packet`, Reviewer first. `bind` also returns this work packet; binding is not delivery.
This order also applies to replacement sessions and avoids racing child work
against Main's binding. See the [native backend](../backends/subagent.md).
The helper does not make a native tool call. Do not create a capability assertion
from a hypothetical tool schema or use Main as a hidden peer relay.

## Child turns

The generated packet contains the exact task, request ID and commands:
```
python3 "$pp" begin --task "$own_task" --request-id "$request_id"
python3 "$pp" submit --task "$own_task" --request-id "$request_id" --kind candidate --file "$evidence"
python3 "$pp" submit --task "$own_task" --request-id "$request_id" --kind findings --candidate "$candidate_digest" --file "$findings"
python3 "$pp" submit --task "$own_task" --request-id "$request_id" --kind pass --candidate "$candidate_digest" --file "$verification"
```
Worker/Design submits candidate after implementation, fixes or counter-evidence.
Reviewer submits findings/PASS for the digest returned by its `begin`. The
Reviewer bootstrap has no candidate: `begin` returns `waiting`; end the turn
without reviewing, polling or inventing a report. A normal handoff creates the
next packet for the same peer session and preserves earlier report files.

Herdr `submit` sends the peer's continuation when that peer is idle. It waits at
most 30 seconds for idle, not for task completion. A busy peer leaves delivery
`prepared`; retry `deliver` with the same sender request ID, not `submit`. End
unnecessary blocking waits so the peer can continue. A delivery marked `uncertain`
must be inspected, never blindly sent again. `check` exposes this to Main as a
transport problem, not a review finding. The peer's `begin` acknowledges delivery.

Native `submit` returns `native_call_required`, the registered `agent_id` and
packet path. The child must actually invoke its host's peer-continuation tool.
Python returning a target, a notification, or a report is not proof of delivery.
End each turn after handoff so the peer can resume that same session.

Either child can submit `--kind blocked` or `--kind escalate` with evidence of a
missing prerequisite, ambiguity or same-cause lack of progress. No fixed round
limit, extra approval stage or general agent messaging is added.

## Candidate and PASS

The candidate records an immutable per-turn manifest of the owned tracked files,
tracked deletions, non-ignored untracked files, symlink targets and executable bits.
Its digest binds the actual bytes, including uncommitted work, not merely HEAD.
`head` is informational; it is **not** a complete artifact when the worktree is dirty.
Ignored build outputs and unrelated files outside the declared ownership are not
part of this candidate. Required supported behavior/verification is still the
Reviewer's responsibility; a fingerprint does not prove correctness.

Use a dedicated worktree or disjoint literal `--scope` paths for parallel tasks.
The scope defaults to the entire worktree and must include all owned changes.
Submodules need their own worktree pair. The manifest contains hashes, not a source
archive: preserve the reviewed worktree/diff/commit and evidence until integration.

Only the assigned Reviewer can return PASS. It binds the contract digest, current
candidate digest, Reviewer identity and both current reports. Changed work cannot
reuse an old PASS. Reviewer findings can request a fresh candidate if files changed
during review; this does not need Main adjudication.

## Collection and closure

Main waits for both actual sessions to be idle, then:
```
python3 "$pp" collect --task "$worker"
python3 "$hd" pair-close --task "$worker"
```
`collect` checks the live candidate and uses the backend's existing collection
checks for both reports. It records the reviewed result as delivered. Native Main
instead closes the recorded actual agent IDs with native tools, then records
closure with `frontierplan.py close-record`.

A valid collected pair can close immediately; do not wait for Astra. BLOCKED or
ESCALATE is not completion. Do not close unresolved work except after capturing
state and explicitly replacing the participant. Closure retains reports and files.
A previously verified lost terminal is never closed using its reused pane ID.

If a revised Plan drops a stopped old task, Main may explicitly abandon that pair:
```
python3 "$pp" abandon --task "$old_worker" --file "$abandonment_evidence"
python3 "$hd" pair-close --task "$old_worker"
```
The evidence must explain why the revised Plan excludes the task, where its
worktree/diff/reports are preserved, and the observed idle/lost state of both
sessions. For native sessions Main verifies idle using the actual host before
`abandon`, then closes/records each live agent through native tools as usual.
Herdr verifies idle and terminal identity itself and records activity sequences;
later activity requires inspection and a fresh `abandon` capture before closure.
`check` exposes retained abandoned panes as `abandoned_needs_close`.

`ABANDONED` is a recorded scope decision, never PASS or permission to integrate
unfinished changes. Current-Plan tasks and active pairs cannot be abandoned.
The record preserves the existing candidate, reports and pending-handoff evidence,
including absence of a report from an idle Reviewer bootstrap. A revised Plan
cannot finish while an old stopped pair remains unresolved: resume it under the
new contract or abandon it explicitly. Abandoned pairs do not block the new Plan
and may close even after finish; lost or unlaunched terminals are never closed.

Once collected, the task is sealed. Later work must be a follow-up/integration pair,
not edits under the old PASS. Final checks validate the delivered candidate and
current reports, rather than rehashing an old worktree forever after subsequent
tasks changed it. Before live pane closure the candidate is checked again. Main
must integrate the actual reviewed artifact; the helper is not a merge engine.

## Exceptions and recovery

If Herdr IPC fails before either participant starts, even a child's `blocked`
submission can fail its live identity check. Preserve the local error reports.
Main may record this externally observed startup failure, without impersonating a
child or manufacturing a report:
```
python3 "$hd" pair-block-start --task "$worker" --file "$transport_evidence"
```
This requires the current Plan, both original participants idle with live identity
and activity evidence, no current result (including `working`), and no candidate,
handoff or collection. It records `BLOCKED` plus separate `startup_blocker`
evidence. It neither repairs permissions nor completes/closes the pair. Restore
the existing transport before `pair-resume`, or explicitly abandon the stopped
work after a revised Plan excludes it. Existing identity/activity checks still
apply at abandonment and closure. Never call a live participant lost merely to
get around this failure.

Main may `pair-resume --task <member> --file <resolution>` for a stopped pair or a
candidate changed after PASS but before collection. `--contract-file` records an
explicit scope clarification, never a Reviewer-created requirement. After adopting
a revised Plan, supply this updated contract explicitly when resuming stopped old
work; it updates that pair's Plan binding. Active pairs must complete or escalate
before a revised Plan can be adopted, so no running peer is silently stranded. This resumes
the existing Worker once; the subsequent review loop is peer-to-peer.

For observed session loss, first record `frontierplan.py retire-lost` with real
runtime evidence. `herdr.py pair-replace --task <lost-or-stopped-member> --file
<recovery-evidence>` creates the same-role/profile replacement, retaining the
contract, candidate and report history. A live stopped member must have been
collected before replacement, and its superseded idle pane may then close. A lost
or reused terminal is never closed. If replacing a Reviewer without a valid current
Worker candidate, bind/launch it, then resume the Worker to publish a new candidate.
Native Main uses `pairs.py resume/replace` and the actual native lifecycle tools.
Replacement native children use the same identity-bootstrap/bind/work sequence;
continuing an already bound session needs no new bootstrap.

Astra's final check is still once per Plan with no veto. Concrete later repairs use
new pairs, and their PASS returns to Main, not an Astra re-acceptance loop.

Do not migrate an in-flight unpaired run to this workflow implicitly. Finish it
using the version that created it, or explicitly start a new run with the user's
existing state preserved. Raw `prepare`/`spawn` remain low-level recovery/staging
operations; unpaired executors cannot satisfy the final completion checks.
