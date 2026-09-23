#!/usr/bin/env python3
"""Visible FrontierPlan transport. No hidden-agent or model fallback.

Identity, no-focus splitting, and report/activity checks adapted from
phni3j9a/axiom_for_herdr (MIT); see THIRD_PARTY_NOTICES.md.
"""
from __future__ import annotations

import argparse
from contextlib import ExitStack
import json
import math
import os
from pathlib import Path
import shutil
import subprocess
import struct
import sys
import time

import frontierplan as fp


class Herdr:
    def __init__(self, state: dict | None = None, socket: str | None = None):
        binding = (state or {}).get("herdr", {})
        self.binary = binding.get("binary") or os.environ.get("HERDR_BIN_PATH") or shutil.which("herdr")
        fp.require(self.binary, "herdr is not on PATH on this host.")
        self.env = os.environ.copy()
        if state is not None:
            self.env.pop("HERDR_SOCKET_PATH", None)
            socket = binding.get("socket")
        if socket:
            self.env["HERDR_SOCKET_PATH"] = socket

    def call(self, *args: str) -> dict:
        try:
            result = subprocess.run([self.binary, *map(str, args)], env=self.env,
                                    capture_output=True, text=True, timeout=45, check=False)
        except subprocess.TimeoutExpired as exc:
            raise fp.Failure("herdr timed out; delivery may have occurred. Inspect before retrying.") from exc
        fp.require(result.returncode == 0, (result.stderr or result.stdout)[-3000:])
        value = json.loads(result.stdout)
        fp.require("result" in value and "error" not in value, f"Unexpected herdr response: {value}")
        return value["result"]

    def agents(self) -> dict:
        return {a["name"]: a for a in self.call("agent", "list")["agents"] if a.get("name")}


def session_id(pane: dict) -> str | None:
    values = []
    for key in ("agent_session", "agent_session_id", "session_id", "thread_id"):
        value = pane.get(key)
        candidates = (value.get("value"), value.get("id")) if isinstance(value, dict) else (value,)
        for item in candidates:
            if item is None or item == "":
                continue
            fp.require(isinstance(item, str) and item.strip(), "Invalid Main session metadata.")
            values.append(item)
    fp.require(len(set(values)) <= 1, "Contradictory live Main session IDs.")
    return values[0] if values else None


def agent_kind(pane: dict) -> str:
    value = pane.get("agent")
    fp.require(isinstance(value, str) and value.strip().lower() not in ("", "none", "unknown", "shell"),
               "herdr must identify Main's agent kind; do not guess an unrecognized terminal.")
    return value.strip().lower()


def caller_identity() -> dict | None:
    """Explicit provider-neutral identity, or the existing Codex environment."""
    agent = os.environ.get("FRONTIERPLAN_MAIN_AGENT", "").strip().lower()
    session = os.environ.get("FRONTIERPLAN_MAIN_SESSION_ID", "").strip()
    fp.require(bool(agent) == bool(session),
               "Set both FRONTIERPLAN_MAIN_AGENT and FRONTIERPLAN_MAIN_SESSION_ID, or neither.")
    codex = fp.thread_id()
    if agent:
        fp.require(not codex or (agent == "codex" and session == codex),
                   "Explicit Main identity contradicts the Codex environment; inspect inherited IDs.")
        return {"agent": agent, "session_id": session}
    return {"agent": "codex", "session_id": codex} if codex else None


def current_pane(api: Herdr) -> dict:
    expected = os.environ.get("HERDR_PANE_ID")
    fp.require(expected, "No current Main identity. Supply verified FRONTIERPLAN_MAIN_AGENT and "
               "FRONTIERPLAN_MAIN_SESSION_ID for every Main helper command; never guess from focus/cwd.")
    pane = api.call("pane", "current", "--current")["pane"]
    fp.require(pane.get("pane_id") == expected and pane.get("terminal_id"),
               "Current pane does not match HERDR_PANE_ID; inspect the host/socket binding.")
    return pane


