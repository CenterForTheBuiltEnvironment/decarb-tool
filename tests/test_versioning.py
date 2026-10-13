"""Tests for the release tooling (scripts/) and the single-sourced app version."""

import tomllib

import pytest
from scripts.bump_version import CHANGELOG as CHANGELOG_PATH
from scripts.bump_version import (
    PYPROJECT,
    bump,
    extract_section,
    read_pyproject_version,
    release_changelog,
    set_pyproject_version,
)
from scripts.check_release import check_release

from layout.footer import shell_footer
from utils.version import get_version

CHANGELOG = """# Changelog

Intro text.

## [Unreleased]

### Fixed

- A bug

## [0.1.0] - 2026-01-01

### Added

- First release
"""


@pytest.mark.unit
class TestBump:
    @pytest.mark.parametrize(
        ("part", "expected"),
        [("patch", "0.1.1"), ("minor", "0.2.0"), ("major", "1.0.0"), ("0.3.0", "0.3.0")],
    )
    def test_bump(self, part, expected):
        assert bump("0.1.0", part) == expected

    @pytest.mark.parametrize("part", ["0.1.0", "0.0.9", "1.0", "v0.2.0"])
    def test_rejects_invalid_or_lower_version(self, part):
        with pytest.raises(ValueError):
            bump("0.1.0", part)

    def test_pyproject_version_roundtrip(self):
        text = '[project]\nname = "x"\nversion = "0.1.0"\n\n[tool.ruff]\ntarget-version = "py312"\n'
        new = set_pyproject_version(text, "0.2.0")
        assert read_pyproject_version(new) == "0.2.0"
        assert 'target-version = "py312"' in new


@pytest.mark.unit
class TestChangelog:
    def test_extract_section(self):
        assert extract_section(CHANGELOG, "Unreleased") == "### Fixed\n\n- A bug"
        assert extract_section(CHANGELOG, "0.1.0") == "### Added\n\n- First release"
        assert extract_section(CHANGELOG, "9.9.9") is None

    def test_release_moves_unreleased_entries(self):
        new = release_changelog(CHANGELOG, "0.1.1", "2026-02-01")
        assert extract_section(new, "Unreleased") == ""
        assert extract_section(new, "0.1.1") == "### Fixed\n\n- A bug"
        assert extract_section(new, "0.1.0") == "### Added\n\n- First release"
        assert "## [0.1.1] - 2026-02-01" in new
        assert new.index("## [Unreleased]") < new.index("## [0.1.1]") < new.index("## [0.1.0]")
        assert new.startswith("# Changelog\n\nIntro text.\n\n")

    def test_release_refuses_empty_unreleased(self):
        released = release_changelog(CHANGELOG, "0.1.1", "2026-02-01")
        with pytest.raises(ValueError, match="empty"):
            release_changelog(released, "0.1.2", "2026-03-01")


@pytest.mark.unit
class TestCheckRelease:
    def test_valid_release(self):
        released = release_changelog(CHANGELOG, "0.1.1", "2026-02-01")
        assert check_release("0.1.1", released, "0.1.0", base_has_changelog=True) == []

    def test_flags_missing_bump_section_and_unreleased_entries(self):
        problems = check_release("0.1.0", CHANGELOG.replace("0.1.0", "0.0.1"), "0.1.0", True)
        assert len(problems) == 3

    def test_first_release_may_restart_numbering(self):
        released = release_changelog(CHANGELOG, "0.1.1", "2026-02-01")
        assert check_release("0.1.1", released, "1.2.0", base_has_changelog=False) == []


@pytest.mark.unit
def test_app_version_comes_from_pyproject():
    with PYPROJECT.open("rb") as f:
        assert get_version() == tomllib.load(f)["project"]["version"]
    assert f"Version {get_version()}" in str(shell_footer())


@pytest.mark.unit
def test_repo_changelog_has_current_version():
    assert extract_section(CHANGELOG_PATH.read_text(), get_version()) is not None
