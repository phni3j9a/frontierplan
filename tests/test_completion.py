"""Completion delivery and assignment handoff regressions; all agents are simulated."""
from pathlib import Path
import io
import sys
import unittest
from unittest.mock import patch

import test_frontierplan as base
import test_herdr as transport
import test_herdr_lifecycle as lifecycle
import frontierplan as fp
import herdr as hd


class Completion(unittest.TestCase):
    setUp = base.Protocol.setUp
    git = base.Protocol.git
    write = base.Protocol.write
    report = base.Protocol.report
    setup_api = transport.HerdrTransport.setup_api
    director = transport.HerdrTransport.director
    director_plan = transport.HerdrTransport.director_plan

    def test_lost_wait_output_does_not_acknowledge_complete_or_blocked(self):
        director = self.director()
        for status, report in (("complete", {"kind": "reply", "user_response": "Ready"}),
                               ("blocked", "Missing prerequisite")):
            with self.subTest(status=status):
                self.report(director, report, status=status, collect=False)
                first = hd.wait(self.run, 0)
                second = hd.wait(self.run, 0)
                self.assertEqual(first["events"], [{"task": director, "event": "report"}])
                self.assertEqual(second, first)
                self.assertEqual(len(fp.uncollected_reports(Path(self.run))), 1)
                hd.collect(director)
                self.assertEqual(fp.uncollected_reports(Path(self.run)), [])
        self.assertEqual(hd.check(self.run)["events"], [{"task": director, "event": "blocked"}])

    def test_existing_uncollected_report_is_visible_without_notification_history(self):
        director = self.director()
        self.report(director, {"kind": "reply", "user_response": "Ready"}, collect=False)
        hd.wait(self.run, 0)
        before = (Path(self.run) / "wait-notices.json").read_bytes()
        with fp.lock(Path(self.run) / ".wait.lock"):
            self.assertEqual(hd.check(self.run)["events"][0]["event"], "report")
        self.assertEqual((Path(self.run) / "wait-notices.json").read_bytes(), before)
        self.assertFalse((Path(director) / "receipt.json").exists())

    def test_same_file_working_to_complete_wakes_existing_waiter(self):
        director = self.director(); task = fp.task_at(director)[1]
        fp.publish(director, task["request_id"], "working")
        agent = self.api.registered[task["name"]]; agent["agent_status"] = "working"
        def complete(_):
            self.report(director, {"kind": "reply", "user_response": "Ready"}, collect=False)
            agent.update(agent_status="idle", state_change_seq=3)
        with patch.object(hd.time, "sleep", side_effect=complete):
            result = hd.wait(self.run)
        self.assertEqual(result["events"], [{"task": director, "event": "report"}])
        hd.collect(director)
        self.assertEqual(hd.check(self.run), {"events": [], "pending": 0})

    def test_published_report_requires_idle_before_collection(self):
        director = self.director(); task = fp.task_at(director)[1]
        self.report(director, {"kind": "reply", "user_response": "Ready"}, collect=False)
        agent = self.api.registered[task["name"]]; agent["agent_status"] = "working"
        self.assertEqual(hd.check(self.run)["events"][0]["event"], "report_waiting_idle")
        with self.assertRaises(fp.Failure): hd.collect(director)
        agent["agent_status"] = "idle"
        self.assertEqual(hd.wait(self.run, 0)["events"][0]["event"], "report")

    def test_old_request_does_not_satisfy_new_assignment(self):
        director = self.director()
        self.report(director, {"kind": "reply", "user_response": "First"}); hd.collect(director)
        old = fp.task_at(director)[1]["request_id"]
        hd.send(director, self.input)
        self.assertNotEqual(fp.task_at(director)[1]["request_id"], old)
        self.assertEqual(fp.uncollected_reports(Path(self.run)), [])
        self.assertEqual(hd.check(self.run), {"events": [], "pending": 1})

    def test_five_minute_heartbeat_keeps_unresolved_conditions_visible(self):
        director = self.director()
        self.report(director, "Missing prerequisite", status="blocked"); hd.collect(director)
        hd.wait(self.run, 0)
        clock = [0.0]
        def advance(seconds): clock[0] += seconds
        with patch.object(hd.time, "monotonic", side_effect=lambda: clock[0]), patch.object(hd.time, "sleep", side_effect=advance):
            result = hd.wait(self.run)
        self.assertEqual(clock[0], 300)
        self.assertEqual(result, {"events": [{"task": director, "event": "blocked"}], "pending": 1, "timeout": True})
        for invalid in (-1, 301, 3600):
            with self.assertRaises(fp.Failure): hd.wait(self.run, invalid)

    def test_cli_check_and_default_wait(self):
        director = self.director()
        self.report(director, {"kind": "reply", "user_response": "Ready"}, collect=False)
        for action in ("check", "wait"):
            stream = io.StringIO()
            with patch.object(sys, "argv", ["herdr.py", action, "--run", self.run]), patch.object(sys, "stdout", stream):
                hd.cli()
            self.assertIn('"report"', stream.getvalue())