def validate_session(pane: dict, expected: str, agent: str = "codex", *,
                     require_session: bool = False) -> None:
    fp.require(agent_kind(pane) == agent, "Main's agent kind does not match the live pane.")
    observed = session_id(pane)
    fp.require(not require_session or observed, "Main's live session ID is missing; inspect before continuing.")
    fp.require(not observed or observed == expected, "Main's conversation does not match the live pane.")


def main_pane(state: dict, api: Herdr) -> dict:
    fp.require(os.environ.get("FRONTIERPLAN_ROLE") not in fp.CHILDREN, "Only Main manages this run.")
    fp.require(state["backend"] == "herdr" and state.get("herdr"), "This is not a bound herdr run.")
    terminal = state["herdr"]["main_terminal_id"]
    matches = [p for p in api.call("pane", "list")["panes"] if p.get("terminal_id") == terminal]
    fp.require(len(matches) == 1, "Main's original terminal is missing or ambiguous; no pane changed.")
    pane = matches[0]
    if "main_identity" not in state:
        fp.main_only(state)  # Legacy Codex run; no recursive live-identity branch.
        validate_session(pane, state["main_thread_id"])
        return pane
    expected = state["main_identity"]
    validate_session(pane, expected["session_id"], expected["agent"],
                     require_session=state["herdr"].get("session_verified", False))
    caller = caller_identity()
    if caller is not None:
        fp.require(caller == expected, "This run belongs to a different Main agent/conversation.")
    else:
        current = current_pane(api)
        fp.require(current.get("terminal_id") == terminal and current.get("pane_id") == pane.get("pane_id"),
                   "The calling pane is not Main's original terminal; no pane changed.")
        validate_session(current, expected["session_id"], expected["agent"], require_session=True)
    return pane  # Follow terminal identity, not focus, cwd or a reused pane ID.


def initialize(cwd: str, request_file: str, pane_id: str | None = None,
               terminal_id: str | None = None, socket: str | None = None) -> dict:
    fp.require(os.environ.get("FRONTIERPLAN_ROLE") not in fp.CHILDREN, "Children cannot initialize runs.")
    fp.require(bool(pane_id) == bool(terminal_id), "Supply both Main pane and terminal IDs.")
    identity = caller_identity()
    api = Herdr(socket=socket)
    if pane_id:
        pane = api.call("pane", "get", pane_id)["pane"]
        fp.require(pane.get("pane_id") == pane_id and pane.get("terminal_id") == terminal_id,
                   "The selected Main pane/terminal does not match.")
        if identity is None:
            current = current_pane(api)
            fp.require(current.get("terminal_id") == terminal_id and current.get("pane_id") == pane_id,
                       "Explicit pane IDs alone do not establish the calling Main's identity.")
    else:
        pane = current_pane(api)
    if identity is None:
        observed = session_id(pane)
        fp.require(observed, "herdr does not expose Main's session ID. Verify it externally and set "
                   "FRONTIERPLAN_MAIN_AGENT plus FRONTIERPLAN_MAIN_SESSION_ID; do not invent an ID.")
        identity = {"agent": agent_kind(pane), "session_id": observed}
    validate_session(pane, identity["session_id"], identity["agent"])
    binding = {"binary": str(api.binary), "socket": api.env.get("HERDR_SOCKET_PATH"),
               "main_pane_id": pane["pane_id"], "main_terminal_id": pane["terminal_id"],
               "session_verified": session_id(pane) is not None}
    value = fp.initialize("herdr", cwd, request_file, main_identity=identity, herdr_binding=binding)
    return {"run": value["run"], "main_pane": pane["pane_id"], "main_identity": identity}


def live(task: dict, agents: dict) -> dict:
    handle = task.get("handle") or {}
    agent = agents.get(task["name"])
    fp.require(agent and agent.get("terminal_id") == handle.get("terminal_id")
               and str(agent.get("agent", "")).lower() == "codex",
               "The original Codex session is unavailable; inspect recorded handles, do not guess.")
    return agent


