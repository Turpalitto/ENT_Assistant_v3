import json
import pathlib
import tempfile
import traceback

import slicer


SOURCE_DIR = pathlib.Path(r"C:\entv1\data\mri_otitis_patient002")
OUTPUT_DIR = pathlib.Path(r"C:\entv1\artifacts")
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
REPORT_PATH = OUTPUT_DIR / "mri_otitis_load_result.json"
SCENE_PATH = OUTPUT_DIR / "mri_otitis_loaded_scene.mrb"

PREFERRED_SERIES = {
    "t2_tse_ax",
    "t2_FLAIR_tra_4mm",
    "T1 Cor",
    "t2_ci3d_tra",
}


def main():
    payload = {
        "sourceDir": str(SOURCE_DIR),
        "scenePath": str(SCENE_PATH),
        "loadedSeries": [],
    }

    try:
        from DICOMLib import DICOMUtils

        temp_db_dir = tempfile.mkdtemp(prefix="slicer_dicom_load_case_")
        payload["tempDbDir"] = temp_db_dir

        with DICOMUtils.TemporaryDICOMDatabase(temp_db_dir) as db:
            slicer.dicomDatabase = db
            DICOMUtils.importDicom(str(SOURCE_DIR), db)

            patients = list(db.patients())
            payload["patientCount"] = len(patients)

            for patient_uid in patients:
                for study_uid in db.studiesForPatient(patient_uid):
                    for series_uid in db.seriesForStudy(study_uid):
                        files = list(db.filesForSeries(series_uid))
                        if not files:
                            continue
                        first_file = files[0]
                        description = db.fileValue(first_file, "0008,103E")
                        modality = db.fileValue(first_file, "0008,0060")
                        if description not in PREFERRED_SERIES:
                            continue

                        before_ids = {slicer.mrmlScene.GetNthNode(i).GetID() for i in range(slicer.mrmlScene.GetNumberOfNodes())}
                        loaded_ok = False
                        try:
                            loaded_ok = bool(DICOMUtils.loadSeriesByUID([series_uid]))
                        except Exception as error:
                            payload["loadedSeries"].append(
                                {
                                    "seriesUid": series_uid,
                                    "seriesDescription": description,
                                    "modality": modality,
                                    "loaded": False,
                                    "error": str(error),
                                }
                            )
                            continue

                        created_nodes = []
                        for i in range(slicer.mrmlScene.GetNumberOfNodes()):
                            node = slicer.mrmlScene.GetNthNode(i)
                            if node.GetID() not in before_ids and node.IsA("vtkMRMLScalarVolumeNode"):
                                created_nodes.append(node.GetName())

                        payload["loadedSeries"].append(
                            {
                                "seriesUid": series_uid,
                                "seriesDescription": description,
                                "modality": modality,
                                "loaded": loaded_ok,
                                "createdVolumeNodes": created_nodes,
                            }
                        )

            payload["sceneSaveSuccess"] = bool(slicer.util.saveScene(str(SCENE_PATH)))
            payload["scalarVolumeCount"] = len(slicer.util.getNodesByClass("vtkMRMLScalarVolumeNode"))

    except Exception as error:
        payload["error"] = str(error)
        payload["traceback"] = traceback.format_exc()

    REPORT_PATH.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
    slicer.util.exit()


if __name__ == "__main__":
    main()
