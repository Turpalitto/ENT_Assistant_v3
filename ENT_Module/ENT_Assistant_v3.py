import importlib.util
import os
import subprocess
import sys

import qt
import slicer
from slicer.ScriptedLoadableModule import *


MODULE_DIR = os.path.dirname(__file__)
REPO_ROOT = os.path.abspath(os.path.join(MODULE_DIR, ".."))
if REPO_ROOT not in sys.path:
    sys.path.insert(0, REPO_ROOT)

from ENT_Module.ent_assistant_core import AnalysisConfig, get_presets


class ENT_Assistant_v3(ScriptedLoadableModule):
    def __init__(self, parent):
        super().__init__(parent)
        parent.title = "ENT Assistant v3"
        parent.categories = ["ENT"]
        parent.contributors = ["ENT AI Assistant (2026)"]
        parent.helpText = "ENT and head CT analysis helper for 3D Slicer."
        parent.acknowledgementText = "Uses open-source medical imaging workflows."


class ENT_Assistant_v3Widget(ScriptedLoadableModuleWidget):
    def setup(self):
        super().setup()
        layout = self.layout
        self.presets = get_presets()
        self.lastVolumeNodeId = None
        self.lastSegmentationNodeId = None

        title = qt.QLabel(
            "<h2>ENT Assistant v3</h2>"
            "<p>Analyze ENT and sinus CT studies with threshold presets, open-source AI segmentation and radiology-style draft reporting.</p>"
        )
        title.setWordWrap(True)
        layout.addWidget(title)

        layout.addWidget(qt.QLabel("Analysis preset"))
        self.presetCombo = qt.QComboBox()
        self.presetKeyByTitle = {}
        for preset in self.presets.values():
            self.presetCombo.addItem(preset.title, preset.key)
            self.presetKeyByTitle[preset.title] = preset.key
        layout.addWidget(self.presetCombo)

        self.presetDescription = qt.QLabel("")
        self.presetDescription.setWordWrap(True)
        layout.addWidget(self.presetDescription)

        self.batchModeCombo = qt.QComboBox()
        self.batchModeCombo.addItems(["active", "all", "compare_first_two"])
        batchModeForm = qt.QFormLayout()
        batchModeForm.addRow("Batch mode", self.batchModeCombo)
        self.reportModeCombo = qt.QComboBox()
        self.reportModeCombo.addItems(["assistant", "radiology", "surgeon"])
        batchModeForm.addRow("Report mode", self.reportModeCombo)
        layout.addLayout(batchModeForm)

        self.useTotalSegmentator = qt.QCheckBox("Use TotalSegmentator when available")
        self.useTotalSegmentator.checked = True
        layout.addWidget(self.useTotalSegmentator)

        self.saveReportCheck = qt.QCheckBox("Save JSON report to repository /reports")
        self.saveReportCheck.checked = True
        layout.addWidget(self.saveReportCheck)

        self.exportHtmlReportCheck = qt.QCheckBox("Export HTML report")
        self.exportHtmlReportCheck.checked = True
        layout.addWidget(self.exportHtmlReportCheck)

        self.preopChecklistCheck = qt.QCheckBox("Generate pre-op ENT/FESS checklist")
        self.preopChecklistCheck.checked = True
        layout.addWidget(self.preopChecklistCheck)

        self.exportResultsCheck = qt.QCheckBox("Export segmentation outputs to repository /exports")
        self.exportResultsCheck.checked = True
        layout.addWidget(self.exportResultsCheck)

        self.exportSegNrrdCheck = qt.QCheckBox("Export segmentation as .seg.nrrd")
        self.exportSegNrrdCheck.checked = True
        layout.addWidget(self.exportSegNrrdCheck)

        self.exportLabelmapCheck = qt.QCheckBox("Export labelmap as .nii.gz")
        self.exportLabelmapCheck.checked = True
        layout.addWidget(self.exportLabelmapCheck)

        self.exportSurfaceCheck = qt.QCheckBox("Export surface models as STL")
        self.exportSurfaceCheck.checked = False
        layout.addWidget(self.exportSurfaceCheck)

        self.exportRtstructCheck = qt.QCheckBox("RTSTRUCT readiness / safe export layer")
        self.exportRtstructCheck.checked = False
        layout.addWidget(self.exportRtstructCheck)

        self.aiOptionsForm = qt.QFormLayout()
        self.aiQualityCombo = qt.QComboBox()
        self.aiQualityCombo.addItems(["normal", "fast"])
        self.useCpuCheck = qt.QCheckBox()
        self.useCpuCheck.checked = False
        self.robustCropCheck = qt.QCheckBox()
        self.robustCropCheck.checked = True
        self.aiOptionsForm.addRow("AI quality", self.aiQualityCombo)
        self.aiOptionsForm.addRow("Use CPU only", self.useCpuCheck)
        self.aiOptionsForm.addRow("Robust crop", self.robustCropCheck)
        layout.addLayout(self.aiOptionsForm)

        thresholdsForm = qt.QFormLayout()
        self.boneMinSpin = qt.QSpinBox()
        self.boneMinSpin.setRange(-2000, 5000)
        self.boneMinSpin.setValue(300)
        self.boneMaxSpin = qt.QSpinBox()
        self.boneMaxSpin.setRange(-2000, 5000)
        self.boneMaxSpin.setValue(3000)
        self.airMinSpin = qt.QSpinBox()
        self.airMinSpin.setRange(-2000, 5000)
        self.airMinSpin.setValue(-1000)
        self.airMaxSpin = qt.QSpinBox()
        self.airMaxSpin.setRange(-2000, 5000)
        self.airMaxSpin.setValue(-300)
        thresholdsForm.addRow("Bone min HU", self.boneMinSpin)
        thresholdsForm.addRow("Bone max HU", self.boneMaxSpin)
        thresholdsForm.addRow("Air min HU", self.airMinSpin)
        thresholdsForm.addRow("Air max HU", self.airMaxSpin)
        layout.addLayout(thresholdsForm)

        self.runBtn = qt.QPushButton("Run ENT / sinus CT analysis")
        self.runBtn.clicked.connect(self.runPipeline)
        layout.addWidget(self.runBtn)

        self.stackBtn = qt.QPushButton("Check open-source stack")
        self.stackBtn.clicked.connect(self.checkOpenSourceStack)
        layout.addWidget(self.stackBtn)

        self.recomputeBtn = qt.QPushButton("Recompute last report from segmentation")
        self.recomputeBtn.clicked.connect(self.recomputeLastReport)
        layout.addWidget(self.recomputeBtn)

        viewButtons = qt.QHBoxLayout()
        self.sinus3dBtn = qt.QPushButton("Prepare 3D sinus view")
        self.sinus3dBtn.clicked.connect(self.prepareSinus3DView)
        viewButtons.addWidget(self.sinus3dBtn)
        self.internal3dBtn = qt.QPushButton("Internal head view")
        self.internal3dBtn.clicked.connect(self.prepareInternalHeadView)
        viewButtons.addWidget(self.internal3dBtn)
        self.surgical3dBtn = qt.QPushButton("FESS planning view")
        self.surgical3dBtn.clicked.connect(self.prepareSurgicalView)
        viewButtons.addWidget(self.surgical3dBtn)
        layout.addLayout(viewButtons)

        self.devBtn = qt.QPushButton("Run DEV helper")
        self.devBtn.clicked.connect(self.runDevScript)
        layout.addWidget(self.devBtn)

        self.updateBtn = qt.QPushButton("Git Pull")
        self.updateBtn.clicked.connect(self.updateFromGit)
        layout.addWidget(self.updateBtn)

        self.pushBtn = qt.QPushButton("Git Save + Push")
        self.pushBtn.clicked.connect(self.saveAndPush)
        layout.addWidget(self.pushBtn)

        self.reloadBtn = qt.QPushButton("Reload Module")
        self.reloadBtn.clicked.connect(self.reloadModule)
        layout.addWidget(self.reloadBtn)

        self.output = qt.QTextEdit()
        self.output.setReadOnly(True)
        layout.addWidget(self.output)

        self.findingsTable = qt.QTableWidget()
        self.findingsTable.setColumnCount(4)
        self.findingsTable.setHorizontalHeaderLabels(["Category", "Structure", "Status", "Details"])
        self.findingsTable.horizontalHeader().setStretchLastSection(True)
        self.findingsTable.setEditTriggers(qt.QAbstractItemView.NoEditTriggers)
        layout.addWidget(self.findingsTable)

        self.presetCombo.currentIndexChanged.connect(self.updatePresetDescription)
        self.updatePresetDescription()

    def runPipeline(self):
        try:
            pipeline_path = os.path.abspath(os.path.join(REPO_ROOT, "slicer_scripts", "ent_analysis_pipeline.py"))
            module = self._load_python_module("ent_analysis_pipeline_runtime", pipeline_path)
            config = AnalysisConfig(
                preset_key=self.getSelectedPresetKey(),
                batch_mode=self.batchModeCombo.currentText,
                use_totalsegmentator=self.useTotalSegmentator.checked,
                save_report=self.saveReportCheck.checked,
                report_mode=self.reportModeCombo.currentText,
                export_html_report=self.exportHtmlReportCheck.checked,
                generate_preop_checklist=self.preopChecklistCheck.checked,
                export_results=self.exportResultsCheck.checked,
                export_seg_nrrd=self.exportSegNrrdCheck.checked,
                export_labelmap_nifti=self.exportLabelmapCheck.checked,
                export_surface_models=self.exportSurfaceCheck.checked,
                export_rtstruct=self.exportRtstructCheck.checked,
                ai_quality=self.aiQualityCombo.currentText,
                use_cpu=self.useCpuCheck.checked,
                robust_crop=self.robustCropCheck.checked,
                bone_threshold_min=self.boneMinSpin.value,
                bone_threshold_max=self.boneMaxSpin.value,
                air_threshold_min=self.airMinSpin.value,
                air_threshold_max=self.airMaxSpin.value,
            )

            self.output.clear()
            self.populateFindingsTable([])
            result = module.run_ent_analysis(config, log_callback=self.appendOutput)
            if "cases" in result:
                self.appendOutput(f"Batch completed: {result['count']} volumes")
                if result.get("batchIndexPath"):
                    self.appendOutput(f"Batch index: {result['batchIndexPath']}")
                if result.get("batchCsvPath"):
                    self.appendOutput(f"Batch CSV: {result['batchCsvPath']}")
                if result.get("comparisonIndexPath"):
                    self.appendOutput(f"Comparison index: {result['comparisonIndexPath']}")
                if result.get("timelinePath"):
                    self.appendOutput(f"Timeline index: {result['timelinePath']}")
                for comparison in result.get("comparisons", [])[:2]:
                    self.appendOutput(comparison.get("summaryText", ""))
                first_case = (result.get("cases") or [{}])[0]
                self.lastVolumeNodeId = first_case.get("volumeNodeId")
                self.lastSegmentationNodeId = first_case.get("segmentationNodeId")
                self.populateFindingsTable(((first_case.get("sinusReport") or {}).get("findingRows")) or [])
                return
            self.appendOutput("")
            self.appendOutput(f"Completed preset: {result['preset']}")
            self.lastVolumeNodeId = result.get("volumeNodeId")
            self.lastSegmentationNodeId = result.get("segmentationNodeId")
            if result.get("reportPath"):
                self.appendOutput(f"Report: {result['reportPath']}")
            if result.get("htmlReportPath"):
                self.appendOutput(f"HTML report: {result['htmlReportPath']}")
            export_info = result.get("exportInfo")
            if export_info:
                self.appendOutput(f"Export directory: {export_info.get('directory')}")
            rtstruct_readiness = result.get("rtstructReadiness")
            if rtstruct_readiness:
                self.appendOutput(f"RTSTRUCT ready: {rtstruct_readiness.get('ready')}")
            sinus_report = result.get("sinusReport")
            if sinus_report:
                self.appendOutput("")
                self.appendOutput(sinus_report.get("reportText", ""))
                self.populateFindingsTable(sinus_report.get("findingRows") or [])
                suitability = sinus_report.get("suitability") or {}
                self.appendOutput(f"Suitability: {suitability.get('level')} ({suitability.get('score')})")
        except Exception as error:
            self.output.setText(f"Pipeline error:\n{error}")

    def recomputeLastReport(self):
        try:
            if not self.lastVolumeNodeId or not self.lastSegmentationNodeId:
                self.output.setText("Run an analysis first so there is a volume and segmentation to recompute from.")
                return
            pipeline_path = os.path.abspath(os.path.join(REPO_ROOT, "slicer_scripts", "ent_analysis_pipeline.py"))
            module = self._load_python_module("ent_analysis_pipeline_runtime_recompute", pipeline_path)
            config = AnalysisConfig(
                preset_key=self.getSelectedPresetKey(),
                batch_mode="active",
                use_totalsegmentator=False,
                save_report=self.saveReportCheck.checked,
                report_mode=self.reportModeCombo.currentText,
                export_html_report=self.exportHtmlReportCheck.checked,
                generate_preop_checklist=self.preopChecklistCheck.checked,
                export_results=False,
                export_rtstruct=False,
            )
            self.output.clear()
            result = module.recompute_ent_analysis(self.lastVolumeNodeId, self.lastSegmentationNodeId, config, log_callback=self.appendOutput)
            self.appendOutput(f"Recomputed preset: {result['preset']}")
            if result.get("reportPath"):
                self.appendOutput(f"Report: {result['reportPath']}")
            if result.get("htmlReportPath"):
                self.appendOutput(f"HTML report: {result['htmlReportPath']}")
            sinus_report = result.get("sinusReport")
            if sinus_report:
                self.populateFindingsTable(sinus_report.get("findingRows") or [])
                self.appendOutput("")
                self.appendOutput(sinus_report.get("reportText", ""))
        except Exception as error:
            self.output.setText(f"Recompute error:\n{error}")

    def runDevScript(self):
        try:
            script_path = os.path.abspath(os.path.join(REPO_ROOT, "slicer_scripts", "dev.py"))
            module = self._load_python_module("ent_dev_runtime", script_path)
            module.run()
            self.output.setText("DEV helper completed.")
        except Exception as error:
            self.output.setText(f"DEV error:\n{error}")

    def updateFromGit(self):
        try:
            result = subprocess.run(
                ["git", "pull"],
                cwd=REPO_ROOT,
                capture_output=True,
                text=True,
            )
            if result.returncode == 0:
                self.output.setText("Git Pull completed.\n\n" + result.stdout)
            else:
                self.output.setText("Git Pull error.\n\n" + result.stderr)
        except Exception as error:
            self.output.setText(f"Error:\n{error}")

    def saveAndPush(self):
        try:
            subprocess.run(["git", "add", "."], cwd=REPO_ROOT, check=False)
            subprocess.run(
                ["git", "commit", "-m", "Auto update from ENT module"],
                cwd=REPO_ROOT,
                check=False,
            )
            result = subprocess.run(
                ["git", "push"],
                cwd=REPO_ROOT,
                capture_output=True,
                text=True,
            )
            if result.returncode == 0:
                self.output.setText("Git Push completed.\n\n" + result.stdout)
            else:
                self.output.setText("Git Push warning.\n\n" + result.stderr)
        except Exception as error:
            self.output.setText(f"Push error:\n{error}")

    def reloadModule(self):
        slicer.util.reloadScriptedModule("ENT_Assistant_v3")

    def updatePresetDescription(self):
        preset_key = self.getSelectedPresetKey()
        preset = self.presets[preset_key]
        self.presetDescription.setText(preset.description)

    def checkOpenSourceStack(self):
        try:
            stack_path = os.path.abspath(os.path.join(MODULE_DIR, "open_source_stack.py"))
            module = self._load_python_module("ent_open_source_stack_runtime", stack_path)
            report = module.inspect_open_source_stack()
            self.output.setText(report["summary"])
        except Exception as error:
            self.output.setText(f"Stack check error:\n{error}")

    def getSelectedPresetKey(self):
        return self.presetKeyByTitle.get(self.presetCombo.currentText, "ent_threshold")

    def appendOutput(self, message):
        existing = self.output.toPlainText()
        text = f"{existing}\n{message}".strip() if existing else str(message)
        self.output.setPlainText(text)
        self.output.verticalScrollBar().setValue(self.output.verticalScrollBar().maximum)

    def populateFindingsTable(self, rows):
        self.findingsTable.setRowCount(len(rows))
        for row_index, row in enumerate(rows):
            self.findingsTable.setItem(row_index, 0, qt.QTableWidgetItem(str(row.get("category", ""))))
            self.findingsTable.setItem(row_index, 1, qt.QTableWidgetItem(str(row.get("structure", ""))))
            self.findingsTable.setItem(row_index, 2, qt.QTableWidgetItem(str(row.get("status", ""))))
            self.findingsTable.setItem(row_index, 3, qt.QTableWidgetItem(str(row.get("details", ""))))
        if not rows:
            self.findingsTable.setRowCount(0)

    def prepareSinus3DView(self):
        self._runVisualization("prepare_sinus_3d_scene")

    def prepareInternalHeadView(self):
        self._runVisualization("prepare_internal_head_view")

    def prepareSurgicalView(self):
        self._runVisualization("prepare_surgical_focus_view")

    def _runVisualization(self, function_name):
        try:
            if not self.lastVolumeNodeId:
                self.output.setText("Run analysis first, or load a CT and analyze it to prepare 3D visualization.")
                return
            volume_node = slicer.mrmlScene.GetNodeByID(self.lastVolumeNodeId)
            segmentation_node = slicer.mrmlScene.GetNodeByID(self.lastSegmentationNodeId) if self.lastSegmentationNodeId else None
            visualization_path = os.path.abspath(os.path.join(MODULE_DIR, "sinus_visualization.py"))
            module = self._load_python_module("ent_sinus_visualization_runtime", visualization_path)
            result = getattr(module, function_name)(volume_node, segmentation_node)
            self.appendOutput(f"Visualization prepared: {function_name}")
            if result:
                self.appendOutput(str(result))
        except Exception as error:
            self.output.setText(f"Visualization error:\n{error}")

    def _load_python_module(self, module_name, path):
        spec = importlib.util.spec_from_file_location(module_name, path)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return module
