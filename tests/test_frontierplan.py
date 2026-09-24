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

PLAN = {"kind": "plan", "plan_id": "plan-1", "user_response": "Plan ready.",
        "plan": "Implement the requested feature.", "acceptance_criteria": ["It works."],
        "verification": ["Focused: unit tests.", "Final (once): full suite."]}
FINAL = {"kind": "final_check", "plan_id": "plan-1",
         "ac_status": [{"criterion": "It works.", "status": "met", "evidence": "unit tests"}],
         "findings": [], "plan_divergence": []}


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
        _, data, _, _ = fp.task_at(task)
        result = fp.publish(task, data["request_id"], status, self.write("report.txt", value))
        if collect: fp.collect(task)
        return result

    def decide(self, task, value):
        self.report(task, value)
        return fp.decision(task)

    def director(self):
        return fp.start_director(self.run)["task"]

    def plan(self, authorized=True):
        director = self.director()
        self.decide(director, dict(PLAN, authorization_message=1) if authorized else PLAN)
        return director

    def executing(self):
        director = self.plan(); fp.start(self.run)
        return director

    def reviewed(self):
        director = self.executing()
        worker = self.prepare("worker"); self.report(worker, "Implemented; tests actually passed.")
        reviewer = self.prepare("reviewer"); self.report(reviewer, "FINDINGS: none")
        return director, worker, reviewer

    def final_checked(self):
        director, worker, reviewer = self.reviewed()
        fp.final_check(self.run, self.write("evidence.md", "Criteria map; diff; tests; findings."))
        self.decide(director, FINAL)
        return director, worker, reviewer

    def state(self):
        return fp.run_at(self.run)[1]

    # Planning: Astra judges, Main relays.

    def test_only_director_before_implementation(self):
        self.director()
        for role in ("worker", "design", "reviewer"):
            with self.subTest(role=role), self.assertRaises(fp.Failure): self.prepare(role)
        with self.assertRaises(fp.Failure): fp.prepare(self.run, "researcher", material="Look around.")

    def test_director_packet_names_contract_and_user_words(self):
        facts = self.write("facts.md", "Worktree: /tmp/wt")
        packet = Path(fp.start_director(self.run, facts)["packet"]).read_text()
        self.assertIn("core/astra.md", packet)
        self.assertIn("messages/1.md", packet)
        self.assertIn("Worktree: /tmp/wt", packet)
        self.assertIn("not user authority", packet)
        self.assertIn("No delegation", packet)

    def test_research_relay_is_verbatim_and_returns_reports(self):
        director = self.director()
        out = self.decide(director, {"kind": "research", "requests": [
            {"id": "r1", "assignment": "Survey module A exactly."},
            {"id": "r2", "assignment": "Collect CI history."}]})
        self.assertEqual(out["next"], "relay")
        step = fp.relay(self.run)
        self.assertEqual(step["action"], "spawn_researchers")
        self.assertEqual([t["research_id"] for t in step["tasks"]], ["r1", "r2"])
        packet = Path(step["tasks"][0]["packet"]).read_text()
        self.assertIn("Survey module A exactly.", packet)
        self.assertIn("read-only", packet)
        self.assertEqual(step["tasks"][0]["profile"]["model"], "gpt-6-luna")
        for i, item in enumerate(step["tasks"]):
            fp.bind(item["task"], self.write(f"h{i}.json", {"agent_id": f"r{i}", "evidence": "spawned"}))
        self.assertEqual(fp.relay(self.run)["action"], "wait")
        self.report(step["tasks"][0]["task"], "Module A facts.")
        self.report(step["tasks"][1]["task"], "CI history unavailable.", status="blocked")
        back = fp.relay(self.run)
        self.assertEqual(back["action"], "return_to_director")
        self.assertEqual(back["director"]["task"], director)
        text = Path(back["director"]["packet"]).read_text()
        self.assertIn("r1 (complete)", text); self.assertIn("r2 (blocked)", text)
        self.assertIn("research_results", text)
        with self.assertRaises(fp.Failure): fp.relay(self.run)

    def test_user_message_during_research_returns_with_results(self):
        director = self.director()
        self.decide(director, {"kind": "research", "requests": [{"id": "r1", "assignment": "A"}]})
        task = fp.relay(self.run)["tasks"][0]["task"]
        fp.bind(task, self.write("h.json", {"agent_id": "r1", "evidence": "spawned"}))
        out = fp.message(self.run, self.write("m2.md", "Also check B."))
        self.assertEqual(out["next"], "relay")
        with self.assertRaises(fp.Failure): fp.forward(self.run)
        self.report(task, "A facts.")
        packet = Path(fp.relay(self.run)["director"]["packet"]).read_text()
        self.assertIn("messages/2.md", packet)
        self.decide(director, dict(PLAN, authorization_message=1))  # Not stale: Astra saw message 2.

    def test_relay_does_not_duplicate_after_partial_preparation(self):
        director = self.director()
        self.decide(director, {"kind": "research", "requests": [{"id": "r1", "assignment": "A"}, {"id": "r2", "assignment": "B"}]})
        real = fp.prepare; calls = []
        def flaky(*args, **kwargs):
            calls.append(1)
            if len(calls) == 2: raise fp.Failure("interrupted")
            return real(*args, **kwargs)
        with patch.object(fp, "prepare", side_effect=flaky):
            with self.assertRaises(fp.Failure): fp.relay(self.run)
        step = fp.relay(self.run)
        self.assertEqual([t["research_id"] for t in step["tasks"]], ["r1", "r2"])
        self.assertEqual(sum(t["role"] == "researcher" for _, t in fp.tasks(Path(self.run))), 2)

    def test_research_requests_are_validated(self):
        director = self.director()
        self.report(director, {"kind": "research", "requests": [{"id": "r1"}]})
        with self.assertRaises(fp.Failure): fp.decision(director)

    def test_reply_is_relayed_verbatim(self):
        director = self.director()
        out = self.decide(director, {"kind": "reply", "user_response": "推奨: A案。B案は重い。"})
        self.assertEqual(out["next"], "relay_to_user")
        self.assertEqual(out["relay_to_user"], "推奨: A案。B案は重い。")

    def test_presented_plan_waits_for_user_then_authorize(self):
        director = self.plan(authorized=False)
        self.assertEqual(self.state()["phase"], "planned")
        with self.assertRaises(fp.Failure): fp.start(self.run)
        with self.assertRaises(fp.Failure): self.prepare("worker")
        self.assertTrue(fp.message(self.run, self.write("m2.md", "A案で進めて"))["forward_to_director"])
        with self.assertRaises(fp.Failure): fp.start(self.run)
        packet = Path(fp.forward(self.run)["packet"]).read_text()
        self.assertIn("messages/2.md", packet); self.assertNotIn("messages/1.md\n", packet)
        out = self.decide(director, {"kind": "authorize", "plan_id": "plan-1", "authorization_message": 2})
        self.assertEqual(out["next"], "start")
        self.assertEqual(fp.start(self.run)["phase"], "executing")

    def test_plan_with_authorization_starts(self):
        director = self.director()
        out = self.decide(director, dict(PLAN, authorization_message=1))
        self.assertEqual(out["next"], "relay_to_user_then_start")
        self.assertEqual(fp.start(self.run)["phase"], "executing")

    def test_authorization_must_name_existing_message_and_current_plan(self):
        director = self.director()
        self.report(director, dict(PLAN, authorization_message=5))
        with self.assertRaises(fp.Failure): fp.decision(director)
        self.decide(director, PLAN)
        fp.message(self.run, self.write("m2.md", "OK")); fp.forward(self.run)
        self.report(director, {"kind": "authorize", "plan_id": "other", "authorization_message": 2})
        with self.assertRaises(fp.Failure): fp.decision(director)

    def test_new_planning_message_voids_authorization(self):
        director = self.director()
        self.decide(director, dict(PLAN, authorization_message=1))
        fp.message(self.run, self.write("m2.md", "やっぱり実装は待って"))
        fp.forward(self.run)
        with self.assertRaises(fp.Failure): fp.start(self.run)
        self.decide(director, {"kind": "reply", "user_response": "止めました。"})
        with self.assertRaises(fp.Failure): fp.start(self.run)
        fp.message(self.run, self.write("m3.md", "やはり進めて")); fp.forward(self.run)
        self.decide(director, {"kind": "research", "requests": [{"id": "r1", "assignment": "A"}]})
        with self.assertRaises(fp.Failure): fp.start(self.run)

    def test_blocked_report_is_a_blocked_decision(self):
        director = self.director()
        self.report(director, "The GitHub connector is unavailable.", status="blocked")
        out = fp.decision(director)
        self.assertEqual(out["decision"]["kind"], "blocked")
        self.assertEqual(out["relay_to_user"], "The GitHub connector is unavailable.")
        fp.message(self.run, self.write("m2.md", "Connected now.")); fp.forward(self.run)
        self.report(director, {"kind": "blocked", "user_response": "Still missing access."}, status="blocked")
        self.assertEqual(fp.decision(director)["relay_to_user"], "Still missing access.")

    def test_user_message_during_turn_makes_planning_decision_stale(self):
        director = self.director()
        fp.message(self.run, self.write("m2.md", "Also support dark mode."))
        self.report(director, dict(PLAN, authorization_message=1))
        with self.assertRaises(fp.Failure): fp.decision(director)
        fp.forward(self.run)
        self.decide(director, dict(PLAN, authorization_message=1))
        self.assertEqual(fp.start(self.run)["phase"], "executing")

    def test_message_is_stored_verbatim(self):
        value = "Exact wording\nwith line breaks"
        stored = fp.message(self.run, self.write("m.md", value))
        self.assertEqual(Path(stored["file"]).read_text(), value)

    def test_execution_messages_go_to_main(self):
        self.executing()
        out = fp.message(self.run, self.write("m2.md", "Rename the button."))
        self.assertEqual(out["next"], "main_decides")
        with self.assertRaises(fp.Failure): fp.forward(self.run)

    def test_decision_kind_must_match_turn(self):
        director = self.director()
        for value in ({"kind": "advice", "advice": "x"}, FINAL, {"kind": "accept", "user_response": "x"}):
            with self.subTest(kind=value["kind"]):
                self.report(director, value)
                with self.assertRaises(fp.Failure): fp.decision(director)

    def test_replan_requires_new_plan_id(self):
        director = self.plan(authorized=False)
        fp.message(self.run, self.write("m2.md", "Change it.")); fp.forward(self.run)
        self.report(director, PLAN)
        with self.assertRaises(fp.Failure): fp.decision(director)

    def test_missing_plan_fields_rejected(self):
        director = self.director()
        self.report(director, dict(PLAN, acceptance_criteria=[]))
        with self.assertRaises(fp.Failure): fp.decision(director)

    def test_must_collect_before_decision_and_no_duplicate(self):
        director = self.director()
        self.report(director, {"kind": "reply", "user_response": "x"}, collect=False)
        with self.assertRaises(fp.Failure): fp.decision(director)
        fp.collect(director); fp.decision(director)
        with self.assertRaises(fp.Failure): fp.decision(director)

    def test_begin_invalidates_old_report(self):
        director = self.director()
        self.report(director, {"kind": "reply", "user_response": "old"}, collect=False)
        fp.publish(director, fp.task_at(director)[1]["request_id"], "working")
        with self.assertRaises(fp.Failure): fp.collect(director)

    def test_discussion_finish(self):
        director = self.director()
        self.decide(director, {"kind": "reply", "user_response": "Advice only."})
        self.assertEqual(fp.finish(self.run, discussion=True)["user_response"], "Advice only.")

    def test_one_director(self):
        self.director()
        with self.assertRaises(fp.Failure): self.director()

    # Execution: Main coordinates.

    def test_worker_keeps_session_for_fixes(self):
        self.executing()
        worker = self.prepare("worker"); self.report(worker, "Implemented.")
        again = fp.prepare(self.run, "worker", self.input, reuse=worker)
        self.assertEqual(again["task"], worker)

    def test_cannot_continue_uncollected_turn(self):
        self.executing()
        worker = self.prepare("worker"); self.report(worker, "Implemented.", collect=False)
        with self.assertRaises(fp.Failure): self.prepare("worker", reuse=worker)

    def test_consultation_advice_is_mains_to_adopt(self):
        director = self.executing()
        packet = Path(fp.consult(self.run, self.write("q.md", "FP-003 returned twice; approach?"))["packet"]).read_text()
        self.assertIn("consultation", packet); self.assertIn("FP-003 returned twice", packet)
        out = self.decide(director, {"kind": "advice", "advice": "Drop the cache layer."})
        self.assertEqual(out["next"], "main_decides")
        fp.consult(self.run, self.write("q2.md", "Scope?"))
        out = self.decide(director, {"kind": "advice", "advice": "Ask.", "user_response": "A (recommended) or B?"})
        self.assertEqual(out["next"], "relay_to_user")

    def test_consultation_can_revise_plan(self):
        director = self.executing()
        fp.consult(self.run, self.write("q.md", "Plan no longer fits."))
        out = self.decide(director, dict(PLAN, plan_id="plan-2", authorization_message=1))
        self.assertEqual(out["next"], "relay_to_user_then_start")
        with self.assertRaises(fp.Failure): self.prepare("worker")
        fp.start(self.run)
        self.assertEqual(self.state()["plan"]["id"], "plan-2")

    # Final check: once, after review.

    def test_final_check_requires_review_and_idle_executors(self):
        self.executing()
        worker = self.prepare("worker"); self.report(worker, "Done.")
        with self.assertRaises(fp.Failure): fp.final_check(self.run, self.input)
        reviewer = self.prepare("reviewer")
        with self.assertRaises(fp.Failure): fp.final_check(self.run, self.input)
        self.report(reviewer, "FINDINGS: none")
        packet = Path(fp.final_check(self.run, self.write("e.md", "Evidence body"))["packet"]).read_text()
        self.assertIn("HEAD:", packet); self.assertIn("Evidence body", packet)

    def test_blocked_review_does_not_count_as_review(self):
        self.executing()
        worker = self.prepare("worker"); self.report(worker, "Done.")
        reviewer = self.prepare("reviewer"); self.report(reviewer, "Cannot read the diff.", status="blocked")
        with self.assertRaises(fp.Failure): fp.final_check(self.run, self.input)

    def test_git_failure_is_not_reported_as_clean(self):
        self.reviewed()
        with patch.object(fp, "git", return_value=None):
            packet = Path(fp.final_check(self.run, self.input)["packet"]).read_text()
        self.assertIn("HEAD: unavailable (git failed)", packet)
        self.assertNotIn("clean", packet)

    def test_final_check_runs_once_per_plan(self):
        director, worker, reviewer = self.final_checked()
        self.assertEqual(self.state()["final_checks"], {"plan-1": self.state()["last_decision"]["file"]})
        with self.assertRaises(fp.Failure): fp.final_check(self.run, self.input)
        # Accepted findings go to the same Worker and Reviewer, never back to Astra.
        self.prepare("worker", reuse=worker); self.report(worker, "Fixed FP-101.")
        self.prepare("reviewer", reuse=reviewer); self.report(reviewer, "FINDINGS: none")
        self.assertIn("Final", fp.finish(self.run, self.write("r.md", "Final report"))["user_response"])

    def test_final_check_shape(self):
        director, _, _ = self.reviewed()
        bad = [dict(FINAL, ac_status=[]),
               dict(FINAL, ac_status=[{"criterion": "It works.", "status": "accepted", "evidence": "x"}]),
               dict(FINAL, plan_id="other"),
               {k: v for k, v in FINAL.items() if k != "findings"}]
        fp.final_check(self.run, self.input)
        for value in bad:
            with self.subTest(value=value):
                self.report(director, value)
                with self.assertRaises(fp.Failure): fp.decision(director)
        self.decide(director, FINAL)

    def test_final_check_divergence_can_go_to_user(self):
        director, _, _ = self.reviewed()
        fp.final_check(self.run, self.input)
        out = self.decide(director, dict(FINAL, plan_divergence=["Scope grew."], user_response="Keep (recommended) or trim?"))
        self.assertEqual(out["next"], "relay_to_user")

    def test_finish_requires_final_check_and_report(self):
        self.reviewed()
        with self.assertRaises(fp.Failure): fp.finish(self.run, self.input)
        with self.assertRaises(fp.Failure): fp.finish(self.run, discussion=True)

    def test_finish_requires_collected_executors(self):
        _, worker, _ = self.final_checked()
        self.prepare("worker", reuse=worker)
        with self.assertRaises(fp.Failure): fp.finish(self.run, self.input)
        self.report(worker, "Fixed.")
        out = fp.finish(self.run, self.write("r.md", "Final report body"))
        self.assertEqual(out["user_response"], "Final report body")
        self.assertEqual((Path(self.run) / "final-report.md").read_text(), "Final report body")

    # Closing and recovery.

    def closure(self, task, name="c.json"):
        agent = f"agent-{fp.task_at(task)[1]['id']}"
        fp.bind(task, self.write(f"h-{name}", {"agent_id": agent, "evidence": "spawned"}))
        return self.write(name, {"agent_id": agent, "closed": True, "evidence": "close tool ok"})

    def test_close_record_lifecycle(self):
        director = self.executing()
        worker = self.prepare("worker"); closure = self.closure(worker)
        with self.assertRaises(fp.Failure): fp.close_record(worker, closure)  # No report yet.
        self.report(worker, "Blocked on credentials.", status="blocked")
        with self.assertRaises(fp.Failure): fp.close_record(worker, closure)  # Blocker stays open.
        self.prepare("worker", reuse=worker); self.report(worker, "Done.")
        fp.close_record(worker, closure)
        self.assertTrue(fp.task_at(worker)[1]["closed"])
        with self.assertRaises(fp.Failure): self.prepare("worker", reuse=worker)
        director_closure = self.closure(director, "d.json")
        with self.assertRaises(fp.Failure): fp.close_record(director, director_closure)

    def test_close_record_requires_actual_identity(self):
        self.executing()
        worker = self.prepare("worker"); self.report(worker, "Done.")
        self.closure(worker)
        wrong = self.write("wrong.json", {"agent_id": "another", "closed": True, "evidence": "ok"})
        with self.assertRaises(fp.Failure): fp.close_record(worker, wrong)

    def test_native_id_cannot_be_reused_for_another_role(self):
        director = self.executing()
        handle = self.write("handle.json", {"agent_id": "actual-id", "evidence": "tool result"})
        fp.bind(director, handle)
        worker = self.prepare("worker")
        with self.assertRaises(fp.Failure): fp.bind(worker, handle)

    def test_lost_director_recovery(self):
        task = self.plan(authorized=False)
        fp.retire_lost(task, self.write("lost.md", "Runtime reports the session missing."))
        replacement = self.director()
        self.assertNotEqual(task, replacement)
        self.assertIn("messages/1.md", Path(fp.task_at(replacement)[1]["packet"]).read_text())

    def test_lost_director_during_execution_needs_handoff(self):
        task = self.executing()
        fp.retire_lost(task, self.write("lost.md", "Session gone."))
        with self.assertRaises(fp.Failure): self.director()
        replacement = fp.start_director(self.run, self.write("handoff.md", "Plan and reports."))
        self.assertEqual(fp.task_at(replacement["task"])[1]["purpose"], "consultation")

    def test_wrong_main_identity_rejected(self):
        with patch.dict(os.environ, {"CODEX_THREAD_ID": "other"}):
            with self.assertRaises(fp.Failure): self.director()

    def test_child_cannot_manage_run(self):
        with patch.dict(os.environ, {"FRONTIERPLAN_ROLE": "director"}):
            with self.assertRaises(fp.Failure): self.director()

    def test_stale_lock_not_removed_automatically(self):
        target = Path(self.run) / ".state.lock"; target.write_text("999999")
        with self.assertRaises(fp.Failure): self.director()
        self.assertTrue(target.exists())

    def test_old_run_format_rejected(self):
        state = fp.read(Path(self.run) / "run.json"); state["schema_version"] = 1
        fp.atomic(Path(self.run) / "run.json", state)
        with self.assertRaises(fp.Failure): self.director()

    def test_profiles_role_specific_lowercase(self):
        expected = {"director": ("gpt-6-astra", "xhigh"), "researcher": ("gpt-6-luna", "max"),
                    "worker": ("gpt-6-luna", "max"), "design": ("gpt-6-sol", "max"),
                    "reviewer": ("gpt-6-sol", "xhigh")}
        for role, (model, effort) in expected.items():
            with self.subTest(role=role):
                value = dict({"role": role, "model": model, "reasoning_effort": effort},
                             **({"service_tier": "fast"} if role in ("worker", "researcher") else {}))
                self.assertEqual(fp.profile(role), value)
        self.assertEqual(fp.profile("main"), {"role": "main", "inherit_session": True})
        with self.assertRaises(fp.Failure): fp.profile("director", "fable")

    def test_package_and_extracted_integrity(self):
        self.assertEqual(validate(ROOT / "plugins/frontierplan"), [])
        archives = package(self.root / "dist")
        self.assertEqual(len(archives), 2)
        self.assertTrue(all(p.exists() for p in archives))

    def test_claude_code_marketplace_and_explicit_invocation(self):
        market = json.loads((ROOT / ".claude-plugin/marketplace.json").read_text())
        entry, = market["plugins"]
        self.assertEqual(entry["name"], "frontierplan")
        self.assertEqual((ROOT / ".claude-plugin" / ".." / entry["source"]).resolve(),
                         (ROOT / "plugins/frontierplan").resolve())
        copy = self.root / "plugin"
        shutil.copytree(ROOT / "plugins/frontierplan", copy,
                        ignore=shutil.ignore_patterns("__pycache__"))
        skill = copy / "skills/astraplan-herdr/SKILL.md"
        skill.write_text(skill.read_text().replace("disable-model-invocation: true\n", ""))
        self.assertIn("Explicit-only Claude Code invocation required: astraplan-herdr", validate(copy))


if __name__ == "__main__": unittest.main()