def ready(agent: dict) -> bool:
    return agent.get("agent_status") in ("idle", "done") and not agent.get("launch_pending", False)


def owned_pane(task: dict, state: dict, api: Herdr) -> dict:
    """Resolve the original terminal, then verify the actual pane occupant too."""
    fp.require(task["role"] in fp.CHILDREN, "Never manage Main as a participant.")
    agent = live(task, api.agents())
    terminal = agent["terminal_id"]
    fp.require(terminal != state["herdr"]["main_terminal_id"], "Never close or split Main as a child.")
    panes = [p for p in api.call("pane", "list")["panes"] if p.get("terminal_id") == terminal]
    fp.require(len(panes) == 1 and panes[0]["pane_id"] == agent.get("pane_id"),
               "Participant terminal is missing, moved inconsistently or ambiguous.")
    pane = api.call("pane", "get", agent["pane_id"])["pane"]
    fp.require(pane.get("pane_id") == agent["pane_id"] and pane.get("terminal_id") == terminal
               and str(pane.get("agent", "")).lower() == "codex",
               "Pane occupant changed; no pane modified.")
    return agent


def safe_collected(path: Path, task: dict, state: dict, api: Herdr) -> dict:
    result = fp.collected(path, task)
    receipt = fp.read(path / "receipt.json")
    agent = owned_pane(task, state, api)
    fp.require(ready(agent) and receipt.get("state_change_seq") is not None
               and receipt.get("terminal_id") == agent["terminal_id"]
               and agent.get("state_change_seq") == receipt["state_change_seq"],
               "Agent activity changed after collection; keep the pane open.")
    fp.require(fp.digest(fp.current_result(path, task)) == fp.digest(result), "Report changed during inspection.")
    return agent


def contains(outer: dict, inner: dict) -> bool:
    return (inner["width"] > 0 and inner["height"] > 0
            and outer["x"] <= inner["x"] and outer["y"] <= inner["y"]
            and inner["x"] + inner["width"] <= outer["x"] + outer["width"]
            and inner["y"] + inner["height"] <= outer["y"] + outer["height"])


def split_regions(split: dict) -> tuple[dict, dict]:
    """Herdr ratios apply to the first child; pane rects may be inset by chrome."""
    first, second = dict(split["rect"]), dict(split["rect"])
    fp.require(split["direction"] in ("right", "down"), "Unknown layout split direction.")
    size, position = ("width", "x") if split["direction"] == "right" else ("height", "y")
    # Match Herdr's positive f32 multiplication/rounding, including odd dimensions.
    f32 = lambda value: struct.unpack("f", struct.pack("f", value))[0]
    ratio = split["ratio"]
    fp.require(math.isfinite(ratio) and 0 < ratio < 1, "Invalid layout split ratio.")
    first[size] = math.floor(f32(f32(first[size]) * f32(ratio)) + 0.5)
    second[size] -= first[size]
    second[position] += first[size]
    return first, second


