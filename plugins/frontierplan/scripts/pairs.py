#!/usr/bin/env python3
"""Bounded Worker/Design–Reviewer handoffs, using the existing task ledger.

One pair record, existing per-turn reports, no broker/daemon. Native continuation
is performed by the child through its real host tools, never by this Python helper.
Like frontierplan.py, this is a cooperative protocol, not a security sandbox.
"""
from __future__ import annotations

import argparse
from contextlib import contextmanager
import hashlib
import json
import os
from pathlib import Path
import shlex
import stat
import subprocess
import sys
import time
import uuid

import frontierplan as fp

TERMINAL = ("PASS", "BLOCKED", "ESCALATE")
KINDS = ("candidate", "findings", "pass", "blocked", "escalate")


def at(task_path: str | Path) -> tuple[Path, dict, Path, dict]:
    path, task, root, state = fp.task_at(task_path)
    fp.require(task.get("pair"), "This participant is not registered in a pair.")
    record = Path(task["pair"])
    fp.require(record.parent.parent == root / "tasks" and record.name == "pair.json",
               "Pair path is outside this run.")
    pair = fp.read(record)
    fp.require(pair["run"] == str(root) and pair["id"] == record.parent.name, "Pair/run mismatch.")
    return record, pair, root, state


def members(pair: dict) -> list[Path]:
    return [Path(pair["run"]) / "tasks" / pair[key] for key in ("worker", "reviewer")]


@contextmanager
def edit(task_path: str | Path):
    record, _, root, _ = at(task_path)
    with fp.lock(record.parent / ".pair.lock"):
        pair, state = fp.read(record), fp.read(root / "run.json")
        yield record, pair, root, state
        fp.atomic(record, pair)


def scopes(values: list[str] | None) -> list[str]:
    result = values or ["."]
    fp.require(all(v and not Path(v).is_absolute() and ".." not in Path(v).parts
                   and ".git" not in Path(v).parts for v in result), "Scopes must be relative repository paths.")
    return sorted(set(str(Path(v)) for v in result))


def snapshot(pair: dict) -> dict:
    """Fingerprint owned tracked AND non-ignored untracked files, including deletions.

    No HEAD-only shortcut: uncommitted changes also invalidate a review. Pass
    literal pathspecs, so wildcard-looking filenames do not expand the boundary.
    """
    result = subprocess.run(["git", "--literal-pathspecs", "-C", pair["cwd"], "ls-files", "-z",
                             "--cached", "--others", "--exclude-standard", "--", *pair["scope"]],
                            capture_output=True, check=False, timeout=45)
    fp.require(result.returncode == 0, "Cannot snapshot the candidate; a Git worktree is required.")
    entries = {}
    for raw in sorted(set(result.stdout.split(b"\0")) - {b""}):
        name = os.fsdecode(raw)
        path = Path(pair["cwd"]) / name
        fp.require(path.parent.resolve().is_relative_to(Path(pair["cwd"])), "Candidate path crosses a directory symlink.")
        try:
            mode = path.lstat().st_mode
        except FileNotFoundError:
            entries[name] = {"deleted": True}
            continue
        if stat.S_ISLNK(mode):
            entries[name] = {"symlink": os.readlink(path)}
        else:
            fp.require(stat.S_ISREG(mode), f"Cannot fingerprint {name}; review submodules in their own worktree.")
            h = hashlib.sha256()
            with path.open("rb") as stream:
                for chunk in iter(lambda: stream.read(1024 * 1024), b""):
                    h.update(chunk)
            entries[name] = {"sha256": h.hexdigest(), "executable": bool(mode & 0o111)}
    return {"scope": pair["scope"], "files": entries}


