from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path
import re
from typing import Dict, Iterable, List, Optional


@dataclass(frozen=True)
class AnalysisPreset:
    key: str
    title: str
    description: str
    mode: str
    totalsegmentator_task: Optional[str] = None
    expected_masks: Optional[List[str]] = None
    bone_threshold_min: int = 300
    bone_threshold_max: int = 3000
    air_threshold_min: int = -1000
    air_threshold_max: int = -300
    soft_tissue_threshold_min: int = -150
    soft_tissue_threshold_max: int = 250
    minimum_expected_volume_ml: float = 0.1
    maximum_expected_volume_ml: float = 5000.0

    def to_dict(self) -> Dict[str, object]:
        return asdict(self)


@dataclass
class AnalysisConfig:
    preset_key: str
    use_totalsegmentator: bool = True
    save_report: bool = True
    report_dir: Optional[str] = None
    batch_mode: str = "active"
    export_results: bool = True
    export_seg_nrrd: bool = True
    export_labelmap_nifti: bool = True
    export_surface_models: bool = False
    export_rtstruct: bool = False
    export_dir: Optional[str] = None
    ai_quality: str = "normal"
    use_cpu: bool = False
    robust_crop: bool = True
    bone_threshold_min: Optional[int] = None
    bone_threshold_max: Optional[int] = None
    air_threshold_min: Optional[int] = None
    air_threshold_max: Optional[int] = None


DEFAULT_PRESETS: Dict[str, AnalysisPreset] = {
    "ent_threshold": AnalysisPreset(
        key="ent_threshold",
        title="ENT CT: bone + airway",
        description="Fast fallback segmentation for ENT CT studies using classic HU thresholds.",
        mode="threshold",
    ),
    "head_neck_ai": AnalysisPreset(
        key="head_neck_ai",
        title="Head & neck AI preset",
        description="Uses TotalSegmentator for glands, pharynx, nasal cavities and auditory canals.",
        mode="totalsegmentator",
        totalsegmentator_task="head_glands_cavities",
        expected_masks=[
            "parotid_gland_left",
            "parotid_gland_right",
            "submandibular_gland_left",
            "submandibular_gland_right",
            "nasopharynx",
            "oropharynx",
            "hypopharynx",
            "nasal_cavity_left",
            "nasal_cavity_right",
            "auditory_canal_left",
            "auditory_canal_right",
        ],
    ),
    "craniofacial_ai": AnalysisPreset(
        key="craniofacial_ai",
        title="Craniofacial AI preset",
        description="Uses TotalSegmentator for skull, mandible, sinuses and teeth.",
        mode="totalsegmentator",
        totalsegmentator_task="craniofacial_structures",
        expected_masks=[
            "skull",
            "mandible",
            "sinus_maxillary",
            "sinus_frontal",
            "teeth_upper",
            "teeth_lower",
        ],
    ),
    "larynx_ai": AnalysisPreset(
        key="larynx_ai",
        title="Larynx and hyoid AI preset",
        description="Uses TotalSegmentator for laryngeal air space and hyoid-cartilage structures.",
        mode="totalsegmentator",
        totalsegmentator_task="headneck_bones_vessels",
        expected_masks=[
            "larynx_air",
            "hyoid",
            "thyroid_cartilage",
            "cricoid_cartilage",
            "styloid_process_left",
            "styloid_process_right",
        ],
    ),
}


def get_presets() -> Dict[str, AnalysisPreset]:
    return DEFAULT_PRESETS.copy()


def get_preset(preset_key: str) -> AnalysisPreset:
    return get_presets().get(preset_key, DEFAULT_PRESETS["ent_threshold"])


def sanitize_filename(value: str) -> str:
    cleaned = re.sub(r"[^A-Za-z0-9._-]+", "_", value.strip())
    return cleaned.strip("._") or "analysis"


def ensure_report_dir(path_hint: Optional[str], repo_root: str) -> Path:
    target = Path(path_hint) if path_hint else Path(repo_root) / "reports"
    target.mkdir(parents=True, exist_ok=True)
    return target


def ensure_export_dir(path_hint: Optional[str], repo_root: str) -> Path:
    target = Path(path_hint) if path_hint else Path(repo_root) / "exports"
    target.mkdir(parents=True, exist_ok=True)
    return target


def build_report_path(report_dir: Path, volume_name: str, preset_title: str) -> Path:
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"{sanitize_filename(volume_name)}__{sanitize_filename(preset_title)}__{timestamp}.json"
    return report_dir / filename


