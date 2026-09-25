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
               terminal_id: str | None = None, socket: str | None = None,
               variant: str = "standard") -> dict:
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
    value = fp.initialize("herdr", cwd, request_file, main_identity=identity, herdr_binding=binding,
                          variant=variant)
    return {"run": value["run"], "main_pane": pane["pane_id"], "main_identity": identity,
            "variant": variant}


def child_agent(task: dict) -> str:
    """The agent kind this participant was launched as; fixed by its profile."""
    return task["profile"].get("agent", "codex")


def live(task: dict, agents: dict) -> dict:
    handle = task.get("handle") or {}
    agent = agents.get(task["name"])
    fp.require(agent and agent.get("terminal_id") == handle.get("terminal_id")
               and str(agent.get("agent", "")).lower() == child_agent(task),
               "The original child session is unavailable; inspect recorded handles, do not guess.")
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
               and str(pane.get("agent", "")).lower() == child_agent(task),
               "Pane occupant changed; no pane modified.")
    return agent


def safe_collected(path: Path, task: dict, state: dict, api: Herdr, complete: bool = True) -> dict:
    result = fp.collected(path, task, complete)
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
        if other["id"] == task["id"] or fp.ended(other):
            continue
        if not other.get("handle") and other.get("delivery") == "prepared":
            continue  # Prepared in the same batch (e.g. researchers); it has no pane yet.
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


def devin_args(task: dict, path: Path) -> list[str]:
    # No OS sandbox: Devin's bypass mode auto-approves every tool (edits, shell, fetch,
    # MCP) with the user's own permissions; see backends/herdr.md.
    return ["--permission-mode", "dangerous", "--model", task["profile"]["model"],
            "--export", str(path / "devin-session.json")]


def devin_evidence(path: Path) -> dict:
    """Models recorded in Devin's own session export; absent evidence is reported as such."""
    export = path / "devin-session.json"
    try:
        value = json.loads(export.read_text(encoding="utf-8"))
        models = sorted({s["model_name"] for s in value.get("steps", [])
                         if s.get("source") == "agent" and s.get("model_name")})
        return {"export": str(export), "session_id": value.get("session_id"), "observed_models": models}
    except (OSError, ValueError, TypeError, AttributeError):
        return {"export": str(export), "observed_models": None, "note": "Session export unavailable."}


def deliver(path: Path, task: dict, api: Herdr) -> None:
    fp.require(ready(live(task, api.agents())), "Agent must be idle before delivery.")
    task.update(delivery="uncertain", submitted_at=time.time())
    fp.atomic(path / "task.json", task)
    api.call("agent", "prompt", task["name"], f"Read {task['packet']} and perform its assignment and return protocol.")
    task["delivery"] = "sent"
    fp.atomic(path / "task.json", task)


def launch(root: Path, path: Path, api: Herdr) -> dict:
    """Split, start and prompt one prepared participant."""
    task = fp.read(path / "task.json")
    fp.require(not task.get("handle") and task.get("delivery") == "prepared",
               "Participant start is uncertain or already done; inspect the recorded task.")
    kind = child_agent(task)
    if kind == "devin":
        # Fail before any pane mutation when the child cannot be launched as profiled.
        fp.require(shutil.which("devin"), "devin is not on PATH on this host; no pane changed.")
        args = devin_args(task, path)
    # Expose the task before any terminal mutation for partial-failure recovery.
    print(json.dumps({"prepared_task": str(path), "name": task["name"]}), flush=True)
    with fp.transaction(root) as (_, state):
        target_id, direction, ratio, binding = spawn_target(root, state, task, api)
        pane = api.call("pane", "split", target_id, "--direction", direction, "--ratio", ratio,
                        "--cwd", task["cwd"], "--no-focus", "--env", f"FRONTIERPLAN_ROLE={task['role']}",
                        "--env", f"FRONTIERPLAN_TASK={path}", "--env", "FRONTIERPLAN_MAIN_AGENT=",
                        "--env", "FRONTIERPLAN_MAIN_SESSION_ID=")["pane"]
        task["handle"] = {"pane_id": pane["pane_id"], "terminal_id": pane["terminal_id"]}
        task["delivery"] = "starting"
        fp.atomic(path / "task.json", task)
        state["herdr"]["layout"] = binding
    if kind == "devin":
        task["requested_devin_args"] = args
    else:
        args = codex_args(task, root, pane, api)
        task["requested_codex_args"] = args
    fp.atomic(path / "task.json", task)
    api.call("pane", "rename", pane["pane_id"], f"FrontierPlan · {task['role']}")
    started = api.call("agent", "start", task["name"], "--kind", kind, "--pane", pane["pane_id"],
                       "--timeout", "30000", "--", *args)
    task["launched_argv"] = started.get("argv")
    fp.atomic(path / "task.json", task)
    deliver(path, task, api)
    return {"task": str(path), "handle": task["handle"], "delivery": task["delivery"]}