def actor(task_path: str, request_id: str, pair: dict, state: dict) -> tuple[Path, dict, str]:
    path, task, _, _ = fp.task_at(task_path)
    side = "reviewer" if task["role"] == "reviewer" else "worker"
    fp.require(task["id"] == pair[side] and task["request_id"] == request_id,
               "Stale participant or turn; only the registered pair may send.")
    fp.require(not fp.ended(task) and not task.get("closing"), "Participant ended or is closing.")
    fp.require(state["phase"] == "executing" and state["plan"]["id"] == pair["plan_id"],
               "Pair belongs to an inactive Plan.")
    fp.require(task.get("handle"), "Main must bind/launch this participant first.")
    if state["backend"] == "herdr":
        import herdr as hd
        fp.require(os.environ.get("FRONTIERPLAN_ROLE") == task["role"]
                   and Path(os.environ.get("FRONTIERPLAN_TASK", "/")).resolve() == path,
                   "The calling child does not own this task.")
        api = hd.Herdr(state)
        current = hd.current_pane(api)
        agent = hd.live(task, api.agents())
        fp.require(current.get("terminal_id") == agent["terminal_id"]
                   and current.get("pane_id") == agent["pane_id"], "The calling terminal is not this child.")
    else:
        # A native handle must include the *observed* child conversation identity.
        # agent_id and CODEX_THREAD_ID are not assumed to mean the same thing.
        fp.require(fp.thread_id() and fp.thread_id() == task["handle"].get("thread_id"),
                   "Native pair calls require the bound child's observed thread_id.")
    return path, task, side


def write_result(path: Path, task: dict, status: str, report: str, **extra) -> dict:
    result = {"task_id": task["id"], "request_id": task["request_id"], "status": status,
              "report": report, "published_at": time.time(), **extra}
    with fp.lock(path / ".report.lock"):
        fp.atomic(path / f"{task['request_id']}.result.json", result)
    return result


def packet(path: Path, task: dict, pair: dict, message: str) -> None:
    command = shlex.join([sys.executable, str(fp.ROOT / "scripts" / "pairs.py")])
    base = f"--task {shlex.quote(str(path))} --request-id {task['request_id']}"
    body = f"""# FrontierPlan paired assignment
Role: {task['role']}. You are NOT Main. Pair: {task['pair']}.
Read {fp.ROOT / 'core' / 'roles.md'}, {fp.ROOT / 'core' / 'review.md'},
and {fp.ROOT / 'core' / 'pairs.md'}.
{fp.ROLE_CONTRACTS[task['role']].format(review=fp.ROOT / 'core' / 'review.md')}
No delegation, peer management, model changes or publishing. Only the registered
peer handoff through pairs.py is permitted. Preserve user changes and permissions.

## Short Task Contract
{pair['contract']}
Contract digest: {pair['contract_digest']}
Working directory: {pair['cwd']}
Fingerprint scope: {json.dumps(pair['scope'])}
Plan: {pair['plan_id']}

## This turn
{message}

## Return protocol
Before work (also for a direct user follow-up):
{command} begin {base}
If it returns waiting, end this turn and wait for the actual peer continuation.
Otherwise implement, or review read-only, within the contract above.
Write focused evidence/finding IDs to an absolute report file under {path}.
Worker/Design submits candidate (also for a fix or concrete counter-evidence);
Reviewer submits findings or pass. Either may submit blocked or escalate for a
missing prerequisite, requirement ambiguity, or same-cause lack of progress:
{command} submit {base} --kind <candidate|findings|pass|blocked|escalate> --file <report>
For findings/pass also supply --candidate <digest returned by begin>.
Herdr delivery resumes ONLY your peer. A busy peer leaves a prepared handoff:
{command} deliver {base}
For native subagents the helper returns a native_call_required target and packet;
YOU call the host's actual peer-continuation tool. Main must not relay this turn.
Notification alone is not continuation. Never blindly retry uncertain delivery.
After handing off, end your turn so your peer can resume you. Do not poll the peer
or remain in a blocking agent wait. PASS ends the pair's work, not the whole Plan.
Main collects the result and closes both sessions. Keep reports; do not edit the
pair record, another participant's files, or run.json directly.
"""
    target = path / f"{task['request_id']}.task.md"
    target.write_text(body, encoding="utf-8")
    task["packet"] = str(target)
    fp.atomic(path / "task.json", task)


def turn(pair: dict, target: Path, message: str, sender: dict | None = None) -> dict:
    task = fp.read(target / "task.json")
    fp.require(not fp.ended(task) and not task.get("closing"), "Peer unavailable; ask Main for replacement.")
    task.update(request_id=uuid.uuid4().hex[:12], delivery="prepared", created_at=time.time())
    packet(target, task, pair, message)
    handoff = {"from": sender["id"] if sender else "main",
               "from_request": sender["request_id"] if sender else None,
               "to": task["id"], "request_id": task["request_id"], "packet": task["packet"],
               "delivery": "prepared"}
    pair["pending"] = handoff
    return handoff


