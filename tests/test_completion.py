"""Completion delivery regressions; all agents are simulated."""
from pathlib import Path
import io
import sys
import unittest
from unittest.mock import patch

import test_frontierplan as base
import test_herdr as transport
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
        fp.decision(director)
        old = fp.task_at(director)[1]["request_id"]
        fp.message(self.run, self.input); hd.forward(self.run)
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


if __name__ == "__main__": unittest.main()
