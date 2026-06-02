import unittest

from ENT_Module.mri_reporting import build_ent_mri_report, build_ent_mri_suitability, detect_mri_sequences


class MriReportingTests(unittest.TestCase):
    def test_detect_mri_sequences(self):
        tags = detect_mri_sequences("t2_ci3d_tra ep2d_diff_3scan_trace t1_vibe_fs_tra")
        self.assertIn("high_res_t2", tags)
        self.assertIn("dwi", tags)
        self.assertIn("postcontrast_t1", tags)

    def test_build_ent_mri_suitability(self):
        suitability = build_ent_mri_suitability(
            {"dicomModality": "MR", "spacingMm": [0.5, 0.5, 0.8]},
            ["high_res_t2", "dwi"],
        )
        self.assertEqual(suitability["level"], "good")

    def test_build_ent_mri_report(self):
        report = build_ent_mri_report(
            {"dicomModality": "MR", "spacingMm": [0.5, 0.5, 0.8], "dicomSeriesDescription": "t2_ci3d_tra ep2d_diff_3scan_trace"},
            [
                {"segment": "MRI_Foreground", "volume_ml": 1200.0},
                {"segment": "MRI_LowSignal", "volume_ml": 180.0},
            ],
        )
        self.assertIn("MRI ENT support suitability", report["impression"])
        self.assertTrue(report["findingRows"])
        self.assertIn("specialist", report["patientSummary"].lower())


if __name__ == "__main__":
    unittest.main()
