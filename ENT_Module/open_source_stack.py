from __future__ import annotations

import importlib
import subprocess
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
        "name": "MONAI",
        "type": "python",
        "check": lambda: _can_import("monai"),
        "purpose": "Deep-learning transforms, inferers and medical imaging building blocks for local AI pipelines.",
        "source": "https://github.com/project-monai/monai",
    },
    {
        "name": "MONAI Label CLI",
        "type": "cli",
        "check": lambda: shutil.which("monailabel"),
        "purpose": "Local MONAI Label server/runtime for custom sinus segmentation apps and iterative annotation.",
        "source": "https://github.com/Project-MONAI/MONAILabel",
    },
    {
        "name": "SlicerMONAIViz",
        "type": "module",
        "check": lambda: hasattr(slicer.modules, "monaiviz"),
        "purpose": "MONAI-centric 3D Slicer workflows for AI visualization and model experimentation.",
        "source": "https://github.com/Project-MONAI/SlicerMONAIViz",
    },
    {
        "name": "nnU-Net v2",
        "type": "cli",
        "check": lambda: shutil.which("nnUNetv2_predict"),
        "purpose": "Open-source training and inference backbone for custom sinus CT segmentation models.",
        "source": "https://github.com/MIC-DKFZ/nnUNet",
    },
    {
        "name": "SlicerNNInteractive",
        "type": "module",
        "check": lambda: hasattr(slicer.modules, "nninteractive"),
        "purpose": "Prompt-based interactive segmentation with points, boxes and scribbles.",
        "source": "https://github.com/coendevente/SlicerNNInteractive",
    },
    {
        "name": "SlicerRT",
        "type": "module",
        "check": lambda: hasattr(slicer.modules, "dicomrtimportexport") or hasattr(slicer.modules, "beams"),
        "purpose": "DICOM RT import/export and contour analysis toolkit for 3D Slicer.",
        "source": "https://github.com/SlicerRt/SlicerRT",
    },
    {
        "name": "SlicerVMTK",
        "type": "module",
        "check": lambda: hasattr(slicer.modules, "crosssectionanalysis") or hasattr(slicer.modules, "extractcenterline"),
        "purpose": "Open-source vascular/tubular analysis toolkit useful for advanced centerline-style workflows.",
        "source": "https://github.com/vmtk/SlicerExtension-VMTK",
    },
    {
        "name": "Endoscopy",
        "type": "module",
        "check": lambda: hasattr(slicer.modules, "endoscopy"),
        "purpose": "3D Slicer module for virtual endoscopy-style camera navigation along paths.",
        "source": "https://www.slicer.org/",
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


def _can_import(module_name: str) -> bool:
    try:
        importlib.import_module(module_name)
        return True
    except Exception:
        return False


def _runtime_profile() -> Dict[str, object]:
    profile: Dict[str, object] = {
        "torch": {"available": False, "version": None, "cuda": False},
        "monai": {"available": False, "version": None},
        "simpleitk": {"available": False, "version": None},
        "gpu": {"available": False, "name": None, "memoryMb": None},
    }
    try:
        torch = importlib.import_module("torch")
        profile["torch"] = {
            "available": True,
            "version": getattr(torch, "__version__", None),
            "cuda": bool(getattr(torch, "cuda", None) and torch.cuda.is_available()),
        }
    except Exception:
        pass
    try:
        monai = importlib.import_module("monai")
        profile["monai"] = {
            "available": True,
            "version": getattr(monai, "__version__", None),
        }
    except Exception:
        pass
    try:
        sitk = importlib.import_module("SimpleITK")
        profile["simpleitk"] = {
            "available": True,
            "version": getattr(sitk, "__version__", None),
        }
    except Exception:
        pass
    nvidia_smi = shutil.which("nvidia-smi")
    if nvidia_smi:
        try:
            result = subprocess.run(
                [
                    nvidia_smi,
                    "--query-gpu=name,memory.total",
                    "--format=csv,noheader,nounits",
                ],
                capture_output=True,
                text=True,
                check=False,
                timeout=5,
            )
            line = (result.stdout or "").strip().splitlines()[0] if (result.stdout or "").strip() else ""
            if line:
                name, memory_mb = [part.strip() for part in line.split(",", 1)]
                profile["gpu"] = {
                    "available": True,
                    "name": name,
                    "memoryMb": int(memory_mb) if memory_mb.isdigit() else None,
                }
        except Exception:
            pass
    return profile


def inspect_open_source_stack() -> Dict[str, object]:
    rows: List[Dict[str, object]] = []
    runtime = _runtime_profile()
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
    lines.append("Local runtime profile:")
    torch_state = runtime["torch"]
    monai_state = runtime["monai"]
    sitk_state = runtime["simpleitk"]
    gpu_state = runtime["gpu"]
    lines.append(
        f"- Torch in Slicer Python: {'OK' if torch_state['available'] else 'MISSING'}"
        f" | version={torch_state['version'] or 'n/a'} | CUDA={'yes' if torch_state['cuda'] else 'no'}"
    )
    lines.append(f"- MONAI in Slicer Python: {'OK' if monai_state['available'] else 'MISSING'} | version={monai_state['version'] or 'n/a'}")
    lines.append(f"- SimpleITK in Slicer Python: {'OK' if sitk_state['available'] else 'MISSING'} | version={sitk_state['version'] or 'n/a'}")
    if gpu_state["available"]:
        lines.append(f"- NVIDIA GPU: {gpu_state['name']} | VRAM ~{gpu_state['memoryMb']} MB")
    else:
        lines.append("- NVIDIA GPU: not detected through nvidia-smi")

    lines.append("")
    lines.append("Recommended minimum stack for this project:")
    lines.append("- TotalSegmentator for baseline ENT/head segmentation and sinus cavity bootstrapping")
    lines.append("- SegmentEditorExtraEffects for local refinement in Slicer")
    lines.append("- MONAI Label and/or nnU-Net v2 for custom sinus CT segmentation workflows")
    lines.append("- SlicerNNInteractive for rapid correction of anatomy/pathology masks")
    lines.append("- Endoscopy and/or SlicerVMTK for advanced navigation or tubular-analysis workflows when needed")
    lines.append("- Slicer export workflow for .seg.nrrd, labelmaps and surface models")
    lines.append("- SlicerRT for DICOM RT readiness and contour comparison/export workflows")
    lines.append("")
    lines.append("Backend guidance for this workstation:")
    if gpu_state["available"] and (gpu_state.get("memoryMb") or 0) >= 10000:
        lines.append("- This GPU is strong enough for local TotalSegmentator, nnU-Net inference and MONAI Label server workflows.")
    else:
        lines.append("- Prefer lighter CPU-compatible workflows or external GPU environments for heavier AI backends.")
    if torch_state["available"] and not torch_state["cuda"]:
        lines.append("- Current Slicer Python torch build is CPU-only, so GPU MONAI pipelines should run from an external Python environment.")
    if not monai_state["available"]:
        lines.append("- MONAI is not installed in Slicer Python yet; keep MONAI integration optional unless you prepare a dedicated environment.")

    return {"components": rows, "runtime": runtime, "summary": "\n".join(lines)}