class AssignmentRelease(unittest.TestCase):
    setUp = base.Protocol.setUp
    git = base.Protocol.git
    write = base.Protocol.write
    report = base.Protocol.report
    setup_api = transport.HerdrTransport.setup_api
    director = transport.HerdrTransport.director
    director_plan = transport.HerdrTransport.director_plan
    task = lifecycle.Lifecycle.task
    agent = lifecycle.Lifecycle.agent
    accept = lifecycle.Lifecycle.accept

    def worker(self, role="worker"):
        director = self.director(); self.director_plan(director)
        worker = hd.spawn(self.run, role, self.input)["task"]
        self.report(worker, "Assignment integrated. Tests passed. Review still required."); hd.collect(worker)
        return director, worker

    def evidence(self, worker):
        evidence = hd.release_check(worker)
        evidence["decision"].update(integrated=True, assignment_complete=True,
                                    no_active_processes=True, no_longer_needed=True,
                                    reason="Assignment complete; any review fixes go to a fresh Worker.")
        return self.write("assignment-release.json", evidence)

    def test_release_before_review_then_fresh_fix_and_same_reviewer(self):
        director, worker = self.worker()
        hd.release(worker, self.evidence(worker))
        self.assertEqual(hd.check(self.run)["pending"], 0)
        with self.assertRaises(fp.Failure): fp.candidate(self.run, self.input)
        reviewer = hd.spawn(self.run, "reviewer", self.input)["task"]
        self.report(reviewer, "FP-001: concrete defect"); hd.collect(reviewer)
        fix = hd.spawn(self.run, "worker", self.input)["task"]
        self.assertNotEqual(self.task(fix)["handle"], self.task(worker)["handle"])
        (self.project / "file.txt").write_text("fixed\n")
        self.report(fix, "FP-001 fixed and verified"); hd.collect(fix)
        hd.release(fix, self.evidence(fix))
        with self.assertRaises(fp.Failure): fp.candidate(self.run, self.input)
        handle = self.task(reviewer)["handle"]
        hd.send(reviewer, self.input); self.report(reviewer, "FP-001 resolved; FINDINGS: none"); hd.collect(reviewer)
        self.assertEqual(handle, self.task(reviewer)["handle"])
        self.accept(director); hd.release(reviewer); fp.finish(self.run)
        for task in (worker, fix, reviewer, director): hd.close(task)
        self.assertEqual(len([c for c in self.api.calls if c[:2] == ("pane", "close")]), 4)
        self.assertTrue((Path(worker) / (self.task(worker)["request_id"] + ".result.json")).exists())

    def test_design_can_finish_before_review(self):
        _, design = self.worker("design")
        hd.release(design, self.evidence(design))
        self.assertTrue(self.task(design)["released"])

    def test_herdr_assignment_release_cannot_be_used_by_native_backend(self):
        _, worker = self.worker(); hd.release(worker, self.evidence(worker))
        path, state = fp.run_at(self.run)
        state["backend"] = "subagent"; fp.atomic(path / "run.json", state)
        with self.assertRaises(fp.Failure): fp.executors_ready(path)

    def test_release_requires_explicit_decision_and_current_activity(self):
        _, worker = self.worker()
        template = hd.release_check(worker)
        with self.assertRaises(fp.Failure): hd.release(worker, self.write("blank.json", template))
        file = self.evidence(worker)
        self.agent(worker)["agent_status"] = "working"
        with self.assertRaises(fp.Failure): hd.release(worker, file)
        self.agent(worker)["agent_status"] = "idle"
        self.agent(worker)["state_change_seq"] += 1
        with self.assertRaises(fp.Failure): hd.release(worker, file)
        hd.collect(worker)
        with self.assertRaises(fp.Failure): hd.release(worker, file)
        evidence = fp.read(self.evidence(worker)); evidence["decision"]["no_active_processes"] = False
        with self.assertRaises(fp.Failure): hd.release(worker, self.write("active.json", evidence))
        self.assertFalse(any(c[:2] == ("pane", "close") for c in self.api.calls))

    def test_release_rejects_stale_candidate_uncollected_report_and_other_terminal(self):
        _, worker = self.worker(); file = self.evidence(worker)
        (self.project / "file.txt").write_text("changed\n")
        with self.assertRaises(fp.Failure): hd.release(worker, file)
        file = self.evidence(worker)
        self.report(worker, "New report", collect=False)
        with self.assertRaises(fp.Failure): hd.release(worker, file)
        hd.collect(worker); file = self.evidence(worker)
        self.agent(worker)["terminal_id"] = "unrelated"
        with self.assertRaises(fp.Failure): hd.release(worker, file)
        self.assertFalse(any(c[:2] == ("pane", "close") for c in self.api.calls))

    def test_archived_assignment_report_cannot_be_replaced_or_reused(self):
        _, worker = self.worker(); hd.release(worker, self.evidence(worker))
        with self.assertRaises(fp.Failure): hd.send(worker, self.input)
        path, task, _, _ = fp.task_at(worker)
        result_file = path / (task["request_id"] + ".result.json")
        result = fp.read(result_file); result["report"] = "changed"
        fp.atomic(result_file, result); fp.collect(worker)
        with self.assertRaises(fp.Failure): fp.executors_ready(Path(self.run))


