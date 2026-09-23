# herdr backend

Requires Python 3.11+, Git for candidate verification, herdr and Codex on the same
host. Main is an existing session inside herdr, not necessarily Codex: a recognized
Devin or another agent can coordinate while all children still run through Codex.
Main keeps its existing agent, model, effort and permissions. FrontierPlan never
launches, switches or retunes Main, and never edits user configuration automatically.
Set absolute helper paths from this installed plugin, not a guessed checkout path:
```
fp=<plugin-root>/scripts/frontierplan.py
hd=<plugin-root>/scripts/herdr.py
```

## Initialize and start ONLY Director

Save the original user request to a UTF-8 file, then:
```
python3 "$hd" init --cwd "$project" --request-file "$request"
python3 "$hd" spawn --run "$run" --role director --file "$assignment"
```
Retain returned run/task handles and `main_identity`. Assignment contains original
dialogue references, known repository/worktree locations and permissions, not Main's
researched Plan. The common `frontierplan.py init --backend herdr` entry point also
uses the same binding procedure; it cannot create an unbound herdr run.

### Main identity: agent kind + session ID + terminal ID

When `HERDR_PANE_ID` is available, the helper checks `pane current --current` against
that ID. With no explicit identity or Codex identity in the environment, it derives
Main's agent kind and session ID from this verified current pane. It does not look
at focus, cwd, the only available agent, or model names to guess Main.

Codex's `CODEX_THREAD_ID` / `CODEX_SESSION_ID` remain supported and must agree when
both are present. For other hosts that cannot expose a trustworthy current pane or
session ID, independently verify Main's actual agent kind, actual session ID and
pane/terminal pair, then supply the provider-neutral identity in Main's command
environment for **every** helper invocation (both scripts), not only initialization:
```
export FRONTIERPLAN_MAIN_AGENT="$verified_agent_kind"
export FRONTIERPLAN_MAIN_SESSION_ID="$verified_session_id"
python3 "$hd" init --cwd "$project" --request-file "$request" \
  --main-pane "$verified_pane" --main-terminal-id "$verified_terminal" --socket "$socket"
```
Use the agent kind reported by the installed herdr, not an assumed product label.
For example `devin` is appropriate only if that is the actual reported kind. These
are FrontierPlan variables, not claims about a Devin-specific environment API.
Do not invent a session ID, reuse a previous session's value, or copy an unrelated
pane's identity. Explicit pane IDs alone do not prove which conversation is calling.
Set both identity variables or neither. Contradictions with live metadata or inherited
Codex IDs stop the command; inspect stale environment values rather than overriding
checks. A shell/unknown/unrecognized agent cannot be made valid merely by naming it.

If live session metadata is absent, an independently verified explicit identity can
be used with the verified agent kind and terminal; this is cooperative identity
checking, not authentication. A session ID observed at initialization must remain
available and equal on later commands. The shared ledger also verifies live identity
before Main-only operations such as message, authorize, prepare, decision and finish.

Main's original terminal remains the anchor after moves/swaps. With an explicit or
Codex session identity, its current pane is located by terminal ID. Auto-detection
also needs a correct current `HERDR_PANE_ID`; if the host leaves it stale after a
move, stop and re-establish the verified current context or explicit identity. Do
not infer caller identity from the saved run alone. Replaced terminals, changed
agent/session identities and ambiguous matches fail closed before pane mutation.
Pre-existing Codex/herdr runs keep their original Codex ownership checks; there is
no automatic owner migration. Native subagent runs still require Codex native tools.

The plugin's installation metadata remains Codex-oriented. A non-Codex host must
explicitly load this SKILL and its referenced contracts and be able to run the local
helpers on the herdr host; this change does not install a Devin plugin or establish
remote connectivity. Actual provider/host compatibility requires a real-host smoke
test. Simulated Devin tests are not evidence of real model routing or billing.

### Role layout

The Director splits Main `right / 0.4`: Main retains the left 40%, Astra gets the
right 60%. The first Worker/Design (or Reviewer if it is the first execution role)
splits Astra `down / 0.4`: Astra retains the upper 40% of that right region and the
execution area receives the lower 60%. Subsequent Worker/Design/Reviewer spawns
split the widest owned execution pane `right / 0.5`, with leftmost pane then ID
breaking ties. These subdivisions need not produce equal columns.