def spawn_target(root: Path, state: dict, task: dict, api: Herdr) -> tuple[str, str, str, dict]:
    main = main_pane(state, api)
    layout = api.call("pane", "layout", "--pane", main["pane_id"])["layout"]
    fp.require(layout.get("workspace_id") and layout.get("tab_id") and not layout.get("zoomed"),
               "An unzoomed, identifiable layout is required before splitting.")
    panes = {p["pane_id"]: p["rect"] for p in layout["panes"]}
    fp.require(len(panes) == len(layout["panes"]) and main["pane_id"] in panes,
               "Main layout is missing or ambiguous.")
    fp.require(all(contains(layout["area"], rect) for rect in panes.values()),
               "Layout has empty/outside pane geometry; enlarge or inspect it before splitting.")
    binding = state["herdr"].get("layout")
    if task["role"] == "director":
        fp.require(not binding, "Director layout already exists; inspect it before recovering a lost Director.")
        binding = {"workspace_id": layout["workspace_id"], "tab_id": layout["tab_id"],
                   "director_task": task["id"]}
        return main["pane_id"], "right", "0.4", binding
    fp.require(binding and all(layout[k] == binding[k] for k in ("workspace_id", "tab_id")),
               "The saved Director layout cannot be identified; no split performed.")
    owned, director = set(), None
    for _, other in fp.tasks(root):
        if other["id"] == task["id"] or other.get("released") or other.get("closed") or other.get("lost"):
            continue
        fp.require(other.get("handle") and not other.get("closing"), "Resolve the partially started/closing participant first.")
        agent = owned_pane(other, state, api)
        fp.require(agent["pane_id"] in panes and agent["pane_id"] not in owned,
                   "Owned participant moved outside the execution layout or shares a pane.")
        owned.add(agent["pane_id"])
        if other["id"] == binding["director_task"] and other["role"] == "director":
            director = agent["pane_id"]
    fp.require(director, "The original Director anchor is unavailable.")
    members = lambda rect: {key for key, pane in panes.items() if contains(rect, pane)}
    regions = []
    for split in layout.get("splits", []):
        if split["direction"] != "right":
            continue
        left, right = split_regions(split)
        if members(left) == {main["pane_id"]} and members(right) == owned:
            regions.append(right)
    fp.require(len(regions) == 1, "Main/Director region changed; do not guess or rebalance user panes.")
    execution = owned - {director}
    if not execution:
        return director, "down", "0.4", binding
    lower = []
    for split in layout.get("splits", []):
        if split["direction"] == "down" and split["rect"] == regions[0]:
            upper, bottom = split_regions(split)
            if members(upper) == {director} and members(bottom) == execution:
                lower.append(bottom)
    fp.require(len(lower) == 1, "Execution region changed; no split performed.")
    # Largest width, then position/ID for deterministic ties. Never split Astra again
    # while execution participants remain, and never rebalance existing ratios.
    target = min(execution, key=lambda key: (-panes[key]["width"], panes[key]["x"], key))
    return target, "right", "0.5", binding


def codex_args(task: dict, root: Path, pane: dict, api: Herdr) -> list[str]:
    p = task["profile"]
    args = ["-C", task["cwd"], "-m", p["model"], "-c", f'model_reasoning_effort="{p["reasoning_effort"]}"',
            "-c", 'default_permissions=":workspace"']
    if p.get("service_tier") == "fast":
        args += ["-c", 'service_tier="fast"', "-c", "features.fast_mode=true"]
    env = {"FRONTIERPLAN_ROLE": task["role"], "FRONTIERPLAN_TASK": str(root / "tasks" / task["id"]),
           "HERDR_PANE_ID": pane["pane_id"], "HERDR_BIN_PATH": str(api.binary),
           "FRONTIERPLAN_MAIN_AGENT": "", "FRONTIERPLAN_MAIN_SESSION_ID": ""}
    if api.env.get("HERDR_SOCKET_PATH"):
        env["HERDR_SOCKET_PATH"] = api.env["HERDR_SOCKET_PATH"]
    for key, value in env.items():
        args += ["-c", f"shell_environment_policy.set.{key}={json.dumps(value)}"]
    return args + ["--sandbox", "workspace-write", "--ask-for-approval", "never",
                   "--add-dir", str(root), "--no-alt-screen"]


def deliver(path: Path, task: dict, api: Herdr) -> None:
    fp.require(ready(live(task, api.agents())), "Agent must be idle before delivery.")
    task.update(delivery="uncertain", submitted_at=time.time())
    fp.atomic(path / "task.json", task)
    api.call("agent", "prompt", task["name"], f"Read {task['packet']} and perform its assignment and return protocol.")
    task["delivery"] = "sent"
    fp.atomic(path / "task.json", task)


