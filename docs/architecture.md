# Architecture / v0.1.0

FrontierPlan = shared contracts + role profiles + execution backend.

```
User <-> Main (transport) <-> Director (Astra)
                               research / dialogue / design / Plan
                 Director Plan + actual user implementation consent
                                   |
                          Main coordinates
                         /       |        \
                     Worker    Design    Reviewer
                         \       |        /
                          integrated candidate + evidence
                                   |
                          Director acceptance/report
```

The arrows express responsibility, not nested spawn: Main starts and manages EVERY
participant, including Director. Director never creates children. Before execution,
Director personally does all research and design; the old “Astra asks Luna to research”
route is deliberately removed. Model effort identifiers are lowercase xhigh/max.

`skills/` chooses director/astra + herdr/subagent; `core/` defines common behavior;
`profiles/` holds role-specific runtime data; `backends/` defines real transport steps.
`scripts/frontierplan.py` provides a local cooperative ledger, packets, immutable
Director decision archives and Git candidate freshness checks. `scripts/herdr.py`
implements visible CLI sessions, identity-aware continuation, wait and cleanup.
Native tool calls stay in Main, since shell Python cannot invoke Codex agent tools.

The ledger refuses executor preparation before a current Plan + referenced user
consent, duplicate Directors, cross-role native ID reuse, stale request reports,
stale user/Plan/candidate decisions, premature cleanup and changed review candidates.
It does not verify the semantic truth of consent/evidence or sandbox a process.
There is no always-on daemon, external API runner, MCP server, custom agent
installation, dashboard, automatic settings rewrite or model/backend fallback.

Fable is not shipped. Add a verified Director profile plus a supported launcher and
contract tests before registering its SKILLs. Do not assume Codex native subagents
accept arbitrary third-party models. Keep vendor connection details out of core.
Astra/herdr and Astra/subagent use identical role profiles and workflow contracts.

Upstream identity/activity patterns came from axiom_for_herdr, not its old Main-owned
acceptance policy. No runtime dependency on upstream repositories remains.

## Public references used for package/compatibility design

- [Plugin packaging](https://developers.openai.com/plugins/build/plugins): portable
  root manifest and optional Codex compatibility manifest; all referenced data ships.
- [Skills](https://developers.openai.com/codex/skills): skill packaging. Explicit-only
  agents/openai.yaml follows the existing repository's tested configuration.
- [Native subagents](https://developers.openai.com/codex/multi-agent): effective
  permissions may inherit the parent's live runtime overrides.

Public APIs and host versions vary; exact native argument names and effective
permissions must be checked on the target host. Historical upstream tests are not
FrontierPlan validation. See validation.md for the boundary of automated coverage.
