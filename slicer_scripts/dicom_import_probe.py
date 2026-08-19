import json
import pathlib
import tempfile
import traceback

import slicer


def main():
    source_dir = pathlib.Path(r"C:\entv1\data\mri_otitis_patient002")
    output_path = pathlib.Path(r"C:\entv1\dicom_import_probe.json")
    payload = {
        "sourceDir": str(source_dir),
        "sourceExists": source_dir.exists(),
        "fileCount": len(list(source_dir.glob("*.dcm"))) if source_dir.exists() else 0,
    }

    try:
        from DICOMLib import DICOMUtils

        temp_db_dir = tempfile.mkdtemp(prefix="slicer_dicom_probe_")
        payload["tempDbDir"] = temp_db_dir

        with DICOMUtils.TemporaryDICOMDatabase(temp_db_dir) as db:
            slicer.dicomDatabase = db
            DICOMUtils.importDicom(str(source_dir), db)

            patients = list(db.patients())
            payload["patientCount"] = len(patients)
            payload["patients"] = []

            for patient_uid in patients:
                patient_entry = {
                    "patientUid": patient_uid,
                    "studies": [],
                }
                for study_uid in db.studiesForPatient(patient_uid):
                    study_entry = {
                        "studyUid": study_uid,
                        "series": [],
                    }
                    for series_uid in db.seriesForStudy(study_uid):
                        files = list(db.filesForSeries(series_uid))
                        first_file = files[0] if files else None
                        study_entry["series"].append(
                            {
                                "seriesUid": series_uid,
                                "fileCount": len(files),
                                "seriesDescription": db.fileValue(first_file, "0008,103E") if first_file else None,
                                "modality": db.fileValue(first_file, "0008,0060") if first_file else None,
                            }
                        )
                    patient_entry["studies"].append(study_entry)
                payload["patients"].append(patient_entry)

    except Exception as error:
        payload["error"] = str(error)
        payload["traceback"] = traceback.format_exc()

    output_path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
    slicer.util.exit()


if __name__ == "__main__":
    main()
