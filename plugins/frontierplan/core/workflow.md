# Shared workflow

## 1. Director-led understanding, research and planning

Main does transport/environment setup only. Save the user's exact current message
and relevant earlier public dialogue, known repo/worktree locations and permissions.
Do not rewrite ambiguous intent into a conclusion before Astra receives it.
Initialize one run using the selected backend and start one Director. Forward every
new user message through `message` and the existing Director session, preserving
user words separately from Main hypotheses and external evidence.

Astra performs all research personally: repository inspection, authorized web or
connected-source lookups, existing behavior checks and isolated experiments.
No Main/Luna research delegation before implementation. Product edits, commits,
publishing and implementation are not research. Temporary probes use an isolated
scratch area; tests that generate files or affect services need appropriate scope.
If required tools, permissions or facts are unavailable, Director names the blocker.
Main may resolve transport/authorization under its existing rules, not take over
research or silently change the backend/model. Do not auto-enable network access.

The same Director drafts replies/questions in the user's language and then a Plan
with intent, non-goals, approach, acceptance criteria, verification and replanning
triggers. Main relays conclusions without re-deciding them. Correct actual transport
facts or return contradictory claims to Director; do not relay fabricated results.
Return conclusions and concise rationale, not private chain-of-thought.

Consultation-only requests stop at a Director reply/Plan. A Plan is not user consent
to implement. Record the actual authorizing message reference with `authorize` only
when it really authorizes implementation. Start using `start` after the current Plan.
No unconditional human approval round: existing implementation authorization suffices.

## 2. Main-led execution under the Plan

Main splits executable work, assigns ownership, chooses useful parallelism,
integrates and adjudicates ordinary review findings. Worker handles implementation,
tests, debugging and repetitive monitoring. Design is optional, implementation-phase
UI realization under the Director's already settled product/design direction.
Neither is delegated unresolved pre-implementation design.

Launch independent work before waiting. No arbitrary team-size limit, but respect
host concurrency limits and reserve capacity for the retained Director and Reviewer.
Use disjoint write ownership or explicitly prepared worktrees; serialize overlap.
Preserve existing user edits. Workers do not commit/publish unless specifically
within the user-authorized scope. Main integrates into the run's candidate worktree
before independent review. Reports from separate worktrees are evidence, not the
integrated candidate. Never delete branches/worktrees as a side effect of cleanup.

Main may fix mechanical integration within the Plan, but may not drop requirements,
choose a different architecture, accept material risk or declare final completion.
Return such decisions to the same Director. Director does any necessary new
research itself. New user input pauses new dispatch until Director reconciles it;
stop/cancel instructions are acted on immediately. Do not wait for Astra to stop work.
Normal factual progress updates are Main's responsibility and do not need Astra.

## 3. Independent review, then Director acceptance

Read review.md. Start a fresh Worker/Design for each bounded implementation,
review-fix or verification assignment by default. Reuse a retained session only for
a small immediate follow-up, and record the concrete reason in its assignment.
Do not rotate per tool call, or copy the entire old conversation into a fresh worker.
Pass the current Plan/non-goals, worktree/HEAD, accepted finding IDs, expected behavior,
sufficient tests, prior report and unfinished work. Reuse the same Issue worktree
when appropriate; a fresh session does not require a new branch or dependency install.

After an assignment is complete, Main collects the report, verifies integration and
that no writes or owned processes remain, records that this session has no remaining
role, and promptly releases Worker/Design using the backend protocol. Independent
review need not have finished yet. Release never resolves findings or grants acceptance;
later fixes go to a fresh Worker with the evidence above. A blocked/incomplete
assignment is retained until resolved, not reported as complete to free capacity.

Retain the same independent Reviewer through fixes and Director acceptance of the
exact candidate. In herdr, release the accepted Reviewer before finish when the
safety checks pass. Native Reviewer closure remains part of final wrap-up.
Retention past a Worker/Design assignment's release point is exceptional: Main records
the participant and specific reason, and reassesses it before waiting again. If
safety checks fail, retain the participant and report the reason; never bypass them.
Keep the same Astra throughout dialogue, planning, execution and final reporting.

Release ends a live role, not its evidence: preserve task/report/decision history.
Released reports remain part of candidate/acceptance/finish checks. A released
Reviewer's report only satisfies review for its exact candidate and Plan; subsequent
changes require new review as applicable. Before asking Astra for final acceptance,
collect the current reports and register the candidate/evidence packet.
Check that the run candidate worktree is the actual
integrated worktree, and that review, tests and packet identify that same candidate.
Do not send an acceptance request with an unregistered or incorrectly rooted candidate.
Astra personally checks the actual artifacts, review adjudication, criteria coverage,
verification gaps and residual risk. It can accept or return a revised Plan; Main
cannot convert a failure/blocker into acceptance. Acceptance is tied to the current
Plan, current user input and exact candidate. Any subsequent candidate change needs
re-review as applicable and renewed Director acceptance, even a new commit of the
same working files (HEAD/index are part of the fingerprint).

Director writes the final user response. `finish` returns that text only after valid
acceptance; `finish --discussion` is available only when no execution participants
were created. Call finish only when overall work is actually wrapping up. An interim
reply or user-input wait does not finish the session. Perform backend-specific safe
closure after finish; never close sessions with incomplete assignments, active work,
or unrelated ownership. Herdr
`release` is distinct from post-finish `close`: final cleanup records already released
participants without trying to close their old pane IDs again. Neither operation
closes Main, deletes reports or deletes worktrees/branches.

## Waiting

Follow [Completion reconciliation](waiting.md) and the selected backend instructions.

## Failures and recovery

Do not silently substitute models, efforts or backends. Astra unavailable means
FrontierPlan's decision path is blocked, not that Main becomes Director. Complete
safe already-authorized housekeeping only, and report the real limitation.
Keep blocked reports and partial-start handles visible. Avoid duplicate delivery
after an uncertain timeout. For verified lost sessions, record `retire-lost` with
specific runtime evidence, then rehydrate a replacement from original user messages,
current Plan, findings and reports. Never retire a merely slow/idle session as lost.
Replacements preserve the role/model and review independence. This helper records
loss; it does not independently verify it or kill a process. Unresolved work carried
by a lost task must be explicitly recovered, not silently dropped.

Persist handles, current Plan and decisions in the run across turns/compaction.
The temporary run directory is not a durable archive. Transfer important accepted
conclusions to normal project documentation only within the authorized scope.
No background daemon, dashboard, auto-invocation hook or automatic config mutation.
