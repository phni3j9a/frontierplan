#!/usr/bin/env python3
"""Build plugin/source ZIPs from Git-tracked working files; validate both exports."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import subprocess
import tempfile
import zipfile

from validate_plugin import validate

ROOT = Path(__file__).resolve().parents[1]


def tracked_files(root: Path) -> list[Path]:
    """Use the index as the inventory, reading current working-tree contents."""
    try:
        top = subprocess.check_output(
            ["git", "-C", str(root), "rev-parse", "--show-toplevel"],
            stderr=subprocess.PIPE, text=True).strip()
        if Path(top).resolve() != root.resolve():
            raise ValueError("Package from the repository root")
        names = subprocess.check_output(
            ["git", "-C", str(root), "ls-files", "--cached", "-z"],
            stderr=subprocess.PIPE).decode().split("\0")
    except subprocess.CalledProcessError as exc:
        raise ValueError("Source packaging needs a Git checkout; stage new files first") from exc
    return sorted({root / name for name in names if name})


def package(output: Path, root: Path = ROOT) -> list[Path]:
    root = root.resolve()
    plugin = root / "plugins/frontierplan"
    errors = validate(plugin)
    if errors:
        raise ValueError("\n".join(errors))
    files = tracked_files(root)
    version = json.loads((plugin / "plugin.json").read_text())["version"]
    output = output.resolve()
    output.mkdir(parents=True, exist_ok=True)
    archives = []
    for name, source in (("plugin", plugin), ("source", root)):
        target = output / f"frontierplan-v{version}-{name}.zip"
        with zipfile.ZipFile(target, "w", compression=zipfile.ZIP_DEFLATED) as archive:
            for file in files:
                if (not file.is_relative_to(source) or not file.is_file()
                        or file.is_symlink() or not file.resolve().is_relative_to(root)
                        or file.is_relative_to(output)):
                    continue
                archive.write(file, file.relative_to(source))
        archives.append(target)
    for archive_path, plugin_path in ((archives[0], Path(".")),
                                      (archives[1], Path("plugins/frontierplan"))):
        with tempfile.TemporaryDirectory() as temp:
            with zipfile.ZipFile(archive_path) as archive:
                archive.extractall(temp)
            errors = validate(Path(temp) / plugin_path)
            if errors:
                raise ValueError("Extracted package failed validation (stage new files first): "
                                 + "; ".join(errors))
    return archives


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=ROOT / "dist")
    for archive in package(parser.parse_args().output):
        print(archive)
