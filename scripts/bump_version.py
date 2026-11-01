"""Cut a release: bump the version in pyproject.toml and date the [Unreleased] changelog entries.

Usage (from the repo root):
    python -m scripts.bump_version patch|minor|major [--dry-run]
    python -m scripts.bump_version 0.4.0 [--dry-run]
"""

import argparse
import re
import sys
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PYPROJECT = ROOT / "pyproject.toml"
CHANGELOG = ROOT / "CHANGELOG.md"

VERSION_LINE = re.compile(r'^version = "([^"]+)"', re.MULTILINE)
SECTION_HEADING = re.compile(r"^## \[([^\]]+)\].*$", re.MULTILINE)
UNRELEASED = "Unreleased"


def parse_version(version: str) -> tuple[int, int, int]:
    match = re.fullmatch(r"(\d+)\.(\d+)\.(\d+)", version)
    if not match:
        raise ValueError(f"Not a MAJOR.MINOR.PATCH version: {version!r}")
    return tuple(int(part) for part in match.groups())


def bump(current: str, part: str) -> str:
    """Return the next version: `part` is major/minor/patch or an explicit X.Y.Z."""
    major, minor, patch = parse_version(current)
    if part == "major":
        return f"{major + 1}.0.0"
    if part == "minor":
        return f"{major}.{minor + 1}.0"
    if part == "patch":
        return f"{major}.{minor}.{patch + 1}"
    if parse_version(part) <= (major, minor, patch):
        raise ValueError(f"New version {part} must be higher than the current {current}")
    return part


def read_pyproject_version(pyproject_text: str) -> str:
    match = VERSION_LINE.search(pyproject_text)
    if not match:
        raise ValueError('No `version = "..."` line found in pyproject.toml')
    return match.group(1)


def set_pyproject_version(pyproject_text: str, version: str) -> str:
    return VERSION_LINE.sub(f'version = "{version}"', pyproject_text, count=1)


def extract_section(changelog_text: str, name: str) -> str | None:
    """Return the body of the `## [name]` section (without its heading), or None if missing."""
    headings = list(SECTION_HEADING.finditer(changelog_text))
    for i, heading in enumerate(headings):
        if heading.group(1) == name:
            end = headings[i + 1].start() if i + 1 < len(headings) else len(changelog_text)
            return changelog_text[heading.end() : end].strip()
    return None


def release_changelog(changelog_text: str, version: str, release_date: str) -> str:
    """Move the [Unreleased] entries into a new `## [version] - date` section."""
    unreleased = extract_section(changelog_text, UNRELEASED)
    if unreleased is None:
        raise ValueError("CHANGELOG.md has no '## [Unreleased]' section")
    if not unreleased:
        raise ValueError("The [Unreleased] section of CHANGELOG.md is empty; nothing to release")
    if extract_section(changelog_text, version) is not None:
        raise ValueError(f"CHANGELOG.md already has a section for {version}")

    heading = next(h for h in SECTION_HEADING.finditer(changelog_text) if h.group(1) == UNRELEASED)
    next_heading = next(
        (h for h in SECTION_HEADING.finditer(changelog_text) if h.start() > heading.start()), None
    )
    end = next_heading.start() if next_heading else len(changelog_text)
    released = f"## [{UNRELEASED}]\n\n## [{version}] - {release_date}\n\n{unreleased}\n" + (
        "\n" if next_heading else ""
    )
    return changelog_text[: heading.start()] + released + changelog_text[end:]


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("part", help="major, minor, patch, or an explicit X.Y.Z")
    parser.add_argument("--dry-run", action="store_true", help="print the result, write nothing")
    args = parser.parse_args(argv)

    pyproject_text = PYPROJECT.read_text()
    changelog_text = CHANGELOG.read_text()
    current = read_pyproject_version(pyproject_text)

    try:
        new = bump(current, args.part)
        new_changelog = release_changelog(changelog_text, new, date.today().isoformat())
    except ValueError as e:
        print(f"error: {e}", file=sys.stderr)
        return 1

    if args.dry_run:
        print(f"{current} -> {new} (dry run, nothing written)\n")
        print(f"## [{new}]\n\n{extract_section(new_changelog, new)}")
        return 0

    PYPROJECT.write_text(set_pyproject_version(pyproject_text, new))
    CHANGELOG.write_text(new_changelog)
    print(f"{current} -> {new}: updated pyproject.toml and CHANGELOG.md")
    return 0


if __name__ == "__main__":
    sys.exit(main())