Every split uses `--no-focus`. Existing user panes outside the original Main region
and manual ratios remain intact; there is no global rebalance. The helper binds the
Director task and tab/workspace, then verifies the live Main/Director/execution
regions using `pane layout` split geometry and terminal ownership. Insets from pane
borders/gaps are allowed. Zoomed, zero-sized, missing or ambiguous layouts stop
dispatch before splitting. A moved participant or a user pane inserted inside the
managed region may require manual restoration of the layout before dispatch resumes.
Failed preparation leaves its task handle visible; inspect before retrying.

Removing execution panes lets Herdr collapse the vacated split naturally. Once all
execution panes are released, Astra occupies the right region again. If new work is
authorized before finish, its first execution pane recreates `down / 0.4` from the
verified Astra anchor. Retained Reviewer panes also count as execution panes.
Runs started before role-layout metadata existed cannot guess an execution region;
finish/clean up those runs with their existing participants before starting a new run.
A lost Director anchor likewise requires explicit layout/session recovery; the helper
does not split Main to silently replace it.

## Reports and continuation
```
python3 "$hd" collect --task "$director"
python3 "$fp" decision --task "$director"
python3 "$fp" message --run "$run" --file "$new_user_message"
python3 "$hd" send --task "$director" --file "$followup"
```
Children use the shared begin/report commands embedded in their packets. Always
collect through herdr.py to record live idle/activity evidence. Use send for the
same Director or Reviewer. Spawn fresh Workers/Design for bounded assignments by
default; send to an existing Worker only for a justified small immediate follow-up.

After a current Director Plan and actual implementation authorization:
```
python3 "$fp" authorize --run "$run" --message 1
python3 "$fp" start --run "$run"
python3 "$hd" spawn --run "$run" --role worker --file "$bounded_assignment"
```
The example message number is not blanket permission: use the real authorizing
message. Optional design and later independent reviewer use the same spawn command.
Candidate, decision and finish use frontierplan.py. Before candidate/finish ensure
all participating live terminals are idle and no direct user activity is outstanding.
After finish, use `python3 "$hd" close --task "$task"` for each owned participant,
including released records (which need no further pane operation).
Closed records are not evidence of actual closure; the transport verifies and closes
first. Never close Main, active/uncollected work or a terminal with changed identity.

## Release completed execution participants

The authoritative role lifecycle is in [workflow.md](../core/workflow.md).
After a completed Worker/Design assignment, collect its report, integrate its work,
and verify that no writes or owned processes remain. Review fixes may be assigned
to a new Worker later; pending independent review does not require keeping this
session alive. Obtain a read-only decision template:
```
python3 "$hd" release-check --task "$worker"
```
Save it outside the candidate checkout, for example in the run directory. Preserve
`binding` exactly: it binds backend, current task/request, report/receipt, handle, integrated
candidate, Plan and user input. Read the report and verify the actual state before
setting the decision fields:
```
"decision": {
  "integrated": true,
  "assignment_complete": true,
  "no_active_processes": true,
  "no_longer_needed": true,
  "reason": "Assignment integrated and processes stopped; review fixes will use a fresh Worker."
}
```
The helper cannot infer these facts from prose. Do not set them merely to free a
pane. Then:
```
python3 "$hd" release --task "$worker" --file "$release_decision"
```
An active session, stale report/activity/Plan/candidate, or changed terminal fails
before close. Inspect the cause and create a fresh decision only when it is true.
Release archives the complete assignment evidence, not a claim of review approval.
Candidate submission still requires an independent review of the integrated tree.

For existing runs, `release-check --reviewer "$reviewer"` remains supported with
its original reviewed-release decision (`integrated`, `unresolved_findings: []`,
`no_longer_needed`, `reason`). Existing archived review evidence remains verifiable.
New runs normally use assignment release above instead of retaining Workers for review.

Reviewer needs no Main release-decision file; its gate is Astra's current acceptance.
After Astra accepts the exact candidate and safety checks pass, release Reviewer
before finish:
```
python3 "$hd" release --task "$reviewer"
```
This requires unchanged accepted candidate, collected acceptance and idle/fresh live
participants. Release eligible Workers before Reviewer when both are ready. Retaining
participants beyond their release point requires an explicit exception and a specific
reason recorded in the run's evidence or decision notes, as required by the shared
workflow. Participants retained for such exceptions remain subject to safe post-finish
cleanup. Failed safety checks require retention and a recorded reason; do not bypass
them. Never release Astra; use `close` only after finish.

