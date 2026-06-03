import tempfile
import unittest
from pathlib import Path

from ENT_Module.roundtrip_import import detect_roundtrip_candidates


class RoundTripImportTests(unittest.TestCase):
    def test_detect_roundtrip_candidates(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            workspace = Path(temp_dir)
            (workspace / "nnunet_prediction").mkdir()
            (workspace / "nnunet_prediction" / "case.nii.gz").write_text("x", encoding="utf-8")
            (workspace / "totalseg_output").mkdir()
            (workspace / "totalseg_output" / "mask.nii.gz").write_text("x", encoding="utf-8")
            (workspace / "labelmap.nii.gz").write_text("x", encoding="utf-8")

            result = detect_roundtrip_candidates(str(workspace))
            self.assertTrue(result["nnunetPrediction"].endswith("case.nii.gz"))
            self.assertTrue(result["totalsegmentatorOutputDir"].endswith("totalseg_output"))
            self.assertTrue(result["genericLabelmap"].endswith("labelmap.nii.gz"))


if __name__ == "__main__":
    unittest.main()
