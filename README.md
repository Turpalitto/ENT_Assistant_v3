# ENT Assistant v3

ENT Assistant v3 is a 3D Slicer helper module for ENT and head CT analysis. The starting repository was only a simple launcher around ad-hoc scripts; this version adds actual presets, reusable pipeline code, optional open-source AI segmentation, and report generation.

The newest workflow also targets `AI-assisted CT sinus reporting` for paranasal sinus CT studies, with sinus-focused anatomy tracking, pathology heuristics, OMC status estimation, anatomic-variant flags, and draft radiology-style text output.
The project now also includes an `ENT / temporal bone MRI support` workflow for MRI sequence-aware ENT review, patient summary, and structured support reporting.

## Added capabilities

- Structured Slicer UI with analysis presets.
- Safe module loading instead of raw `exec(open(...).read())`.
- Optional integration with [TotalSegmentator](https://github.com/wasserth/totalsegmentator) for open-source head and neck segmentation tasks.
- Fallback threshold-based segmentation for bone, air, and soft tissue.
- Volume measurement report export to `reports/*.json`.
- Structured report draft inspired by open-source clinical reporting workflows.
- Dedicated `CT PNS: AI-assisted sinus report` preset for paranasal sinus CT.
- Dedicated `ENT / temporal bone MRI support` preset for MRI sequence-aware ENT review.
- Rule-based QC checks for suspicious or incomplete segmentations.
- Export pipeline for `.seg.nrrd`, `.nii.gz` labelmaps, and optional STL surfaces.
- AI runtime options inspired by SlicerTotalSegmentator, including `fast`, CPU mode, and `robust_crop`.
- Batch analysis mode for processing all loaded CT volumes in one run.
- ENT-oriented summary for airway/cavity structures and left/right asymmetry.
- Batch CSV registry for downstream triage, QA and spreadsheet workflows.
- Heuristic ENT flags for possible reduced aeration and notable nasal asymmetry.
- Pairwise follow-up comparison between sequential or first-two loaded studies.
- DICOM-oriented study metadata export when volumes come from Slicer DICOM loading.
- Auto-grouped longitudinal timeline by `PatientID + StudyDate`.
- RTSTRUCT readiness layer for SlicerRT-aware environments.
- Narrower ENT pathology-oriented rules for sinus aeration, nasal passages, laryngeal air column and pharyngeal disproportion.
- Sinus CT rule engine for opacification pattern, possible fluid level, likely OMC obstruction, probable septal deviation, possible hypoplasia, and FESS-relevant anatomy flags.
- Draft radiology report sections: `Description`, `Impression`, and `Recommendations for ENT`.
- Findings table in the Slicer UI for sinus findings, OMC status, and anatomic variants.
- 3D visualization helpers for sinus-focused, internal-head, and FESS-planning views.
- Report-mode switcher: `assistant`, `radiology`, `surgeon`.
- HTML report export and recompute-from-segmentation workflow.
- Auto screenshots for HTML reports.
- Modality-aware screenshot capture: CT gets 3D + slice views, MRI gets slice-first evidence views without noisy CT-style 3D rendering.
- Explainability/evidence section in HTML reports based on structured finding rows.
- One-click `Radiology` and `FESS` report buttons.
- DICOM import helper and case-bundle export helper in the Slicer UI.
- `AI runtime advisor` button with per-framework fit summary for the current workstation.
- `Export AI workspace` button that writes image/label artifacts plus nnU-Net-friendly workspace layout and command templates.
- Open-source stack check with local runtime profile for Torch, MONAI, SimpleITK, and NVIDIA GPU readiness.
- Shared core helpers for presets and report naming.

## Open-source references used

- [TotalSegmentator](https://github.com/wasserth/totalsegmentator)
- [nnU-Net](https://github.com/MIC-DKFZ/nnUNet)
- [MONAI Label](https://github.com/project-monai/monailabel)
- [MONAI](https://github.com/project-monai/monai)
- [SlicerSegmentEditorExtraEffects](https://github.com/lassoan/SlicerSegmentEditorExtraEffects)
- [Raidionics-Slicer](https://github.com/raidionics/Raidionics-Slicer)
- [CloudSegmentatorResults](https://github.com/ImagingDataCommons/CloudSegmentatorResults)
- [SlicerAirwaySegmentation](https://github.com/Slicer/SlicerAirwaySegmentation)
- [Explainable CT AI](https://github.com/rachellea/explainable-ct-ai)
- [AI-Powered MRI Viewer](https://github.com/albertovalverde/AI-Powered-MRI-Viewer)

The current presets use the public TotalSegmentator tasks `head_glands_cavities`, `headneck_bones_vessels`, and `craniofacial_structures`, which are directly relevant to ENT and head CT workflows. The sinus CT preset builds a sinus-specific rule layer on top of these anatomical masks, while leaving room for a future custom `nnU-Net` / `MONAI Label` sinus model. The runtime stack check now also reports whether `MONAI` is actually available inside Slicer Python, because many workstations end up with CPU-only Torch in Slicer and GPU-enabled AI in a separate environment.

## Presets

- `CT PNS: AI-assisted sinus report`
- `ENT / temporal bone MRI support`
- `ENT CT: bone + airway`
- `Head & neck AI preset`
- `Craniofacial AI preset`
- `Larynx and hyoid AI preset`

## Sinus CT workflow

The `CT PNS: AI-assisted sinus report` preset is designed as a clinician-support workflow, not a standalone diagnosis engine. It currently does the following:

- bootstraps anatomy from available open-source segmentation outputs
- splits combined sinus masks into left/right measurement rows when needed
- estimates sinus aeration and soft-tissue occupancy from CT intensities inside the segmented cavities
- flags likely total opacification, partial opacification, probable fluid level, likely OMC obstruction, probable septal deviation, possible sinus hypoplasia, and FESS-relevant variants when enough evidence is present
- estimates an approximate Lund-Mackay-style burden score from opacification and OMC status
- generates a short surgical-planning summary for FESS-oriented review
- writes structured draft sections:
  - `Description`
  - `Impression`
  - `Recommendations for ENT`

After analysis, the module can also prepare three built-in 3D visualization modes in Slicer:

- `Prepare 3D sinus view`
- `Internal head view`
- `FESS planning view`

These views use volume rendering plus styled segment colors/opacities to better expose bone, internal sinus cavities, nasal cavity, septum, and OMC-related structures in the 3D window.

The module now also supports:

- `report mode = assistant`
  - balanced ENT support summary
- `report mode = radiology`
  - more conservative imaging-style summary
- `report mode = surgeon`
  - emphasizes drainage pathways and FESS-relevant anatomy

You can switch report mode and then use `Recompute last report from segmentation` to regenerate the report without rerunning AI segmentation.

The UI also now includes:

- `Radiology one-click report`
- `FESS one-click report`
- `MRI one-click report`
- `Import DICOM folder`
- `Export current case bundle`

The exported case bundle can include the JSON report, HTML report, screenshots, and export directory contents when available.
For MRI, the HTML export now favors axial/coronal/sagittal slice evidence instead of CT-like 3D screenshots, to keep the viewer clinically readable.
The `Export AI workspace` action now also prepares:

- `image.nii.gz`
- `segmentation.seg.nrrd`
- `labelmap.nii.gz`
- `nnunet_workspace/imagesTs/<case>_0000.nii.gz`
- `nnunet_workspace/labelsTs/<case>.nii.gz` when labels exist
- `nnunet_workspace/dataset.json`
- starter `.cmd` templates for `TotalSegmentator`, `MONAI Label`, and `nnU-Net`

This is intentionally template-driven and conservative. The current implementation favors reproducible wording over free-form generative text.

## Export outputs

When enabled in the module UI, analysis results can be exported to:

- `exports/<case>__<preset>/segmentation.seg.nrrd`
- `exports/<case>__<preset>/segmentation_labelmap.nii.gz`
- optional STL surfaces for per-segment 3D models

## Batch mode

The module can now analyze:

- only the active volume
- all loaded scalar volumes in the current Slicer scene
- the first two loaded scalar volumes as a follow-up comparison pair

Batch runs write per-case JSON reports plus `reports/batch_index.json`.
They also write `reports/batch_registry.csv` for quick review in Excel/Sheets.
If at least two cases are processed, they also write `reports/comparison_index.json`.
Longitudinal runs also write `reports/longitudinal_timeline.json`.

## Heuristic flags

The module can add non-diagnostic heuristic flags such as:

- `possible_reduced_aeration`
- `possible_nasal_asymmetry`

These are screening-style computational hints only, not clinical conclusions.

## Future model path

The intended production architecture for sinus CT is:

- `3D Slicer` for visualization, segmentation review, export, and findings table
- `nnU-Net` or `MONAI Label` for custom sinus/pathology segmentation
- deterministic sinus rules for interpretation
- structured report generator for radiology-style draft text

The current repository implements the Slicer shell, reporting logic, and open-source integration points. A dedicated custom sinus model still requires labeled CT training data.

## DICOM and comparison

When a volume was loaded from the Slicer DICOM database, the report can include patient/study/series metadata fields already available in the local DICOM index.

Comparison mode summarizes overlapping segment deltas between consecutive cases in batch mode or between the first two loaded studies in `compare_first_two`.

## RTSTRUCT readiness

The module now checks whether the current 3D Slicer environment looks ready for RTSTRUCT export:

- SlicerRT-related module detected
- `DicomRtImportExportPlugin` available in-session
- Slicer DICOM database available
- volume loaded with DICOM instance UIDs

When readiness passes, the module attempts scripted RTSTRUCT export through SlicerRT's `DicomRtImportExportPlugin` by exporting both the primary anatomical CT volume and the segmentation together.

## Installing AI support

Install TotalSegmentator in the Python environment available to 3D Slicer, or expose the `TotalSegmentator` CLI in `PATH`.

```bash
pip install TotalSegmentator
```

If it is not available, the module falls back to classical threshold segmentation automatically.

## Important note

This is a research/development aid and not a certified medical device.
