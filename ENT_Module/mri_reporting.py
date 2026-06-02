from __future__ import annotations

from typing import Dict, List


MRI_SEQUENCE_PATTERNS = {
    "t1": ["t1", "vibe", "mprage", "spgr"],
    "t2": ["t2", "tse", "space", "cube"],
    "flair": ["flair"],
    "dwi": ["diff", "dwi", "trace"],
    "adc": ["adc"],
    "high_res_t2": ["ciss", "fie", "fiesta", "drive", "ci3d", "space", "cube"],
    "postcontrast_t1": ["vibe_fs", "t1_fs", "post", "c+"],
}


def build_ent_mri_report(study_info: Dict[str, object], measurements: List[Dict[str, object]], report_mode: str = "assistant") -> Dict[str, object]:
    sequence_text = str(study_info.get("dicomSeriesDescription") or "")
    sequence_tags = detect_mri_sequences(sequence_text)
    suitability = build_ent_mri_suitability(study_info, sequence_tags)
    findings = build_mri_findings(sequence_tags, measurements)
    recommendations = build_mri_recommendations(sequence_tags, suitability, report_mode)
    impression_lines = build_mri_impression(sequence_tags, suitability, findings, report_mode)
    patient_summary = build_mri_patient_summary(sequence_tags, suitability)
    return {
        "reportMode": report_mode,
        "sequenceTags": sequence_tags,
        "suitability": suitability,
        "findings": findings,
        "recommendations": recommendations,
        "impressionLines": impression_lines,
        "impression": "\n".join(impression_lines),
        "patientSummary": patient_summary,
        "description": build_mri_description(sequence_tags, study_info, findings, report_mode),
        "reportText": build_mri_report_text(sequence_tags, study_info, findings, impression_lines, recommendations, patient_summary),
        "findingRows": build_mri_finding_rows(sequence_tags, suitability, findings),
        "disclaimer": "MRI ENT workflow is an AI-assisted support layer and not a stand-alone diagnostic system.",
    }


def detect_mri_sequences(series_description: str) -> List[str]:
    text = series_description.lower()
    matches: List[str] = []
    for tag, patterns in MRI_SEQUENCE_PATTERNS.items():
        if any(pattern in text for pattern in patterns):
            matches.append(tag)
    return sorted(set(matches))


def build_ent_mri_suitability(study_info: Dict[str, object], sequence_tags: List[str]) -> Dict[str, object]:
    modality = str(study_info.get("dicomModality") or "")
    spacing = study_info.get("spacingMm") or []
    notes = []
    score = 0
    if modality.upper() == "MR":
        score += 2
    else:
        notes.append(f"Modality is {modality or 'unknown'}, while this workflow is intended for MRI.")
    if "high_res_t2" in sequence_tags:
        score += 2
    if "dwi" in sequence_tags or "adc" in sequence_tags:
        score += 1
    if spacing and len(spacing) >= 3:
        slice_thickness = float(spacing[2])
        if slice_thickness <= 1.2:
            score += 2
        elif slice_thickness <= 3.5:
            score += 1
        else:
            notes.append(f"Slice thickness {slice_thickness:.2f} mm may be limiting for fine ENT anatomy.")
    if score >= 4:
        level = "good"
    elif score >= 2:
        level = "limited"
    else:
        level = "poor"
    if not notes:
        notes.append("MRI characteristics look usable for AI-assisted ENT review.")
    return {"level": level, "score": score, "notes": notes}


def build_mri_findings(sequence_tags: List[str], measurements: List[Dict[str, object]]) -> List[Dict[str, object]]:
    findings = []
    foreground = next((row for row in measurements if row.get("segment") == "MRI_Foreground"), None)
    low_signal = next((row for row in measurements if row.get("segment") == "MRI_LowSignal"), None)
    if "high_res_t2" in sequence_tags:
        findings.append({"code": "high_res_t2_available", "message": "High-resolution T2-like sequence detected; suitable for fluid-space and labyrinthine review."})
    if "dwi" in sequence_tags or "adc" in sequence_tags:
        findings.append({"code": "diffusion_available", "message": "Diffusion-weighted imaging appears available; useful for restricted-diffusion targets such as cholesteatoma workup."})
    if "postcontrast_t1" in sequence_tags:
        findings.append({"code": "postcontrast_available", "message": "Post-contrast T1-like sequence appears available for enhancement assessment."})
    if foreground:
        findings.append({"code": "foreground_segment", "message": f"MRI foreground mask volume: {foreground.get('volume_ml')} mL."})
    if low_signal:
        findings.append({"code": "lowsignal_segment", "message": f"Low-signal mask volume: {low_signal.get('volume_ml')} mL."})
    return findings


