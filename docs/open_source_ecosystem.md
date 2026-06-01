# Open-source ecosystem for ENT Assistant v3

This repository now uses or aligns with the following open-source projects:

## Integrated directly

- [TotalSegmentator](https://github.com/wasserth/totalsegmentator)
  Used for AI presets relevant to ENT and head CT:
  - `head_glands_cavities`
  - `headneck_bones_vessels`
  - `craniofacial_structures`
  Also used as design reference for:
  - `fast` inference mode
  - `robust_crop`
  - CPU execution fallback

## Checked by the module

- [SlicerTotalSegmentator](https://github.com/lassoan/SlicerTotalSegmentator)
- [SlicerSegmentEditorExtraEffects](https://github.com/lassoan/SlicerSegmentEditorExtraEffects)
- [MONAI Label](https://github.com/Project-MONAI/MONAILabel)
- [SlicerNNInteractive](https://github.com/coendevente/SlicerNNInteractive)
- [Raidionics-Slicer](https://github.com/raidionics/Raidionics-Slicer)
- [CloudSegmentatorResults](https://github.com/ImagingDataCommons/CloudSegmentatorResults)

## Why these matter

- `TotalSegmentator` provides strong open-source baseline anatomical segmentation for CT.
- `SegmentEditorExtraEffects` is useful when the automatic result needs ENT-specific cleanup around narrow airways or sinus borders.
- `MONAI Label` and `SlicerNNInteractive` are good next steps if this project evolves into interactive annotation or dataset-building workflows for ENT/head pathology.
- `Raidionics-Slicer` is a useful open-source reference for standardized report generation patterns inside 3D Slicer.
- `CloudSegmentatorResults` is a useful open-source reference for rule-based segmentation QC, especially volume sanity checks and suspicious-output filtering.
- Slicer core export documentation is the reference for writing segmentation outputs as `.seg.nrrd`, labelmaps, and surface files.
- Batch-style report indexing in this project follows the same general open-source principle of reproducible per-case outputs plus a machine-readable aggregate index.
