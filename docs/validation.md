# Validation / v0.5.2

## Automated package checks

Run from a Git checkout with Python 3.11+:

```bash
python3 tools/validate_plugin.py
python3 -m unittest discover -s tests -v
python3 tools/package_release.py
```

Stage new files before packaging: the inventory comes from Git's index, while
file contents come from the working tree. Both archives are extracted and their
plugin is validated. No source-checkout path or Python runtime is needed to read
the extracted plugin. Source packaging itself requires a Git checkout.

Tests cover manifest agreement, explicit invocation on all three host formats,
packaged resources and local links, rejection of runtime code/profiles, and
archive contents. In particular, untracked/ignored settings, symlinks and existing
ZIPs are not added by a recursive scan. No test launches an agent or uses API keys.
CI runs these checks on Python 3.11 and 3.13.

Tests of the deleted ledger, receipt protocol and fake Herdr state machine were
removed with that implementation. Package checks do not establish agent reasoning
quality, runtime routing, permissions or end-to-end coordination.

When Claude Code is available, its own schema validators add an independent check:

```bash
claude plugin validate --strict .
claude plugin validate --strict plugins/frontierplan
```

The generic skill-creator quick validator does not recognize the existing
Claude/Devin frontmatter keys (`disable-model-invocation`, `triggers`). Its raw
check therefore rejects all three entries for those keys. Their values are
checked by the package tests; standard metadata and body also passed quick
validation on temporary copies with only those two extensions removed. The
distributed skills keep both extensions, preserving explicit invocation.

## Current validation boundary

The v0.5.2 review-convergence changes are instructions-only. Package validation
and manual consistency review do not establish live model adherence, shorter
reviews or fewer missed defects. No live-model before/after comparison has been
run for this revision; the scenarios below are target-host checks, not results.

The v0.5.1 task-review/final-check change was implemented and reviewed by Main
alone at the user's request, without launching child models. That historical
validation also covered package integrity and instruction consistency, not live
model adherence.

During v0.5.0 validation, installed Herdr 0.9.1's
`--skill` and command help were checked, along with the official v0.9.3
[SKILL](https://github.com/herdrdev/herdr/blob/v0.9.3/skills/herdr/SKILL.md).
Codex CLI 0.159.3 and Devin CLI 3000.11.3 help confirm the native launch options.
These checks establish documented syntax, not successful live model starts.

On 2026-10-01, a [real pane-only check](evidence/issue-21-cli-layout.json) ran the
three literal split commands from the new Herdr guide on Herdr 0.9.1 in an
isolated named server with a temporary config and plain shell panes. It verified
40/60 and 40/60 placement, additional horizontal splits, unchanged Main focus,
manual resize preservation, execution-area recreation and collapse to Main alone.
The test workspace, server and temporary directory were removed afterward.

This establishes shell-pane splits and cleanup, not Astra/Worker/Reviewer
behavior. No synthetic agents were used, and no child model was launched. There
is no claimed before/after model-performance benchmark for v0.5.0.

## Target-host behavioral checks

Use a disposable project and the chosen host's installed plugin when these
checks are run. Record versions, task input, actual outputs and limits.

| Scenario | Observe |
|---|---|
| Consultation only | Astra answers; Main relays; no executor is started |
| Research request | Main starts requested Researchers and returns their results |
| Worker reports completion with a missing task requirement | Reviewer compares Main's assignment with the actual diff and evidence; same Worker and Reviewer continue through accepted fixes |
| Several independent defects in the assigned scope | First review covers the scope and affected behavior and groups its findings; it does not stop at a finding-count cutoff or expand into unrelated repository improvements |
| Real requirement violation, including a P2, mixed with speculative hardening or design preferences | Main uses concrete impact and evidence, not severity alone; optional improvements do not become requirements, while unnecessary complexity with present costs remains reviewable |
| Reproducible defect and a defect that is hard to automate | Where practical, a regression test fails before repair and passes afterward; Reviewer checks its relevance and also considers concrete static or manual evidence rather than requiring an automated reproduction for every issue |
| Repair introduces a regression in a caller outside the diff | Same Reviewer verifies accepted fixes and affected behavior; the new regression is reported and verified after repair, not ignored as out of scope |
| Rejected/deferred concern returns with unchanged evidence | Main's decisions and reasons carry into re-review; the concern is not reopened without new evidence. Newly established defects, including initial-review misses, still receive evidence-based adjudication |
| Same concern repeats without useful new information | Main diagnoses requirement interpretation, failure conditions or conflicting fixes before assigning another patch; design consultation does not restart Astra's final check |
| Requirements and necessary checks pass, but optional suggestions remain | Main closes task review without a zero-suggestion demand or round/time quota; integration and Astra's one overall check still follow |
| Required verification cannot be completed | Main reports and adjudicates the limitation instead of treating an unperformed check as passed or claiming completion solely because findings stopped |
| UI implementation by Design | Independent Reviewer verifies Design's assigned task with the same boundaries as Worker tasks |
| Concrete regression or contradictory assignment | Reviewer reports evidence to Main without adding requirements or independently redesigning the task |
| Tasks pass separately but fail when combined | Main assigns integration checks to Worker; Reviewer verifies that task and its evidence |
| Integrated result misses the user's goal or a Plan requirement | Astra identifies overall gaps once; Main adjudicates; accepted fixes return to the implementer and same Reviewer without another Astra final check |
| Interruption and resume | Retained names/IDs, review decisions and reasons, and latest results are read; no duplicate prompt on timeout or fresh review caused by losing adjudication context |
| Herdr layout | Main/Astra 40/60, lower execution region, additional horizontal splits, no focus theft |
| SWE-2 difference | Only Researcher/Worker use Devin; recorded model and permissions are distinguished |
| Native route | Actual native tools and explicit routing work; no shell emulation |

Repeat applicable scenarios on the standard Herdr, SWE-2 and native routes.
Compare output quality, coordination call count and stalls with the prior version
before claiming the lighter instructions perform better. Verify effective model,
effort, tier and permissions from host/runtime evidence, not self-report.

For a convergence comparison, keep task input, starting project revision, backend,
models/effort/tier, permissions and available checks comparable, changing only the
plugin revision. Use repeated comparable runs rather than a single favorable
example. From ordinary transcripts or short notes, compare repair/re-review cycles,
repeated adjudicated findings, review elapsed time and missed defects found by the
same independent checks of the final result. Distinguish late discoveries of
pre-existing defects from repair-induced regressions. Fewer rounds or faster
completion alone is not an improvement if requirements or defects are missed.
No new ledger, reporting schema or runtime instrumentation is required.

## Historical evidence

The old helper-specific smoke scripts were removed with the runtime. Reproduce
them from their original Git revision, not by installing them into v0.5.x.

- [2026-09-20 layout evidence](evidence/issue-4-herdr-layout.json):
  v0.1 with Herdr 0.9.0; real pane operations, synthetic agents.
- [2026-09-24 layout evidence](evidence/issue-11-herdr-layout.json):
  v0.2 with Herdr 0.9.1; real splits/moves/cleanup, synthetic agent lifecycle.
- [2026-09-25 SWE-2 evidence](evidence/issue-15-swe2-devin-smoke.json):
  v0.3, Herdr 0.9.1 and Devin 3000.11.3; real Researcher/Worker, synthetic
  Astra/Reviewer. Same-session correction and exported SWE-2 model names passed.

Those results do not establish the full current workflow. The earlier Devin
sandbox probes stalled on edit/write approval; that was the reason for the
variant's existing `dangerous` choice. The new plugin does not recreate those
permission experiments or claim an OS boundary for that mode.