Successful release records `released: true, closed: false`, the Main disposition and
assignment evidence (or the legacy release review / Astra acceptance for Reviewer). Task files,
reports and evidence survive; later re-review cannot overwrite the archived copy.
Released sessions reject send/begin/report and are excluded from wait pending work.
Candidate/acceptance/finish still validate their archived evidence. Later changes
can use a new Worker with the preserved history; the existing live Reviewer continues
if retained. After an accepted Reviewer has been released, new review needs a new
Reviewer and must not reuse an old report for a different candidate/Plan.

Both release and close verify ownership, unique original terminal, current pane
occupant, complete collected report and unchanged `state_change_seq`. A moved owned
terminal can be closed only at its independently verified current pane, never by
blindly reusing its original pane ID. Report/run locks prevent competing helper
writes during closure. Herdr's pane lookup and close are separate API calls: these
cooperative checks do not atomically intercept direct user typing or pane swaps.
Avoid manual input/movement during the close operation.

Before closing, the helper persists a `closing` record with the intended operation,
pane/terminal identity and release evidence. A lost response or crash leaves that
record and blocks retry/dispatch/finish; it is not success. Inspect that exact
terminal and whether closure occurred before manually recovering the record; do not
clear it automatically or retry against a reused pane ID. `close` still requires
overall `finish`, and final cleanup of a released record never sends a second close.

## Waiting

Follow [Completion reconciliation](../core/waiting.md). On entry/resume and after
any lost result handle, inspect current conditions without consuming notifications:
```
python3 "$hd" check --run "$run"
```
`check` is read-only and may run while the one waiter is alive. It returns current
`events` and `pending`, including already-announced but uncollected reports. It does
not collect reports or close sessions. Inspect each returned task and collect ready
reports through `herdr.py collect` before advancing their next action.

Use one `python3 "$hd" wait --run "$run" --timeout 300` process per run (300 is also
the default and maximum). Retain its execution handle. Its local two-second checks
do not invoke Main's model. Await the SAME handle with the host's result-wait tool,
including outer wrappers, and continue after host-limited yields. Set that outer wait
within 300 seconds or a lower supported/higher-priority cap; never invent unavailable
arguments. Do not start another waiter when the outer call yields or is interrupted.

An unread complete/blocked report returns again until collected with current idle
activity evidence. `report_waiting_idle` means publication arrived but the live
session is not yet idle: wait before collection or closure. Unchanged collected
blockers and other anomalies do not repeatedly wake Main inside a wait, but remain
visible on every `check` and on the next timeout heartbeat. Resolve them or record
the retained prerequisite before waiting again. Collected complete idle participants
and released tasks are not pending; pending:0 alone does not release anyone.

On a busy/stale lock, inspect the recorded owning PID and existing execution handle.
Reuse the live waiter, or verify its termination before recovering its lock. Do not
retry lock failures in a fast loop, launch a second watcher, or monitor only new files.
A wait exit is not proof that Main read/collected its result. Keep the result-wait path
active; a background waiter cannot guarantee waking a Main that has ended its turn.
Long-running process monitoring after implementation starts belongs to its Worker.

## Permissions, routing and partial failures

Each child requests workspace-write + never and `default_permissions=":workspace"`,
matching the predecessor's CLI 0.154.0/shared app-server 0.153.4 workaround. This is
NOT a cross-version permission guarantee. Verify effective permissions and model /
effort from session evidence, not launch args or a child's self-report. Only Worker
adds fast overrides. No role enables network access; Director's research uses only
already available authorized search/connector/command tools. Missing tools are blockers.
Main's explicit identity variables are cleared in child pane and Codex shell
configuration; the child-role guard still prevents children from managing the run.

Starting/sending persists the task and uncertain-delivery state before mutation.
Inspect the recorded terminal after failures; don't duplicate prompts or start another
Director to bypass an error. Wait/collect fail closed on identity mismatch. The
protocol is cooperative and cannot atomically intercept direct typing.
