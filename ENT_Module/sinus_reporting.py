from __future__ import annotations

from typing import Dict, Iterable, List, Optional, Tuple


SINUS_LABELS = {
    "sinus_maxillary_left": "левая верхнечелюстная пазуха",
    "sinus_maxillary_right": "правая верхнечелюстная пазуха",
    "sinus_frontal_left": "левая лобная пазуха",
    "sinus_frontal_right": "правая лобная пазуха",
    "sinus_ethmoid_left": "левые клетки решетчатого лабиринта",
    "sinus_ethmoid_right": "правые клетки решетчатого лабиринта",
    "sinus_sphenoid_left": "левая клиновидная пазуха",
    "sinus_sphenoid_right": "правая клиновидная пазуха",
}

SINUS_GROUPS = {
    "maxillary": ("sinus_maxillary_left", "sinus_maxillary_right"),
    "frontal": ("sinus_frontal_left", "sinus_frontal_right"),
    "ethmoid": ("sinus_ethmoid_left", "sinus_ethmoid_right"),
    "sphenoid": ("sinus_sphenoid_left", "sinus_sphenoid_right"),
}

SINUS_SMALL_VOLUME_THRESHOLDS_ML = {
    "sinus_maxillary": 4.0,
    "sinus_frontal": 1.5,
    "sinus_ethmoid": 1.0,
    "sinus_sphenoid": 1.5,
}


def build_ct_sinus_report(measurements: Iterable[Dict[str, object]], study_info: Optional[Dict[str, object]] = None) -> Dict[str, object]:
    rows = list(measurements)
    by_name = {str(row.get("segment", "")): row for row in rows}
    sinus_findings = _build_sinus_findings(by_name)
    anatomic_variants = _build_anatomic_variants(by_name, sinus_findings)
    omc_status = _build_omc_status(by_name, sinus_findings)
    diagnosis_hints = _build_diagnosis_hints(sinus_findings, omc_status)
    lund_mackay = _build_lund_mackay_score(sinus_findings, omc_status)
    surgical_summary = _build_surgical_summary(sinus_findings, omc_status, anatomic_variants)
    description = _build_description(sinus_findings, anatomic_variants, omc_status)
    impression_lines = _build_impression_lines(diagnosis_hints, omc_status, anatomic_variants)
    recommendations = _build_recommendations(diagnosis_hints, omc_status, anatomic_variants, study_info or {})
    return {
        "studyModality": (study_info or {}).get("dicomModality"),
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
        "reportText": _build_report_text(description, impression_lines, recommendations, lund_mackay, surgical_summary),
        "findingRows": _build_finding_rows(sinus_findings, anatomic_variants, omc_status, lund_mackay, surgical_summary),
        "disclaimer": "AI-assisted sinus CT reporting support. Final interpretation remains with the physician.",
    }


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
        if opacified_fraction >= 0.9:
            pattern = "тотальное затемнение"
            severity = "severe"
        elif opacified_fraction >= 0.5:
            pattern = "выраженная частичная опацификация"
            severity = "moderate_to_severe"
        elif opacified_fraction >= 0.2:
            pattern = "умеренная пристеночная/частичная опацификация"
            severity = "moderate"
        elif opacified_fraction >= 0.08:
            pattern = "легкие признаки пристеночного утолщения слизистой"
            severity = "mild"
        else:
            pattern = "аэрация сохранена"
            severity = "none"

        fluid_level = _has_probable_fluid_level(row)
        root_name, side = _split_root_and_side(segment_name)
        finding = {
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
            "probableFluidLevel": fluid_level,
            "likelyInflammatory": severity != "none",
        }
        findings.append(finding)

    _annotate_hypoplasia(findings)
    return findings


def _annotate_hypoplasia(findings: List[Dict[str, object]]) -> None:
    by_group: Dict[str, List[Dict[str, object]]] = {}
    for finding in findings:
        by_group.setdefault(str(finding["sinus"]), []).append(finding)

    for sinus_name, pair in by_group.items():
        if len(pair) != 2:
            continue
        left, right = sorted(pair, key=lambda item: str(item["side"]))
        smaller = left if float(left["volumeMl"]) <= float(right["volumeMl"]) else right
        larger = right if smaller is left else left
        threshold = SINUS_SMALL_VOLUME_THRESHOLDS_ML.get(sinus_name, 1.0)
        smaller_volume = float(smaller["volumeMl"])
        larger_volume = max(float(larger["volumeMl"]), 0.01)
        if smaller_volume < threshold and (smaller_volume / larger_volume) <= 0.6:
            smaller["hypoplasiaCandidate"] = True
            smaller["pattern"] += "; вероятная гипоплазия"
        else:
            smaller["hypoplasiaCandidate"] = False
        larger.setdefault("hypoplasiaCandidate", False)


