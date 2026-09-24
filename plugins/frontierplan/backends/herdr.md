# herdr backend

Requires Python 3.11+ and herdr plus Codex on the same host; Git only labels the
final-check packet. Main is an existing session inside herdr, not necessarily
Codex: a recognized Devin or another agent can coordinate while all children still
run through Codex.
Main keeps its existing agent, model, effort and permissions. FrontierPlan never
launches, switches or retunes Main, and never edits user configuration automatically.
Set absolute helper paths from this installed plugin, not a guessed checkout path:
```
fp=<plugin-root>/scripts/frontierplan.py
hd=<plugin-root>/scripts/herdr.py
```

## Initialize and start Astra

Save the user's exact request to a UTF-8 file, then:
```
python3 "$hd" init --cwd "$project" --request-file "$request"
python3 "$hd" spawn --run "$run" --role director [--file "$transport_facts"]
```
Retain the returned run/task handles and `main_identity`. The optional file holds
transport facts only (repository/worktree paths, available environments, known
permissions), never Main's research or a Plan. The common
`frontierplan.py init --backend herdr` entry point uses the same binding procedure;
it cannot create an unbound herdr run.

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
before Main-only operations such as message, forward, prepare, decision and finish.

Main's original terminal remains the anchor after moves/swaps. With an explicit or
Codex session identity, its current pane is located by terminal ID. Auto-detection
also needs a correct current `HERDR_PANE_ID`; if the host leaves it stale after a
move, stop and re-establish the verified current context or explicit identity. Do
not infer caller identity from the saved run alone. Replaced terminals, changed
agent/session identities and ambiguous matches fail closed before pane mutation.
Pre-existing Codex/herdr runs keep their original Codex ownership checks; there is
no automatic owner migration. Native subagent runs still require Codex native tools.

The plugin ships Codex, Claude Code and portable (Devin) manifests. Claude Code as
Main installs the plugin through its marketplace and invokes this SKILL explicitly;
herdr reports its pane as `claude` with the conversation's session ID, so the
current-pane identity path applies. Any non-Codex host must explicitly load this
SKILL and its referenced contracts and be able to run the local helpers on the herdr
host; FrontierPlan does not establish remote connectivity. Actual provider/host compatibility requires a real-host smoke
test. Simulated Devin tests are not evidence of real model routing or billing.

### Role layout

The Director splits Main `right / 0.4`: Main retains the left 40%, Astra gets the
right 60%. The first researcher or Worker/Design/Reviewer splits Astra `down / 0.4`: Astra retains the upper 40% of that right region and the
execution area receives the lower 60%. Subsequent researcher/Worker/Design/Reviewer spawns
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
execution panes are closed, Astra occupies the right region again. If new work is
authorized before finish, its first execution pane recreates `down / 0.4` from the
verified Astra anchor. Retained Reviewer panes also count as execution panes.
Runs started before role-layout metadata existed cannot guess an execution region;
finish/clean up those runs with their existing participants before starting a new run.
A lost Director anchor likewise requires explicit layout/session recovery; the helper
does not split Main to silently replace it.

## Planning relay

After Astra's turn returns, collect it and record the decision:
```
python3 "$hd" collect --task "$director"
python3 "$fp" decision --task "$director"
```
Do exactly what `next` says, without adding judgment:

- `relay`: `python3 "$hd" relay --run "$run"` starts one researcher per request with
  Astra's exact text. Wait, collect each researcher, then run `relay` again. When all
  reports are collected it sends Astra their unedited report paths and closes the
  researchers. A `wait` result lists the researchers still pending.
- `relay_to_user`: show `relay_to_user` to the user exactly as written. When the user
  answers, store and forward the words:
  ```
  python3 "$fp" message --run "$run" --file "$user_message"
  python3 "$hd" forward --run "$run"
  ```
- `start` / `relay_to_user_then_start`: show the text if present, then
  `python3 "$fp" start --run "$run"`.

If the user writes while Astra is working, store it with `message`; after her turn
returns and is collected, `decision` rejects a stale planning decision and you run
`forward`. If research is in flight, `message` answers `next: relay`: finish the
relay and the new words reach Astra together with the reports. A consultation-only request ends with `python3 "$fp" finish --run "$run" --discussion`.

## Execution

```
python3 "$hd" spawn --run "$run" --role worker --file "$assignment" [--cwd "$worktree"]
python3 "$hd" spawn --run "$run" --role reviewer --file "$review_request"
python3 "$hd" send --task "$worker" --file "$accepted_fixes"
python3 "$hd" send --task "$reviewer" --file "$rereview_request"
python3 "$hd" consult --run "$run" --file "$question"
```
Roles: `worker` (Luna MAX fast), `design` (Sol MAX), `reviewer` (Sol XHIGH).
Children use the begin/report commands embedded in their packets. Always collect
through herdr.py to record live idle/activity evidence. `send` continues the same
Worker/Design/Reviewer session; Astra's turns use `forward`, `relay`, `consult` and
`final-check`. After `consult`, collect and run `decision`; the advice is Main's to
adopt (`next: main_decides`) unless it carries a `user_response` to relay.

When review has converged and every Worker/Design/Reviewer is idle and collected:
```
python3 "$hd" final-check --run "$run" --file "$evidence"
python3 "$hd" collect --task "$director"
python3 "$fp" decision --task "$director"
```
It runs once per Plan. Adjudicate its findings like Reviewer findings; accepted
fixes go to the responsible Worker and the same Reviewer, not back to Astra. Then:
```
python3 "$fp" finish --run "$run" --file "$final_report"
```

## Closing participants

```
python3 "$hd" close --task "$task"
```
Close a researcher once `relay` has returned its report (relay does this), a
Worker/Design/Reviewer when Main ends its review cycle, and Astra only after finish.
Close requires the participant's current report to be collected and unchanged
activity since collection; unresolved Worker/Design/Reviewer blockers stay open until
finish. Never close Main.

Close verifies ownership, the unique original terminal, the current pane occupant,
the collected report and unchanged `state_change_seq`. A moved owned terminal is
closed only at its verified current pane, never by reusing its original pane ID.
Herdr's pane lookup and close are separate calls; these cooperative checks do not
atomically intercept direct typing or pane swaps. Avoid manual input during closure.

Before closing, the helper persists a `closing` record with the pane/terminal
identity. A lost response or crash leaves that record and blocks retry; it is not
success. Inspect that terminal and whether closure occurred before recovering the
record manually; never retry against a reused pane ID. Closing keeps task files,
reports and evidence.

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
and closed tasks are not pending; pending:0 alone does not close anyone.

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
adds fast overrides. No role enables network access; Astra and researchers use only already available
authorized search/connector/command tools. Missing tools are blockers.
Main's explicit identity variables are cleared in child pane and Codex shell
configuration; the child-role guard still prevents children from managing the run.

Starting/sending persists the task and uncertain-delivery state before mutation.
Inspect the recorded terminal after failures; don't duplicate prompts or start another
Director or researcher to bypass an error. Wait/collect fail closed on identity mismatch. The
protocol is cooperative and cannot atomically intercept direct typing.
