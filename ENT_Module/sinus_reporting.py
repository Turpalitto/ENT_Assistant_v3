from __future__ import annotations

from typing import Dict, Iterable, List, Optional, Tuple


SINUS_LABELS = {
    "sinus_maxillary_left": "Left maxillary sinus",
    "sinus_maxillary_right": "Right maxillary sinus",
    "sinus_frontal_left": "Left frontal sinus",
    "sinus_frontal_right": "Right frontal sinus",
    "sinus_ethmoid_left": "Left ethmoid cells",
    "sinus_ethmoid_right": "Right ethmoid cells",
    "sinus_sphenoid_left": "Left sphenoid sinus",
    "sinus_sphenoid_right": "Right sphenoid sinus",
}

SINUS_SMALL_VOLUME_THRESHOLDS_ML = {
    "sinus_maxillary": 4.0,
    "sinus_frontal": 1.5,
    "sinus_ethmoid": 1.0,
    "sinus_sphenoid": 1.5,
}


def build_ct_sinus_report(
    measurements: Iterable[Dict[str, object]],
    study_info: Optional[Dict[str, object]] = None,
    report_mode: str = "assistant",
    include_checklist: bool = True,
) -> Dict[str, object]:
    rows = list(measurements)
    by_name = {str(row.get("segment", "")): row for row in rows}
    sinus_findings = _build_sinus_findings(by_name)
    anatomic_variants = _build_anatomic_variants(by_name, sinus_findings)
    omc_status = _build_omc_status(by_name, sinus_findings)
    diagnosis_hints = _build_diagnosis_hints(sinus_findings, omc_status)
    lund_mackay = _build_lund_mackay_score(sinus_findings, omc_status)
    surgical_summary = _build_surgical_summary(sinus_findings, omc_status, anatomic_variants)
    suitability = build_sinus_ct_suitability(study_info or {})
    description = _build_description(sinus_findings, anatomic_variants, omc_status, report_mode)
    impression_lines = _build_impression_lines(diagnosis_hints, omc_status, anatomic_variants, report_mode)
    recommendations = _build_recommendations(diagnosis_hints, omc_status, anatomic_variants, study_info or {}, suitability)
    checklist = _build_preop_checklist(sinus_findings, omc_status, anatomic_variants) if include_checklist else []
    patient_summary = _build_patient_summary(sinus_findings, omc_status, anatomic_variants)
    return {
        "studyModality": (study_info or {}).get("dicomModality"),
        "reportMode": report_mode,
        "suitability": suitability,
        "sinusFindings": sinus_findings,
        "anatomicVariants": anatomic_variants,
        "omcStatus": omc_status,
        "diagnosisHints": diagnosis_hints,
        "lundMackay": lund_mackay,
        "surgicalPlanning": surgical_summary,
        "description": description,
        "impression": "\n".join(impression_lines),
        "impressionLines": impression_lines,
        "recommendations": recommendations,
        "preOpChecklist": checklist,
        "patientSummary": patient_summary,
        "reportText": _build_report_text(description, impression_lines, recommendations, lund_mackay, surgical_summary, checklist),
        "findingRows": _build_finding_rows(sinus_findings, anatomic_variants, omc_status, lund_mackay, surgical_summary),
        "disclaimer": "AI-assisted sinus CT reporting support. Final interpretation remains with the physician.",
    }


def build_sinus_ct_suitability(study_info: Dict[str, object]) -> Dict[str, object]:
    modality = str(study_info.get("dicomModality") or "")
    spacing = study_info.get("spacingMm") or []
    series_description = str(study_info.get("dicomSeriesDescription") or "").lower()
    notes: List[str] = []
    score = 0

    if modality.upper() == "CT":
        score += 2
    else:
        notes.append(f"Modality is {modality or 'unknown'}, while sinus workflow is optimized for CT.")

    if spacing and len(spacing) >= 3:
        slice_thickness = float(spacing[2])
        if slice_thickness <= 1.5:
            score += 2
        elif slice_thickness <= 3.0:
            score += 1
            notes.append(f"Slice thickness {slice_thickness:.2f} mm is acceptable but not ideal for fine sinus anatomy.")
        else:
            notes.append(f"Slice thickness {slice_thickness:.2f} mm may reduce accuracy for OMC/FESS planning.")

    if any(keyword in series_description for keyword in ["sinus", "pns", "head", "facial", "skull"]):
        score += 1

    if score >= 4:
        level = "good"
    elif score >= 2:
        level = "limited"
    else:
        level = "poor"
    if not notes:
        notes.append("Study characteristics look acceptable for AI-assisted sinus CT review.")
    return {"level": level, "score": score, "notes": notes}


