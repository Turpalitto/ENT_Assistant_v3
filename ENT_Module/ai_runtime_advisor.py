from __future__ import annotations

import json
import os
import shutil
import subprocess
from pathlib import Path
from typing import Dict, List, Optional


def inspect_local_ai_runtimes() -> Dict[str, object]:
    gpu = _inspect_gpu()
    external_envs = detect_external_envs()
    tools = {
        "TotalSegmentator": _which("TotalSegmentator") or _which("totalsegmentator"),
        "monailabel": _which("monailabel"),
        "nnUNetv2_predict": _which("nnUNetv2_predict"),
        "nnUNet_predict": _which("nnUNet_predict"),
        "python": _probe_python(),
        "PythonSlicer": _which("PythonSlicer"),
    }
    resolved_tools = resolve_tools_with_envs(tools, external_envs)

    preferred_ct_backend = "threshold"
    if resolved_tools["TotalSegmentator"]:
        preferred_ct_backend = "TotalSegmentator"
    elif resolved_tools["nnUNetv2_predict"] or resolved_tools["nnUNet_predict"]:
        preferred_ct_backend = "nnU-Net"

    interactive_backend = "SegmentEditorExtraEffects / manual refinement"
    if resolved_tools["monailabel"]:
        interactive_backend = "MONAI Label"

    workspace_recommendation = build_workspace_recommendation(
        gpu=gpu,
        tools=resolved_tools,
        preferred_ct_backend=preferred_ct_backend,
        interactive_backend=interactive_backend,
    )
    framework_fit = build_framework_fit_report(gpu=gpu, tools=resolved_tools)

    lines = ["AI runtime advisor:"]
    lines.append(f"- Preferred CT backend: {preferred_ct_backend}")
    lines.append(f"- Preferred interactive refinement path: {interactive_backend}")
    if gpu.get("available"):
        lines.append(f"- GPU: {gpu.get('name')} | VRAM ~{gpu.get('memoryMb')} MB | CUDA {gpu.get('cudaVersion') or 'n/a'}")
    else:
        lines.append("- GPU: not detected through nvidia-smi")
    for tool_name, tool_value in resolved_tools.items():
        lines.append(f"- {tool_name}: {'OK' if tool_value else 'MISSING'}{f' | {tool_value}' if tool_value else ''}")
    if external_envs:
        lines.append("")
        lines.append("Detected external AI environments:")
        for env_row in external_envs:
            lines.append(f"- {env_row['name']}: {env_row['python']} | tools={', '.join(env_row['availableTools']) or 'none'}")
    lines.append("")
    lines.append("Framework fit for this workstation:")
    for row in framework_fit:
        lines.append(f"- {row['project']}: {row['status']} | {row['summary']}")
    lines.append("")
    lines.extend(f"- {row}" for row in workspace_recommendation)

    return {
        "gpu": gpu,
        "tools": resolved_tools,
        "pathTools": tools,
        "externalEnvs": external_envs,
        "preferredCtBackend": preferred_ct_backend,
        "interactiveBackend": interactive_backend,
        "frameworkFit": framework_fit,
        "recommendations": workspace_recommendation,
        "summary": "\n".join(lines),
    }


def build_workspace_recommendation(
    *,
    gpu: Dict[str, object],
    tools: Dict[str, Optional[str]],
    preferred_ct_backend: str,
    interactive_backend: str,
) -> List[str]:
    lines: List[str] = []
    if preferred_ct_backend == "TotalSegmentator":
        lines.append("Use TotalSegmentator as the first-line automatic CT anatomy backend inside the current workflow.")
    elif preferred_ct_backend == "nnU-Net":
        lines.append("Use nnU-Net for local sinus-focused inference if a trained model and environment are available.")
    else:
        lines.append("Keep threshold/rule-based fallback as the immediate baseline until a stronger local backend is installed.")

    if interactive_backend == "MONAI Label":
        lines.append("MONAI Label CLI is available, so interactive annotation or iterative correction can be attached to exported workspaces.")
    else:
        lines.append("Prepare exported image/label bundles now, and add MONAI Label later without changing the Slicer reporting workflow.")

    if gpu.get("available") and (gpu.get("memoryMb") or 0) >= 10000:
        lines.append("This workstation is suitable for GPU-backed TotalSegmentator, MONAI Label apps, and nnU-Net inference in an external Python environment.")
    else:
        lines.append("Prefer CPU-safe or lighter workflows on this workstation until a larger GPU runtime is available.")

    if not tools.get("python"):
        lines.append("No standalone Python runtime was detected from PATH, so external MONAI/nnU-Net setup will need an explicit Python/conda installation.")
    return lines


