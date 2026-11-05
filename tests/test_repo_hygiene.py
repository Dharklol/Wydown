"""Self-tests for the repository hygiene bootstrap gate."""

import unittest

from scripts.check_repo_hygiene import inspect_file


class HygieneChecks(unittest.TestCase):
    def test_valid_markdown(self):
        self.assertEqual(inspect_file("docs/README.md", b"# Heading\n"), [])

    def test_trailing_whitespace_fails(self):
        errors = inspect_file("README.md", b"bad  \n")
        self.assertTrue(any("trailing whitespace" in error for error in errors))

    def test_missing_newline_fails(self):
        errors = inspect_file("docs/example.toml", b"mode = 'paper'")
        self.assertTrue(any("final newline" in error for error in errors))

    def test_unpinned_action_fails(self):
        errors = inspect_file(
            ".github/workflows/ci.yml",
            b"steps:\n  - uses: actions/checkout@v4\n",
        )
        self.assertTrue(any("pinned to SHA" in error for error in errors))

    def test_pinned_action_passes(self):
        errors = inspect_file(
            ".github/workflows/ci.yml",
            b"steps:\n  - uses: actions/checkout@11bd71901bbe5b1630ceea73d27597364c9af683\n",
        )
        self.assertEqual(errors, [])

    def test_private_key_fails(self):
        errors = inspect_file(
            "notes.txt",
            b"-----BEGIN " + b"RSA PRIVATE KEY-----\nMII...\n",
        )
        self.assertTrue(any("private key" in error for error in errors))

    def test_database_file_is_blocked(self):
        errors = inspect_file("storage/runtime.sqlite", b"SQLite format 3\x00")
        self.assertTrue(any("database artifact" in error for error in errors))

    def test_secret_env_is_blocked(self):
        errors = inspect_file(".env", b"TOKEN=fake\n")
        self.assertTrue(any("environment" in error for error in errors))


if __name__ == "__main__":
    unittest.main()
