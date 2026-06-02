# AI-Assisted CT Sinus Reporting Workflow

This repository now includes a dedicated `CT PNS: AI-assisted sinus report` workflow aimed at `clinical decision support`, not autonomous diagnosis.

## Architecture

1. `3D Slicer`
   - DICOM loading
   - 2D/3D visualization
   - segmentation review
   - findings table
   - structured export

2. `Open-source segmentation backbones`
   - `TotalSegmentator` for baseline craniofacial anatomy bootstrapping
   - `MONAI Label` for interactive annotation and future custom app deployment
   - `nnU-Net v2` for future supervised sinus CT model training/inference

3. `Sinus interpretation layer`
   - per-sinus aeration/opacification estimation
   - probable fluid-level heuristics
   - probable OMC obstruction logic
   - anatomic-variant flags relevant to FESS
   - approximate Lund-Mackay burden scoring
   - FESS-oriented planning notes
   - deterministic text generation

4. `Report generator`
   - `Description`
   - `Impression`
   - `Recommendations for ENT`

## Current rule coverage

The present implementation can already draft findings for:

- maxillary, frontal, ethmoid, and sphenoid sinus involvement
- total or partial opacification patterns
- probable fluid level
- probable septal deviation from nasal cavity asymmetry
- possible sinus hypoplasia
- possible OMC obstruction
- FESS-relevant anatomic variants when represented in the segmentation
- approximate Lund-Mackay scoring
- structured surgical planning notes for endoscopic sinus surgery review

## 3D visualization layer

The Slicer module now exposes three immediate visualization helpers:

- `Prepare 3D sinus view`
  - emphasizes sinus cavities against semitransparent bone rendering
- `Internal head view`
  - increases visibility of internal cavities and reduces bone dominance
- `FESS planning view`
  - highlights OMC, nasal septum, and related structures when available

These are not just cosmetic views. They are intended to make preoperative review faster inside the same Slicer workflow.

## Report modes

The workflow now supports three immediate report modes without rerunning segmentation:

- `assistant`
  - balanced AI-assisted ENT summary
- `radiology`
  - conservative imaging wording
- `surgeon`
  - emphasizes FESS corridor, drainage pathways, and pre-op relevance

After a segmentation is already available, the module can regenerate the report text through `Recompute last report from segmentation`.

## Export

Current report export options include:

- JSON report
- HTML report
- batch CSV registry

The HTML export is designed as a practical handoff artifact for review outside Slicer.

## What still needs a trained model

The following are architected for, but still benefit from a dedicated sinus model and labeled data:

- direct mucosal-thickening segmentation
- direct liquid segmentation
- direct cyst/polyp segmentation
- direct OMC mask segmentation
- robust concha bullosa detection from dedicated turbinate labels
- quantitative pre-FESS risk scoring

## Data strategy

Recommended path for the custom model:

- start with `100-300` curated CT sinus studies for prototype training
- target `1000+` studies for stronger generalization
- store manual labels in Slicer / MONAI Label-compatible formats
- train `nnU-Net v2` as a baseline benchmark
- expose inference inside Slicer through either:
  - a custom `MONAI Label` app
  - a local `nnU-Net` inference wrapper

## Safety note

This workflow should be presented as:

- `AI-assisted CT sinus reporting tool`
- `decision-support system for paranasal sinus CT`

It should not be presented as a fully autonomous diagnostic system.
