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

Codex limits nesting with `agents.max_depth` (default 1): a child cannot be relied on
to spawn its own children. That is why Astra's research requests go through Main's
relay. Do not change the user's depth setting to work around this.

Require effective children to meet the intended workspace-write + never boundary.
Native children may inherit the parent's live permission overrides, even over a
custom profile. If the existing parent/session cannot meet the boundary, report it
and request authorized setup; do not silently use broad access, switch Main's mode,
or install a custom agent to pretend it overrides live permissions. The helper cannot
sandbox or authenticate native children. Verify effective model/effort and completion
from real runtime evidence. Preserve the evidence with the returned agent handle.

## Spawning and binding

Every new child follows the same steps. The helper prints a `packet` and `profile`.
Call the actual spawn tool with that profile's model and effort and the packet as
the assignment, with no conversation fork when supported (e.g. `fork_turns="none"`
on the known V2 surface). Then record the returned identity once:
```
{"agent_id":"<returned-id>","evidence":"<launch/runtime evidence reference>"}
```
```
python3 "$fp" bind --task "$task" --handle-file "$handle"
```
This records evidence supplied by Main, not an independently verified model claim.
Luna roles request fast separately from effort max. Use ONLY a field/value the live
schema supports (the predecessor used `service_tier="priority"` for the CLI fast
tier); otherwise disclose unverified fast while keeping Luna/max.

A continuation prepares a packet for an existing task; send it through the host's
same-session follow-up tool to the recorded ID. Do not spawn again or rebind. The
helper preparation is not delivery; verify the tool result before claiming it was sent.

## Planning relay

```
fp=<plugin-root>/scripts/frontierplan.py
python3 "$fp" init --backend subagent --cwd "$project" --request-file "$request"
python3 "$fp" start-director --run "$run" [--file "$transport_facts"]
```
Spawn Astra from the packet (Astra / `xhigh`, no tier override) and bind it. When her
turn returns, verify idle state and record her decision:
```
python3 "$fp" collect --task "$director"
python3 "$fp" decision --task "$director"
```
Do exactly what `next` says, without adding judgment:

- `relay`: run `python3 "$fp" relay --run "$run"`. `spawn_researchers` lists packets
  to spawn and bind as researchers (Luna / `max`). Wait for them, collect each, and
  run `relay` again. `return_to_director` gives a prepared Astra packet: send it as a
  follow-up to Astra, then close the listed researchers (see closing below).
- `relay_to_user`: show `relay_to_user` to the user exactly as written. When the user
  answers:
  ```
  python3 "$fp" message --run "$run" --file "$user_message"
  python3 "$fp" forward --run "$run"
  ```
  and send the prepared packet to Astra as a follow-up.
- `start` / `relay_to_user_then_start`: show the text if present, then
  `python3 "$fp" start --run "$run"`.

If the user writes during research, `message` answers `next: relay`: finish the relay
and the new words reach Astra together with the reports. A consultation-only request
ends with `python3 "$fp" finish --run "$run" --discussion`.

## Execution

```
python3 "$fp" prepare --run "$run" --role worker --file "$assignment" [--cwd "$worktree"]
python3 "$fp" prepare --run "$run" --role reviewer --file "$review_request"
python3 "$fp" prepare --run "$run" --role worker --file "$accepted_fixes" --reuse "$worker"
python3 "$fp" consult --run "$run" --file "$question"
```
New tasks are spawned and bound; `--reuse` and `consult` produce follow-ups for the
existing session. Reserve concurrency for Astra and the Reviewer and manage
independent work under the host limit. After `consult`, collect and run `decision`.

When review has converged and every Worker/Design/Reviewer is idle and collected:
```
python3 "$fp" final-check --run "$run" --file "$evidence"
```
Send the packet to Astra, collect, and run `decision`. It runs once per Plan;
accepted fixes go to the responsible Worker and the same Reviewer. Then:
```
python3 "$fp" finish --run "$run" --file "$final_report"
```

## Closing participants

Close a researcher after its report returned to Astra, a Worker/Design/Reviewer
when Main ends its review cycle, and Astra only after finish. Verify live idle state
and the collected current report, call the host's actual close tool on the recorded
agent ID, and save its result:
```json
{"agent_id":"<actual closed ID>","closed":true,"evidence":"<actual close tool result or reference>"}
```
```
python3 "$fp" close-record --task "$task" --closure-file "$closure"
```
This records Main-supplied evidence; it never invokes a native tool. Uncertain
closure needs explicit inspection; do not blindly retry or mark it closed. If safe
close is unavailable, keep the session and disclose that capability limit.

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
with the same role/model plus the current user messages, Plan and prior reports.
Merely idle is not lost. An unavailable Astra blocks planning; Main does not take
over research or planning.
