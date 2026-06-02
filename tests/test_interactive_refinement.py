import unittest

from ENT_Module.interactive_refinement import build_prompt_templates, build_refinement_checklist


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


if __name__ == "__main__":
    unittest.main()
