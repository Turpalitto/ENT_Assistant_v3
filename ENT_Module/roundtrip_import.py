from __future__ import annotations

import json
from pathlib import Path
from typing import Dict, List, Optional

import numpy as np
import slicer


DEFAULT_SINUS_NNUNET_LABEL_MAP = {
    1: "sinus_maxillary_right",
    2: "sinus_maxillary_left",
    3: "sinus_frontal_right",
    4: "sinus_frontal_left",
    5: "sinus_ethmoid_right",
    6: "sinus_ethmoid_left",
    7: "sinus_sphenoid_right",
    8: "sinus_sphenoid_left",
    9: "nasal_cavity_right",
    10: "nasal_cavity_left",
    11: "ostiomeatal_complex_right",
    12: "ostiomeatal_complex_left",
    13: "nasal_septum",
    14: "concha_bullosa_right",
    15: "concha_bullosa_left",
}


def detect_roundtrip_candidates(workspace_directory: str) -> Dict[str, object]:
    workspace = Path(workspace_directory)
    manifest = _load_workspace_manifest(workspace)
    case_name = str((manifest.get("caseName") if manifest else "") or "")
    nnunet_prediction = _find_best_nnunet_prediction(workspace, case_name)

    totalseg_dir = _find_totalseg_output_dir(workspace)

    generic_labelmap = workspace / "labelmap.nii.gz"
    if not generic_labelmap.exists():
        generic_labelmap = None

    return {
        "workspace": str(workspace),
        "nnunetPrediction": nnunet_prediction,
        "totalsegmentatorOutputDir": str(totalseg_dir) if totalseg_dir else None,
        "genericLabelmap": str(generic_labelmap) if generic_labelmap else None,
    }


def import_roundtrip_results(workspace_directory: str, reference_volume_node) -> Dict[str, object]:
    candidates = detect_roundtrip_candidates(workspace_directory)
    if candidates.get("nnunetPrediction"):
        return _import_nnunet_prediction(candidates["nnunetPrediction"], reference_volume_node)
    if candidates.get("totalsegmentatorOutputDir"):
        return _import_totalsegmentator_masks(candidates["totalsegmentatorOutputDir"], reference_volume_node)
    if candidates.get("genericLabelmap"):
        return _import_generic_labelmap(candidates["genericLabelmap"], reference_volume_node)
    raise RuntimeError("No round-trip prediction artifacts were found in the selected workspace.")


def _import_nnunet_prediction(labelmap_path: str, reference_volume_node) -> Dict[str, object]:
    success, label_node = slicer.util.loadLabelVolume(labelmap_path, returnNode=True)
    if not success:
        raise RuntimeError(f"Failed to load nnU-Net prediction labelmap: {labelmap_path}")
    try:
        segmentation_node = slicer.mrmlScene.AddNewNodeByClass("vtkMRMLSegmentationNode")
        segmentation_node.SetName("ENT_RoundTrip_nnUNet")
        segmentation_node.CreateDefaultDisplayNodes()
        segmentation_node.SetReferenceImageGeometryParameterFromVolumeNode(reference_volume_node)
        _import_multilabel_prediction_to_segmentation(label_node, reference_volume_node, segmentation_node)
        return {
            "source": "nnUNet",
            "segmentationNodeId": segmentation_node.GetID(),
            "segmentationNodeName": segmentation_node.GetName(),
        }
    finally:
        slicer.mrmlScene.RemoveNode(label_node)


def _import_totalsegmentator_masks(output_dir: str, reference_volume_node) -> Dict[str, object]:
    output_path = Path(output_dir)
    segmentation_node = slicer.mrmlScene.AddNewNodeByClass("vtkMRMLSegmentationNode")
    segmentation_node.SetName("ENT_RoundTrip_TotalSegmentator")
    segmentation_node.CreateDefaultDisplayNodes()
    segmentation_node.SetReferenceImageGeometryParameterFromVolumeNode(reference_volume_node)
    imported = 0
    for mask_path in sorted(output_path.glob("*.nii.gz")):
        success, label_node = slicer.util.loadLabelVolume(str(mask_path), returnNode=True)
        if not success:
            continue
        try:
            before = segmentation_node.GetSegmentation().GetNumberOfSegments()
            slicer.modules.segmentations.logic().ImportLabelmapToSegmentationNode(label_node, segmentation_node)
            after = segmentation_node.GetSegmentation().GetNumberOfSegments()
            if after > before:
                segment_id = segmentation_node.GetSegmentation().GetNthSegmentID(after - 1)
                segmentation_node.GetSegmentation().GetSegment(segment_id).SetName(_normalize_totalseg_segment_name(mask_path))
                imported += 1
        finally:
            slicer.mrmlScene.RemoveNode(label_node)
    if imported <= 0:
        raise RuntimeError("TotalSegmentator output directory was found, but no masks could be imported.")
    segmentation_node.CreateClosedSurfaceRepresentation()
    segmentation_node.GetDisplayNode().SetVisibility3D(True)
    return {
        "source": "TotalSegmentator",
        "segmentationNodeId": segmentation_node.GetID(),
        "segmentationNodeName": segmentation_node.GetName(),
        "importedMasks": imported,
    }


