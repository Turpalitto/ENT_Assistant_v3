import unittest

from ENT_Module.interactive_refinement import (
    build_monailabel_prompt_payload,
    build_prompt_templates,
    build_refinement_checklist,
    build_vista3d_prompt_payload,
)


class InteractiveRefinementTests(unittest.TestCase):
    def test_build_refinement_checklist_uses_qc_and_findings(self):
        rows = build_refinement_checklist(
            {
                "qualityChecks": [{"code": "missing_mask", "level": "warning", "message": "Mask is missing."}],
                "sinusReport": {
                    "findingRows": [
                        {"structure": "sinus_maxillary_right", "status": "flag", "details": "Possible opacification."}
                    ]
                },
            }
        )
        self.assertTrue(any(row["title"] == "missing_mask" for row in rows))
        self.assertTrue(any(row["title"] == "sinus_maxillary_right" for row in rows))

    def test_build_prompt_templates(self):
        payload = build_prompt_templates(
            {
                "volumeName": "Case1",
                "preset": "CT PNS",
                "mriReport": {
                    "findingRows": [
                        {"structure": "internal_auditory_canal", "details": "Review boundary."},
                    ]
                },
            }
        )
        self.assertEqual(payload["case"], "Case1")
        self.assertTrue(payload["targets"])
        self.assertEqual(payload["targets"][0]["name"], "internal_auditory_canal")

    def test_build_monai_and_vista_payloads(self):
        result = {
            "volumeName": "Case1",
            "preset": "CT PNS",
            "measurements": [{"segment": "sinus_maxillary_left", "sourceSegment": "sinus_maxillary", "volume_ml": 12.0}],
            "sinusReport": {
                "findingRows": [
                    {"structure": "sinus_maxillary_left", "details": "Refine this region."},
                ]
            },
        }
        monai = build_monailabel_prompt_payload(result)
        vista = build_vista3d_prompt_payload(result)
        self.assertEqual(monai["prompts"][0]["label"], "sinus_maxillary_left")
        self.assertIn("sinus_maxillary_left", monai["prompts"][0]["related_segments"])
        self.assertEqual(vista["targets"][0]["name"], "sinus_maxillary_left")


if __name__ == "__main__":
    unittest.main()
