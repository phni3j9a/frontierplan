"""Simulated provider-neutral Main checks; not a Devin/herdr real-host smoke test."""
from __future__ import annotations

import contextlib
import copy
import io
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import unittest
from unittest.mock import patch

import test_frontierplan as base
import test_herdr as transport
import frontierplan as fp
import herdr as hd


class ProviderHerdr(transport.FakeHerdr):
    def __init__(self):
        super().__init__()
        self.panes[0].update(agent="devin", agent_session="devin-session",
                             model="host-selected-model", reasoning_effort="host-selected-effort")
        self.current = "main-pane"

    def call(self, *args):
        if args[:2] == ("pane", "current"):
            self.calls.append(args)
            return {"pane": copy.deepcopy(next(p for p in self.panes if p["pane_id"] == self.current))}
        return super().call(*args)


class MainIdentity(unittest.TestCase):
    git = base.Protocol.git
    write = base.Protocol.write
    report = base.Protocol.report

    def setUp(self):
        base.Protocol.setUp(self)
        self.native_run = self.run
        env = patch.dict(os.environ, {"CODEX_THREAD_ID": "", "CODEX_SESSION_ID": "",
                                     "HERDR_PANE_ID": "main-pane"})
        env.start(); self.addCleanup(env.stop)
        self.api = ProviderHerdr()
        api = patch.object(hd, "Herdr", side_effect=lambda *a, **k: self.api)
        api.start(); self.addCleanup(api.stop)
        output = contextlib.redirect_stdout(io.StringIO())
        output.__enter__(); self.addCleanup(output.__exit__, None, None, None)

    def explicit(self, *, session="devin-session", agent="devin"):
        env = patch.dict(os.environ, {"FRONTIERPLAN_MAIN_AGENT": agent,
                                     "FRONTIERPLAN_MAIN_SESSION_ID": session, "HERDR_PANE_ID": ""})
        env.start(); self.addCleanup(env.stop)

    def initialize(self, *, explicit=False):
        args = ("main-pane", "main-terminal", "/fake/socket") if explicit else ()
        value = hd.initialize(str(self.project), self.input, *args)
        self.run = value["run"]
        self.addCleanup(shutil.rmtree, self.run, True)
        return value

    def test_current_pane_autodetects_devin_without_codex_env(self):
        value = self.initialize()
        self.assertEqual(value["main_identity"], {"agent": "devin", "session_id": "devin-session"})
        fp.authorize(self.run, 1)
        fp.message(self.run, self.input)
        self.assertEqual(fp.run_at(self.run)[1]["user_seq"], 2)

    def test_explicit_identity_works_without_current_pane_env(self):
        self.explicit(agent="Devin")
        self.initialize(explicit=True)
        fp.authorize(self.run, 1)
        self.assertFalse(any(c[:2] == ("pane", "current") for c in self.api.calls))

    def test_explicit_pane_pair_alone_cannot_claim_a_conversation(self):
        with patch.dict(os.environ, {"HERDR_PANE_ID": ""}), self.assertRaises(fp.Failure):
            self.initialize(explicit=True)

    def test_current_pane_response_must_match_environment(self):
        with patch.dict(os.environ, {"HERDR_PANE_ID": "another-pane"}), self.assertRaises(fp.Failure):
            self.initialize()

    def test_missing_live_session_needs_explicit_verified_identity(self):
        self.api.panes[0].pop("agent_session")
        with self.assertRaises(fp.Failure): self.initialize()
        self.explicit(); self.initialize(explicit=True)
        fp.authorize(self.run, 1)
        self.api.panes[0]["agent_session"] = "different"
        with self.assertRaises(fp.Failure): fp.authorize(self.run, 1)

    def test_previously_observed_session_cannot_disappear(self):
        self.explicit(); self.initialize(explicit=True)
        self.api.panes[0].pop("agent_session")
        with self.assertRaises(fp.Failure): fp.authorize(self.run, 1)

    def test_partial_explicit_identity_is_rejected(self):
        for env in ({"FRONTIERPLAN_MAIN_AGENT": "devin"},
                    {"FRONTIERPLAN_MAIN_SESSION_ID": "devin-session"}):
            with self.subTest(env=env), patch.dict(os.environ, env), self.assertRaises(fp.Failure):
                self.initialize()

    def test_explicit_identity_must_match_live_session(self):
        self.explicit(session="different")
        with self.assertRaises(fp.Failure): self.initialize(explicit=True)

    def test_explicit_identity_cannot_hide_codex_conflict(self):
        self.explicit()
        with patch.dict(os.environ, {"CODEX_THREAD_ID": "inherited"}), self.assertRaises(fp.Failure):
            self.initialize(explicit=True)

    def test_codex_environment_aliases_must_agree(self):
        with patch.dict(os.environ, {"CODEX_THREAD_ID": "one", "CODEX_SESSION_ID": "two"}), self.assertRaises(fp.Failure):
            self.initialize()

    def test_session_metadata_variants_and_conflicts(self):
        for field, value in (("agent_session", {"value": "s"}), ("agent_session", {"id": "s"}),
                             ("agent_session_id", "s"), ("session_id", "s"), ("thread_id", "s")):
            with self.subTest(field=field, value=value): self.assertEqual(hd.session_id({field: value}), "s")
        for pane in ({"agent_session": "one", "session_id": "two"},
                     {"agent_session": {"value": "one", "id": "two"}}, {"agent_session": ["s"]}):
            with self.subTest(pane=pane), self.assertRaises(fp.Failure): hd.session_id(pane)

    def test_unrecognized_agent_kind_is_not_guessed(self):
        for agent in (None, "", "unknown", "shell"):
            self.api.panes[0]["agent"] = agent
            with self.subTest(agent=agent), self.assertRaises(fp.Failure): self.initialize()

    def test_agent_kind_change_blocks_common_ledger_before_write(self):
        self.initialize(); before = Path(self.run, "run.json").read_bytes()
        self.api.panes[0]["agent"] = "codex"
        with self.assertRaises(fp.Failure): fp.message(self.run, self.input)
        self.assertEqual(Path(self.run, "run.json").read_bytes(), before)

    def test_session_change_blocks_spawn_before_pane_mutation(self):
        self.initialize(); self.api.panes[0]["agent_session"] = "different"
        with self.assertRaises(fp.Failure): hd.spawn(self.run, "director", self.input)
        self.assertFalse(any(c[:2] == ("pane", "split") for c in self.api.calls))

    def test_reused_pane_with_other_terminal_blocks_common_ledger(self):
        self.initialize(); self.api.panes[0]["terminal_id"] = "replacement"
        with self.assertRaises(fp.Failure): fp.authorize(self.run, 1)

    def test_unrelated_current_pane_cannot_manage_main(self):
        self.initialize()
        other = dict(self.api.panes[0], pane_id="other", terminal_id="other-terminal")
        self.api.panes.append(other); self.api.current = "other"
        with patch.dict(os.environ, {"HERDR_PANE_ID": "other"}), self.assertRaises(fp.Failure):
            fp.authorize(self.run, 1)

    def test_ambiguous_terminal_is_rejected(self):
        self.initialize(); self.api.panes.append(dict(self.api.panes[0], pane_id="duplicate"))
        with self.assertRaises(fp.Failure): fp.authorize(self.run, 1)

    def test_explicit_identity_follows_manual_terminal_move(self):
        self.explicit(); self.initialize(explicit=True)
        self.api.panes[0]["pane_id"] = "moved"
        fp.authorize(self.run, 1)
        self.assertEqual(hd.main_pane(fp.run_at(self.run)[1], self.api)["pane_id"], "moved")

    def test_lost_caller_evidence_is_not_replaced_by_saved_identity(self):
        self.initialize()
        with patch.dict(os.environ, {"HERDR_PANE_ID": ""}), self.assertRaises(fp.Failure):
            fp.authorize(self.run, 1)

    def test_children_cannot_initialize_or_manage_main(self):
        self.initialize(); before = list(self.api.calls)
        for role in fp.CHILDREN:
            with self.subTest(role=role), patch.dict(os.environ, {"FRONTIERPLAN_ROLE": role}):
                with self.assertRaises(fp.Failure): hd.initialize(str(self.project), self.input)
                with self.assertRaises(fp.Failure): fp.authorize(self.run, 1)
        self.assertEqual(self.api.calls, before)

    def test_native_subagent_still_requires_codex_identity(self):
        self.explicit()
        with self.assertRaises(fp.Failure): fp.authorize(self.native_run, 1)
        with self.assertRaises(fp.Failure): fp.initialize("subagent", str(self.project), self.input)
        with patch.dict(os.environ, {"CODEX_THREAD_ID": "main-test"}):
            fp.authorize(self.native_run, 1)  # No herdr or generic-identity fallback.
        self.assertEqual(self.api.calls, [])

    def test_legacy_codex_run_remains_usable_and_guarded(self):
        self.api.panes[0].update(agent="codex", agent_session="main-test")
        with patch.dict(os.environ, {"CODEX_THREAD_ID": "main-test"}):
            self.initialize()
            path = Path(self.run, "run.json"); state = fp.read(path)
            state.pop("main_identity"); state["herdr"].pop("session_verified")
            fp.atomic(path, state)
            fp.authorize(self.run, 1); hd.main_pane(state, self.api)
            self.api.panes[0]["agent_session"] = "other"
            with self.assertRaises(fp.Failure): hd.main_pane(state, self.api)
        with self.assertRaises(fp.Failure): fp.authorize(self.run, 1)

    def test_main_profile_rejects_routing_overrides(self):
        profiles = self.root / "profiles"; profiles.mkdir()
        for key in ("model", "reasoning_effort", "service_tier"):
            (profiles / "main.toml").write_text(f'role = "main"\ninherit_session = true\n{key} = "override"\n')
            with self.subTest(key=key), patch.object(fp, "ROOT", self.root), self.assertRaises(fp.Failure):
                fp.profile("main")

    def test_devin_full_execution_acceptance_and_child_routing(self):
        self.initialize(); original = copy.deepcopy(self.api.panes[0])
        director = hd.spawn(self.run, "director", self.input)["task"]
        self.report(director, {"kind": "reply", "user_response": "Need clarification"})
        hd.collect(director); fp.decision(director)
        fp.message(self.run, self.input); hd.send(director, self.input)
        self.report(director, {"kind": "plan", "plan_id": "p1", "user_response": "Plan",
                              "plan": "Implement", "acceptance_criteria": ["Works"], "verification": ["Tests"]})
        hd.collect(director); fp.decision(director); fp.authorize(self.run, 2); fp.start(self.run)
        worker = hd.spawn(self.run, "worker", self.input)["task"]
        self.report(worker, "Implemented; simulated test evidence."); hd.collect(worker)
        design = hd.spawn(self.run, "design", self.input)["task"]
        self.report(design, "UI implemented; simulated test evidence."); hd.collect(design)
        reviewer = hd.spawn(self.run, "reviewer", self.input)["task"]
        self.report(reviewer, "FINDINGS: none"); hd.collect(reviewer)
        candidate = fp.candidate(self.run, self.input)
        hd.send(director, self.input)
        self.report(director, {"kind": "accept", "plan_id": "p1", "candidate_id": candidate["id"],
                              "user_response": "Astra final report"})
        hd.collect(director); fp.decision(director)
        self.assertEqual(fp.finish(self.run)["user_response"], "Astra final report")
        for task in (director, worker, design, reviewer): hd.close(task)
        self.assertEqual(self.api.panes, [original])
        starts = [c for c in self.api.calls if c[:2] == ("agent", "start")]
        self.assertEqual(len(starts), 4)
        self.assertTrue(all(c[c.index("--kind") + 1] == "codex" for c in starts))
        for task, model, effort in ((director, "gpt-6-astra", "xhigh"),
                                    (worker, "gpt-6-luna", "max"), (design, "gpt-6-sol", "max"),
                                    (reviewer, "gpt-6-sol", "xhigh")):
            args = fp.task_at(task)[1]["requested_codex_args"]
            self.assertEqual(args[args.index("-m") + 1], model)
            self.assertIn(f'model_reasoning_effort="{effort}"', args)
            self.assertEqual('service_tier="fast"' in args, task == worker)
            self.assertEqual('features.fast_mode=true' in args, task == worker)
            self.assertIn('shell_environment_policy.set.FRONTIERPLAN_MAIN_AGENT=""', args)
            self.assertIn('shell_environment_policy.set.FRONTIERPLAN_MAIN_SESSION_ID=""', args)

    def test_common_and_transport_cli_share_identity_and_json_errors(self):
        # Exercise real Python entry points against a minimal fake CLI, not real herdr.
        binary = self.root / "fake-herdr"
        binary.write_text(f'#!{sys.executable}\nimport json\npane = {self.api.panes[0]!r}\n'
                          'print(json.dumps({"result": {"pane": pane, "panes": [pane], "agents": []}}))\n')
        binary.chmod(0o700)
        env = dict(os.environ, HERDR_BIN_PATH=str(binary))
        script = str(fp.ROOT / "scripts/frontierplan.py")
        def call(*args, environment=env):
            return subprocess.run([sys.executable, script, *args], env=environment,
                                  capture_output=True, text=True, timeout=10)
        result = call("init", "--backend", "herdr", "--cwd", str(self.project), "--request-file", self.input)
        self.assertEqual(result.returncode, 0, result.stderr)
        run = json.loads(result.stdout)["run"]; self.addCleanup(shutil.rmtree, run, True)
        self.assertEqual(call("authorize", "--run", run, "--message", "1").returncode, 0)
        wrong = dict(env, FRONTIERPLAN_MAIN_AGENT="devin", FRONTIERPLAN_MAIN_SESSION_ID="wrong")
        failure = call("status", "--run", run, environment=wrong)
        self.assertEqual(failure.returncode, 1); self.assertIn("error", json.loads(failure.stderr))
        self.assertNotIn("Traceback", failure.stderr)
        result = subprocess.run([sys.executable, str(fp.ROOT / "scripts/herdr.py"), "wait", "--run", run,
                                 "--timeout", "0"], env=env, capture_output=True, text=True, timeout=10)
        self.assertEqual(result.returncode, 0, result.stderr)


if __name__ == "__main__": unittest.main()