def _build_sinus_findings(by_name: Dict[str, Dict[str, object]]) -> List[Dict[str, object]]:
    findings: List[Dict[str, object]] = []
    for segment_name, label in SINUS_LABELS.items():
        row = by_name.get(segment_name)
        if not row:
            continue
        air_fraction = float(row.get("air_fraction", 0.0))
        soft_fraction = float(row.get("soft_fraction", 0.0))
        fluid_fraction = float(row.get("fluid_fraction", 0.0))
        opacified_fraction = max(0.0, min(1.0, 1.0 - air_fraction))
        pattern, severity = _pattern_from_opacification(opacified_fraction)
        root_name, side = _split_root_and_side(segment_name)
        findings.append(
            {
                "segment": segment_name,
                "label": label,
                "sinus": root_name,
                "side": side,
                "volumeMl": round(float(row.get("volume_ml", 0.0)), 2),
                "airFraction": round(air_fraction, 3),
                "softFraction": round(soft_fraction, 3),
                "fluidFraction": round(fluid_fraction, 3),
                "opacifiedFraction": round(opacified_fraction, 3),
                "meanHu": row.get("mean_hu"),
                "pattern": pattern,
                "severity": severity,
                "probableFluidLevel": _has_probable_fluid_level(row),
                "likelyInflammatory": severity != "none",
            }
        )
    _annotate_hypoplasia(findings)
    return findings


def _pattern_from_opacification(opacified_fraction: float) -> Tuple[str, str]:
    if opacified_fraction >= 0.9:
        return "Total opacification", "severe"
    if opacified_fraction >= 0.5:
        return "Marked partial opacification", "moderate_to_severe"
    if opacified_fraction >= 0.2:
        return "Moderate mural or partial opacification", "moderate"
    if opacified_fraction >= 0.08:
        return "Mild mucosal thickening pattern", "mild"
    return "Aeration preserved", "none"


def _annotate_hypoplasia(findings: List[Dict[str, object]]) -> None:
    grouped: Dict[str, List[Dict[str, object]]] = {}
    for finding in findings:
        grouped.setdefault(str(finding["sinus"]), []).append(finding)
    for sinus_name, pair in grouped.items():
        if len(pair) != 2:
            continue
        smaller = min(pair, key=lambda item: float(item["volumeMl"]))
        larger = max(pair, key=lambda item: float(item["volumeMl"]))
        threshold = SINUS_SMALL_VOLUME_THRESHOLDS_ML.get(sinus_name, 1.0)
        smaller_volume = float(smaller["volumeMl"])
        larger_volume = max(float(larger["volumeMl"]), 0.01)
        candidate = smaller_volume < threshold and (smaller_volume / larger_volume) <= 0.6
        smaller["hypoplasiaCandidate"] = candidate
        larger.setdefault("hypoplasiaCandidate", False)
        if candidate:
            smaller["pattern"] += "; possible hypoplasia"


def _build_anatomic_variants(by_name: Dict[str, Dict[str, object]], sinus_findings: List[Dict[str, object]]) -> List[Dict[str, object]]:
    variants: List[Dict[str, object]] = []
    nasal_left = float(by_name.get("nasal_cavity_left", {}).get("volume_ml", 0.0))
    nasal_right = float(by_name.get("nasal_cavity_right", {}).get("volume_ml", 0.0))
    if nasal_left > 0 and nasal_right > 0:
        ratio = max(nasal_left, nasal_right) / max(min(nasal_left, nasal_right), 0.01)
        if ratio >= 1.6:
            direction = "leftward" if nasal_left < nasal_right else "rightward"
            variants.append(
                {
                    "code": "probable_septal_deviation",
                    "message": f"Probable {direction} septal deviation.",
                    "importance": "fess_relevant",
                }
            )
    for finding in sinus_findings:
        if finding.get("hypoplasiaCandidate"):
            variants.append(
                {
                    "code": "sinus_hypoplasia_candidate",
                    "message": f"Possible hypoplasia: {finding['label']}.",
                    "importance": "variant",
                }
            )
    for side in ("left", "right"):
        for candidate in (f"concha_bullosa_{side}", f"middle_turbinate_pneumatized_{side}", f"middle_turbinate_{side}"):
            row = by_name.get(candidate)
            if not row:
                continue
            if "concha_bullosa" in candidate or float(row.get("air_fraction", 0.0)) >= 0.5:
                variants.append(
                    {
                        "code": f"concha_bullosa_{side}",
                        "message": f"Concha bullosa of the middle turbinate on the {side}.",
                        "importance": "fess_relevant",
                    }
                )
                break
    for key, title in (("retention_cyst", "retention cyst"), ("polyp", "polypoid lesion")):
        for segment_name in by_name:
            if key in segment_name:
                variants.append(
                    {
                        "code": key,
                        "message": f"Segment compatible with {title}: {segment_name}.",
                        "importance": "pathology",
                    }
                )
    return variants


