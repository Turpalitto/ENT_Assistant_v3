from __future__ import annotations

import shutil
import json
from pathlib import Path
from typing import Dict, List, Optional

import slicer


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