def build_framework_fit_report(*, gpu: Dict[str, object], tools: Dict[str, Optional[str]]) -> List[Dict[str, str]]:
    gpu_memory = int(gpu.get("memoryMb") or 0)
    has_gpu = bool(gpu.get("available"))
    has_external_python = bool(tools.get("python"))
    has_totalseg = bool(tools.get("TotalSegmentator"))
    has_monailabel = bool(tools.get("monailabel"))
    has_nnunet = bool(tools.get("nnUNetv2_predict") or tools.get("nnUNet_predict"))

    rows: List[Dict[str, str]] = [
        {
            "project": "MONAI",
            "status": "setup_needed" if not has_external_python else "ready_for_env",
            "summary": "Core medical imaging AI framework; practical here after preparing an external Python environment.",
        },
        {
            "project": "nnU-Net",
            "status": "ready" if has_nnunet else "setup_needed",
            "summary": "Strong open-source segmentation backbone; your GPU is sufficient for inference once the environment/model are prepared.",
        },
        {
            "project": "TotalSegmentator",
            "status": "ready" if has_totalseg else "setup_needed",
            "summary": "Very suitable for your CT workflow and hardware; already the best immediate automatic CT anatomy backend here.",
        },
        {
            "project": "3D Slicer",
            "status": "ready",
            "summary": "Already fits your workstation well and remains the main interactive workstation for CT/MRI review.",
        },
        {
            "project": "MONAI Label",
            "status": "ready" if has_monailabel else "setup_needed",
            "summary": "Good fit for interactive AI labeling with Slicer once a local server/app environment is installed.",
        },
        {
            "project": "VISTA3D",
            "status": "setup_needed" if has_gpu and gpu_memory >= 10000 else "limited",
            "summary": "Potentially feasible on your GPU in an external MONAI environment, but not something to hard-wire into Slicer Python right now.",
        },
        {
            "project": "OHIF Viewer",
            "status": "ready",
            "summary": "Fits your PC easily as a browser-based DICOM viewer; useful mainly as a separate web viewer/integration target.",
        },
        {
            "project": "ITK-SNAP",
            "status": "ready",
            "summary": "Lightweight and well-suited for manual or semi-automatic correction workflows on your machine.",
        },
        {
            "project": "Merlin",
            "status": "limited",
            "summary": "Interesting CT VLM research direction, but not the best immediate local fit for this ENT/Slicer workflow without a dedicated Python/model setup.",
        },
        {
            "project": "ATOMMIC",
            "status": "setup_needed" if has_gpu and has_external_python else "limited",
            "summary": "MRI-focused reconstruction/segmentation toolbox; relevant for advanced MRI research workflows rather than immediate Slicer deployment.",
        },
    ]
    return rows


def detect_external_envs() -> List[Dict[str, object]]:
    candidates: List[Path] = []
    home = Path.home()
    for name in ["ent_ai_env", ".venv", "venv", "monai_env", "nnunet_env"]:
        candidates.append(home / name)
        candidates.append(Path("C:/entv1") / name)
    seen = set()
    envs: List[Dict[str, object]] = []
    for env_dir in candidates:
        env_dir = env_dir.resolve()
        if env_dir in seen:
            continue
        seen.add(env_dir)
        python_exe = env_dir / "Scripts" / "python.exe"
        if not python_exe.exists():
            continue
        envs.append(_inspect_env(env_dir, python_exe))
    return envs


def resolve_tools_with_envs(tools: Dict[str, Optional[str]], envs: List[Dict[str, object]]) -> Dict[str, Optional[str]]:
    resolved = dict(tools)
    for env in envs:
        scripts_dir = str(Path(env["python"]).parent)
        mapping = {
            "TotalSegmentator": str(Path(scripts_dir) / "TotalSegmentator.exe"),
            "monailabel": str(Path(scripts_dir) / "monailabel.exe"),
            "nnUNetv2_predict": str(Path(scripts_dir) / "nnUNetv2_predict.exe"),
            "nnUNet_predict": str(Path(scripts_dir) / "nnUNet_predict.exe"),
        }
        for key, candidate in mapping.items():
            if not resolved.get(key) and Path(candidate).exists():
                resolved[key] = candidate
        if not resolved.get("python"):
            resolved["python"] = env["python"]
    return resolved


