#!/usr/bin/env python3
"""Opt-in real Herdr pane smoke with SYNTHETIC agents; never launches a model.

Requires an already running disposable, empty Herdr server via --socket. Uses real
pane/layout/close calls; only agent identity/start/prompt/status are simulated.
Prints JSON evidence to stdout. This is not a model-routing or full agent smoke.
"""
from __future__ import annotations

import argparse
import copy
import json
from pathlib import Path
import subprocess
import sys
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tests"))
import test_herdr as transport
from test_herdr_lifecycle import Lifecycle
import frontierplan as fp
import herdr as hd


class SyntheticAgents:
    def __init__(self, real, main):
        self.real, self.main = real, main
        self.binary, self.env = real.binary, real.env
        self.panes = [self.annotate(main)]
        self.registered, self.calls = {}, []

    def annotate(self, pane):
        return dict(pane, agent="codex", agent_session="main-test"
                    if pane["terminal_id"] == self.main["terminal_id"] else "synthetic-agent")

    def agents(self):
        panes = {p["terminal_id"]: p for p in self.real.call("pane", "list")["panes"]}
        return {name: dict(agent, pane_id=panes[agent["terminal_id"]]["pane_id"])
                for name, agent in self.registered.items() if agent["terminal_id"] in panes}

    def call(self, *args):
        self.calls.append(args)
        if args[:2] == ("agent", "start"):
            pane = self.real.call("pane", "get", args[args.index("--pane") + 1])["pane"]
            self.registered[args[2]] = dict(self.annotate(pane), name=args[2],
                                          agent_status="idle", state_change_seq=1, launch_pending=False)
            return {"argv": list(args[args.index("--") + 1:])}
        if args[:2] == ("agent", "prompt"):
            self.registered[args[2]]["state_change_seq"] += 1
            return {}
        result = self.real.call(*args)
        if "pane" in result: result["pane"] = self.annotate(result["pane"])
        if "panes" in result: result["panes"] = [self.annotate(p) for p in result["panes"]]
        return result


def smoke(socket):
    real = hd.Herdr(socket=socket)
    real.env.pop("HERDR_SESSION", None)
    fp.require(not real.call("workspace", "list")["workspaces"],
               "Smoke requires an empty disposable server; no existing workspaces changed.")
    case = Lifecycle()
    case.setUp()
    created = None
    evidence = {"herdr_version": subprocess.check_output([real.binary, "--version"], text=True).strip(),
                "real": ["pane creation", "layout geometry", "focus", "resize", "move", "pane close", "split collapse"],
                "synthetic": ["agent identity", "model start", "prompts", "reports", "acceptance", "activity"],
                "models_launched": 0, "snapshots": {}}
    try:
        created = real.call("workspace", "create", "--cwd", str(case.project), "--label", "FrontierPlan issue 4 smoke", "--no-focus")
        main = created["root_pane"]
        api = SyntheticAgents(real, main)
        def capture(name):
            layout = real.call("pane", "layout", "--pane", main["pane_id"])["layout"]
            evidence["snapshots"][name] = copy.deepcopy(layout)
            fp.require(layout["focused_pane_id"] == main["pane_id"], "Spawn stole Main focus.")
            return layout
        with patch.object(transport, "FakeHerdr", return_value=api):
            director = case.director(); case.director_plan(director)
            planning = capture("planning")
            fp.require(planning["splits"][0]["ratio"] == 0.4, "Main ratio is not 40/60.")
            worker = hd.spawn(case.run, "worker", case.input)["task"]
            design = hd.spawn(case.run, "design", case.input)["task"]
            for task in (worker, design):
                case.report(task, "SYNTHETIC: implemented and integrated"); hd.collect(task)
            reviewer = hd.spawn(case.run, "reviewer", case.input)["task"]
            case.report(reviewer, "SYNTHETIC: FINDINGS: none"); hd.collect(reviewer)
            execution = capture("execution")
            fp.require([(s["direction"], s["ratio"]) for s in execution["splits"]]
                       == [("right", 0.4), ("down", 0.4), ("right", 0.5), ("right", 0.5)],
                       "Execution escaped the role layout.")
            real.call("pane", "resize", "--pane", main["pane_id"], "--direction", "right", "--amount", "0.1")
            capture("manually_resized")
            worker_decision = case.evidence(worker, reviewer)
            real.call("pane", "move", case.task(worker)["handle"]["pane_id"], "--new-tab",
                      "--workspace", created["workspace"]["workspace_id"], "--label", "moved-owned-worker", "--no-focus")
            capture("worker_moved")
            hd.release(worker, worker_decision)
            hd.release(design, case.evidence(design, reviewer))
            capture("workers_released")
            case.accept(director); hd.release(reviewer)
            capture("reviewer_released")
            case.replan(director)
            new_worker = hd.spawn(case.run, "worker", case.input)["task"]
            recreated = capture("execution_recreated")
            fp.require([(s["direction"], s["ratio"]) for s in recreated["splits"]]
                       == [("right", 0.5), ("down", 0.4)], "Manual ratio or recreated execution region changed.")
            case.report(new_worker, "SYNTHETIC: late fix"); hd.collect(new_worker)
            new_reviewer = hd.spawn(case.run, "reviewer", case.input)["task"]
            case.report(new_reviewer, "SYNTHETIC: FINDINGS: none"); hd.collect(new_reviewer)
            hd.release(new_worker, case.evidence(new_worker, new_reviewer))
            case.accept(director); hd.release(new_reviewer); fp.finish(case.run)
            for path, _ in fp.tasks(Path(case.run)): hd.close(str(path))
            final = capture("finished")
            fp.require(len(final["panes"]) == 1, "Owned child panes remain.")
            evidence["split_calls"] = [{"target": c[2], "direction": c[c.index("--direction") + 1],
                                        "ratio": float(c[c.index("--ratio") + 1]), "no_focus": "--no-focus" in c}
                                       for c in api.calls if c[:2] == ("pane", "split")]
            evidence["close_calls"] = [c for c in api.calls if c[:2] == ("pane", "close")]
            fp.require(len(evidence["close_calls"]) == 6, "A released pane was closed twice or not closed.")
            evidence["result"] = "PASS"
    finally:
        case.doCleanups()
        if created:
            # Only the disposable workspace created above. A server stop is left to
            # its owner so this script cannot terminate an arbitrary running server.
            real.call("workspace", "close", created["workspace"]["workspace_id"])
    return evidence


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--socket", required=True)
    args = parser.parse_args()
    print(json.dumps(smoke(args.socket), ensure_ascii=False, indent=2))
