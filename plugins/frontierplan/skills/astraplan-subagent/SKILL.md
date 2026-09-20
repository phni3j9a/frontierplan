---
name: astraplan-subagent
description: Astra-led research, user dialogue, design and planning, followed by coordinated implementation and Astra final acceptance through subagent.
triggers:
  - user
---

# AstraPlan-subagent

Apply only to the engineering task explicitly invoked by the user and its follow-ups.
Small ordinary tasks outside this invocation do not activate FrontierPlan.
If a delegated assignment identifies you as Director, Worker, Design or Reviewer,
perform that assignment yourself; never initialize another run or delegate again.
This includes the Director: it researches personally, not through children.

Otherwise you are Main, the execution coordinator. Use only the **subagent**
backend for this run. Do not combine this skill with another FrontierPlan skill,
Axiom, or an unrequested hidden-agent fallback.

Resolve the plugin root two directories above this SKILL.md. Read, in order:
- [Shared workflow](../../core/workflow.md)
- [Role boundaries](../../core/roles.md)
- [Dialogue and decision handoff](../../core/handoff.md)
- [subagent operations](../../backends/subagent.md)
Read [Review](../../core/review.md) before implementation review.

Use `profiles/director/astra.toml` and the shared role-specific `profiles/*.toml`.
Astra / `xhigh` is mandatory from the first substantive user reply through final
acceptance. Main inherits its existing Codex session's model and effort; this backend still
requires Codex native subagent tools. This skill never replaces Main or changes
global defaults. Child effort values are lowercase.

Before implementation, **only Astra** understands the request, researches code and
external sources with available authorized tools, performs isolated probes,
chooses design, drafts user replies, and creates the Plan. Main passes original
user words and known locations/permissions; Main does not research or re-plan.
Do not launch Worker, Design or Reviewer before a current Director Plan and actual
user implementation authorization. Once started, Main splits, assigns, integrates
and adjudicates review against that Plan. Director decides substantive changes
and final acceptance and writes the final user report.

Use the bundled local helpers for packets and freshness checks. They are cooperative
workflow aids, not a sandbox, proof of consent, or automatic tool interception.
Retain the Director for the ongoing user work, and implementation participants
through final acceptance. A returned turn, an intermediate user reply, or a context
compaction is not permission to close sessions. Never claim unavailable tools,
unobserved model routing, unrun tests, or an unreturned Director decision succeeded.
