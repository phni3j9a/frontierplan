"""Issue 17: simulated pair protocol and transport, never real-host evidence."""
from pathlib import Path
import json
import os
import unittest
from unittest.mock import patch

import test_frontierplan as base
import test_herdr as transport
import frontierplan as fp
import herdr as hd
import pairs
from pair_support import child, create_pair, pair_turn, pass_pair, passed_pair


class NativePairs(unittest.TestCase):
    setUp = base.Protocol.setUp
    git = base.Protocol.git
    write = base.Protocol.write
    report = base.Protocol.report
    decide = base.Protocol.decide
    director = base.Protocol.director
    plan = base.Protocol.plan
    executing = base.Protocol.executing

    def ready(self):
        self.executing()
        return create_pair(self)

    def test_capability_is_explicit_and_not_an_invented_native_bridge(self):
        self.executing()
        with self.assertRaisesRegex(fp.Failure, "unverified"):
            pairs.create(self.run, self.input)
        with self.assertRaisesRegex(fp.Failure, "child-to-peer"):
            pairs.create(self.run, self.input, capability_file=self.write("bad-cap.json", {"direct_peer_resume": False, "evidence": "notifications only"}))
        self.assertEqual(len(fp.tasks(Path(self.run))), 1)  # Astra only; no partial pair.
        worker, reviewer = create_pair(self)
        result = pair_turn(self, worker, "candidate")
        self.assertTrue(result["native_call_required"])
        self.assertEqual(result["agent_id"], fp.task_at(reviewer)[1]["handle"]["agent_id"])
        self.assertNotIn("sent", result)

    def test_main_cannot_impersonate_child_or_adjudicate_review(self):
        worker, reviewer = self.ready()
        data = fp.task_at(worker)[1]
        with self.assertRaises(fp.Failure): pairs.begin(worker, data["request_id"])
        with child(self, worker):
            with self.assertRaises(fp.Failure): pairs.begin(reviewer, fp.task_at(reviewer)[1]["request_id"])
        pair_turn(self, worker, "candidate")
        with self.assertRaises(fp.Failure): fp.collect(worker)
        with self.assertRaises(fp.Failure): fp.prepare(self.run, "worker", self.input, reuse=worker)

    def test_plain_complete_report_cannot_replace_a_pair_verdict(self):
        worker, reviewer = self.ready()
        for path in (worker, reviewer):
            with self.assertRaises(fp.Failure): self.report(path, "PASS")
        with self.assertRaises(fp.Failure): fp.final_check(self.run, self.input)

    def test_reviewer_bootstrap_is_idle_without_reviewing_empty_work(self):
        worker, reviewer = self.ready()
        with child(self, reviewer) as data:
            self.assertTrue(pairs.begin(reviewer, data["request_id"])["waiting"])
        self.assertIsNone(fp.current_result(Path(reviewer), fp.task_at(reviewer)[1]))
        self.assertEqual(fp.uncollected_reports(Path(self.run)), [])

    def test_fix_and_counter_evidence_use_same_sessions_and_finding_history(self):
        worker, reviewer = self.ready()
        original = [fp.task_at(p)[1]["handle"] for p in (worker, reviewer)]
        pair_turn(self, worker, "candidate", "Implemented; targeted tests")
        pair_turn(self, reviewer, "findings", "FP-001: a concrete failing case; smallest correction")
        old_report = Path(reviewer) / (fp.task_at(reviewer)[1]["request_id"] + ".result.json")
        pair_turn(self, worker, "candidate", "FP-001 counter-evidence: the required behavior already passes")
        self.assertIn("FP-001", old_report.read_text())
        pair_turn(self, reviewer, "pass", "FP-001 resolved by the evidence; required checks pass")
        self.assertEqual(original, [fp.task_at(p)[1]["handle"] for p in (worker, reviewer)])
        self.assertEqual(len(fp.uncollected_reports(Path(self.run))), 2)
        self.assertEqual(pairs.collect(worker)["status"], "PASS")
        self.assertEqual(fp.uncollected_reports(Path(self.run)), [])

    def test_worker_cannot_pass_and_old_turn_cannot_send_again(self):
        worker, reviewer = self.ready()
        with child(self, worker) as data:
            pairs.begin(worker, data["request_id"])
            with self.assertRaises(fp.Failure): pairs.submit(worker, data["request_id"], "pass", self.input)
        old = fp.task_at(worker)[1]["request_id"]
        pair_turn(self, worker, "candidate")
        pair_turn(self, reviewer, "findings")
        with child(self, worker), self.assertRaisesRegex(fp.Failure, "Stale"):
            pairs.submit(worker, old, "candidate", self.input)

    def test_candidate_change_during_review_can_return_to_worker_without_main(self):
        worker, reviewer = self.ready()
        pair_turn(self, worker, "candidate")
        with child(self, reviewer) as data:
            started = pairs.begin(reviewer, data["request_id"])
            (self.project / "file.txt").write_text("changed without a new candidate\n")
            with self.assertRaisesRegex(fp.Failure, "Candidate changed"):
                pairs.submit(reviewer, data["request_id"], "pass", self.input, started["candidate"])
            pairs.submit(reviewer, data["request_id"], "findings", self.write("stale.md", "FP-001: publish the current candidate"), started["candidate"])
        pair_turn(self, worker, "candidate")
        pair_turn(self, reviewer, "pass")
        self.assertEqual(pairs.collect(worker)["status"], "PASS")

    def test_uncommitted_and_untracked_changes_invalidate_uncollected_pass(self):
        worker, reviewer = self.ready()
        pass_pair(self, worker, reviewer, collect=False)
        for filename in ("file.txt", "new.txt"):
            with self.subTest(filename=filename):
                path = self.project / filename
                old = path.read_bytes() if path.exists() else None
                path.write_text("new bytes")
                with self.assertRaisesRegex(fp.Failure, "Candidate changed"):
                    pairs.collect(worker)
                if old is None: path.unlink()
                else: path.write_bytes(old)
        pairs.collect(worker)

    def test_scope_fingerprints_content_deletion_modes_and_not_unrelated_files(self):
        pair = {"cwd": str(self.project), "scope": ["file.txt"]}
        initial = fp.digest(pairs.snapshot(pair))
        (self.project / "unrelated.txt").write_text("not this task")
        self.assertEqual(initial, fp.digest(pairs.snapshot(pair)))
        (self.project / "file.txt").chmod(0o755)
        self.assertNotEqual(initial, fp.digest(pairs.snapshot(pair)))
        (self.project / "file.txt").unlink()
        self.assertEqual(pairs.snapshot(pair)["files"]["file.txt"], {"deleted": True})
        for bad in ("../outside", "/outside", ".git/config"):
            with self.assertRaises(fp.Failure): pairs.scopes([bad])

    def test_contract_or_manifest_or_reviewer_change_invalidates_pass(self):
        worker, reviewer = self.ready()
        pass_pair(self, worker, reviewer)
        record, pair, _, _ = pairs.at(worker)
        for field, value in (("contract", "a changed requirement"), ("contract_digest", "old")):
            changed = dict(pair, **{field: value})
            with self.subTest(field=field), self.assertRaises(fp.Failure): pairs.valid_pass(changed)
        manifest = Path(pair["candidate"]["manifest"])
        saved = manifest.read_bytes(); manifest.write_text("{}")
        with self.assertRaises(fp.Failure): pairs.valid_pass(pair)
        manifest.write_bytes(saved)
        path, data, _, _ = fp.task_at(reviewer)
        data["handle"]["agent_id"] = "replacement"
        fp.atomic(path / "task.json", data)
        with self.assertRaises(fp.Failure): pairs.valid_pass(pair)

    def test_completed_task_is_sealed_not_reopened_by_followup_work(self):
        worker, reviewer = self.ready()
        pass_pair(self, worker, reviewer)
        for task_path in (worker, reviewer):
            task = fp.task_at(task_path)[1]
            closure = self.write("closed.json", {"agent_id": task["handle"]["agent_id"], "closed": True, "evidence": "simulated native close"})
            fp.close_record(task_path, closure)
        newer_worker, newer_reviewer = create_pair(self)
        pair_turn(self, newer_worker, "candidate", change=lambda: (self.project / "file.txt").write_text("follow-up"))
        pair_turn(self, newer_reviewer, "pass")
        pairs.collect(newer_worker)
        root, state = fp.run_at(self.run)
        pairs.require_all_complete(root, state)  # Old sealed candidate is still a valid delivered result.
        with child(self, newer_worker) as data, self.assertRaises(fp.Failure):
            pairs.begin(newer_worker, data["request_id"])

    def test_lost_session_after_collection_does_not_invalidate_delivered_work(self):
        worker, reviewer = self.ready()
        pass_pair(self, worker, reviewer)
        fp.retire_lost(reviewer, self.write("lost-after-collect.md", "SIMULATED session exited after result collection"))
        pairs.require_all_complete(*fp.run_at(self.run))
        with self.assertRaises(fp.Failure): pairs.replace(reviewer, self.input)

    def test_revised_plan_waits_for_active_pair_then_requires_explicit_contract(self):
        director = self.executing()
        worker, reviewer = create_pair(self)
        fp.consult(self.run, self.input)
        revised = dict(base.PLAN, plan_id="plan-2", authorization_message=1)
        self.report(director, revised)
        with self.assertRaisesRegex(fp.Failure, "active pairs"):
            fp.decision(director)
        pair_turn(self, worker, "blocked", "Requirement needs Plan clarification")
        pairs.collect(worker)
        fp.decision(director)
        with self.assertRaisesRegex(fp.Failure, "Start the current Plan"):
            pairs.resume(worker, self.input, self.input)
        fp.start(self.run)
        with self.assertRaisesRegex(fp.Failure, "updated Task Contract"):
            pairs.resume(worker, self.input)
        pairs.resume(worker, self.input, self.input)
        pass_pair(self, worker, reviewer)
        self.assertEqual(pairs.at(worker)[1]["plan_id"], "plan-2")
        pairs.require_all_complete(*fp.run_at(self.run))

    def test_stagnation_escalates_and_main_resolves_without_round_quota(self):
        worker, reviewer = self.ready()
        pair_turn(self, worker, "candidate")
        pair_turn(self, reviewer, "findings", "FP-001: missing behavior")
        pair_turn(self, worker, "escalate", "FP-001: same approach fails; need an environment fix")
        self.assertEqual(pairs.collect(worker)["status"], "ESCALATE")
        with self.assertRaises(fp.Failure): pairs.require_collected(worker)
        with self.assertRaises(fp.Failure): fp.final_check(self.run, self.input)
        result = pairs.resume(worker, self.write("resolution.md", "Fixed test environment; keep the contract"))
        self.assertEqual(result["task"], worker)
        pass_pair(self, worker, reviewer)
        self.assertEqual(pairs.at(worker)[1]["status"], "PASS")

    def test_main_does_not_reopen_valid_pass_but_can_recover_stale_collection(self):
        worker, reviewer = self.ready()
        pass_pair(self, worker, reviewer, collect=False)
        with self.assertRaises(fp.Failure): pairs.resume(worker, self.input)
        (self.project / "file.txt").write_text("changed before collection")
        pairs.resume(worker, self.write("resubmit.md", "Collection detected different bytes; resubmit latest candidate"))
        pass_pair(self, worker, reviewer)

    def test_reviewer_replacement_preserves_candidate_and_blocks_old_session(self):
        worker, reviewer = self.ready()
        pair_turn(self, worker, "candidate")
        old_candidate = pairs.at(worker)[1]["candidate"]
        fp.retire_lost(reviewer, self.write("lost.md", "SIMULATED runtime: reviewer process exited"))
        new = pairs.replace(reviewer, self.write("replacement.md", "Resume from previous reports, not a new broad review"))
        fresh = new["task"]
        self.assertEqual(old_candidate, pairs.at(worker)[1]["candidate"])
        self.assertIn(reviewer, Path(new["packet"]).read_text())
        fp.bind(fresh, self.write("fresh.json", {"agent_id": "new-reviewer", "thread_id": "new-reviewer-thread", "evidence": "simulated new session"}))
        with child(self, reviewer) as data, self.assertRaises(fp.Failure): pairs.begin(reviewer, data["request_id"])
        pair_turn(self, fresh, "pass")
        pairs.collect(worker)
        pairs.require_all_complete(*fp.run_at(self.run))
        self.assertEqual(fp.task_at(fresh)[1]["profile"]["model"], "gpt-6-sol")

    def test_blocked_worker_replacement_keeps_reports_and_same_reviewer(self):
        worker, reviewer = self.ready()
        pair_turn(self, worker, "blocked", "Tool unavailable; stopped rather than looping")
        pairs.collect(worker)
        new = pairs.replace(worker, self.write("replace.md", "Main selected a different implementation approach"))
        fresh = new["task"]
        self.assertEqual(pairs.at(reviewer)[1]["reviewer"], Path(reviewer).name)
        self.assertIn(worker, Path(new["packet"]).read_text())
        fp.bind(fresh, self.write("fresh.json", {"agent_id": "new-worker", "thread_id": "new-worker-thread", "evidence": "simulated new session"}))
        pass_pair(self, fresh, reviewer)
        pairs.require_all_complete(*fp.run_at(self.run))

    def test_final_check_and_finish_require_all_pairs_not_just_some_review(self):
        director = self.executing()
        first = passed_pair(self)
        worker, reviewer = create_pair(self)
        with self.assertRaises(fp.Failure): fp.final_check(self.run, self.input)
        pass_pair(self, worker, reviewer)
        fp.final_check(self.run, self.input)
        self.decide(director, base.FINAL)
        repair_worker, repair_reviewer = create_pair(self)
        pair_turn(self, repair_worker, "candidate")
        with self.assertRaises(fp.Failure): fp.finish(self.run, self.input)
        pair_turn(self, repair_reviewer, "pass")
        with self.assertRaises(fp.Failure): fp.finish(self.run, self.input)
        pairs.collect(repair_worker)
        self.assertEqual(fp.finish(self.run, self.input)["phase"], "closed")


