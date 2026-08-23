#!/usr/bin/env python3
"""
release.py — Create a git tag and a GitHub release built from the commits
since the previous tag. If any step after tag creation fails, everything
that was already created (tag, release, alias tags) is rolled back.

Environment variables required:
    GITHUB_TOKEN        Token with permission to push tags and manage releases
    GITHUB_REPOSITORY   "owner/repo" (set automatically by GitHub Actions)

Optional:
    GITHUB_OUTPUT        Path to the file GitHub Actions collects outputs from

Usage:
    python release.py --tag v1.2.3 [--target main] [--draft] [--prerelease]
                      [--aliases v1 v1.0]
"""
import argparse
import os
import subprocess
import sys
import time
import requests

API_URL = "https://api.github.com"


def run(cmd, check=True, capture=True):
    """Run a shell command, print its output, and return stdout (stripped)."""
    print(f"$ {' '.join(cmd)}")
    result = subprocess.run(cmd, capture_output=capture, text=True)
    if capture:
        if result.stdout:
            print(result.stdout.strip())
        if result.stderr:
            print(result.stderr.strip(), file=sys.stderr)
    if check and result.returncode != 0:
        raise RuntimeError(f"Command failed ({result.returncode}): {' '.join(cmd)}")
    return result.stdout.strip() if capture else ""


def set_output(name, value):
    """Write a step output for GitHub Actions (no-op if run outside Actions)."""
    output_file = os.environ.get("GITHUB_OUTPUT")
    if not output_file:
        return
    with open(output_file, "a") as f:
        f.write(f"{name}={value}\n")


class GitHubClient:
    def __init__(self, token, repo):
        self.repo = repo
        self.session = requests.Session()
        self.session.headers.update({
            "Authorization": f"Bearer {token}",
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
        })

    def create_release(self, tag_name, target_commitish, name, body, draft=False, prerelease=False):
        url = f"{API_URL}/repos/{self.repo}/releases"
        payload = {
            "tag_name": tag_name,
            "target_commitish": target_commitish,
            "name": name,
            "body": body,
            "draft": draft,
            "prerelease": prerelease,
        }
        resp = self.session.post(url, json=payload)
        resp.raise_for_status()
        return resp.json()

    def delete_release(self, release_id):
        url = f"{API_URL}/repos/{self.repo}/releases/{release_id}"
        resp = self.session.delete(url)
        if resp.status_code not in (204, 404):
            resp.raise_for_status()

    def get_prs_for_commits(self, commit_shas):
        """Return a de-duplicated list of merged PRs that include any of the given commits.

        Uses GET /repos/{owner}/{repo}/commits/{sha}/pulls to resolve each SHA.
        PRs are returned in ascending PR-number order (a reliable proxy for
        merge order within a single repo).

        Note: one API request is made per commit SHA. For very large commit ranges
        (hundreds of commits) this may be slow and could approach GitHub API rate limits
        (5,000 requests/hour for authenticated requests). In that case the release action
        will surface the underlying HTTP error.
        """
        seen = set()
        prs = []
        for sha in commit_shas:
            url = f"{API_URL}/repos/{self.repo}/commits/{sha}/pulls"
            resp = self.session.get(url)
            if resp.status_code in (404, 422):
                continue
            if resp.status_code in (403, 429):
                retry_after = int(resp.headers.get("Retry-After", "60"))
                print(f"Rate limited; sleeping {retry_after}s before retrying {sha}",
                      file=sys.stderr)
                time.sleep(retry_after)
                resp = self.session.get(url)
            resp.raise_for_status()
            for pr in resp.json():
                if pr["number"] in seen:
                    continue
                if not pr.get("merged_at"):
                    continue
                seen.add(pr["number"])
                prs.append({
                    "number": pr["number"],
                    "title": pr["title"],
                    "html_url": pr["html_url"],
                    "user": pr["user"]["login"],
                    "assignees": [a["login"] for a in (pr.get("assignees") or [])],
                })
        prs.sort(key=lambda p: p["number"])
        return prs


def _format_pr_attribution(pr):
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


def get_previous_tag():
    """Return the most recent tag reachable from HEAD, or None if there isn't one."""
    result = subprocess.run(
        ["git", "describe", "--tags", "--abbrev=0"],
        capture_output=True, text=True,
    )
    if result.returncode != 0:
        return None
    return result.stdout.strip()


def get_commits_in_range(previous_tag):
    """Return a list of commit SHAs reachable from HEAD but not from previous_tag.

    If previous_tag is None, returns an empty list (caller will fall back to git log).
    """
    if not previous_tag:
        return []
    result = subprocess.run(
        ["git", "log", f"{previous_tag}..HEAD", "--pretty=format:%H", "--no-merges"],
        capture_output=True, text=True,
    )
    if result.returncode != 0:
        return []
    return [sha for sha in result.stdout.strip().splitlines() if sha]