def summarize_measurements(measurements: Iterable[Dict[str, object]]) -> str:
    rows = list(measurements)
    if not rows:
        return "No segment measurements were produced."
    return "\n".join(
        f"- {row.get('segment', 'unknown')}: {row.get('volume_ml', 0.0):.2f} mL ({row.get('voxel_count', 0)} voxels)"
        for row in rows
    )


def build_impression(preset_title: str, measurements: Iterable[Dict[str, object]]) -> str:
    rows = sorted(list(measurements), key=lambda row: float(row.get("volume_ml", 0.0)), reverse=True)
    if not rows:
        return f"{preset_title}: no measurable segments were produced."

    lead = rows[:3]
    segment_summary = ", ".join(f"{row['segment']} {row['volume_ml']:.2f} mL" for row in lead)
    return f"{preset_title}: dominant segmented structures -> {segment_summary}."


def build_ent_summary(preset: AnalysisPreset, measurements: Iterable[Dict[str, object]]) -> Dict[str, object]:
    rows = list(measurements)
    measurement_by_name = {str(row.get("segment", "")): row for row in rows}
    air_like_segments = []
    for row in rows:
        name = str(row.get("segment", "")).lower()
        if "air" in name or "sinus" in name or "nasal_cavity" in name or "pharynx" in name:
            air_like_segments.append(row)

    top_airway = sorted(air_like_segments, key=lambda row: float(row.get("volume_ml", 0.0)), reverse=True)[:5]
    asymmetry = []
    heuristic_flags = []
    for left_name, left_row in measurement_by_name.items():
        if not left_name.endswith("_left"):
            continue
        right_name = left_name[: -len("_left")] + "_right"
        if right_name not in measurement_by_name:
            continue
        left_volume = float(left_row.get("volume_ml", 0.0))
        right_volume = float(measurement_by_name[right_name].get("volume_ml", 0.0))
        smaller = min(left_volume, right_volume)
        if smaller <= 0:
            continue
        ratio = max(left_volume, right_volume) / smaller
        asymmetry.append(
            {
                "pair": [left_name, right_name],
                "ratio": round(ratio, 2),
                "leftVolumeMl": round(left_volume, 2),
                "rightVolumeMl": round(right_volume, 2),
            }
        )
        root_name = left_name[: -len("_left")]
        if "nasal_cavity" in root_name and ratio >= 2.0:
            heuristic_flags.append(
                {
                    "code": "possible_nasal_asymmetry",
                    "message": f"Nasal cavity volume asymmetry is elevated for {root_name} ({ratio:.2f}x).",
                }
            )

    asymmetry.sort(key=lambda row: row["ratio"], reverse=True)
    for row in top_airway:
        segment_name = str(row.get("segment", ""))
        volume_ml = float(row.get("volume_ml", 0.0))
        if volume_ml < 1.0 and (
            "nasal_cavity" in segment_name or "sinus" in segment_name or "pharynx" in segment_name or "air" in segment_name
        ):
            heuristic_flags.append(
                {
                    "code": "possible_reduced_aeration",
                    "message": f"Air-containing structure {segment_name} has low measured volume ({volume_ml:.2f} mL).",
                }
            )

    return {
        "preset": preset.title,
        "airwayOrCavitySegments": [
            {"segment": row["segment"], "volumeMl": row["volume_ml"]} for row in top_airway
        ],
        "strongestAsymmetry": asymmetry[:3],
        "heuristicFlags": heuristic_flags,
        "summaryText": build_ent_summary_text(preset.title, top_airway, asymmetry[:3], heuristic_flags),
    }


def build_ent_summary_text(
    preset_title: str,
    top_airway_rows: Iterable[Dict[str, object]],
    asymmetry_rows: Iterable[Dict[str, object]],
    heuristic_flags: Iterable[Dict[str, object]],
) -> str:
    airway_rows = list(top_airway_rows)
    asymmetry = list(asymmetry_rows)
    flags = list(heuristic_flags)
    chunks = [f"{preset_title} ENT summary:"]
    if airway_rows:
        chunks.append(
            "largest airway/cavity-related segments -> "
            + ", ".join(f"{row['segment']} {row['volume_ml']:.2f} mL" for row in airway_rows[:3])
        )
    else:
        chunks.append("no airway/cavity-focused segments identified")
    if asymmetry:
        lead = asymmetry[0]
        chunks.append(
            f"top asymmetry -> {lead['pair'][0]} vs {lead['pair'][1]} ({lead['ratio']:.2f}x)"
        )
    else:
        chunks.append("no measurable left/right asymmetry pairs")
    if flags:
        chunks.append("heuristic flags -> " + ", ".join(flag["code"] for flag in flags[:3]))
    return "; ".join(chunks) + "."


