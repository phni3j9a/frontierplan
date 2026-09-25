from __future__ import annotations

import contextlib
import io
import json
from pathlib import Path
import shutil
import unittest
from unittest.mock import patch

import test_herdr as th
import frontierplan as fp
import herdr as hd


class Swe2Variant(unittest.TestCase):
    """astraplan-herdr-swe2: Devin SWE-2 fills only the Luna seats."""
    git = th.base.Protocol.git
    write = th.base.Protocol.write
    report = th.base.Protocol.report
    director = th.HerdrTransport.director
    decide = th.HerdrTransport.decide
    director_plan = th.HerdrTransport.director_plan

    def setUp(self):
        th.base.Protocol.setUp(self)
        which = patch.object(hd.shutil, "which", side_effect=lambda name: f"/usr/bin/{name}")
        which.start(); self.addCleanup(which.stop)

    def setup_api(self, variant="swe2"):
        self.api = th.FakeHerdr()
        self.addCleanup(patch.stopall)
        patch.object(hd, "Herdr", side_effect=lambda *a, **k: self.api).start()
        main = self.api.panes[0]
        value = hd.initialize(str(self.project), self.input, main["pane_id"], main["terminal_id"],
                              self.api.env["HERDR_SOCKET_PATH"], variant)
        self.run = value["run"]
        self.addCleanup(shutil.rmtree, self.run, True)
        self.output = contextlib.redirect_stdout(io.StringIO()); self.output.__enter__()
        self.addCleanup(self.output.__exit__, None, None, None)

    def starts(self):
        return [c for c in self.api.calls if c[:2] == ("agent", "start")]

    def kind(self, call):
        return call[call.index("--kind") + 1]

    def test_variant_recorded_and_restricted_to_herdr(self):
        self.setup_api()
        self.assertEqual(fp.run_at(self.run)[1]["variant"], "swe2")
        with self.assertRaises(fp.Failure):
            fp.initialize("subagent", str(self.project), self.input, variant="swe2")
        with self.assertRaises(fp.Failure):
            fp.initialize("subagent", str(self.project), self.input, variant="fable")

    def test_profiles_replace_only_luna_roles(self):
        for role in ("researcher", "worker"):
            self.assertEqual(fp.profile(role, variant="swe2"),
                             {"role": role, "agent": "devin", "model": "swe-2-max", "reasoning_effort": "max"})
        for role in ("director", "design", "reviewer", "main"):
            self.assertEqual(fp.profile(role, variant="swe2"), fp.profile(role))

    def test_worker_and_researcher_start_on_devin_others_on_codex(self):
        director = self.director()
        self.decide(director, {"kind": "research", "requests": [{"id": "r1", "assignment": "Survey A."}]})
        researcher = hd.relay(self.run)["tasks"][0]["task"]
        self.report(researcher, "Facts."); hd.collect(researcher)
        hd.relay(self.run)
        self.director_plan(director)
        worker = hd.spawn(self.run, "worker", self.input)["task"]
        design = hd.spawn(self.run, "design", self.input)["task"]
        reviewer = hd.spawn(self.run, "reviewer", self.input)["task"]
        kinds = [self.kind(c) for c in self.starts()]
        self.assertEqual(kinds, ["codex", "devin", "devin", "codex", "codex"])
        for task in (researcher, worker):
            data = fp.task_at(task)[1]
            self.assertNotIn("requested_codex_args", data)
            # Exactly the bypass-mode launch; no sandbox, derived config or fast tier.
            self.assertEqual(data["requested_devin_args"],
                             ["--permission-mode", "dangerous", "--model", "swe-2-max",
                              "--export", str(Path(task) / "devin-session.json")])
            self.assertFalse((Path(task) / "devin-config.json").exists())
        for task in (director, design, reviewer):
            data = fp.task_at(task)[1]
            self.assertNotIn("requested_devin_args", data)
            self.assertFalse(any('service_tier="fast"' == a for a in data["requested_codex_args"]))

    def test_missing_devin_stops_before_pane_change(self):
        director = self.director(); self.director_plan(director)
        splits = sum(c[:2] == ("pane", "split") for c in self.api.calls)
        with patch.object(hd.shutil, "which", return_value=None):
            with self.assertRaises(fp.Failure): hd.spawn(self.run, "worker", self.input)
        self.assertEqual(sum(c[:2] == ("pane", "split") for c in self.api.calls), splits)

    def test_collect_records_devin_session_evidence(self):
        director = self.director(); self.director_plan(director)
        worker = hd.spawn(self.run, "worker", self.input)["task"]
        (Path(worker) / "devin-session.json").write_text(json.dumps({
            "session_id": "eager-rhinoceros", "agent": {"model_name": "SWE-2 Max"},
            "steps": [{"source": "user", "message": "x"},
                      {"source": "agent", "model_name": "swe-2-max"},
                      {"source": "agent", "model_name": "swe-2-max"}]}))
        self.report(worker, "Implemented.", collect=False)
        result = hd.collect(worker)
        evidence = {"export": str(Path(worker) / "devin-session.json"),
                    "session_id": "eager-rhinoceros", "observed_models": ["swe-2-max"]}
        self.assertEqual(result["session_evidence"], evidence)
        self.assertEqual(result["profile_model"], "swe-2-max")
        self.assertEqual(fp.read(Path(worker) / "receipt.json")["session_evidence"], evidence)

    def test_collect_reports_missing_export_as_unverified(self):
        director = self.director(); self.director_plan(director)
        worker = hd.spawn(self.run, "worker", self.input)["task"]
        self.report(worker, "Implemented.", collect=False)
        self.assertIsNone(hd.collect(worker)["session_evidence"]["observed_models"])

    def test_codex_pane_cannot_stand_in_for_devin_task(self):
        director = self.director(); self.director_plan(director)
        worker = hd.spawn(self.run, "worker", self.input)["task"]
        name = fp.task_at(worker)[1]["name"]
        self.api.registered[name]["agent"] = "codex"
        self.report(worker, "Implemented.", collect=False)
        with self.assertRaises(fp.Failure): hd.collect(worker)
        self.assertIn({"task": worker, "event": "unavailable"}, hd.check(self.run)["events"])

    def test_full_cycle_closes_devin_participants(self):
        director = self.director(); self.director_plan(director)
        worker = hd.spawn(self.run, "worker", self.input)["task"]
        self.report(worker, "Implemented.", collect=False); hd.collect(worker)
        self.assertEqual(hd.check(self.run)["pending"], 0)
        reviewer = hd.spawn(self.run, "reviewer", self.input)["task"]
        self.report(reviewer, "FINDINGS: FP-001", collect=False); hd.collect(reviewer)
        hd.send(worker, self.write("fix.md", "FP-001 accepted: fix it."))
        self.assertEqual(sum(self.kind(c) == "devin" for c in self.starts()), 1)  # same session
        self.report(worker, "Fixed.", collect=False); hd.collect(worker)
        hd.send(reviewer, self.write("rereview.md", "Re-review FP-001."))
        self.report(reviewer, "FINDINGS: none", collect=False); hd.collect(reviewer)
        hd.final_check(self.run, self.write("evidence.md", "Criteria map."))
        self.decide(director, {"kind": "final_check", "plan_id": "p1",
                               "ac_status": [{"criterion": "Works", "status": "met", "evidence": "tests"}],
                               "findings": [], "plan_divergence": []})
        hd.close(worker); hd.close(reviewer)
        fp.finish(self.run, self.write("final.md", "Main's report."))
        hd.close(director)
        self.assertTrue(all(fp.task_at(t)[1]["closed"] for t in (worker, reviewer, director)))

    def test_standard_run_is_unchanged(self):
        self.setup_api("standard")
        self.assertEqual(fp.run_at(self.run)[1]["variant"], "standard")
        director = hd.spawn(self.run, "director")["task"]; self.director_plan(director)
        worker = hd.spawn(self.run, "worker", self.input)["task"]
        self.assertEqual({self.kind(c) for c in self.starts()}, {"codex"})
        args = fp.task_at(worker)[1]["requested_codex_args"]
        self.assertEqual(args[args.index("-m") + 1], "gpt-6-luna")
        self.assertNotIn("requested_devin_args", fp.task_at(worker)[1])


if __name__ == "__main__": unittest.main()
