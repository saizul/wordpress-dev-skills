"""Shared helpers: load skill scripts as modules (they are not a package)."""

from __future__ import annotations

import importlib.util
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
FIXTURES = Path(__file__).resolve().parent / "fixtures"


def load_script(skill: str, filename: str):
    path = ROOT / "skills" / skill / "scripts" / filename
    name = f"skill_{skill.replace('-', '_')}_{path.stem}"
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def run_script(skill: str, filename: str, *args: str, stdin: str | None = None):
    path = ROOT / "skills" / skill / "scripts" / filename
    return subprocess.run(
        [sys.executable, str(path), *args],
        input=stdin,
        capture_output=True,
        text=True,
        check=False,
    )


@pytest.fixture
def fixtures() -> Path:
    return FIXTURES