def create(run: str, file: str, cwd: str | None = None, scope: list[str] | None = None,
           role: str = "worker", capability_file: str | None = None) -> dict:
    root, state = fp.run_at(run)
    fp.main_only(state)
    fp.require(role in ("worker", "design"), "Only Worker/Design can implement a pair task.")
    capability = None
    if state["backend"] == "subagent":
        fp.require(capability_file, "Native peer resume is unverified; provide actual host capability evidence first.")
        capability = fp.read(capability_file)
        fp.require(capability.get("direct_peer_resume") is True and fp.nonempty(capability.get("evidence")),
                   "Host must support child-to-peer continuation; no hidden Main relay.")
    cwd = str(Path(cwd or state["cwd"]).resolve())
    fp.require(fp.git(cwd, "rev-parse", "--show-toplevel") == cwd, "Assign a Git worktree root as pair cwd.")
    contract = fp.text(file)
    owned = scopes(scope)
    snapshot({"cwd": cwd, "scope": owned})  # Fail before creating participants.
    worker = fp.prepare(run, role, file, cwd)
    reviewer = fp.prepare(run, "reviewer", file, cwd)
    path = Path(worker["task"])
    record = path / "pair.json"
    pair = {"id": path.name, "run": str(root), "plan_id": state["plan"]["id"],
            "worker": path.name, "reviewer": Path(reviewer["task"]).name, "cwd": cwd,
            "scope": owned, "contract": contract, "contract_digest": fp.digest(contract),
            "status": "IMPLEMENTING", "candidate": None, "pass": None, "collected": None,
            "pending": None, "native_capability": capability}
    with fp.transaction(run):
        fp.atomic(record, pair)
        for item in (worker, reviewer):
            target = Path(item["task"])
            task = fp.read(target / "task.json")
            task["pair"] = str(record)
            packet(target, task, pair, "Implement the contract." if target == path else
                   "Bootstrap only: no candidate yet. begin returns waiting; end this turn until your peer resumes you.")
            item.update(packet=task["packet"])
    return {"pair": str(record), "worker": worker, "reviewer": reviewer,
            "note": "Launch/bind Reviewer first, then Worker. Real-host support is not established by this record."}


def begin(task_path: str, request_id: str) -> dict:
    with edit(task_path) as (_, pair, _, state):
        path, task, side = actor(task_path, request_id, pair, state)
        fp.require(not pair["collected"], "This task was collected; create a bounded follow-up pair for new work.")
        if side == "reviewer" and pair["status"] in ("IMPLEMENTING", "BLOCKED", "ESCALATE") and pair["candidate"] is None:
            return {"waiting": True, "note": "End this bootstrap turn; do not poll or review without a candidate."}
        expected = ("REVIEW", "PASS") if side == "reviewer" else ("IMPLEMENTING", "FIX_REQUIRED", "PASS")
        fp.require(pair["status"] in expected, "It is not your turn; ask Main to resume a blocked pair.")
        pair.update(status="REVIEW" if side == "reviewer" else "IMPLEMENTING", **{"pass": None})
        if side == "worker":
            pair["candidate"] = None
        pending = pair["pending"]
        if pending and pending["to"] == task["id"] and pending["request_id"] == request_id:
            pair["pending"] = None
        write_result(path, task, "working", "")
        return {"working": True, "candidate": (pair["candidate"] or {}).get("digest"),
                "contract_digest": pair["contract_digest"]}


