import importlib.util
from pathlib import Path
import tempfile
import unittest


spec = importlib.util.spec_from_file_location("resolver", Path(__file__).with_name("resolve-dev-url.py"))
resolver = importlib.util.module_from_spec(spec)
spec.loader.exec_module(resolver)


class TargetTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)

    def test_checkout_env_beats_other_env_file(self):
        (self.root / ".env").write_text('PORT="4371" # local\n')
        (self.root / ".env.local").write_text("PORT=3000\n")
        self.assertEqual("http://localhost:4371", resolver.resolve(self.root))

    def test_env_local_works_when_no_env_target(self):
        (self.root / ".env").write_text("UNRELATED=present\n")
        (self.root / ".env.local").write_text("export PORT='4381'\n")
        self.assertEqual("http://localhost:4381", resolver.resolve(self.root))

    def test_project_helper_is_authoritative(self):
        (self.root / "bin").mkdir()
        helper = self.root / "bin/dev-info"
        helper.write_text("#!/bin/sh\nprintf 'PORT=4400\\nAPP_URL=http://localhost:4400\\n'\n")
        helper.chmod(0o755)
        (self.root / ".env").write_text("PORT=3000\n")
        self.assertEqual("http://localhost:4400", resolver.resolve(self.root))
        helper.write_text("#!/bin/sh\nexit 1\n")
        with self.assertRaises(ValueError):
            resolver.resolve(self.root)

    def test_missing_target_does_not_guess(self):
        with self.assertRaises(ValueError):
            resolver.resolve(self.root)

    def test_dynamic_env_value_is_not_executed(self):
        (self.root / ".env").write_text('PORT="$(touch unexpected)"\n')
        with self.assertRaises(ValueError):
            resolver.resolve(self.root)
        self.assertFalse((self.root / "unexpected").exists())

    def test_remote_or_invalid_target_is_rejected(self):
        for value in ["https://production.example.com", "http://user:pass@localhost:3000", "http://localhost:99999"]:
            with self.subTest(value=value), self.assertRaises(ValueError):
                resolver.local_url(value)


if __name__ == "__main__":
    unittest.main()
