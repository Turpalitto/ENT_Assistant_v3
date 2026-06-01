from __future__ import annotations

from typing import Dict, Optional

import slicer


SEGMENT_STYLE_RULES = {
    "skull": {"color": (0.88, 0.78, 0.64), "opacity3d": 0.12},
    "mandible": {"color": (0.94, 0.82, 0.70), "opacity3d": 0.18},
    "sinus_maxillary": {"color": (0.15, 0.65, 0.95), "opacity3d": 0.55},
    "sinus_frontal": {"color": (0.12, 0.78, 0.68), "opacity3d": 0.55},
    "sinus_ethmoid": {"color": (0.35, 0.85, 0.55), "opacity3d": 0.50},
    "sinus_sphenoid": {"color": (0.05, 0.55, 0.80), "opacity3d": 0.58},
    "nasal_cavity": {"color": (1.00, 0.72, 0.20), "opacity3d": 0.45},
    "ostiomeatal_complex": {"color": (1.00, 0.35, 0.10), "opacity3d": 0.80},
    "nasal_septum": {"color": (0.95, 0.90, 0.78), "opacity3d": 0.35},
    "concha_bullosa": {"color": (0.92, 0.48, 0.18), "opacity3d": 0.70},
    "parotid_gland": {"color": (0.85, 0.40, 0.55), "opacity3d": 0.35},
    "submandibular_gland": {"color": (0.78, 0.35, 0.50), "opacity3d": 0.35},
    "larynx_air": {"color": (0.15, 0.80, 1.00), "opacity3d": 0.60},
}


def prepare_ct_volume_rendering(volume_node, preset_name: str = "CT-Bone", shift: Optional[float] = None) -> Dict[str, object]:
    logic = slicer.modules.volumerendering.logic()
    display_node = logic.GetFirstVolumeRenderingDisplayNode(volume_node)
    if not display_node:
        display_node = logic.CreateDefaultVolumeRenderingNodes(volume_node)
    preset = logic.GetPresetByName(preset_name)
    if preset:
        display_node.GetVolumePropertyNode().Copy(preset)
    display_node.SetVisibility(True)
    display_node.SetCroppingEnabled(False)
    volume_property = display_node.GetVolumePropertyNode().GetVolumeProperty()
    if shift is not None:
        scalar_opacity = volume_property.GetScalarOpacity()
        for index in range(scalar_opacity.GetSize()):
            node = [0.0, 0.0, 0.0, 0.0]
            scalar_opacity.GetNodeValue(index, node)
            node[0] = float(node[0]) + float(shift)
            scalar_opacity.SetNodeValue(index, node)
    return {"displayNodeId": display_node.GetID(), "preset": preset_name}


def style_segmentation_for_sinus_view(segmentation_node, mode: str = "sinus") -> Dict[str, object]:
    display_node = segmentation_node.GetDisplayNode()
    if not display_node:
        segmentation_node.CreateDefaultDisplayNodes()
        display_node = segmentation_node.GetDisplayNode()
    display_node.SetVisibility3D(True)
    display_node.SetVisibility2D(True)
    display_node.SetOpacity3D(0.6)
    segmentation = segmentation_node.GetSegmentation()
    styled = []
    for index in range(segmentation.GetNumberOfSegments()):
        segment_id = segmentation.GetNthSegmentID(index)
        segment = segmentation.GetSegment(segment_id)
        segment_name = segment.GetName()
        style = _resolve_style(segment_name, mode)
        if style.get("color"):
            segment.SetColor(*style["color"])
        if style.get("opacity3d") is not None:
            display_node.SetSegmentOpacity3D(segment_id, style["opacity3d"])
        if style.get("opacity2d_fill") is not None:
            display_node.SetSegmentOpacity2DFill(segment_id, style["opacity2d_fill"])
        if style.get("opacity2d_outline") is not None:
            display_node.SetSegmentOpacity2DOutline(segment_id, style["opacity2d_outline"])
        styled.append({"segment": segment_name, "style": style})
    return {"styledSegments": styled}


def prepare_sinus_3d_scene(volume_node, segmentation_node=None) -> Dict[str, object]:
    rendering = prepare_ct_volume_rendering(volume_node, preset_name="CT-Bone", shift=-150)
    styling = style_segmentation_for_sinus_view(segmentation_node, mode="sinus") if segmentation_node else None
    _center_views(volume_node)
    return {"rendering": rendering, "styling": styling}


def prepare_internal_head_view(volume_node, segmentation_node=None) -> Dict[str, object]:
    rendering = prepare_ct_volume_rendering(volume_node, preset_name="CT-Air", shift=50)
    styling = style_segmentation_for_sinus_view(segmentation_node, mode="internal") if segmentation_node else None
    _center_views(volume_node)
    return {"rendering": rendering, "styling": styling}


def prepare_surgical_focus_view(volume_node, segmentation_node=None) -> Dict[str, object]:
    rendering = prepare_ct_volume_rendering(volume_node, preset_name="CT-Bone", shift=-250)
    styling = style_segmentation_for_sinus_view(segmentation_node, mode="surgical") if segmentation_node else None
    _center_views(volume_node)
    return {"rendering": rendering, "styling": styling}


def _resolve_style(segment_name: str, mode: str) -> Dict[str, object]:
    normalized = segment_name.lower()
    matched = {"opacity2d_fill": 0.35, "opacity2d_outline": 1.0}
    for key, style in SEGMENT_STYLE_RULES.items():
        if key in normalized:
            matched.update(style)
            break
    if mode == "internal" and ("skull" in normalized or "mandible" in normalized):
        matched["opacity3d"] = 0.06
    if mode == "surgical" and "ostiomeatal_complex" in normalized:
        matched["opacity3d"] = 0.95
    if mode == "surgical" and "nasal_septum" in normalized:
        matched["opacity3d"] = 0.55
    return matched


def _center_views(volume_node) -> None:
    selection_node = slicer.app.applicationLogic().GetSelectionNode()
    selection_node.SetReferenceActiveVolumeID(volume_node.GetID())
    slicer.app.applicationLogic().PropagateVolumeSelection()
    slicer.util.resetSliceViews()
    layout_manager = slicer.app.layoutManager()
    if layout_manager and layout_manager.threeDWidget(0):
        layout_manager.threeDWidget(0).threeDView().resetFocalPoint()
