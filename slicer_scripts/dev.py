# ==========================================
# ENT Assistant DEV Script
# Всё временное писать сюда
# ==========================================

import slicer
import numpy as np


def get_active_volume():
    volumes = slicer.util.getNodesByClass("vtkMRMLScalarVolumeNode")
    if not volumes:
        raise RuntimeError("❌ Нет загруженного volume")
    return volumes[0]


def simple_bone_3d(threshold=300):
    volumeNode = get_active_volume()

    segNode = slicer.mrmlScene.AddNewNodeByClass(
        "vtkMRMLSegmentationNode", "DEV_Bone_Seg"
    )
    segNode.CreateDefaultDisplayNodes()
    segNode.SetReferenceImageGeometryParameterFromVolumeNode(volumeNode)

    arr = slicer.util.arrayFromVolume(volumeNode)
    mask = (arr > threshold).astype(np.uint8)

    labelmap = slicer.mrmlScene.AddNewNodeByClass(
        "vtkMRMLLabelMapVolumeNode", "TempLabel"
    )

    slicer.util.updateVolumeFromArray(labelmap, mask)
    labelmap.CopyOrientation(volumeNode)

    slicer.modules.segmentations.logic().ImportLabelmapToSegmentationNode(
        labelmap, segNode
    )

    slicer.mrmlScene.RemoveNode(labelmap)

    segNode.CreateClosedSurfaceRepresentation()
    segNode.GetDisplayNode().SetVisibility3D(True)

    print("✅ DEV 3D bone created")


def run():
    simple_bone_3d()


if __name__ == "__main__":
    run()
