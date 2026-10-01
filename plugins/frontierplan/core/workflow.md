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

Give Workers the Plan, relevant project context, scope, completion criteria and
the checks they should run. Use Design when UI work needs a dedicated owner.
Researchers investigate without changing the project. Each participant can use
the skills and tools appropriate to its assignment and existing authorization.

Use an independent Reviewer to examine the actual result against the request,
including unnecessary complexity and concrete regressions. Main decides which
findings to accept and explains consequential decisions. Send accepted fixes to
the responsible Worker and return the result to the same Reviewer. Keep those
sessions through the review cycle; neither a round quota nor elapsed time is a
reason to stop or ask whether to continue.

When the result is ready, ask Astra once per Plan to check it against the user's
intent and Plan, with the diff, verification and remaining limitations. Main
adjudicates her findings like review findings. Address accepted fixes with the
Worker and Reviewer, then Main reports the outcome. Astra is an adviser here,
not an additional acceptance gate.

Keep the user informed during work. Ask for input when a real scope or cost
decision needs it, carrying forward permission already given.

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
