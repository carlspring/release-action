import os
import subprocess
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "scripts"))

import next_version  # noqa: E402


class BumpTest(unittest.TestCase):

    def test_increments_patch(self):
        self.assertEqual(next_version.bump("1.2.3"), "1.2.4")

    def test_keeps_v_prefix(self):
        self.assertEqual(next_version.bump("v1.2.3"), "v1.2.4")

    def test_increments_pre_release_number(self):
        self.assertEqual(next_version.bump("1.2.3-alpha-1"), "1.2.3-alpha-2")
        self.assertEqual(next_version.bump("1.2.3-beta-1"), "1.2.3-beta-2")
        self.assertEqual(next_version.bump("1.2.3-milestone-1"), "1.2.3-milestone-2")
        self.assertEqual(next_version.bump("1.2.3-rc-1"), "1.2.3-rc-2")
        self.assertEqual(next_version.bump("v2.0.0-milestone-9"), "v2.0.0-milestone-10")

    def test_rejects_unconventional_suffix(self):
        for tag in ("1.2.3-beta", "1.2.3-rc1", "1.2.3-rc.1", "1.2.3-foo-7", "1.2.3-RC-1",
                    "1.2.3-dev-1"):
            with self.subTest(tag=tag):
                with self.assertRaisesRegex(ValueError, f"{tag} doesn't follow"):
                    next_version.bump(tag)

    def test_rejects_non_version(self):
        with self.assertRaises(ValueError):
            next_version.bump("v1")


class NextVersionTest(unittest.TestCase):

    def test_no_tags_gives_initial_version(self):
        self.assertEqual(next_version.next_version([]), "1.0.0")

    def test_only_non_version_tags_gives_initial_version(self):
        self.assertEqual(next_version.next_version(["v1", "latest"]), "1.0.0")

    def test_ignores_alias_tags(self):
        self.assertEqual(next_version.next_version(["v1", "v1.0", "v1.0.3"]), "v1.0.4")

    def test_picks_highest_version_numerically(self):
        self.assertEqual(next_version.next_version(["1.9.0", "1.10.0", "1.2.0"]), "1.10.1")

    def test_mixed_prefixes_compare_by_number_and_keep_the_latest_style(self):
        self.assertEqual(next_version.next_version(["1.1.0", "v1.2.0"]), "v1.2.1")
        self.assertEqual(next_version.next_version(["v1.1.0", "1.2.0"]), "1.2.1")

    def test_final_release_beats_its_pre_releases(self):
        self.assertEqual(next_version.next_version(["1.0.0-rc-2", "1.0.0"]), "1.0.1")

    def test_pre_release_types_rank_alpha_beta_milestone_rc(self):
        tags = ["1.0.0-rc-1", "1.0.0-alpha-5", "1.0.0-milestone-2", "1.0.0-beta-3"]
        self.assertEqual(next_version.next_version(tags), "1.0.0-rc-2")
        self.assertEqual(next_version.next_version(tags[1:]), "1.0.0-milestone-3")

    def test_unconventional_latest_tag_fails(self):
        with self.assertRaises(ValueError):
            next_version.next_version(["1.0.0", "1.0.1-beta"])

    def test_unconventional_tag_is_not_skipped_in_favour_of_pre_releases(self):
        with self.assertRaises(ValueError):
            next_version.next_version(["1.0.1-rc-1", "1.0.1-rc1"])

    def test_unconventional_tag_of_older_version_is_harmless(self):
        self.assertEqual(next_version.next_version(["1.0.0-beta", "1.0.0", "1.0.1"]), "1.0.2")

    def test_newer_pre_release_is_bumped(self):
        self.assertEqual(
            next_version.next_version(["1.0.0", "1.0.1-rc-1", "1.0.1-rc-2"]), "1.0.1-rc-3",
        )


class GetTagsTest(unittest.TestCase):

    def test_returns_only_tags_reachable_from_head(self):
        with tempfile.TemporaryDirectory() as repo:
            def git(*args):
                subprocess.run(["git", *args], cwd=repo, check=True, capture_output=True)

            git("init", "-q", "-b", "main")
            git("config", "user.name", "Test")
            git("config", "user.email", "test@example.com")
            git("config", "commit.gpgsign", "false")
            git("config", "tag.gpgsign", "false")
            git("commit", "-q", "--allow-empty", "-m", "initial")
            git("tag", "1.0.0")
            git("checkout", "-q", "-b", "other")
            git("commit", "-q", "--allow-empty", "-m", "elsewhere")
            git("tag", "2.0.0")
            git("checkout", "-q", "main")

            cwd = os.getcwd()
            os.chdir(repo)
            try:
                self.assertEqual(next_version.get_tags(), ["1.0.0"])
            finally:
                os.chdir(cwd)


if __name__ == "__main__":
    unittest.main()
