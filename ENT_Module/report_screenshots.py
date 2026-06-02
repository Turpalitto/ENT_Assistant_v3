from __future__ import annotations

from pathlib import Path
from typing import Dict, List

import slicer

from ENT_Module import sinus_visualization


def capture_report_screenshots(
    volume_node,
    segmentation_node,
    target_dir: str,
    report_kind: str = "sinus_ct",
) -> List[Dict[str, str]]:
    directory = Path(target_dir)
    directory.mkdir(parents=True, exist_ok=True)
    results: List[Dict[str, str]] = []
    if report_kind == "mri_ent":
        plans = [
            ("red_slice", None, lambda path: _grab_slice("Red", path)),
            ("green_slice", None, lambda path: _grab_slice("Green", path)),
            ("yellow_slice", None, lambda path: _grab_slice("Yellow", path)),
        ]
    else:
        plans = [
            ("sinus_3d", sinus_visualization.prepare_sinus_3d_scene, _grab_3d_view),
            ("internal_head", sinus_visualization.prepare_internal_head_view, _grab_3d_view),
            ("fess_planning", sinus_visualization.prepare_surgical_focus_view, _grab_3d_view),
            ("red_slice", None, lambda path: _grab_slice("Red", path)),
            ("green_slice", None, lambda path: _grab_slice("Green", path)),
            ("yellow_slice", None, lambda path: _grab_slice("Yellow", path)),
        ]
    for key, prepare_fn, grab_fn in plans:
        if prepare_fn:
            prepare_fn(volume_node, segmentation_node)
        file_path = directory / f"{key}.png"
        if grab_fn(str(file_path)):
            results.append({"key": key, "path": str(file_path)})
    return results


def _grab_3d_view(path: str) -> bool:
    layout_manager = slicer.app.layoutManager()
    if not layout_manager or not layout_manager.threeDWidget(0):
        return False
    pixmap = layout_manager.threeDWidget(0).threeDView().grab()
    return bool(pixmap and pixmap.save(path))


def _grab_slice(slice_name: str, path: str) -> bool:
    layout_manager = slicer.app.layoutManager()
    if not layout_manager:
        return False
    slice_widget = layout_manager.sliceWidget(slice_name)
    if not slice_widget:
        return False
    pixmap = slice_widget.grab()
    return bool(pixmap and pixmap.save(path))
