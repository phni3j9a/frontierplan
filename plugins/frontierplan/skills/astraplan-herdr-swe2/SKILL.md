---
name: astraplan-herdr-swe2
description: Explicitly invoke Astra-led planning and Main-led implementation in Herdr panes, using Devin SWE-2 for Researcher and Worker.
disable-model-invocation: true
triggers:
  - user
---

# AstraPlan-herdr-swe2

Use this entry for the user's explicitly invoked task and its follow-ups.
Read the [shared workflow](../../core/workflow.md) and
[role/model table](../../core/roles.md) from this loaded Plugin.
Read the [Herdr operations and pane layout](../../backends/herdr.md), then
load the installed official guidance with `herdr --skill`.
Also read the [SWE-2 launch difference](../../backends/swe2.md); it changes only
Researcher and Worker. Astra, Design and Reviewer remain Codex seats.

Main relays Astra's planning decisions and user dialogue. Once implementation
starts, Main coordinates assignments, independent review and completion, with
Astra's one final check. Keep Main's existing session and use this selected
backend. Control panes and agents directly through the Herdr CLI.
