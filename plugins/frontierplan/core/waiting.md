# Completion reconciliation

Main owns completion delivery through the next action, not just starting a waiter.
Apply this contract to both backends using their documented native operations.

- Reconcile every current request on entry, after user steering/compaction/resume,
  on a completion notification, and at most about 300 seconds apart while Main is
  actively coordinating pending work. Native notifications may return sooner.
- Compare current result/request identity with its collection receipt. An unread
  complete/blocked result remains actionable even if a previous wait announced it.
  Do not use file creation, notification history or an old request as the only signal.
- Distinguish report publication, live idle state, collection, and the next action.
  A complete report is a returned assignment, not review approval or final acceptance.
  A published report with a busy session is visible but cannot yet be collected,
  re-prompted or closed. Inspect persistent discrepancies without removing idle guards.
- Collect every ready report, read it and resolve its next action: integration,
  bounded new assignment, review, Astra's decision and its relay, or explicit
  blocker retention.
  A collected blocker remains unresolved until its prerequisite is actually resolved.
- Keep one supported wait per run and retain its execution handle, including outer
  wrappers. Use the host's available result-wait mechanism with a maximum of about
  300 seconds, or its lower supported limit/higher-priority cap. Resume the same
  live handle; do not launch another waiter because the outer tool yielded.
- Before another wait, reconcile outstanding results and close participants whose
  lifetime Main has ended. Do not spin on an unchanged blocker or
  report_waiting_idle; use the bounded wait and its next heartbeat.
- While autonomous execution is still required and supported, keep the active
  result-wait/continuation path. A progress update must not end that path with a
  final response that leaves only a background shell running. Main taking a new
  turn is not implied by a timer firing, a file changing or a shell exiting.
- If the host cannot continue waiting or resume Main without user input, disclose
  that concrete limitation and retain handles/results for the next reconciliation.
  Do not promise unattended monitoring. User stop/cancel instructions still take
  priority; this contract does not authorize a daemon or synthetic user prompts.

During planning, a returned Astra decision or researcher report is handled the same
way: collect it and perform the helper's `next` step without adding judgment.

Batch pending participants in one check. The five-minute interval is a reconciliation
ceiling during active coordination, not a requirement to delay native notifications
or busy-poll every agent. Routine unchanged status need not produce a long update.
Record host limits and actual completion evidence; simulated tests do not prove that
a suspended Main will wake up on the real host.
