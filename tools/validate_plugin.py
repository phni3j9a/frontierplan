#!/usr/bin/env python3
"""Validate a checkout or a standalone extracted FrontierPlan plugin."""
from __future__ import annotations

import argparse
import ast
import json
from pathlib import Path
import re
import tomllib

DEFAULT = Path(__file__).resolve().parents[1] / "plugins" / "frontierplan"


def validate(root: Path) -> list[str]:
    errors = []
    def check(ok, msg):
        if not ok: errors.append(msg)
    try:
        manifest = json.loads((root / "plugin.json").read_text())
        legacy = json.loads((root / ".codex-plugin/plugin.json").read_text())
        check(manifest.get("name") == "frontierplan", "Wrong plugin name")
        check(manifest.get("$schema") == "https://agent-plugins.org/schemas/1.0.0/plugin.schema.json", "Missing portable manifest schema")
        for key in ("name", "version", "description", "author", "repository", "license"):
            check(manifest.get(key) == legacy.get(key), f"Compatibility manifest drift: {key}")
        check(manifest["extensions"]["com.openai"]["interface"] == legacy["interface"], "Interface metadata drift")
        check(legacy.get("skills") == "./skills/", "Invalid legacy skills path")
        skills = {p.name for p in (root / "skills").iterdir() if p.is_dir()}
        check(skills == {"astraplan-herdr", "astraplan-subagent"}, "Exactly two implemented SKILLs must ship")
        for skill in skills:
            body = (root / "skills" / skill / "SKILL.md").read_text()
            check(body.startswith(f"---\nname: {skill}\n"), f"Skill frontmatter mismatch: {skill}")
            frontmatter = re.search(r"(?ms)\A---\n(.*?)\n---", body)
            triggers = re.search(r"(?m)^triggers:[ \t]*(.*(?:\n[ \t]+-[ \t]*\w+)*)",
                                 frontmatter.group(1) if frontmatter else "")
            check(triggers and set(re.findall(r"\w+", triggers.group(1))) == {"user"},
                  f"Explicit-only Devin triggers required: {skill}")
            policy = (root / "skills" / skill / "agents/openai.yaml").read_text()
            check(bool(re.search(r"(?m)^  allow_implicit_invocation: false\s*$", policy)), f"Explicit invocation required: {skill}")
            check(f"$frontierplan:{skill}" in policy, f"Wrong skill prompt: {skill}")
        profiles = sorted((root / "profiles").rglob("*.toml"))
        expected = {"director": ("gpt-6-astra", "xhigh"), "main": (None, None),
                    "worker": ("gpt-5.6-luna", "max"), "design": ("gpt-5.6-sol", "max"),
                    "reviewer": ("gpt-5.6-sol", "xhigh")}
        seen = set()
        for path in profiles:
            data = tomllib.loads(path.read_text())
            role = data.get("role")
            check(role in expected and role not in seen, f"Unexpected/duplicate profile: {path}")
            seen.add(role)
            if role == "main":
                check(data.get("inherit_session") is True and
                      not {"model", "reasoning_effort", "service_tier"} & data.keys(),
                      "Main must inherit the existing session without routing overrides")
            check((data.get("model"), data.get("reasoning_effort")) == expected.get(role), f"Model/effort mismatch: {path}")
            check((role == "worker" and data.get("service_tier") == "fast") or
                  (role != "worker" and "service_tier" not in data), f"Unexpected tier override: {path}")
        check(seen == set(expected), "Missing role profile")
        for required in ("core/workflow.md", "core/roles.md", "core/handoff.md", "core/review.md",
                         "backends/herdr.md", "backends/subagent.md", "scripts/frontierplan.py",
                         "scripts/herdr.py", "LICENSE", "THIRD_PARTY_NOTICES.md"):
            check((root / required).is_file(), f"Missing packaged resource: {required}")
        for path in root.rglob("*.md"):
            for example in re.findall(r"```json\n(.*?)\n```", path.read_text(), re.S):
                json.loads(example)
            for target in re.findall(r"\]\(([^)]+)\)", path.read_text()):
                if "://" in target or target.startswith("#"): continue
                resolved = (path.parent / target.split("#")[0]).resolve()
                check(resolved.is_relative_to(root.resolve()) and resolved.exists(), f"Broken/outside package link: {path}: {target}")
        for path in (root / "scripts").glob("*.py"):
            ast.parse(path.read_text(), filename=str(path))
    except (OSError, ValueError, KeyError, SyntaxError) as exc:
        errors.append(str(exc))
    return errors


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--plugin", type=Path, default=DEFAULT)
    errors = validate(parser.parse_args().plugin)
    if errors:
        raise SystemExit("\n".join(errors))
    print("FrontierPlan package validation: OK")
