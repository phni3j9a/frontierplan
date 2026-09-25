#!/usr/bin/env python3
"""Opt-in astraplan-herdr-swe2 smoke: REAL Devin SWE-2 children, SYNTHETIC Codex seats.

Run it from a recognized agent's pane inside the herdr server you want to use; that
pane becomes Main through the helper's normal current-pane identity check. The run
splits Main's pane like a real run, so start it from a tab that holds only Main.

Researcher and Worker are launched with `herdr agent start --kind devin` and do their
work through the real packets, sandbox and report protocol. Astra and the Reviewer
never start a model: their panes stay shells, and this script publishes their
decisions/reports as explicit fixtures. Pane, layout, wait, collect and close calls
all go through the real helper and Herdr. Prints JSON evidence to stdout.
"""
from __future__ import annotations

import argparse
import copy
import json
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import time
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "plugins/frontierplan/scripts"))
import frontierplan as fp
import herdr as hd

RealHerdr = hd.Herdr


class CodexSeatsSynthetic:
    """Real Herdr, except that Codex agents are replaced by registered shell panes."""

    def __init__(self, state=None, socket=None):
        self.real = RealHerdr(state, socket)
        self.binary, self.env = self.real.binary, self.real.env
        self.synthetic = SYNTHETIC

    def annotate(self, pane):
        if any(a["terminal_id"] == pane.get("terminal_id") for a in self.synthetic.values()):
            return dict(pane, agent="codex")
        return pane

    def agents(self):
        panes = {p["terminal_id"]: p for p in self.real.call("pane", "list")["panes"]}
        agents = self.real.agents()
        for name, agent in self.synthetic.items():
            if agent["terminal_id"] in panes:
                agents[name] = dict(agent, pane_id=panes[agent["terminal_id"]]["pane_id"])
        return agents

    def call(self, *args):
        args = tuple(map(str, args))
        if args[:2] == ("agent", "start") and args[args.index("--kind") + 1] == "codex":
            pane = self.real.call("pane", "get", args[args.index("--pane") + 1])["pane"]
            self.synthetic[args[2]] = dict(pane, name=args[2], agent="codex", agent_status="idle",
                                           state_change_seq=1, launch_pending=False)
            return {"argv": list(args[args.index("--") + 1:]), "synthetic": True}
        if args[:2] == ("agent", "prompt") and args[2] in self.synthetic:
            self.synthetic[args[2]]["state_change_seq"] += 1
            return {"synthetic": True}
        result = self.real.call(*args)
        if args[:2] == ("pane", "close"):
            for name in [n for n, a in self.synthetic.items() if a.get("pane_id") == args[2]]:
                self.synthetic.pop(name)
        if isinstance(result.get("pane"), dict): result["pane"] = self.annotate(result["pane"])
        if isinstance(result.get("panes"), list): result["panes"] = [self.annotate(p) for p in result["panes"]]
        return result


SYNTHETIC: dict = {}
EVENTS: list = []


def log(step, **data):
    EVENTS.append(dict(step=step, at=time.strftime("%Y-%m-%dT%H:%M:%S%z"), **data))
    print(json.dumps(EVENTS[-1], ensure_ascii=False), file=sys.stderr, flush=True)


def write(directory: Path, name: str, value) -> str:
    path = directory / name
    path.write_text(value if isinstance(value, str) else json.dumps(value, ensure_ascii=False), encoding="utf-8")
    return str(path)


def synthetic_report(scratch: Path, task: str, value, status="complete"):
    data = fp.task_at(task)[1]
    fp.publish(task, data["request_id"], status, write(scratch, f"{data['request_id']}.fixture", value))


def await_report(run: str, task: str, limit: float) -> dict:
    """Real helper waits until this task's report can be collected."""
    deadline = time.monotonic() + limit
    while time.monotonic() < deadline:
        snapshot = hd.wait(run, timeout=min(300, max(1, int(deadline - time.monotonic()))))
        mine = [e["event"] for e in snapshot["events"] if e["task"] == task]
        if "report" in mine:
            return hd.collect(task)
        fp.require(not {"unavailable", "blocked", "idle_without_report", "unknown"} & set(mine),
                   f"Participant needs attention: {mine}; inspect its pane.")
    raise fp.Failure("Timed out waiting for the Devin report; the pane is left open for inspection.")


def layout(api, main_pane: str) -> dict:
    value = api.call("pane", "layout", "--pane", main_pane)["layout"]
    return {"panes": [{"pane_id": p["pane_id"], "rect": p["rect"]} for p in value["panes"]]}


