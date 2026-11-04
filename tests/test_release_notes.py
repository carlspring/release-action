import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "scripts"))

from release_notes import (  # noqa: E402
    commit_entries,
    parse_message,
    pr_entries,
    render_sections,
)

REPO_URL = "https://github.com/acme/widget"


class ParseMessageTest(unittest.TestCase):

    def test_type_and_subject(self):
        parsed = parse_message("feat: add a widget")
        self.assertEqual(parsed["type"], "feat")
        self.assertIsNone(parsed["scope"])
        self.assertEqual(parsed["subject"], "add a widget")
        self.assertFalse(parsed["breaking"])

    def test_scope(self):
        parsed = parse_message("fix(tracing): close the exporter")
        self.assertEqual(parsed["type"], "fix")
        self.assertEqual(parsed["scope"], "tracing")
        self.assertEqual(parsed["subject"], "close the exporter")

    def test_type_is_case_insensitive(self):
        self.assertEqual(parse_message("Docs: fix typo")["type"], "docs")

    def test_only_first_line_is_the_subject(self):
        parsed = parse_message("refactor: tidy up\n\nLonger explanation here.\n")
        self.assertEqual(parsed["subject"], "tidy up")

    def test_bang_marks_breaking(self):
        parsed = parse_message("feat(api)!: drop v1 endpoints")
        self.assertTrue(parsed["breaking"])
        self.assertEqual(parsed["type"], "feat")
        self.assertEqual(parsed["scope"], "api")

    def test_breaking_change_footer_marks_breaking(self):
        parsed = parse_message("feat: new config\n\nBREAKING CHANGE: old keys removed")
        self.assertTrue(parsed["breaking"])

    def test_unprefixed_message_has_no_type(self):
        parsed = parse_message("Update README.md")
        self.assertIsNone(parsed["type"])
        self.assertEqual(parsed["subject"], "Update README.md")

    def test_unknown_type_keeps_full_subject(self):
        parsed = parse_message("wip: half done")
        self.assertIsNone(parsed["type"])
        self.assertEqual(parsed["subject"], "wip: half done")

    def test_git_revert_is_a_revert(self):
        parsed = parse_message('Revert "feat: add a widget"')
        self.assertEqual(parsed["type"], "revert")
        self.assertEqual(parsed["subject"], 'Revert "feat: add a widget"')


class RenderSectionsTest(unittest.TestCase):

    def entry(self, message, ref="(ref)"):
        return {**parse_message(message), "ref": ref}

    def test_groups_entries_under_section_headings(self):
        body = render_sections([
            self.entry("fix: a bug", "(1)"),
            self.entry("feat: a feature", "(2)"),
        ])
        self.assertEqual(
            body,
            "### Features\n\n- a feature (2)\n\n"
            "### Bug Fixes\n\n- a bug (1)",
        )

    def test_sections_follow_fixed_order(self):
        messages = [
            "chore: c", "revert: r", "style: s", "ci: ci", "build: b", "test: t",
            "docs: d", "refactor: rf", "perf: p", "fix: f", "feat: ft", "random",
        ]
        body = render_sections([self.entry(m) for m in messages])
        headings = [line for line in body.splitlines() if line.startswith("### ")]
        self.assertEqual(headings, [
            "### Features", "### Bug Fixes", "### Performance",
            "### Code Refactoring", "### Documentation", "### Tests",
            "### Build", "### CI", "### Styles", "### Reverts",
            "### Chores", "### Other Changes",
        ])

    def test_empty_sections_are_omitted(self):
        body = render_sections([self.entry("docs: d")])
        self.assertNotIn("### Features", body)
        self.assertIn("### Documentation", body)

    def test_scope_is_rendered_in_bold(self):
        body = render_sections([self.entry("fix(tracing): close it", "(x)")])
        self.assertIn("- **tracing**: close it (x)", body)

    def test_breaking_changes_come_first_and_only_once(self):
        body = render_sections([
            self.entry("fix: small"),
            self.entry("feat!: big"),
        ])
        self.assertTrue(body.startswith("### ⚠ Breaking Changes\n\n- big (ref)"))
        self.assertEqual(body.count("big"), 1)

    def test_entries_keep_their_input_order_within_a_section(self):
        body = render_sections([
            self.entry("fix: second", "(2)"),
            self.entry("fix: first", "(1)"),
        ])
        self.assertIn("- second (2)\n- first (1)", body)

    def test_no_entries_renders_empty_string(self):
        self.assertEqual(render_sections([]), "")


class CommitEntriesTest(unittest.TestCase):

    def test_links_short_hash_to_commit(self):
        sha = "8148b1d0e6e30e5f41d373b0d2271c76d28b2d02"
        [entry] = commit_entries([{"sha": sha, "message": "feat(x): y"}], REPO_URL)
        self.assertEqual(entry["type"], "feat")
        self.assertEqual(entry["scope"], "x")
        self.assertEqual(entry["ref"], f"([8148b1d0]({REPO_URL}/commit/{sha}))")


class PrEntriesTest(unittest.TestCase):

    def pr(self, **overrides):
        pr = {
            "number": 42,
            "title": "fix(api): handle nulls",
            "html_url": f"{REPO_URL}/pull/42",
            "user": "carlspring",
            "assignees": [],
        }
        pr.update(overrides)
        return pr

    def test_categorises_by_title_and_links_pr(self):
        [entry] = pr_entries([self.pr()])
        self.assertEqual(entry["type"], "fix")
        self.assertEqual(entry["scope"], "api")
        self.assertEqual(entry["subject"], "handle nulls")
        self.assertEqual(entry["ref"], f"([#42]({REPO_URL}/pull/42)) (@carlspring)")

    def test_bot_suffix_is_stripped(self):
        [entry] = pr_entries([self.pr(user="dependabot[bot]")])
        self.assertTrue(entry["ref"].endswith("(@dependabot)"))

    def test_copilot_lists_assignees_first(self):
        [entry] = pr_entries([self.pr(user="Copilot", assignees=["carlspring", "Copilot"])])
        self.assertTrue(entry["ref"].endswith("(@carlspring, @Copilot)"))


if __name__ == "__main__":
    unittest.main()
