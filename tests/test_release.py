import os
import subprocess
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "scripts"))

import release  # noqa: E402

REPO_URL = "https://github.com/acme/widget"


def git(*args, cwd):
    return subprocess.run(
        ["git", *args], cwd=cwd, check=True, capture_output=True, text=True,
    ).stdout.strip()


class FakeGitHub:
    def __init__(self, prs):
        self.prs = prs
        self.requested_shas = None

    def get_prs_for_commits(self, commit_shas):
        self.requested_shas = commit_shas
        return self.prs


class BuildReleaseBodyTest(unittest.TestCase):

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        repo = self.tmp.name
        git("init", "-q", "-b", "main", cwd=repo)
        git("config", "user.name", "Test", cwd=repo)
        git("config", "user.email", "test@example.com", cwd=repo)
        git("config", "commit.gpgsign", "false", cwd=repo)
        git("config", "tag.gpgsign", "false", cwd=repo)
        git("commit", "-q", "--allow-empty", "-m", "chore: initial", cwd=repo)
        git("tag", "v1.0.0", cwd=repo)
        git("commit", "-q", "--allow-empty", "-m", "fix(core): repair it", cwd=repo)
        self.fix_sha = git("rev-parse", "HEAD", cwd=repo)
        git("commit", "-q", "--allow-empty", "-m", "feat: shiny", cwd=repo)
        self.feat_sha = git("rev-parse", "HEAD", cwd=repo)

        cwd = os.getcwd()
        os.chdir(repo)
        self.addCleanup(os.chdir, cwd)

    def test_commit_mode_groups_commits_since_previous_tag(self):
        body = release.build_release_body(
            FakeGitHub([]), "v1.0.0", [], group_by="commit", repo_url=REPO_URL,
        )
        self.assertEqual(
            body,
            "## Changes since v1.0.0\n\n"
            "### Features\n\n"
            f"- shiny ([{self.feat_sha[:8]}]({REPO_URL}/commit/{self.feat_sha}))\n\n"
            "### Bug Fixes\n\n"
            f"- **core**: repair it ([{self.fix_sha[:8]}]({REPO_URL}/commit/{self.fix_sha}))",
        )

    def test_commit_mode_does_not_query_pull_requests(self):
        gh = FakeGitHub([])
        release.build_release_body(gh, "v1.0.0", [], group_by="commit", repo_url=REPO_URL)
        self.assertIsNone(gh.requested_shas)

    def test_pull_request_mode_groups_prs_by_title(self):
        gh = FakeGitHub([{
            "number": 7,
            "title": "docs: explain things",
            "html_url": f"{REPO_URL}/pull/7",
            "user": "carlspring",
            "assignees": [],
        }])
        body = release.build_release_body(
            gh, "v1.0.0", [], group_by="pull-request", repo_url=REPO_URL,
        )
        self.assertEqual(gh.requested_shas, [self.feat_sha, self.fix_sha])
        self.assertEqual(
            body,
            "## Changes since v1.0.0\n\n"
            "### Documentation\n\n"
            f"- explain things ([#7]({REPO_URL}/pull/7)) (@carlspring)",
        )

    def test_pull_request_mode_falls_back_to_commits_when_no_prs(self):
        body = release.build_release_body(
            FakeGitHub([]), "v1.0.0", [], group_by="pull-request", repo_url=REPO_URL,
        )
        self.assertIn("### Features\n\n- shiny", body)
        self.assertIn("### Bug Fixes\n\n- **core**: repair it", body)

    def test_without_previous_tag_uses_whole_history(self):
        body = release.build_release_body(
            FakeGitHub([]), None, [], group_by="commit", repo_url=REPO_URL,
        )
        self.assertTrue(body.startswith("## Changes since the beginning\n\n"))
        self.assertIn("### Chores\n\n- initial", body)

    def test_no_commits_reports_no_changes(self):
        git("tag", "v1.1.0", cwd=self.tmp.name)
        body = release.build_release_body(
            FakeGitHub([]), "v1.1.0", [], group_by="commit", repo_url=REPO_URL,
        )
        self.assertEqual(body, "## Changes since v1.1.0\n\nNo changes recorded.")

    def test_aliases_are_mentioned(self):
        body = release.build_release_body(
            FakeGitHub([]), "v1.0.0", ["v1"], group_by="commit", repo_url=REPO_URL,
        )
        self.assertTrue(body.endswith("\n\nThis release is marked as the current `v1`."))


if __name__ == "__main__":
    unittest.main()
