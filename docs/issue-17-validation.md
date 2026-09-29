# Issue #17: local Codex validation handoff

Status: **real Herdr and native peer-continuation validation pending**. The Python
suite simulates both backends; it cannot establish that live agents receive and
resume peer turns. The user will perform Herdr validation with local Codex. Do not
label the smoke complete or enable a hidden Main relay to make it pass.

## Automated checks

From this PR checkout (Python 3.11+):
```
python tools/validate_plugin.py
python -m unittest discover -s tests -v
python tools/package_release.py
```
`tests/test_pairs.py` covers direct same-session handoff, current-candidate PASS,
uncommitted/untracked changes, ownership and stale identity, counter-evidence,
stagnation/resume, replacement, completion/closure and transport failure races.
These are simulated tests, including the fixture's native capability assertions.

## Real Herdr smoke — local Codex

Use a disposable Git repository/worktree and the PR's installed plugin copy (or
explicitly identify a contributor smoke using this checkout's helper paths).
Do not silently substitute a checkout for an already loaded skill. Record plugin
commit, Python/Herdr/Codex versions, selected standard/SWE2 variant and Main's
actual agent/session/terminal. Follow existing setup permissions; do not broaden
permissions or modify global config to make the smoke pass.

Run a small user-authorized task through normal Astra planning and `start`, for
example implementing a tiny normalization function with an explicit edge-case
contract and focused tests. Main should assign exactly one Worker–Reviewer pair.
Use a test-only seeded candidate with one known contract violation so at least one
real finding/fix turn is exercised; clearly label the injected failure as fixture
setup, not normal behavior. The Reviewer still independently checks the contract.
Never fabricate Astra decisions or PASS reports as a substitute for agent execution.

After planning, save the actual `$run`, `$worker` and `$reviewer` returned by:
```
hd=<resolved-plugin-root>/scripts/herdr.py
pp=<resolved-plugin-root>/scripts/pairs.py
fp=<resolved-plugin-root>/scripts/frontierplan.py
python3 "$hd" pair-spawn --run "$run" --file "$short_contract" --cwd "$worktree"
```
Observe and preserve evidence of this chain:

1. Reviewer starts in bootstrap and becomes idle; Worker receives the task.
2. Worker publishes a candidate; **the Worker-originating helper** prompts the
   same registered Reviewer, which resumes and returns a concrete finding.
3. That Reviewer prompts the same Worker; Worker fixes the finding and runs the
   focused check. It prompts the same Reviewer again, which verifies and returns
   PASS for the latest candidate. Main sends none of these ordinary prompts.
4. Main checks status, collects both idle participants, then closes both panes:
   ```
   python3 "$pp" status --task "$worker"
   python3 "$hd" check --run "$run"
   python3 "$pp" collect --task "$worker"
   python3 "$hd" pair-close --task "$worker"
   ```
   Preserve the returned cwd/candidate, pair record, per-turn reports, actual
   session identities, prompt logs, collection receipts and terminal-close results.
5. Integrate the exact reviewed artifact and verify required integration checks.
   Astra checks this Plan once. A deliberately tested follow-up repair uses a new
   pair and ends at Reviewer PASS/Main finish, without another Astra final check.

Record whether Herdr is actually willing to accept `agent prompt` from each child,
not just Main. Confirm both children end their turn after handoff; a worker blocked
in a permanent peer wait prevents its own continuation. A busy-peer retry must not
create duplicate prompts. An uncertain prompt response must be investigated, not
blindly retried. Inspect wrong/reused terminal handling only in a disposable run.

For SWE2, repeat the essential round trip with a real Devin Worker and Codex
Reviewer; record Devin's actual exported model and existing bypass-mode boundary.
Standard-Codex evidence does not establish SWE2 interoperability.

## Native backend evidence

Test separately on a host exposing actual child-to-peer continuation in both
directions with persistent identities. The helper cannot implement a missing host
capability. Supply observed child `thread_id` separately from the native `agent_id`;
never assume they are equal. Save actual tool names/arguments/results, resumed
session IDs, effective model/permissions and the finding/fix/PASS chain.

If the host only permits parent-to-child continuation or notifications, mark pair
execution **unsupported on that host**. Do not provide a fake capability file or
have Main relay packets while claiming direct pairing. No native capability was
validated by the automated suite or by the Herdr-only smoke.

## Evidence summary to add to the PR

Record each backend/variant as pass, failed or not run, with the tested commit,
commands, actual result paths, identity continuity, Main's ordinary relay count
(expected zero), candidate/PASS binding and pane cleanup. State model/routing gaps
and manual interventions. One smoke demonstrates feasibility, not a proven
convergence, latency or cost improvement across projects.
