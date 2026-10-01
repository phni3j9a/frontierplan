# Roles and model selection

This is the shared model table for all three entry points. Select the role's
model and lowercase effort explicitly when starting a child. Main inherits its
existing session; FrontierPlan neither launches nor retunes it.

| Role | Model | Effort | Tier | Responsibility |
|---|---|---|---|---|
| Astra (Director) | `gpt-6-astra` | `xhigh` | Host default | Research, design, Plan, advice, one final check |
| Main | Existing session | Inherited | Inherited | Planning relay, then execution and review decisions |
| Researcher | `gpt-6-luna` | `max` | fast | Focused research without project changes |
| Worker | `gpt-6-luna` | `max` | fast | Implementation, tests, fixes and monitoring |
| Design | `gpt-6-sol` | `max` | Host default | Optional UI implementation |
| Reviewer | `gpt-6-sol` | `xhigh` | Host default | Independent review and re-review |

In **astraplan-herdr-swe2**, only Researcher and Worker instead use Devin CLI's
`swe-2-max`. Effort is encoded in that model name; there is no fast-tier override.
The other roles are unchanged. See [SWE-2 operations](../backends/swe2.md).

For each assignment, provide the relevant role and task context directly.
Main creates the participants and relays research requests, so Astra need not
have permission to create nested agents. Workers retain ownership through fixes;
the Reviewer retains the independent review context.

Request fast for Luna where the host supports it. If it is unavailable or cannot
be verified, say so while preserving the requested model and effort. Do not
infer effective routing or permissions from an agent's self-description.
