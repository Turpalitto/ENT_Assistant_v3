import pathlib
import unittest

from ENT_Module.ent_assistant_core import build_impression, build_report_path, get_preset, sanitize_filename, summarize_measurements


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


if __name__ == "__main__":
    unittest.main()
