"""Version comparison for the plugin's update check. Run: npm test."""
import unittest

from support import main


class VersionKeyTest(unittest.TestCase):
    def test_order(self):
        order = ["v.0.8.3", "0.9.3", "0.10.0-beta.1", "0.10.0-beta.2", "v0.10.0", "0.10.1"]
        keys = [main.version_key(v) for v in order]
        self.assertEqual(keys, sorted(keys))
        self.assertEqual(len(set(keys)), len(keys))

    def test_spellings_of_the_same_release_are_equal(self):
        self.assertEqual(main.version_key("0.9.3"), main.version_key("v0.9.3"))
        self.assertEqual(main.version_key("0.9"), main.version_key("0.9.0"))

    def test_beta_is_offered_its_release_but_not_the_reverse(self):
        self.assertGreater(main.version_key("0.10.0"), main.version_key("0.10.0-beta.1"))
        self.assertLess(main.version_key("0.9.3"), main.version_key("0.10.0-beta.1"))