def spawn(run: str, role: str, file: str, cwd: str | None = None) -> dict:
    root, state = fp.run_at(run)
    api = Herdr(state)
    main_pane(state, api)
    value = fp.prepare(run, role, file, cwd)
    path, task, _, _ = fp.task_at(value["task"])
    # Persist and expose the task before any terminal mutation for partial-failure recovery.
    print(json.dumps({"prepared_task": str(path), "name": task["name"]}), flush=True)
    with fp.transaction(root) as (_, state):
        target_id, direction, ratio, binding = spawn_target(root, state, task, api)
        pane = api.call("pane", "split", target_id, "--direction", direction, "--ratio", ratio,
                        "--cwd", task["cwd"], "--no-focus", "--env", f"FRONTIERPLAN_ROLE={role}",
                        "--env", f"FRONTIERPLAN_TASK={path}", "--env", "FRONTIERPLAN_MAIN_AGENT=",
                        "--env", "FRONTIERPLAN_MAIN_SESSION_ID=")["pane"]
        task["handle"] = {"pane_id": pane["pane_id"], "terminal_id": pane["terminal_id"]}
        task["delivery"] = "starting"
        fp.atomic(path / "task.json", task)
        state["herdr"]["layout"] = binding
    args = codex_args(task, root, pane, api)
    task["requested_codex_args"] = args
    fp.atomic(path / "task.json", task)
    api.call("pane", "rename", pane["pane_id"], f"FrontierPlan · {role}")
    started = api.call("agent", "start", task["name"], "--kind", "codex", "--pane", pane["pane_id"],
                       "--timeout", "30000", "--", *args)
    task["launched_argv"] = started.get("argv")
    fp.atomic(path / "task.json", task)
    deliver(path, task, api)
    return {"task": str(path), "handle": task["handle"], "delivery": task["delivery"]}


def send(task_path: str, file: str) -> dict:
    path, task, root, state = fp.task_at(task_path)
    api = Herdr(state)
    main_pane(state, api)
    fp.require(ready(live(task, api.agents())), "Wait for the existing session to become idle.")
    fp.prepare(str(root), task["role"], file, reuse=str(path))
    task = fp.read(path / "task.json")
    deliver(path, task, api)
    return {"task": str(path), "request_id": task["request_id"], "delivery": task["delivery"]}


def collect(task_path: str) -> dict:
    path, task, _, state = fp.task_at(task_path)
    api = Herdr(state)
    main_pane(state, api)
    fp.require(not task.get("released") and not task.get("closing"), "Participant is released or closing.")
    agent = live(task, api.agents())
    fp.require(ready(agent), "Wait until the agent is idle before collection.")
    fp.require("state_change_seq" in agent, "herdr lacks activity sequence evidence; cannot collect safely.")
    result = fp.collect(task_path)
    receipt = fp.read(path / "receipt.json")
    receipt.update(state_change_seq=agent["state_change_seq"], terminal_id=agent["terminal_id"])
    fp.atomic(path / "receipt.json", receipt)
    return result


