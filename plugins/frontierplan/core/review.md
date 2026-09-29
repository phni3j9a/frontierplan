# Bounded Sol task verification

Adapted from phni3j9a/axiom_for_herdr's MIT-licensed review guidance.

> Review exists to close the assigned task, not to improve the system.

Each task has one Worker (or Design) and one fresh independent Sol Reviewer
(`gpt-6-sol` / `xhigh`). Keep both sessions through the task's fix/re-review cycle.
The Reviewer verifies the short Task Contract, not the whole project. Astra is
never this Reviewer. Main assigns and integrates; it neither relays ordinary
findings nor ACCEPT/REJECT/DEFERs them.

## Boundary and evidence

Main supplies the objective, owned scope, observable completion conditions,
relevant supported contracts and required focused checks. Link the Plan and
non-goals where useful. A small task needs a small contract, not a checklist of
hypothetical edge cases. Use the current candidate and independent requirements,
not the Worker's confidence or its self-authored tests alone.

Review project content read-only: no project edits, commits, formatters or
auto-fixes. Reports/protocol data under the assigned run directory are permitted.

A material finding needs concrete current evidence of a requirement violation,
relevant supported-contract break, bug/regression, security/data-integrity/
compatibility defect, or missing verification that prevents judging the task.
Hypothetical use, optional hardening, style, preference and future extensibility
are not blockers. Candidate-created code/tests/schemas do not create requirements.
Unnecessary complexity is reviewable only when independently unjustified machinery
materially increases failure surface or maintenance; request removal only when it
is the smallest correction. Do not use this as permission for broad redesign.

## Direct completion loop

Use [pairs.md](pairs.md). Worker sends a candidate with focused evidence directly
to its registered Reviewer. Reviewer sends concrete findings directly back; Worker
fixes them or returns concrete counter-evidence. Reviewer decides task-local PASS
when the required checks support completion and no material defect remains. PASS
is the normal outcome of sufficient verification, **not** permission to skip it.
Only the assigned Reviewer can publish PASS for the current candidate/contract.
Main receives that reviewed result or a blocker/escalation, not every round.

Keep reports short and use stable finding IDs:
```
FP-001 <concrete defect>
Evidence: <existing requirement; actual failing behavior; path/command>
Impact: <material consequence>
Correction: <smallest correction or required focused check>
```
For PASS, record resolved finding IDs, required verification and relevant gaps.
Task PASS is not permission to publish or overall project acceptance.

## Convergence and escalation

Re-review primarily checks the previous findings and regressions caused by the
fixes. Do not restart broad review, invent requirements or reopen resolved concerns
without materially new evidence. Newly evidenced serious existing-contract or
correctness/security/data-integrity/compatibility defects remain admissible,
including defects missed initially. Do not search for optional improvements.

There is no fixed finding or round quota. If another iteration cannot make useful
progress for the same underlying reason, return ESCALATE: this covers both unclear
requirements and a clear task the current Worker cannot implement because of its
approach, capability or environment. Give the evidence and intervention needed.
Main resolves ownership/scope/environment or replaces a session; it does not
become the ordinary review judge. Consult Astra only for Plan-level decisions.

A replacement keeps the current contract, candidate, earlier finding IDs and
verification. Do not change role/model or use loss as a fresh broad-review excuse.

After PASS, Main collects the exact reviewed result and closes both idle sessions.
Do not keep completed pairs until Astra's final check. Later integration changes or
concrete findings from Astra's one-time check get a bounded follow-up pair.
Astra does not re-accept the fix; Main owns completion.