def build_case_comparison(previous_case: Dict[str, object], current_case: Dict[str, object]) -> Dict[str, object]:
    previous_measurements = {
        row.get("segment"): row for row in previous_case.get("measurements", []) if row.get("segment")
    }
    current_measurements = {
        row.get("segment"): row for row in current_case.get("measurements", []) if row.get("segment")
    }
    deltas = []
    for segment_name in sorted(set(previous_measurements.keys()) & set(current_measurements.keys())):
        previous_volume = float(previous_measurements[segment_name].get("volume_ml", 0.0))
        current_volume = float(current_measurements[segment_name].get("volume_ml", 0.0))
        delta_volume = round(current_volume - previous_volume, 2)
        delta_percent = None if previous_volume == 0 else round((delta_volume / previous_volume) * 100.0, 2)
        deltas.append(
            {
                "segment": segment_name,
                "previousVolumeMl": round(previous_volume, 2),
                "currentVolumeMl": round(current_volume, 2),
                "deltaVolumeMl": delta_volume,
                "deltaPercent": delta_percent,
            }
        )
    deltas.sort(key=lambda row: abs(float(row.get("deltaVolumeMl", 0.0))), reverse=True)
    return {
        "previousCase": previous_case.get("volumeName"),
        "currentCase": current_case.get("volumeName"),
        "segmentDeltas": deltas,
        "summaryText": build_case_comparison_text(previous_case.get("volumeName"), current_case.get("volumeName"), deltas),
    }


def build_case_comparison_text(previous_name: str, current_name: str, deltas: Iterable[Dict[str, object]]) -> str:
    rows = list(deltas)
    if not rows:
        return f"Comparison {previous_name} -> {current_name}: no overlapping segment names for comparison."
    lead = rows[:3]
    return (
        f"Comparison {previous_name} -> {current_name}: "
        + ", ".join(f"{row['segment']} {row['deltaVolumeMl']:+.2f} mL" for row in lead)
        + "."
    )


def build_longitudinal_timeline(cases: Iterable[Dict[str, object]]) -> Dict[str, object]:
    rows = list(cases)
    grouped: Dict[str, List[Dict[str, object]]] = {}
    for case in rows:
        study_info = case.get("studyInfo") or {}
        patient_id = str(study_info.get("dicomPatientId") or "unknown_patient")
        grouped.setdefault(patient_id, []).append(case)

    patient_timelines = []
    for patient_id, patient_cases in grouped.items():
        sorted_cases = sorted(
            patient_cases,
            key=lambda case: str((case.get("studyInfo") or {}).get("dicomStudyDate") or case.get("volumeName") or ""),
        )
        comparisons = [
            build_case_comparison(previous_case, current_case)
            for previous_case, current_case in zip(sorted_cases, sorted_cases[1:])
        ]
        patient_timelines.append(
            {
                "patientId": patient_id,
                "caseCount": len(sorted_cases),
                "studies": [
                    {
                        "volumeName": case.get("volumeName"),
                        "studyDate": (case.get("studyInfo") or {}).get("dicomStudyDate"),
                        "seriesDescription": (case.get("studyInfo") or {}).get("dicomSeriesDescription"),
                        "reportPath": case.get("reportPath"),
                    }
                    for case in sorted_cases
                ],
                "comparisons": comparisons,
            }
        )
    return {
        "patientCount": len(patient_timelines),
        "patients": patient_timelines,
    }


