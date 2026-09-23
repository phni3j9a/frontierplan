# Codex native subagent backend

This backend is executed by Main using the host's actual native agent tools.
The Python helper prepares packets and records receipts; it does NOT invoke
spawn_agent through subprocess, API, an MCP server, or an invented Python bridge.
No custom agent TOML or global config is installed. Main remains the existing session.

## Capability check (transport only, not project research)

Inspect the live tool schema: explicit model/effort selection, persistent returned
agent identity, same-session follow-up, event-aware wait and safe close must exist.
Use exposed field names, not assumed schema. In the predecessor's Multi-Agent V2
surface these were spawn_agent with model/reasoning_effort/fork_turns, followup_task
and wait_agent; other versions may differ. These names are examples, not registered
tools created by FrontierPlan. Refuse unspecified model inheritance or backend fallback.

Require effective children to meet the intended workspace-write + never boundary.
Native children may inherit the parent's live permission overrides, even over a
custom profile. If the existing parent/session cannot meet the boundary, report it
and request authorized setup; do not silently use broad access, switch Main's mode,
or install a custom agent to pretend it overrides live permissions. The helper cannot
sandbox or authenticate native children. Verify effective model/effort and completion
from real runtime evidence. Preserve the evidence with the returned agent handle.

## First Director
```
fp=<plugin-root>/scripts/frontierplan.py
python3 "$fp" init --backend subagent --cwd "$project" --request-file "$request"
python3 "$fp" prepare --run "$run" --role director --file "$assignment"
```
Read the returned profile and packet. Call the actual spawn tool with Astra /
`xhigh` and the packet as its assignment, using no conversation fork when supported
(e.g. `fork_turns="none"` on the known V2 surface). Do not fork Main's hidden reasoning
or full tool history as a substitute for user dialogue. No tier override for Director.
Only one Director is created; no Worker/Design/Reviewer before implementation.

After successful native spawn, write a handle file from the actual tool result:
```
{"agent_id":"<returned-id>","evidence":"<launch/runtime evidence reference>"}
```
Then `python3 "$fp" bind --task "$director" --handle-file "$handle"`.
This records evidence supplied by Main, not an independently verified model claim.

The child reads the packet and uses its begin/report commands. Wait via the host's
native event-aware wait, then verify idle state and collect:
```
python3 "$fp" collect --task "$director"
python3 "$fp" decision --task "$director"
```
Forward every new user message with `message`, then prepare its next request with
`prepare --run "$run" --role director --file "$followup" --reuse "$director"`.
Send the new packet through the host's same-session follow-up tool to the recorded
ID. Do NOT call spawn again or rebind. The helper preparation is not actual delivery;
verify the tool result before claiming the follow-up was sent.

## Implementation and return

After actual authorization and the current Director Plan, use authorize/start.
Prepare Worker/Design/Reviewer packets in the same manner; spawn separately and bind
each returned identity once. Reserve concurrency for Director and Reviewer; manage
independent work under the host limit. Use fresh Workers for bounded fixes by default
and the same Reviewer for re-review. No Director-to-worker nested spawning.

Worker's profile requests fast separately from effort max. On schemas with the
corresponding API field, the predecessor used service_tier="priority" for the CLI's
fast tier. Use ONLY a field/value supported by the live schema; otherwise verify
inherited fast evidence or disclose unverified/unavailable fast while retaining the
specified Luna/max model/effort. Do not claim fast based on the label alone.

### Release completed Worker/Design assignments

Collect the complete report after verifying live identity and idle state. Integrate
its work, check that no writes/owned processes remain, and get the decision template:
```
python3 "$fp" release-check --task "$worker"
```
Save the JSON outside the candidate checkout. Preserve `binding`. Set `decision`'s
`integrated`, `assignment_complete`, `no_active_processes`, `no_longer_needed` to true
only after checking those facts, and give a concrete `reason`. Recheck live state and
the binding immediately before calling the host's actual close tool on the recorded
agent ID. Save its successful result/reference in a closure file:
```json
{"agent_id":"<actual closed ID>","closed":true,"evidence":"<actual close tool result or reference>"}
```
Only after successful native closure:
```
python3 "$fp" release-record --task "$worker" --file "$release_decision" --closure-file "$closure"
```
These commands record Main-supplied evidence, not an independently verified native
closure. They never invoke a native tool. Uncertain closure or a stale binding after
close needs explicit inspection/recovery; keep the evidence and do not blindly retry
close or falsely mark the assignment released. A slow/idle participant is not lost.
If safe close is unavailable, retain the session and disclose that capability limit.

Released assignments remain evidence for candidate/acceptance; they do not replace
independent review. Use fresh Workers for later fixes, retaining the same Reviewer.
Use candidate/decision/finish once the integrated tree and participants are quiescent.
Director receives actual evidence and writes acceptance/final report. At final wrap-up,
close each remaining owned idle session with the native tool, then use `close-record`.
For an already released task, only `close-record` is needed; never close its ID again.
Director and Reviewer cannot use assignment release to bypass final acceptance.

## Wait and recovery

Follow [Completion reconciliation](../core/waiting.md). Retain IDs across turns and
compaction. On entry/resume, notifications and each heartbeat, inspect:
```
python3 "$fp" status --run "$run"
```
Its `uncollected` list compares each current request's complete/blocked result with
its receipt and does not consume notifications. Check the host's actual live state
before collecting. Also inspect pending/blocked tasks in `tasks`; absence from
`uncollected` alone does not mean all work is finished or all blockers are resolved.

Wait on useful pending sessions through the actual native event-aware tool, with an
upper bound of about 300 seconds (e.g. `timeout_ms=300000` only if the live schema
supports it). A lower host or higher-priority cap takes precedence. Receive native
notifications immediately, reconcile on return, and continue the supported wait while
pending work remains. A final response with a promise to monitor does not provide a
continuation mechanism. Do not emulate native notifications with shell watchers or
claim unattended resumption without actual host support.

A lost session requires observed runtime evidence, `retire-lost`, and a replacement
with the same role/model plus current dialogue, Plan, prior reports/findings. Merely
idle is not lost. An unavailable Astra is a blocked Director path, not permission
for Main/Luna to take over research/planning/acceptance.
