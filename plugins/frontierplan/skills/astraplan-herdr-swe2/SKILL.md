---
name: astraplan-herdr-swe2
description: AstraPlan-herdr with Devin SWE-2 in the Luna seats. Astra owns research and planning with SWE-2 researchers; Main then coordinates SWE-2 implementation, independent Sol review and Astra's one-time final check through visible herdr panes.
disable-model-invocation: true
triggers:
  - user
---

# AstraPlan-herdr-swe2

Apply only to the engineering task explicitly invoked by the user and its follow-ups.
Small ordinary tasks outside this invocation do not activate FrontierPlan.
If a delegated assignment identifies you as Director, Researcher, Worker, Design or
Reviewer, perform that assignment yourself; never initialize another run or delegate.

Otherwise you are Main. This is `astraplan-herdr` with one change: Researchers and
Workers run as Devin CLI `swe-2-max` instead of Codex `gpt-6-luna` / `max` / fast.
Astra, Design and the Reviewer stay on Codex. Use only the **herdr** backend and
initialize the run with `--variant swe2`; the variant is fixed for the whole run.
Do not combine this skill with another FrontierPlan skill, Axiom, or an unrequested
hidden-agent or model fallback. If Devin or SWE-2 is unavailable, stop and report.

Resolve the plugin root as the directory two levels above this SKILL.md, using
the path the host provided for this invocation. If no path was provided, use only
the copy the host installed and loaded as this plugin; never substitute a source
checkout, worktree, extracted package, or another copy found by searching. If that
copy cannot be identified uniquely, stop and ask the user. State the resolved root
before the first helper command. Read, in order:
- [Shared workflow](../../core/workflow.md)
- [Role boundaries](../../core/roles.md)
- [Decisions and relay](../../core/handoff.md)
- [herdr operations](../../backends/herdr.md), including its SWE-2 variant section
Read [Review](../../core/review.md) before independent review.

## Two phases

**Planning — Astra decides, you relay.** Start the run with the user's exact words
(`python3 "$hd" init --variant swe2 ...`) and start Astra. Until the Plan starts, you
do not research, summarize, reinterpret or answer for her. After each Astra turn,
run `decision` and do its `next` step: relay her research to SWE-2 researchers, show
her `user_response` to the user verbatim, give new user messages to her with
`forward`, and `start` when she has recorded implementation authorization. Resolve
only transport problems yourself.

**Execution — you decide (axiom_for_herdr).** Split, assign, integrate and
adjudicate review against Astra's Plan. Keep each responsible SWE-2 Worker through
its review cycle and send it the accepted fixes. Keep one independent Sol Reviewer
through the cycle; there is no round limit. Consult Astra when the Plan no longer
fits or a finding keeps returning. When review converges, run Astra's one-time
final check, adjudicate its findings like any Reviewer finding, then write the
final report and finish.

Return to the user only for Astra's planning messages, the completion report, or a
scope/cost-changing branch presented as options with a recommendation. Never ask
whether to continue because of review rounds or elapsed time.

## Environment

Main inherits its existing host agent, model and effort; Codex and Devin CLI are
required for children, not Main. Devin children run in Devin's OS sandbox, which on
Linux needs `bwrap` and `socat`; FrontierPlan does not install them. Verify Main's
agent/session/terminal identity as documented in the herdr backend. This skill never
replaces Main or changes global defaults or the user's Devin configuration.
Profiles: `profiles/director/astra.toml`, `profiles/swe2/*.toml` for Researcher and
Worker, and the other role-specific `profiles/*.toml`; child effort values are
lowercase.

Verify SWE-2 routing from the `session_evidence` that `collect` records from Devin's
own session export, not from launch arguments or a child's self-report.

The bundled helpers are cooperative workflow aids, not a sandbox, proof of consent,
or automatic tool interception. Follow [Completion reconciliation](../../core/waiting.md):
reconcile unread results on resume and at most about five minutes apart during
active coordination, retain the live wait handle, and do not leave only a background
process after a final response. Layout: Main left 40%, Astra right 60%; the first
researcher or executor creates the lower 60% of Astra's region, and later
participants split only that area. A returned turn, an intermediate user reply or a
context compaction does not end Astra. Never claim unavailable tools, unobserved
model routing, unrun tests, or an unreturned Astra decision succeeded.