def build_release_body(gh, previous_tag, alias_list):
    """Build the GitHub release body from merged PRs since previous_tag.

    Uses the git commit range (previous_tag..HEAD) to identify which commits
    belong to this release, then resolves those commits to their associated PRs
    via the GitHub API. Falls back to a plain git log when no PRs are found.
    """
    commit_shas = get_commits_in_range(previous_tag)

    pr_list = gh.get_prs_for_commits(commit_shas) if commit_shas else []
    if pr_list:
        lines = [
            (f'* <a href="{pr["html_url"]}">'
             f'#{pr["number"]}: {pr["title"]}</a> ({_format_pr_attribution(pr)})')
            for pr in pr_list
        ]
        changelog = "\n".join(lines)
    else:
        # Fall back to git log when no PRs are found
        rev_range = f"{previous_tag}..HEAD" if previous_tag else "HEAD"
        log = run(
            ["git", "log", rev_range, "--pretty=format:- %s (%h)", "--no-merges"],
            check=False,
        )
        changelog = log if log else "No changes recorded."

    sections = [f"## Changes since {previous_tag or 'the beginning'}\n\n{changelog}"]

    for alias in alias_list:
        sections.append(f"This release is marked as the current `{alias}`.")

    return "\n\n".join(sections)


def create_git_tag(tag_name, message):
    run(["git", "tag", "-a", tag_name, "-m", message])
    run(["git", "push", "origin", tag_name])


def create_alias_tag(alias, tag_name):
    """Create (or force-update) a lightweight alias tag pointing to the commit of tag_name.

    Uses `rev-parse tag^{}` to dereference the tag to its underlying commit SHA
    (a no-op for lightweight tags, but correct for annotated tags). run() returns
    the stripped output, so the SHA is safe to pass directly to git tag.
    """
    commit_sha = run(["git", "rev-parse", f"{tag_name}^{{}}"])
    run(["git", "tag", "-f", alias, commit_sha])
    run(["git", "push", "--force", "origin", alias])


def delete_git_tag(tag_name):
    """Best-effort deletion of a tag on the remote and locally."""
    subprocess.run(["git", "push", "--delete", "origin", tag_name],
                   capture_output=True, text=True)
    subprocess.run(["git", "tag", "-d", tag_name],
                   capture_output=True, text=True)


def main():
    parser = argparse.ArgumentParser(
        description="Create a tagged GitHub release with rollback on failure."
    )
    parser.add_argument("--tag", required=True, help="Tag to create, e.g. v1.2.3")
    parser.add_argument("--target", default="main", help="Branch/commit the tag points to")
    parser.add_argument("--draft", action="store_true")
    parser.add_argument("--prerelease", action="store_true")
    parser.add_argument(
        "--aliases",
        default="",
        metavar="ALIAS_LIST",
        help="Space-separated alias tags to create, e.g. 'v1 v1.0'. "
             "Overridden by the RELEASE_ALIASES environment variable if set.",
    )
    args = parser.parse_args()
    # Allow aliases to be supplied via env var (avoids shell word-splitting issues).
    # The env var takes precedence only when it is non-empty.
    aliases_env = os.environ.get("RELEASE_ALIASES", "")
    aliases_raw = aliases_env if aliases_env.strip() else args.aliases
    alias_list = [a for a in aliases_raw.split() if a]

    token = os.environ.get("GITHUB_TOKEN")
    repo = os.environ.get("GITHUB_REPOSITORY")
    if not token or not repo:
        print("GITHUB_TOKEN and GITHUB_REPOSITORY must be set", file=sys.stderr)
        sys.exit(1)

    gh = GitHubClient(token, repo)

    tag_created = False
    release = None
    aliases_created = []

    try:
        run(["git", "config", "user.name", "github-actions[bot]"])
        run(["git", "config", "user.email", "github-actions[bot]@users.noreply.github.com"])

        previous_tag = get_previous_tag()
        print(f"Previous tag: {previous_tag or '(none found)'}")

        # 1. Create and push the git tag
        create_git_tag(args.tag, f"Release {args.tag}")
        tag_created = True

        # 2. Build release body from merged PRs since the previous tag
        body = build_release_body(gh, previous_tag, alias_list)
        print("Release body:\n" + body)

        # 3. Create the GitHub release from that tag
        release = gh.create_release(
            tag_name=args.tag,
            target_commitish=args.target,
            name=args.tag,
            body=body,
            draft=args.draft,
            prerelease=args.prerelease,
        )
        print(f"Created release: {release['html_url']}")

        # 4. Create alias tags (e.g. v1, v1.0) pointing at the same commit
        for alias in alias_list:
            create_alias_tag(alias, args.tag)
            aliases_created.append(alias)
            print(f"Created alias tag: {alias}")

        set_output("tag", args.tag)
        set_output("release_id", release["id"])
        set_output("release_url", release["html_url"])

    except Exception as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        print("Rolling back...", file=sys.stderr)

        if release is not None:
            try:
                gh.delete_release(release["id"])
                print(f"Deleted release {release['id']}", file=sys.stderr)
            except Exception as cleanup_exc:
                print(f"Failed to delete release: {cleanup_exc}", file=sys.stderr)

        if tag_created:
            delete_git_tag(args.tag)
            print(f"Deleted tag {args.tag}", file=sys.stderr)

        for alias in aliases_created:
            delete_git_tag(alias)
            print(f"Deleted alias tag {alias}", file=sys.stderr)

        sys.exit(1)


if __name__ == "__main__":
    main()
