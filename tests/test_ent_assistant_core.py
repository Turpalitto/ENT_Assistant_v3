import pathlib
import unittest

from ENT_Module.ent_assistant_core import (
    build_impression,
    build_quality_checks,
    build_report_path,
    get_preset,
    sanitize_filename,
    summarize_measurements,
)


class EntAssistantCoreTests(unittest.TestCase):
    def test_sanitize_filename(self):
        self.assertEqual(sanitize_filename("CT Head #12"), "CT_Head_12")

    def test_get_preset_falls_back(self):
        self.assertEqual(get_preset("missing").key, "ent_threshold")

    def test_build_report_path_has_json_suffix(self):
        path = build_report_path(pathlib.Path("reports"), "CT Head", "Head & neck AI preset")
        self.assertEqual(path.suffix, ".json")

    def test_summarize_measurements(self):
        summary = summarize_measurements(
            [
                {"segment": "Bone", "volume_ml": 12.5, "voxel_count": 1000},
                {"segment": "Air", "volume_ml": 8.2, "voxel_count": 700},
            ]
        )
        self.assertIn("Bone", summary)
        self.assertIn("8.20", summary)

    def test_build_impression(self):
        impression = build_impression(
            "Head & neck AI preset",
            [
                {"segment": "Bone", "volume_ml": 12.5},
                {"segment": "Air", "volume_ml": 8.2},
            ],
        )
        self.assertIn("Head & neck AI preset", impression)
        self.assertIn("Bone 12.50 mL", impression)

    def test_build_quality_checks_detects_small_and_asymmetry(self):
        preset = get_preset("head_neck_ai")
        findings = build_quality_checks(
            preset,
            [
                {"segment": "parotid_gland_left", "volume_ml": 9.0, "voxel_count": 100},
                {"segment": "parotid_gland_right", "volume_ml": 2.0, "voxel_count": 50},
                {"segment": "nasopharynx", "volume_ml": 0.05, "voxel_count": 1},
            ],
        )
        codes = {finding["code"] for finding in findings}
        self.assertIn("very_small_segment", codes)
        self.assertIn("left_right_asymmetry", codes)


if __name__ == "__main__":
    unittest.main()
