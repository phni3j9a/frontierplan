# Native subagent operations

Main uses the host's actual spawn, follow-up, wait and lifecycle tools directly.
There is no shell bridge, helper packet, custom profile installation or global
configuration change. This entry needs Codex native subagent capabilities;
another host without those tools should explain the limitation.

Inspect the live tool schema and select the explicit model/effort from the
[role table](../core/roles.md). Names such as `spawn_agent`,
`followup_task` and `wait_agent` are examples; use only tools and fields the
host actually exposes. If that routing cannot be expressed, report the missing
capability rather than inheriting an unspecified child model or changing backend.

Give each child its assignment, relevant project instructions and the applicable
shared workflow/role guidance. Prefer a focused context without an entire
conversation fork when the host supports it. Main remains the parent of all
participants, including Researchers requested by Astra; nested agents are not
needed.

Retain the returned ID and use same-session follow-up for fixes, re-review and
Astra consultation. Request Luna's fast tier only through a supported field;
lack of tier evidence does not imply a different model or effort. Permissions
may inherit from the parent; use the host's actual boundary and respect the
user's existing authorization. A role prompt does not narrow that boundary.

Use native completion notifications and supported waits. Keep handles across
yields, read results before continuing, and inspect retained IDs after resume
rather than spawning duplicates. A lost session needs its current task context
passed to any replacement. No shell watcher or receipt file adds native events.

When work is finished, use the actual release/close operation if available.
If the host has none, leave the idle session and report that limitation; do not
invent a tool or claim that interrupting a turn deleted the session.