def _build_omc_status(by_name: Dict[str, Dict[str, object]], sinus_findings: List[Dict[str, object]]) -> Dict[str, object]:
    status = {
        "left": {"state": "indeterminate", "message": "Insufficient direct data for left OMC assessment."},
        "right": {"state": "indeterminate", "message": "Insufficient direct data for right OMC assessment."},
    }
    for side in ("left", "right"):
        direct = by_name.get(f"ostiomeatal_complex_{side}") or by_name.get(f"omc_{side}")
        if direct:
            air_fraction = float(direct.get("air_fraction", 0.0))
            opacified_fraction = 1.0 - air_fraction
            if opacified_fraction >= 0.7:
                status[side] = {"state": "blocked", "message": f"OMC on the {side} appears blocked."}
            elif opacified_fraction >= 0.3:
                status[side] = {"state": "partially_blocked", "message": f"OMC on the {side} appears partially blocked."}
            else:
                status[side] = {"state": "patent", "message": f"OMC on the {side} appears patent."}
            continue
        supporting_count = 0
        for sinus_root in ("sinus_maxillary", "sinus_ethmoid", "sinus_frontal"):
            finding = _find_sinus(sinus_findings, sinus_root, side)
            if finding and float(finding["opacifiedFraction"]) >= 0.5:
                supporting_count += 1
        if supporting_count >= 2:
            status[side] = {"state": "possibly_blocked", "message": f"Likely OMC drainage compromise on the {side}."}
        elif supporting_count == 1:
            status[side] = {"state": "possibly_narrowed", "message": f"Possible OMC narrowing on the {side}."}
    return status


def _build_diagnosis_hints(sinus_findings: List[Dict[str, object]], omc_status: Dict[str, Dict[str, str]]) -> List[Dict[str, object]]:
    hints: List[Dict[str, object]] = []
    for finding in sinus_findings:
        if finding["severity"] == "none":
            continue
        side_label = "right-sided" if finding["side"] == "right" else "left-sided"
        disease_label = {
            "sinus_maxillary": "maxillary sinusitis",
            "sinus_frontal": "frontal sinusitis",
            "sinus_ethmoid": "ethmoid sinusitis",
            "sinus_sphenoid": "sphenoid sinusitis",
        }.get(str(finding["sinus"]), "sinusitis")
        qualifier = "with possible fluid level" if finding.get("probableFluidLevel") else finding["pattern"]
        hints.append(
            {
                "code": "sinusitis_pattern",
                "segment": finding["segment"],
                "message": f"CT features of {side_label} {disease_label}: {qualifier}.",
            }
        )
    for side in ("left", "right"):
        omc = omc_status[side]
        if omc["state"] in {"blocked", "partially_blocked", "possibly_blocked"}:
            hints.append(
                {
                    "code": "omc_obstruction",
                    "side": side,
                    "message": f"Features suggest impaired drainage through the {side} OMC.",
                }
            )
    return hints


