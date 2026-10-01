"""Package behavior tests. No model, external service or Herdr runtime required."""
from __future__ import annotations

import json
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest
import zipfile

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))
from package_release import package
from validate_plugin import SKILLS, validate


class PackageChecks(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name) / "repo"
        self.plugin = self.root / "plugins/frontierplan"
        shutil.copytree(ROOT / "plugins/frontierplan", self.plugin,
                        ignore=shutil.ignore_patterns("__pycache__"))
        (self.root / ".gitignore").write_text(".claude/\ndist/\n__pycache__/\n")
        (self.root / "README.md").write_text("A source file.\n")
        self.git("init", "--quiet")
        self.git("add", ".")

    def git(self, *args):
        return subprocess.check_output(["git", "-C", str(self.root), *args],
                                       stderr=subprocess.PIPE)

    def replace(self, relative, before, after):
        path = self.plugin / relative
        body = path.read_text()
        self.assertIn(before, body)
        path.write_text(body.replace(before, after))

    def test_checkout_and_independent_copy_validate(self):
        self.assertEqual(validate(ROOT / "plugins/frontierplan"), [])
        self.assertEqual(validate(self.plugin), [])

    def test_manifest_drift_is_rejected(self):
        for manifest in (".codex-plugin/plugin.json", ".claude-plugin/plugin.json"):
            with self.subTest(manifest=manifest):
                path = self.plugin / manifest
                original = path.read_text()
                data = json.loads(original)
                data["version"] = "0.0.0"
                path.write_text(json.dumps(data))
                self.assertTrue(any("manifest drift: version" in e for e in validate(self.plugin)))
                path.write_text(original)

    def test_implicit_invocation_is_rejected_for_each_host(self):
        for skill in SKILLS:
            for file, before, after, host in (
                ("SKILL.md", "disable-model-invocation: true", "disable-model-invocation: false", "Claude Code"),
                ("SKILL.md", "  - user", "  - agent", "Devin"),
                ("agents/openai.yaml", "allow_implicit_invocation: false", "allow_implicit_invocation: true", "Codex"),
            ):
                with self.subTest(skill=skill, host=host):
                    relative = f"skills/{skill}/{file}"
                    original = (self.plugin / relative).read_text()
                    self.replace(relative, before, after)
                    self.assertTrue(any(f"Explicit-only {host}" in e for e in validate(self.plugin)))
                    (self.plugin / relative).write_text(original)

    def test_unknown_skill_is_rejected(self):
        shutil.copytree(self.plugin / "skills/astraplan-herdr",
                        self.plugin / "skills/automatic-fallback")
        self.assertIn("Exactly three implemented SKILLs must ship", validate(self.plugin))

    def test_missing_resource_is_rejected(self):
        (self.plugin / "core/workflow.md").unlink()
        self.assertTrue(any("Missing/outside packaged resource" in e for e in validate(self.plugin)))

    def test_local_links_must_resolve_inside_standalone_plugin(self):
        for target in ("missing.md", "../../../README.md"):
            with self.subTest(target=target):
                path = self.plugin / "core/link-test.md"
                path.write_text(f"[reference]({target})\n")
                self.assertTrue(any("Broken/outside package link" in e for e in validate(self.plugin)))
                path.unlink()

    def test_external_links_do_not_need_a_network(self):
        (self.plugin / "core/link-test.md").write_text("[docs](https://example.invalid/docs)\n")
        self.assertEqual(validate(self.plugin), [])

    def test_runtime_code_and_profiles_are_rejected(self):
        for relative in ("scripts/controller.py", "profiles/worker.toml"):
            with self.subTest(relative=relative):
                path = self.plugin / relative
                path.parent.mkdir(exist_ok=True)
                path.write_text("# unexpected runtime resource\n")
                self.assertTrue(any("Runtime code/profile" in e for e in validate(self.plugin)))
                path.unlink()

    def test_invalid_manifest_reports_errors(self):
        (self.plugin / "plugin.json").write_text("{not json}")
        self.assertTrue(validate(self.plugin))

    def test_archives_are_standalone_and_use_only_tracked_files(self):
        for relative in (".claude/settings.local.json", "plugins/frontierplan/local-notes.md",
                         "docs/untracked.md", "dist/old.zip", "tests/__pycache__/test.pyc"):
            path = self.root / relative
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text("LOCAL ONLY\n")
        (self.root / "README.md").write_text("Working tree content, not the staged version.\n")
        archives = package(self.root / "dist", self.root)
        self.assertEqual(len(archives), 2)
        for archive_path in archives:
            with zipfile.ZipFile(archive_path) as archive:
                self.assertFalse(any("LOCAL ONLY" in archive.read(name).decode() for name in archive.namelist()))
                dest = Path(self.temp.name) / archive_path.stem
                archive.extractall(dest)
                plugin = dest if archive_path.name.endswith("-plugin.zip") else dest / "plugins/frontierplan"
                self.assertEqual(validate(plugin), [])
                self.assertFalse(any(p.suffix in {".py", ".toml"} for p in plugin.rglob("*")))
                if archive_path.name.endswith("-source.zip"):
                    self.assertEqual(archive.read("README.md").decode(),
                                     "Working tree content, not the staged version.\n")

    def test_new_required_resource_must_be_staged(self):
        self.git("rm", "--cached", "plugins/frontierplan/core/workflow.md")
        with self.assertRaisesRegex(ValueError, "stage new files first"):
            package(self.root / "dist", self.root)

    def test_tracked_symlink_does_not_export_its_target(self):
        external = Path(self.temp.name) / "private.txt"
        external.write_text("OUTSIDE CONTENT")
        (self.root / "private-link").symlink_to(external)
        self.git("add", "private-link")
        for archive_path in package(self.root / "dist", self.root):
            with zipfile.ZipFile(archive_path) as archive:
                self.assertNotIn("private-link", archive.namelist())

    def test_deleted_working_file_is_not_exported(self):
        (self.root / "README.md").unlink()
        source = package(self.root / "dist", self.root)[1]
        with zipfile.ZipFile(source) as archive:
            self.assertNotIn("README.md", archive.namelist())

    def test_source_packaging_requires_its_own_checkout(self):
        shutil.rmtree(self.root / ".git")
        with self.assertRaisesRegex(ValueError, "Git checkout"):
            package(self.root / "dist", self.root)


if __name__ == "__main__":
    unittest.main()