class NativeAssignmentRelease(unittest.TestCase):
    setUp = base.Protocol.setUp
    git = base.Protocol.git
    write = base.Protocol.write
    report = base.Protocol.report
    prepare = base.Protocol.prepare
    plan = base.Protocol.plan
    executing = base.Protocol.executing

    def setup_worker(self):
        director = self.executing(); worker = self.prepare("worker")
        fp.bind(worker, self.write("handle.json", {"agent_id": "worker-native-1", "evidence": "Actual tool launch reference"}))
        self.report(worker, "Integrated; tests passed")
        evidence = fp.assignment_release_check(worker)
        evidence["decision"].update(integrated=True, assignment_complete=True, no_active_processes=True,
                                    no_longer_needed=True, reason="Use fresh worker for later fixes")
        closure = {"agent_id": "worker-native-1", "closed": True, "evidence": "Actual close tool result reference"}
        return director, worker, self.write("release.json", evidence), self.write("closure.json", closure)

    def test_native_closed_worker_preserves_evidence_until_acceptance(self):
        director, worker, file, closure = self.setup_worker()
        fp.release_record(worker, file, closure)
        self.assertEqual(fp.uncollected_reports(Path(self.run)), [])
        with self.assertRaises(fp.Failure): fp.candidate(self.run, self.input)
        reviewer = self.prepare("reviewer"); self.report(reviewer, "FINDINGS: none")
        candidate = fp.candidate(self.run, self.input)
        self.prepare("director", reuse=director)
        self.report(director, {"kind": "accept", "plan_id": "plan-1", "candidate_id": candidate["id"], "user_response": "Accepted"})
        fp.decision(director); fp.finish(self.run)
        for task in (worker, reviewer, director): fp.close_record(task)
        self.assertTrue(fp.task_at(worker)[1]["closed"])

    def test_native_close_result_identity_and_success_are_required(self):
        _, worker, file, closure = self.setup_worker()
        for change in ({"agent_id": "other"}, {"closed": False}, {"evidence": ""}):
            data = fp.read(closure); data.update(change)
            with self.assertRaises(fp.Failure): fp.release_record(worker, file, self.write("invalid.json", data))
        self.assertFalse(fp.task_at(worker)[1].get("released"))

    def test_native_new_result_invalidates_preclosure_decision(self):
        _, worker, file, closure = self.setup_worker()
        self.report(worker, "New direct instruction and result")
        with self.assertRaises(fp.Failure): fp.release_record(worker, file, closure)

    def test_native_release_cannot_be_used_by_herdr_backend(self):
        _, worker, file, closure = self.setup_worker()
        fp.release_record(worker, file, closure)
        path, state = fp.run_at(self.run)
        state["backend"] = "herdr"; fp.atomic(path / "run.json", state)
        with self.assertRaises(fp.Failure): fp.executors_ready(path)

    def test_director_and_reviewer_cannot_use_assignment_release(self):
        director, _, _, _ = self.setup_worker()
        reviewer = self.prepare("reviewer"); self.report(reviewer, "FINDINGS: none")
        for task in (director, reviewer):
            with self.assertRaises(fp.Failure): fp.assignment_release_check(task)


if __name__ == "__main__": unittest.main()
