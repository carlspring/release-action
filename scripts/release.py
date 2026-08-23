#!/usr/bin/env python3
"""
release.py — Create a git tag and a GitHub release built from the commits
since the previous tag. If any step after tag creation fails, everything
that was already created (tag, release) is rolled back.

Environment variables required:
    GITHUB_TOKEN        Token with permission to push tags and manage releases
    GITHUB_REPOSITORY   "owner/repo" (set automatically by GitHub Actions)

Optional:
    GITHUB_OUTPUT        Path to the file GitHub Actions collects outputs from

Usage:
    python release.py --tag v1.2.3 [--target main] [--draft] [--prerelease]
"""
import argparse
import os
import subprocess
import sys
import textwrap

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


def get_previous_tag():
    """Return the most recent tag reachable from HEAD, or None if there isn't one."""
    result = subprocess.run(
        ["git", "describe", "--tags", "--abbrev=0"],
        capture_output=True, text=True,
    )
    if result.returncode != 0:
        return None
    return result.stdout.strip()


def get_commits_since(previous_tag):
    """Return a changelog string of commits since previous_tag (or full history)."""
    rev_range = f"{previous_tag}..HEAD" if previous_tag else "HEAD"
    log = run(
        ["git", "log", rev_range, "--pretty=format:- %s (%h)", "--no-merges"],
        check=False,
    )
    return log if log else "No changes recorded."


def create_git_tag(tag_name, message):
    run(["git", "tag", "-a", tag_name, "-m", message])
    run(["git", "push", "origin", tag_name])


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
    args = parser.parse_args()

    token = os.environ.get("GITHUB_TOKEN")
    repo = os.environ.get("GITHUB_REPOSITORY")
    if not token or not repo:
        print("GITHUB_TOKEN and GITHUB_REPOSITORY must be set", file=sys.stderr)
        sys.exit(1)

    gh = GitHubClient(token, repo)

    tag_created = False
    release = None

    try:
        run(["git", "config", "user.name", "github-actions[bot]"])
        run(["git", "config", "user.email", "github-actions[bot]@users.noreply.github.com"])

        previous_tag = get_previous_tag()
        print(f"Previous tag: {previous_tag or '(none found)'}")

        changelog = get_commits_since(previous_tag)
        print("Changelog:\n" + changelog)

        # 1. Create and push the git tag
        create_git_tag(args.tag, f"Release {args.tag}")
        tag_created = True

        # 2. Create the GitHub release from that tag
        body = textwrap.dedent(f"""\
            ## Changes since {previous_tag or 'the beginning'}

            {changelog}
        """)
        release = gh.create_release(
            tag_name=args.tag,
            target_commitish=args.target,
            name=args.tag,
            body=body,
            draft=args.draft,
            prerelease=args.prerelease,
        )
        print(f"Created release: {release['html_url']}")

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

        sys.exit(1)


if __name__ == "__main__":
    main()
