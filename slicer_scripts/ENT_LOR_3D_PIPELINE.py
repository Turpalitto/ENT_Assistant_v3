import slicer
import vtk

def ENT_LOR_3D_PIPELINE():

    print("🚀 ENT LOR 3D Pipeline started...")

    # --------------------------------------------------
    # 1. Получаем активный volume
    # --------------------------------------------------
    volumes = slicer.util.getNodesByClass("vtkMRMLScalarVolumeNode")
    if not volumes:
        raise RuntimeError("❌ Нет загруженного volume")

    volumeNode = volumes[0]

    # Активируем volume
    selectionNode = slicer.app.applicationLogic().GetSelectionNode()
    selectionNode.SetReferenceActiveVolumeID(volumeNode.GetID())
    slicer.app.applicationLogic().PropagateVolumeSelection()

    print("✅ Volume активирован:", volumeNode.GetName())

    # --------------------------------------------------
    # 2. Создаём segmentation
    # --------------------------------------------------
    segmentationNode = slicer.mrmlScene.AddNewNodeByClass("vtkMRMLSegmentationNode")
    segmentationNode.SetName("ENT_LOR_Segmentation")
    segmentationNode.CreateDefaultDisplayNodes()
    segmentationNode.SetReferenceImageGeometryParameterFromVolumeNode(volumeNode)

    # Добавляем сегменты
    boneSegmentId = segmentationNode.GetSegmentation().AddEmptySegment("Bone")
    airSegmentId = segmentationNode.GetSegmentation().AddEmptySegment("Air")

    print("✅ Segments created")

    # --------------------------------------------------
    # 3. Segment Editor
    # --------------------------------------------------
    segmentEditorWidget = slicer.qMRMLSegmentEditorWidget()
    segmentEditorWidget.setMRMLScene(slicer.mrmlScene)

    segmentEditorNode = slicer.mrmlScene.AddNewNodeByClass("vtkMRMLSegmentEditorNode")
    segmentEditorWidget.setMRMLSegmentEditorNode(segmentEditorNode)
    segmentEditorWidget.setSegmentationNode(segmentationNode)
    segmentEditorWidget.setSourceVolumeNode(volumeNode)

    # --------------------------------------------------
    # 4. КОСТЬ (Threshold)
    # --------------------------------------------------
    segmentEditorNode.SetSelectedSegmentID(boneSegmentId)
    segmentEditorWidget.setActiveEffectByName("Threshold")
    effect = segmentEditorWidget.activeEffect()
    effect.setParameter("MinimumThreshold", "300")
    effect.setParameter("MaximumThreshold", "3000")
    effect.self().onApply()

    print("✅ Bone segmented")

    # --------------------------------------------------
    # 5. ВОЗДУХ (Threshold)
    # --------------------------------------------------
    segmentEditorNode.SetSelectedSegmentID(airSegmentId)
    segmentEditorWidget.setActiveEffectByName("Threshold")
    effect = segmentEditorWidget.activeEffect()
    effect.setParameter("MinimumThreshold", "-1000")
    effect.setParameter("MaximumThreshold", "-300")
    effect.self().onApply()

    print("✅ Air segmented")

    # --------------------------------------------------
    # 6. 3D построение
    # --------------------------------------------------
    segmentationNode.CreateClosedSurfaceRepresentation()

    displayNode = segmentationNode.GetDisplayNode()
    displayNode.SetSegmentVisibility3D(boneSegmentId, True)
    displayNode.SetSegmentVisibility3D(airSegmentId, True)

    displayNode.SetSegmentOpacity3D(boneSegmentId, 1.0)
    displayNode.SetSegmentOpacity3D(airSegmentId, 0.3)

    # Цвета
    segmentationNode.GetSegmentation().GetSegment(boneSegmentId).SetColor(0.9, 0.8, 0.6)
    segmentationNode.GetSegmentation().GetSegment(airSegmentId).SetColor(0.2, 0.6, 1.0)

    print("✅ 3D surface создан")

    # --------------------------------------------------
    # 7. Surgical View (камера спереди)
    # --------------------------------------------------
    threeDView = slicer.app.layoutManager().threeDWidget(0).threeDView()
    threeDView.resetCamera()
    threeDView.resetFocalPoint()

    print("🎯 Surgical view установлен")

    return "✅ ENT LOR 3D готов (кость + воздух)"


# --------------------------------------------------
# Автоматический запуск если файл выполняется
# --------------------------------------------------

if __name__ == "__main__":
    print(ENT_LOR_3D_PIPELINE())
