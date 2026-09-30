"""Role layout and close safety against simulated Herdr; no live model claims."""
from __future__ import annotations

from pathlib import Path
import io
import json
import sys
import unittest
from unittest.mock import patch

import test_frontierplan as base
import test_herdr as transport
import frontierplan as fp
import herdr as hd


class Lifecycle(unittest.TestCase):
    setUp = base.Protocol.setUp
    git = base.Protocol.git
    write = base.Protocol.write
    report = base.Protocol.report
    setup_api = transport.HerdrTransport.setup_api
    director = transport.HerdrTransport.director
    decide = transport.HerdrTransport.decide
    director_plan = transport.HerdrTransport.director_plan

    def task(self, task): return fp.task_at(task)[1]
    def agent(self, task): return self.api.registered[self.task(task)["name"]]
    def splits(self): return [c for c in self.api.calls if c[:2] == ("pane", "split")]
    def closes(self): return [c for c in self.api.calls if c[:2] == ("pane", "close")]

    def reviewed(self, role="worker"):
        director = self.director(); self.director_plan(director)
        worker = hd.spawn(self.run, role, self.input)["task"]
        self.report(worker, "Implemented and integrated; test evidence."); hd.collect(worker)
        reviewer = hd.spawn(self.run, "reviewer", self.input)["task"]
        self.report(reviewer, "FINDINGS: none"); hd.collect(reviewer)
        return director, worker, reviewer

    def replan(self, director):
        hd.consult(self.run, self.write("q.md", "The Plan no longer fits."))
        self.decide(director, {"kind": "plan", "plan_id": "p2", "user_response": "Revised",
                               "plan": "Apply the new fix", "acceptance_criteria": ["Fix works"],
                               "verification": ["Test fix"], "authorization_message": 1})
        fp.start(self.run)

    def assert_no_close(self, task):
        before = self.closes()
        with self.assertRaises(fp.Failure): hd.close(task)
        self.assertEqual(self.closes(), before)
        self.assertFalse(self.task(task)["closed"])

    def test_role_layout_and_widest_execution_split(self):
        director, worker, reviewer = self.reviewed()
        design = hd.spawn(self.run, "design", self.input)["task"]
        calls = self.splits()
        self.assertEqual([(c[c.index("--direction") + 1], c[c.index("--ratio") + 1]) for c in calls],
                         [("right", "0.4"), ("down", "0.4"), ("right", "0.5"), ("right", "0.5")])
        self.assertEqual([c[2] for c in calls], ["main-pane", self.agent(director)["pane_id"],
                                              self.agent(worker)["pane_id"], self.agent(worker)["pane_id"]])
        self.assertTrue(all("--no-focus" in c for c in calls))
        layout = self.api.layout(); rects = {p["pane_id"]: p["rect"] for p in layout["panes"]}
        self.assertEqual(rects[self.agent(director)["pane_id"]]["y"], 1)
        for task in (worker, reviewer, design):
            self.assertGreater(rects[self.agent(task)["pane_id"]]["y"], 40)

    def test_manual_resize_and_unrelated_outer_pane_preserved(self):
        self.setup_api()
        user = self.api.call("pane", "split", "main-pane", "--direction", "down", "--ratio", "0.7")["pane"]
        director = hd.spawn(self.run, "director", self.input)["task"]; self.director_plan(director)
        self.api.tree["first"]["ratio"] = 0.3
        hd.spawn(self.run, "worker", self.input)
        self.api.tree["first"]["second"]["ratio"] = 0.6
        hd.spawn(self.run, "reviewer", self.input)
        self.assertEqual(self.api.tree["ratio"], 0.7)
        self.assertEqual(self.api.tree["first"]["ratio"], 0.3)
        self.assertEqual(self.api.tree["first"]["second"]["ratio"], 0.6)
        self.assertEqual(self.api.tree["second"], user["pane_id"])

    def test_missing_director_anchor_never_splits_main(self):
        director, _, _ = self.reviewed()
        self.api.registered.pop(self.task(director)["name"])
        before = self.splits()
        with self.assertRaises(fp.Failure): hd.spawn(self.run, "worker", self.input)
        self.assertEqual(self.splits(), before)

    def test_user_pane_inside_execution_region_stops_spawn(self):
        _, worker, _ = self.reviewed()
        self.api.call("pane", "split", self.agent(worker)["pane_id"], "--direction", "right", "--ratio", "0.5")
        before = self.splits()
        with self.assertRaises(fp.Failure): hd.spawn(self.run, "worker", self.input)
        self.assertEqual(self.splits(), before)

    def test_swapped_main_director_stops_spawn(self):
        director, _, _ = self.reviewed()
        pane = self.agent(director)["pane_id"]
        self.api.tree = self.api.replace(self.api.tree, "main-pane", "temporary")
        self.api.tree = self.api.replace(self.api.tree, pane, "main-pane")
        self.api.tree = self.api.replace(self.api.tree, "temporary", pane)
        before = self.splits()
        with self.assertRaises(fp.Failure): hd.spawn(self.run, "worker", self.input)
        self.assertEqual(self.splits(), before)

    def test_moved_execution_participant_stops_spawn(self):
        _, worker, _ = self.reviewed()
        self.api.tree = self.api.replace(self.api.tree, self.agent(worker)["pane_id"], None)
        before = self.splits()
        with self.assertRaises(fp.Failure): hd.spawn(self.run, "worker", self.input)
        self.assertEqual(self.splits(), before)

    def test_zoomed_layout_stops_spawn(self):
        self.setup_api(); self.api.zoomed = True
        with self.assertRaises(fp.Failure): hd.spawn(self.run, "director", self.input)
        self.assertEqual(self.splits(), [])

    def test_empty_geometry_stops_spawn_instead_of_ignoring_pane(self):
        self.setup_api(); self.api.area["height"] = 2
        with self.assertRaises(fp.Failure): hd.spawn(self.run, "director", self.input)
        self.assertEqual(self.splits(), [])

    def test_worker_fix_and_rereview_reuse_original_sessions(self):
        _, worker, reviewer = self.reviewed()
        handles = [self.task(t)["handle"] for t in (worker, reviewer)]
        self.report(reviewer, "FINDINGS: FP-001 fix required"); hd.collect(reviewer)
        hd.send(worker, self.input)
        self.assert_no_close(worker)  # Working on the accepted fix.
        (self.project / "file.txt").write_text("fixed\n")
        self.report(worker, "Fixed FP-001; integrated; tests passed"); hd.collect(worker)
        hd.send(reviewer, self.input)
        self.report(reviewer, "FINDINGS: none; FP-001 resolved"); hd.collect(reviewer)
        self.assertEqual([self.task(t)["handle"] for t in (worker, reviewer)], handles)
        hd.close(worker); hd.close(reviewer)
        self.assertTrue(all(self.task(t)["closed"] for t in (worker, reviewer)))

    def test_cli_close_and_consult(self):
        director, worker, _ = self.reviewed()
        with patch.object(sys, "argv", ["herdr.py", "close", "--task", worker]), patch.object(sys, "stdout", io.StringIO()):
            hd.cli()
        self.assertTrue(self.task(worker)["closed"])
        stream = io.StringIO()
        with patch.object(sys, "argv", ["herdr.py", "consult", "--run", self.run, "--file", self.input]), patch.object(sys, "stdout", stream):
            hd.cli()
        self.assertEqual(json.loads(stream.getvalue())["purpose"], "consultation")

    def test_astra_and_main_cannot_be_closed_early(self):
        director, worker, _ = self.reviewed()
        self.assert_no_close(director)
        data = self.task(worker); data["role"] = "main"; fp.atomic(Path(worker) / "task.json", data)
        self.assert_no_close(worker)
        data["role"] = "worker"; data["handle"]["terminal_id"] = "main-terminal"
        fp.atomic(Path(worker) / "task.json", data)
        self.agent(worker)["terminal_id"] = "main-terminal"
        self.assert_no_close(worker)

    def test_blocked_executor_stays_open_until_finish(self):
        director, worker, _ = self.reviewed()
        hd.send(worker, self.input); self.report(worker, "Blocked on credentials", status="blocked"); hd.collect(worker)
        self.assert_no_close(worker)

    def test_active_or_uncollected_or_changed_activity_rejected(self):
        _, worker, _ = self.reviewed()
        agent = self.agent(worker)
        for change in ({"agent_status": "working"}, {"launch_pending": True}, {"state_change_seq": 999}):
            original = dict(agent); agent.update(change)
            self.assert_no_close(worker); agent.clear(); agent.update(original)
        receipt = Path(worker) / "receipt.json"; receipt.unlink()
        self.assert_no_close(worker)

    def test_new_report_requires_collection_before_close(self):
        _, worker, _ = self.reviewed()
        hd.send(worker, self.input); self.report(worker, "Another turn", collect=False)
        self.assert_no_close(worker)

    def test_pane_occupant_mismatch_or_ambiguous_terminal_rejected(self):
        _, worker, _ = self.reviewed()
        pane = next(p for p in self.api.panes if p["pane_id"] == self.agent(worker)["pane_id"])
        original = dict(pane); pane["terminal_id"] = "unrelated"
        self.assert_no_close(worker); pane.update(original)
        self.api.panes.append(dict(pane, pane_id="duplicate"))
        self.assert_no_close(worker)

    def test_reused_original_pane_id_never_closes_unrelated_terminal(self):
        _, worker, _ = self.reviewed()
        agent = self.agent(worker); old = agent["pane_id"]
        pane = next(p for p in self.api.panes if p["pane_id"] == old)
        agent["pane_id"] = "moved-owned-pane"; pane["pane_id"] = "moved-owned-pane"
        self.api.tree = self.api.replace(self.api.tree, old, "moved-owned-pane")
        unrelated = dict(pane, pane_id=old, terminal_id="unrelated-terminal")
        self.api.panes.append(unrelated)
        hd.close(worker)
        self.assertEqual(self.closes(), [("pane", "close", "moved-owned-pane")])
        self.assertIn(unrelated, self.api.panes)

    def test_closed_worker_excluded_from_wait_and_rejects_new_turns(self):
        _, worker, reviewer = self.reviewed()
        hd.close(worker); hd.close(reviewer)
        self.assertEqual(hd.wait(self.run, 0), {"events": [], "pending": 0})
        self.assertTrue(hd.close(worker)["already_closed"])
        for action in (lambda: hd.send(worker, self.input), lambda: fp.prepare(self.run, "worker", self.input, reuse=worker),
                       lambda: fp.publish(worker, self.task(worker)["request_id"], "working"),
                       lambda: hd.collect(worker), lambda: fp.retire_lost(worker, self.input)):
            with self.assertRaises(fp.Failure): action()
        self.assertTrue((Path(worker) / (self.task(worker)["request_id"] + ".result.json")).exists())

    def test_finish_then_close_everything_but_main(self):
        director, worker, reviewer = self.reviewed()
        hd.final_check(self.run, self.input)
        self.decide(director, {"kind": "final_check", "plan_id": "p1",
                               "ac_status": [{"criterion": "Works", "status": "met", "evidence": "tests"}],
                               "findings": [], "plan_divergence": []})
        hd.close(worker)
        self.assertEqual(fp.finish(self.run, self.write("final.md", "Report"))["user_response"], "Report")
        for task in (reviewer, director): hd.close(task)
        self.assertEqual([p["pane_id"] for p in self.api.panes], ["main-pane"])

    def test_empty_execution_region_recreated_after_closes(self):
        director, worker, reviewer = self.reviewed()
        hd.close(worker); hd.close(reviewer)
        self.assertEqual(self.api.tree["second"], self.agent(director)["pane_id"])
        self.replan(director)
        hd.spawn(self.run, "worker", self.input)
        split = self.splits()[-1]
        self.assertEqual((split[2], split[split.index("--direction") + 1], split[split.index("--ratio") + 1]),
                         (self.agent(director)["pane_id"], "down", "0.4"))

    def test_researchers_use_and_release_the_execution_region(self):
        director = self.director()
        self.decide(director, {"kind": "research", "requests": [{"id": "r1", "assignment": "A"}, {"id": "r2", "assignment": "B"}]})
        tasks = [t["task"] for t in hd.relay(self.run)["tasks"]]
        calls = self.splits()
        self.assertEqual([(c[2], c[c.index("--direction") + 1]) for c in calls[1:]],
                         [(self.agent(director)["pane_id"], "down"), (self.agent(tasks[0])["pane_id"], "right")])
        for task in tasks: self.report(task, "facts"); hd.collect(task)
        hd.relay(self.run)
        self.assertEqual(self.api.tree["second"], self.agent(director)["pane_id"])

    def test_uncertain_close_is_recorded_and_never_retried_automatically(self):
        _, worker, _ = self.reviewed()
        original = self.api.call
        def fail(*args):
            if args[:2] == ("pane", "close"):
                original(*args)
                raise fp.Failure("Response lost after actual close")
            return original(*args)
        with patch.object(self.api, "call", side_effect=fail):
            with self.assertRaises(fp.Failure): hd.close(worker)
        before = self.closes()
        self.assert_no_close(worker)
        self.assertEqual(self.closes(), before)
        self.assertIn("pane_id", self.task(worker)["closing"])
        with self.assertRaises(fp.Failure): hd.wait(self.run, 0)


if __name__ == "__main__": unittest.main()
