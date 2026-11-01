"""CI checks for releases, and release notes for the GitHub Release.

Usage (from the repo root):
    python -m scripts.check_release --base-ref origin/main   # PR into main: is this a valid release?
    python -m scripts.check_release --notes                  # print the current version's changelog section
"""

import argparse
import subprocess
import sys

from scripts.bump_version import (
    CHANGELOG,
    PYPROJECT,
    UNRELEASED,
    extract_section,
    parse_version,
    read_pyproject_version,
)


def _git_show(ref: str, path: str) -> str | None:
    result = subprocess.run(["git", "show", f"{ref}:{path}"], capture_output=True, text=True)
    return result.stdout if result.returncode == 0 else None


def check_release(
    version: str, changelog_text: str, base_version: str, base_has_changelog: bool
) -> list[str]:
    """Return a list of problems; empty means the release is valid."""
    problems = []
    # The first versioned release (no CHANGELOG.md on the base yet) restarted the numbering at
    # 0.1.0, so the version-increase check only applies from then on.
    if base_has_changelog and parse_version(version) <= parse_version(base_version):
        problems.append(
            f"Version {version} is not higher than {base_version} on the base branch. "
            "Run `python -m scripts.bump_version patch|minor|major`."
        )
    if extract_section(changelog_text, version) is None:
        problems.append(f"CHANGELOG.md has no '## [{version}]' section.")
    if extract_section(changelog_text, UNRELEASED):
        problems.append(
            "CHANGELOG.md still has entries under [Unreleased]; "
            "run the bump script to move them into the release."
        )
    return problems


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--base-ref", help="git ref of the branch being merged into")
    group.add_argument("--notes", action="store_true", help="print the release notes")
    args = parser.parse_args(argv)

    version = read_pyproject_version(PYPROJECT.read_text())
    changelog_text = CHANGELOG.read_text()

    if args.notes:
        notes = extract_section(changelog_text, version)
        if notes is None:
            print(f"error: CHANGELOG.md has no section for {version}", file=sys.stderr)
            return 1
        print(notes)
        return 0

    base_pyproject = _git_show(args.base_ref, "pyproject.toml")
    if base_pyproject is None:
        print(f"error: could not read pyproject.toml at {args.base_ref}", file=sys.stderr)
        return 1
    base_version = read_pyproject_version(base_pyproject)
    base_has_changelog = _git_show(args.base_ref, "CHANGELOG.md") is not None

    problems = check_release(version, changelog_text, base_version, base_has_changelog)
    for problem in problems:
        print(f"error: {problem}", file=sys.stderr)
    if not problems:
        print(f"OK: releasing {version} (base: {base_version})")
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main())
