import tempfile
import unittest
from pathlib import Path

from ENT_Module.env_setup import build_install_hints, generate_external_env_setup


class EnvSetupTests(unittest.TestCase):
    def test_build_install_hints(self):
        rows = build_install_hints()
        names = {row["project"] for row in rows}
        self.assertIn("MONAI Label", names)
        self.assertIn("TotalSegmentator", names)
        self.assertIn("nnU-Net", names)

    def test_generate_external_env_setup(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            result = generate_external_env_setup(temp_dir, env_name="test_env")
            self.assertTrue(Path(result["files"]["install_python"]).exists())
            self.assertTrue(Path(result["files"]["install_stack"]).exists())
            self.assertTrue(Path(result["files"]["readme"]).exists())
            self.assertTrue(Path(result["files"]["bootstrap_all"]).exists())


if __name__ == "__main__":
    unittest.main()
