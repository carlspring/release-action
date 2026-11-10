"""
next_version.py — Compute the next release version from the existing tags.

Tags are expected to look like "MAJOR.MINOR.PATCH" with an optional "v" prefix
and an optional "-SUFFIX" (e.g. "1.2.3", "v1.2.3", "1.2.3-rc-1"). Tags that
don't match (alias tags such as "v1", or anything else) are ignored.

The latest version tag is bumped as follows:
    1.2.3        -> 1.3.0         (increment the minor number, reset the patch number)
    1.2.3-rc-1   -> 1.2.3-rc-2    (increment the pre-release number)
    1.2.3-beta   -> 1.3.0         (unrecognised suffix: increment the minor number)
The "v" prefix, if any, is kept. With no version tags at all, the result is
INITIAL_VERSION.
"""
import re
import subprocess

INITIAL_VERSION = "1.0.0"

_VERSION_RE = re.compile(r"^(?P<prefix>v?)(?P<major>\d+)\.(?P<minor>\d+)\.(?P<patch>\d+)"
                         r"(?P<suffix>-.+)?$")
_SUFFIX_RE = re.compile(r"^-(?P<type>.+)-(?P<number>\d+)$")


def _sort_key(match):
    """Order versions numerically, with a pre-release before its final release."""
    numbers = tuple(int(match[part]) for part in ("major", "minor", "patch"))
    suffix = match["suffix"]
    if not suffix:
        return numbers + (1, "", 0)
    pre = _SUFFIX_RE.match(suffix)
    if pre:
        return numbers + (0, pre["type"], int(pre["number"]))
    return numbers + (0, suffix, 0)


def latest_version_tag(tags):
    """Return the highest version among tags, or None if none of them is a version."""
    matches = [m for m in (_VERSION_RE.match(t) for t in tags) if m]
    if not matches:
        return None
    return max(matches, key=_sort_key).string


def bump(tag):
    """Return the version that follows tag (see the module docstring for the rules)."""
    match = _VERSION_RE.match(tag)
    if not match:
        raise ValueError(f"Not a version tag: {tag}")
    prefix, major, minor, patch = (match[p] for p in ("prefix", "major", "minor", "patch"))
    pre = _SUFFIX_RE.match(match["suffix"] or "")
    if pre:
        return f"{prefix}{major}.{minor}.{patch}-{pre['type']}-{int(pre['number']) + 1}"
    return f"{prefix}{major}.{int(minor) + 1}.0"


def next_version(tags):
    """Return the next version given the existing tags."""
    latest = latest_version_tag(tags)
    return bump(latest) if latest else INITIAL_VERSION


def get_tags():
    """Return the tags reachable from HEAD."""
    result = subprocess.run(
        ["git", "tag", "--merged", "HEAD"],
        capture_output=True, text=True, check=True,
    )
    return result.stdout.split()
