from __future__ import annotations

import shutil
import json
from pathlib import Path
from typing import Dict, List, Optional

import slicer
import vtk

from ENT_Module.ai_runtime_advisor import build_nnunet_dataset_stub, inspect_local_ai_runtimes, write_ai_workspace_bundle


def import_dicom_folder(folder_path: str, load_patient: bool = True) -> Dict[str, object]:
    try:
        from DICOMLib import DICOMUtils
    except Exception as error:
        raise RuntimeError(f"DICOMLib is not available in this Slicer session: {error}")

    folder = Path(folder_path)
    if not folder.exists():
        raise RuntimeError(f"DICOM folder does not exist: {folder_path}")
    database = getattr(slicer, "dicomDatabase", None)
    if not database:
        raise RuntimeError("Slicer DICOM database is not available.")

    imported = DICOMUtils.importDicom(str(folder), database)
    patient_uids = list(database.patients())
    loaded = []
    if load_patient and patient_uids:
        loaded = DICOMUtils.loadPatientByUID(patient_uids[-1])
    return {
        "folder": str(folder),
        "imported": bool(imported is None or imported),
        "patientCount": len(patient_uids),
        "lastPatientUid": patient_uids[-1] if patient_uids else None,
        "loaded": loaded,
    }


def export_case_bundle(result: Dict[str, object], target_directory: str) -> Dict[str, object]:
    target_dir = Path(target_directory)
    target_dir.mkdir(parents=True, exist_ok=True)
    copied: List[str] = []
    for candidate in _collect_case_paths(result):
        source = Path(candidate)
        if not source.exists():
            continue
        destination = target_dir / source.name
        if source.is_file():
            shutil.copy2(source, destination)
            copied.append(str(destination))
        elif source.is_dir():
            bundle_dir = target_dir / source.name
            if bundle_dir.exists():
                shutil.rmtree(bundle_dir)
            shutil.copytree(source, bundle_dir)
            copied.append(str(bundle_dir))
    return {"directory": str(target_dir), "files": copied}


def export_ai_workspace(result: Dict[str, object], target_directory: str) -> Dict[str, object]:
    target_dir = Path(target_directory)
    target_dir.mkdir(parents=True, exist_ok=True)

    volume_node = _get_scene_node(result.get("volumeNodeId"))
    if not volume_node:
        raise RuntimeError("Volume node is not available in the current Slicer scene.")
    segmentation_node = _get_scene_node(result.get("segmentationNodeId"))

    copied_bundle = export_case_bundle(result, str(target_dir))
    image_path = target_dir / "image.nii.gz"
    if not slicer.util.saveNode(volume_node, str(image_path)):
        raise RuntimeError("Failed to export active volume to AI workspace image.nii.gz")

    segmentation_path = None
    labelmap_path = None
    if segmentation_node:
        seg_path = target_dir / "segmentation.seg.nrrd"
        if slicer.util.saveNode(segmentation_node, str(seg_path)):
            segmentation_path = str(seg_path)
        labelmap_node = slicer.mrmlScene.AddNewNodeByClass("vtkMRMLLabelMapVolumeNode", "ENT_AI_Workspace_Labelmap")
        try:
            ids = vtk.vtkStringArray()
            segmentation = segmentation_node.GetSegmentation()
            for index in range(segmentation.GetNumberOfSegments()):
                ids.InsertNextValue(segmentation.GetNthSegmentID(index))
            slicer.modules.segmentations.logic().ExportSegmentsToLabelmapNode(
                segmentation_node,
                ids,
                labelmap_node,
                volume_node,
            )
            label_path = target_dir / "labelmap.nii.gz"
            if slicer.util.saveNode(labelmap_node, str(label_path)):
                labelmap_path = str(label_path)
        finally:
            slicer.mrmlScene.RemoveNode(labelmap_node)

    nnunet_paths = _prepare_nnunet_workspace(
        target_dir,
        case_name=result.get("volumeName") or volume_node.GetName(),
        modality=(result.get("studyInfo") or {}).get("dicomModality") or "",
        image_path=str(image_path),
        labelmap_path=labelmap_path,
    )
    vista3d_paths = _prepare_vista3d_workspace(
        target_dir,
        case_name=result.get("volumeName") or volume_node.GetName(),
        image_path=str(image_path),
        labelmap_path=labelmap_path,
        result=result,
    )
    advisor = inspect_local_ai_runtimes()
    workspace_meta = write_ai_workspace_bundle(
        str(target_dir),
        case_name=result.get("volumeName") or volume_node.GetName(),
        modality=(result.get("studyInfo") or {}).get("dicomModality") or "",
        study_info=result.get("studyInfo") or {},
        report_result=result,
        image_path=str(image_path),
        segmentation_path=segmentation_path,
        labelmap_path=labelmap_path,
        nnunet_artifacts=nnunet_paths,
    )
    return {
        "directory": str(target_dir),
        "caseBundle": copied_bundle,
        "imagePath": str(image_path),
        "segmentationPath": segmentation_path,
        "labelmapPath": labelmap_path,
        "nnunetWorkspace": nnunet_paths,
        "vista3dWorkspace": vista3d_paths,
        "runtimeAdvisor": advisor,
        "workspaceMeta": workspace_meta,
    }