def spawn(run: str, role: str, file: str | None = None, cwd: str | None = None) -> dict:
    root, state = fp.run_at(run)
    api = Herdr(state)
    main_pane(state, api)
    fp.require(role != "researcher", "Researchers start only through relay.")
    if role == "director":
        value = fp.start_director(run, file)
    else:
        fp.require(file, "An assignment file is required.")
        value = fp.prepare(run, role, file, cwd)
    return launch(root, Path(value["task"]), api)


def continue_session(path: Path, api: Herdr) -> dict:
    task = fp.read(path / "task.json")
    deliver(path, task, api)
    return {"task": str(path), "request_id": task["request_id"], "delivery": task["delivery"],
            "purpose": task.get("purpose")}


def send(task_path: str, file: str) -> dict:
    """Same-session follow-up for a Worker/Design fix or Reviewer re-review."""
    path, task, root, state = fp.task_at(task_path)
    api = Herdr(state)
    main_pane(state, api)
    fp.require(task["role"] in fp.EXECUTORS, "Use forward, relay, consult or final-check for Astra.")
    fp.require(ready(live(task, api.agents())), "Wait for the existing session to become idle.")
    fp.prepare(str(root), task["role"], file, reuse=str(path))
    return continue_session(path, api)


def director_turn(run: str, prepare) -> dict:
    root, state = fp.run_at(run)
    api = Herdr(state)
    main_pane(state, api)
    path, task = fp.director_task(root)
    fp.require(ready(live(task, api.agents())), "Wait for Astra to become idle.")
    prepare()
    return continue_session(path, api)


def forward(run: str) -> dict:
    return director_turn(run, lambda: fp.forward(run))


def consult(run: str, file: str) -> dict:
    return director_turn(run, lambda: fp.consult(run, file))


def final_check(run: str, file: str) -> dict:
    return director_turn(run, lambda: fp.final_check(run, file))


def relay(run: str) -> dict:
    """Carry Astra's research requests and the unedited reports; no Main judgment."""
    root, state = fp.run_at(run)
    api = Herdr(state)
    main_pane(state, api)
    _, director = fp.director_task(root)
    # Astra must be able to take the reports before the relay marks them returned.
    fp.require(ready(live(director, api.agents())), "Wait for Astra to become idle.")
    step = fp.relay(run)
    if step["action"] == "spawn_researchers":
        return {"action": "spawned", "tasks": [launch(root, Path(t["task"]), api) for t in step["tasks"]]}
    if step["action"] == "wait":
        return step
    director = Path(step["director"]["task"])
    delivered = continue_session(director, api)
    closed = []
    for researcher in step["researchers"]:
        if not fp.ended(fp.task_at(researcher)[1]):
            closed.append(close(researcher))
    return {"action": "returned_to_director", "director": delivered, "closed": closed}


