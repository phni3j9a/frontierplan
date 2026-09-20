from __future__ import annotations

import contextlib
import copy
import io
import json
import math
from pathlib import Path
import shutil
import time
import unittest
from unittest.mock import patch

import test_frontierplan as base
import frontierplan as fp
import herdr as hd


class FakeHerdr:
    def __init__(self):
        self.binary = "/fake/herdr"
        self.env = {"HERDR_SOCKET_PATH": "/fake/socket"}
        self.panes = [{"pane_id":"main-pane", "terminal_id":"main-terminal", "agent":"codex", "agent_session":"main-test"}]
        self.registered = {}
        self.calls = []
        self.fail_prompt = False
        self.tree = "main-pane"
        self.next_pane = 1
        self.area = {"x": 0, "y": 0, "width": 200, "height": 100}
        self.zoomed = False

    def replace(self, node, target, value):
        if isinstance(node, str): return value if node == target else node
        first = self.replace(node["first"], target, value)
        second = self.replace(node["second"], target, value)
        if first is None: return second
        if second is None: return first
        return dict(node, first=first, second=second)

    def layout(self):
        panes, splits = [], []
        def visit(node, rect):
            if node is None: return
            if isinstance(node, str):
                # Real Herdr returns pane rects inset by borders/gaps, but full split rects.
                panes.append({"pane_id": node, "rect": dict(rect, x=rect["x"] + 1, y=rect["y"] + 1,
                              width=max(0, rect["width"] - 2), height=max(0, rect["height"] - 2))})
                return
            split = {"direction": node["direction"], "ratio": node["ratio"], "rect": dict(rect)}
            splits.append(split)
            first, second = dict(rect), dict(rect)
            size, pos = ("width", "x") if node["direction"] == "right" else ("height", "y")
            first[size] = math.floor(rect[size] * node["ratio"] + 0.5)
            second[size] -= first[size]; second[pos] += first[size]
            visit(node["first"], first); visit(node["second"], second)
        visit(self.tree, self.area)
        return {"workspace_id": "workspace", "tab_id": "tab", "zoomed": self.zoomed,
                "area": self.area, "panes": panes, "splits": splits}

    def agents(self): return copy.deepcopy(self.registered)

    def call(self, *args):
        self.calls.append(args)
        if args[:2] == ("pane", "list"): return {"panes": copy.deepcopy(self.panes)}
        if args[:2] == ("pane", "get"):
            return {"pane": copy.deepcopy(next(p for p in self.panes if p["pane_id"] == args[2]))}
        if args[:2] == ("pane", "layout"):
            return {"layout": self.layout()}
        if args[:2] == ("pane", "split"):
            number = self.next_pane; self.next_pane += 1
            pane = {"pane_id":f"pane-{number}", "terminal_id":f"terminal-{number}", "agent":"codex"}
            self.tree = self.replace(self.tree, args[2], {"direction": args[args.index("--direction") + 1],
                                    "ratio": float(args[args.index("--ratio") + 1]),
                                    "first": args[2], "second": pane["pane_id"]})
            self.panes.append(pane)
            return {"pane": copy.deepcopy(pane)}
        if args[:2] == ("pane", "rename"): return {}
        if args[:2] == ("agent", "start"):
            pane_id = args[args.index("--pane")+1]
            pane = next(p for p in self.panes if p["pane_id"] == pane_id)
            self.registered[args[2]] = dict(pane, name=args[2], agent_status="idle", state_change_seq=1, launch_pending=False)
            return {"argv":list(args[args.index("--")+1:])}
        if args[:2] == ("agent", "prompt"):
            if self.fail_prompt: raise fp.Failure("Transport timeout; delivery uncertain")
            self.registered[args[2]]["state_change_seq"] += 1
            return {}
        if args[:2] == ("pane", "close"):
            self.panes = [p for p in self.panes if p["pane_id"] != args[2]]
            self.registered = {k: a for k, a in self.registered.items() if a["pane_id"] != args[2]}
            self.tree = self.replace(self.tree, args[2], None)
            return {}
        raise AssertionError(f"Unexpected herdr invocation: {args}")


