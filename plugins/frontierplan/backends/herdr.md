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

First split is right/0.5; later splits use the largest owned child area. No global
rebalance or focus stealing; respect manual resize/movement.

## Reports and continuation
```
python3 "$hd" collect --task "$director"
python3 "$fp" decision --task "$director"
python3 "$fp" message --run "$run" --file "$new_user_message"
python3 "$hd" send --task "$director" --file "$followup"
```
Children use the shared begin/report commands embedded in their packets. Always
collect through herdr.py to record live idle/activity evidence. Use send for the
same Director, Worker or Reviewer; never routinely replace a retained session.

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
After finish, use `python3 "$hd" close --task "$task"` for each owned participant.
Closed records are not evidence of actual closure; the transport verifies and closes
first. Never close Main, active/uncollected work or a terminal with changed identity.

## Waiting

Use one `python3 "$hd" wait --run "$run" --timeout 3600` process per run. Retain its
execution handle. Local two-second state checks do not invoke Main's model. The
outer result wait must also be `yield_time_ms=3600000` where the host supports it;
the helper timeout alone does not prevent short model wakeups. Resume the SAME handle,
including yielded wrappers. Do not spawn duplicate waiters or repeatedly call status.
Events/steering/process exit can return sooner; act immediately. Retained idle agents
with collected complete reports do not count as pending. Pending:0 does not close them.
Unchanged blocked notifications are suppressed, not resolved. Resolve each returned
event or explicitly retain its blocker before waiting again.

If the host/higher-priority rules cannot honor the one-hour result wait, state the
observed limitation; don't silently substitute short polling or label it equivalent.
Continue independent useful work or yield to the user. Do not claim unattended
monitoring without a live supported wait mechanism. Long-running process monitoring
after implementation starts belongs to its Luna Worker, not repeated Main checks.

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