def build_ent_pathology_flags(measurements: Iterable[Dict[str, object]]) -> List[Dict[str, object]]:
    rows = list(measurements)
    by_name = {str(row.get("segment", "")): row for row in rows}
    flags: List[Dict[str, object]] = []

    def volume(name: str) -> float:
        return float(by_name.get(name, {}).get("volume_ml", 0.0))

    nasal_left = volume("nasal_cavity_left")
    nasal_right = volume("nasal_cavity_right")
    if nasal_left > 0 and nasal_right > 0:
        ratio = max(nasal_left, nasal_right) / min(nasal_left, nasal_right)
        if ratio >= 2.0:
            flags.append(
                {
                    "code": "entorhino_nasal_passage_asymmetry",
                    "message": f"Nasal cavity asymmetry is elevated ({ratio:.2f}x).",
                }
            )

    sinus_total = sum(
        volume(name)
        for name in [
            "sinus_maxillary",
            "sinus_frontal",
            "sinus_sphenoid",
            "sinus_ethmoid",
        ]
    )
    if 0 < sinus_total < 2.0:
        flags.append(
            {
                "code": "entorhino_low_sinus_aeration",
                "message": f"Combined sinus aeration volume appears low ({sinus_total:.2f} mL).",
            }
        )

    larynx_air = volume("larynx_air")
    if 0 < larynx_air < 1.5:
        flags.append(
            {
                "code": "larynx_low_air_column",
                "message": f"Laryngeal air column volume appears reduced ({larynx_air:.2f} mL).",
            }
        )

    oro = volume("oropharynx")
    hypo = volume("hypopharynx")
    if oro > 0 and hypo > 0 and max(oro, hypo) / min(oro, hypo) >= 2.5:
        flags.append(
            {
                "code": "pharyngeal_airway_disproportion",
                "message": "Marked oropharynx/hypopharynx disproportion detected.",
            }
        )

    return flags


def build_quality_checks(preset: AnalysisPreset, measurements: Iterable[Dict[str, object]]) -> List[Dict[str, object]]:
    rows = list(measurements)
    findings: List[Dict[str, object]] = []

    if not rows:
        findings.append(
            {
                "level": "error",
                "code": "no_segments",
                "message": "No measurable segments were produced.",
            }
        )
        return findings

    measurement_by_name = {str(row.get("segment", "")): row for row in rows}
    for row in rows:
        name = str(row.get("segment", "unknown"))
        volume_ml = float(row.get("volume_ml", 0.0))
        voxel_count = int(row.get("voxel_count", 0))
        if voxel_count == 0 or volume_ml <= 0:
            findings.append(
                {
                    "level": "error",
                    "code": "empty_segment",
                    "segment": name,
                    "message": f"Segment {name} is empty.",
                }
            )
        elif volume_ml < preset.minimum_expected_volume_ml:
            findings.append(
                {
                    "level": "warning",
                    "code": "very_small_segment",
                    "segment": name,
                    "message": f"Segment {name} is very small ({volume_ml:.2f} mL).",
                }
            )
        elif volume_ml > preset.maximum_expected_volume_ml:
            findings.append(
                {
                    "level": "warning",
                    "code": "very_large_segment",
                    "segment": name,
                    "message": f"Segment {name} is unusually large ({volume_ml:.2f} mL).",
                }
            )

    expected_masks = preset.expected_masks or []
    missing_masks = [mask for mask in expected_masks if mask not in measurement_by_name]
    if missing_masks:
        findings.append(
            {
                "level": "warning",
                "code": "missing_expected_masks",
                "message": "Some expected structures were not produced.",
                "missingMasks": missing_masks,
            }
        )

    findings.extend(_build_left_right_balance_checks(measurement_by_name))
    if not findings:
        findings.append(
            {
                "level": "info",
                "code": "qc_pass",
                "message": "No simple rule-based quality issues were detected.",
            }
        )
    return findings


def _build_left_right_balance_checks(measurement_by_name: Dict[str, Dict[str, object]]) -> List[Dict[str, object]]:
    findings: List[Dict[str, object]] = []
    names = set(measurement_by_name.keys())
    processed_roots = set()

    for name in names:
        if name.endswith("_left"):
            root = name[: -len("_left")]
            left_name = name
            right_name = f"{root}_right"
        elif name.endswith("_right"):
            root = name[: -len("_right")]
            left_name = f"{root}_left"
            right_name = name
        else:
            continue

        if root in processed_roots:
            continue
        processed_roots.add(root)
        if left_name not in measurement_by_name or right_name not in measurement_by_name:
            continue

        left_volume = float(measurement_by_name[left_name].get("volume_ml", 0.0))
        right_volume = float(measurement_by_name[right_name].get("volume_ml", 0.0))
        larger = max(left_volume, right_volume)
        smaller = min(left_volume, right_volume)
        if smaller <= 0:
            continue
        ratio = larger / smaller
        if ratio >= 3.0:
            findings.append(
                {
                    "level": "warning",
                    "code": "left_right_asymmetry",
                    "segmentPair": [left_name, right_name],
                    "message": f"Strong left/right asymmetry detected for {root} ({ratio:.2f}x).",
                }
            )

    return findings
