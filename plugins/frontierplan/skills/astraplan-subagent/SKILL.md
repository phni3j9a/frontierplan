---
name: astraplan-subagent
description: Explicitly invoke Astra-led planning and Main-led implementation with independent task review through Codex native subagents.
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
starts, Main coordinates assignments, integration verification and completion.
Reviewer verifies assigned implementation tasks; Astra checks overall intent and
Plan fulfillment once. Follow the shared workflow for their boundaries. Keep
Main's existing session and use this selected backend. Call native tools directly.