def release_binding(path: Path, task: dict, state: dict, reviewer_path: str, api: Herdr) -> tuple[dict, dict]:
    fp.require(task["role"] in ("worker", "design"), "Only Worker/Design uses a release decision.")
    fp.require(state["phase"] in ("executing", "acceptance", "accepted")
               and not state["awaiting_director"] and state.get("plan"), "Reconcile the current Plan/input before release.")
    review_path, reviewer, review_root, _ = fp.task_at(reviewer_path)
    fp.require(review_root == path.parent.parent and reviewer["role"] == "reviewer"
               and not any(reviewer.get(k) for k in ("lost", "closed", "released", "closing")),
               "Use a retained independent Reviewer from this run.")
    for p, t in ((path, task), (review_path, reviewer)):
        fp.require(not any(t.get(k) for k in ("lost", "closed", "released", "closing")), "Participant is unavailable.")
        safe_collected(p, t, state, api)
        fp.require(t.get("plan_id") == state["plan"]["id"], "Release requires the current Plan.")
    report = fp.collected(review_path, reviewer)
    candidate = fp.snapshot(state["cwd"])["id"]
    fp.require(report.get("reviewed_snapshot") == candidate, "Re-review the current candidate before release.")
    binding = {"task_id": task["id"], "request_id": task["request_id"],
               "result_digest": fp.digest(fp.collected(path, task)),
               "receipt_digest": fp.digest(fp.read(path / "receipt.json")),
               "candidate_id": candidate, "plan_id": state["plan"]["id"], "user_seq": state["user_seq"],
               "reviewer": {"task_id": reviewer["id"], "request_id": reviewer["request_id"],
                            "result_digest": fp.digest(report),
                            "receipt_digest": fp.digest(fp.read(review_path / "receipt.json"))}}
    return binding, report


def release_check(task_path: str, reviewer_path: str | None = None) -> dict:
    """Read-only template. Main must supply the substantive disposition explicitly."""
    path, task, _, state = fp.task_at(task_path)
    api = Herdr(state)
    main_pane(state, api)
    if reviewer_path is None:
        safe_collected(path, task, state, api)
        return fp.assignment_release_check(task_path)
    binding, _ = release_binding(path, task, state, reviewer_path, api)
    return {"binding": binding, "decision": {"integrated": False, "unresolved_findings": [],
            "no_longer_needed": False, "reason": ""}}


def shutdown(task_path: str, operation: str, file: str | None = None) -> dict:
    path, _, root, _ = fp.task_at(task_path)
    with fp.transaction(root) as (_, state), ExitStack() as locks:
        locks.enter_context(fp.lock(path / ".report.lock"))
        task = fp.read(path / "task.json")
        api = Herdr(state)
        main_pane(state, api)
        fp.require(task["role"] in fp.CHILDREN, "Never close Main.")
        fp.require(not task.get("closing"), "Previous pane close is uncertain; inspect its saved handle before recovery.")
        if operation == "close":
            fp.require(state["phase"] == "closed", "Do not close participants before overall wrap-up.")
            if task.get("closed"):
                return {"closed": True, "already_closed": True}
            if task.get("released"):
                fp.released_evidence(path, task)
                task["closed"] = True
                fp.atomic(path / "task.json", task)
                return {"closed_record": task["id"], "already_released": True}
        else:
            fp.require(state["phase"] != "closed" and task["role"] != "director",
                       "Astra stays until finish; use close for final cleanup.")
            if task.get("released"):
                fp.released_evidence(path, task)
                return {"released": True, "already_released": True}
        fp.require(not task.get("closed") and not task.get("lost"), "Participant is unavailable.")
        release = None
        peer = None
        if operation == "release":
            if task["role"] == "reviewer":
                fp.require(state["phase"] == "accepted" and state.get("acceptance")
                           and not state["awaiting_director"], "Retain Reviewer until Astra accepts the exact candidate.")
                fp.require(fp.snapshot(state["cwd"])["id"] == state["acceptance"]["candidate_id"],
                           "Accepted candidate changed; keep Reviewer for re-review.")
                fp.executors_ready(root, require_review=True, candidate_id=state["candidate"]["id"])
                for p, t in fp.tasks(root):
                    if t["role"] != "director" and not any(t.get(k) for k in ("released", "closed", "lost")):
                        safe_collected(p, t, state, api)
                director_path, director, _, _ = fp.task_at(state["acceptance"]["task"])
                locks.enter_context(fp.lock(director_path / ".report.lock"))
                safe_collected(director_path, director, state, api)
                fp.require(fp.digest(fp.collected(director_path, director)) == state["acceptance"]["result_digest"],
                           "Director acceptance changed.")
                release = {"binding": {"task_id": task["id"], "request_id": task["request_id"],
                           "result_digest": fp.digest(fp.collected(path, task)), "plan_id": state["plan"]["id"],
                           "candidate_id": state["candidate"]["id"]}, "acceptance": state["acceptance"]}
                peer = (director_path, director)
            else:
                fp.require(file, "Worker/Design release requires a release-check template with Main's decision.")
                evidence = fp.read(file)
                binding = evidence.get("binding") or {}
                decision = evidence.get("decision") or {}
                if binding.get("kind") == "assignment":
                    safe_collected(path, task, state, api)
                    fp.require(binding == fp.assignment_release_binding(path, task, state),
                               "Release evidence is stale; collect and obtain a fresh Main decision.")
                    fp.assignment_release_decision(decision)
                    release = {"binding": binding, "decision": decision}
                else:
                    # Keep existing reviewed-release records/commands usable.
                    review_id = binding.get("reviewer", {}).get("task_id", "")
                    fp.require(review_id and any(t["id"] == review_id and t["role"] == "reviewer" for _, t in fp.tasks(root)),
                               "Unknown release Reviewer.")
                    review_path = root / "tasks" / review_id
                    locks.enter_context(fp.lock(review_path / ".report.lock"))
                    current, review = release_binding(path, task, state, str(review_path), api)
                    fp.require(binding == current, "Release evidence is stale; collect/review and obtain a fresh Main decision.")
                    fp.release_decision(decision)
                    release = {"binding": binding, "decision": decision, "review_report": review}
                    peer = (review_path, fp.read(review_path / "task.json"))
        if release:
            fp.require(fp.snapshot(state["cwd"])["id"] == release["binding"]["candidate_id"],
                       "Candidate changed during release; keep the participant.")
        if peer:
            safe_collected(*peer, state, api)
        agent = safe_collected(path, task, state, api)
        # Preserve intent before the external side effect. A timeout/crash must never
        # become an automatic retry against a possibly reused pane ID.
        task["closing"] = {"operation": operation, "pane_id": agent["pane_id"],
                           "terminal_id": agent["terminal_id"], "release": release}
        fp.atomic(path / "task.json", task)
        api.call("pane", "close", agent["pane_id"])
        task.pop("closing")
        if operation == "release":
            task.update(released=True, release=release)
        else:
            task["closed"] = True
        fp.atomic(path / "task.json", task)
        return {"released": True, "task": str(path)} if operation == "release" else {"closed_record": task["id"]}