def build_mri_description(sequence_tags: List[str], study_info: Dict[str, object], findings: List[Dict[str, object]], report_mode: str) -> str:
    lines = [
        f"MRI modality support review for series: {study_info.get('dicomSeriesDescription') or study_info.get('volumeName')}.",
        "Detected sequence families: " + (", ".join(sequence_tags) if sequence_tags else "none confidently recognized") + ".",
    ]
    for finding in findings:
        lines.append(finding["message"])
    if report_mode == "surgeon":
        lines.append("Surgeon mode emphasizes sequences relevant to preoperative soft-tissue and diffusion review.")
    return "\n".join(lines)


def build_mri_impression(sequence_tags: List[str], suitability: Dict[str, object], findings: List[Dict[str, object]], report_mode: str) -> List[str]:
    lines = [f"MRI ENT support suitability: {suitability.get('level')} ({suitability.get('score')})."]
    if "high_res_t2" in sequence_tags:
        lines.append("High-resolution T2 sequence support is present for detailed skull-base or temporal-bone style review.")
    if "dwi" in sequence_tags or "adc" in sequence_tags:
        lines.append("Diffusion support is present.")
    if "postcontrast_t1" in sequence_tags:
        lines.append("Contrast-sensitive T1 support appears present.")
    if report_mode == "radiology":
        lines.append("Focus: conservative MRI sequence-based radiology support.")
    elif report_mode == "surgeon":
        lines.append("Focus: preoperative MRI sequence utility for ENT/skull-base review.")
    else:
        lines.append("Focus: AI-assisted integrated MRI support summary.")
    return lines


def build_mri_recommendations(sequence_tags: List[str], suitability: Dict[str, object], report_mode: str) -> List[str]:
    recommendations = []
    if suitability.get("level") != "good":
        recommendations.extend(suitability.get("notes", [])[:2])
    if "high_res_t2" not in sequence_tags:
        recommendations.append("Consider adding a high-resolution T2 sequence when detailed temporal bone or fluid-space review is needed.")
    if "dwi" not in sequence_tags and report_mode in {"assistant", "radiology", "surgeon"}:
        recommendations.append("Consider diffusion-weighted imaging when cholesteatoma or restricted-diffusion pathology is part of the differential.")
    if "postcontrast_t1" not in sequence_tags:
        recommendations.append("Add post-contrast T1 imaging when enhancement characterization is clinically relevant.")
    if not recommendations:
        recommendations.append("Review MRI findings together with ENT examination and the clinical indication.")
    return recommendations


def build_mri_patient_summary(sequence_tags: List[str], suitability: Dict[str, object]) -> str:
    parts = [f"This MRI review support looks {suitability.get('level')} for ENT interpretation."]
    if "high_res_t2" in sequence_tags:
        parts.append("A fine-detail fluid-sensitive sequence is available.")
    if "dwi" in sequence_tags:
        parts.append("Diffusion imaging is also present.")
    parts.append("This summary does not replace your radiologist or ENT specialist.")
    return " ".join(parts)


def build_mri_report_text(
    sequence_tags: List[str],
    study_info: Dict[str, object],
    findings: List[Dict[str, object]],
    impression_lines: List[str],
    recommendations: List[str],
    patient_summary: str,
) -> str:
    return "\n".join(
        [
            "Description:",
            build_mri_description(sequence_tags, study_info, findings, "assistant"),
            "",
            "Impression:",
            "\n".join(f"- {line}" for line in impression_lines),
            "",
            "Recommendations:",
            "\n".join(f"- {line}" for line in recommendations),
            "",
            "Patient-friendly summary:",
            patient_summary,
        ]
    )


def build_mri_finding_rows(sequence_tags: List[str], suitability: Dict[str, object], findings: List[Dict[str, object]]) -> List[Dict[str, str]]:
    rows = [
        {"category": "MRI", "structure": "Suitability", "status": str(suitability.get("level")), "details": " | ".join(suitability.get("notes", []))}
    ]
    for tag in sequence_tags:
        rows.append({"category": "Sequence", "structure": tag, "status": "present", "details": tag})
    for finding in findings:
        rows.append({"category": "Finding", "structure": finding["code"], "status": "info", "details": finding["message"]})
    return rows