class HerdrTransport(unittest.TestCase):
    setUp = base.Protocol.setUp
    git = base.Protocol.git
    write = base.Protocol.write
    report = base.Protocol.report

    def setup_api(self):
        self.api = FakeHerdr()
        self.addCleanup(patch.stopall)
        patch.object(hd, "Herdr", side_effect=lambda *a, **k: self.api).start()
        main = self.api.panes[0]
        value = hd.initialize(str(self.project), self.input, main["pane_id"], main["terminal_id"],
                              self.api.env["HERDR_SOCKET_PATH"])
        self.run = value["run"]
        self.addCleanup(shutil.rmtree, self.run, True)
        self.output = contextlib.redirect_stdout(io.StringIO()); self.output.__enter__()
        self.addCleanup(self.output.__exit__, None, None, None)

    def director(self):
        self.setup_api()
        return hd.spawn(self.run, "director", self.input)["task"]

    def director_plan(self, task):
        self.report(task, {"kind":"plan", "plan_id":"p1", "user_response":"Plan", "plan":"Implement.",
                           "acceptance_criteria":["Works"], "verification":["Tests"]})
        hd.collect(task); fp.decision(task); fp.authorize(self.run, 1); fp.start(self.run)

    def discussion_finished(self):
        task = self.director()
        self.report(task, {"kind":"reply", "user_response":"Advice"})
        hd.collect(task); fp.decision(task); fp.finish(self.run, discussion=True)
        return task

    def test_main_pair_must_match(self):
        self.setup_api()
        with self.assertRaises(fp.Failure): hd.initialize(str(self.project), self.input, "main-pane", "wrong")

    def test_main_conversation_must_match(self):
        self.setup_api(); self.api.panes[0]["agent_session"] = "another-conversation"
        with self.assertRaises(fp.Failure): hd.main_pane(fp.run_at(self.run)[1], self.api)

    def test_main_terminal_move_is_followed(self):
        self.setup_api(); self.api.panes[0]["pane_id"] = "moved-main"
        self.assertEqual(hd.main_pane(fp.run_at(self.run)[1], self.api)["pane_id"], "moved-main")

    def test_reused_pane_with_other_terminal_rejected(self):
        self.setup_api(); self.api.panes[0]["terminal_id"] = "replacement"
        with self.assertRaises(fp.Failure): hd.main_pane(fp.run_at(self.run)[1], self.api)

    def test_spawn_director_no_focus_fixed_permissions(self):
        task = self.director(); data = fp.task_at(task)[1]
        split = next(c for c in self.api.calls if c[:2] == ("pane", "split"))
        self.assertIn("--no-focus", split); self.assertEqual(split[2], "main-pane")
        args = data["requested_codex_args"]
        self.assertEqual(args[args.index("-m")+1], "gpt-6-astra")
        self.assertIn('model_reasoning_effort="xhigh"', args)
        self.assertIn('default_permissions=":workspace"', args)
        self.assertEqual(args[args.index("--sandbox")+1], "workspace-write")
        self.assertEqual(args[args.index("--ask-for-approval")+1], "never")
        self.assertFalse(any("service_tier" in arg for arg in args))

    def test_worker_not_spawned_before_plan(self):
        self.setup_api()
        with self.assertRaises(fp.Failure): hd.spawn(self.run, "worker", self.input)
        self.assertFalse(any(c[:2] == ("pane", "split") for c in self.api.calls))

    def test_worker_splits_owned_area_and_requests_fast(self):
        director = self.director(); self.director_plan(director)
        worker = hd.spawn(self.run, "worker", self.input)["task"]
        splits = [c for c in self.api.calls if c[:2] == ("pane", "split")]
        self.assertEqual(splits[-1][2], fp.task_at(director)[1]["handle"]["pane_id"])
        args = fp.task_at(worker)[1]["requested_codex_args"]
        self.assertIn('service_tier="fast"', args)
        self.assertIn('model_reasoning_effort="max"', args)

    def test_followup_reuses_session(self):
        task = self.director(); original = fp.task_at(task)[1]["handle"]
        self.report(task, {"kind":"reply", "user_response":"Need more context"}); hd.collect(task)
        hd.send(task, self.input)
        self.assertEqual(fp.task_at(task)[1]["handle"], original)
        self.assertEqual(sum(c[:2] == ("agent", "start") for c in self.api.calls), 1)

    def test_busy_session_not_prompted(self):
        task = self.director(); data = fp.task_at(task)[1]
        self.api.registered[data["name"]]["agent_status"] = "working"
        before = len(self.api.calls)
        with self.assertRaises(fp.Failure): hd.send(task, self.input)
        self.assertEqual(len(self.api.calls), before+1)  # Only Main identity inspection.

    def test_partial_delivery_is_recorded_not_duplicated(self):
        self.setup_api(); self.api.fail_prompt = True
        with self.assertRaises(fp.Failure): hd.spawn(self.run, "director", self.input)
        saved = fp.tasks(Path(self.run))
        self.assertEqual(len(saved), 1); self.assertEqual(saved[0][1]["delivery"], "uncertain")
        with self.assertRaises(fp.Failure): hd.spawn(self.run, "director", self.input)
        self.assertEqual(sum(c[:2] == ("pane", "split") for c in self.api.calls), 1)

    def test_close_rejects_activity_after_collection(self):
        task = self.discussion_finished(); data = fp.task_at(task)[1]
        self.api.registered[data["name"]]["state_change_seq"] += 1
        with self.assertRaises(fp.Failure): hd.close(task)
        self.assertFalse(any(c[:2] == ("pane", "close") for c in self.api.calls))

    def test_close_rejects_wrong_terminal_identity(self):
        task = self.discussion_finished(); data = fp.task_at(task)[1]
        self.api.registered[data["name"]]["terminal_id"] = "unrelated"
        with self.assertRaises(fp.Failure): hd.close(task)

    def test_close_only_owned_completed_participant(self):
        task = self.discussion_finished(); hd.close(task)
        closed = [c[2] for c in self.api.calls if c[:2] == ("pane", "close")]
        self.assertEqual(closed, [fp.task_at(task)[1]["handle"]["pane_id"]])
        self.assertNotIn("main-pane", closed)

    def test_wait_idle_retention_is_not_pending(self):
        task = self.director(); self.report(task, {"kind":"reply", "user_response":"Advice"}); hd.collect(task)
        self.assertEqual(hd.wait(self.run, timeout=0), {"events":[], "pending":0})
        self.assertFalse(fp.task_at(task)[1]["closed"])

    def test_wait_suppresses_unchanged_blocker_not_resolution(self):
        task = self.director(); self.report(task, "Missing tool", status="blocked"); hd.collect(task)
        first = hd.wait(self.run, timeout=0); second = hd.wait(self.run, timeout=0)
        self.assertEqual(len(first["events"]), 1)
        self.assertEqual(second["events"], []); self.assertEqual(second["pending"], 1)
        self.assertTrue(second["timeout"])

    def test_duplicate_waiter_rejected(self):
        self.setup_api(); path = Path(self.run) / ".wait.lock"; path.write_text("another waiter")
        with self.assertRaises(fp.Failure): hd.wait(self.run, timeout=0)
        self.assertTrue(path.exists())

    def test_wait_notifies_missing_original_agent(self):
        task = self.director(); self.api.registered.clear()
        events = hd.wait(self.run, timeout=0)["events"]
        self.assertEqual(events, [{"task":task, "event":"unavailable"}])


if __name__ == "__main__": unittest.main()