def release(task_path: str, file: str | None = None) -> dict:
    return shutdown(task_path, "release", file)


def close(task_path: str) -> dict:
    return shutdown(task_path, "close")


def pending_snapshot(root: Path, api: Herdr) -> tuple[dict, dict]:
    """Current conditions, not just newly delivered notifications. No receipt writes."""
    events, marks, pending = [], {}, 0
    agents = api.agents()
    for path, task in fp.tasks(root):
        if task.get("closed") or task.get("lost") or task.get("released"):
            continue
        if task.get("closing"):
            raise fp.Failure("Participant closure is uncertain; inspect the saved closing record.")
        agent = agents.get(task["name"])
        if agent and (agent.get("terminal_id") != (task.get("handle") or {}).get("terminal_id")
                      or agent.get("agent") != "codex"):
            agent = None
        result = fp.current_result(path, task)
        receipt = fp.read(path / "receipt.json") if (path / "receipt.json").exists() else {}
        unchanged = result and receipt.get("digest") == fp.digest(result)
        collected_idle = (unchanged and agent and ready(agent) and "state_change_seq" in agent
                          and agent["state_change_seq"] == receipt.get("state_change_seq")
                          and agent.get("terminal_id") == receipt.get("terminal_id"))
        if collected_idle and result["status"] == "complete":
            continue
        pending += 1
        event = None
        if not agent: event = "unavailable"
        elif agent.get("agent_status") in ("blocked", "unknown"): event = agent["agent_status"]
        elif result and result["status"] in ("complete", "blocked"):
            if not ready(agent): event = "report_waiting_idle"
            elif collected_idle: event = "blocked"
            else: event = "report"
        elif ready(agent) and time.time() - task.get("submitted_at", time.time()) > 8:
            event = "idle_without_report"
        if event:
            events.append({"task": str(path), "event": event})
            marks[str(path)] = fp.digest({"request": task["request_id"], "result": result, "event": event,
                                          "seq": (agent or {}).get("state_change_seq")})
    return {"events": events, "pending": pending}, marks