def write_ai_workspace_bundle(
    target_directory: str,
    *,
    case_name: str,
    modality: str,
    study_info: Dict[str, object],
    report_result: Dict[str, object],
    image_path: Optional[str] = None,
    segmentation_path: Optional[str] = None,
    labelmap_path: Optional[str] = None,
    nnunet_artifacts: Optional[Dict[str, object]] = None,
) -> Dict[str, object]:
    target_dir = Path(target_directory)
    target_dir.mkdir(parents=True, exist_ok=True)

    runtime = inspect_local_ai_runtimes()
    commands = _build_command_templates(case_name, modality, runtime)
    payload = {
        "caseName": case_name,
        "modality": modality,
        "studyInfo": study_info,
        "runtimeAdvisor": runtime,
        "reportSummary": {
            "reportPath": report_result.get("reportPath"),
            "htmlReportPath": report_result.get("htmlReportPath"),
            "preset": report_result.get("preset"),
        },
        "artifacts": {
            "image": image_path,
            "segmentation": segmentation_path,
            "labelmap": labelmap_path,
            "nnunetImageTest": (nnunet_artifacts or {}).get("imageTestPath"),
            "nnunetLabelTest": (nnunet_artifacts or {}).get("labelTestPath"),
            "nnunetDatasetJson": (nnunet_artifacts or {}).get("datasetJsonPath"),
        },
        "commandTemplates": commands,
    }

    manifest_path = target_dir / "ai_workspace_manifest.json"
    manifest_path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
    readme_path = target_dir / "README_AI_WORKSPACE.txt"
    readme_path.write_text(_build_workspace_readme(payload), encoding="utf-8")
    for command_name, command_text in commands.items():
        if command_text:
            (target_dir / f"{command_name}.cmd").write_text(command_text + "\n", encoding="utf-8")

    return {
        "manifestPath": str(manifest_path),
        "readmePath": str(readme_path),
        "commands": commands,
    }


def build_nnunet_dataset_stub(case_name: str, modality: str, *, has_labels: bool) -> Dict[str, object]:
    channel_name = "CT" if str(modality).upper() == "CT" else "MRI"
    return {
        "name": "ENTAssistantWorkspace",
        "description": "Auto-generated nnU-Net style workspace exported from ENT Assistant v3",
        "tensorImageSize": "3D",
        "reference": "https://github.com/MIC-DKFZ/nnUNet",
        "licence": "research",
        "release": "1.0",
        "channel_names": {"0": channel_name},
        "labels": {
            "background": 0,
            "label_1": 1,
        },
        "numTraining": 1 if has_labels else 0,
        "file_ending": ".nii.gz",
        "cases": [_sanitize_name(case_name)],
    }


def _build_workspace_readme(payload: Dict[str, object]) -> str:
    artifacts = payload.get("artifacts") or {}
    runtime = payload.get("runtimeAdvisor") or {}
    lines = [
        "ENT Assistant v3 - AI workspace bundle",
        "",
        f"Case: {payload.get('caseName')}",
        f"Modality: {payload.get('modality') or 'unknown'}",
        "",
        "Artifacts:",
        f"- image: {artifacts.get('image') or 'missing'}",
        f"- segmentation: {artifacts.get('segmentation') or 'missing'}",
        f"- labelmap: {artifacts.get('labelmap') or 'missing'}",
        "",
        "Runtime recommendations:",
    ]
    for row in runtime.get("recommendations") or []:
        lines.append(f"- {row}")
    lines.extend(
        [
            "",
            "Starter command files are included as .cmd templates.",
            "Edit environment paths/model paths as needed before running them.",
        ]
    )
    return "\n".join(lines)