def _build_anatomic_variants(by_name: Dict[str, Dict[str, object]], sinus_findings: List[Dict[str, object]]) -> List[Dict[str, object]]:
    variants: List[Dict[str, object]] = []

    nasal_left = float(by_name.get("nasal_cavity_left", {}).get("volume_ml", 0.0))
    nasal_right = float(by_name.get("nasal_cavity_right", {}).get("volume_ml", 0.0))
    if nasal_left > 0 and nasal_right > 0:
        ratio = max(nasal_left, nasal_right) / max(min(nasal_left, nasal_right), 0.01)
        if ratio >= 1.6:
            deviation_side = "влево" if nasal_left < nasal_right else "вправо"
            variants.append(
                {
                    "code": "probable_septal_deviation",
                    "message": f"Вероятное искривление перегородки носа {deviation_side}.",
                    "importance": "fess_relevant",
                }
            )

    for finding in sinus_findings:
        if finding.get("hypoplasiaCandidate"):
            variants.append(
                {
                    "code": "sinus_hypoplasia_candidate",
                    "message": f"Вероятная гипоплазия: {finding['label']}.",
                    "importance": "variant",
                }
            )

    for side in ("left", "right"):
        for candidate in (
            f"concha_bullosa_{side}",
            f"middle_turbinate_pneumatized_{side}",
            f"middle_turbinate_{side}",
        ):
            row = by_name.get(candidate)
            if not row:
                continue
            if "concha_bullosa" in candidate or float(row.get("air_fraction", 0.0)) >= 0.5:
                side_label = "слева" if side == "left" else "справа"
                variants.append(
                    {
                        "code": f"concha_bullosa_{side}",
                        "message": f"Concha bullosa средней носовой раковины {side_label}.",
                        "importance": "fess_relevant",
                    }
                )
                break

    for key, title in (
        ("retention_cyst", "ретенционная киста"),
        ("polyp", "полиповидное образование"),
    ):
        for segment_name in by_name:
            if key not in segment_name:
                continue
            variants.append(
                {
                    "code": key,
                    "message": f"Выявлен сегмент, совместимый с {title}: {segment_name}.",
                    "importance": "pathology",
                }
            )

    return variants


def _build_omc_status(by_name: Dict[str, Dict[str, object]], sinus_findings: List[Dict[str, object]]) -> Dict[str, object]:
    status = {
        "left": {"state": "indeterminate", "message": "Недостаточно данных для прямой оценки ОМК слева."},
        "right": {"state": "indeterminate", "message": "Недостаточно данных для прямой оценки ОМК справа."},
    }

    for side in ("left", "right"):
        direct = by_name.get(f"ostiomeatal_complex_{side}") or by_name.get(f"omc_{side}")
        if direct:
            air_fraction = float(direct.get("air_fraction", 0.0))
            opacified_fraction = 1.0 - air_fraction
            if opacified_fraction >= 0.7:
                status[side] = {"state": "blocked", "message": f"ОМК {('слева' if side == 'left' else 'справа')} блокирован."}
            elif opacified_fraction >= 0.3:
                status[side] = {
                    "state": "partially_blocked",
                    "message": f"ОМК {('слева' if side == 'left' else 'справа')} частично блокирован.",
                }
            else:
                status[side] = {"state": "patent", "message": f"ОМК {('слева' if side == 'left' else 'справа')} проходим."}
            continue

        maxillary = _find_sinus(sinus_findings, "sinus_maxillary", side)
        ethmoid = _find_sinus(sinus_findings, "sinus_ethmoid", side)
        frontal = _find_sinus(sinus_findings, "sinus_frontal", side)
        supporting_count = 0
        if maxillary and float(maxillary["opacifiedFraction"]) >= 0.5:
            supporting_count += 1
        if ethmoid and float(ethmoid["opacifiedFraction"]) >= 0.5:
            supporting_count += 1
        if frontal and float(frontal["opacifiedFraction"]) >= 0.5:
            supporting_count += 1
        if supporting_count >= 2:
            status[side] = {
                "state": "possibly_blocked",
                "message": f"Вероятна обструкция ОМК {('слева' if side == 'left' else 'справа')}.",
            }
        elif supporting_count == 1:
            status[side] = {
                "state": "possibly_narrowed",
                "message": f"Возможное сужение ОМК {('слева' if side == 'left' else 'справа')}.",
            }

    return status


