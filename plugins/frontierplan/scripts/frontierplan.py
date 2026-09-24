#!/usr/bin/env python3
"""FrontierPlan's local, cooperative handoff ledger. Python 3.11+, stdlib only.

This is not an authorization service, model runner, or sandbox. Native agent
calls belong to Main; herdr.py supplies the visible CLI transport.
"""
from __future__ import annotations

import argparse
from contextlib import contextmanager
import hashlib
import json
import os
from pathlib import Path
import shlex
import subprocess
import sys
import tempfile
import time
import tomllib
import uuid

ROOT = Path(__file__).resolve().parent.parent
ROLES = ("director", "main", "researcher", "worker", "design", "reviewer")
CHILDREN = tuple(r for r in ROLES if r != "main")
EXECUTORS = ("worker", "design", "reviewer")
PLANNING = ("planning", "planned")
# Director decision kinds accepted for each kind of Director turn.
PURPOSES = {
    "planning": ("research", "reply", "plan", "authorize", "blocked"),
    "research_results": ("research", "reply", "plan", "authorize", "blocked"),
    "consultation": ("advice", "plan", "blocked"),
    "final_check": ("final_check", "blocked"),
}
AC_STATUS = ("met", "partial", "unverified")


class Failure(Exception):
    """An actionable, non-retryable-until-inspected protocol error."""


def require(condition: object, message: str) -> None:
    if not condition:
        raise Failure(message)


def read(path: Path | str) -> dict:
    value = json.loads(Path(path).read_text(encoding="utf-8"))
    require(isinstance(value, dict), f"Expected a JSON object: {path}")
    return value


def text(path: Path | str) -> str:
    value = Path(path).expanduser().read_text(encoding="utf-8")
    require(value.strip(), f"Empty input: {path}")
    return value


def digest(value: object) -> str:
    return hashlib.sha256(json.dumps(value, sort_keys=True, ensure_ascii=False).encode()).hexdigest()


