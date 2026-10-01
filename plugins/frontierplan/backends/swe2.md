# SWE-2 difference

Use the shared [Herdr operations](herdr.md), including the same pane layout.
Only Researcher and Worker launch with Devin; the [role table](../core/roles.md)
defines the model. Confirm Devin CLI is available before creating their panes.

```bash
herdr agent start "$name" --kind devin --pane "$pane" -- \
  --permission-mode dangerous --model "$model"
```

Set `model` to the SWE-2 model in the role table. The pane's working directory
is the assignment's project. Prompt, wait, read, same-session fixes and cleanup
use the same Herdr commands as the Codex seats.

This preserves the existing SWE-2 variant's permission choice: `dangerous`
auto-approves all tools without an OS sandbox. It is broader than the Codex launch
request. A read-only Researcher assignment is an instruction, not enforcement.
Use this variant only with that trust; do not silently apply it to other roles.

Devin reads the user's configuration, rules and integration hooks unchanged.
Effort is part of the model name and no fast tier is requested. Usage follows
the account's Devin limits. For a routing check, optionally add
`--export "$session_export"` with a chosen output path and inspect Devin's
recorded model names after a turn. Without that evidence, report routing as
unverified rather than treating the launch arguments as proof.