def collect(task_path: str) -> dict:
    path, task, _, state = fp.task_at(task_path)
    api = Herdr(state)
    main_pane(state, api)
    fp.require(not fp.ended(task) and not task.get("closing"), "Participant is closed or closing.")
    agent = live(task, api.agents())
    fp.require(ready(agent), "Wait until the agent is idle before collection.")
    fp.require("state_change_seq" in agent, "herdr lacks activity sequence evidence; cannot collect safely.")
    result = fp.collect(task_path)
    receipt = fp.read(path / "receipt.json")
    receipt.update(state_change_seq=agent["state_change_seq"], terminal_id=agent["terminal_id"])
    if child_agent(task) == "devin":
        evidence = devin_evidence(path)
        receipt["session_evidence"] = evidence
        result = dict(result, session_evidence=evidence, profile_model=task["profile"]["model"])
    fp.atomic(path / "receipt.json", receipt)
    return result


def close(task_path: str) -> dict:
    """End a participant whose lifetime Main has ended; Astra only after finish."""
    path, _, root, _ = fp.task_at(task_path)
    with fp.transaction(root) as (_, state), ExitStack() as locks:
        locks.enter_context(fp.lock(path / ".report.lock"))
        task = fp.read(path / "task.json")
        api = Herdr(state)
        main_pane(state, api)
        if task.get("closed"):
            return {"closed": True, "already_closed": True}
        fp.require(not task.get("closing"), "Previous pane close is uncertain; inspect its saved handle before recovery.")
        fp.closable(path, task, state)
        agent = safe_collected(path, task, state, api, complete=fp.needs_complete(task, state))
        # Preserve intent before the external side effect. A timeout/crash must never
        # become an automatic retry against a possibly reused pane ID.
        task["closing"] = {"pane_id": agent["pane_id"], "terminal_id": agent["terminal_id"]}
        fp.atomic(path / "task.json", task)
        api.call("pane", "close", agent["pane_id"])
        task.pop("closing")
        task["closed"] = True
        fp.atomic(path / "task.json", task)
        return {"closed_record": task["id"]}


def pending_snapshot(root: Path, api: Herdr) -> tuple[dict, dict]:
    """Current conditions, not just newly delivered notifications. No receipt writes."""
    events, marks, pending = [], {}, 0
    agents = api.agents()
    for path, task in fp.tasks(root):
        if fp.ended(task):
            continue
        if task.get("closing"):
            raise fp.Failure("Participant closure is uncertain; inspect the saved closing record.")
        agent = agents.get(task["name"])
        if agent and (agent.get("terminal_id") != (task.get("handle") or {}).get("terminal_id")
                      or str(agent.get("agent", "")).lower() != child_agent(task)):
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
    q = sub.add_parser("init"); q.add_argument("--cwd", default=os.getcwd()); q.add_argument("--request-file", required=True); q.add_argument("--main-pane"); q.add_argument("--main-terminal-id"); q.add_argument("--socket"); q.add_argument("--variant", choices=fp.VARIANTS, default="standard")
    q = sub.add_parser("spawn"); q.add_argument("--run", required=True); q.add_argument("--role", choices=("director", *fp.EXECUTORS), required=True); q.add_argument("--file"); q.add_argument("--cwd")
    q = sub.add_parser("send"); q.add_argument("--task", required=True); q.add_argument("--file", required=True)
    for name in ("collect", "close"):
        q = sub.add_parser(name); q.add_argument("--task", required=True)
    for name in ("consult", "final-check"):
        q = sub.add_parser(name); q.add_argument("--run", required=True); q.add_argument("--file", required=True)
    for name in ("forward", "relay", "check"):
        q = sub.add_parser(name); q.add_argument("--run", required=True)
    q = sub.add_parser("wait"); q.add_argument("--run", required=True); q.add_argument("--timeout", type=int, default=300)
    a = p.parse_args()
    if a.action == "init": result = initialize(a.cwd, a.request_file, a.main_pane, a.main_terminal_id, a.socket, a.variant)
    elif a.action == "spawn": result = spawn(a.run, a.role, a.file, a.cwd)
    elif a.action == "send": result = send(a.task, a.file)
    elif a.action == "collect": result = collect(a.task)
    elif a.action == "close": result = close(a.task)
    elif a.action == "forward": result = forward(a.run)
    elif a.action == "relay": result = relay(a.run)
    elif a.action == "consult": result = consult(a.run, a.file)
    elif a.action == "final-check": result = final_check(a.run, a.file)
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