def _build_diagnosis_hints(sinus_findings: List[Dict[str, object]], omc_status: Dict[str, Dict[str, str]]) -> List[Dict[str, object]]:
    hints: List[Dict[str, object]] = []
    for finding in sinus_findings:
        if finding["severity"] == "none":
            continue
        side = "правостороннего" if finding["side"] == "right" else "левостороннего"
        sinus_label = {
            "sinus_maxillary": "верхнечелюстного синусита",
            "sinus_frontal": "фронтита",
            "sinus_ethmoid": "этмоидита",
            "sinus_sphenoid": "сфеноидита",
        }.get(str(finding["sinus"]), "синусита")
        qualifier = "с вероятным уровнем жидкости" if finding.get("probableFluidLevel") else finding["pattern"]
        hints.append(
            {
                "code": "sinusitis_pattern",
                "segment": finding["segment"],
                "message": f"КТ-признаки {side} {sinus_label}: {qualifier}.",
            }
        )

    for side in ("left", "right"):
        omc = omc_status[side]
        if omc["state"] in {"blocked", "partially_blocked", "possibly_blocked"}:
            side_label = "слева" if side == "left" else "справа"
            hints.append(
                {
                    "code": "omc_obstruction",
                    "side": side,
                    "message": f"Признаки нарушения дренажа через ОМК {side_label}.",
                }
            )
    return hints


def _build_description(
    sinus_findings: List[Dict[str, object]],
    anatomic_variants: List[Dict[str, object]],
    omc_status: Dict[str, Dict[str, str]],
) -> str:
    lines: List[str] = []
    abnormal_findings = [finding for finding in sinus_findings if finding["severity"] != "none"]
    if not abnormal_findings:
        lines.append("Пневматизация околоносовых пазух в целом сохранена.")
    else:
        for finding in abnormal_findings:
            text = f"{finding['label']}: {finding['pattern']}"
            if finding.get("probableFluidLevel"):
                text += ", возможен уровень жидкости"
            text += "."
            lines.append(text)

    for side in ("right", "left"):
        message = omc_status[side]["message"]
        if omc_status[side]["state"] != "indeterminate":
            lines.append(message)

    for variant in anatomic_variants:
        lines.append(variant["message"])

    return "\n".join(lines)


def _build_impression_lines(
    diagnosis_hints: List[Dict[str, object]],
    omc_status: Dict[str, Dict[str, str]],
    anatomic_variants: List[Dict[str, object]],
) -> List[str]:
    lines: List[str] = []
    if diagnosis_hints:
        lines.extend(_compress_sinusitis_hints(diagnosis_hints))
    else:
        lines.append("Явных КТ-признаков значимого синусита не выявлено по доступным сегментам.")

    omc_lines = [row["message"] for row in omc_status.values() if row["state"] in {"blocked", "partially_blocked", "possibly_blocked"}]
    lines.extend(omc_lines[:2])

    fess_variants = [row["message"] for row in anatomic_variants if row.get("importance") == "fess_relevant"]
    if fess_variants:
        lines.append("Анатомические варианты, значимые перед FESS: " + "; ".join(fess_variants[:3]))
    return lines


def _build_recommendations(
    diagnosis_hints: List[Dict[str, object]],
    omc_status: Dict[str, Dict[str, str]],
    anatomic_variants: List[Dict[str, object]],
    study_info: Dict[str, object],
) -> List[str]:
    recommendations = []
    modality = str(study_info.get("dicomModality") or "").upper()
    if modality and modality != "CT":
        recommendations.append("Алгоритм рентгенологического режима оптимизирован под КТ ОНП; для других модальностей интерпретацию следует ограничить.")
    if diagnosis_hints:
        recommendations.append("Рекомендуется сопоставление с клиникой и эндоскопической картиной ЛОР-органов.")
    if any(row["state"] in {"blocked", "partially_blocked", "possibly_blocked"} for row in omc_status.values()):
        recommendations.append("При планировании лечения оценить состояние остеомеатального комплекса и путей дренажа.")
    if any(row.get("importance") == "fess_relevant" for row in anatomic_variants):
        recommendations.append("Учитывать описанные анатомические варианты при предоперационном планировании FESS.")
    if not recommendations:
        recommendations.append("При отсутствии клинических симптомов возможно динамическое наблюдение по стандартной ЛОР-тактике.")
    return recommendations


