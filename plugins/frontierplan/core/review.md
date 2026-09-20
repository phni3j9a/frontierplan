# Independent review and Director acceptance

Start a fresh Sol / `xhigh` Reviewer after implementation/integration, independent
from Director, Workers and Design. Use the same Reviewer for accepted fixes and
re-review, and original Workers for fixes. Do not use Luna or the planning Director
as the independent Reviewer. Follow the participant lifecycle in
[workflow.md](workflow.md): Workers stay through their relevant review/rework;
herdr may release them afterward with Main's explicit decision. The Reviewer stays
through Director acceptance of the exact candidate.

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
  Evidence: ...
  Impact: ...
  Remediation: ...
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

Send bounded accepted fixes to the original responsible Workers, then the updated
candidate and verification to the same Reviewer. Freeze finding IDs; do not revive
rejected preference/hardening suggestions without new independent evidence. Newly
introduced/revealed material defects remain reviewable. Changed scope/design/criteria
returns to Director. Main may manage review mechanics, but not redefine completion.
No arbitrary round quota; report non-convergence to Director rather than loop blindly.
