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

## Installing AI support

Install TotalSegmentator in the Python environment available to 3D Slicer, or expose the `TotalSegmentator` CLI in `PATH`.

```bash
pip install TotalSegmentator
```

If it is not available, the module falls back to classical threshold segmentation automatically.

## Important note

This is a research/development aid and not a certified medical device.
