import unittest

from research.evaluation import engine_identity
from research.evaluation.engine_identity import ENGINE_FILES, engine_files_changed


class EngineIdentityTests(unittest.TestCase):
    def test_engine_files_changed_with_fake_git(self):
        calls = []

        def git(args):
            calls.append(args)
            return 0, "research/evaluation/native_engine.py\n"

        self.assertEqual(engine_files_changed(git, "abc", "def"), ["research/evaluation/native_engine.py"])
        self.assertEqual(calls, [["diff", "--name-only", "abc", "def", "--", *ENGINE_FILES]])
        self.assertEqual(engine_files_changed(lambda args: (0, ""), "abc", "def"), [])

    def test_unknown_commit_raises_naming_it(self):
        with self.assertRaisesRegex(ValueError, "deadbeef"):
            engine_files_changed(lambda args: (128, "bad object"), "abc", "deadbeef")

    def test_dirty_commit_rejected_before_git(self):
        def git(args):
            raise AssertionError("git must not run")

        for a, b in (("abc+dirty", "def"), ("abc", "def+dirty")):
            with self.assertRaisesRegex(ValueError, "dirty commit is not a reproducible engine identity"):
                engine_files_changed(git, a, b)

    def test_engine_files_constant(self):
        self.assertEqual(len(ENGINE_FILES), 5)
        self.assertTrue(callable(engine_identity.run_git))


if __name__ == "__main__":
    unittest.main()
