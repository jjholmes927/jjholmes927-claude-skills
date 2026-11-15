from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest


class SetupTests(unittest.TestCase):
    def test_setup_is_repeatable_and_preserves_existing_hooks(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "scripts").mkdir()
            setup = root / "scripts/setup-dev.sh"
            shutil.copyfile(Path(__file__).with_name("setup-dev.sh"), setup)
            subprocess.run(["git", "init", "-q", str(root)], check=True)
            for _ in range(2):
                self.assertEqual(0, subprocess.run(["bash", str(setup)], capture_output=True).returncode)
            self.assertEqual(".githooks", subprocess.check_output(["git", "-C", str(root), "config", "--local", "core.hooksPath"], text=True).strip())
            subprocess.run(["git", "-C", str(root), "config", "--local", "core.hooksPath", "custom-hooks"], check=True)
            self.assertEqual(1, subprocess.run(["bash", str(setup)], capture_output=True).returncode)
            self.assertEqual("custom-hooks", subprocess.check_output(["git", "-C", str(root), "config", "--local", "core.hooksPath"], text=True).strip())
            subprocess.run(["git", "-C", str(root), "config", "--local", "--unset", "core.hooksPath"], check=True)
            (root / ".git/hooks/pre-push").write_text("existing hook")
            self.assertEqual(1, subprocess.run(["bash", str(setup)], capture_output=True).returncode)
            self.assertEqual("existing hook", (root / ".git/hooks/pre-push").read_text())


if __name__ == "__main__":
    unittest.main()