def submit(task_path: str, request_id: str, kind: str, file: str, candidate: str | None = None) -> dict:
    report = fp.text(file)
    with edit(task_path) as (_, pair, _, state):
        path, task, side = actor(task_path, request_id, pair, state)
        fp.require(not pair["collected"], "The completed pair is sealed; create a follow-up task.")
        fp.require(kind in KINDS, "Unknown pair message.")
        if kind in ("blocked", "escalate"):
            fp.require(pair["status"] not in ("PASS", "BLOCKED", "ESCALATE"), "Pair already returned a terminal result.")
            pair.update(status=kind.upper(), **{"pass": None})
            write_result(path, task, "blocked", report, pair_kind=kind)
            return {"status": pair["status"], "notify_main": True}
        current = fp.current_result(path, task)
        fp.require(current and current["status"] == "working", "Call begin before work; this turn was already submitted or not started.")
        if kind == "candidate":
            fp.require(side == "worker" and pair["status"] == "IMPLEMENTING", "Only the assigned implementer submits candidates.")
            manifest = snapshot(pair)
            target = path / f"{request_id}.candidate.json"
            fp.atomic(target, manifest)
            pair["candidate"] = {"digest": fp.digest(manifest), "manifest": str(target),
                                 "head": fp.git(pair["cwd"], "rev-parse", "HEAD")}
            result = write_result(path, task, "complete", report, pair_kind=kind, candidate=pair["candidate"]["digest"])
            pair.update(status="REVIEW", **{"pass": None})
            peer = members(pair)[1]
        else:
            fp.require(side == "reviewer" and pair["status"] == "REVIEW", "Only the assigned Reviewer can return findings/PASS.")
            fp.require(candidate and candidate == (pair["candidate"] or {}).get("digest"), "Review must name the current candidate digest.")
            if kind == "pass":
                fp.require(candidate == fp.digest(snapshot(pair)), "Candidate changed during review; return findings requesting a new candidate.")
            result = write_result(path, task, "complete", report, pair_kind=kind, candidate=candidate)
            if kind == "pass":
                worker_path = members(pair)[0]
                worker_task = fp.read(worker_path / "task.json")
                pair.update(status="PASS", pending=None)
                pair["pass"] = {"contract_digest": pair["contract_digest"], "candidate_digest": candidate,
                                "reviewer": task["id"], "reviewer_handle": fp.digest(task["handle"]),
                                "reviewer_report": fp.digest(result),
                                "worker_report": fp.digest(fp.current_result(worker_path, worker_task))}
                return {"status": "PASS", "notify_main": True, "pass": pair["pass"]}
            pair.update(status="FIX_REQUIRED", **{"pass": None})
            peer = members(pair)[0]
        message = (f"Peer report: {path / (request_id + '.result.json')}\n"
                   f"Candidate: {json.dumps(pair['candidate'])}\n"
                   "Resolve only this task's concrete findings; use stable IDs, smallest fixes and focused verification.")
        turn(pair, peer, message, task)
    return deliver(task_path, request_id)


def deliver(task_path: str, request_id: str) -> dict:
    record, pair, _, state = at(task_path)
    actor(task_path, request_id, pair, state)
    pending = pair["pending"]
    fp.require(pending and pending["from"] == Path(task_path).resolve().name
               and pending["from_request"] == request_id, "No pending handoff owned by this turn.")
    if state["backend"] == "herdr":
        import herdr as hd
        return hd.deliver_pair(task_path, request_id)
    peer = fp.read(record.parent.parent / pending["to"] / "task.json")
    fp.require(peer.get("handle") and peer["handle"].get("thread_id"), "Peer is not bound with observed native identity.")
    return {"native_call_required": True, "agent_id": peer["handle"]["agent_id"],
            "packet": pending["packet"], "request_id": pending["request_id"],
            "note": "Child must call its actual native peer-resume tool. Nothing was delivered by Python; Main must not relay."}


def valid_pass(pair: dict, *, live: bool = False) -> dict:
    verdict, candidate = pair.get("pass"), pair.get("candidate")
    fp.require(pair["status"] == "PASS" and verdict and candidate, "Every implementation task requires its latest Reviewer PASS.")
    fp.require(verdict["contract_digest"] == pair["contract_digest"] == fp.digest(pair["contract"])
               and verdict["candidate_digest"] == candidate["digest"] == fp.digest(fp.read(candidate["manifest"])),
               "Stale PASS: contract or candidate version changed.")
    worker_path, reviewer_path = members(pair)
    worker, reviewer = fp.read(worker_path / "task.json"), fp.read(reviewer_path / "task.json")
    fp.require((pair["collected"] or (not worker.get("lost") and not reviewer.get("lost")))
               and verdict["reviewer"] == reviewer["id"]
               and verdict["reviewer_handle"] == fp.digest(reviewer["handle"]), "Stale PASS: assigned session changed.")
    worker_result = fp.current_result(worker_path, worker)
    reviewer_result = fp.current_result(reviewer_path, reviewer)
    fp.require(worker_result and reviewer_result and worker_result["status"] == reviewer_result["status"] == "complete"
               and worker_result.get("pair_kind") == "candidate" and reviewer_result.get("pair_kind") == "pass"
               and worker_result.get("candidate") == reviewer_result.get("candidate") == candidate["digest"]
               and verdict["worker_report"] == fp.digest(worker_result)
               and verdict["reviewer_report"] == fp.digest(reviewer_result),
               "Stale PASS: current reports changed.")
    if live or not pair["collected"]:
        fp.require(candidate["digest"] == fp.digest(snapshot(pair)), "Candidate changed after review; a new review is required.")
    return verdict