def _build_description(
    sinus_findings: List[Dict[str, object]],
    anatomic_variants: List[Dict[str, object]],
    omc_status: Dict[str, Dict[str, str]],
    report_mode: str,
) -> str:
    lines: List[str] = []
    abnormal = [finding for finding in sinus_findings if finding["severity"] != "none"]
    if not abnormal:
        lines.append("Paranasal sinus aeration is largely preserved.")
    else:
        for finding in abnormal:
            text = f"{finding['label']}: {finding['pattern']}"
            if finding.get("probableFluidLevel"):
                text += ", possible fluid level"
            lines.append(text + ".")
    for side in ("right", "left"):
        if omc_status[side]["state"] != "indeterminate":
            lines.append(omc_status[side]["message"])
    for variant in anatomic_variants:
        lines.append(variant["message"])
    if report_mode == "surgeon":
        lines.append("Surgical mode emphasizes drainage pathway anatomy and pre-FESS variants.")
    return "\n".join(lines)


def _build_impression_lines(
    diagnosis_hints: List[Dict[str, object]],
    omc_status: Dict[str, Dict[str, str]],
    anatomic_variants: List[Dict[str, object]],
    report_mode: str,
) -> List[str]:
    lines: List[str] = []
    if diagnosis_hints:
        lines.extend(_compress_sinusitis_hints(diagnosis_hints))
    else:
        lines.append("No strong sinusitis pattern was detected from the currently available segments.")
    lines.extend([row["message"] for row in omc_status.values() if row["state"] in {"blocked", "partially_blocked", "possibly_blocked"}][:2])
    fess_variants = [row["message"] for row in anatomic_variants if row.get("importance") == "fess_relevant"]
    if fess_variants:
        lines.append("FESS-relevant anatomic variants: " + "; ".join(fess_variants[:3]))
    if report_mode == "surgeon":
        lines.append("Focus: surgical corridor, drainage pathways, and anatomy relevant to FESS planning.")
    elif report_mode == "radiology":
        lines.append("Focus: conservative radiology-style summary.")
    else:
        lines.append("Focus: AI-assisted integrated summary for ENT review.")
    return lines


def _build_recommendations(
    diagnosis_hints: List[Dict[str, object]],
    omc_status: Dict[str, Dict[str, str]],
    anatomic_variants: List[Dict[str, object]],
    study_info: Dict[str, object],
    suitability: Dict[str, object],
) -> List[str]:
    recommendations = []
    modality = str(study_info.get("dicomModality") or "").upper()
    if modality and modality != "CT":
        recommendations.append("The dedicated sinus workflow is optimized for CT; interpret other modalities cautiously.")
    if suitability.get("level") != "good":
        recommendations.extend(suitability.get("notes", [])[:2])
    if diagnosis_hints:
        recommendations.append("Correlate imaging findings with symptoms and ENT endoscopy.")
    if any(row["state"] in {"blocked", "partially_blocked", "possibly_blocked"} for row in omc_status.values()):
        recommendations.append("Review the osteomeatal complex and drainage pathways before treatment planning.")
    if any(row.get("importance") == "fess_relevant" for row in anatomic_variants):
        recommendations.append("Account for the listed anatomic variants during pre-FESS planning.")
    if not recommendations:
        recommendations.append("If clinically asymptomatic, standard ENT follow-up may be sufficient.")
    return recommendations


def _build_report_text(
    description: str,
    impression_lines: Iterable[str],
    recommendations: Iterable[str],
    lund_mackay: Dict[str, object],
    surgical_summary: Dict[str, object],
    checklist: Iterable[Dict[str, object]],
) -> str:
    impression = "\n".join(f"- {line}" for line in impression_lines)
    recommendation_lines = "\n".join(f"- {line}" for line in recommendations)
    surgical_lines = "\n".join(f"- {line}" for line in surgical_summary.get("summaryLines", []))
    checklist_lines = "\n".join(f"- {row.get('item')}: {row.get('status')} ({row.get('note')})" for row in checklist)
    return "\n".join(
        [
            "Description:",
            description or "No data.",
            "",
            "Burden score:",
            f"Lund-Mackay (approx.): {lund_mackay.get('totalScore', 0)} / 24",
            "",
            "Impression:",
            impression,
            "",
            "Surgically relevant features:",
            surgical_lines or "- None highlighted.",
            "",
            "Pre-op checklist:",
            checklist_lines or "- Not generated.",
            "",
            "Recommendations:",
            recommendation_lines,
        ]
    )


