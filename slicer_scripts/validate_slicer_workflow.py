import json
import shutil
import sys
import tempfile
from pathlib import Path

import numpy as np
import slicer

from ENT_Module import ai_runtime_advisor
from ENT_Module import interactive_refinement
from ENT_Module import slicer_workflow


REPO_ROOT = Path(r"C:\entv1")
SAMPLE_VOLUME = REPO_ROOT / "ENT_Module" / "10 t2_ci3d_tra.nrrd"
RESULT_PATH = REPO_ROOT / "artifacts" / "slicer_function_validation.json"


def main():
    RESULT_PATH.parent.mkdir(parents=True, exist_ok=True)
    slicer.mrmlScene.Clear(0)

    verification = {
        "sampleVolume": str(SAMPLE_VOLUME),
        "checks": {},
        "errors": [],
    }

    try:
        success, volume_node = slicer.util.loadVolume(str(SAMPLE_VOLUME), returnNode=True)
        if not success:
            raise RuntimeError(f"Failed to load sample volume: {SAMPLE_VOLUME}")
        verification["checks"]["loadVolume"] = {"ok": True, "nodeName": volume_node.GetName()}

        segmentation_node = _create_test_segmentation(volume_node)
        verification["checks"]["createSegmentation"] = {
            "ok": True,
            "nodeName": segmentation_node.GetName(),
            "segmentCount": segmentation_node.GetSegmentation().GetNumberOfSegments(),
        }

        result = {
            "preset": "mri_ent_support",
            "volumeName": volume_node.GetName(),
            "volumeNodeId": volume_node.GetID(),
            "segmentationNodeId": segmentation_node.GetID(),
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

        workspace_dir = Path(tempfile.mkdtemp(prefix="ent_ai_workspace_"))
        try:
            _run_step(
                verification,
                "exportAiWorkspace",
                lambda: _build_export_check(slicer_workflow.export_ai_workspace(result, str(workspace_dir))),
            )
            _run_step(
                verification,
                "launchNnUNetDryRun",
                lambda: _build_launcher_check(
                    slicer_workflow.launch_workspace_command(
                        str(workspace_dir),
                        "run_nnunet_inference_example",
                        dry_run=True,
                    )
                ),
            )
            _run_step(
                verification,
                "bootstrapEnvDryRun",
                lambda: _build_launcher_check(slicer_workflow.bootstrap_external_env(str(workspace_dir), dry_run=True)),
            )
            _run_step(
                verification,
                "importRoundTripWorkspace",
                lambda: _build_roundtrip_check(slicer_workflow.import_roundtrip_workspace(str(workspace_dir), volume_node)),
            )
        finally:
            shutil.rmtree(workspace_dir, ignore_errors=True)

        _run_step(
            verification,
            "prepareInteractiveRefinement",
            lambda: _build_refinement_check(interactive_refinement.prepare_interactive_refinement(volume_node, segmentation_node, result)),
        )
        _run_step(
            verification,
            "aiRuntimeAdvisor",
            lambda: _build_advisor_check(ai_runtime_advisor.inspect_local_ai_runtimes()),
        )

        dicom_folder = REPO_ROOT / "data" / "mri_otitis_patient002"
        if dicom_folder.exists():
            _run_step(
                verification,
                "importDicomFolder",
                lambda: _build_dicom_check(slicer_workflow.import_dicom_folder(str(dicom_folder), load_patient=False)),
            )
        else:
            verification["checks"]["importDicomFolder"] = {"ok": False, "error": "Known DICOM test folder not found."}
    except Exception as error:
        verification["errors"].append(str(error))

    RESULT_PATH.write_text(json.dumps(verification, indent=2, ensure_ascii=False), encoding="utf-8")
    print(json.dumps(verification, indent=2, ensure_ascii=False))
    sys.stdout.flush()


def _create_test_segmentation(volume_node):
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


def _run_step(verification, name, callback):
    try:
        verification["checks"][name] = {"ok": True, **callback()}
    except Exception as error:
        verification["checks"][name] = {"ok": False, "error": str(error)}


def _build_export_check(workspace):
    return {
        "directory": workspace["directory"],
        "imageExists": Path(workspace["imagePath"]).exists(),
        "segmentationExists": Path(workspace["segmentationPath"]).exists() if workspace.get("segmentationPath") else False,
        "labelmapExists": Path(workspace["labelmapPath"]).exists() if workspace.get("labelmapPath") else False,
        "manifestExists": Path((workspace.get("workspaceMeta") or {}).get("manifestPath", "")).exists(),
    }


def _build_launcher_check(result):
    return {
        "launchMode": result.get("launchMode"),
        "logPath": result.get("logPath"),
        "logExists": Path(result["logPath"]).exists(),
    }


def _build_roundtrip_check(imported):
    imported_node = slicer.mrmlScene.GetNodeByID(imported["segmentationNodeId"])
    return {
        "source": imported.get("source"),
        "segmentationNodeName": imported.get("segmentationNodeName"),
        "segmentCount": imported_node.GetSegmentation().GetNumberOfSegments() if imported_node else 0,
    }


def _build_refinement_check(refinement):
    return {
        "summary": refinement.get("summary"),
        "checklistCount": len(refinement.get("checklist") or []),
    }


def _build_advisor_check(advisor):
    return {
        "preferredCtBackend": advisor.get("preferredCtBackend"),
        "interactiveBackend": advisor.get("interactiveBackend"),
        "frameworkCount": len(advisor.get("frameworkFit") or []),
    }


def _build_dicom_check(dicom_result):
    return {
        "patientCount": dicom_result.get("patientCount"),
        "imported": dicom_result.get("imported"),
    }


if __name__ == "__main__":
    main()
