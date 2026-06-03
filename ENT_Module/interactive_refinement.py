from __future__ import annotations

import json
from pathlib import Path
from typing import Dict, List, Optional

import slicer


def prepare_interactive_refinement(volume_node, segmentation_node, result: Optional[Dict[str, object]] = None) -> Dict[str, object]:
    if not volume_node:
        raise RuntimeError("Volume node is required for interactive refinement.")
    if not segmentation_node:
        raise RuntimeError("Segmentation node is required for interactive refinement.")

    _set_active_volume(volume_node)
    _show_segmentation_for_editing(segmentation_node)
    _open_segment_editor(volume_node, segmentation_node)
    checklist = build_refinement_checklist(result or {})

    return {
        "volumeName": volume_node.GetName(),
        "segmentationName": segmentation_node.GetName(),
        "checklist": checklist,
        "summary": "\n".join(f"- {row['title']}: {row['details']}" for row in checklist) if checklist else "Interactive refinement prepared.",
    }


def export_refinement_package(result: Dict[str, object], target_directory: str) -> Dict[str, object]:
    target_dir = Path(target_directory)
    target_dir.mkdir(parents=True, exist_ok=True)
    checklist = build_refinement_checklist(result)
    prompt_templates = build_prompt_templates(result)
    monai_prompts = build_monailabel_prompt_payload(result)
    vista_prompts = build_vista3d_prompt_payload(result)

    checklist_path = target_dir / "refinement_checklist.json"
    checklist_path.write_text(json.dumps(checklist, indent=2, ensure_ascii=False), encoding="utf-8")

    prompts_path = target_dir / "interactive_prompt_templates.json"
    prompts_path.write_text(json.dumps(prompt_templates, indent=2, ensure_ascii=False), encoding="utf-8")
    monai_prompts_path = target_dir / "monailabel_prompt_payload.json"
    monai_prompts_path.write_text(json.dumps(monai_prompts, indent=2, ensure_ascii=False), encoding="utf-8")
    vista_prompts_path = target_dir / "vista3d_prompt_payload.json"
    vista_prompts_path.write_text(json.dumps(vista_prompts, indent=2, ensure_ascii=False), encoding="utf-8")

    instructions_path = target_dir / "REFINEMENT_NOTES.txt"
    instructions_path.write_text(_build_refinement_notes(checklist), encoding="utf-8")

    return {
        "directory": str(target_dir),
        "checklistPath": str(checklist_path),
        "promptTemplatesPath": str(prompts_path),
        "monaiPromptPath": str(monai_prompts_path),
        "vistaPromptPath": str(vista_prompts_path),
        "notesPath": str(instructions_path),
    }


def build_refinement_checklist(result: Dict[str, object]) -> List[Dict[str, str]]:
    rows: List[Dict[str, str]] = []
    for finding in result.get("qualityChecks") or []:
        rows.append(
            {
                "title": finding.get("code", "qc_item"),
                "priority": str(finding.get("level", "info")),
                "details": str(finding.get("message", "")),
            }
        )
    report = result.get("sinusReport") or result.get("mriReport") or {}
    for finding in (report.get("findingRows") or [])[:8]:
        rows.append(
            {
                "title": str(finding.get("structure", "finding")),
                "priority": str(finding.get("status", "info")),
                "details": str(finding.get("details", "")),
            }
        )
    if not rows:
        rows.append(
            {
                "title": "general_review",
                "priority": "info",
                "details": "Review boundaries on the active slice planes and correct the most clinically important structures first.",
            }
        )
    return rows


def build_prompt_templates(result: Dict[str, object]) -> Dict[str, object]:
    report = result.get("sinusReport") or result.get("mriReport") or {}
    measurements = result.get("measurements") or []
    targets = []
    for finding in report.get("findingRows") or []:
        structure = str(finding.get("structure", "")).strip()
        if structure:
            related_segments = _find_related_segments(structure, measurements)
            targets.append(
                {
                    "name": structure,
                    "target": structure,
                    "relatedSegments": related_segments,
                    "positivePoints": [],
                    "negativePoints": [],
                    "boxes": [],
                    "notes": str(finding.get("details", "")),
                }
            )
    if not targets:
        targets.append(
            {
                "name": "region_of_interest",
                "target": "region_of_interest",
                "relatedSegments": [],
                "positivePoints": [],
                "negativePoints": [],
                "boxes": [],
                "notes": "Fill with interactive prompts for MONAI Label / VISTA3D / nnInteractive correction.",
            }
        )
    return {
        "case": result.get("volumeName"),
        "preset": result.get("preset"),
        "targets": targets,
    }