def _import_generic_labelmap(labelmap_path: str, reference_volume_node) -> Dict[str, object]:
    success, label_node = slicer.util.loadLabelVolume(labelmap_path, returnNode=True)
    if not success:
        raise RuntimeError(f"Failed to load generic labelmap: {labelmap_path}")
    try:
        segmentation_node = slicer.mrmlScene.AddNewNodeByClass("vtkMRMLSegmentationNode")
        segmentation_node.SetName("ENT_RoundTrip_Labelmap")
        segmentation_node.CreateDefaultDisplayNodes()
        segmentation_node.SetReferenceImageGeometryParameterFromVolumeNode(reference_volume_node)
        slicer.modules.segmentations.logic().ImportLabelmapToSegmentationNode(label_node, segmentation_node)
        segmentation_node.CreateClosedSurfaceRepresentation()
        segmentation_node.GetDisplayNode().SetVisibility3D(True)
        return {
            "source": "labelmap",
            "segmentationNodeId": segmentation_node.GetID(),
            "segmentationNodeName": segmentation_node.GetName(),
        }
    finally:
        slicer.mrmlScene.RemoveNode(label_node)


def _import_multilabel_prediction_to_segmentation(label_node, volume_node, segmentation_node) -> None:
    label_array = slicer.util.arrayFromVolume(label_node)
    imported_any = False
    for label_value, segment_name in DEFAULT_SINUS_NNUNET_LABEL_MAP.items():
        binary_mask = label_array == int(label_value)
        if int(binary_mask.sum()) <= 0:
            continue
        tmp_label = slicer.mrmlScene.AddNewNodeByClass("vtkMRMLLabelMapVolumeNode", f"tmp_{segment_name}")
        tmp_label.CopyOrientation(label_node)
        tmp_label.SetOrigin(label_node.GetOrigin())
        tmp_label.SetSpacing(label_node.GetSpacing())
        slicer.util.updateVolumeFromArray(tmp_label, binary_mask.astype(np.uint8))
        tmp_label.CreateDefaultDisplayNodes()
        before = segmentation_node.GetSegmentation().GetNumberOfSegments()
        slicer.modules.segmentations.logic().ImportLabelmapToSegmentationNode(tmp_label, segmentation_node)
        after = segmentation_node.GetSegmentation().GetNumberOfSegments()
        if after > before:
            imported_segment_id = segmentation_node.GetSegmentation().GetNthSegmentID(after - 1)
            segmentation_node.GetSegmentation().GetSegment(imported_segment_id).SetName(segment_name)
        slicer.mrmlScene.RemoveNode(tmp_label)
        imported_any = True
    if not imported_any:
        raise RuntimeError("nnU-Net prediction did not contain any labels mapped to known sinus structures.")
    segmentation_node.CreateClosedSurfaceRepresentation()
    segmentation_node.GetDisplayNode().SetVisibility3D(True)


def _load_workspace_manifest(workspace: Path) -> Optional[Dict[str, object]]:
    manifest_path = workspace / "ai_workspace_manifest.json"
    if not manifest_path.exists():
        return None
    try:
        return json.loads(manifest_path.read_text(encoding="utf-8"))
    except Exception:
        return None


def _find_best_nnunet_prediction(workspace: Path, case_name: str) -> Optional[str]:
    candidates: List[Path] = []
    for directory_name in ["nnunet_prediction", "predictions", "prediction", "inference", "output"]:
        directory = workspace / directory_name
        if directory.exists():
            candidates.extend(sorted(directory.glob("*.nii.gz")))
    if not candidates:
        return None
    case_key = case_name.lower().replace(" ", "_")
    ranked = sorted(candidates, key=lambda path: _score_prediction_candidate(path, case_key), reverse=True)
    return str(ranked[0])


def _score_prediction_candidate(path: Path, case_key: str) -> int:
    name = path.name.lower()
    score = 0
    if case_key and case_key in name:
        score += 10
    if "pred" in name or "prediction" in name:
        score += 6
    if "softmax" in name or "prob" in name:
        score -= 8
    if name.endswith(".nii.gz"):
        score += 2
    return score


def _find_totalseg_output_dir(workspace: Path) -> Optional[Path]:
    direct = workspace / "totalseg_output"
    if direct.exists() and any(direct.glob("*.nii.gz")):
        return direct
    for directory in workspace.rglob("*"):
        if directory.is_dir() and "totalseg" in directory.name.lower() and any(directory.glob("*.nii.gz")):
            return directory
    return None


def _normalize_totalseg_segment_name(mask_path: Path) -> str:
    return mask_path.stem.replace(".nii", "").replace("__", "_")