def _build_report_text(
    description: str,
    impression_lines: Iterable[str],
    recommendations: Iterable[str],
    lund_mackay: Dict[str, object],
    surgical_summary: Dict[str, object],
) -> str:
    impression = "\n".join(f"- {line}" for line in impression_lines)
    recommendation_lines = "\n".join(f"- {line}" for line in recommendations)
    surgical_lines = "\n".join(f"- {line}" for line in surgical_summary.get("summaryLines", []))
    return "\n".join(
        [
            "Описание:",
            description or "Нет данных.",
            "",
            "Оценка распространенности:",
            f"Lund-Mackay (approx.): {lund_mackay.get('totalScore', 0)} / 24",
            "",
            "Заключение:",
            impression,
            "",
            "Хирургически значимые особенности:",
            surgical_lines or "- Не выделены.",
            "",
            "Рекомендации для ЛОР-врача:",
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
                "structure": "ОМК слева" if side == "left" else "ОМК справа",
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
            "details": " | ".join(
                f"{item['region']}={item['score']}" for item in lund_mackay.get("regionScores", [])[:8]
            ),
        }
    )
    for line in surgical_summary.get("summaryLines", []):
        rows.append(
            {
                "category": "Surgery",
                "structure": "FESS planning",
                "status": "note",
                "details": line,
            }
        )
    return rows


def _compress_sinusitis_hints(hints: List[Dict[str, object]]) -> List[str]:
    per_side: Dict[str, List[str]] = {"left": [], "right": []}
    per_side_groups: Dict[str, List[str]] = {"left": [], "right": []}
    for hint in hints:
        if hint.get("code") != "sinusitis_pattern":
            continue
        segment = str(hint.get("segment", ""))
        _, side = _split_root_and_side(segment)
        group, _ = _split_root_and_side(segment)
        readable_group = {
            "sinus_maxillary": "верхнечелюстной",
            "sinus_frontal": "лобный",
            "sinus_ethmoid": "решетчатый",
            "sinus_sphenoid": "клиновидный",
        }.get(group, group)
        per_side_groups[side].append(readable_group)
        per_side[side].append(hint["message"])

    lines: List[str] = []
    for side in ("right", "left"):
        groups = sorted(set(per_side_groups[side]))
        if not groups:
            continue
        side_label = "правосторонний" if side == "right" else "левосторонний"
        lines.append(f"КТ-признаки {side_label} риносинусита с вовлечением: {', '.join(groups)}.")
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
        if opacified_fraction < 0.1:
            score = 0
        elif opacified_fraction < 0.9:
            score = 1
        else:
            score = 2
        region_name = f"{finding['label']}"
        region_scores.append({"region": region_name, "score": score})
        total += score
    for side in ("right", "left"):
        state = omc_status.get(side, {}).get("state")
        score = 2 if state in {"blocked", "possibly_blocked"} else 1 if state == "partially_blocked" else 0
        region_scores.append(
            {
                "region": f"ОМК {'справа' if side == 'right' else 'слева'}",
                "score": score,
            }
        )
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
        readable = ", ".join("справа" if side == "right" else "слева" for side in blocked_sides)
        summary_lines.append(f"Есть признаки нарушения дренажа через ОМК: {readable}.")
        risk_factors.append("omc_drainage_risk")

    severe_sinuses = [finding["label"] for finding in sinus_findings if finding.get("severity") in {"severe", "moderate_to_severe"}]
    if severe_sinuses:
        summary_lines.append("Наиболее выраженные изменения: " + "; ".join(severe_sinuses[:4]) + ".")
        risk_factors.append("high_opacification_burden")

    relevant_variants = [variant["message"] for variant in anatomic_variants if variant.get("importance") == "fess_relevant"]
    if relevant_variants:
        summary_lines.append("Анатомические особенности для учета перед FESS: " + "; ".join(relevant_variants[:4]))
        risk_factors.append("fess_anatomic_variants")

    hypoplasia = [variant["message"] for variant in anatomic_variants if variant.get("code") == "sinus_hypoplasia_candidate"]
    if hypoplasia:
        summary_lines.append("Возможные гипоплазированные пазухи: " + "; ".join(hypoplasia[:2]))
        risk_factors.append("sinus_hypoplasia")

    if not summary_lines:
        summary_lines.append("Грубых анатомических факторов риска для FESS по текущим автоматическим правилам не выделено.")

    return {"summaryLines": summary_lines, "riskFactors": risk_factors}
