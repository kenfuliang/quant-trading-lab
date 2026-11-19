import unittest

A, B = "a" * 40, "b" * 40

from research.evaluation import engine_identity
from research.evaluation.engine_identity import ENGINE_FILES, engine_files_changed


class EngineIdentityTests(unittest.TestCase):
    def test_engine_files_changed_with_fake_git(self):
        calls = []

        def git(args):
            calls.append(args)
            return 0, "research/evaluation/native_engine.py\n"

        self.assertEqual(engine_files_changed(git, A, B), ["research/evaluation/native_engine.py"])
        self.assertEqual(calls, [["diff", "--name-only", "--end-of-options", A, B, "--", *ENGINE_FILES]])
        self.assertEqual(engine_files_changed(lambda args: (0, ""), A, B), [])

    def test_only_full_lowercase_shas_are_accepted(self):
        def git(args):
            raise AssertionError("git must not run")

        for bad in ("HEAD", "main", "abc1234", "A" * 40, "a" * 39, "a" * 41, "--output=/tmp/x", "-p", "", None,
                    "a" * 40 + "\n", "HEAD~1"):
            for a, b in ((bad, B), (A, bad)):
                with self.subTest(a=a, b=b), self.assertRaisesRegex(ValueError, "40-hex|dirty"):
                    engine_files_changed(git, a, b)

    def test_unknown_commit_raises_naming_it(self):
        with self.assertRaisesRegex(ValueError, "d{40}"):
            engine_files_changed(lambda args: (128, "bad object"), A, "d" * 40)

    def test_dirty_commit_rejected_before_git(self):
        def git(args):
            raise AssertionError("git must not run")

        for a, b in ((A + "+dirty", B), (A, B + "+dirty")):
            with self.assertRaisesRegex(ValueError, "dirty commit is not a reproducible engine identity"):
                engine_files_changed(git, a, b)

    def test_engine_files_constant(self):
        self.assertEqual(len(ENGINE_FILES), 7)
        self.assertIn("research/evaluation/run_output.py", ENGINE_FILES)
        self.assertIn("requirements.lock.txt", ENGINE_FILES)
        self.assertTrue(callable(engine_identity.run_git))


if __name__ == "__main__":
    unittest.main()