def smoke(limit: float) -> dict:
    scratch = Path(tempfile.mkdtemp(prefix="fp-swe2-smoke-"))
    project = scratch / "project"; project.mkdir()
    git = lambda *a: subprocess.run(["git", "-C", str(project), *a], check=True, capture_output=True, text=True).stdout
    git("init", "-q"); git("config", "user.email", "smoke@example.invalid"); git("config", "user.name", "smoke")
    (project / "calc.py").write_text("def add(a, b):\n    return a + b\n")
    git("add", "."); git("commit", "-qm", "base")
    request = write(scratch, "request.md", "Add a subtract(a, b) function to calc.py with a unit test.")
    evidence = {"versions": {name: subprocess.run([name, "--version"], capture_output=True, text=True).stdout.strip()
                             for name in ("devin", "herdr")}}
    with patch.object(hd, "Herdr", CodexSeatsSynthetic):
        run = hd.initialize(str(project), request, variant="swe2")
        evidence["init"] = run; run = run["run"]; log("init", run=run)
        api = hd.Herdr(fp.run_at(run)[1]); main = hd.main_pane(fp.run_at(run)[1], api)["pane_id"]
        director = hd.spawn(run, "director")["task"]; log("director_synthetic", task=director)
        synthetic_report(scratch, director, {"kind": "research", "requests": [{"id": "r1", "assignment":
            f"In {project}, read calc.py and report the exact function names it defines and the "
            "command you used. Read-only; do not modify the project."}]})
        hd.collect(director); fp.decision(director)
        researcher = hd.relay(run)["tasks"][0]["task"]; log("researcher_started", task=researcher)
        evidence["layout_research"] = layout(api, main)
        evidence["researcher"] = {"collect": await_report(run, researcher, limit)}
        log("researcher_collected")
        back = hd.relay(run); evidence["researcher"]["closed"] = back["closed"]
        synthetic_report(scratch, director, {"kind": "plan", "plan_id": "p1", "user_response": "Plan (fixture).",
            "plan": "Add subtract(a, b) to calc.py and a unittest.", "acceptance_criteria":
            ["subtract(5, 3) == 2", "unittest passes"], "verification": ["python3 -m unittest"],
            "authorization_message": 1})
        hd.collect(director); fp.decision(director); fp.start(run)
        worker = hd.spawn(run, "worker", write(scratch, "assignment.md",
            f"In {project}: add subtract(a, b) to calc.py and create test_calc.py with a unittest "
            "covering add and subtract. Run `python3 -m unittest` and include its output. Do not commit.")
            )["task"]
        log("worker_started", task=worker)
        evidence["layout_execution"] = layout(api, main)
        evidence["worker"] = {"first": await_report(run, worker, limit)}; log("worker_collected")
        reviewer = hd.spawn(run, "reviewer", write(scratch, "review.md", "Review (fixture)."))["task"]
        synthetic_report(scratch, reviewer, "FINDINGS: FP-001 subtract lacks a docstring (fixture).")
        hd.collect(reviewer)
        hd.send(worker, write(scratch, "fix.md", "FP-001 accepted: add a one-line docstring to subtract "
                              "in calc.py, rerun `python3 -m unittest`, and report."))
        evidence["worker"]["fix"] = await_report(run, worker, limit); log("worker_fix_collected")
        hd.send(reviewer, write(scratch, "rereview.md", "Re-review FP-001 (fixture)."))
        synthetic_report(scratch, reviewer, "FINDINGS: none (fixture)."); hd.collect(reviewer)
        hd.final_check(run, write(scratch, "evidence.md", "Fixture evidence."))
        synthetic_report(scratch, director, {"kind": "final_check", "plan_id": "p1", "ac_status": [
            {"criterion": "subtract(5, 3) == 2", "status": "met", "evidence": "fixture"},
            {"criterion": "unittest passes", "status": "met", "evidence": "fixture"}],
            "findings": [], "plan_divergence": []})
        hd.collect(director); fp.decision(director)
        data = fp.task_at(worker)[1]
        evidence["worker"]["requested_devin_args"] = data["requested_devin_args"]
        evidence["worker"]["launched_argv"] = data.get("launched_argv")
        evidence["worker"]["devin_permissions"] = fp.read(Path(worker) / "devin-config.json")["permissions"]
        evidence["project"] = {"status": git("status", "--short"), "diff": git("diff"),
                               "untracked_test": (project / "test_calc.py").read_text()
                               if (project / "test_calc.py").exists() else None,
                               "unittest": subprocess.run([sys.executable, "-m", "unittest", "-v"], cwd=project,
                                                          capture_output=True, text=True).stderr[-1500:]}
        evidence["closed"] = [hd.close(worker), hd.close(reviewer)]
        fp.finish(run, write(scratch, "final.md", "Smoke final report (fixture)."))
        evidence["closed"].append(hd.close(director))
        evidence["layout_final"] = layout(api, main)
    evidence["events"] = EVENTS
    shutil.rmtree(scratch)
    shutil.rmtree(run)
    return evidence


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--limit", type=float, default=1200, help="seconds allowed per Devin report")
    try:
        print(json.dumps(smoke(parser.parse_args().limit), ensure_ascii=False, indent=2))
    except fp.Failure as exc:
        print(json.dumps({"error": str(exc), "events": EVENTS}, ensure_ascii=False, indent=2))
        sys.exit(1)
