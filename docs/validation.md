# Validation

## Automated (no API keys, models, Codex or herdr installation required)

Run `python3 tools/validate_plugin.py`, `python3 -m unittest discover -s tests -v`,
and `python3 tools/package_release.py`. Tests use temporary Git repositories and a
fake herdr command surface; no external network/model calls occur. CI runs the same
suite on Python 3.11 and 3.13. The package validator checks both entry points,
explicit invocation policy, manifests, lowercase role profiles, local references
and standalone extracted-package integrity. It also requires the Claude Code
manifest to match the portable one and both SKILLs to carry
`disable-model-invocation: true`; `claude plugin validate --strict .` and
`claude plugin validate --strict plugins/frontierplan` check the Claude Code
marketplace and plugin schemas when the Claude Code CLI is available (not in CI).

Coverage includes Astra-only dispatch before execution, the research relay (verbatim
requests, no duplicate researchers after a partial failure, unedited reports back to
Astra), verbatim user relay and forwarding, stale planning decisions after new user
input, Astra-recorded implementation authorization, decision kinds per turn,
consultation and Plan revision, the once-per-Plan final check and its shape, finish
preconditions, same-session Worker fixes and Reviewer re-review, close guards, lost
Astra recovery, wrong Main identity, no-focus layout, fixed launch policy,
unread-report reconciliation and partial delivery failures. Tests do not establish
reasoning quality, Plan proportionality or real routing.

Role-routing checks cover the native helper's profiles and simulated herdr launch
arguments: Director uses `gpt-6-astra` / `xhigh`, Researcher and Worker use
`gpt-6-luna` / `max` with fast requested, Design uses `gpt-6-sol` / `max`, and
Reviewer uses `gpt-6-sol` / `xhigh`. Main still inherits its existing session.
Runtime routing and effective Luna tier require target-host evidence; the offline
suite does not launch these models.

`tests/test_herdr_lifecycle.py` exercises the 40/60 role layout with a split-tree
fake, inset pane rectangles, manual ratios, moved/missing anchors and unrelated panes;
researchers sharing and then vacating the execution region; same-session fixes and
re-review; close guards for activity, identity, occupant, reused pane IDs, blockers
and Astra before finish; execution-area recreation and final cleanup. Uncertain close
responses must preserve the intent and stop automatic retry.

`tests/test_completion.py` covers unread complete/blocked replay after lost wait output,
read-only reconciliation while a waiter is alive, same-file publication, idle gating,
old requests and the five-minute heartbeat. The clock and herdr are simulated; no
model is launched by these tests.

## Herdr pane smoke (real transport, synthetic agents)

`tools/smoke_herdr_layout.py --socket <disposable-server-socket>` is opt-in. It
requires an empty, already running disposable Herdr server, creates its own workspace,
and cleans up that workspace. Its owner must stop the disposable server afterward.
Use an isolated `XDG_CONFIG_HOME` and `HERDR_CONFIG_PATH` with a simple `/bin/sh`
terminal config when starting that server; do not point it at an active user server.
It calls the real pane/layout/resize/move/close APIs, but replaces agent identity,
start/prompt, status, reports and Astra decisions with explicit synthetic fixtures.
It never launches a model or sends a real agent a prompt. The source checkout's tests
are required to run this optional tool; it is not a plugin runtime dependency. Keep
the server's socket path short (Unix sockets allow about 107 bytes).

On 2026-09-24, Herdr 0.9.1 passed the v0.2 smoke on an isolated local server. The
saved [JSON evidence](evidence/issue-11-herdr-layout.json) has nine layout snapshots:
planning, two researchers below Astra, research returned (researchers closed),
execution, manual Main resize, Worker moved to another tab, review cycle closed after
the final check, execution recreated below Astra with the manual width preserved, and
the final Main-only layout. Focus stayed on Main; eight owned child panes were closed
exactly once. The disposable workspace and server were cleaned up. The earlier
2026-09-20 Herdr 0.9.0 run of the v0.1 flow is kept as
[issue-4 evidence](evidence/issue-4-herdr-layout.json).

This establishes real Herdr geometry and pane operations with the helper, not real
Astra/Worker/Reviewer session lifecycle, model routing, effective permissions or
end-to-end autonomous agent behavior. Those remain target-host checks below.

## Target-host smoke tests (not performed by the offline automated suite)

1. Install from the marketplace in a fresh Codex (or Claude Code) session. Confirm exactly two skills
   appear and do not activate on ordinary requests. Confirm shared resources survive
   installation/ZIP extraction and all role profile reads work.
2. Invoke each skill for a consultation-only task. Confirm Astra alone answers, Main
   relays her text verbatim, and no Worker/Design/Reviewer starts.
3. Ask for a task where Astra requests research. Confirm Main starts the researchers
   with her exact requests, returns the unedited report paths, and closes them; on
   the subagent backend confirm nothing nests below Astra.
4. Check actual child runtime model/effort, effective permission and Luna tier
   evidence; launch args alone and a child's self-report are insufficient. Native
   permission inheritance needs separate validation from the herdr CLI route.
5. Authorize a small implementation in a disposable repository. Confirm the Plan
   (with its simpler alternative and two-stage verification), Main's assignments,
   the same Worker receiving accepted fixes, the same Reviewer re-reviewing, one
   Astra final check, and Main's final report are all visible, and that the user is
   not asked to continue because of review rounds.
6. Add user input during planning and during execution, interrupt a child, move
   herdr panes, or remove a session. Confirm stale planning decisions are rejected,
   execution input stays with Main, and identity guards prevent closing unrelated panes.
7. Without sending `continue`, confirm child publication → Main result delivery →
   collection → next action actually runs on each target host. Record timestamps and
   the host's supported wait limit. Exercise a report already present before waiting,
   working→complete in the same file, a lost/interrupted outer wait then resume, and
   an old request that must not satisfy a new assignment.

Do not publish a claim that live Astra/herdr/native integration has passed until
these target-host checks have actually been executed and their versions/evidence
recorded. Failure must be reported, not masked by another model or backend.
