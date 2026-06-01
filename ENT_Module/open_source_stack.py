from __future__ import annotations

import shutil
from typing import Dict, List

import slicer


OPEN_SOURCE_COMPONENTS = [
    {
        "name": "TotalSegmentator",
        "type": "cli",
        "check": lambda: shutil.which("TotalSegmentator") or shutil.which("totalsegmentator"),
        "purpose": "Automatic segmentation of head, neck and craniofacial structures from CT.",
        "source": "https://github.com/wasserth/totalsegmentator",
    },
    {
        "name": "SlicerTotalSegmentator",
        "type": "module",
        "check": lambda: hasattr(slicer.modules, "totalsegmentator"),
        "purpose": "3D Slicer extension wrapper around TotalSegmentator.",
        "source": "https://github.com/lassoan/SlicerTotalSegmentator",
    },
    {
        "name": "SegmentEditorExtraEffects",
        "type": "module",
        "check": lambda: hasattr(slicer.modules, "segmenteditorextraeffects"),
        "purpose": "Adds Local Threshold, Watershed and other advanced segmentation tools.",
        "source": "https://github.com/lassoan/SlicerSegmentEditorExtraEffects",
    },
    {
        "name": "MONAI Label",
        "type": "module",
        "check": lambda: hasattr(slicer.modules, "monailabel"),
        "purpose": "Interactive AI-assisted medical image labeling and segmentation workflows.",
        "source": "https://github.com/Project-MONAI/MONAILabel",
    },
    {
        "name": "SlicerNNInteractive",
        "type": "module",
        "check": lambda: hasattr(slicer.modules, "nninteractive"),
        "purpose": "Prompt-based interactive segmentation with points, boxes and scribbles.",
        "source": "https://github.com/coendevente/SlicerNNInteractive",
    },
    {
        "name": "CloudSegmentatorResults reference",
        "type": "reference",
        "check": lambda: True,
        "purpose": "Rule-based QC inspiration for suspicious AI segmentation outputs and volumetric sanity checks.",
        "source": "https://github.com/ImagingDataCommons/CloudSegmentatorResults",
    },
    {
        "name": "Slicer export workflow reference",
        "type": "reference",
        "check": lambda: True,
        "purpose": "Reference for segmentation export to labelmaps and closed-surface formats.",
        "source": "https://github.com/Slicer/Slicer/blob/main/Docs/user_guide/data_loading_and_saving.md",
    },
]


def inspect_open_source_stack() -> Dict[str, object]:
    rows: List[Dict[str, object]] = []
    lines = ["Open-source stack readiness:"]
    for component in OPEN_SOURCE_COMPONENTS:
        available = bool(component["check"]())
        rows.append(
            {
                "name": component["name"],
                "available": available,
                "purpose": component["purpose"],
                "source": component["source"],
            }
        )
        status = "OK" if available else "MISSING"
        lines.append(f"- {component['name']}: {status} | {component['purpose']}")

    lines.append("")
    lines.append("Recommended minimum stack for this project:")
    lines.append("- TotalSegmentator for automatic ENT/head segmentation")
    lines.append("- SegmentEditorExtraEffects for local refinement in Slicer")
    lines.append("- MONAI Label or SlicerNNInteractive for interactive annotation workflows")
    lines.append("- Slicer export workflow for .seg.nrrd, labelmaps and surface models")

    return {"components": rows, "summary": "\n".join(lines)}
