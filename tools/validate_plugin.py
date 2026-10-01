#!/usr/bin/env python3
"""Validate a checkout or an extracted, instructions-only FrontierPlan plugin."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import re

DEFAULT = Path(__file__).resolve().parents[1] / "plugins/frontierplan"
SKILLS = {"astraplan-herdr", "astraplan-herdr-swe2", "astraplan-subagent"}
RESOURCES = (
    "core/workflow.md", "core/roles.md", "backends/herdr.md",
    "backends/swe2.md", "backends/subagent.md", "LICENSE", "THIRD_PARTY_NOTICES.md",
)


def validate(root: Path) -> list[str]:
    root = root.resolve()
    errors = []

    def check(condition, message):
        if not condition:
            errors.append(message)

    try:
        portable = json.loads((root / "plugin.json").read_text())
        codex = json.loads((root / ".codex-plugin/plugin.json").read_text())
        claude = json.loads((root / ".claude-plugin/plugin.json").read_text())
        check(portable.get("name") == "frontierplan", "Wrong plugin name")
        check(portable.get("$schema") == "https://agent-plugins.org/schemas/1.0.0/plugin.schema.json",
              "Missing portable manifest schema")
        check(re.fullmatch(r"\d+\.\d+\.\d+", portable.get("version", "")),
              "Invalid plugin version")
        for key in ("name", "version", "description", "author", "repository", "license"):
            check(portable.get(key) == codex.get(key), f"Codex manifest drift: {key}")
            check(portable.get(key) == claude.get(key), f"Claude Code manifest drift: {key}")
        check(portable["extensions"]["com.openai"]["interface"] == codex["interface"],
              "Interface metadata drift")
        check(codex.get("skills") == "./skills/", "Invalid Codex skills path")

        skills = {p.name for p in (root / "skills").iterdir() if p.is_dir()}
        check(skills == SKILLS, "Exactly three implemented SKILLs must ship")
        for skill in sorted(skills):
            body = (root / "skills" / skill / "SKILL.md").read_text()
            match = re.search(r"(?s)\A---\n(.*?)\n---(?:\n|$)", body)
            frontmatter = match.group(1) if match else ""
            check(re.search(rf"(?m)^name: {re.escape(skill)}$", frontmatter),
                  f"Skill frontmatter mismatch: {skill}")
            check(re.search(r"(?m)^description: \S.+$", frontmatter),
                  f"Missing skill description: {skill}")
            triggers = re.search(r"(?m)^triggers:[ \t]*(.*(?:\n[ \t]+-[ \t]*\w+)*)",
                                 frontmatter)
            check(triggers and set(re.findall(r"\w+", triggers.group(1))) == {"user"},
                  f"Explicit-only Devin triggers required: {skill}")
            check(re.search(r"(?m)^disable-model-invocation:[ \t]*true[ \t]*$", frontmatter),
                  f"Explicit-only Claude Code invocation required: {skill}")
            policy = (root / "skills" / skill / "agents/openai.yaml").read_text()
            check(re.search(r"(?m)^  allow_implicit_invocation: false\s*$", policy),
                  f"Explicit-only Codex invocation required: {skill}")
            check(f"$frontierplan:{skill}" in policy, f"Wrong skill prompt: {skill}")

        for resource in RESOURCES:
            path = root / resource
            check(path.is_file() and path.resolve().is_relative_to(root),
                  f"Missing/outside packaged resource: {resource}")
        for path in root.rglob("*"):
            if path.is_file():
                check(path.suffix not in {".py", ".toml"},
                      f"Runtime code/profile in instructions-only plugin: {path.relative_to(root)}")
        for path in root.rglob("*.md"):
            for target in re.findall(r"\]\(([^)]+)\)", path.read_text()):
                if "://" in target or target.startswith("#"):
                    continue
                resolved = (path.parent / target.split("#")[0]).resolve()
                check(resolved.is_relative_to(root) and resolved.is_file(),
                      f"Broken/outside package link: {path.relative_to(root)}: {target}")
    except (OSError, ValueError, KeyError, TypeError, AttributeError) as exc:
        errors.append(str(exc))
    return errors


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--plugin", type=Path, default=DEFAULT)
    errors = validate(parser.parse_args().plugin)
    if errors:
        raise SystemExit("\n".join(errors))
    print("FrontierPlan package validation: OK")
