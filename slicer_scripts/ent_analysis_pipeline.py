from __future__ import annotations

import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
from typing import Dict, List, Optional

import slicer
import vtk


REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if REPO_ROOT not in sys.path:
    sys.path.insert(0, REPO_ROOT)

from ENT_Module.ent_assistant_core import (
    AnalysisConfig,
    build_report_path,
    build_impression,
    build_quality_checks,
    ensure_export_dir,
    ensure_report_dir,
    get_preset,
    sanitize_filename,
    summarize_measurements,
)


class ENTAnalysisPipeline:
    def __init__(self, log_callback=None):
        self.log_callback = log_callback or print

    def log(self, message: str) -> None:
        self.log_callback(message)

    def run(self, config: AnalysisConfig) -> Dict[str, object]:
        volume_node = self._get_active_volume()
        preset = get_preset(config.preset_key)
        self.log(f"Starting preset: {preset.title}")

        if preset.mode == "totalsegmentator" and config.use_totalsegmentator:
            executable = self._find_totalsegmentator()
            if executable:
                self.log(f"Using TotalSegmentator: {executable}")
                segmentation_node = self._run_totalsegmentator(volume_node, preset, executable, config)
            else:
                self.log("TotalSegmentator not found. Falling back to threshold segmentation.")
                segmentation_node = self._run_threshold_segmentation(volume_node, config)
        else:
            segmentation_node = self._run_threshold_segmentation(volume_node, config)

        measurements = self._compute_measurements(segmentation_node, volume_node)
        quality_checks = build_quality_checks(preset, measurements)
        export_info = None
        if config.export_results:
            export_info = self._export_results(segmentation_node, volume_node, preset, config)
            self.log(self._format_export_summary(export_info))
        report_path = None
        if config.save_report:
            report_path = self._save_report(volume_node, preset.title, measurements, quality_checks, export_info, config)
            self.log(f"Report saved: {report_path}")

        summary = summarize_measurements(measurements)
        self.log(summary)
        self.log(self._format_quality_summary(quality_checks))
        return {
            "preset": preset.title,
            "segmentationNodeName": segmentation_node.GetName(),
            "measurements": measurements,
            "qualityChecks": quality_checks,
            "exportInfo": export_info,
            "reportPath": report_path,
            "summary": summary,
        }

    def _get_active_volume(self):
        volumes = slicer.util.getNodesByClass("vtkMRMLScalarVolumeNode")
        if not volumes:
            raise RuntimeError("No loaded scalar volume was found in the scene.")
        volume_node = volumes[0]
        selection_node = slicer.app.applicationLogic().GetSelectionNode()
        selection_node.SetReferenceActiveVolumeID(volume_node.GetID())
        slicer.app.applicationLogic().PropagateVolumeSelection()
        return volume_node

    def _find_totalsegmentator(self) -> Optional[str]:
        return next(
            (
                candidate
                for candidate in [
                    shutil.which("TotalSegmentator"),
                    shutil.which("totalsegmentator"),
                    shutil.which("PythonSlicer"),
                ]
                if candidate
            ),
            None,
        )

    def _run_totalsegmentator(self, volume_node, preset, executable: str, config: AnalysisConfig):
        if not preset.totalsegmentator_task or not preset.expected_masks:
            raise RuntimeError(f"Preset {preset.title} is missing TotalSegmentator settings.")

        workspace = Path(tempfile.mkdtemp(prefix="ent_ai_"))
        input_path = workspace / "input_volume.nii.gz"
        output_dir = workspace / "totalsegmentator_output"
        output_dir.mkdir(parents=True, exist_ok=True)

        if not slicer.util.saveNode(volume_node, str(input_path)):
            raise RuntimeError("Failed to export active volume to NIfTI for TotalSegmentator.")

        command = [executable, "-i", str(input_path), "-o", str(output_dir), "--task", preset.totalsegmentator_task]
        if os.path.basename(executable).lower() == "pythonslicer.exe":
            command = [
                executable,
                "-m",
                "TotalSegmentator",
                "-i",
                str(input_path),
                "-o",
                str(output_dir),
                "--task",
                preset.totalsegmentator_task,
            ]
        if config.ai_quality == "fast":
            command.append("--fast")
        if config.robust_crop:
            command.append("--robust_crop")
        if config.use_cpu:
            command.extend(["--device", "cpu"])

        result = subprocess.run(command, capture_output=True, text=True)
        if result.returncode != 0:
            raise RuntimeError(result.stderr.strip() or "TotalSegmentator failed without stderr output.")

        segmentation_node = slicer.mrmlScene.AddNewNodeByClass("vtkMRMLSegmentationNode")
        segmentation_node.SetName(f"ENT_AI_{preset.key}")
        segmentation_node.CreateDefaultDisplayNodes()
        segmentation_node.SetReferenceImageGeometryParameterFromVolumeNode(volume_node)

        loaded_any = False
        for mask_name in preset.expected_masks:
            mask_path = output_dir / f"{mask_name}.nii.gz"
            if not mask_path.exists():
                continue
            success, label_node = slicer.util.loadLabelVolume(str(mask_path), returnNode=True)
            if not success:
                continue
            label_node.SetName(mask_name)
            before = segmentation_node.GetSegmentation().GetNumberOfSegments()
            slicer.modules.segmentations.logic().ImportLabelmapToSegmentationNode(label_node, segmentation_node)
            after = segmentation_node.GetSegmentation().GetNumberOfSegments()
            if after > before:
                imported_segment_id = segmentation_node.GetSegmentation().GetNthSegmentID(after - 1)
                segmentation_node.GetSegmentation().GetSegment(imported_segment_id).SetName(mask_name)
            slicer.mrmlScene.RemoveNode(label_node)
            loaded_any = True

        if not loaded_any:
            raise RuntimeError("TotalSegmentator finished, but none of the expected masks were imported.")

        segmentation_node.CreateClosedSurfaceRepresentation()
        segmentation_node.GetDisplayNode().SetVisibility3D(True)
        return segmentation_node

    def _run_threshold_segmentation(self, volume_node, config: AnalysisConfig):
        preset = get_preset(config.preset_key)
        bone_min = config.bone_threshold_min if config.bone_threshold_min is not None else preset.bone_threshold_min
        bone_max = config.bone_threshold_max if config.bone_threshold_max is not None else preset.bone_threshold_max
        air_min = config.air_threshold_min if config.air_threshold_min is not None else preset.air_threshold_min
        air_max = config.air_threshold_max if config.air_threshold_max is not None else preset.air_threshold_max

        segmentation_node = slicer.mrmlScene.AddNewNodeByClass("vtkMRMLSegmentationNode")
        segmentation_node.SetName("ENT_Threshold_Segmentation")
        segmentation_node.CreateDefaultDisplayNodes()
        segmentation_node.SetReferenceImageGeometryParameterFromVolumeNode(volume_node)

        bone_segment_id = segmentation_node.GetSegmentation().AddEmptySegment("Bone")
        air_segment_id = segmentation_node.GetSegmentation().AddEmptySegment("Air")
        soft_segment_id = segmentation_node.GetSegmentation().AddEmptySegment("SoftTissue")

        editor_widget = slicer.qMRMLSegmentEditorWidget()
        editor_widget.setMRMLScene(slicer.mrmlScene)
        editor_node = slicer.mrmlScene.AddNewNodeByClass("vtkMRMLSegmentEditorNode")
        editor_widget.setMRMLSegmentEditorNode(editor_node)
        editor_widget.setSegmentationNode(segmentation_node)
        editor_widget.setSourceVolumeNode(volume_node)

        self._apply_threshold(editor_widget, editor_node, bone_segment_id, bone_min, bone_max)
        self._apply_threshold(editor_widget, editor_node, air_segment_id, air_min, air_max)
        self._apply_threshold(
            editor_widget,
            editor_node,
            soft_segment_id,
            preset.soft_tissue_threshold_min,
            preset.soft_tissue_threshold_max,
        )

        segmentation = segmentation_node.GetSegmentation()
        segmentation.GetSegment(bone_segment_id).SetColor(0.90, 0.82, 0.62)
        segmentation.GetSegment(air_segment_id).SetColor(0.26, 0.62, 1.00)
        segmentation.GetSegment(soft_segment_id).SetColor(0.87, 0.48, 0.52)

        segmentation_node.CreateClosedSurfaceRepresentation()
        segmentation_node.GetDisplayNode().SetVisibility3D(True)
        return segmentation_node

    def _apply_threshold(self, editor_widget, editor_node, segment_id: str, minimum: int, maximum: int):
        editor_node.SetSelectedSegmentID(segment_id)
        editor_widget.setActiveEffectByName("Threshold")
        effect = editor_widget.activeEffect()
        effect.setParameter("MinimumThreshold", str(minimum))
        effect.setParameter("MaximumThreshold", str(maximum))
        effect.self().onApply()

    def _compute_measurements(self, segmentation_node, volume_node) -> List[Dict[str, object]]:
        segmentation = segmentation_node.GetSegmentation()
        voxel_volume_mm3 = volume_node.GetSpacing()[0] * volume_node.GetSpacing()[1] * volume_node.GetSpacing()[2]
        results: List[Dict[str, object]] = []

        for index in range(segmentation.GetNumberOfSegments()):
            segment_id = segmentation.GetNthSegmentID(index)
            labelmap_node = slicer.mrmlScene.AddNewNodeByClass("vtkMRMLLabelMapVolumeNode", f"tmp_{index}")
            ids = vtk.vtkStringArray()
            ids.InsertNextValue(segment_id)
            slicer.modules.segmentations.logic().ExportSegmentsToLabelmapNode(
                segmentation_node,
                ids,
                labelmap_node,
                volume_node,
            )
            array = slicer.util.arrayFromVolume(labelmap_node)
            voxel_count = int((array > 0).sum())
            slicer.mrmlScene.RemoveNode(labelmap_node)
            results.append(
                {
                    "segment": segmentation.GetSegment(segment_id).GetName(),
                    "voxel_count": voxel_count,
                    "volume_mm3": round(voxel_count * voxel_volume_mm3, 2),
                    "volume_ml": round((voxel_count * voxel_volume_mm3) / 1000.0, 2),
                }
            )
        return results

    def _save_report(self, volume_node, preset_title: str, measurements, quality_checks, export_info, config: AnalysisConfig) -> str:
        report_dir = ensure_report_dir(config.report_dir, REPO_ROOT)
        report_path = build_report_path(report_dir, volume_node.GetName(), preset_title)
        payload = {
            "volumeName": volume_node.GetName(),
            "preset": preset_title,
            "generatedAt": __import__("datetime").datetime.now().isoformat(),
            "studyInfo": self._extract_study_info(volume_node),
            "measurements": measurements,
            "qualityChecks": quality_checks,
            "exports": export_info,
            "impressionDraft": build_impression(preset_title, measurements),
        }
        report_path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
        return str(report_path)

    def _extract_study_info(self, volume_node) -> Dict[str, object]:
        node_name = volume_node.GetName()
        spacing = [round(value, 4) for value in volume_node.GetSpacing()]
        dimensions = list(volume_node.GetImageData().GetDimensions()) if volume_node.GetImageData() else None
        return {
            "volumeName": node_name,
            "spacingMm": spacing,
            "dimensionsVoxels": dimensions,
        }

    def _format_quality_summary(self, quality_checks) -> str:
        if not quality_checks:
            return "QC: no findings."
        lines = ["QC summary:"]
        for finding in quality_checks:
            level = str(finding.get("level", "info")).upper()
            message = str(finding.get("message", ""))
            lines.append(f"- {level}: {message}")
        return "\n".join(lines)

    def _export_results(self, segmentation_node, volume_node, preset, config: AnalysisConfig) -> Dict[str, object]:
        export_dir = ensure_export_dir(config.export_dir, REPO_ROOT)
        case_dir = export_dir / f"{sanitize_filename(volume_node.GetName())}__{sanitize_filename(preset.title)}"
        case_dir.mkdir(parents=True, exist_ok=True)

        export_info: Dict[str, object] = {"directory": str(case_dir), "files": []}
        if config.export_seg_nrrd:
            try:
                segmentation_path = case_dir / "segmentation.seg.nrrd"
                if slicer.util.saveNode(segmentation_node, str(segmentation_path)):
                    export_info["files"].append(str(segmentation_path))
            except Exception as error:
                export_info.setdefault("warnings", []).append(f"seg_nrrd export failed: {error}")

        if config.export_labelmap_nifti:
            try:
                labelmap_node = slicer.mrmlScene.AddNewNodeByClass("vtkMRMLLabelMapVolumeNode", "ENT_Export_Labelmap")
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
                labelmap_path = case_dir / "segmentation_labelmap.nii.gz"
                if slicer.util.saveNode(labelmap_node, str(labelmap_path)):
                    export_info["files"].append(str(labelmap_path))
                slicer.mrmlScene.RemoveNode(labelmap_node)
            except Exception as error:
                export_info.setdefault("warnings", []).append(f"labelmap export failed: {error}")

        if config.export_surface_models:
            try:
                segmentation_node.CreateClosedSurfaceRepresentation()
                ids = vtk.vtkStringArray()
                segmentation = segmentation_node.GetSegmentation()
                for index in range(segmentation.GetNumberOfSegments()):
                    ids.InsertNextValue(segmentation.GetNthSegmentID(index))
                slicer.modules.segmentations.logic().ExportSegmentsClosedSurfaceRepresentationToFiles(
                    str(case_dir),
                    segmentation_node,
                    ids,
                    "STL",
                    True,
                    1.0,
                    False,
                )
                export_info["files"].append(str(case_dir / "*.stl"))
            except Exception as error:
                export_info.setdefault("warnings", []).append(f"surface export failed: {error}")

        return export_info

    def _format_export_summary(self, export_info) -> str:
        if not export_info:
            return "Exports: disabled."
        files = export_info.get("files", [])
        lines = [f"Exports saved to: {export_info.get('directory', '')}"]
        for file_path in files:
            lines.append(f"- {file_path}")
        for warning in export_info.get("warnings", []):
            lines.append(f"- WARNING: {warning}")
        return "\n".join(lines)


def run_ent_analysis(config: AnalysisConfig, log_callback=None) -> Dict[str, object]:
    return ENTAnalysisPipeline(log_callback=log_callback).run(config)
