import slicer
import qt
import numpy as np
from slicer.ScriptedLoadableModule import *

# ======================================================
# MODULE
# ======================================================

class ENT_Assistant_v3(ScriptedLoadableModule):
    def __init__(self, parent):
        super().__init__(parent)
        parent.title = "ENT Assistant v3"
        parent.categories = ["ENT"]
        parent.helpText = "Корректный 3D головы и пазух (Segmentation)"
        parent.acknowledgementText = "Не заменяет клиническое решение врача"


# ======================================================
# WIDGET
# ======================================================

class ENT_Assistant_v3Widget(ScriptedLoadableModuleWidget):

    def setup(self):
        super().setup()
        layout = self.layout

        layout.addWidget(qt.QLabel("<h3>ENT Assistant v3 — 3D</h3>"))

        self.btnVisual = qt.QPushButton("👤 Visual 3D")
        self.btnSurg   = qt.QPushButton("🦴 Surgical 3D")
        self.btnSkin   = qt.QPushButton("Кожа Вкл/Выкл")
        self.btnBone   = qt.QPushButton("Кость Вкл/Выкл")
        self.btnAir    = qt.QPushButton("Воздух Вкл/Выкл")

        for b in [self.btnVisual, self.btnSurg, self.btnSkin, self.btnBone, self.btnAir]:
            layout.addWidget(b)

        self.logic = ENT_Assistant_v3Logic()

        self.btnVisual.clicked.connect(self.logic.buildVisual3D)
        self.btnSurg.clicked.connect(self.logic.buildSurgical3D)
        self.btnSkin.clicked.connect(lambda: self.logic.toggle("Skin"))
        self.btnBone.clicked.connect(lambda: self.logic.toggle("Bone"))
        self.btnAir.clicked.connect(lambda: self.logic.toggle("Air"))


# ======================================================
# LOGIC
# ======================================================

class ENT_Assistant_v3Logic(ScriptedLoadableModuleLogic):

    # -----------------------------
    # Get CT
    # -----------------------------
    def _getCT(self):
        for v in slicer.util.getNodesByClass("vtkMRMLScalarVolumeNode"):
            arr = slicer.util.arrayFromVolume(v)
            if arr is not None and arr.ndim == 3:
                return v, arr
        raise RuntimeError("КТ не найдено")

    # -----------------------------
    # Find skull bottom by bone drop
    # -----------------------------
    def _findSkullBottomZ(self, boneMask):
        boneCount = boneMask.sum(axis=(1, 2))
        maxVal = boneCount.max()

        if maxVal == 0:
            return int(len(boneCount) * 0.75)

        norm = boneCount / maxVal

        for z in range(len(norm) - 1):
            if norm[z] > 0.15 and norm[z + 1] < 0.05:
                return z + 1

        return int(len(norm) * 0.75)

    # -----------------------------
    # Build anatomical body mask
    # -----------------------------
    def _buildBodyMask(self, arr):
        body = arr > -500
        bone = arr > 300

        zBottom = self._findSkullBottomZ(bone)
        body[zBottom:, :, :] = False

        return body

    # -----------------------------
    # Labelmap helper
    # -----------------------------
    def _createLabelmap(self, vol, mask, name):
        lm = slicer.mrmlScene.AddNewNodeByClass(
            "vtkMRMLLabelMapVolumeNode", name
        )
        slicer.util.updateVolumeFromArray(lm, mask.astype(np.uint8))
        lm.CopyOrientation(vol)
        lm.SetSpacing(vol.GetSpacing())
        lm.SetOrigin(vol.GetOrigin())
        return lm

    # -----------------------------
    # Build segmentation + 3D
    # -----------------------------
    def _buildSegmentation(self, vol, skin, bone, air):
        self.segNode = slicer.mrmlScene.AddNewNodeByClass(
            "vtkMRMLSegmentationNode", "ENT_3D"
        )
        self.segNode.CreateDefaultDisplayNodes()
        self.segNode.SetReferenceImageGeometryParameterFromVolumeNode(vol)

        logic = slicer.modules.segmentations.logic()

        def addSegment(mask, name, color):
            lm = self._createLabelmap(vol, mask, name + "_LM")
            segId = self.segNode.GetSegmentation().AddEmptySegment(name)
            self.segNode.GetSegmentation().GetSegment(segId).SetColor(*color)
            logic.ImportLabelmapToSegmentationNode(lm, self.segNode, segId)
            slicer.mrmlScene.RemoveNode(lm)

        addSegment(skin, "Skin", (1.0, 0.8, 0.6))
        addSegment(bone, "Bone", (0.95, 0.95, 0.95))
        addSegment(air,  "Air",  (0.2, 0.6, 1.0))

        # ===== КЛЮЧЕВОЕ ДЛЯ 3D =====
        self.segNode.CreateClosedSurfaceRepresentation()

        disp = self.segNode.GetDisplayNode()
        disp.SetPreferredDisplayRepresentationName3D("Closed surface")
        disp.SetVisibility3D(True)

        disp.SetSegmentOpacity3D("Skin", 0.25)
        disp.SetSegmentOpacity3D("Bone", 0.6)
        disp.SetSegmentOpacity3D("Air",  0.9)

        slicer.app.layoutManager().setLayout(
            slicer.vtkMRMLLayoutNode.SlicerLayoutOneUp3DView
        )

    # -----------------------------
    # Visual 3D
    # -----------------------------
    def buildVisual3D(self):
        vol, arr = self._getCT()
        body = self._buildBodyMask(arr)

        skin = (arr > -300) & (arr < 300) & body
        bone = (arr > 300) & body
        air  = (arr < -300) & body

        self._buildSegmentation(vol, skin, bone, air)

    # -----------------------------
    # Surgical 3D
    # -----------------------------
    def buildSurgical3D(self):
        vol, arr = self._getCT()
        body = self._buildBodyMask(arr)

        skin = (arr > -300) & (arr < 300) & body
        bone = (arr > 300) & body
        air  = (arr < -300) & body

        self._buildSegmentation(vol, skin, bone, air)

    # -----------------------------
    # Toggle visibility
    # -----------------------------
    def toggle(self, name):
        if not hasattr(self, "segNode"):
            return
        disp = self.segNode.GetDisplayNode()
        disp.SetSegmentVisibility(name, not disp.GetSegmentVisibility(name))
