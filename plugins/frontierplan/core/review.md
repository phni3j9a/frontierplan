# Independent Sol review

Adapted from phni3j9a/axiom_for_herdr's MIT-licensed review guidance.

Start the review cycle with a fresh Reviewer (`gpt-6-sol` / `xhigh`), independent
of Astra, Workers and Design. Keep that same session for re-review, and keep the
Workers responsible for the candidate through the cycle so they can address
accepted findings. Main owns adjudication, risk tolerance within the Plan, and the
decision to end the cycle. Astra is never the independent Reviewer.

## Review boundary

Supply the Plan's intent, acceptance criteria, relevant decisions and non-goals,
the candidate diff, existing changes outside scope, and verification already
performed. Scale this to the task; do not demand fields that add no value.

Review project content read-only: no project edits, commits, formatters, auto-fixes
or commands likely to mutate the candidate. The assigned report location is the
only permitted output.

## Admissible findings

A material finding needs independent current evidence of at least one of:

- a violation of the Plan's intent or an existing supported contract;
- a concrete failure or regression in the candidate;
- a concrete security, data-integrity, trust-boundary or compatibility defect;
- a verification gap that materially prevents judging one of those obligations.

Hypothetical future use, optional hardening, preference, style and generic advice
are not blocking findings. Candidate-created code, tests, schemas, documentation or
abstractions do not establish that their capability is required. Prior reviewer
suggestions do not create requirements.

**Unnecessary complexity is reviewable** when it lacks independent current
justification and materially increases failure surface, state, concurrency,
dependencies, migrations or maintenance. Prefer removing unjustified machinery when
that is the smallest correction that meets the current contract. Do not redesign
beyond the Plan unless its intent cannot otherwise be met.

## Return

Use stable finding IDs:
```
FINDINGS:
- FP-001 <title>
  Evidence: <file/symbol/behavior and independent current basis>
  Impact: <concrete consequence>
  Remediation: <smallest useful correction>

VERIFICATION_GAPS: <only material gaps>
RESIDUAL_RISK: <concise relevant uncertainty>
DIRECT_USER_INSTRUCTIONS: <instruction and effect, or none>
```
Return `FINDINGS: none` when there are no material findings. A complete review is
not a release verdict.

## Adjudication

Main classifies each finding ACCEPT, REJECT, DEFER or ESCALATE and turns accepted
ones into bounded fixes for the responsible Worker, with the finding IDs, the
expected behavior and the required verification. Do not forward every suggestion
blindly. Concrete evidence stays visible in the final report even when Main defers
a mitigation.

## Finding freeze and continuity

There is no fixed finding count and no round limit. After accepted fixes, Main
sends the same Reviewer its adjudication, the updated candidate and verification
evidence. Keep accepted fixes central. Do not reopen REJECT/DEFER concerns without
materially new independent evidence. New findings remain admissible for:

- material defects directly introduced or revealed by an accepted fix;
- newly evidenced concrete correctness, security, data-integrity, trust-boundary
  or compatibility defects, including ones missed initially;
- independently evidenced violations of requirements already inside the boundary.

Do not restart preference or optional-hardening review. If the Plan changes
materially, Main decides whether the same session resets its boundary or a fresh
cycle is useful.

If the same accepted finding keeps returning after fixes, or fixes keep revealing
defects of one kind, that points at the approach rather than the code: Main
consults Astra with the finding history before sending another fix. This is not a
user checkpoint and not a round quota.

If the Reviewer session is lost, a fresh Sol replacement gets the earlier findings,
adjudication, fixes, current candidate and evidence. Never substitute Luna.

Main ends review when the candidate is sufficiently resolved and no accepted
material finding remains unaddressed. Then Main runs Astra's final check; findings
from it are adjudicated the same way and re-reviewed by the same Reviewer. After
the cycle, close the Reviewer and the Workers whose work is resolved.
