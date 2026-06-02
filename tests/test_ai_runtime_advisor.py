import unittest

from ENT_Module.ai_runtime_advisor import (
    build_framework_fit_report,
    build_nnunet_dataset_stub,
    build_workspace_recommendation,
)


class AiRuntimeAdvisorTests(unittest.TestCase):
    def test_build_workspace_recommendation_prefers_gpu_backends(self):
        rows = build_workspace_recommendation(
            gpu={"available": True, "memoryMb": 12227, "name": "RTX", "cudaVersion": "13.1"},
            tools={"python": "C:\\python.exe", "TotalSegmentator": "totalseg", "monailabel": "monailabel"},
            preferred_ct_backend="TotalSegmentator",
            interactive_backend="MONAI Label",
        )
        joined = " ".join(rows)
        self.assertIn("TotalSegmentator", joined)
        self.assertIn("MONAI Label", joined)
        self.assertIn("GPU", joined)

    def test_build_workspace_recommendation_warns_without_python(self):
        rows = build_workspace_recommendation(
            gpu={"available": False, "memoryMb": None, "name": None, "cudaVersion": None},
            tools={"python": None},
            preferred_ct_backend="threshold",
            interactive_backend="SegmentEditorExtraEffects / manual refinement",
        )
        self.assertTrue(any("Python" in row for row in rows))

    def test_build_nnunet_dataset_stub(self):
        payload = build_nnunet_dataset_stub("Case_001", "CT", has_labels=True)
        self.assertEqual(payload["channel_names"]["0"], "CT")
        self.assertEqual(payload["numTraining"], 1)
        self.assertEqual(payload["file_ending"], ".nii.gz")

    def test_build_framework_fit_report(self):
        rows = build_framework_fit_report(
            gpu={"available": True, "memoryMb": 12227, "name": "RTX", "cudaVersion": "13.1"},
            tools={"python": "C:\\python.exe", "TotalSegmentator": "totalseg", "monailabel": None, "nnUNetv2_predict": None},
        )
        names = {row["project"]: row for row in rows}
        self.assertEqual(names["3D Slicer"]["status"], "ready")
        self.assertEqual(names["TotalSegmentator"]["status"], "ready")
        self.assertIn(names["VISTA3D"]["status"], {"setup_needed", "ready"})


if __name__ == "__main__":
    unittest.main()