def build_monailabel_prompt_payload(result: Dict[str, object]) -> Dict[str, object]:
    generic = build_prompt_templates(result)
    return {
        "case": generic.get("case"),
        "preset": generic.get("preset"),
        "prompts": [
            {
                "label": row.get("name"),
                "foreground": row.get("positivePoints", []),
                "background": row.get("negativePoints", []),
                "boxes": row.get("boxes", []),
                "related_segments": row.get("relatedSegments", []),
                "notes": row.get("notes", ""),
            }
            for row in generic.get("targets", [])
        ],
    }


def build_vista3d_prompt_payload(result: Dict[str, object]) -> Dict[str, object]:
    generic = build_prompt_templates(result)
    return {
        "case": generic.get("case"),
        "targets": [
            {
                "name": row.get("name"),
                "positive_points_ijk": row.get("positivePoints", []),
                "negative_points_ijk": row.get("negativePoints", []),
                "bounding_box_ijk": row.get("boxes", []),
                "related_segments": row.get("relatedSegments", []),
                "notes": row.get("notes", ""),
            }
            for row in generic.get("targets", [])
        ],
    }


def _find_related_segments(structure: str, measurements: List[Dict[str, object]]) -> List[str]:
    structure_key = structure.lower()
    matches: List[str] = []
    for row in measurements:
        segment_name = str(row.get("segment", ""))
        source_segment = str(row.get("sourceSegment", ""))
        haystack = f"{segment_name} {source_segment}".lower()
        if structure_key in haystack or haystack.replace("_", " ").find(structure_key.replace("_", " ")) >= 0:
            matches.append(segment_name)
    if matches:
        return sorted(set(matches))
    token_matches = []
    for row in measurements:
        segment_name = str(row.get("segment", ""))
        if any(token for token in structure_key.replace("_", " ").split() if token and token in segment_name.lower()):
            token_matches.append(segment_name)
    return sorted(set(token_matches))[:5]


def _build_refinement_notes(checklist: List[Dict[str, str]]) -> str:
    lines = [
        "ENT Assistant v3 interactive refinement notes",
        "",
        "Suggested workflow:",
        "1. Review the highest-priority QC items first.",
        "2. Correct segmentation boundaries in Segment Editor or an external interactive tool.",
        "3. Recompute the report from the refined segmentation.",
        "",
        "Checklist:",
    ]
    for row in checklist:
        lines.append(f"- {row['title']} [{row['priority']}]: {row['details']}")
    return "\n".join(lines)


def _set_active_volume(volume_node) -> None:
    selection_node = slicer.app.applicationLogic().GetSelectionNode()
    selection_node.SetReferenceActiveVolumeID(volume_node.GetID())
    slicer.app.applicationLogic().PropagateVolumeSelection()


def _show_segmentation_for_editing(segmentation_node) -> None:
    display_node = segmentation_node.GetDisplayNode()
    if not display_node:
        return
    display_node.SetVisibility3D(False)
    if hasattr(display_node, "SetVisibility2DFill"):
        display_node.SetVisibility2DFill(True)
    if hasattr(display_node, "SetVisibility2DOutline"):
        display_node.SetVisibility2DOutline(True)
    if hasattr(display_node, "SetOpacity2DFill"):
        display_node.SetOpacity2DFill(0.25)
    if hasattr(display_node, "SetOpacity2DOutline"):
        display_node.SetOpacity2DOutline(1.0)


def _open_segment_editor(volume_node, segmentation_node) -> None:
    try:
        slicer.util.selectModule("SegmentEditor")
    except Exception:
        # Headless or reduced UI sessions may not expose the main window.
        pass
    editor_widget_container = getattr(slicer.modules, "SegmentEditorWidget", None)
    editor_widget = getattr(editor_widget_container, "editor", None) if editor_widget_container else None
    if editor_widget:
        editor_widget.setSegmentationNode(segmentation_node)
        editor_widget.setSourceVolumeNode(volume_node)
