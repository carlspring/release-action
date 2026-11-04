"""
release_notes.py — Group commits or pull requests into release-note sections
based on their Conventional Commits prefix (https://www.conventionalcommits.org),
e.g. "feat(api): add endpoint" goes under "Features" with the scope "api".

Messages without a recognised prefix are listed under "Other Changes".
Breaking changes ("feat!: ..." or a "BREAKING CHANGE:" footer) are listed
once, in a "Breaking Changes" section at the top.
"""
import re

# Section order in the rendered notes. Each conventional type maps to one section.
SECTIONS = [
    ("feat", "Features"),
    ("fix", "Bug Fixes"),
    ("perf", "Performance"),
    ("refactor", "Code Refactoring"),
    ("docs", "Documentation"),
    ("test", "Tests"),
    ("build", "Build"),
    ("ci", "CI"),
    ("style", "Styles"),
    ("revert", "Reverts"),
    ("chore", "Chores"),
]
BREAKING_TITLE = "⚠ Breaking Changes"
OTHER_TITLE = "Other Changes"

_KNOWN_TYPES = {t for t, _ in SECTIONS}
_HEADER_RE = re.compile(r"^(?P<type>\w+)(?:\((?P<scope>[^)]*)\))?(?P<bang>!)?:\s*(?P<subject>.+)$")
_BREAKING_FOOTER_RE = re.compile(r"^BREAKING[ -]CHANGE:", re.MULTILINE)


def parse_message(message):
    """Parse a commit message or PR title into type, scope, subject and breaking flag.

    "type" is None when the message has no recognised conventional prefix; the
    subject is then the whole first line.
    """
    lines = message.strip().splitlines()
    header = lines[0].strip() if lines else ""
    body = "\n".join(lines[1:])

    match = _HEADER_RE.match(header)
    if match and match["type"].lower() in _KNOWN_TYPES:
        return {
            "type": match["type"].lower(),
            "scope": (match["scope"] or "").strip() or None,
            "subject": match["subject"].strip(),
            "breaking": bool(match["bang"]) or bool(_BREAKING_FOOTER_RE.search(body)),
        }

    # Commits created by "git revert" have no conventional prefix.
    commit_type = "revert" if header.startswith('Revert "') else None
    return {"type": commit_type, "scope": None, "subject": header, "breaking": False}


def _format_entry(entry):
    scope = f"**{entry['scope']}**: " if entry["scope"] else ""
    return f"- {scope}{entry['subject']} {entry['ref']}"


def render_sections(entries):
    """Render entries as "### <Section>" blocks in SECTIONS order, skipping empty ones.

    Each entry is a parse_message() result plus a "ref" string (the link
    appended to the line). Entries keep their input order within a section.
    """
    groups = {title: [] for title in [BREAKING_TITLE] + [t for _, t in SECTIONS] + [OTHER_TITLE]}
    titles = dict(SECTIONS)
    for entry in entries:
        if entry["breaking"]:
            title = BREAKING_TITLE
        else:
            title = titles.get(entry["type"], OTHER_TITLE)
        groups[title].append(_format_entry(entry))

    return "\n\n".join(
        f"### {title}\n\n" + "\n".join(lines)
        for title, lines in groups.items() if lines
    )


def commit_entries(commits, repo_url):
    """Build entries from commits, each a dict with "sha" and "message"."""
    return [
        {**parse_message(c["message"]),
         "ref": f"([{c['sha'][:8]}]({repo_url}/commit/{c['sha']}))"}
        for c in commits
    ]


def format_pr_attribution(pr):
    """Return the attribution string for a PR, e.g. '@carlspring, @Copilot'.

    Rules:
    - Bot-suffix usernames like 'dependabot[bot]' are normalised to 'dependabot'.
    - PRs authored by Copilot list the non-Copilot assignees first, then @Copilot.
    """
    def clean(login):
        return login.replace("[bot]", "")

    author = clean(pr["user"])
    # The GitHub Copilot SWE agent uses the plain login "Copilot" (no [bot] suffix).
    if author == "Copilot":
        others = [clean(a) for a in pr.get("assignees", []) if clean(a) != "Copilot"]
        mentions = others + ["Copilot"]
        return ", ".join(f"@{m}" for m in mentions)
    return f"@{author}"


def pr_entries(prs):
    """Build entries from merged PRs, categorised by their title."""
    return [
        {**parse_message(pr["title"]),
         "ref": f"([#{pr['number']}]({pr['html_url']})) ({format_pr_attribution(pr)})"}
        for pr in prs
    ]
