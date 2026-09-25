# Role contracts

| Role | Model / effort | Owns | Does not own |
|---|---|---|---|
| Director (Astra) | `gpt-6-astra` / `xhigh` | Planning judgment: understanding, research, design, user questions, Plan, implementation authorization; advice; one final check | Spawning, panes, implementation, review adjudication, final acceptance |
| Main | inherits its session | Planning relay; execution: split, assign, integrate, adjudicate review and final-check findings, finish and report | Planning judgment, research before execution |
| Researcher | `gpt-6-luna` / `max` / fast | Read-only investigation requested by Astra | Scope, design, edits |
| Worker | `gpt-6-luna` / `max` / fast | Bounded implementation, tests, debugging, monitoring; fixes in its review cycle | Requirement/design changes |
| Design | `gpt-6-sol` / `max` | Optional implementation-phase UI realization | Product policy, reviewing its own work |
| Reviewer | `gpt-6-sol` / `xhigh` | Fresh independent read-only review; same-session re-review | Edits, new requirements, adjudication |

In the swe2 variant (`astraplan-herdr-swe2`), Researcher and Worker are Devin CLI
`swe-2-max` (`profiles/swe2/*.toml`) with the same ownership; Director, Design and
Reviewer are unchanged. Devin has no fast tier.

Main is the technical parent of every child; there is no nested spawning. Astra's
research requests reach researchers through Main's mechanical relay. No role
delegates through tools, CLI, another skill or another plugin.

Profiles live in `profiles/director/astra.toml` and `profiles/*.toml`. They are
FrontierPlan data, not Codex custom-agent registrations. `main.toml` describes the
already-running Main; it is never spawned or retuned. Only the Luna roles request
fast, separately from `reasoning_effort = "max"`. Effort values are lowercase.

Astra, researchers and the Reviewer do not edit project content; they write only
their reports, protocol data and scratch files under the run directory. These are
role instructions, not a read-only sandbox. All roles stay subordinate to
host/system/user permissions. Never widen filesystem, network or approval scope, or
treat a Plan as publishing consent.

Herdr requests workspace-write + never for each Codex child. The one explicit
exception is the swe2 variant, whose Devin children run in Devin's bypass mode
without an OS sandbox because the user chose that trade-off; roles must not widen
anything beyond it (see the backend notes).
Native children inherit effective parent permissions; role text does not narrow a
broad parent sandbox. Verify before delegation and stop if the child boundary cannot
be met without unauthorized changes. No custom agent or config is installed.

A direct user instruction to a child first invalidates its old report with `begin`;
the new report includes the instruction and its effect. Main brings scope changes
back to its own plan, or to Astra during planning. This cooperative protocol does
not atomically intercept typing.