def atomic(path: Path, value: dict) -> None:
    fd, tmp = tempfile.mkstemp(prefix=".write-", dir=path.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as stream:
            json.dump(value, stream, ensure_ascii=False, indent=2)
            stream.write("\n")
        os.replace(tmp, path)
    finally:
        if os.path.exists(tmp):
            os.unlink(tmp)


@contextmanager
def lock(path: Path):
    # A failed process leaves evidence instead of allowing two writers to race.
    # Never delete another process's lock automatically.
    try:
        fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    except FileExistsError as exc:
        raise Failure(f"Busy/stale lock: {path}; inspect the owning process before recovery.") from exc
    try:
        os.write(fd, str(os.getpid()).encode())
        os.close(fd)
        yield
    finally:
        path.unlink(missing_ok=True)


def thread_id() -> str | None:
    first, second = os.environ.get("CODEX_THREAD_ID"), os.environ.get("CODEX_SESSION_ID")
    require(not (first and second and first != second), "Contradictory Codex conversation IDs.")
    return first or second


def main_only(state: dict) -> None:
    require(os.environ.get("FRONTIERPLAN_ROLE") not in CHILDREN, "Only Main manages this run.")
    if state["backend"] == "herdr" and "main_identity" in state:
        # Ledger commands need the same live identity checks as transport commands.
        from herdr import Herdr, main_pane
        main_pane(state, Herdr(state))
    else:
        require(thread_id() == state["main_thread_id"], "This run belongs to a different Main conversation.")


def run_at(path: str | Path) -> tuple[Path, dict]:
    root = Path(path).expanduser().resolve()
    state = read(root / "run.json")
    require(state.get("schema_version") == 2,
            "Unsupported run format; finish runs created by FrontierPlan 0.1 with that version.")
    return root, state


@contextmanager
def transaction(path: str | Path):
    root, _ = run_at(path)
    with lock(root / ".state.lock"):
        state = read(root / "run.json")
        main_only(state)
        yield root, state
        atomic(root / "run.json", state)


def profile(role: str, director: str = "astra") -> dict:
    require(role in ROLES, "Unknown role.")
    require(director == "astra", "Only the Astra director is shipped.")
    path = ROOT / "profiles" / (f"director/{director}.toml" if role == "director" else f"{role}.toml")
    with path.open("rb") as stream:
        value = tomllib.load(stream)
    require(value.get("role") == role, "Profile/role mismatch.")
    if role == "main":
        require(value.get("inherit_session") is True, "Main must inherit the existing session.")
        require(not {"model", "reasoning_effort", "service_tier"} & value.keys(),
                "Main must not override model, effort or service tier.")
        return value
    require(value.get("reasoning_effort") in ("xhigh", "max"), "effort must be lowercase xhigh or max.")
    require(isinstance(value.get("model"), str) and value["model"], "A model is required.")
    require(role in ("worker", "researcher") or "service_tier" not in value,
            "Only Luna Worker/Researcher have a tier override.")
    return value


def git(cwd: str, *args: str) -> str | None:
    """Output of a read-only git command, or None when it could not run."""
    try:
        result = subprocess.run(["git", "-C", cwd, *args], capture_output=True, text=True,
                                timeout=45, check=False)
    except (OSError, subprocess.TimeoutExpired):
        return None
    return result.stdout.strip() if result.returncode == 0 else None


def tasks(root: Path) -> list[tuple[Path, dict]]:
    return [(p.parent, read(p)) for p in sorted((root / "tasks").glob("*/task.json"))]


def task_at(path: str | Path) -> tuple[Path, dict, Path, dict]:
    path = Path(path).expanduser().resolve()
    task = read(path / "task.json")
    root, state = run_at(task["run"])
    require(path.parent == root / "tasks" and path.name == task["id"], "Task path mismatch.")
    return path, task, root, state


def ended(task: dict) -> bool:
    return bool(task.get("closed") or task.get("lost"))


def current_result(path: Path, task: dict) -> dict | None:
    file = path / f"{task['request_id']}.result.json"
    if not file.exists():
        return None
    result = read(file)
    require(result.get("request_id") == task["request_id"], "Stale result.")
    return result


def receipt_of(path: Path) -> dict:
    return read(path / "receipt.json") if (path / "receipt.json").exists() else {}


def collected(path: Path, task: dict, complete: bool = True) -> dict:
    result = current_result(path, task)
    require(result and result["status"] in (("complete",) if complete else ("complete", "blocked")),
            "A current completed report is required.")
    require(receipt_of(path).get("digest") == digest(result), "Collect the current report first.")
    return result


def completed(path: Path, task: dict) -> bool:
    result = current_result(path, task)
    return bool(result and result["status"] == "complete" and receipt_of(path).get("digest") == digest(result))


def uncollected_reports(root: Path) -> list[dict]:
    """Reconcile current requests, independently of notification delivery history."""
    reports = []
    for path, task in tasks(root):
        if ended(task):
            continue
        result = current_result(path, task)
        if (result and result["status"] in ("complete", "blocked")
                and receipt_of(path).get("digest") != digest(result)):
            reports.append({"task": str(path), "role": task["role"],
                            "request_id": task["request_id"], "status": result["status"]})
    return reports


def director_task(root: Path) -> tuple[Path, dict]:
    live = [(p, t) for p, t in tasks(root) if t["role"] == "director" and not ended(t)]
    require(len(live) == 1, "Exactly one live Director is required; start it or recover the lost one.")
    return live[0]


def idle_executors(root: Path, plan_id: str | None) -> None:
    """Freeze check: every live executor has returned and been collected."""
    for path, task in tasks(root):
        if task["role"] not in EXECUTORS or ended(task):
            continue
        collected(path, task, complete=False)


def initialize(backend: str, cwd: str, request_file: str, *,
               main_identity: dict | None = None, herdr_binding: dict | None = None) -> dict:
    require(os.environ.get("FRONTIERPLAN_ROLE") not in CHILDREN, "Children cannot initialize runs.")
    require(backend in ("herdr", "subagent"), "Unknown backend.")
    if backend == "herdr" and main_identity is None and herdr_binding is None:
        # Do not create an unbound herdr run through the common CLI.
        from herdr import initialize as initialize_herdr
        return initialize_herdr(cwd, request_file)
    if main_identity is not None or herdr_binding is not None:
        require(backend == "herdr" and isinstance(main_identity, dict)
                and isinstance(herdr_binding, dict), "Only herdr accepts a bound Main identity.")
        require(all(isinstance(main_identity.get(k), str) and main_identity[k]
                    for k in ("agent", "session_id")), "Incomplete Main identity.")
        require(herdr_binding.get("main_pane_id") and herdr_binding.get("main_terminal_id"),
                "Incomplete Main terminal binding.")
    owner = main_identity["session_id"] if main_identity is not None else thread_id()
    require(owner, "Main's CODEX_THREAD_ID or CODEX_SESSION_ID is required for native subagents.")
    cwd = str(Path(cwd).expanduser().resolve())
    require(Path(cwd).is_dir(), "cwd must exist.")
    request = text(request_file)
    root = Path(tempfile.mkdtemp(prefix="frontierplan-"))
    for name in ("tasks", "messages", "decisions"):
        (root / name).mkdir(mode=0o700)
    (root / "messages" / "1.md").write_text(request, encoding="utf-8")
    state = {"schema_version": 2, "id": uuid.uuid4().hex[:12], "backend": backend,
             "cwd": cwd, "main_thread_id": owner, "phase": "planning", "user_seq": 1,
             "pending_forward": False, "authorization": None, "plan": None,
             "research": None, "final_checks": {}, "last_decision": None}
    if main_identity is not None:
        state.update(main_identity=dict(main_identity), herdr=dict(herdr_binding))
    atomic(root / "run.json", state)
    return {"run": str(root), "state": state}


def message(run: str, file: str) -> dict:
    """Store the user's exact words. Before execution they go to Astra unchanged."""
    value = text(file)
    with transaction(run) as (root, state):
        require(state["phase"] != "closed", "Start a new run after wrap-up.")
        state["user_seq"] += 1
        target = root / "messages" / f"{state['user_seq']}.md"
        target.write_text(value, encoding="utf-8")
        forward = state["phase"] in PLANNING
        state["pending_forward"] = forward
        if forward:
            # The new words may withdraw consent; only Astra can record it again.
            state["authorization"] = None
        # Pending research returns to Astra together with the new words.
        next_step = ("relay" if research_pending(state) else "forward") if forward else "main_decides"
        return {"message": state["user_seq"], "file": str(target), "forward_to_director": forward,
                "next": next_step}


def research_pending(state: dict) -> bool:
    research = state.get("research")
    return bool(research and not research["returned"])


DIRECTOR_CONTRACT = """You are Astra, FrontierPlan's Director. Follow {astra}.
Before implementation you own every judgment: understanding, research, design,
questions to the user and the Plan. Research yourself read-only and with isolated
probes; request broad investigation from Luna researchers with a `research`
decision. Main relays your decisions without judging them. Do not spawn agents,
manage panes, implement, edit project files, commit or publish."""

ROLE_CONTRACTS = {
    "researcher": """You are a Luna researcher answering Astra's research request.
Investigate read-only. Temporary probes go only under {scratch}. Do not edit project
files, commit or publish. Report facts with evidence (paths, commands, real output,
sources) and uncertainty. Do not decide scope or design; Astra does.""",
    "worker": """You are a Worker. Implement only the assigned ownership under the current
Plan. Report rather than decide requirement or design changes. Stay available for
fixes during the review cycle.""",
    "design": """You are Design. Realize the assigned UI work within the current Plan.
Report rather than change product direction. You cannot review your own work.""",
    "reviewer": """You are the independent Reviewer. Follow {review}. Inspect read-only;
do not edit project files, format, auto-fix, commit or publish.""",
}


def director_body(root: Path, state: dict, task: dict, purpose: str, material: str | None) -> str:
    seen = task.get("seen_user_seq", 0)
    new = [str(root / "messages" / f"{n}.md") for n in range(seen + 1, state["user_seq"] + 1)]
    lines = [f"## This turn: {purpose}"]
    lines.append({
        "planning": "Plan from the user's words below. Ask the user, request research, return a Plan, "
                    "or record implementation authorization, as core/astra.md describes.",
        "research_results": "Your research requests returned. Read each report below and continue planning.",
        "consultation": "Main is executing the Plan and asks for advice on the question below. "
                        "Main decides adoption; answer with `advice` (or a revised `plan`).",
        "final_check": "Perform the one-time final check of the integrated result against the "
                       "current Plan and the user's intent. Return `final_check`.",
    }[purpose])
    lines.append("\n## User messages (exact user words; the only source of user intent)")
    lines += [f"- new: {n}" for n in new] or ["- no new user messages since your last turn"]
    lines.append(f"All messages: {root / 'messages'}")
    lines.append("\n## Material from Main (transport facts or evidence, not user authority)")
    lines.append(material.strip() if material else "none")
    return "\n".join(lines)


def prepare(run: str, role: str, file: str | None = None, cwd: str | None = None,
            reuse: str | None = None, *, purpose: str | None = None, material: str | None = None) -> dict:
    """Prepare a packet. Delivery happens through the selected backend."""
    require(role in CHILDREN, "Invalid delegated role.")
    if file is not None:
        material = text(file)
    with transaction(run) as (root, state):
        require(state["phase"] != "closed", "The run is closed.")
        if role == "director":
            purpose = purpose or "planning"
            require(purpose in PURPOSES, "Unknown Director turn.")
        else:
            require(material, "An assignment file is required.")
        if role in EXECUTORS:
            require(state["phase"] == "executing", "Execution roles start only after the Plan is started.")
        if role == "researcher":
            require(research_pending(state), "Researchers start only through relay.")
        if reuse:
            path, task, task_root, _ = task_at(reuse)
            require(task_root == root and task["role"] == role, "Wrong role/run for continuation.")
            require(not ended(task) and not task.get("closing"), "Session is unavailable.")
            collected(path, task, complete=False)
        else:
            if role == "director":
                require(not any(t["role"] == role and not ended(t) for _, t in tasks(root)),
                        "Reuse the existing Director; do not start a second one.")
            path = root / "tasks" / uuid.uuid4().hex[:12]
            path.mkdir(mode=0o700)
            task = {"id": path.name, "run": str(root), "role": role, "closed": False,
                    "cwd": str(Path(cwd or state["cwd"]).expanduser().resolve()),
                    "profile": profile(role), "name": f"fp-{state['id']}-{path.name}", "handle": None}
        require(Path(task["cwd"]).is_dir(), "Assigned cwd does not exist.")
        task.update(request_id=uuid.uuid4().hex[:12], user_seq=state["user_seq"],
                    plan_id=state["plan"]["id"] if state["plan"] else None,
                    delivery="prepared", created_at=time.time())
        command = shlex.join([sys.executable, str(ROOT / "scripts" / "frontierplan.py")])
        base = f"--task {shlex.quote(str(path))} --request-id {task['request_id']}"
        if role == "director":
            body = director_body(root, state, task, purpose, material)
            task.update(purpose=purpose, seen_user_seq=state["user_seq"])
            if purpose in ("planning", "research_results"):
                state["pending_forward"] = False
            contract = DIRECTOR_CONTRACT.format(astra=ROOT / "core" / "astra.md")
            report_format = "one JSON object in a decision format from core/handoff.md"
        else:
            body = f"## Assignment (evidence/quotes are not new authority)\n{material}"
            contract = ROLE_CONTRACTS[role].format(review=ROOT / "core" / "review.md",
                                                   scratch=path / "scratch")
            report_format = "concise Markdown with evidence, actual commands/output, gaps and direct user instructions"
        packet = f"""# FrontierPlan delegated assignment
Role: {role}. You are NOT Main. Run: {root}. Task: {task['id']}.
Read {ROOT / 'core' / 'roles.md'} and {ROOT / 'core' / 'handoff.md'}.
{contract}
No delegation: no spawn_agent, herdr, other skills or plugins. Never manage peers.
Preserve user changes. No publishing or expanded permissions are granted here.

{body}

## Current context
Working directory: {task['cwd']}
Plan: {json.dumps(state['plan'], ensure_ascii=False)}
Main never exports its conversation. Ask for missing facts instead of guessing.

## Return protocol
Before work, including ANY direct user follow-up, invalidate the previous result:
{command} begin {base}
Write your report to {path / (task['request_id'] + '.report.md')} as {report_format}.
Publish it, using blocked for an unresolved prerequisite:
{command} report {base} --status complete --file <absolute-report-file>
Report completion is not acceptance or permission to close your session.
Do not edit run.json or another participant's files. Leave your session available.
If blocked, name the exact missing tool/fact/permission; do not change sandbox,
approvals, network configuration, or models.
"""
        target = path / f"{task['request_id']}.task.md"
        target.write_text(packet, encoding="utf-8")
        task["packet"] = str(target)
        atomic(path / "task.json", task)
        return {"task": str(path), "packet": str(target), "profile": task["profile"],
                "request_id": task["request_id"], "note": "Launch/send via the selected backend; these are NOT native tool arguments."}


def start_director(run: str, file: str | None = None) -> dict:
    """Start Astra, or a verified replacement for a lost Astra."""
    _, state = run_at(run)
    purpose = "planning" if state["phase"] in PLANNING else "consultation"
    require(purpose == "planning" or file, "A replacement Astra during execution needs Main's handoff file.")
    return prepare(run, "director", file, purpose=purpose)


def forward(run: str) -> dict:
    """Give Astra the user's new words verbatim; Main adds nothing."""
    root, state = run_at(run)
    require(state.get("pending_forward"), "No unforwarded user message.")
    require(not research_pending(state), "Research is in flight; relay returns it to Astra with the new message.")
    path, _ = director_task(root)
    return prepare(run, "director", reuse=str(path), purpose="planning")


def consult(run: str, file: str) -> dict:
    root, state = run_at(run)
    require(state["phase"] == "executing", "Consultation is for the execution phase.")
    path, _ = director_task(root)
    return prepare(run, "director", file, reuse=str(path), purpose="consultation")


def final_check(run: str, file: str) -> dict:
    root, state = run_at(run)
    require(state["phase"] == "executing" and state["plan"], "No executing Plan to check.")
    plan_id = state["plan"]["id"]
    require(plan_id not in state["final_checks"], "The final check already ran for this Plan; it runs once.")
    idle_executors(root, plan_id)
    require(any(t["role"] == "reviewer" and t.get("plan_id") == plan_id and completed(p, t)
                for p, t in tasks(root)), "A completed independent review is required before the final check.")
    head = git(state["cwd"], "rev-parse", "HEAD") or "unavailable (git failed)"
    status = git(state["cwd"], "status", "--short")
    status = "unavailable (git failed)" if status is None else status or "clean"
    material = f"Worktree: {state['cwd']}\nHEAD: {head}\nStatus:\n{status}\n\n{text(file)}"
    path, _ = director_task(root)
    return prepare(run, "director", reuse=str(path), purpose="final_check", material=material)


def bind(task_path: str, handle_file: str) -> dict:
    path, task, root, state = task_at(task_path)
    value = read(handle_file)
    with transaction(root):
        require(state["backend"] == "subagent", "herdr handles are managed by herdr.py.")
        require(value.get("agent_id") and value.get("evidence"), "Record the returned agent ID and launch evidence.")
        require(not task.get("handle"), "Already bound; continue the existing agent.")
        require(not any(t.get("handle") and t["handle"].get("agent_id") == value["agent_id"] for _, t in tasks(root)),
                "One native session cannot fill two roles.")
        task.update(handle=value, delivery="sent")
        atomic(path / "task.json", task)
    return {"bound": task["id"], "handle": value}


def publish(task_path: str, request_id: str, status: str, file: str | None = None) -> dict:
    path, task, _, state = task_at(task_path)
    with lock(path / ".report.lock"):
        task = read(path / "task.json")
        require(not ended(task) and not task.get("closing") and state["phase"] != "closed",
                "Session ended or closure is pending.")
        require(request_id == task["request_id"], "The request is stale.")
        require(status in ("working", "complete", "blocked"), "Invalid status.")
        report = "" if status == "working" else text(file)
        if task["role"] == "director" and status == "complete":
            require(isinstance(json.loads(report), dict), "Director must return a JSON object.")
        result = {"task_id": task["id"], "request_id": request_id, "status": status,
                  "report": report, "published_at": time.time()}
        atomic(path / f"{request_id}.result.json", result)
        return result


def collect(task_path: str) -> dict:
    path, task, _, state = task_at(task_path)
    main_only(state)
    with lock(path / ".report.lock"):
        result = current_result(path, task)
        require(result and result["status"] in ("complete", "blocked"), "No returned report yet.")
        atomic(path / "receipt.json", {"digest": digest(result), "request_id": task["request_id"]})
        return result


def nonempty(value: object) -> bool:
    return isinstance(value, str) and bool(value.strip())


def strings(value: object) -> bool:
    return isinstance(value, list) and all(nonempty(x) for x in value)


def check_authorization(state: dict, root: Path, number: object) -> dict:
    require(isinstance(number, int) and 1 <= number <= state["user_seq"],
            "authorization_message must name an existing user message.")
    return {"message": number, "digest": digest(text(root / "messages" / f"{number}.md"))}


def director_value(result: dict) -> dict:
    """Astra's JSON decision; a report published as blocked is a `blocked` decision."""
    try:
        value = json.loads(result["report"])
    except ValueError:
        value = None
    if result["status"] == "blocked" and not (isinstance(value, dict) and value.get("kind") == "blocked"):
        value = {"kind": "blocked", "user_response": result["report"].strip()}
    require(isinstance(value, dict), "Director must return a JSON object.")
    return value


def decision(task_path: str) -> dict:
    """Record Astra's decision and tell Main the mechanical next step."""
    path, task, root, _ = task_at(task_path)
    with transaction(root) as (_, state):
        require(state["phase"] != "closed", "The run is closed.")
        require(task["role"] == "director" and not ended(task), "Only the live Director returns decisions.")
        result = collected(path, task, complete=False)
        value = director_value(result)
        kind, purpose = value.get("kind"), task.get("purpose", "planning")
        require(kind in PURPOSES[purpose], f"`{kind}` is not a valid answer to a {purpose} turn.")
        if purpose in ("planning", "research_results"):
            require(task["user_seq"] == state["user_seq"] and not state["pending_forward"],
                    "The user wrote again after this turn started; forward the new message instead.")
        target = root / "decisions" / f"{task['request_id']}.json"
        require(not target.exists(), "This Director decision was already recorded.")
        relay = value.get("user_response")
        require(relay is None or nonempty(relay), "user_response must be non-empty text when present.")
        next_step = "relay_to_user" if relay else "main_decides"
        if kind in ("reply", "blocked"):
            require(relay, "Director must write the user response.")
        elif kind == "research":
            require(state["phase"] in PLANNING, "Research requests belong to planning.")
            requests = value.get("requests")
            require(isinstance(requests, list) and requests
                    and all(isinstance(r, dict) and nonempty(r.get("id")) and nonempty(r.get("assignment"))
                            for r in requests), "research needs requests with id and assignment.")
            require(len({r["id"] for r in requests}) == len(requests), "Duplicate research request id.")
            state["research"] = {"decision": str(target), "requests": requests, "tasks": {}, "returned": False}
            next_step = "relay"
        elif kind == "plan":
            for key in ("plan_id", "plan"):
                require(nonempty(value.get(key)), f"Missing {key}.")
            for key in ("acceptance_criteria", "verification"):
                require(strings(value.get(key)) and value[key], f"Missing {key}.")
            require(relay, "Director must present the Plan to the user.")
            prior = [read(p).get("plan_id") for p in (root / "decisions").glob("*.json") if read(p).get("kind") == "plan"]
            require(value["plan_id"] not in prior, "A changed Plan needs a new plan_id.")
            state.update(plan={"id": value["plan_id"], "digest": digest(value), "file": str(target),
                               "user_seq": state["user_seq"]}, phase="planned", authorization=None)
            if value.get("authorization_message") is not None:
                state["authorization"] = dict(check_authorization(state, root, value["authorization_message"]),
                                              plan_id=value["plan_id"])
            next_step = "start" if state["authorization"] else "relay_to_user"
        elif kind == "authorize":
            require(state["phase"] == "planned" and state["plan"] and value.get("plan_id") == state["plan"]["id"],
                    "authorize must name the current Plan.")
            state["authorization"] = dict(check_authorization(state, root, value.get("authorization_message")),
                                          plan_id=value["plan_id"])
            next_step = "start"
        elif kind == "advice":
            require(nonempty(value.get("advice")), "advice text is required.")
        elif kind == "final_check":
            plan = read(state["plan"]["file"])
            require(value.get("plan_id") == plan["plan_id"], "final_check must name the current Plan.")
            rows = value.get("ac_status")
            require(isinstance(rows, list) and len(rows) == len(plan["acceptance_criteria"])
                    and all(isinstance(r, dict) and nonempty(r.get("criterion"))
                            and r.get("status") in AC_STATUS and nonempty(r.get("evidence")) for r in rows),
                    "ac_status needs one {criterion, status, evidence} row per acceptance criterion; "
                    "status is met, partial or unverified.")
            for key in ("findings", "plan_divergence"):
                require(isinstance(value.get(key), list), f"{key} must be a list (empty when none).")
            state["final_checks"][plan["plan_id"]] = str(target)
        if kind in ("plan", "authorize") and relay and next_step == "start":
            next_step = "relay_to_user_then_start"
        atomic(target, value)
        state["last_decision"] = {"kind": kind, "file": str(target), "task": str(path),
                                  "request_id": task["request_id"], "result_digest": digest(result),
                                  "user_seq": state["user_seq"]}
        return {"decision": value, "next": next_step, "relay_to_user": relay,
                "note": "Show relay_to_user to the user exactly as written; do not summarize or add judgment."}


def relay(run: str) -> dict:
    """Mechanical research relay: prepare researchers, or return their reports to Astra."""
    root, state = run_at(run)
    require(research_pending(state), "No pending research request.")
    research = state["research"]
    for request in research["requests"]:
        if request["id"] in research["tasks"]:
            continue
        # Record each prepared task at once so a partial failure never duplicates work.
        value = prepare(run, "researcher", material=request["assignment"])
        with transaction(root) as (_, state):
            state["research"]["tasks"][request["id"]] = value["task"]
        research = state["research"]
    unlaunched = []
    for research_id, task_path in research["tasks"].items():
        task = task_at(task_path)[1]
        if not task.get("handle"):
            require(task.get("delivery") == "prepared",
                    "A researcher start is uncertain; inspect its recorded task before retrying.")
            unlaunched.append({"research_id": research_id, "task": task_path, "packet": task["packet"],
                               "profile": task["profile"]})
    if unlaunched:
        return {"action": "spawn_researchers", "tasks": unlaunched}
    waiting, returned = [], []
    for research_id, task_path in research["tasks"].items():
        path, task, _, _ = task_at(task_path)
        result = current_result(path, task)
        if not (result and result["status"] in ("complete", "blocked")
                and receipt_of(path).get("digest") == digest(result)):
            waiting.append({"research_id": research_id, "task": task_path})
        else:
            report = path / f"{task['request_id']}.report.md"
            returned.append(f"- {research_id} ({result['status']}): {report if report.exists() else 'see result.json'}"
                            f"\n  result record: {path / (task['request_id'] + '.result.json')}")
    if waiting:
        return {"action": "wait", "pending": waiting}
    path, _ = director_task(root)
    material = "Research reports, unedited by Main:\n" + "\n".join(returned)
    value = prepare(run, "director", reuse=str(path), purpose="research_results", material=material)
    with transaction(root) as (_, state):
        state["research"]["returned"] = True
    return {"action": "return_to_director", "director": value, "researchers": list(research["tasks"].values()),
            "note": "Close the returned researchers after delivery."}


def start(run: str) -> dict:
    with transaction(run) as (root, state):
        require(state["phase"] == "planned" and state["plan"], "A current Plan is required.")
        require(not state["pending_forward"], "Forward the newest user message to Astra first.")
        require(not research_pending(state), "Astra's research is still in flight.")
        auth = state["authorization"]
        require(auth and auth.get("plan_id") == state["plan"]["id"]
                and digest(text(root / "messages" / f"{auth['message']}.md")) == auth["digest"],
                "Astra has not recorded implementation authorization for this Plan.")
        state["phase"] = "executing"
        return {"phase": "executing", "plan": state["plan"]}


def finish(run: str, file: str | None = None, discussion: bool = False) -> dict:
    with transaction(run) as (root, state):
        require(state["phase"] != "closed", "The run is already closed.")
        require(not state["pending_forward"], "Forward the newest user message to Astra first.")
        if discussion:
            require(state["phase"] in PLANNING, "Implementation cannot finish as discussion-only.")
            require(not any(t["role"] in EXECUTORS for _, t in tasks(root)),
                    "Implementation cannot finish as discussion-only.")
            last = state["last_decision"]
            require(last and last["kind"] in ("reply", "plan") and last["user_seq"] == state["user_seq"],
                    "Astra must answer the latest user input.")
            report = read(last["file"])["user_response"]
        else:
            require(state["phase"] == "executing" and state["plan"], "No executing Plan.")
            require(state["plan"]["id"] in state["final_checks"], "Run Astra's one-time final check first.")
            require(file, "Main's final report file is required.")
            idle_executors(root, state["plan"]["id"])
            report = text(file)
            (root / "final-report.md").write_text(report, encoding="utf-8")
        state["phase"] = "closed"
        return {"user_response": report, "phase": "closed",
                "note": "Close only owned, idle sessions after transport-specific identity/activity checks."}


def closable(path: Path, task: dict, state: dict) -> dict:
    require(task["role"] in CHILDREN, "Never close Main.")
    require(not ended(task) and not task.get("closing"), "Participant is unavailable or closure is uncertain.")
    if task["role"] == "director":
        require(state["phase"] == "closed", "Astra stays until finish.")
    return collected(path, task, complete=needs_complete(task, state))


def needs_complete(task: dict, state: dict) -> bool:
    # Unresolved executor blockers stay visible until the overall wrap-up. A blocked
    # research answer is still an answer that has been returned to Astra.
    return state["phase"] != "closed" and task["role"] != "researcher"


def close_record(task_path: str, closure_file: str) -> dict:
    """Record an actual native closure; this helper never closes a native agent."""
    path, task, root, _ = task_at(task_path)
    closure = read(closure_file)
    with transaction(root) as (_, state), lock(path / ".report.lock"):
        require(state["backend"] == "subagent", "Use herdr.py close for herdr participants.")
        task = read(path / "task.json")
        closable(path, task, state)
        require(closure.get("agent_id") == (task.get("handle") or {}).get("agent_id")
                and closure.get("closed") is True and nonempty(closure.get("evidence")),
                "Record the actual native close result for this agent ID.")
        task.update(closed=True, closure=closure)
        atomic(path / "task.json", task)
    return {"closed_record": task["id"], "note": "Native closure is Main-supplied evidence, not independently verified."}


def retire_lost(task_path: str, evidence_file: str) -> dict:
    path, task, root, _ = task_at(task_path)
    evidence = text(evidence_file)
    with transaction(root) as (_, state):
        require(state["phase"] != "closed", "The run is closed.")
        require(not ended(task) and not task.get("closing"), "Participant already ended or closing.")
        task.update(lost=True, recovery_evidence=evidence)
        atomic(path / "task.json", task)
    return {"retired_lost_task": task["id"], "note": "No process killed. Main must have verified loss and pass prior evidence to a replacement."}


def cli() -> None:
    p = argparse.ArgumentParser(description=__doc__)
    sub = p.add_subparsers(dest="action", required=True)
    q = sub.add_parser("init"); q.add_argument("--backend", choices=("herdr", "subagent"), required=True); q.add_argument("--cwd", default=os.getcwd()); q.add_argument("--request-file", required=True)
    q = sub.add_parser("start-director"); q.add_argument("--run", required=True); q.add_argument("--file")
    for name in ("message", "consult", "final-check"):
        q = sub.add_parser(name); q.add_argument("--run", required=True); q.add_argument("--file", required=True)
    q = sub.add_parser("prepare"); q.add_argument("--run", required=True); q.add_argument("--role", choices=EXECUTORS, required=True); q.add_argument("--file", required=True); q.add_argument("--cwd"); q.add_argument("--reuse")
    q = sub.add_parser("bind"); q.add_argument("--task", required=True); q.add_argument("--handle-file", required=True)
    for name in ("begin", "report"):
        q = sub.add_parser(name); q.add_argument("--task", required=True); q.add_argument("--request-id", required=True)
        if name == "report":
            q.add_argument("--file", required=True); q.add_argument("--status", choices=("complete", "blocked"), required=True)
    for name in ("collect", "decision"):
        q = sub.add_parser(name); q.add_argument("--task", required=True)
    q = sub.add_parser("close-record"); q.add_argument("--task", required=True); q.add_argument("--closure-file", required=True)
    q = sub.add_parser("retire-lost"); q.add_argument("--task", required=True); q.add_argument("--file", required=True)
    for name in ("forward", "relay", "start", "status", "finish"):
        q = sub.add_parser(name); q.add_argument("--run", required=True)
        if name == "finish": q.add_argument("--file"); q.add_argument("--discussion", action="store_true")
    q = sub.add_parser("profile"); q.add_argument("--role", choices=ROLES, required=True)
    a = p.parse_args()
    if a.action == "init": result = initialize(a.backend, a.cwd, a.request_file)
    elif a.action == "start-director": result = start_director(a.run, a.file)
    elif a.action == "message": result = message(a.run, a.file)
    elif a.action == "forward": result = forward(a.run)
    elif a.action == "consult": result = consult(a.run, a.file)
    elif a.action == "final-check": result = final_check(a.run, a.file)
    elif a.action == "relay": result = relay(a.run)
    elif a.action == "prepare": result = prepare(a.run, a.role, a.file, a.cwd, a.reuse)
    elif a.action == "bind": result = bind(a.task, a.handle_file)
    elif a.action in ("begin", "report"): result = publish(a.task, a.request_id, "working" if a.action == "begin" else a.status, getattr(a, "file", None))
    elif a.action == "collect": result = collect(a.task)
    elif a.action == "decision": result = decision(a.task)
    elif a.action == "start": result = start(a.run)
    elif a.action == "finish": result = finish(a.run, a.file, a.discussion)
    elif a.action == "close-record": result = close_record(a.task, a.closure_file)
    elif a.action == "retire-lost": result = retire_lost(a.task, a.file)
    elif a.action == "profile": result = profile(a.role)
    else:
        root, result = run_at(a.run); main_only(result)
        result = {"state": result, "tasks": [t for _, t in tasks(root)], "uncollected": uncollected_reports(root)}
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    # herdr imports this module too; keep Failure and runtime state single-source.
    sys.modules["frontierplan"] = sys.modules[__name__]
    try:
        cli()
    except (Failure, OSError, ValueError, KeyError, subprocess.TimeoutExpired) as exc:
        print(json.dumps({"error": str(exc)}, ensure_ascii=False), file=sys.stderr)
        sys.exit(1)
