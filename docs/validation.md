# Validation

## Automated (no API keys, models, Codex or herdr installation required)

Run `python3 tools/validate_plugin.py`, `python3 -m unittest discover -s tests -v`,
and `python3 tools/package_release.py`. Tests use temporary Git repositories and a
fake herdr command surface; no external network/model calls occur. CI runs the same
suite on Python 3.11 and 3.13. The package validator checks both entry points,
explicit invocation policy, manifests, lowercase role profiles, local references
and standalone extracted-package integrity.

Coverage includes pre-implementation Director-only dispatch, authorization separation,
current-message reconciliation, same-session follow-up, independent review freshness,
stale acceptance rejection (tracked, staged and untracked changes), premature close,
wrong Main identity, no-focus layout, fixed launch policy, event suppression and
partial delivery failures. Tests do not establish reasoning quality or real routing.

`tests/test_herdr_lifecycle.py` exercises 40/60 role layout with a split-tree fake,
inset pane rectangles, manual ratios, moved/missing anchors and unrelated panes;
same-session fixes/re-review, explicit release decisions and stale/active/identity
guards; archived evidence, late Astra revisions, empty execution area recreation,
Reviewer acceptance gating, wait exclusion and final cleanup without duplicate close.
Uncertain close responses must preserve the intent and stop automatic retry.

## Herdr pane smoke (real transport, synthetic agents)

`tools/smoke_herdr_layout.py --socket <disposable-server-socket>` is opt-in. It
requires an empty, already running disposable Herdr server, creates its own workspace,
and cleans up that workspace. Its owner must stop the disposable server afterward.
Use an isolated `XDG_CONFIG_HOME` and `HERDR_CONFIG_PATH` with a simple `/bin/sh`
terminal config when starting that server; do not point it at an active user server.
It calls the real pane/layout/resize/move/close APIs, but replaces agent identity,
start/prompt, status, reports and acceptance with explicit synthetic fixtures. It
never launches a model or sends a real agent a prompt. The source checkout's tests
are required to run this optional tool; it is not a plugin runtime dependency.

On 2026-09-20, Herdr 0.9.0 passed this smoke on an isolated local server. The saved
[JSON evidence](evidence/issue-4-herdr-layout.json) contains eight actual layout
snapshots: planning (Main 48/Astra 72 columns), execution (Astra 16/executors 24 rows),
manual Main resize to 60 columns, Worker movement to another tab, Worker/Design
release, Reviewer release, recreation of execution below Astra while preserving the
manual width, and final Main-only layout. Focus stayed on Main; six owned child
panes were closed exactly once. The disposable workspace and server were cleaned up.

This establishes real Herdr geometry and pane operations with the helper, not real
Astra/Worker/Reviewer session lifecycle, model routing, effective permissions or
end-to-end autonomous agent behavior. Those remain target-host checks below.

## Target-host smoke tests (not performed by the offline automated suite)

1. Install from the marketplace in a fresh Codex session. Confirm exactly two skills
   appear and do not activate on ordinary requests. Confirm shared resources survive
   installation/ZIP extraction and both role profile reads work.
2. Invoke each skill for a consultation-only task. Confirm ONLY Astra starts, reads
   code/uses required authorized research tools itself, drafts the response and Plan,
   and no Main/Luna research or implementation takes place.
3. Check actual child runtime model/effort, effective permission and Worker tier
   evidence; launch args alone and a child's self-report are insufficient. Native
   permission inheritance needs separate validation from the herdr CLI route.
4. Authorize a small implementation in a disposable repository. Confirm the Plan,
   original Worker, separate Reviewer, same-session fixes/re-review, evidence packet,
   Astra acceptance and Astra-authored final reply are all visible.
5. Add user input after a Plan, alter a candidate after acceptance, interrupt a child,
   move herdr panes, or remove a session. Confirm the appropriate stale/identity guard
   prevents old results from being accepted or unrelated panes from being closed.
6. Confirm one long event-aware wait, early return on report/steering, no repeated
   Main polling, and retained idle participants do not trigger endless waits.

Do not publish a claim that live Astra/herdr/native integration has passed until
these target-host checks have actually been executed and their versions/evidence
recorded. Failure must be reported, not masked by another model or backend.
