#!/usr/bin/env python3
"""Build self-contained plugin and source ZIPs and validate the extracted plugin."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import tempfile
import zipfile

from validate_plugin import validate

ROOT = Path(__file__).resolve().parents[1]
PLUGIN = ROOT / "plugins/frontierplan"


def package(output: Path) -> list[Path]:
    errors = validate(PLUGIN)
    if errors: raise ValueError("\n".join(errors))
    version = json.loads((PLUGIN / "plugin.json").read_text())["version"]
    output = output.resolve(); output.mkdir(parents=True, exist_ok=True)
    archives = []
    for name, source in (("plugin", PLUGIN), ("source", ROOT)):
        target = output / f"frontierplan-v{version}-{name}.zip"
        with zipfile.ZipFile(target, "w", compression=zipfile.ZIP_DEFLATED) as archive:
            for file in sorted(source.rglob("*")):
                rel = file.relative_to(source)
                if (not file.is_file() or file.is_symlink() or file.is_relative_to(output)
                        or any(part in (".git", "__pycache__", "dist", ".pytest_cache") for part in rel.parts)
                        or file.suffix in (".pyc", ".pyo")):
                    continue
                archive.write(file, rel)
        archives.append(target)
    with tempfile.TemporaryDirectory() as temp:
        with zipfile.ZipFile(archives[0]) as archive:
            archive.extractall(temp)
        errors = validate(Path(temp))
        if errors: raise ValueError("Extracted plugin failed validation: " + "; ".join(errors))
    return archives


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=ROOT / "dist")
    for archive in package(parser.parse_args().output):
        print(archive)
