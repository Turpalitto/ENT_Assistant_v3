from __future__ import annotations

from html import escape
from pathlib import Path
from typing import Dict, Iterable, List, Optional


def write_html_report(target_path: str, payload: Dict[str, object]) -> str:
    path = Path(target_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    html = build_html_report(payload)
    path.write_text(html, encoding="utf-8")
    return str(path)


def build_html_report(payload: Dict[str, object]) -> str:
    study_info = payload.get("studyInfo") or {}
    sinus_report = payload.get("sinusReport") or {}
    quality_checks = payload.get("qualityChecks") or []
    measurements = payload.get("measurements") or []
    checklist = sinus_report.get("preOpChecklist") or []
    report_mode = sinus_report.get("reportMode") or "assistant"

    sections = [
        "<!doctype html>",
        "<html><head><meta charset='utf-8'>",
        "<title>ENT Assistant v3 Report</title>",
        _style_block(),
        "</head><body>",
        f"<h1>ENT Assistant v3 - {escape(str(payload.get('preset', 'Report')))}</h1>",
        f"<p class='muted'>Report mode: {escape(str(report_mode))}</p>",
        "<section><h2>Study</h2>",
        _kv_table(
            [
                ("Volume", payload.get("volumeName")),
                ("Modality", study_info.get("dicomModality")),
                ("Study date", study_info.get("dicomStudyDate")),
                ("Series", study_info.get("dicomSeriesDescription")),
                ("Patient ID", study_info.get("dicomPatientId")),
            ]
        ),
        "</section>",
    ]

    if sinus_report:
        sections.extend(
            [
                "<section><h2>Description</h2>",
                f"<pre>{escape(str(sinus_report.get('description', '')))}</pre>",
                "</section>",
                "<section><h2>Impression</h2>",
                _bullet_list(sinus_report.get("impressionLines") or [sinus_report.get("impression")]),
                "</section>",
                "<section><h2>Recommendations</h2>",
                _bullet_list(sinus_report.get("recommendations") or []),
                "</section>",
                "<section><h2>Surgical Planning</h2>",
                _bullet_list((sinus_report.get("surgicalPlanning") or {}).get("summaryLines") or []),
                "</section>",
                "<section><h2>Pre-op Checklist</h2>",
                _checklist_table(checklist),
                "</section>",
            ]
        )

    sections.extend(
        [
            "<section><h2>Measurements</h2>",
            _measurement_table(measurements),
            "</section>",
            "<section><h2>Quality Checks</h2>",
            _quality_table(quality_checks),
            "</section>",
        ]
    )

    sections.append("</body></html>")
    return "".join(sections)


def _style_block() -> str:
    return """
<style>
body { font-family: Segoe UI, Arial, sans-serif; margin: 24px; color: #1d1d1f; background: #f7f5ef; }
h1, h2 { color: #18324a; }
section { background: white; padding: 16px 18px; border-radius: 12px; margin: 0 0 16px 0; box-shadow: 0 4px 18px rgba(0,0,0,0.06); }
table { border-collapse: collapse; width: 100%; }
th, td { border-bottom: 1px solid #e5e2d8; text-align: left; padding: 8px 10px; vertical-align: top; }
th { background: #f0ece1; }
.muted { color: #6b7280; }
pre { white-space: pre-wrap; font-family: inherit; }
ul { margin: 0; padding-left: 20px; }
</style>
"""


def _kv_table(rows: Iterable[tuple]) -> str:
    body = "".join(
        f"<tr><th>{escape(str(label))}</th><td>{escape('' if value is None else str(value))}</td></tr>" for label, value in rows
    )
    return f"<table>{body}</table>"


def _bullet_list(items: Iterable[object]) -> str:
    rows = [item for item in items if item]
    if not rows:
        return "<p class='muted'>No items.</p>"
    return "<ul>" + "".join(f"<li>{escape(str(item))}</li>" for item in rows) + "</ul>"


def _measurement_table(rows: List[Dict[str, object]]) -> str:
    if not rows:
        return "<p class='muted'>No measurements.</p>"
    head = "<tr><th>Segment</th><th>Volume mL</th><th>Mean HU</th><th>Air frac</th><th>Soft frac</th></tr>"
    body = "".join(
        "<tr>"
        f"<td>{escape(str(row.get('segment', '')))}</td>"
        f"<td>{escape(str(row.get('volume_ml', '')))}</td>"
        f"<td>{escape(str(row.get('mean_hu', '')))}</td>"
        f"<td>{escape(str(row.get('air_fraction', '')))}</td>"
        f"<td>{escape(str(row.get('soft_fraction', '')))}</td>"
        "</tr>"
        for row in rows
    )
    return f"<table>{head}{body}</table>"


def _quality_table(rows: List[Dict[str, object]]) -> str:
    if not rows:
        return "<p class='muted'>No QC items.</p>"
    head = "<tr><th>Level</th><th>Code</th><th>Message</th></tr>"
    body = "".join(
        "<tr>"
        f"<td>{escape(str(row.get('level', '')))}</td>"
        f"<td>{escape(str(row.get('code', '')))}</td>"
        f"<td>{escape(str(row.get('message', '')))}</td>"
        "</tr>"
        for row in rows
    )
    return f"<table>{head}{body}</table>"


def _checklist_table(rows: List[Dict[str, object]]) -> str:
    if not rows:
        return "<p class='muted'>No checklist items.</p>"
    head = "<tr><th>Item</th><th>Status</th><th>Note</th></tr>"
    body = "".join(
        "<tr>"
        f"<td>{escape(str(row.get('item', '')))}</td>"
        f"<td>{escape(str(row.get('status', '')))}</td>"
        f"<td>{escape(str(row.get('note', '')))}</td>"
        "</tr>"
        for row in rows
    )
    return f"<table>{head}{body}</table>"