def _build_command_templates(case_name: str, modality: str, runtime: Dict[str, object]) -> Dict[str, str]:
    safe_case = _sanitize_name(case_name)
    tools = runtime.get("tools") or {}
    image_name = "image.nii.gz"
    label_name = "labelmap.nii.gz"
    commands: Dict[str, str] = {}

    if tools.get("monailabel"):
        commands["run_monailabel_example"] = (
            "@echo off\n"
            "REM Edit the app path and studies path before running.\n"
            "set APP_DIR=%CD%\\monailabel_app\n"
            "set STUDIES=%CD%\n"
            f"\"{tools['monailabel']}\" start_server --app %%APP_DIR%% --studies %%STUDIES%% --conf models {safe_case}\n"
        )
    else:
        commands["run_monailabel_example"] = (
            "@echo off\n"
            "REM MONAI Label CLI was not detected. Install it in an external Python environment first.\n"
            "REM Expected workspace image: image.nii.gz\n"
        )

    totalseg_binary = tools.get("TotalSegmentator")
    if totalseg_binary:
        commands["run_totalsegmentator_example"] = (
            "@echo off\n"
            "REM Edit the --task flag as needed. Good ENT-oriented examples: craniofacial_structures, head_glands_cavities, headneck_bones_vessels.\n"
            f"\"{totalseg_binary}\" -i %CD%\\{image_name} -o %CD%\\totalseg_output --task craniofacial_structures --fast\n"
        )
    else:
        commands["run_totalsegmentator_example"] = (
            "@echo off\n"
            "REM TotalSegmentator CLI was not detected. Install it in an external Python environment first.\n"
            "REM Expected workspace image: image.nii.gz\n"
        )

    nnunet_binary = tools.get("nnUNetv2_predict") or tools.get("nnUNet_predict")
    if nnunet_binary:
        commands["run_nnunet_inference_example"] = (
            "@echo off\n"
            "REM Point -i to nnunet_workspace\\imagesTs and edit model/trainer/folds as needed.\n"
            f"\"{nnunet_binary}\" -i %CD%\\nnunet_workspace\\imagesTs -o %CD%\\nnunet_prediction -f all\n"
        )
    else:
        commands["run_nnunet_inference_example"] = (
            "@echo off\n"
            "REM nnU-Net CLI was not detected. Install nnUNetv2_predict in an external Python environment first.\n"
            f"REM Expected input image: {image_name}\n"
            f"REM Optional ground-truth labelmap: {label_name}\n"
        )

    if tools.get("python"):
        commands["run_vista3d_example"] = (
            "@echo off\n"
            "REM Prepare a dedicated external MONAI/VISTA3D environment first.\n"
            "REM The vista3d_workspace folder contains image, optional labelmap, and interactive prompt templates.\n"
            f"\"{tools['python']}\" -c \"print('VISTA3D-ready workspace for {safe_case}:', r'%CD%\\\\vista3d_workspace')\"\n"
        )
    else:
        commands["run_vista3d_example"] = (
            "@echo off\n"
            "REM No standalone Python runtime detected. Install Python/conda first, then use vista3d_workspace as the handoff folder.\n"
        )

    commands["workspace_notes"] = (
        "@echo off\n"
        f"echo Case {safe_case} ({modality or 'unknown'}) exported by ENT Assistant v3\n"
        f"echo Image: {image_name}\n"
        f"echo Labelmap: {label_name}\n"
    )
    return commands


def _which(name: str) -> Optional[str]:
    return shutil.which(name)


def _probe_python() -> Optional[str]:
    for candidate in ["python", "python3"]:
        resolved = shutil.which(candidate)
        if not resolved:
            continue
        try:
            result = subprocess.run(
                [candidate, "-c", "import sys; print(sys.executable)"],
                capture_output=True,
                text=True,
                check=False,
                timeout=5,
            )
            if result.returncode == 0 and (result.stdout or "").strip():
                return (result.stdout or "").strip()
        except Exception:
            continue
    return None


def _inspect_gpu() -> Dict[str, object]:
    nvidia_smi = shutil.which("nvidia-smi")
    if not nvidia_smi:
        return {"available": False, "name": None, "memoryMb": None, "cudaVersion": None}
    try:
        result = subprocess.run(
            [nvidia_smi, "--query-gpu=name,memory.total", "--format=csv,noheader,nounits"],
            capture_output=True,
            text=True,
            check=False,
            timeout=5,
        )
        line = (result.stdout or "").strip().splitlines()[0] if (result.stdout or "").strip() else ""
        name = None
        memory_mb = None
        if line:
            name, memory_text = [part.strip() for part in line.split(",", 1)]
            memory_mb = int(memory_text) if memory_text.isdigit() else None
        summary = subprocess.run([nvidia_smi], capture_output=True, text=True, check=False, timeout=5)
        cuda_version = None
        for row in (summary.stdout or "").splitlines():
            if "CUDA Version:" in row:
                cuda_version = row.split("CUDA Version:", 1)[1].strip().split()[0]
                break
        return {"available": bool(name), "name": name, "memoryMb": memory_mb, "cudaVersion": cuda_version}
    except Exception:
        return {"available": False, "name": None, "memoryMb": None, "cudaVersion": None}


def _sanitize_name(value: str) -> str:
    cleaned = "".join(char if char.isalnum() or char in {"-", "_"} else "_" for char in value.strip())
    return cleaned.strip("._") or "case"


def _inspect_env(env_dir: Path, python_exe: Path) -> Dict[str, object]:
    available_tools: List[str] = []
    scripts_dir = python_exe.parent
    for tool_name in ["TotalSegmentator.exe", "monailabel.exe", "nnUNetv2_predict.exe", "nnUNet_predict.exe"]:
        if (scripts_dir / tool_name).exists():
            available_tools.append(tool_name.replace(".exe", ""))
    return {
        "name": env_dir.name,
        "directory": str(env_dir),
        "python": str(python_exe),
        "availableTools": available_tools,
    }
