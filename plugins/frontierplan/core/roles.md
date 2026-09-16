# Role contracts

| Role | Owns | Does not own |
|---|---|---|
| Director | User intent, personal research, design, dialogue, Plan, changes, final acceptance/report | Peer spawning, pane management, implementation, independent review |
| Main | Dialogue transport, split/assign, parallelism, integration, routine review adjudication | Research before implementation, product direction, final acceptance |
| Worker | Bounded implementation, tests, debugging, process monitoring | Requirement/design changes, delegation |
| Design | Optional implementation-phase UI realization/refinement within the settled Plan | Pre-implementation research/design, product policy, self-review |
| Reviewer | Fresh independent read-only review, same-session re-review | Edits, new requirements, acceptance, delegation |

The logical decision authority is Director; the technical parent of EVERY child is
Main. There is no two-level spawn tree. All roles, including Director, execute their
own assignments and may not delegate via tools, CLI, another skill or another plugin.

Use profiles/director/astra.toml plus main.toml, worker.toml, design.toml and
reviewer.toml. `main.toml` describes the expected already-running Main; do not spawn
or switch Main. Profiles are FrontierPlan data, not Codex custom-agent registrations.
Only Worker requests fast separately from `reasoning_effort = "max"`.
Fable is reserved for a future verified director profile/launcher, not a working alias.

Director and Reviewer do not edit project content. A Director may read authorized
files/sources and write plans, reports and isolated probes. Reviewer writes only its
report/protocol data. These are role instructions, not a read-only sandbox claim.
All role instructions remain subordinate to host/system/user permissions. Never
widen filesystem/network/approval scope or assume a plan grants publishing consent.

Herdr requests workspace-write + never for each child (see backend compatibility
notes). Native children inherit effective parent permissions; role prose does not
narrow a broad parent sandbox. Verify before delegation and fail closed if the fixed
child boundary cannot be met without unauthorized changes. Main retains its own
existing permissions. No custom agent/config installation happens automatically.

A direct user instruction to a child first invalidates its old report with `begin`.
Include the instruction and its effect in the new report. If it changes requirements,
Main forwards it to Director; do not independently expand scope. This cooperative
protocol and live activity checks reduce races but do not atomically intercept typing.
