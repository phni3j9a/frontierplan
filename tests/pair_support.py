"""Simulated peer tool/identity fixtures; not evidence of native or Herdr support."""
from contextlib import contextmanager
import os
from pathlib import Path
from unittest.mock import patch

import frontierplan as fp
import herdr as hd
import pairs


def create_pair(test, role="worker", scope=None):
    state = fp.run_at(test.run)[1]
    if state["backend"] == "herdr":
        value = hd.spawn_pair(test.run, test.input, scope=scope, role=role)
    else:
        capability = test.write("simulated-capability.json", {"direct_peer_resume": True,
                                "evidence": "SIMULATED host in unit tests, not real native tool support"})
        value = pairs.create(test.run, test.input, role=role, scope=scope, capability_file=capability)
        for key in ("reviewer", "worker"):
            task = value[key]["task"]
            identity = "simulated-" + Path(task).name
            data = fp.task_at(task)[1]
            with patch.dict(os.environ, {"CODEX_THREAD_ID": identity, "CODEX_SESSION_ID": ""}):
                observed = pairs.bootstrap(task, data["request_id"])
            fp.bind(task, test.write(f"{identity}.json", {"agent_id": identity, "thread_id": identity,
                                                       "evidence": "simulated spawn"}))
            test.assertEqual(observed["thread_id"], identity)
    return value["worker"]["task"], value["reviewer"]["task"]


@contextmanager
def child(test, task_path):
    path, task, _, state = fp.task_at(task_path)
    env = {"FRONTIERPLAN_ROLE": task["role"], "FRONTIERPLAN_TASK": str(path),
           "FRONTIERPLAN_MAIN_AGENT": "", "FRONTIERPLAN_MAIN_SESSION_ID": "",
           "CODEX_SESSION_ID": ""}
    if state["backend"] == "herdr":
        env.update(HERDR_PANE_ID=task["handle"]["pane_id"], CODEX_THREAD_ID="child-" + task["id"])
        # Some identity fixtures deliberately override pane current to select Main.
        # A real child's --current must return that child's actual terminal.
        current = next(p for p in test.api.panes if p["terminal_id"] == task["handle"]["terminal_id"])
        original = test.api.call
        def call(*args):
            if args[:2] == ("pane", "current"):
                return {"pane": dict(current)}
            return original(*args)
        with patch.dict(os.environ, env), patch.object(test.api, "call", side_effect=call):
            yield task
    else:
        env.update(CODEX_THREAD_ID=task["handle"]["thread_id"])
        with patch.dict(os.environ, env):
            yield task


def pair_turn(test, task_path, kind, report=None, change=None):
    with child(test, task_path) as task:
        started = pairs.begin(task_path, task["request_id"])
        if change:
            change()
        return pairs.submit(task_path, task["request_id"], kind,
                            test.write("pair-report.md", report or "SIMULATED focused verification"),
                            started.get("candidate"))


def pass_pair(test, worker, reviewer, collect=True):
    pair_turn(test, worker, "candidate")
    pair_turn(test, reviewer, "pass")
    if collect:
        pairs.collect(worker)
    return worker, reviewer


def passed_pair(test, role="worker", scope=None):
    return pass_pair(test, *create_pair(test, role=role, scope=scope))
