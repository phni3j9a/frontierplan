#!/usr/bin/env python3
"""Visible FrontierPlan transport. No hidden-agent or model fallback.

Identity, no-focus splitting, and report/activity checks adapted from
phni3j9a/axiom_for_herdr (MIT); see THIRD_PARTY_NOTICES.md.
"""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import shutil
import subprocess
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
    value = pane.get("agent_session")
    if isinstance(value, dict):
        value = value.get("value") or value.get("id")
    return value or pane.get("agent_session_id") or pane.get("session_id") or pane.get("thread_id")


def validate_session(pane: dict, expected: str) -> None:
    fp.require(str(pane.get("agent", "")).lower() == "codex", "The Main terminal is not Codex.")
    observed = session_id(pane)
    fp.require(not observed or observed == expected, "Main's conversation does not match the live pane.")


def main_pane(state: dict, api: Herdr) -> dict:
    fp.main_only(state)
    fp.require(state["backend"] == "herdr" and state.get("herdr"), "This is not a bound herdr run.")
    terminal = state["herdr"]["main_terminal_id"]
    matches = [p for p in api.call("pane", "list")["panes"] if p.get("terminal_id") == terminal]
    fp.require(len(matches) == 1, "Main's original terminal is missing or ambiguous; no pane changed.")
    validate_session(matches[0], state["main_thread_id"])
    return matches[0]  # Preserve terminal identity even after a manual move/swap.


def initialize(cwd: str, request_file: str, pane_id: str | None = None,
               terminal_id: str | None = None, socket: str | None = None) -> dict:
    fp.require(bool(pane_id) == bool(terminal_id), "Supply both Main pane and terminal IDs.")
    fp.require(fp.thread_id(), "Main conversation identity is required.")
    api = Herdr(socket=socket)
    if pane_id:
        pane = api.call("pane", "get", pane_id)["pane"]
        fp.require(pane.get("pane_id") == pane_id and pane.get("terminal_id") == terminal_id,
                   "The selected Main pane/terminal does not match.")
    else:
        fp.require(os.environ.get("HERDR_PANE_ID"),
                   "No HERDR_PANE_ID. Verify Main's conversation, then pass --main-pane and --main-terminal-id.")
        pane = api.call("pane", "current", "--current")["pane"]
    validate_session(pane, fp.thread_id())
    value = fp.initialize("herdr", cwd, request_file)
    with fp.transaction(value["run"]) as (_, state):
        state["herdr"] = {"binary": str(api.binary), "socket": api.env.get("HERDR_SOCKET_PATH"),
                          "main_pane_id": pane["pane_id"], "main_terminal_id": pane["terminal_id"]}
    return {"run": value["run"], "main_pane": pane["pane_id"]}


def live(task: dict, agents: dict) -> dict:
    handle = task.get("handle") or {}
    agent = agents.get(task["name"])
    fp.require(agent and agent.get("terminal_id") == handle.get("terminal_id")
               and str(agent.get("agent", "")).lower() == "codex",
               "The original Codex session is unavailable; inspect recorded handles, do not guess.")
    return agent


def ready(agent: dict) -> bool:
    return agent.get("agent_status") in ("idle", "done") and not agent.get("launch_pending", False)


def codex_args(task: dict, root: Path, pane: dict, api: Herdr) -> list[str]:
    p = task["profile"]
    args = ["-C", task["cwd"], "-m", p["model"], "-c", f'model_reasoning_effort="{p["reasoning_effort"]}"',
            "-c", 'default_permissions=":workspace"']
    if p.get("service_tier") == "fast":
        args += ["-c", 'service_tier="fast"', "-c", "features.fast_mode=true"]
    env = {"FRONTIERPLAN_ROLE": task["role"], "FRONTIERPLAN_TASK": str(root / "tasks" / task["id"]),
           "HERDR_PANE_ID": pane["pane_id"], "HERDR_BIN_PATH": str(api.binary)}
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
    agents = api.agents()
    main = main_pane(state, api)
    layout = api.call("pane", "layout", "--pane", main["pane_id"])["layout"]
    owned = set()
    for _, other in fp.tasks(root):
        if other.get("closed") or other.get("lost") or not other.get("handle"):
            continue
        agent = agents.get(other["name"])
        if agent and agent.get("terminal_id") == other["handle"].get("terminal_id"):
            owned.add(agent["pane_id"])
    candidates = [p for p in layout["panes"] if p["pane_id"] in owned and p["pane_id"] != main["pane_id"]]
    if candidates:
        target = max(candidates, key=lambda p: p["rect"]["width"] * p["rect"]["height"])
        target_id = target["pane_id"]
        direction = "right" if target["rect"]["width"] > 4 * target["rect"]["height"] else "down"
    else:
        target_id, direction = main["pane_id"], "right"
    pane = api.call("pane", "split", target_id, "--direction", direction, "--ratio", "0.5",
                    "--cwd", task["cwd"], "--no-focus", "--env", f"FRONTIERPLAN_ROLE={role}",
                    "--env", f"FRONTIERPLAN_TASK={path}")["pane"]
    task["handle"] = {"pane_id": pane["pane_id"], "terminal_id": pane["terminal_id"]}
    task["delivery"] = "starting"
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
    agent = live(task, api.agents())
    fp.require(ready(agent), "Wait until the agent is idle before collection.")
    fp.require("state_change_seq" in agent, "herdr lacks activity sequence evidence; cannot collect safely.")
    result = fp.collect(task_path)
    receipt = fp.read(path / "receipt.json")
    receipt.update(state_change_seq=agent["state_change_seq"], terminal_id=agent["terminal_id"])
    fp.atomic(path / "receipt.json", receipt)
    return result


