---
name: astraplan-subagent
description: Explicitly invoke Astra-led planning and Main-led implementation with independent review through Codex native subagents.
disable-model-invocation: true
triggers:
  - user
---

# AstraPlan-subagent

Use this entry for the user's explicitly invoked task and its follow-ups.
Read the [shared workflow](../../core/workflow.md) and
[role/model table](../../core/roles.md) from this loaded Plugin.
Use the [native subagent operations](../../backends/subagent.md).

Main relays Astra's planning decisions and user dialogue. Once implementation
starts, Main coordinates assignments, independent review and completion, with
Astra's one final check. Keep Main's existing session and use this selected
backend. Call native tools directly.
