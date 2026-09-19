from __future__ import annotations

import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "plugins/frontierplan/scripts"))
sys.path.insert(0, str(ROOT / "tools"))
import frontierplan as fp
from validate_plugin import validate
from package_release import package


class Protocol(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.project = self.root / "project"; self.project.mkdir()
        self.env = patch.dict(os.environ, {"CODEX_THREAD_ID": "main-test", "CODEX_SESSION_ID": "", "FRONTIERPLAN_ROLE": "",
                                           "FRONTIERPLAN_MAIN_AGENT": "", "FRONTIERPLAN_MAIN_SESSION_ID": "",
                                           "HERDR_PANE_ID": ""})
        self.env.start()
        self.git("init", "-q")
        self.git("config", "user.email", "tests@example.invalid")
        self.git("config", "user.name", "FrontierPlan tests")
        (self.project / "file.txt").write_text("base\n")
        self.git("add", "."); self.git("commit", "-qm", "base")
        self.input = self.write("input.md", "Please implement the requested feature.")
        self.run = fp.initialize("subagent", str(self.project), self.input)["run"]
        self.addCleanup(shutil.rmtree, self.run, True)
        self.addCleanup(self.env.stop); self.addCleanup(self.temp.cleanup)

    def git(self, *args):
        return subprocess.run(["git", "-C", str(self.project), *args], check=True, capture_output=True).stdout

    def write(self, name, value):
        path = self.root / name
        path.write_text(value if isinstance(value, str) else json.dumps(value), encoding="utf-8")
        return str(path)

    def prepare(self, role, reuse=None):
        return fp.prepare(self.run, role, self.input, reuse=reuse)["task"]

    def report(self, task, value, status="complete", collect=True):
        path, data, _, _ = fp.task_at(task)
        result = fp.publish(task, data["request_id"], status, self.write("report.txt", value))
        if collect: fp.collect(task)
        return result

    def plan(self):
        director = self.prepare("director")
        self.report(director, {"kind": "plan", "plan_id": "plan-1", "user_response": "Plan ready.",
                              "plan": "Implement the requested feature.", "acceptance_criteria": ["It works."], "verification": ["Run tests."]})
        fp.decision(director)
        return director

    def executing(self):
        director = self.plan(); fp.authorize(self.run, 1); fp.start(self.run)
        return director

    def ready_candidate(self):
        director = self.executing()
        worker = self.prepare("worker"); self.report(worker, "Implemented; tests actually passed.")
        reviewer = self.prepare("reviewer"); self.report(reviewer, "FINDINGS: none")
        candidate = fp.candidate(self.run, self.write("evidence.md", "Diff; tests; findings; risk evidence."))
        return director, worker, reviewer, candidate

    def accepted(self):
        director, worker, reviewer, candidate = self.ready_candidate()
        self.prepare("director", reuse=director)
        self.report(director, {"kind": "accept", "plan_id": "plan-1", "candidate_id": candidate["id"], "user_response": "Astra's final report."})
        fp.decision(director)
        return director, worker, reviewer, candidate

    def test_only_director_before_implementation(self):
        for role in ("worker", "design", "reviewer"):
            with self.subTest(role=role), self.assertRaises(fp.Failure): self.prepare(role)
        self.prepare("director")

    def test_plan_is_not_authorization(self):
        self.plan()
        with self.assertRaises(fp.Failure): fp.start(self.run)
        with self.assertRaises(fp.Failure): self.prepare("worker")

    def test_authorization_is_not_plan(self):
        fp.authorize(self.run, 1)
        with self.assertRaises(fp.Failure): fp.start(self.run)

    def test_authorization_reference_must_exist(self):
        with self.assertRaises(fp.Failure): fp.authorize(self.run, 99)

    def test_duplicate_director_rejected(self):
        self.prepare("director")
        with self.assertRaises(fp.Failure): self.prepare("director")

    def test_packet_requires_personal_research_and_no_recursion(self):
        task = self.prepare("director")
        body = Path(fp.task_at(task)[1]["packet"]).read_text()
        self.assertIn("Do NOT\nspawn agents or ask Main/Luna to research", body)
        self.assertIn("Latest user input:", body)

    def test_plan_must_be_director_report(self):
        self.executing(); task = self.prepare("worker")
        self.report(task, "Done")
        with self.assertRaises(fp.Failure): fp.decision(task)

    def test_must_collect_before_decision(self):
        task = self.prepare("director")
        self.report(task, {"kind":"reply", "user_response":"Hello"}, collect=False)
        with self.assertRaises(fp.Failure): fp.decision(task)

    def test_same_session_continuation(self):
        task = self.plan()
        previous = fp.task_at(task)[1]["request_id"]
        again = self.prepare("director", reuse=task)
        self.assertEqual(task, again)
        self.assertNotEqual(previous, fp.task_at(task)[1]["request_id"])
        with self.assertRaises(fp.Failure): fp.publish(task, previous, "complete", self.input)

    def test_cannot_continue_uncollected_turn(self):
        task = self.prepare("director")
        with self.assertRaises(fp.Failure): self.prepare("director", reuse=task)

    def test_begin_invalidates_old_report(self):
        task = self.plan(); data = fp.task_at(task)[1]
        fp.publish(task, data["request_id"], "working")
        with self.assertRaises(fp.Failure): fp.collected(Path(task), data)

    def test_message_is_stored_verbatim(self):
        msg = "Mainの解釈ではなく、原文を渡して。\nDo not change scope.\n"
        info = fp.message(self.run, self.write("new.md", msg))
        self.assertEqual(Path(info["file"]).read_text(), msg)

    def test_message_stops_new_dispatch(self):
        self.executing(); fp.message(self.run, self.input)
        with self.assertRaises(fp.Failure): self.prepare("worker")

    def test_stale_director_message_rejected(self):
        task = self.prepare("director")
        self.report(task, {"kind":"reply", "user_response":"Old"})
        fp.message(self.run, self.input)
        with self.assertRaises(fp.Failure): fp.decision(task)

    def test_explicit_continuing_plan_resumes(self):
        task = self.executing(); fp.message(self.run, self.input)
        self.prepare("director", reuse=task)
        self.report(task, {"kind":"reply", "continue_plan_id":"plan-1", "user_response":"Same plan applies."})
        fp.decision(task); fp.start(self.run); self.prepare("worker")

    def test_replan_requires_new_plan_id(self):
        task = self.plan(); self.prepare("director", reuse=task)
        self.report(task, {"kind":"plan", "plan_id":"plan-1", "user_response":"Changed", "plan":"Changed", "acceptance_criteria":["x"], "verification":["x"]})
        with self.assertRaises(fp.Failure): fp.decision(task)

    def test_unknown_research_delegation_kind_rejected(self):
        task = self.prepare("director")
        self.report(task, {"kind":"research", "user_response":"Ask Luna"})
        with self.assertRaises(fp.Failure): fp.decision(task)

    def test_missing_plan_criteria_rejected(self):
        task = self.prepare("director")
        self.report(task, {"kind":"plan", "plan_id":"p", "user_response":"x", "plan":"x"})
        with self.assertRaises(fp.Failure): fp.decision(task)

    def test_duplicate_decision_rejected(self):
        task = self.plan()
        with self.assertRaises(fp.Failure): fp.decision(task)

    def test_review_required(self):
        self.executing()
        with self.assertRaises(fp.Failure): fp.candidate(self.run, self.input)

    def test_review_candidate_changes_while_reviewing(self):
        self.executing(); task = self.prepare("reviewer")
        (self.project / "file.txt").write_text("changed")
        with self.assertRaises(fp.Failure): self.report(task, "FINDINGS: none")
        self.report(task, "Candidate changed", status="blocked")

    def test_review_must_match_latest_candidate(self):
        self.executing(); task = self.prepare("reviewer"); self.report(task, "FINDINGS: none")
        (self.project / "untracked.txt").write_text("new")
        with self.assertRaises(fp.Failure): fp.candidate(self.run, self.input)
        self.prepare("reviewer", reuse=task); self.report(task, "FINDINGS: none")
        fp.candidate(self.run, self.input)

    def test_review_must_match_current_plan_even_without_code_change(self):
        director = self.executing()
        reviewer = self.prepare("reviewer"); self.report(reviewer, "FINDINGS: none")
        self.prepare("director", reuse=director)
        self.report(director, {"kind":"plan", "plan_id":"plan-2", "user_response":"New criteria", "plan":"Changed criteria", "acceptance_criteria":["New requirement"], "verification":["Check it"]})
        fp.decision(director); fp.start(self.run)
        with self.assertRaises(fp.Failure): fp.candidate(self.run, self.input)
        self.prepare("reviewer", reuse=reviewer); self.report(reviewer, "FINDINGS: none")
        fp.candidate(self.run, self.input)

    def test_acceptance_full_flow(self):
        director, worker, reviewer, _ = self.accepted()
        result = fp.finish(self.run)
        self.assertEqual(result["user_response"], "Astra's final report.")
        for task in (worker, reviewer, director): fp.close_record(task)

    def test_main_cannot_finish_without_acceptance(self):
        self.ready_candidate()
        with self.assertRaises(fp.Failure): fp.finish(self.run)

    def test_wrong_candidate_rejected(self):
        task, _, _, _ = self.ready_candidate(); self.prepare("director", reuse=task)
        self.report(task, {"kind":"accept", "plan_id":"plan-1", "candidate_id":"wrong", "user_response":"Done"})
        with self.assertRaises(fp.Failure): fp.decision(task)

    def test_changes_after_acceptance_rejected(self):
        self.accepted(); (self.project / "file.txt").write_text("after acceptance")
        with self.assertRaises(fp.Failure): fp.finish(self.run)

    def test_new_user_message_after_acceptance_rejected(self):
        self.accepted(); fp.message(self.run, self.input)
        with self.assertRaises(fp.Failure): fp.finish(self.run)

    def test_premature_close_rejected(self):
        task = self.plan()
        with self.assertRaises(fp.Failure): fp.close_record(task)

    def test_discussion_can_finish_without_implementation(self):
        task = self.prepare("director"); self.report(task, {"kind":"reply", "user_response":"Design advice."})
        fp.decision(task)
        self.assertEqual(fp.finish(self.run, discussion=True)["user_response"], "Design advice.")

    def test_implementation_cannot_finish_as_discussion(self):
        self.ready_candidate()
        with self.assertRaises(fp.Failure): fp.finish(self.run, discussion=True)

    def test_native_id_cannot_be_reused_for_another_role(self):
        director = self.executing()
        handle = self.write("handle.json", {"agent_id":"actual-id", "evidence":"tool result"})
        fp.bind(director, handle)
        worker = self.prepare("worker")
        with self.assertRaises(fp.Failure): fp.bind(worker, handle)

    def test_lost_director_recovery(self):
        task = self.plan(); fp.retire_lost(task, self.write("lost.md", "Runtime reports the session missing."))
        self.assertNotEqual(task, self.prepare("director"))

    def test_wrong_main_identity_rejected(self):
        with patch.dict(os.environ, {"CODEX_THREAD_ID":"other"}):
            with self.assertRaises(fp.Failure): self.prepare("director")

    def test_child_cannot_manage_run(self):
        with patch.dict(os.environ, {"FRONTIERPLAN_ROLE":"director"}):
            with self.assertRaises(fp.Failure): self.prepare("director")

    def test_stale_lock_not_removed_automatically(self):
        target = Path(self.run) / ".state.lock"; target.write_text("999999")
        with self.assertRaises(fp.Failure): self.prepare("director")
        self.assertTrue(target.exists())

    def test_fingerprint_tracks_index_and_untracked(self):
        initial = fp.snapshot(str(self.project))["id"]
        (self.project / "new.txt").write_text("new")
        untracked = fp.snapshot(str(self.project))["id"]
        self.git("add", "new.txt")
        staged = fp.snapshot(str(self.project))["id"]
        self.assertEqual(len({initial, untracked, staged}), 3)

    def test_symlink_target_not_followed(self):
        outside = self.root / "outside"; outside.write_text("secret")
        (self.project / "link").symlink_to(outside)
        first = fp.snapshot(str(self.project))["id"]
        outside.write_text("changed external content")
        self.assertEqual(first, fp.snapshot(str(self.project))["id"])

    def test_profiles_role_specific_lowercase(self):
        for role in fp.CHILDREN:
            with self.subTest(role=role):
                self.assertIn(fp.profile(role)["reasoning_effort"], ("xhigh", "max"))
        self.assertEqual(fp.profile("main"), {"role": "main", "inherit_session": True})
        with self.assertRaises(fp.Failure): fp.profile("director", "fable")

    def test_package_and_extracted_integrity(self):
        self.assertEqual(validate(ROOT / "plugins/frontierplan"), [])
        archives = package(self.root / "dist")
        self.assertEqual(len(archives), 2)
        self.assertTrue(all(p.exists() for p in archives))


if __name__ == "__main__": unittest.main()
