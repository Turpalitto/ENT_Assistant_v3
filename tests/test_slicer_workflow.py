import shutil
import tempfile
import unittest
from pathlib import Path

import numpy as np
import slicer

from ENT_Module import slicer_workflow


SAMPLE_VOLUME = Path(r"C:\entv1\ENT_Module\10 t2_ci3d_tra.nrrd")


class SlicerWorkflowTests(unittest.TestCase):
    def setUp(self):
        if not hasattr(slicer, "mrmlScene"):
            self.skipTest("Scene-based workflow tests require a full Slicer application session.")
        slicer.mrmlScene.Clear(0)
        self.tempdir = Path(tempfile.mkdtemp(prefix="ent_ai_workspace_"))
        success, volume_node = slicer.util.loadVolume(str(SAMPLE_VOLUME), returnNode=True)
        self.assertTrue(success)
        self.volume_node = volume_node
        self.segmentation_node = self._create_test_segmentation(volume_node)
        self.result = {
            "preset": "mri_ent_support",
            "volumeName": volume_node.GetName(),
            "volumeNodeId": volume_node.GetID(),
            "segmentationNodeId": self.segmentation_node.GetID(),
            "studyInfo": {"dicomModality": "MR"},
            "measurements": [{"segment": "foreground_region", "sourceSegment": "foreground_region"}],
            "mriReport": {
                "findingRows": [
                    {
                        "category": "MRI",
                        "structure": "foreground_region",
                        "status": "review",
                        "details": "Synthetic runtime verification segment.",
                    }
                ]
            },
        }

    def tearDown(self):
        slicer.mrmlScene.Clear(0)
        shutil.rmtree(self.tempdir, ignore_errors=True)

    def test_export_workspace_and_launcher_dry_runs(self):
        workspace = slicer_workflow.export_ai_workspace(self.result, str(self.tempdir))
        self.assertTrue(Path(workspace["imagePath"]).exists())
        self.assertTrue(Path(workspace["segmentationPath"]).exists())
        self.assertTrue(Path(workspace["labelmapPath"]).exists())
        self.assertTrue(Path(workspace["workspaceMeta"]["manifestPath"]).exists())
        self.assertTrue(Path(workspace["envSetup"]["files"]["bootstrap_all"]).exists())

        launch_result = slicer_workflow.launch_workspace_command(
            str(self.tempdir),
            "run_nnunet_inference_example",
            dry_run=True,
        )
        self.assertEqual(launch_result["launchMode"], "dry_run")
        self.assertTrue(Path(launch_result["logPath"]).exists())

        bootstrap_result = slicer_workflow.bootstrap_external_env(str(self.tempdir), dry_run=True)
        self.assertEqual(bootstrap_result["launchMode"], "dry_run")
        self.assertTrue(Path(bootstrap_result["logPath"]).exists())

    def test_roundtrip_import_workspace(self):
        slicer_workflow.export_ai_workspace(self.result, str(self.tempdir))
        imported = slicer_workflow.import_roundtrip_workspace(str(self.tempdir), self.volume_node)
        self.assertIn(imported["source"], {"labelmap", "nnUNet", "TotalSegmentator"})
        imported_node = slicer.mrmlScene.GetNodeByID(imported["segmentationNodeId"])
        self.assertIsNotNone(imported_node)
        self.assertGreater(imported_node.GetSegmentation().GetNumberOfSegments(), 0)

    def _create_test_segmentation(self, volume_node):
        array = slicer.util.arrayFromVolume(volume_node)
        threshold = float(np.percentile(array, 80))
        mask = (array >= threshold).astype(np.uint8)

        label_node = slicer.mrmlScene.AddNewNodeByClass("vtkMRMLLabelMapVolumeNode", "ENT_Test_Labelmap")
        label_node.CopyOrientation(volume_node)
        label_node.SetOrigin(volume_node.GetOrigin())
        label_node.SetSpacing(volume_node.GetSpacing())
        slicer.util.updateVolumeFromArray(label_node, mask)
        label_node.CreateDefaultDisplayNodes()

        segmentation_node = slicer.mrmlScene.AddNewNodeByClass("vtkMRMLSegmentationNode", "ENT_Test_Segmentation")
        segmentation_node.CreateDefaultDisplayNodes()
        segmentation_node.SetReferenceImageGeometryParameterFromVolumeNode(volume_node)
        slicer.modules.segmentations.logic().ImportLabelmapToSegmentationNode(label_node, segmentation_node)
        slicer.mrmlScene.RemoveNode(label_node)
        return segmentation_node


if __name__ == "__main__":
    unittest.main()
