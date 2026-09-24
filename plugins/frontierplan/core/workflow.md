# Shared workflow

FrontierPlan keeps axiom_for_herdr's working structure: Main coordinates, Luna
executes, an independent Sol reviews, and Main decides when the work is done. The
one change is planning: **Astra owns everything up to the Plan**, because that is
where judgment matters most, and Main only relays it.

```
Planning   Astra judges ─┬─ research ──> Luna researchers (relayed by Main)
                         ├─ questions ─> user (relayed verbatim by Main)
                         └─ Plan + authorization
Execution  Main judges: split, assign, integrate, adjudicate review (axiom_for_herdr)
                         └─ consult Astra when stuck or the Plan no longer fits
Final      Astra checks the result once; Main adjudicates, finishes and reports
```

## 1. Planning: Astra decides, Main relays

Initialize one run with the user's exact words and start Astra. Main may add a
short file of transport facts (repository/worktree paths, available environments,
known permissions). It must not add hypotheses, a researched approach or a Plan.

Astra follows [astra.md](astra.md). Each Astra turn returns one decision
([handoff.md](handoff.md)). Main runs the helper's `decision` command and performs
the returned `next` step mechanically:

| `next` | Main does |
|---|---|
| `relay` | run the backend's research relay: start Astra's researchers with her exact requests, then return their unedited reports to her |
| `relay_to_user` | show `relay_to_user` to the user exactly as written, then wait for the user |
| `start` / `relay_to_user_then_start` | (show the text, then) run `start` and begin execution |
| `main_decides` | execution-phase advice or final-check results for Main's own judgment |

A new user message during planning is stored with `message` and given to Astra
unchanged with `forward`. Main never summarizes, reinterprets, answers for Astra
or researches on its own before execution. It may resolve transport problems
(permissions, unavailable tools, a stuck pane) under its existing rules.

Implementation authorization is Astra's call: her Plan or `authorize` decision
names the user message that authorizes implementation. When the Plan needs the
user's agreement first, she presents it and waits. Any new user message before
`start` voids a recorded authorization, because it may withdraw consent; Astra
records it again if it still holds. A consultation-only request ends
with Astra's reply; `finish --discussion` closes it.

## 2. Execution: Main coordinates (axiom_for_herdr)

After `start`, Main owns intent within the Plan, assignment, integration and review
adjudication. Main is assumed capable of judging review findings.

- Ordinary bounded implementation, tests, debugging and long-running monitoring go
  to Luna Workers. Luna compute is almost free; Main context is expensive. Delegate
  when it protects Main context or enables useful parallel work, without splitting
  simple tasks artificially. There is no fixed worker count.
- Unsettled visual or interaction work goes to Sol Design. Settled designs can be
  implemented by Luna.
- Launch independent work before waiting. Use disjoint write ownership or prepared
  worktrees; serialize overlap; preserve existing user changes.
- **Keep the responsible Worker through its review cycle.** Send accepted fixes to
  that same Worker with the finding IDs, Main's decision and required verification.
  A fresh Worker is recovery for a lost session, not the routine next step.
- Delegate repeated CI/build/test monitoring to the responsible Luna Worker. Main
  does not poll it; the Worker reports completion, failure or a needed decision.
- Main may make small adjustments within the Plan. When the Plan no longer fits,
  or the same accepted finding keeps coming back after fixes, Main consults Astra
  (`consult`). Astra returns advice or a revised Plan; Main decides adoption.
- A new user message during execution goes to Main. Main handles it, and consults
  Astra when it changes the Plan's scope or design.

## 3. Independent review

Follow [review.md](review.md). One fresh Sol Reviewer is kept for the whole review
cycle. There is no finding-count or round limit: convergence comes from reviewer
continuity, stable finding IDs, evidence-bounded findings and Main's adjudication.
Main ends review when no accepted material finding remains unaddressed.

## 4. Final check: Astra looks once

After review converges and executors are idle, Main runs `final-check` with an
evidence file: Plan/criteria mapping, the diff range, real test output, review
findings with ACCEPT/REJECT/DEFER decisions, and known gaps. Astra returns an
acceptance-criteria table, findings and Plan divergence **once per Plan**.

Main treats Astra's findings exactly like Reviewer findings: it adjudicates them,
sends accepted fixes to the responsible Worker and has the same Reviewer re-review.
Fixes do not go back to Astra. Astra has no veto. If Astra reports a divergence
whose correction would change scope or cost materially, Main gives the user options
with a recommendation.

## 5. When the user hears from FrontierPlan

Only these three:

1. Astra's planning messages (questions, the Plan), relayed verbatim.
2. The completion report.
3. A branch whose answer changes scope or cost: give concrete options and a
   recommended default. Never ask "should I continue?".

Review rounds, elapsed time or a routine finding are not reasons to return to the user.

## 6. Finish and cleanup

`finish --file <report>` requires Astra's final check for the current Plan and
collected reports from every live Worker/Design/Reviewer. Main writes the final
report: results, Astra's acceptance-criteria table, key decisions, real verification,
and remaining items (rejected/deferred findings, unverified points). Update
repository documentation within the authorized scope. Then close remaining
participants and Astra through the backend. Closing never deletes reports,
worktrees or branches.

Close participants when Main ends their lifetime: researchers after their reports
return to Astra, Workers/Design/Reviewer after their review cycle, Astra after
finish. A participant with unresolved or active work stays open.

## Waiting

Follow [Completion reconciliation](waiting.md) and the selected backend instructions.

## Failures and recovery

Do not silently substitute models, efforts or backends. If Astra is unavailable
during planning, planning is blocked: report it rather than planning in Main.
During execution Main continues its own work and reports the missing consultation.
For a verified lost session, record `retire-lost` with runtime evidence and start a
replacement with the prior reports; the Director replacement also gets the Plan and
user messages. Never retire a merely slow or idle session.

Keep handles, the Plan and decisions in the run across turns and compaction. The
temporary run directory is not a durable archive; keep accepted conclusions in
project documentation. No background daemon, dashboard, auto-invocation hook or
automatic config mutation.
