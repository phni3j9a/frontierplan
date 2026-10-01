# Herdr operations

Read `herdr --skill` from the installed binary and follow its current command
syntax and lifecycle guidance. It is the authority for transport; this document
adds FrontierPlan's layout and role-specific launch choices. Run inside Herdr
(`HERDR_ENV=1`) with the required agent CLIs available. If that environment is
missing, explain what is needed instead of switching backends.

Use the current pane as Main and returned pane IDs or unique agent names for
subsequent operations. Keep the current project directory unless the assignment
requires another workspace. Resolve referenced resources relative to this loaded
Plugin, so a different checkout does not supply the instructions.

## Keep the familiar layout

Use this arrangement within Main's original region; leave other user panes alone:

```text
+--------------------+------------------------------+
|                    | Astra                        |
|                    | upper 40% of the right side  |
| Main               +--------------+---------------+
| left 40%           | Researcher / Worker /        |
|                    | Design / Reviewer            |
|                    | lower 60% of the right side  |
+--------------------+------------------------------+
                     <------- right 60% ------------>
```

1. Split Main to the right with ratio `0.4`; Main retains 40%, Astra gets 60%.
2. When the first Researcher or executor is needed, split Astra down with ratio
   `0.4`; Astra keeps the upper 40% of the right side, execution gets the lower 60%.
3. Put subsequent Researcher/Worker/Design/Reviewer panes in that lower region:
   split its widest current pane right with ratio `0.5`. Do not split Main or
   Astra again while execution panes remain. For equal widths, prefer the leftmost.
4. When all execution panes close, Herdr naturally restores Astra's right region.
   Recreate the lower region from Astra when later work needs it.

These are layout instructions, not a geometry gate. Preserve manual resizing and
use the participants' current locations after moves. Inspect the layout to choose
the next appropriate split; do not stop work merely because ratios have changed
or globally rebalance the user's panes. Use `--no-focus` to leave focus with Main.

For a fresh layout, set `project` to the assignment's working directory and run
these steps as participants are needed, reading each returned ID before the next:

```bash
herdr pane split --current --direction right --ratio 0.4 --cwd "$project" --no-focus
# Set astra_pane from .result.pane.pane_id in that response.
herdr pane split "$astra_pane" --direction down --ratio 0.4 --cwd "$project" --no-focus
# Set execution_pane from that response. Later choose the widest execution pane.
herdr pane split "$execution_pane" --direction right --ratio 0.5 --cwd "$project" --no-focus
```

## Launch and continue

Choose a unique name per participant (for example `fp21-astra`) and an available
shell pane from the layout above. Set `model` and `effort` from the
[shared role table](../core/roles.md), then pass native Codex arguments after `--`:

```bash
herdr agent start "$name" --kind codex --pane "$pane" -- \
  -C "$project" -m "$model" -c "model_reasoning_effort=\"$effort\"" \
  --sandbox workspace-write --ask-for-approval never --no-alt-screen
```

For the Luna roles, also pass `-c 'service_tier="fast"'` and
`-c 'features.fast_mode=true'` after `--` when the installed Codex supports them.
Other roles have no tier override. These are per-session launch arguments, not
changes to the user's config. Effective permissions can depend on the host/version;
do not replace a failed sandbox request with unrestricted access. Older
Codex/shared-server versions needed `-c 'default_permissions=":workspace"'`;
use a host-supported setting only when needed, rather than enforcing that
compatibility workaround everywhere.

After startup is ready, send the role, request and relevant context. Supply
readable paths to the shared workflow/role table or include the relevant content;
children need their assignment, not another invocation of the coordinating SKILL.

```bash
herdr agent prompt "$name" "$assignment" --wait --timeout 300000
herdr agent read "$name" --source recent-unwrapped --lines 200
# Send fixes or follow-up questions to this same name once its turn is settled.
```

Use `agent wait` when work is already running. The timeout above is in
milliseconds; host limits can be lower. Retain the command handle through yields
and await it rather than launching another waiter. If `prompt --wait` times out,
inspect `agent get` and `agent read` before deciding what to do.

`idle`/`done` indicate readiness, not successful completion of a particular
assignment. Read the output and resolve any blocked state. Do not stack a new
assignment onto a working agent: a lifecycle wait does not distinguish requests.
Use ordinary responses first; if terminal history cannot recover the result,
follow the official SKILL's fallback of asking for a Markdown file.

## Resume and release

On resume, use the retained names and `agent list`/`agent get` to locate
participants and read their latest results. A moved pane may have a new ID.
Before closing a finished participant, resolve its current pane and check that
it still hosts that participant, then use `pane close` for the pane you created.
Keep sessions needed for fixes and leave unrelated panes and Main untouched.

The CLI supplies startup readiness, prompt delivery, wait and read operations.
It does not prove semantic success or receipt by Main, and cannot by itself
resume a Main whose host has stopped running. No FrontierPlan ledger is needed.

References: [official SKILL](https://herdr.dev/docs/agent-skill/),
[agent automation](https://herdr.dev/docs/agent-automation/).
