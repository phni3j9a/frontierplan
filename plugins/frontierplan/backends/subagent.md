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
independent work under the host limit. Use original Workers for fixes and the same
fresh Reviewer for re-review. No Director-to-worker nested spawning.

Worker's profile requests fast separately from effort max. On schemas with the
corresponding API field, the predecessor used service_tier="priority" for the CLI's
fast tier. Use ONLY a field/value supported by the live schema; otherwise verify
inherited fast evidence or disclose unverified/unavailable fast while retaining the
specified Luna/max model/effort. Do not claim fast based on the label alone.

Use candidate/decision/finish from the shared helper after the integrated worktree
and participants are quiescent. Director receives the actual evidence and writes
acceptance/final report. Then use the host's close tool on each owned idle session;
only after successful native closure call `close-record`. Preserve pending/lost
handles rather than pretending they were closed. Do not close on a turn-complete event.

## Wait and recovery

Retain IDs across turns/compaction. Wait on the useful pending set, not on already
collected idle participants. On the known V2 surface use an event-aware one-hour
upper wait (`timeout_ms=3600000`), which may return earlier on activity/steering.
Don't repeatedly wake Main with default/short status checks. If the host has a lower
limit, disclose it and use the supported event mechanism without pretending the
one-hour policy is met. Never invent unavailable wait arguments or background work.

A lost session requires observed runtime evidence, `retire-lost`, and a replacement
with the same role/model plus current dialogue, Plan, prior reports/findings. Merely
idle is not lost. An unavailable Astra is a blocked Director path, not permission
for Main/Luna to take over research/planning/acceptance.
