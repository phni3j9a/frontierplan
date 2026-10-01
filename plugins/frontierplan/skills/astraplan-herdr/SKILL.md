---
name: astraplan-herdr
description: Explicitly invoke Astra-led planning and Main-led implementation with independent task review in visible Herdr panes.
disable-model-invocation: true
triggers:
  - user
---

# AstraPlan-herdr

Use this entry for the user's explicitly invoked task and its follow-ups.
Read the [shared workflow](../../core/workflow.md) and
[role/model table](../../core/roles.md) from this loaded Plugin.
Read the [Herdr operations and pane layout](../../backends/herdr.md), then
load the installed official guidance with `herdr --skill`.

Main relays Astra's planning decisions and user dialogue. Once implementation
starts, Main coordinates assignments, integration verification and completion.
Reviewer verifies assigned implementation tasks; Astra checks overall intent and
Plan fulfillment once. Follow the shared workflow for their boundaries. Keep
Main's existing session and use this selected backend. Control panes and agents
directly through the Herdr CLI.
