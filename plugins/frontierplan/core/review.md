# Independent review and Director acceptance

Start a fresh Sol / `xhigh` Reviewer after implementation/integration, independent
from Director, Workers and Design. Use the same Reviewer for accepted fixes and
re-review; assign fixes to a fresh Worker by default under [workflow.md](workflow.md).
Do not use Luna or the planning Director as the independent Reviewer. Worker/Design
sessions may be released after their completed assignment, before independent review.
The Reviewer stays through Director acceptance of the exact candidate.

Review the accepted intent, non-goals, current Plan/criteria, integrated candidate,
existing out-of-scope changes and actual verification. Inspect read-only; no edits,
formatters, auto-fixes, commits, publishing or tests that mutate product files.

Material findings need current evidence of a requirement/contract violation,
concrete regression, correctness/security/data-integrity/compatibility defect, or a
verification gap preventing judgment of those obligations. Preference, hypothetical
future use and optional hardening do not create blocking requirements. Existing
candidate code and prior reviewer suggestions do not establish user requirements.

Return stable IDs, evidence, concrete impact and the smallest useful remedy:
```
FINDINGS:
- FP-001 ...
  Requirement: <existing accepted criterion/contract>
  Evidence: <reproduction and current candidate>
  Impact: ...
  Remediation: <smallest useful fix>
  Closure: <expected behavior and minimum sufficient verification>
VERIFICATION_GAPS: ...
RESIDUAL_RISK: ...
DIRECT_USER_INSTRUCTIONS: none / original instruction and effect
```
Return FINDINGS: none when no material findings exist. A completed review is not
release acceptance. The helper fingerprints the candidate at review assignment and
report publication; changes during review require a blocked report and a new turn.

Main applies the already-agreed criteria: ACCEPT supported fixes, REJECT unsupported
claims, DEFER only within previously agreed risk policy, ESCALATE consequential
uncertainty. Main cannot drop requirements, accept new material risks or choose a
new architecture by calling it review adjudication. Director decides those questions.
Include important rejected/deferred evidence in Director's final packet.

For each accepted fix, Main supplies the requirement, reproduction, expected behavior
and minimum sufficient verification to the assigned Worker. Preserve finding IDs and
explicit ACCEPT/REJECT/DEFER decisions. Start the next Reviewer turn with the changed
candidate, actual verification and that same closure checklist. Re-review the fixes
and affected behavior; do not restart an open-ended search for unrelated improvements.
Newly introduced/revealed material defects remain reviewable, with new evidence.
Do not revive rejected preferences/hardening without independent new evidence.

Aim for one initial review and one fix-verification pass in ordinary work. If the
same accepted finding remains unresolved after two fix-verification passes, or
acceptance conditions keep expanding, Main stops automatic rework dispatch and sends
Director the finding history, attempted fixes, remaining evidence and proposed bounded
next step. Director diagnoses misunderstanding, design/scope complexity and sufficient
verification before further work. This is a convergence checkpoint, never automatic
acceptance after a round quota. Existing authorization permits continued agreed work;
do not add a new user approval round merely because this checkpoint was reached.

Director should reassess whether the verification machinery is proportionate to the
user's goal. Plan wording or a prior suggestion alone does not prove every additional
layer is necessary. Keep real correctness, privacy and data-integrity obligations;
choose the smallest verification that establishes them. Main must not independently
weaken requirements, accept new material risk or redefine completion.
