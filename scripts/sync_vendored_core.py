#!/usr/bin/env python3
"""Copy src/energy_engine into custom_components/energy_engine/core.

HACS only ever checks out custom_components/energy_engine/ into a user's Home
Assistant config - it never sees src/. The HA integration vendors the core
engine to be self-contained, so this script has to be run (and its output
committed) whenever src/energy_engine changes, before tagging a release.
"""

from __future__ import annotations

import shutil
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
SOURCE = REPO_ROOT / "src" / "energy_engine"
DEST = REPO_ROOT / "custom_components" / "energy_engine" / "core"


def main() -> None:
    if DEST.exists():
        shutil.rmtree(DEST)
    shutil.copytree(
        SOURCE,
        DEST,
        ignore=shutil.ignore_patterns("__pycache__", "*.pyc"),
    )
    print(f"Vendored {SOURCE} -> {DEST}")


if __name__ == "__main__":
    main()
