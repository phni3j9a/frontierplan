# Working together

FrontierPlan gives capable agents a division of responsibility, not a state
machine. Use ordinary messages, the project's normal tools and proportionate
verification. An assignment needs a purpose, relevant context, scope and a useful
definition of done; let its owner choose the implementation and report format.

This workflow applies to an explicitly invoked FrontierPlan task and its follow-ups.
Follow the user's latest instructions, including changes to scope or staffing.
If you receive a delegated role assignment, do that work and report to Main;
you are not being asked to start another coordinating team.

## Planning: Astra decides, Main relays

Main sends Astra the user's request, project instructions and relevant context.
Astra owns the interpretation, research, design and Plan. She can investigate
directly or ask Main to start Researchers with specific questions. Main passes on
her requests and returns their findings without rewriting them.

Main shows Astra's questions, advice and Plan to the user verbatim and forwards
the user's replies verbatim. Include new input received while work is running
before acting on an older Plan. Main handles transport issues; substantive
planning decisions stay with Astra.

Astra's Plan should explain the intended result, approach, scope and verification
at a level suited to the task. Prefer the simpler approach that meets the request.
Ask about uncertainty that materially changes the outcome or cost. A consultation
ends with advice; an implementation request already authorizes work within its
scope, so do not create another approval ritual.

## Execution: Main coordinates and decides

Once the Plan is ready and implementation is authorized, Main owns assignments,
integration, review decisions and completion. Keep the user's objective in view
when new information arrives; consult Astra when her design judgment would help.

Keep the user informed during work. Ask for input when a real scope or cost
decision needs it, carrying forward permission already given.

Give Workers the Plan, relevant project context, task purpose, scope, completion
criteria and the checks they should run. Use Design when UI work needs a dedicated
owner. Researchers investigate without changing the project. Each participant can
use the skills and tools appropriate to its assignment and existing authorization.

### Reviewer: verify the assigned task

Use an independent Reviewer to verify that the responsible Worker correctly
completed Main's assignment. Review coherent implementation tasks, not every
commit. Design's UI implementation follows the same review process.

Supply Main's task purpose, scope, completion criteria, relevant Plan constraints,
the actual diff and verification results. Check these artifacts independently;
the implementer's completion report cannot narrow the assignment. Review missed
requirements, implementation defects, material verification gaps, unnecessary
complexity and regressions caused by the changes, including affected behavior
outside the diff. Report contradictory assignments or concrete out-of-scope
problems to Main; do not add requirements or redesign the task yourself.

Main decides which findings to accept and explains consequential decisions. Send
accepted fixes to the responsible Worker or Design and return the result to the
same Reviewer. Keep those sessions through the review cycle; neither a round
quota nor elapsed time is a reason to stop or ask whether to continue.

### Main: verify integration

Main owns verification across task boundaries. Assign necessary integration
checks to a Worker and have the Reviewer verify that assignment and its evidence.
Individually completed tasks do not establish that the combined result works.

### Astra: check the overall result once

When the integrated result is ready, ask Astra once per Plan to check whether it
fulfills the user's intent and Plan. Supply the Plan, diff, task and integration
verification, review decisions and remaining limitations. Focus on overall goal
fulfillment, gaps left by task decomposition and meaningful divergence from the
Plan. Do not repeat the Reviewer's task-level implementation review, introduce
new requirements or demand verification beyond the agreed Plan. Any concrete
defect encountered still goes to Main.

Main adjudicates Astra's findings like review findings. Address accepted fixes
with the responsible Worker or Design and the same Reviewer; fixes do not return
to Astra for another final check. Main decides completion and reports the outcome.
Astra is an adviser here, not an additional acceptance gate.

## Continuity and completion

Prefer the host's completion notifications and supported waits over repeated
status polling. Read a participant's result before assigning the next step:
a completed turn or an idle terminal is not proof that its task succeeded.
A timeout alone does not justify duplicating a prompt or replacing an agent.

For long work, keep a short handoff note with the current Plan, participant
names/IDs, unfinished work and the next action. Choose a convenient location;
there is no required schema or update command. On resume, inspect those
participants and their latest results before continuing. If a session is lost,
recover its context and identify any replacement clearly.

Retain the running wait's handle across host yields. A background command does
not guarantee that a stopped Main will resume; describe any actual host limit.

Once a participant's results are read and its work is finished, release the
session using the chosen backend's supported operation. Keep Astra through the
final check and keep Main's existing session. Finish with the delivered result,
checks actually performed and any remaining work, including retained sessions.

## Environment

Use the [role table](roles.md) for model selection and only the selected backend.
Report an unavailable model or backend instead of silently substituting another.
Main keeps its existing host, model and settings. Permissions, authentication
and available tools come from that environment; role instructions do not create
a sandbox. FrontierPlan does not install daemons or edit global configuration.