def launch_workspace_command(target_directory: str, command_name: str) -> Dict[str, object]:
    target_dir = Path(target_directory)
    command_path = target_dir / f"{command_name}.cmd"
    if not command_path.exists():
        raise RuntimeError(f"Workspace command file was not found: {command_path}")
    process = slicer.util.launchConsoleProcess(["cmd.exe", "/c", str(command_path)])
    return {
        "directory": str(target_dir),
        "commandName": command_name,
        "commandPath": str(command_path),
        "pid": getattr(process, "pid", None),
    }


def _collect_case_paths(result: Dict[str, object]) -> List[str]:
    paths: List[str] = []
    for key in ("reportPath", "htmlReportPath"):
        value = result.get(key)
        if value:
            paths.append(str(value))
    export_info = result.get("exportInfo") or {}
    directory = export_info.get("directory")
    if directory:
        paths.append(str(directory))
    screenshot_info = result.get("reportScreenshots") or _load_report_screenshots(result.get("reportPath"))
    for row in screenshot_info:
        if row.get("path"):
            paths.append(str(row["path"]))
    return paths


def _load_report_screenshots(report_path: Optional[str]) -> List[Dict[str, object]]:
    if not report_path:
        return []
    path = Path(report_path)
    if not path.exists():
        return []
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return []
    return payload.get("reportScreenshots") or []


def _get_scene_node(node_id: Optional[str]):
    if not node_id:
        return None
    try:
        return slicer.mrmlScene.GetNodeByID(node_id)
    except Exception:
        return None


def _prepare_nnunet_workspace(
    target_dir: Path,
    *,
    case_name: str,
    modality: str,
    image_path: str,
    labelmap_path: Optional[str],
) -> Dict[str, object]:
    case_id = _sanitize_case_id(case_name)
    nnunet_dir = target_dir / "nnunet_workspace"
    images_ts_dir = nnunet_dir / "imagesTs"
    labels_ts_dir = nnunet_dir / "labelsTs"
    images_ts_dir.mkdir(parents=True, exist_ok=True)
    labels_ts_dir.mkdir(parents=True, exist_ok=True)

    nnunet_image = images_ts_dir / f"{case_id}_0000.nii.gz"
    shutil.copy2(image_path, nnunet_image)

    nnunet_label = None
    if labelmap_path and Path(labelmap_path).exists():
        nnunet_label = labels_ts_dir / f"{case_id}.nii.gz"
        shutil.copy2(labelmap_path, nnunet_label)

    dataset_json = nnunet_dir / "dataset.json"
    dataset_json.write_text(
        json.dumps(
            build_nnunet_dataset_stub(case_id, modality, has_labels=bool(nnunet_label)),
            indent=2,
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    return {
        "directory": str(nnunet_dir),
        "imageTestPath": str(nnunet_image),
        "labelTestPath": str(nnunet_label) if nnunet_label else None,
        "datasetJsonPath": str(dataset_json),
    }


def _prepare_vista3d_workspace(
    target_dir: Path,
    *,
    case_name: str,
    image_path: str,
    labelmap_path: Optional[str],
    result: Dict[str, object],
) -> Dict[str, object]:
    vista_dir = target_dir / "vista3d_workspace"
    vista_dir.mkdir(parents=True, exist_ok=True)
    image_dst = vista_dir / "image.nii.gz"
    shutil.copy2(image_path, image_dst)
    label_dst = None
    if labelmap_path and Path(labelmap_path).exists():
        label_dst = vista_dir / "labelmap.nii.gz"
        shutil.copy2(labelmap_path, label_dst)
    prompts_path = vista_dir / "prompts_template.json"
    prompts_path.write_text(json.dumps(_build_vista3d_prompt_template(case_name, result), indent=2, ensure_ascii=False), encoding="utf-8")
    return {
        "directory": str(vista_dir),
        "imagePath": str(image_dst),
        "labelmapPath": str(label_dst) if label_dst else None,
        "promptsPath": str(prompts_path),
    }


def _build_vista3d_prompt_template(case_name: str, result: Dict[str, object]) -> Dict[str, object]:
    report = result.get("sinusReport") or result.get("mriReport") or {}
    targets = []
    for finding in (report.get("findingRows") or [])[:10]:
        structure = str(finding.get("structure", "")).strip()
        if not structure:
            continue
        targets.append(
            {
                "name": structure,
                "positive_points_ijk": [],
                "negative_points_ijk": [],
                "bounding_box_ijk": [],
                "notes": str(finding.get("details", "")),
            }
        )
    if not targets:
        targets.append(
            {
                "name": "region_of_interest",
                "positive_points_ijk": [],
                "negative_points_ijk": [],
                "bounding_box_ijk": [],
                "notes": "Fill with VISTA3D-style interactive prompts.",
            }
        )
    return {"case": case_name, "targets": targets}


def _sanitize_case_id(value: str) -> str:
    cleaned = "".join(char if char.isalnum() or char in {"_", "-"} else "_" for char in value.strip())
    return cleaned.strip("._") or "case"
