# ENT Assistant v3

ENT Assistant v3 is a 3D Slicer helper module for ENT and head CT analysis. The starting repository was only a simple launcher around ad-hoc scripts; this version adds actual presets, reusable pipeline code, optional open-source AI segmentation, and report generation.

## Added capabilities

- Structured Slicer UI with analysis presets.
- Safe module loading instead of raw `exec(open(...).read())`.
- Optional integration with [TotalSegmentator](https://github.com/wasserth/totalsegmentator) for open-source head and neck segmentation tasks.
- Fallback threshold-based segmentation for bone, air, and soft tissue.
- Volume measurement report export to `reports/*.json`.
- Structured report draft inspired by open-source clinical reporting workflows.
- Rule-based QC checks for suspicious or incomplete segmentations.
- Export pipeline for `.seg.nrrd`, `.nii.gz` labelmaps, and optional STL surfaces.
- AI runtime options inspired by SlicerTotalSegmentator, including `fast`, CPU mode, and `robust_crop`.
- Batch analysis mode for processing all loaded CT volumes in one run.
- ENT-oriented summary for airway/cavity structures and left/right asymmetry.
- Batch CSV registry for downstream triage, QA and spreadsheet workflows.
- Heuristic ENT flags for possible reduced aeration and notable nasal asymmetry.
- Pairwise follow-up comparison between sequential or first-two loaded studies.
- DICOM-oriented study metadata export when volumes come from Slicer DICOM loading.
- Shared core helpers for presets and report naming.

## Open-source references used

- [TotalSegmentator](https://github.com/wasserth/totalsegmentator)
- [SlicerSegmentEditorExtraEffects](https://github.com/lassoan/SlicerSegmentEditorExtraEffects)
- [Raidionics-Slicer](https://github.com/raidionics/Raidionics-Slicer)
- [CloudSegmentatorResults](https://github.com/ImagingDataCommons/CloudSegmentatorResults)

The current presets use the public TotalSegmentator tasks `head_glands_cavities`, `headneck_bones_vessels`, and `craniofacial_structures`, which are directly relevant to ENT and head CT workflows.

## Presets

- `ENT CT: bone + airway`
- `Head & neck AI preset`
- `Craniofacial AI preset`
- `Larynx and hyoid AI preset`

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

## Heuristic flags

The module can add non-diagnostic heuristic flags such as:

- `possible_reduced_aeration`
- `possible_nasal_asymmetry`

These are screening-style computational hints only, not clinical conclusions.

## DICOM and comparison

When a volume was loaded from the Slicer DICOM database, the report can include patient/study/series metadata fields already available in the local DICOM index.

Comparison mode summarizes overlapping segment deltas between consecutive cases in batch mode or between the first two loaded studies in `compare_first_two`.

## Installing AI support

Install TotalSegmentator in the Python environment available to 3D Slicer, or expose the `TotalSegmentator` CLI in `PATH`.

```bash
pip install TotalSegmentator
```

If it is not available, the module falls back to classical threshold segmentation automatically.

## Important note

This is a research/development aid and not a certified medical device.