def close(task_path: str) -> dict:
    path, task, root, state = fp.task_at(task_path)
    api = Herdr(state)
    main_pane(state, api)
    fp.require(state["phase"] == "closed", "Do not close participants before overall wrap-up.")
    if task.get("closed"):
        return {"closed": True, "already_closed": True}
    result = fp.collected(path, task)
    receipt = fp.read(path / "receipt.json")
    agent = live(task, api.agents())
    fp.require(agent["terminal_id"] != state["herdr"]["main_terminal_id"], "Never close Main.")
    fp.require(ready(agent) and receipt.get("state_change_seq") is not None
               and agent.get("state_change_seq") == receipt["state_change_seq"],
               "Agent activity changed after collection; keep the pane open.")
    fp.require(fp.digest(fp.current_result(path, task)) == fp.digest(result), "Report changed during close.")
    api.call("pane", "close", agent["pane_id"])
    return fp.close_record(task_path)


def wait(run: str, timeout: int = 3600) -> dict:
    fp.require(0 <= timeout <= 3600, "Wait timeout must be between 0 and 3600 seconds.")
    root, state = fp.run_at(run)
    api = Herdr(state)
    main_pane(state, api)
    deadline = time.monotonic() + timeout
    notice_file = root / "wait-notices.json"
    with fp.lock(root / ".wait.lock"):
        previous = fp.read(notice_file) if notice_file.exists() else {}
        while True:
            events, current, pending = [], {}, 0
            agents = api.agents()
            for path, task in fp.tasks(root):
                if task.get("closed") or task.get("lost"):
                    continue
                agent = agents.get(task["name"])
                if agent and agent.get("terminal_id") != (task.get("handle") or {}).get("terminal_id"):
                    agent = None
                result = fp.current_result(path, task)
                receipt = fp.read(path / "receipt.json") if (path / "receipt.json").exists() else {}
                unchanged = result and receipt.get("digest") == fp.digest(result)
                if (unchanged and result["status"] == "complete" and agent and ready(agent)
                        and agent.get("state_change_seq") == receipt.get("state_change_seq")):
                    continue
                pending += 1
                event = None
                if not agent: event = "unavailable"
                elif agent.get("agent_status") in ("blocked", "unknown"): event = agent["agent_status"]
                elif ready(agent) and result and result["status"] in ("complete", "blocked"): event = "report"
                elif ready(agent) and time.time() - task.get("submitted_at", time.time()) > 8: event = "idle_without_report"
                if event:
                    mark = fp.digest({"request": task["request_id"], "result": result, "event": event,
                                      "seq": (agent or {}).get("state_change_seq")})
                    current[str(path)] = mark
                    if previous.get(str(path)) != mark:
                        events.append({"task": str(path), "event": event})
            if previous != current:
                fp.atomic(notice_file, current)
                previous = current
            if events or not pending:
                return {"events": events, "pending": pending}
            if time.monotonic() >= deadline:
                return {"events": [], "pending": pending, "timeout": True}
            time.sleep(min(2, max(0, deadline - time.monotonic())))


def cli() -> None:
    p = argparse.ArgumentParser(description=__doc__)
    sub = p.add_subparsers(dest="action", required=True)
    q = sub.add_parser("init"); q.add_argument("--cwd", default=os.getcwd()); q.add_argument("--request-file", required=True); q.add_argument("--main-pane"); q.add_argument("--main-terminal-id"); q.add_argument("--socket")
    q = sub.add_parser("spawn"); q.add_argument("--run", required=True); q.add_argument("--role", choices=fp.CHILDREN, required=True); q.add_argument("--file", required=True); q.add_argument("--cwd")
    q = sub.add_parser("send"); q.add_argument("--task", required=True); q.add_argument("--file", required=True)
    for name in ("collect", "close"):
        q = sub.add_parser(name); q.add_argument("--task", required=True)
    q = sub.add_parser("wait"); q.add_argument("--run", required=True); q.add_argument("--timeout", type=int, default=3600)
    a = p.parse_args()
    if a.action == "init": result = initialize(a.cwd, a.request_file, a.main_pane, a.main_terminal_id, a.socket)
    elif a.action == "spawn": result = spawn(a.run, a.role, a.file, a.cwd)
    elif a.action == "send": result = send(a.task, a.file)
    elif a.action == "collect": result = collect(a.task)
    elif a.action == "close": result = close(a.task)
    else: result = wait(a.run, a.timeout)
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    try:
        cli()
    except (fp.Failure, OSError, ValueError, KeyError, subprocess.TimeoutExpired) as exc:
        print(json.dumps({"error": str(exc)}, ensure_ascii=False), file=sys.stderr)
        sys.exit(1)