def _build_finding_rows(
    sinus_findings: Iterable[Dict[str, object]],
    anatomic_variants: Iterable[Dict[str, object]],
    omc_status: Dict[str, Dict[str, str]],
    lund_mackay: Dict[str, object],
    surgical_summary: Dict[str, object],
) -> List[Dict[str, str]]:
    rows: List[Dict[str, str]] = []
    for finding in sinus_findings:
        if finding["severity"] == "none":
            continue
        rows.append(
            {
                "category": "Sinus",
                "structure": finding["label"],
                "status": finding["pattern"],
                "details": f"Air {finding['airFraction']:.2f}, opacified {finding['opacifiedFraction']:.2f}",
            }
        )
    for side in ("left", "right"):
        rows.append(
            {
                "category": "OMC",
                "structure": "Left OMC" if side == "left" else "Right OMC",
                "status": omc_status[side]["state"],
                "details": omc_status[side]["message"],
            }
        )
    for variant in anatomic_variants:
        rows.append(
            {
                "category": "Variant",
                "structure": variant["code"],
                "status": variant["importance"],
                "details": variant["message"],
            }
        )
    rows.append(
        {
            "category": "Score",
            "structure": "Lund-Mackay",
            "status": str(lund_mackay.get("totalScore", 0)),
            "details": " | ".join(f"{item['region']}={item['score']}" for item in lund_mackay.get("regionScores", [])[:8]),
        }
    )
    for line in surgical_summary.get("summaryLines", []):
        rows.append({"category": "Surgery", "structure": "FESS planning", "status": "note", "details": line})
    return rows


def _compress_sinusitis_hints(hints: List[Dict[str, object]]) -> List[str]:
    per_side_groups: Dict[str, List[str]] = {"left": [], "right": []}
    for hint in hints:
        if hint.get("code") != "sinusitis_pattern":
            continue
        segment = str(hint.get("segment", ""))
        group, side = _split_root_and_side(segment)
        readable_group = {
            "sinus_maxillary": "maxillary sinus",
            "sinus_frontal": "frontal sinus",
            "sinus_ethmoid": "ethmoid cells",
            "sinus_sphenoid": "sphenoid sinus",
        }.get(group, group)
        per_side_groups[side].append(readable_group)
    lines: List[str] = []
    for side in ("right", "left"):
        groups = sorted(set(per_side_groups[side]))
        if groups:
            side_label = "Right-sided" if side == "right" else "Left-sided"
            lines.append(f"CT features of {side_label.lower()} rhinosinusitis involving: {', '.join(groups)}.")
    if not lines:
        return [hint["message"] for hint in hints[:3]]
    return lines


def _find_sinus(findings: Iterable[Dict[str, object]], sinus_root: str, side: str) -> Optional[Dict[str, object]]:
    for finding in findings:
        if finding["sinus"] == sinus_root and finding["side"] == side:
            return finding
    return None


def _has_probable_fluid_level(row: Dict[str, object]) -> bool:
    air_fraction = float(row.get("air_fraction", 0.0))
    fluid_fraction = float(row.get("fluid_fraction", 0.0))
    inferior_soft_fraction = float(row.get("inferior_soft_fraction", 0.0))
    superior_soft_fraction = float(row.get("superior_soft_fraction", 0.0))
    return fluid_fraction >= 0.1 and air_fraction >= 0.1 and inferior_soft_fraction > (superior_soft_fraction + 0.2)


def _split_root_and_side(segment_name: str) -> Tuple[str, str]:
    if segment_name.endswith("_left"):
        return segment_name[: -len("_left")], "left"
    if segment_name.endswith("_right"):
        return segment_name[: -len("_right")], "right"
    return segment_name, "unknown"


def _build_lund_mackay_score(sinus_findings: Iterable[Dict[str, object]], omc_status: Dict[str, Dict[str, str]]) -> Dict[str, object]:
    region_scores: List[Dict[str, object]] = []
    total = 0
    for finding in sinus_findings:
        opacified_fraction = float(finding.get("opacifiedFraction", 0.0))
        score = 0 if opacified_fraction < 0.1 else 1 if opacified_fraction < 0.9 else 2
        region_scores.append({"region": finding["label"], "score": score})
        total += score
    for side in ("right", "left"):
        state = omc_status.get(side, {}).get("state")
        score = 2 if state in {"blocked", "possibly_blocked"} else 1 if state == "partially_blocked" else 0
        region_scores.append({"region": f"{side.title()} OMC", "score": score})
        total += score
    return {"totalScore": total, "regionScores": region_scores}


