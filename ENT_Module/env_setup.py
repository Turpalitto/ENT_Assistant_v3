from __future__ import annotations

from pathlib import Path
from typing import Dict, List


def generate_external_env_setup(target_directory: str, env_name: str = "ent_ai_env") -> Dict[str, object]:
    target_dir = Path(target_directory)
    target_dir.mkdir(parents=True, exist_ok=True)

    files = {
        "install_python": target_dir / "01_install_python.cmd",
        "create_env": target_dir / "02_create_env.cmd",
        "install_torch": target_dir / "03_install_gpu_torch.cmd",
        "install_stack": target_dir / "04_install_ent_ai_stack.cmd",
        "activate_env": target_dir / "05_activate_env.cmd",
        "nnunet_env": target_dir / "06_set_nnunet_env.cmd",
        "bootstrap_all": target_dir / "07_bootstrap_all.cmd",
        "readme": target_dir / "README_ENV_SETUP.txt",
    }

    files["install_python"].write_text(_install_python_cmd(), encoding="utf-8")
    files["create_env"].write_text(_create_env_cmd(env_name), encoding="utf-8")
    files["install_torch"].write_text(_install_torch_cmd(env_name), encoding="utf-8")
    files["install_stack"].write_text(_install_stack_cmd(env_name), encoding="utf-8")
    files["activate_env"].write_text(_activate_env_cmd(env_name), encoding="utf-8")
    files["nnunet_env"].write_text(_nnunet_env_cmd(env_name), encoding="utf-8")
    files["bootstrap_all"].write_text(_bootstrap_all_cmd(), encoding="utf-8")
    files["readme"].write_text(_readme_text(env_name), encoding="utf-8")

    return {
        "directory": str(target_dir),
        "files": {key: str(path) for key, path in files.items()},
        "installHints": build_install_hints(),
    }


def build_install_hints() -> List[Dict[str, str]]:
    return [
        {
            "project": "Python",
            "command": "winget install -e --id Python.Python.3.10",
            "source": "Official Windows package manager",
        },
        {
            "project": "PyTorch (GPU)",
            "command": "python -m pip install torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cu128",
            "source": "Official PyTorch install flow",
        },
        {
            "project": "TotalSegmentator",
            "command": "python -m pip install TotalSegmentator",
            "source": "Official TotalSegmentator README flow",
        },
        {
            "project": "MONAI Label",
            "command": "python -m pip install -U monailabel",
            "source": "Official MONAI Label README flow",
        },
        {
            "project": "nnU-Net",
            "command": "python -m pip install nnunetv2",
            "source": "Official nnU-Net installation flow",
        },
    ]


def _install_python_cmd() -> str:
    return (
        "@echo off\n"
        "REM Installs Python 3.10 via winget if it is missing.\n"
        "winget install -e --id Python.Python.3.10\n"
    )


def _create_env_cmd(env_name: str) -> str:
    return (
        "@echo off\n"
        "REM Create a standalone venv for external AI backends.\n"
        f"python -m venv %USERPROFILE%\\{env_name}\n"
    )


def _install_torch_cmd(env_name: str) -> str:
    return (
        "@echo off\n"
        f"call %USERPROFILE%\\{env_name}\\Scripts\\activate.bat\n"
        "python -m pip install --upgrade pip\n"
        "REM Official PyTorch CUDA wheel line; adjust if your preferred CUDA wheel changes.\n"
        "python -m pip install torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cu128\n"
    )


def _install_stack_cmd(env_name: str) -> str:
    return (
        "@echo off\n"
        f"call %USERPROFILE%\\{env_name}\\Scripts\\activate.bat\n"
        "python -m pip install --upgrade pip\n"
        "python -m pip install TotalSegmentator\n"
        "python -m pip install -U monailabel\n"
        "python -m pip install nnunetv2 SimpleITK nibabel\n"
    )


def _activate_env_cmd(env_name: str) -> str:
    return (
        "@echo off\n"
        f"call %USERPROFILE%\\{env_name}\\Scripts\\activate.bat\n"
        "cmd /k\n"
    )


def _nnunet_env_cmd(env_name: str) -> str:
    return (
        "@echo off\n"
        f"call %USERPROFILE%\\{env_name}\\Scripts\\activate.bat\n"
        "set nnUNet_raw=%CD%\\nnunet_workspace\\raw\n"
        "set nnUNet_preprocessed=%CD%\\nnunet_workspace\\preprocessed\n"
        "set nnUNet_results=%CD%\\nnunet_workspace\\results\n"
        "mkdir %nnUNet_raw% 2>nul\n"
        "mkdir %nnUNet_preprocessed% 2>nul\n"
        "mkdir %nnUNet_results% 2>nul\n"
        "echo nnU-Net environment variables configured for this workspace.\n"
    )


def _readme_text(env_name: str) -> str:
    return "\n".join(
        [
            "ENT Assistant v3 - External AI environment setup",
            "",
            f"Suggested venv name: {env_name}",
            "",
            "Recommended order:",
            "1. Run 01_install_python.cmd if Python is not installed.",
            "2. Run 02_create_env.cmd",
            "3. Run 03_install_gpu_torch.cmd",
            "4. Run 04_install_ent_ai_stack.cmd",
            "5. Run 06_set_nnunet_env.cmd inside the exported AI workspace if using nnU-Net",
            "Or run 07_bootstrap_all.cmd for the default sequence.",
            "",
            "These scripts are templates. Review and adjust them before running on your workstation.",
        ]
    )


def _bootstrap_all_cmd() -> str:
    return (
        "@echo off\n"
        "call 01_install_python.cmd\n"
        "call 02_create_env.cmd\n"
        "call 03_install_gpu_torch.cmd\n"
        "call 04_install_ent_ai_stack.cmd\n"
    )