def check(run: str) -> dict:
    """Read-only reconciliation, also usable while the one waiter is running."""
    root, state = fp.run_at(run)
    api = Herdr(state)
    main_pane(state, api)
    return pending_snapshot(root, api)[0]


def wait(run: str, timeout: int = 300) -> dict:
    fp.require(0 <= timeout <= 300, "Wait timeout must be between 0 and 300 seconds.")
    root, state = fp.run_at(run)
    api = Herdr(state)
    main_pane(state, api)
    deadline = time.monotonic() + timeout
    notice_file = root / "wait-notices.json"
    with fp.lock(root / ".wait.lock"):
        previous = fp.read(notice_file) if notice_file.exists() else {}
        while True:
            snapshot, current = pending_snapshot(root, api)
            # An uncollected (or activity-stale) report must survive a lost wait output.
            wake = any(e["event"] == "report" or previous.get(e["task"]) != current[e["task"]]
                       for e in snapshot["events"])
            if previous != current:
                fp.atomic(notice_file, current)
                previous = current
            if wake or not snapshot["pending"]:
                return snapshot
            if time.monotonic() >= deadline:
                return dict(snapshot, timeout=True)
            time.sleep(min(2, max(0, deadline - time.monotonic())))


def cli() -> None:
    p = argparse.ArgumentParser(description=__doc__)
    sub = p.add_subparsers(dest="action", required=True)
    q = sub.add_parser("init"); q.add_argument("--cwd", default=os.getcwd()); q.add_argument("--request-file", required=True); q.add_argument("--main-pane"); q.add_argument("--main-terminal-id"); q.add_argument("--socket")
    q = sub.add_parser("spawn"); q.add_argument("--run", required=True); q.add_argument("--role", choices=fp.CHILDREN, required=True); q.add_argument("--file", required=True); q.add_argument("--cwd")
    q = sub.add_parser("send"); q.add_argument("--task", required=True); q.add_argument("--file", required=True)
    for name in ("collect", "close"):
        q = sub.add_parser(name); q.add_argument("--task", required=True)
    q = sub.add_parser("release-check"); q.add_argument("--task", required=True); q.add_argument("--reviewer")
    q = sub.add_parser("release"); q.add_argument("--task", required=True); q.add_argument("--file")
    q = sub.add_parser("check"); q.add_argument("--run", required=True)
    q = sub.add_parser("wait"); q.add_argument("--run", required=True); q.add_argument("--timeout", type=int, default=300)
    a = p.parse_args()
    if a.action == "init": result = initialize(a.cwd, a.request_file, a.main_pane, a.main_terminal_id, a.socket)
    elif a.action == "spawn": result = spawn(a.run, a.role, a.file, a.cwd)
    elif a.action == "send": result = send(a.task, a.file)
    elif a.action == "collect": result = collect(a.task)
    elif a.action == "close": result = close(a.task)
    elif a.action == "release-check": result = release_check(a.task, a.reviewer)
    elif a.action == "release": result = release(a.task, a.file)
    elif a.action == "check": result = check(a.run)
    else: result = wait(a.run, a.timeout)
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    sys.modules["herdr"] = sys.modules[__name__]
    try:
        cli()
    except (fp.Failure, OSError, ValueError, KeyError, subprocess.TimeoutExpired) as exc:
        print(json.dumps({"error": str(exc)}, ensure_ascii=False), file=sys.stderr)
        sys.exit(1)
