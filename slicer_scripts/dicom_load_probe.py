import json
import pathlib
import tempfile
import traceback

import slicer


def main():
    source_dir = pathlib.Path(r"C:\entv1\data\mri_otitis_patient002")
    output_path = pathlib.Path(r"C:\entv1\dicom_load_probe.json")
    payload = {"sourceDir": str(source_dir)}

    try:
        from DICOMLib import DICOMUtils

        temp_db_dir = tempfile.mkdtemp(prefix="slicer_dicom_load_probe_")
        payload["tempDbDir"] = temp_db_dir

        with DICOMUtils.TemporaryDICOMDatabase(temp_db_dir) as db:
            slicer.dicomDatabase = db
            DICOMUtils.importDicom(str(source_dir), db)

            patients = list(db.patients())
            payload["patients"] = []
            sh_node = slicer.vtkMRMLSubjectHierarchyNode.GetSubjectHierarchyNode(slicer.mrmlScene)

            for patient_uid in patients:
                patient_info = {"patientUid": patient_uid, "series": []}
                for study_uid in db.studiesForPatient(patient_uid):
                    for series_uid in db.seriesForStudy(study_uid):
                        files = list(db.filesForSeries(series_uid))
                        first_file = files[0] if files else None
                        before_ids = set()
                        for i in range(slicer.mrmlScene.GetNumberOfNodes()):
                            before_ids.add(slicer.mrmlScene.GetNthNode(i).GetID())
                        ok = False
                        error_text = None
                        try:
                            loaded = DICOMUtils.loadSeriesByUID([series_uid])
                            ok = bool(loaded)
                        except Exception as error:
                            error_text = str(error)
                        after_nodes = []
                        for i in range(slicer.mrmlScene.GetNumberOfNodes()):
                            node = slicer.mrmlScene.GetNthNode(i)
                            if node.GetID() not in before_ids:
                                after_nodes.append({"id": node.GetID(), "name": node.GetName(), "class": node.GetClassName()})
                        patient_info["series"].append(
                            {
                                "seriesUid": series_uid,
                                "seriesDescription": db.fileValue(first_file, "0008,103E") if first_file else None,
                                "modality": db.fileValue(first_file, "0008,0060") if first_file else None,
                                "fileCount": len(files),
                                "loaded": ok,
                                "error": error_text,
                                "createdNodes": after_nodes,
                            }
                        )
                        slicer.mrmlScene.Clear(0)
                payload["patients"].append(patient_info)

    except Exception as error:
        payload["error"] = str(error)
        payload["traceback"] = traceback.format_exc()

    output_path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
    slicer.util.exit()


if __name__ == "__main__":
    main()