def require_collected(task_path: str | Path, *, live: bool = False) -> None:
    _, pair, _, _ = at(task_path)
    verdict = valid_pass(pair, live=live)
    fp.require(pair["collected"] == fp.digest(verdict), "Main must collect the completed pair before closing/finishing.")
    for path in members(pair):
        fp.collected(path, fp.read(path / "task.json"))


def collect(task_path: str) -> dict:
    with edit(task_path) as (record, pair, _, state):
        fp.main_only(state)
        fp.require(pair["status"] in TERMINAL, "Ordinary review belongs to the pair; wait for PASS or an escalation.")
        if pair["status"] != "PASS":
            reports = []
            for path in members(pair):
                task = fp.read(path / "task.json")
                result = fp.current_result(path, task)
                if result and result["status"] in ("complete", "blocked") and not fp.ended(task):
                    if state["backend"] == "herdr":
                        from herdr import collect as collect_task
                    else:
                        collect_task = fp.collect
                    reports.append(collect_task(str(path)))
            return {"status": pair["status"], "pair": str(record), "reports": reports,
                    "note": "Not completed. Main resolves scope/environment/capability, then resumes or replaces; do not close unresolved work."}
        verdict = valid_pass(pair, live=True)
        for path in members(pair):
            if state["backend"] == "herdr":
                from herdr import collect as collect_task
            else:
                collect_task = fp.collect
            collect_task(str(path))
        valid_pass(pair, live=True)
        pair["collected"] = fp.digest(verdict)
        return {"status": "PASS", "pair": str(record), "candidate": pair["candidate"], "cwd": pair["cwd"],
                "tasks": [str(p) for p in members(pair)], "note": "Collected exact reviewed candidate. Main closes both idle sessions now; later edits need a follow-up pair."}


def require_all_complete(root: Path, state: dict) -> None:
    seen = set()
    for path, task in fp.tasks(root):
        if task["role"] not in fp.EXECUTORS or task.get("plan_id") != state["plan"]["id"]:
            continue
        fp.require(task.get("pair"), "Unpaired executor: register implementation and Reviewer together with pairs.py create.")
        if task["pair"] not in seen:
            require_collected(path)
            seen.add(task["pair"])
    fp.require(seen, "No reviewed execution pair for this Plan.")


def status(task_path: str) -> dict:
    record, pair, _, state = at(task_path)
    path, task, _, _ = fp.task_at(task_path)
    if fp.thread_id() == state["main_thread_id"] or os.environ.get("FRONTIERPLAN_ROLE") not in fp.CHILDREN and state["backend"] == "herdr":
        fp.main_only(state)
    else:
        actor(str(path), task["request_id"], pair, state)
    return {"pair": str(record), **pair}


def resume(task_path: str, file: str, contract_file: str | None = None) -> dict:
    """Main resolves a blocker, not ordinary findings. No new approval layer."""
    message = fp.text(file)
    with edit(task_path) as (_, pair, _, state):
        fp.main_only(state)
        fp.require(state["phase"] == "executing", "Start the current Plan before resuming execution.")
        changed_plan = pair["plan_id"] != state["plan"]["id"]
        fp.require(not changed_plan or contract_file, "A revised Plan needs an explicit updated Task Contract.")
        stale_candidate = (pair["status"] == "PASS" and not pair["collected"]
                           and pair["candidate"]["digest"] != fp.digest(snapshot(pair)))
        fp.require(pair["status"] in ("BLOCKED", "ESCALATE") or stale_candidate,
                   "Main intervenes only for a stopped pair or a candidate changed before collection.")
        for path in members(pair):
            task = fp.read(path / "task.json")
            fp.require(not fp.ended(task), "Replace a lost session before resuming.")
            if state["backend"] == "herdr":
                import herdr as hd
                fp.require(hd.ready(hd.live(task, hd.Herdr(state).agents())), "Wait until both participants are idle.")
        if changed_plan:
            pair["plan_id"] = state["plan"]["id"]
            for path in members(pair):
                task = fp.read(path / "task.json")
                task["plan_id"] = pair["plan_id"]
                fp.atomic(path / "task.json", task)
        if contract_file:
            pair["contract"] = fp.text(contract_file)
            pair["contract_digest"] = fp.digest(pair["contract"])
        pair.update(status="IMPLEMENTING", candidate=None, collected=None, pending=None, **{"pass": None})
        pending = turn(pair, members(pair)[0], "Main's blocker resolution (not ordinary review adjudication):\n" + message)
        return {"task": str(members(pair)[0]), "packet": pending["packet"],
                "note": "Main sends this one exception follow-up through the actual backend; ordinary review remains peer-to-peer."}


