# ==========================================
# ENT Assistant DEV Script
# Temporary experiments can live here.
# ==========================================

import numpy as np
import slicer


def get_active_volume():
    volumes = slicer.util.getNodesByClass("vtkMRMLScalarVolumeNode")
    if not volumes:
        raise RuntimeError("No loaded volume found.")
    return volumes[0]


def simple_bone_3d(threshold=300):
    volume_node = get_active_volume()

    seg_node = slicer.mrmlScene.AddNewNodeByClass("vtkMRMLSegmentationNode", "DEV_Bone_Seg")
    seg_node.CreateDefaultDisplayNodes()
    seg_node.SetReferenceImageGeometryParameterFromVolumeNode(volume_node)

    array = slicer.util.arrayFromVolume(volume_node)
    mask = (array > threshold).astype(np.uint8)

    labelmap = slicer.mrmlScene.AddNewNodeByClass("vtkMRMLLabelMapVolumeNode", "TempLabel")
    slicer.util.updateVolumeFromArray(labelmap, mask)
    labelmap.CopyOrientation(volume_node)

    slicer.modules.segmentations.logic().ImportLabelmapToSegmentationNode(labelmap, seg_node)
    slicer.mrmlScene.RemoveNode(labelmap)

    seg_node.CreateClosedSurfaceRepresentation()
    seg_node.GetDisplayNode().SetVisibility3D(True)
    print("DEV 3D bone created")


def run():
    simple_bone_3d()


if __name__ == "__main__":
    run()