def _build_surgical_summary(
    sinus_findings: Iterable[Dict[str, object]],
    omc_status: Dict[str, Dict[str, str]],
    anatomic_variants: Iterable[Dict[str, object]],
) -> Dict[str, object]:
    summary_lines: List[str] = []
    risk_factors: List[str] = []
    blocked_sides = [side for side in ("right", "left") if omc_status.get(side, {}).get("state") in {"blocked", "partially_blocked", "possibly_blocked"}]
    if blocked_sides:
        summary_lines.append("Drainage impairment suggested at: " + ", ".join(side.title() for side in blocked_sides) + " OMC.")
        risk_factors.append("omc_drainage_risk")
    severe_sinuses = [finding["label"] for finding in sinus_findings if finding.get("severity") in {"severe", "moderate_to_severe"}]
    if severe_sinuses:
        summary_lines.append("Highest inflammatory burden: " + "; ".join(severe_sinuses[:4]) + ".")
        risk_factors.append("high_opacification_burden")
    relevant_variants = [variant["message"] for variant in anatomic_variants if variant.get("importance") == "fess_relevant"]
    if relevant_variants:
        summary_lines.append("Anatomic factors to review before FESS: " + "; ".join(relevant_variants[:4]))
        risk_factors.append("fess_anatomic_variants")
    hypoplasia = [variant["message"] for variant in anatomic_variants if variant.get("code") == "sinus_hypoplasia_candidate"]
    if hypoplasia:
        summary_lines.append("Possible hypoplastic sinus anatomy: " + "; ".join(hypoplasia[:2]))
        risk_factors.append("sinus_hypoplasia")
    if not summary_lines:
        summary_lines.append("No major automatically detected pre-FESS risk features were highlighted.")
    return {"summaryLines": summary_lines, "riskFactors": risk_factors}


def _build_preop_checklist(
    sinus_findings: Iterable[Dict[str, object]],
    omc_status: Dict[str, Dict[str, str]],
    anatomic_variants: Iterable[Dict[str, object]],
) -> List[Dict[str, object]]:
    variant_messages = [variant.get("message", "") for variant in anatomic_variants]
    has_septal = any("septal" in message.lower() for message in variant_messages)
    has_concha = any("concha bullosa" in message.lower() for message in variant_messages)
    return [
        {
            "item": "OMC patency reviewed",
            "status": "attention" if any(omc_status[side]["state"] in {"blocked", "partially_blocked", "possibly_blocked"} for side in ("left", "right")) else "ok",
            "note": "Check drainage pathways before treatment planning.",
        },
        {
            "item": "Septal deviation",
            "status": "present" if has_septal else "not_flagged",
            "note": "Deviation may affect corridor planning.",
        },
        {
            "item": "Concha bullosa",
            "status": "present" if has_concha else "not_flagged",
            "note": "Review middle turbinate anatomy.",
        },
        {
            "item": "High inflammatory burden",
            "status": "attention" if any(finding.get("severity") in {"severe", "moderate_to_severe"} for finding in sinus_findings) else "low",
            "note": "Correlate with symptoms and endoscopy.",
        },
    ]


def _build_patient_summary(
    sinus_findings: Iterable[Dict[str, object]],
    omc_status: Dict[str, Dict[str, str]],
    anatomic_variants: Iterable[Dict[str, object]],
) -> str:
    abnormal = [finding for finding in sinus_findings if finding.get("severity") != "none"]
    if not abnormal:
        return "The sinus cavities look mostly open on this automated review. Please discuss the scan together with your ENT specialist."
    sides = sorted({finding.get("side") for finding in abnormal})
    side_text = "both sides" if len(sides) > 1 else ("the right side" if "right" in sides else "the left side")
    omc_issue = any(omc_status[side]["state"] in {"blocked", "partially_blocked", "possibly_blocked"} for side in ("left", "right"))
    variant_issue = any(variant.get("importance") == "fess_relevant" for variant in anatomic_variants)
    lines = [f"The automated review suggests inflammatory change involving {side_text} of the sinus system."]
    if omc_issue:
        lines.append("There may also be narrowing or blockage in the drainage pathway.")
    if variant_issue:
        lines.append("Some anatomic differences were also flagged that may matter if surgery is being considered.")
    lines.append("This is a support summary and should be confirmed by your doctor.")
    return " ".join(lines)