class HerdrPairs(unittest.TestCase):
    setUp = base.Protocol.setUp
    git = base.Protocol.git
    write = base.Protocol.write
    report = base.Protocol.report
    setup_api = transport.HerdrTransport.setup_api
    director = transport.HerdrTransport.director
    decide = transport.HerdrTransport.decide
    director_plan = transport.HerdrTransport.director_plan

    def ready(self):
        director = self.director(); self.director_plan(director)
        return create_pair(self)

    def test_direct_fix_round_trip_never_calls_main_and_keeps_sessions(self):
        worker, reviewer = self.ready()
        handles = [fp.task_at(p)[1]["handle"] for p in (worker, reviewer)]
        starts = len([c for c in self.api.calls if c[:2] == ("agent", "start")])
        with patch.object(fp, "main_only", side_effect=AssertionError("Main was asked to mediate")):
            pair_turn(self, worker, "candidate")
            pair_turn(self, reviewer, "findings", "FP-001: fix the concrete defect")
            pair_turn(self, worker, "candidate", "FP-001 corrected")
            pair_turn(self, reviewer, "pass")
        self.assertEqual(starts, len([c for c in self.api.calls if c[:2] == ("agent", "start")]))
        self.assertEqual(handles, [fp.task_at(p)[1]["handle"] for p in (worker, reviewer)])
        targets = [c[2] for c in self.api.calls if c[:2] == ("agent", "prompt")][-3:]
        self.assertEqual(targets, [fp.task_at(reviewer)[1]["name"], fp.task_at(worker)[1]["name"], fp.task_at(reviewer)[1]["name"]])
        pairs.collect(worker)
        hd.close_pair(worker)
        self.assertEqual(len(self.api.panes), 2)  # Main + Astra, before final check.
        self.assertFalse(fp.task_at(fp.director_task(Path(self.run))[0])[1]["closed"])

    def test_main_wait_does_not_collect_ordinary_pair_reports(self):
        worker, reviewer = self.ready()
        pair_turn(self, worker, "candidate")
        self.assertEqual(fp.uncollected_reports(Path(self.run)), [])
        self.assertEqual(hd.check(self.run)["events"], [])
        self.assertGreater(hd.check(self.run)["pending"], 0)
        pair_turn(self, reviewer, "findings")
        self.assertEqual(hd.check(self.run)["events"], [])
        pair_turn(self, worker, "candidate")
        pair_turn(self, reviewer, "pass")
        self.assertEqual(len(hd.check(self.run)["events"]), 2)
        pairs.collect(worker)
        self.assertEqual(hd.check(self.run), {"events": [], "pending": 0})

    def test_busy_peer_retains_one_handoff_until_it_can_really_resume(self):
        worker, reviewer = self.ready()
        peer = self.api.registered[fp.task_at(reviewer)[1]["name"]]
        peer["agent_status"] = "working"
        original = hd.deliver_pair
        with patch.object(hd, "deliver_pair", side_effect=lambda p, r: original(p, r, timeout=0)):
            result = pair_turn(self, worker, "candidate")
        self.assertTrue(result["peer_busy"])
        pending = pairs.at(worker)[1]["pending"]
        peer["agent_status"] = "idle"
        with child(self, worker) as task:
            result = pairs.deliver(worker, task["request_id"])
            self.assertEqual(result["delivery"], "sent")
            with self.assertRaises(fp.Failure): pairs.deliver(worker, task["request_id"])
        self.assertEqual(pending["request_id"], fp.task_at(reviewer)[1]["request_id"])
        pair_turn(self, reviewer, "pass")
        pairs.collect(worker)

    def test_uncertain_delivery_is_not_blindly_retried_and_main_sees_it(self):
        worker, reviewer = self.ready()
        self.api.fail_prompt = True
        with self.assertRaises(fp.Failure): pair_turn(self, worker, "candidate")
        before = len(self.api.calls)
        with child(self, worker) as data, self.assertRaisesRegex(fp.Failure, "uncertain"):
            pairs.deliver(worker, data["request_id"])
        self.assertFalse(any(c[:2] == ("agent", "prompt") for c in self.api.calls[before:]))
        self.assertTrue(any(e["event"] == "pair_delivery_uncertain" for e in hd.check(self.run)["events"]))
        # The prompt may in fact have been delivered despite its timeout.
        self.api.fail_prompt = False
        pair_turn(self, reviewer, "pass")
        self.assertIsNone(pairs.at(worker)[1]["pending"])
        pairs.collect(worker)

    def test_peer_begin_before_prompt_returns_does_not_resurrect_pending_delivery(self):
        worker, reviewer = self.ready()
        original = self.api.call
        def fast_peer(*args):
            value = original(*args)
            if args[:2] == ("agent", "prompt") and args[2] == fp.task_at(reviewer)[1]["name"]:
                with child(self, reviewer) as data:
                    pairs.begin(reviewer, data["request_id"])
            return value
        with patch.object(self.api, "call", side_effect=fast_peer):
            pair_turn(self, worker, "candidate")
        self.assertIsNone(pairs.at(worker)[1]["pending"])

    def test_wrong_pair_and_reused_terminal_cannot_send_or_close(self):
        worker, reviewer = self.ready()
        other_worker, other_reviewer = create_pair(self)
        with child(self, worker), self.assertRaises(fp.Failure):
            pairs.begin(other_worker, fp.task_at(other_worker)[1]["request_id"])
        peer = self.api.registered[fp.task_at(reviewer)[1]["name"]]
        original_terminal = peer["terminal_id"]
        peer["terminal_id"] = "reused-by-another-agent"
        with self.assertRaises(fp.Failure): pair_turn(self, worker, "candidate")
        peer["terminal_id"] = original_terminal
        with child(self, worker) as data: pairs.deliver(worker, data["request_id"])
        pair_turn(self, reviewer, "pass")
        with self.assertRaises(fp.Failure): hd.close_pair(worker)  # not collected
        pairs.collect(worker)
        peer["state_change_seq"] += 1
        with self.assertRaises(fp.Failure): hd.close(reviewer)
        self.assertFalse(fp.task_at(reviewer)[1]["closed"])

    def test_blocker_panes_stay_until_main_resolves_and_pair_passes(self):
        worker, reviewer = self.ready()
        pair_turn(self, worker, "escalate", "Same cause prevents progress; need Main's environment decision")
        pairs.collect(worker)
        with self.assertRaises(fp.Failure): hd.close_pair(worker)
        hd.resume_pair(worker, self.write("intervention.md", "Environment repaired; implement unchanged requirements"))
        pass_pair(self, worker, reviewer)
        hd.close_pair(worker)
        self.assertTrue(fp.task_at(worker)[1]["closed"])
        self.assertTrue(fp.task_at(reviewer)[1]["closed"])


if __name__ == "__main__":
    unittest.main()