def replace(task_path: str, file: str) -> dict:
    """Main replaces one lost/stopped session, preserving the pair's evidence."""
    evidence = fp.text(file)
    record, pair, root, state = at(task_path)
    fp.main_only(state)
    old_path, old, _, _ = fp.task_at(task_path)
    side = "reviewer" if old["role"] == "reviewer" else "worker"
    fp.require(pair[side] == old["id"] and not pair["collected"], "Cannot replace a completed or superseded participant.")
    fp.require(old.get("lost") or pair["status"] in ("BLOCKED", "ESCALATE"), "Only lost/stopped participants need replacement.")
    if not old.get("lost"):
        fp.collected(old_path, old, complete=False)
        if state["backend"] == "herdr":
            import herdr as hd
            hd.safe_collected(old_path, old, state, hd.Herdr(state), complete=False)
    new = fp.prepare(str(root), old["role"], material=pair["contract"], cwd=pair["cwd"])
    with edit(task_path) as (_, pair, _, state):
        fp.main_only(state)
        fp.require(pair[side] == old["id"], "The participant was already replaced.")
        target = Path(new["task"])
        task = fp.read(target / "task.json")
        task["pair"] = str(record)
        old["replaced_by"] = task["id"]
        fp.atomic(old_path / "task.json", old)
        pair[side] = task["id"]
        pair.update(pending=None, collected=None, **{"pass": None})
        if side == "worker":
            pair.update(status="IMPLEMENTING", candidate=None)
        else:
            worker_path = members(pair)[0]
            result = fp.current_result(worker_path, fp.read(worker_path / "task.json"))
            if pair["candidate"] and result and result.get("pair_kind") == "candidate" and result["status"] == "complete":
                pair["status"] = "REVIEW"
            else:
                pair["candidate"] = None
                pair["status"] = "BLOCKED"  # Main resumes the existing Worker after binding the replacement.
        packet(target, task, pair, f"Replacement reason/evidence:\n{evidence}\n"
               f"Earlier reports/findings: {old_path}\nCurrent candidate: {json.dumps(pair['candidate'])}\n"
               "Continue the same bounded contract, stable findings and existing verification. Do not restart broad review.")
        new["packet"] = task["packet"]
    return dict(new, replaced_task=str(old_path), note="Main launches/binds this same-profile replacement. Close the superseded idle session only after capturing its reports; never close a reused/lost terminal.")


def cli() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="action", required=True)
    q = sub.add_parser("create"); q.add_argument("--run", required=True); q.add_argument("--file", required=True)
    q.add_argument("--cwd"); q.add_argument("--scope", action="append"); q.add_argument("--role", choices=("worker", "design"), default="worker"); q.add_argument("--capability-file")
    for name in ("begin", "submit", "deliver"):
        q = sub.add_parser(name); q.add_argument("--task", required=True); q.add_argument("--request-id", required=True)
        if name == "submit":
            q.add_argument("--kind", choices=KINDS, required=True); q.add_argument("--file", required=True); q.add_argument("--candidate")
    for name in ("collect", "status", "resume", "replace"):
        q = sub.add_parser(name); q.add_argument("--task", required=True)
        if name in ("resume", "replace"): q.add_argument("--file", required=True)
        if name == "resume": q.add_argument("--contract-file")
    a = parser.parse_args()
    if a.action == "create": result = create(a.run, a.file, a.cwd, a.scope, a.role, a.capability_file)
    elif a.action == "begin": result = begin(a.task, a.request_id)
    elif a.action == "submit": result = submit(a.task, a.request_id, a.kind, a.file, a.candidate)
    elif a.action == "deliver": result = deliver(a.task, a.request_id)
    elif a.action == "resume": result = resume(a.task, a.file, a.contract_file)
    elif a.action == "replace": result = replace(a.task, a.file)
    else: result = {"collect": collect, "status": status}[a.action](a.task)
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    sys.modules["pairs"] = sys.modules[__name__]
    try:
        cli()
    except (fp.Failure, OSError, ValueError, KeyError, subprocess.TimeoutExpired) as exc:
        print(json.dumps({"error": str(exc)}, ensure_ascii=False), file=sys.stderr)
        sys.exit(1)
