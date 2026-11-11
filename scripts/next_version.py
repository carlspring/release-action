"""
next_version.py — Compute the next release version from the existing tags.

Version tags look like "MAJOR.MINOR.PATCH" with an optional "v" prefix and an
optional "-SUFFIX" (e.g. "1.2.3", "v1.2.3", "1.2.3-rc-1"). Other tags (alias
tags such as "v1", or anything else) are ignored.

Pre-releases must follow the convention "-TYPE-N", where TYPE is one of
PRE_RELEASE_TYPES. They rank in that order, below their final release:
    1.2.3-alpha-1 < 1.2.3-beta-1 < 1.2.3-milestone-1 < 1.2.3-rc-1 < 1.2.3

The latest version tag is bumped as follows:
    1.2.3        -> 1.2.4         (increment the patch number)
    1.2.3-rc-1   -> 1.2.3-rc-2    (increment the pre-release number)
The "v" prefix, if any, is kept. With no version tags at all, the result is
INITIAL_VERSION.

If the latest version tag has any other suffix (e.g. "1.2.3-beta", "1.2.3-rc1",
"1.2.3-rc.1"), no version is guessed: ValueError is raised. Such a tag ranks
above the pre-releases of its version, so it can't be skipped silently.
"""
import re
import subprocess

INITIAL_VERSION = "1.0.0"

PRE_RELEASE_TYPES = ("alpha", "beta", "milestone", "rc")

_VERSION_RE = re.compile(r"^(?P<prefix>v?)(?P<major>\d+)\.(?P<minor>\d+)\.(?P<patch>\d+)"
                         r"(?P<suffix>-.+)?$")
_PRE_RELEASE_RE = re.compile(rf"^-(?P<type>{'|'.join(PRE_RELEASE_TYPES)})-(?P<number>\d+)$")

# Rank within one MAJOR.MINOR.PATCH: pre-releases by type, then any
# unconventional suffix, then the final release.
_UNCONVENTIONAL_RANK = len(PRE_RELEASE_TYPES)
_FINAL_RANK = len(PRE_RELEASE_TYPES) + 1


def _sort_key(match):
    """Order versions numerically, with pre-releases before their final release."""
    numbers = tuple(int(match[part]) for part in ("major", "minor", "patch"))
    suffix = match["suffix"]
    if not suffix:
        return numbers + (_FINAL_RANK, 0)
    pre = _PRE_RELEASE_RE.match(suffix)
    if pre:
        return numbers + (PRE_RELEASE_TYPES.index(pre["type"]), int(pre["number"]))
    return numbers + (_UNCONVENTIONAL_RANK, 0)


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
    suffix = match["suffix"]
    if not suffix:
        return f"{prefix}{major}.{minor}.{int(patch) + 1}"
    pre = _PRE_RELEASE_RE.match(suffix)
    if not pre:
        conventions = ", ".join(f"-{t}-N" for t in PRE_RELEASE_TYPES)
        raise ValueError(
            f"Cannot compute the next version: the latest version tag {tag} doesn't follow "
            f"the pre-release convention ({conventions}). Set the tag explicitly."
        )
    return f"{prefix}{major}.{minor}.{patch}-{pre['type']}-{int(pre['number']) + 1}"


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
