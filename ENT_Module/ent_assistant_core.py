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

    def to_dict(self) -> Dict[str, object]:
        return asdict(self)


@dataclass
class AnalysisConfig:
    preset_key: str
    use_totalsegmentator: bool = True
    save_report: bool = True
    report_dir: Optional[str] = None
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
