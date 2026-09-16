# herdr backend

Requires Python 3.11+, Git for candidate verification, herdr and Codex on the same
host, and a Main Codex conversation already inside herdr. Set absolute helper paths
from this installed plugin, not a guessed checkout path:
```
fp=<plugin-root>/scripts/frontierplan.py
hd=<plugin-root>/scripts/herdr.py
```
Main is expected to be Sol / `xhigh`. Before starting it, the host-specific launch
configuration used by the predecessor was:
```
codex -m gpt-5.6-sol -c 'model_reasoning_effort="xhigh"' -c background_terminal_max_timeout=3600000
```
Verify these flags against the installed CLI. Never edit user configuration yourself.

## Initialize and start ONLY Director

Save the original user request to a UTF-8 file, then:
```
python3 "$hd" init --cwd "$project" --request-file "$request"
python3 "$hd" spawn --run "$run" --role director --file "$assignment"
```
Retain returned run/task handles. Assignment contains original dialogue references,
known repository/worktree locations and permissions, not Main's researched Plan.
For a shared app-server without HERDR_PANE_ID, inspect available herdr panes and
match the current Codex conversation before using:
```
python3 "$hd" init --cwd "$project" --request-file "$request" \
  --main-pane "$verified_pane" --main-terminal-id "$verified_terminal" --socket "$socket"
```
Never pick Main by focus, matching cwd or “only agent”. If herdr advertises a session
ID it must match; otherwise verify terminal content or an explicit user association.
Main is bound by conversation + terminal identity and may move without being confused
with a replacement pane. First split is right/0.5; later splits use the largest owned
child area. No global rebalance or focus stealing; respect manual resize/movement.

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

Starting/sending persists the task and uncertain-delivery state before mutation.
Inspect the recorded terminal after failures; don't duplicate prompts or start another
Director to bypass an error. Wait/collect fail closed on identity mismatch. The
protocol is cooperative and cannot atomically intercept direct typing.
