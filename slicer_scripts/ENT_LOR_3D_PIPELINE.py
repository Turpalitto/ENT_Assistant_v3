import os
import sys


REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if REPO_ROOT not in sys.path:
    sys.path.insert(0, REPO_ROOT)

from ENT_Module.ent_assistant_core import AnalysisConfig
from slicer_scripts.ent_analysis_pipeline import run_ent_analysis


def ENT_LOR_3D_PIPELINE():
    return run_ent_analysis(
        AnalysisConfig(
            preset_key="ent_threshold",
            use_totalsegmentator=False,
            save_report=True,
        )
    )


if __name__ == "__main__":
    print(ENT_LOR_3D_PIPELINE())
