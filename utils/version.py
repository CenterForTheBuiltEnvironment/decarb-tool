"""Single source of truth for the app version: `[project].version` in pyproject.toml."""

import tomllib
from functools import cache
from pathlib import Path

PYPROJECT = Path(__file__).resolve().parent.parent / "pyproject.toml"


@cache
def get_version() -> str:
    with PYPROJECT.open("rb") as f:
        return tomllib.load(f)["project"]["version"]
