"""Role layout and release safety against simulated Herdr; no live model claims."""
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

    def evidence(self, worker, reviewer):
        evidence = hd.release_check(worker, reviewer)
        evidence["decision"].update(integrated=True, no_longer_needed=True,
                                    reason="Integrated into the reviewed candidate; all assigned findings resolved.")
        return self.write("release.json", evidence)

    def accept(self, director):
        candidate = fp.candidate(self.run, self.input)
        hd.send(director, self.input)
        self.report(director, {"kind": "accept", "plan_id": fp.run_at(self.run)[1]["plan"]["id"],
                              "candidate_id": candidate["id"], "user_response": "Astra accepted this candidate."})
        hd.collect(director); fp.decision(director)

    def replan(self, director):
        hd.send(director, self.input)
        self.report(director, {"kind": "plan", "plan_id": "p2", "user_response": "Revise implementation",
                              "plan": "Apply the new fix", "acceptance_criteria": ["Fix works"], "verification": ["Test fix"]})
        hd.collect(director); fp.decision(director); fp.start(self.run)

    def assert_no_close(self, worker, evidence=None):
        before = self.closes()
        with self.assertRaises(fp.Failure): hd.release(worker, evidence)
        self.assertEqual(self.closes(), before)
        self.assertFalse(self.task(worker).get("released"))

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

    def test_cli_release_check_is_read_only_and_release_uses_decision(self):
        _, worker, reviewer = self.reviewed()
        before = Path(self.run, "run.json").read_bytes()
        stream = io.StringIO()
        with patch.object(sys, "argv", ["herdr.py", "release-check", "--task", worker, "--reviewer", reviewer]), patch.object(sys, "stdout", stream):
            hd.cli()
        template = json.loads(stream.getvalue())
        self.assertFalse(template["decision"]["integrated"])
        self.assertEqual(Path(self.run, "run.json").read_bytes(), before)
        self.assertEqual(self.closes(), [])
        file = self.evidence(worker, reviewer)
        with patch.object(sys, "argv", ["herdr.py", "release", "--task", worker, "--file", file]): hd.cli()
        self.assertTrue(self.task(worker)["released"])

    def test_worker_requires_explicit_main_decision_after_review(self):
        _, worker, reviewer = self.reviewed()
        self.assert_no_close(worker)
        template = hd.release_check(worker, reviewer)
        self.assert_no_close(worker, self.write("template.json", template))
        for patch_decision in ({"integrated": False}, {"no_longer_needed": False},
                               {"unresolved_findings": ["FP-001 requires this Worker"]}, {"reason": ""}):
            file = self.evidence(worker, reviewer); value = fp.read(file)
            value["decision"].update(patch_decision)
            self.assert_no_close(worker, self.write("invalid.json", value))

    def test_worker_fix_and_rereview_reuse_original_sessions(self):
        _, worker, reviewer = self.reviewed()
        handles = [self.task(t)["handle"] for t in (worker, reviewer)]
        self.report(reviewer, "FINDINGS: FP-001 fix required"); hd.collect(reviewer)
        evidence = fp.read(self.evidence(worker, reviewer))
        evidence["decision"]["unresolved_findings"] = ["FP-001"]
        self.assert_no_close(worker, self.write("finding.json", evidence))
        hd.send(worker, self.input)
        (self.project / "file.txt").write_text("fixed\n")
        self.report(worker, "Fixed FP-001; integrated; tests passed"); hd.collect(worker)
        with self.assertRaises(fp.Failure): hd.release_check(worker, reviewer)
        hd.send(reviewer, self.input)
        self.report(reviewer, "FINDINGS: none; FP-001 resolved"); hd.collect(reviewer)
        self.assertEqual([self.task(t)["handle"] for t in (worker, reviewer)], handles)
        hd.release(worker, self.evidence(worker, reviewer))
        self.assertTrue(self.task(worker)["released"])
        self.assertFalse(self.task(worker)["closed"])
        self.assertFalse(self.task(reviewer).get("released"))

    def test_design_uses_worker_release_policy(self):
        _, design, reviewer = self.reviewed("design")
        hd.release(design, self.evidence(design, reviewer))
        self.assertTrue(self.task(design)["released"])

    def test_astra_and_main_cannot_be_released(self):
        director, worker, reviewer = self.reviewed()
        file = self.evidence(worker, reviewer)
        self.assert_no_close(director)
        self.accept(director); self.assert_no_close(director)
        data = self.task(worker); data["role"] = "main"; fp.atomic(Path(worker) / "task.json", data)
        self.assert_no_close(worker)
        data["role"] = "worker"; fp.atomic(Path(worker) / "task.json", data)
        data["handle"]["terminal_id"] = "main-terminal"; fp.atomic(Path(worker) / "task.json", data)
        self.agent(worker)["terminal_id"] = "main-terminal"
        self.assert_no_close(worker, file)

    def test_active_or_uncollected_or_changed_activity_rejected(self):
        _, worker, reviewer = self.reviewed(); file = self.evidence(worker, reviewer)
        agent = self.agent(worker)
        for change in ({"agent_status": "working"}, {"launch_pending": True}, {"state_change_seq": 999}):
            original = dict(agent); agent.update(change)
            self.assert_no_close(worker, file); agent.clear(); agent.update(original)
        receipt = Path(worker) / "receipt.json"; receipt.unlink()
        self.assert_no_close(worker, file)

    def test_changed_report_or_new_request_invalidates_release_decision(self):
        _, worker, reviewer = self.reviewed(); file = self.evidence(worker, reviewer)
        self.report(worker, "New report"); hd.collect(worker)
        self.assert_no_close(worker, file)
        file = self.evidence(worker, reviewer)
        hd.send(worker, self.input); self.report(worker, "Another turn"); hd.collect(worker)
        self.assert_no_close(worker, file)

    def test_changed_reviewer_report_or_activity_invalidates_decision(self):
        _, worker, reviewer = self.reviewed(); file = self.evidence(worker, reviewer)
        self.report(reviewer, "New finding"); hd.collect(reviewer)
        self.assert_no_close(worker, file)
        file = self.evidence(worker, reviewer)
        self.agent(reviewer)["state_change_seq"] += 1
        self.assert_no_close(worker, file)

    def test_changed_candidate_plan_or_user_input_invalidates_decision(self):
        director, worker, reviewer = self.reviewed(); file = self.evidence(worker, reviewer)
        (self.project / "new.txt").write_text("changed candidate")
        self.assert_no_close(worker, file)
        (self.project / "new.txt").unlink()
        fp.message(self.run, self.input)
        self.assert_no_close(worker, file)
        self.replan(director)
        self.assert_no_close(worker, file)

    def test_new_plan_invalidates_binding_even_after_both_reports_updated(self):
        director, worker, reviewer = self.reviewed(); file = self.evidence(worker, reviewer)
        self.replan(director)
        for task, report in ((worker, "Implementation still satisfies new Plan"), (reviewer, "FINDINGS: none")):
            hd.send(task, self.input); self.report(task, report); hd.collect(task)
        self.assert_no_close(worker, file)
        hd.release(worker, self.evidence(worker, reviewer))

    def test_pane_occupant_mismatch_or_ambiguous_terminal_rejected(self):
        _, worker, reviewer = self.reviewed(); file = self.evidence(worker, reviewer)
        pane = next(p for p in self.api.panes if p["pane_id"] == self.agent(worker)["pane_id"])
        original = dict(pane); pane["terminal_id"] = "unrelated"
        self.assert_no_close(worker, file); pane.update(original)
        self.api.panes.append(dict(pane, pane_id="duplicate"))
        self.assert_no_close(worker, file)

    def test_reused_original_pane_id_never_closes_unrelated_terminal(self):
        _, worker, reviewer = self.reviewed(); file = self.evidence(worker, reviewer)
        agent = self.agent(worker); old = agent["pane_id"]
        pane = next(p for p in self.api.panes if p["pane_id"] == old)
        agent["pane_id"] = "moved-owned-pane"; pane["pane_id"] = "moved-owned-pane"
        self.api.tree = self.api.replace(self.api.tree, old, "moved-owned-pane")
        unrelated = dict(pane, pane_id=old, terminal_id="unrelated-terminal")
        self.api.panes.append(unrelated)
        hd.release(worker, file)
        self.assertEqual(self.closes(), [("pane", "close", "moved-owned-pane")])
        self.assertIn(unrelated, self.api.panes)

    def test_released_worker_excluded_from_wait_but_evidence_retained(self):
        _, worker, reviewer = self.reviewed()
        file = self.evidence(worker, reviewer); hd.release(worker, file)
        self.assertEqual(hd.wait(self.run, 0), {"events": [], "pending": 0})
        self.assertTrue(hd.release(worker)["already_released"])
        for action in (lambda: hd.send(worker, self.input), lambda: fp.prepare(self.run, "worker", self.input, reuse=worker),
                       lambda: fp.publish(worker, self.task(worker)["request_id"], "working"),
                       lambda: hd.collect(worker), lambda: fp.retire_lost(worker, self.input)):
            with self.assertRaises(fp.Failure): action()
        fp.candidate(self.run, self.input)
        data = self.task(worker); data["release"]["review_report"]["report"] = "tampered"
        fp.atomic(Path(worker) / "task.json", data)
        with self.assertRaises(fp.Failure): fp.executors_ready(Path(self.run))

    def test_released_worker_report_tampering_blocks_candidate(self):
        _, worker, reviewer = self.reviewed(); hd.release(worker, self.evidence(worker, reviewer))
        data = self.task(worker); result_path = Path(worker) / (data["request_id"] + ".result.json")
        result = fp.read(result_path); result["report"] = "tampered"; fp.atomic(result_path, result)
        fp.collect(worker)  # Recollecting cannot authorize modification of archived release evidence.
        with self.assertRaises(fp.Failure): fp.candidate(self.run, self.input)

    def test_reviewer_stays_until_exact_candidate_accepted(self):
        director, _, reviewer = self.reviewed()
        self.assert_no_close(reviewer)
        self.accept(director)
        (self.project / "file.txt").write_text("changed after acceptance")
        self.assert_no_close(reviewer)

    def test_reviewer_release_rejects_new_director_activity(self):
        director, _, reviewer = self.reviewed(); self.accept(director)
        self.agent(director)["state_change_seq"] += 1
        self.assert_no_close(reviewer)

    def test_reviewer_release_rejects_new_worker_activity_after_acceptance(self):
        director, worker, reviewer = self.reviewed(); self.accept(director)
        self.agent(worker)["state_change_seq"] += 1
        self.assert_no_close(reviewer)

    def test_herdr_reviewed_release_cannot_be_used_by_native_backend(self):
        director, worker, reviewer = self.reviewed()
        hd.release(worker, self.evidence(worker, reviewer))
        run_file = Path(self.run, "run.json"); state = fp.read(run_file)
        state["backend"] = "subagent"; state.pop("main_identity"); fp.atomic(run_file, state)
        with self.assertRaises(fp.Failure): fp.candidate(self.run, self.input)

    def test_release_then_finish_closes_only_remaining_owned_panes(self):
        director, worker, reviewer = self.reviewed()
        hd.release(worker, self.evidence(worker, reviewer))
        self.accept(director); hd.release(reviewer)
        self.assertEqual(fp.finish(self.run)["user_response"], "Astra accepted this candidate.")
        for task in (worker, reviewer, director): hd.close(task)
        self.assertEqual(len(self.closes()), 3)
        self.assertEqual([p["pane_id"] for p in self.api.panes], ["main-pane"])
        self.assertTrue(all(self.task(t)["closed"] for t in (worker, reviewer, director)))
        self.assertTrue(hd.close(worker)["already_closed"])

    def test_late_astra_revision_assigns_new_worker_keeps_reviewer(self):
        director, worker, reviewer = self.reviewed()
        hd.release(worker, self.evidence(worker, reviewer)); fp.candidate(self.run, self.input)
        self.replan(director)
        new = hd.spawn(self.run, "worker", self.input)["task"]
        self.assertNotEqual(self.task(new)["handle"], self.task(worker)["handle"])
        (self.project / "file.txt").write_text("late fix")
        self.report(new, "Late Astra fix; inherited prior task/report/findings."); hd.collect(new)
        hd.send(reviewer, self.input); self.report(reviewer, "FINDINGS: none after late fix"); hd.collect(reviewer)
        hd.release(new, self.evidence(new, reviewer))
        self.accept(director); fp.finish(self.run)

    def test_empty_execution_region_recreated_and_old_reviewer_not_reused(self):
        director, worker, reviewer = self.reviewed()
        hd.release(worker, self.evidence(worker, reviewer)); self.accept(director); hd.release(reviewer)
        self.assertEqual(self.api.tree["second"], self.agent(director)["pane_id"])
        self.replan(director)
        new = hd.spawn(self.run, "worker", self.input)["task"]
        split = self.splits()[-1]
        self.assertEqual((split[2], split[split.index("--direction") + 1], split[split.index("--ratio") + 1]),
                         (self.agent(director)["pane_id"], "down", "0.4"))
        self.report(new, "New work"); hd.collect(new)
        with self.assertRaises(fp.Failure): fp.candidate(self.run, self.input)
        new_reviewer = hd.spawn(self.run, "reviewer", self.input)["task"]
        self.report(new_reviewer, "FINDINGS: none"); hd.collect(new_reviewer)
        self.accept(director); fp.finish(self.run)

    def test_uncertain_close_is_recorded_and_never_retried_automatically(self):
        _, worker, reviewer = self.reviewed(); file = self.evidence(worker, reviewer)
        original = self.api.call
        def fail(*args):
            if args[:2] == ("pane", "close"):
                original(*args)
                raise fp.Failure("Response lost after actual close")
            return original(*args)
        with patch.object(self.api, "call", side_effect=fail):
            self.assert_no_close_after_timeout(worker, file)
        before = self.closes()
        self.assert_no_close(worker, file)
        self.assertEqual(self.closes(), before)
        self.assertEqual(self.task(worker)["closing"]["operation"], "release")
        with self.assertRaises(fp.Failure): fp.candidate(self.run, self.input)
        with self.assertRaises(fp.Failure): hd.wait(self.run, 0)

    def assert_no_close_after_timeout(self, worker, file):
        with self.assertRaises(fp.Failure): hd.release(worker, file)
        self.assertFalse(self.task(worker).get("released"))


if __name__ == "__main__": unittest.main()
