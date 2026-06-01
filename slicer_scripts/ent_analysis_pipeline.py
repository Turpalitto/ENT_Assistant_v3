from __future__ import annotations

import json
import os
from pathlib import Path
import csv
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
    build_case_comparison,
    build_ent_pathology_flags,
    build_ent_summary,
    build_longitudinal_timeline,
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
        return self._run_for_volume(volume_node, config)

    def run_batch(self, config: AnalysisConfig) -> Dict[str, object]:
        volume_nodes = self._get_volume_nodes(config.batch_mode)
        results = []
        for index, volume_node in enumerate(volume_nodes, start=1):
            self.log(f"[{index}/{len(volume_nodes)}] Processing volume: {volume_node.GetName()}")
            results.append(self._run_for_volume(volume_node, config))
        batch_export = self._save_batch_index(results, config) if results and config.save_report else None
        batch_csv = self._save_batch_csv(results, config) if results and config.save_report else None
        comparisons = self._build_batch_comparisons(results)
        comparison_index = self._save_comparison_index(comparisons, config) if comparisons and config.save_report else None
        longitudinal_timeline = build_longitudinal_timeline(results)
        timeline_path = self._save_longitudinal_timeline(longitudinal_timeline, config) if results and config.save_report else None
        if batch_export:
            self.log(f"Batch index saved: {batch_export}")
        if batch_csv:
            self.log(f"Batch CSV saved: {batch_csv}")
        if comparison_index:
            self.log(f"Comparison index saved: {comparison_index}")
        if timeline_path:
            self.log(f"Timeline index saved: {timeline_path}")
        return {
            "mode": config.batch_mode,
            "count": len(results),
            "cases": results,
            "batchIndexPath": batch_export,
            "batchCsvPath": batch_csv,
            "comparisons": comparisons,
            "comparisonIndexPath": comparison_index,
            "timelinePath": timeline_path,
            "longitudinalTimeline": longitudinal_timeline,
        }

    def _run_for_volume(self, volume_node, config: AnalysisConfig) -> Dict[str, object]:
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
        ent_summary = build_ent_summary(preset, measurements)
        pathology_flags = build_ent_pathology_flags(measurements)
        rtstruct_readiness = self._check_rtstruct_readiness(volume_node)
        export_info = None
        if config.export_results:
            export_info = self._export_results(segmentation_node, volume_node, preset, config)
            self.log(self._format_export_summary(export_info))
        report_path = None
        if config.save_report:
            report_path = self._save_report(volume_node, preset.title, measurements, quality_checks, ent_summary, export_info, config)
            self.log(f"Report saved: {report_path}")

        summary = summarize_measurements(measurements)
        self.log(summary)
        self.log(self._format_quality_summary(quality_checks))
        self.log(ent_summary["summaryText"])
        if pathology_flags:
            self.log(self._format_pathology_flags(pathology_flags))
        return {
            "volumeName": volume_node.GetName(),
            "studyInfo": self._extract_study_info(volume_node),
            "preset": preset.title,
            "segmentationNodeName": segmentation_node.GetName(),
            "measurements": measurements,
            "qualityChecks": quality_checks,
            "entSummary": ent_summary,
            "pathologyFlags": pathology_flags,
            "rtstructReadiness": rtstruct_readiness,
            "exportInfo": export_info,
            "reportPath": report_path,
            "summary": summary,
        }

    def _get_volume_nodes(self, batch_mode: str):
        volumes = slicer.util.getNodesByClass("vtkMRMLScalarVolumeNode")
        if not volumes:
            raise RuntimeError("No loaded scalar volume was found in the scene.")
        if batch_mode == "all":
            return list(volumes)
        if batch_mode == "compare_first_two":
            if len(volumes) < 2:
                raise RuntimeError("Comparison mode requires at least two loaded scalar volumes.")
            return list(volumes)[:2]
        return [volumes[0]]

    def _get_active_volume(self):
        volume_node = self._get_volume_nodes("active")[0]
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

    def _save_report(self, volume_node, preset_title: str, measurements, quality_checks, ent_summary, export_info, config: AnalysisConfig) -> str:
        report_dir = ensure_report_dir(config.report_dir, REPO_ROOT)
        report_path = build_report_path(report_dir, volume_node.GetName(), preset_title)
        pathology_flags = build_ent_pathology_flags(measurements)
        rtstruct_readiness = self._check_rtstruct_readiness(volume_node)
        payload = {
            "volumeName": volume_node.GetName(),
            "preset": preset_title,
            "generatedAt": __import__("datetime").datetime.now().isoformat(),
            "studyInfo": self._extract_study_info(volume_node),
            "measurements": measurements,
            "qualityChecks": quality_checks,
            "entSummary": ent_summary,
            "pathologyFlags": pathology_flags,
            "rtstructReadiness": rtstruct_readiness,
            "exports": export_info,
            "impressionDraft": build_impression(preset_title, measurements),
        }
        report_path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
        return str(report_path)

    def _save_batch_index(self, results, config: AnalysisConfig) -> str:
        report_dir = ensure_report_dir(config.report_dir, REPO_ROOT)
        index_path = report_dir / "batch_index.json"
        payload = {
            "generatedAt": __import__("datetime").datetime.now().isoformat(),
            "count": len(results),
            "cases": [
                {
                    "volumeName": result.get("volumeName"),
                    "preset": result.get("preset"),
                    "reportPath": result.get("reportPath"),
                    "exportDirectory": (result.get("exportInfo") or {}).get("directory"),
                    "qcCodes": [finding.get("code") for finding in result.get("qualityChecks", [])],
                }
                for result in results
            ],
        }
        index_path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
        return str(index_path)

    def _save_batch_csv(self, results, config: AnalysisConfig) -> str:
        report_dir = ensure_report_dir(config.report_dir, REPO_ROOT)
        csv_path = report_dir / "batch_registry.csv"
        with csv_path.open("w", encoding="utf-8", newline="") as handle:
            writer = csv.DictWriter(
                handle,
                fieldnames=[
                    "volumeName",
                    "preset",
                    "reportPath",
                    "exportDirectory",
                    "topAirwaySegment",
                    "topAirwayVolumeMl",
                    "topAsymmetryPair",
                    "topAsymmetryRatio",
                    "heuristicFlags",
                    "qcCodes",
                    "dicomStudyDate",
                    "dicomSeriesDescription",
                    "pathologyFlags",
                    "rtstructReady",
                ],
            )
            writer.writeheader()
            for result in results:
                ent_summary = result.get("entSummary") or {}
                airway_rows = ent_summary.get("airwayOrCavitySegments") or []
                asymmetry_rows = ent_summary.get("strongestAsymmetry") or []
                flags = ent_summary.get("heuristicFlags") or []
                top_airway = airway_rows[0] if airway_rows else {}
                top_asymmetry = asymmetry_rows[0] if asymmetry_rows else {}
                writer.writerow(
                    {
                        "volumeName": result.get("volumeName"),
                        "preset": result.get("preset"),
                        "reportPath": result.get("reportPath"),
                        "exportDirectory": (result.get("exportInfo") or {}).get("directory"),
                        "topAirwaySegment": top_airway.get("segment"),
                        "topAirwayVolumeMl": top_airway.get("volumeMl"),
                        "topAsymmetryPair": " | ".join(top_asymmetry.get("pair", [])) if top_asymmetry else "",
                        "topAsymmetryRatio": top_asymmetry.get("ratio"),
                        "heuristicFlags": " | ".join(flag.get("code", "") for flag in flags),
                        "qcCodes": " | ".join(finding.get("code", "") for finding in result.get("qualityChecks", [])),
                        "dicomStudyDate": (result.get("studyInfo") or {}).get("dicomStudyDate"),
                        "dicomSeriesDescription": (result.get("studyInfo") or {}).get("dicomSeriesDescription"),
                        "pathologyFlags": " | ".join(flag.get("code", "") for flag in result.get("pathologyFlags", [])),
                        "rtstructReady": (result.get("rtstructReadiness") or {}).get("ready"),
                    }
                )
        return str(csv_path)

    def _extract_study_info(self, volume_node) -> Dict[str, object]:
        node_name = volume_node.GetName()
        spacing = [round(value, 4) for value in volume_node.GetSpacing()]
        dimensions = list(volume_node.GetImageData().GetDimensions()) if volume_node.GetImageData() else None
        payload = {
            "volumeName": node_name,
            "spacingMm": spacing,
            "dimensionsVoxels": dimensions,
        }
        payload.update(self._extract_dicom_metadata(volume_node))
        return payload

    def _extract_dicom_metadata(self, volume_node) -> Dict[str, object]:
        payload: Dict[str, object] = {}
        try:
            instance_uids = volume_node.GetAttribute("DICOM.instanceUIDs")
            if not instance_uids:
                return payload
            first_uid = str(instance_uids).split()[0]
            database = getattr(slicer, "dicomDatabase", None)
            if not database:
                return payload
            payload["dicomInstanceUid"] = first_uid
            payload["dicomPatientName"] = database.fileValue(first_uid, "0010,0010")
            payload["dicomPatientId"] = database.fileValue(first_uid, "0010,0020")
            payload["dicomStudyDate"] = database.fileValue(first_uid, "0008,0020")
            payload["dicomStudyDescription"] = database.fileValue(first_uid, "0008,1030")
            payload["dicomSeriesDescription"] = database.fileValue(first_uid, "0008,103E")
            payload["dicomModality"] = database.fileValue(first_uid, "0008,0060")
        except Exception:
            return payload
        return {key: value for key, value in payload.items() if value}

    def _build_batch_comparisons(self, results) -> List[Dict[str, object]]:
        if len(results) < 2:
            return []
        return [build_case_comparison(previous_case, current_case) for previous_case, current_case in zip(results, results[1:])]

    def _save_comparison_index(self, comparisons, config: AnalysisConfig) -> str:
        report_dir = ensure_report_dir(config.report_dir, REPO_ROOT)
        path = report_dir / "comparison_index.json"
        payload = {
            "generatedAt": __import__("datetime").datetime.now().isoformat(),
            "count": len(comparisons),
            "comparisons": comparisons,
        }
        path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
        return str(path)

    def _save_longitudinal_timeline(self, timeline, config: AnalysisConfig) -> str:
        report_dir = ensure_report_dir(config.report_dir, REPO_ROOT)
        path = report_dir / "longitudinal_timeline.json"
        payload = {"generatedAt": __import__("datetime").datetime.now().isoformat(), "timeline": timeline}
        path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
        return str(path)

    def _format_quality_summary(self, quality_checks) -> str:
        if not quality_checks:
            return "QC: no findings."
        lines = ["QC summary:"]
        for finding in quality_checks:
            level = str(finding.get("level", "info")).upper()
            message = str(finding.get("message", ""))
            lines.append(f"- {level}: {message}")
        return "\n".join(lines)

    def _format_pathology_flags(self, pathology_flags) -> str:
        lines = ["ENT pathology-oriented flags:"]
        for flag in pathology_flags:
            lines.append(f"- {flag.get('code')}: {flag.get('message')}")
        return "\n".join(lines)

    def _check_rtstruct_readiness(self, volume_node) -> Dict[str, object]:
        module_available = hasattr(slicer.modules, "dicomrtimportexport") or hasattr(slicer.modules, "beams")
        plugin_available = self._get_rtstruct_exporter() is not None
        dicom_database_available = bool(getattr(slicer, "dicomDatabase", None))
        dicom_instance_uids = bool(volume_node.GetAttribute("DICOM.instanceUIDs"))
        ready = module_available and plugin_available and dicom_database_available and dicom_instance_uids
        reasons = []
        if not module_available:
            reasons.append("SlicerRT export module not detected.")
        if not plugin_available:
            reasons.append("DicomRtImportExportPlugin is not available in this session.")
        if not dicom_database_available:
            reasons.append("Slicer DICOM database is not available.")
        if not dicom_instance_uids:
            reasons.append("Volume was not loaded with DICOM instance UIDs.")
        return {
            "ready": ready,
            "moduleAvailable": module_available,
            "pluginAvailable": plugin_available,
            "dicomDatabaseAvailable": dicom_database_available,
            "hasDicomInstanceUids": dicom_instance_uids,
            "notes": reasons or ["Environment looks ready for RTSTRUCT export attempts."],
        }

    def _get_rtstruct_exporter(self):
        try:
            import DicomRtImportExportPlugin

            exporter_class = getattr(DicomRtImportExportPlugin, "DicomRtImportExportPluginClass", None)
            if exporter_class:
                return exporter_class()
        except Exception:
            pass
        try:
            dicom_plugins = getattr(slicer.modules, "dicomPlugins", None)
            plugin_class = dicom_plugins.get("DicomRtImportExportPlugin") if dicom_plugins else None
            if plugin_class:
                return plugin_class()
        except Exception:
            pass
        return None

    def _attempt_rtstruct_export(self, case_dir, segmentation_node, volume_node) -> Dict[str, object]:
        exporter = self._get_rtstruct_exporter()
        if exporter is None:
            return {"success": False, "message": "DicomRtImportExportPlugin is not available."}

        sh_node = slicer.vtkMRMLSubjectHierarchyNode.GetSubjectHierarchyNode(slicer.mrmlScene)
        volume_item_id = sh_node.GetItemByDataNode(volume_node)
        segmentation_item_id = sh_node.GetItemByDataNode(segmentation_node)
        if not volume_item_id or not segmentation_item_id:
            return {"success": False, "message": "Subject hierarchy items were not found for volume/segmentation."}

        study_item_id = sh_node.GetItemParent(volume_item_id)
        if study_item_id:
            sh_node.SetItemParent(segmentation_item_id, study_item_id)

        exportables = []
        errors = []
        for item_id, label in [(volume_item_id, "volume"), (segmentation_item_id, "segmentation")]:
            try:
                exportables.extend(exporter.examineForExport(item_id))
            except Exception as error:
                errors.append(f"{label} examineForExport failed: {error}")

        if errors:
            return {"success": False, "message": " | ".join(errors)}
        if not exportables:
            return {"success": False, "message": "No exportables were returned by SlicerRT exporter."}

        output_dir = str(case_dir / "rtstruct_dicom")
        Path(output_dir).mkdir(parents=True, exist_ok=True)
        for exportable in exportables:
            try:
                exportable.directory = output_dir
            except Exception:
                pass

        try:
            export_result = exporter.export(exportables)
        except Exception as error:
            return {"success": False, "message": f"RTSTRUCT export call failed: {error}"}

        success = bool(export_result) or export_result is None
        return {
            "success": success,
            "message": "RTSTRUCT export attempted through DicomRtImportExportPlugin.",
            "directory": output_dir,
            "rawResult": str(export_result),
        }

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

        if config.export_rtstruct:
            readiness = self._check_rtstruct_readiness(volume_node)
            export_info["rtstructReadiness"] = readiness
            if readiness.get("ready"):
                rtstruct_result = self._attempt_rtstruct_export(case_dir, segmentation_node, volume_node)
                export_info["rtstructExport"] = rtstruct_result
                if rtstruct_result.get("success") and rtstruct_result.get("directory"):
                    export_info["files"].append(str(Path(rtstruct_result["directory"]) / "*.dcm"))
                else:
                    export_info.setdefault("warnings", []).append(
                        f"RTSTRUCT export attempt did not complete: {rtstruct_result.get('message')}"
                    )
            else:
                export_info.setdefault("warnings", []).append(
                    "RTSTRUCT export skipped because readiness checks did not pass."
                )

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
    pipeline = ENTAnalysisPipeline(log_callback=log_callback)
    if config.batch_mode in {"all", "compare_first_two"}:
        return pipeline.run_batch(config)
    return pipeline.run(config)
