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
        self.lastResult = None
        self.lastAiWorkspaceDir = None

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

        self.autoScreenshotsCheck = qt.QCheckBox("Auto-capture screenshots for HTML report")
        self.autoScreenshotsCheck.checked = True
        layout.addWidget(self.autoScreenshotsCheck)

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

        reportButtons = qt.QHBoxLayout()
        self.radiologyBtn = qt.QPushButton("Radiology one-click report")
        self.radiologyBtn.clicked.connect(self.runRadiologyReport)
        reportButtons.addWidget(self.radiologyBtn)
        self.fessBtn = qt.QPushButton("FESS one-click report")
        self.fessBtn.clicked.connect(self.runFessReport)
        reportButtons.addWidget(self.fessBtn)
        self.mriBtn = qt.QPushButton("MRI one-click report")
        self.mriBtn.clicked.connect(self.runMriReport)
        reportButtons.addWidget(self.mriBtn)
        layout.addLayout(reportButtons)

        self.stackBtn = qt.QPushButton("Check open-source stack")
        self.stackBtn.clicked.connect(self.checkOpenSourceStack)
        layout.addWidget(self.stackBtn)

        self.runtimeAdvisorBtn = qt.QPushButton("AI runtime advisor")
        self.runtimeAdvisorBtn.clicked.connect(self.checkAiRuntimeAdvisor)
        layout.addWidget(self.runtimeAdvisorBtn)

        self.recomputeBtn = qt.QPushButton("Recompute last report from segmentation")
        self.recomputeBtn.clicked.connect(self.recomputeLastReport)
        layout.addWidget(self.recomputeBtn)

        workflowButtons = qt.QHBoxLayout()
        self.importDicomBtn = qt.QPushButton("Import DICOM folder")
        self.importDicomBtn.clicked.connect(self.importDicomFolder)
        workflowButtons.addWidget(self.importDicomBtn)
        self.exportBundleBtn = qt.QPushButton("Export current case bundle")
        self.exportBundleBtn.clicked.connect(self.exportCurrentCaseBundle)
        workflowButtons.addWidget(self.exportBundleBtn)
        layout.addLayout(workflowButtons)

        aiWorkflowButtons = qt.QHBoxLayout()
        self.exportAiWorkspaceBtn = qt.QPushButton("Export AI workspace")
        self.exportAiWorkspaceBtn.clicked.connect(self.exportAiWorkspace)
        aiWorkflowButtons.addWidget(self.exportAiWorkspaceBtn)
        self.refineBtn = qt.QPushButton("Prepare interactive refinement")
        self.refineBtn.clicked.connect(self.prepareInteractiveRefinement)
        aiWorkflowButtons.addWidget(self.refineBtn)
        layout.addLayout(aiWorkflowButtons)

        launcherButtons = qt.QHBoxLayout()
        self.launchTotalSegBtn = qt.QPushButton("Launch TotalSegmentator")
        self.launchTotalSegBtn.clicked.connect(lambda: self.launchWorkspaceCommand("run_totalsegmentator_example"))
        launcherButtons.addWidget(self.launchTotalSegBtn)
        self.launchNnUNetBtn = qt.QPushButton("Launch nnU-Net")
        self.launchNnUNetBtn.clicked.connect(lambda: self.launchWorkspaceCommand("run_nnunet_inference_example"))
        launcherButtons.addWidget(self.launchNnUNetBtn)
        self.launchMonaiBtn = qt.QPushButton("Launch MONAI Label")
        self.launchMonaiBtn.clicked.connect(lambda: self.launchWorkspaceCommand("run_monailabel_example"))
        launcherButtons.addWidget(self.launchMonaiBtn)
        self.launchVistaBtn = qt.QPushButton("VISTA3D-ready export")
        self.launchVistaBtn.clicked.connect(lambda: self.launchWorkspaceCommand("run_vista3d_example"))
        launcherButtons.addWidget(self.launchVistaBtn)
        self.bootstrapEnvBtn = qt.QPushButton("Bootstrap AI env")
        self.bootstrapEnvBtn.clicked.connect(self.bootstrapExternalEnv)
        launcherButtons.addWidget(self.bootstrapEnvBtn)
        self.importRoundTripBtn = qt.QPushButton("Import round-trip results")
        self.importRoundTripBtn.clicked.connect(self.importRoundTripResults)
        launcherButtons.addWidget(self.importRoundTripBtn)
        layout.addLayout(launcherButtons)

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
            config = self._buildAnalysisConfig()

            self.output.clear()
            self.populateFindingsTable([])
            result = module.run_ent_analysis(config, log_callback=self.appendOutput)
            self.lastResult = result
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
            mri_report = result.get("mriReport")
            if sinus_report:
                self.appendOutput("")
                self.appendOutput(sinus_report.get("reportText", ""))
                self.populateFindingsTable(sinus_report.get("findingRows") or [])
                suitability = sinus_report.get("suitability") or {}
                self.appendOutput(f"Suitability: {suitability.get('level')} ({suitability.get('score')})")
                self.appendOutput(f"Patient summary: {sinus_report.get('patientSummary')}")
            elif mri_report:
                self.appendOutput("")
                self.appendOutput(mri_report.get("reportText", ""))
                self.populateFindingsTable(mri_report.get("findingRows") or [])
                suitability = mri_report.get("suitability") or {}
                self.appendOutput(f"MRI suitability: {suitability.get('level')} ({suitability.get('score')})")
                self.appendOutput(f"Patient summary: {mri_report.get('patientSummary')}")
        except Exception as error:
            self.output.setText(f"Pipeline error:\n{error}")

    def recomputeLastReport(self):
        try:
            if not self.lastVolumeNodeId or not self.lastSegmentationNodeId:
                self.output.setText("Run an analysis first so there is a volume and segmentation to recompute from.")
                return
            pipeline_path = os.path.abspath(os.path.join(REPO_ROOT, "slicer_scripts", "ent_analysis_pipeline.py"))
            module = self._load_python_module("ent_analysis_pipeline_runtime_recompute", pipeline_path)
            config = self._buildRecomputeConfig()
            self.output.clear()
            result = module.recompute_ent_analysis(self.lastVolumeNodeId, self.lastSegmentationNodeId, config, log_callback=self.appendOutput)
            self.lastResult = result
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
            else:
                mri_report = result.get("mriReport")
                if mri_report:
                    self.populateFindingsTable(mri_report.get("findingRows") or [])
                    self.appendOutput("")
                    self.appendOutput(mri_report.get("reportText", ""))
        except Exception as error:
            self.output.setText(f"Recompute error:\n{error}")

    def runRadiologyReport(self):
        index = self.presetCombo.findText("CT PNS: AI-assisted sinus report")
        if index >= 0:
            self.presetCombo.setCurrentIndex(index)
        self.reportModeCombo.setCurrentText("radiology")
        self.runPipeline()

    def runFessReport(self):
        index = self.presetCombo.findText("CT PNS: AI-assisted sinus report")
        if index >= 0:
            self.presetCombo.setCurrentIndex(index)
        self.reportModeCombo.setCurrentText("surgeon")
        self.runPipeline()

    def runMriReport(self):
        self.reportModeCombo.setCurrentText("assistant")
        index = self.presetCombo.findText("ENT / temporal bone MRI support")
        if index >= 0:
            self.presetCombo.setCurrentIndex(index)
        self.runPipeline()

    def importDicomFolder(self):
        try:
            folder = qt.QFileDialog.getExistingDirectory(slicer.util.mainWindow(), "Select DICOM folder")
            if not folder:
                return
            workflow_path = os.path.abspath(os.path.join(MODULE_DIR, "slicer_workflow.py"))
            module = self._load_python_module("ent_slicer_workflow_runtime_import", workflow_path)
            result = module.import_dicom_folder(folder)
            self.output.setText(f"DICOM import completed.\n\n{result}")
        except Exception as error:
            self.output.setText(f"DICOM import error:\n{error}")

    def exportCurrentCaseBundle(self):
        try:
            if not self.lastResult:
                self.output.setText("Run or recompute a case first so there is something to export.")
                return
            folder = qt.QFileDialog.getExistingDirectory(slicer.util.mainWindow(), "Select export folder")
            if not folder:
                return
            workflow_path = os.path.abspath(os.path.join(MODULE_DIR, "slicer_workflow.py"))
            module = self._load_python_module("ent_slicer_workflow_runtime_export", workflow_path)
            result = module.export_case_bundle(self.lastResult, folder)
            self.appendOutput(f"Case bundle exported: {result}")
        except Exception as error:
            self.output.setText(f"Case bundle export error:\n{error}")

    def exportAiWorkspace(self):
        try:
            if not self.lastResult:
                self.output.setText("Run or recompute a case first so there is something to export into an AI workspace.")
                return
            folder = qt.QFileDialog.getExistingDirectory(slicer.util.mainWindow(), "Select AI workspace folder")
            if not folder:
                return
            workflow_path = os.path.abspath(os.path.join(MODULE_DIR, "slicer_workflow.py"))
            module = self._load_python_module("ent_slicer_workflow_runtime_ai_export", workflow_path)
            result = module.export_ai_workspace(self.lastResult, folder)
            self.lastAiWorkspaceDir = result.get("directory")
            self.appendOutput(f"AI workspace exported: {result.get('directory')}")
            if result.get("workspaceMeta"):
                self.appendOutput(f"AI manifest: {(result.get('workspaceMeta') or {}).get('manifestPath')}")
            if result.get("nnunetWorkspace"):
                self.appendOutput(f"nnU-Net workspace: {(result.get('nnunetWorkspace') or {}).get('directory')}")
            if result.get("vista3dWorkspace"):
                self.appendOutput(f"VISTA3D workspace: {(result.get('vista3dWorkspace') or {}).get('directory')}")
            if result.get("interactiveRefinement"):
                self.appendOutput(f"Interactive prompts: {(result.get('interactiveRefinement') or {}).get('directory')}")
            if result.get("envSetup"):
                self.appendOutput(f"Env setup scripts: {(result.get('envSetup') or {}).get('directory')}")
        except Exception as error:
            self.output.setText(f"AI workspace export error:\n{error}")

    def prepareInteractiveRefinement(self):
        try:
            if not self.lastVolumeNodeId or not self.lastSegmentationNodeId:
                self.output.setText("Run an analysis first so there is a volume and segmentation to refine.")
                return
            volume_node = slicer.mrmlScene.GetNodeByID(self.lastVolumeNodeId)
            segmentation_node = slicer.mrmlScene.GetNodeByID(self.lastSegmentationNodeId)
            refinement_path = os.path.abspath(os.path.join(MODULE_DIR, "interactive_refinement.py"))
            module = self._load_python_module("ent_interactive_refinement_runtime", refinement_path)
            result = module.prepare_interactive_refinement(volume_node, segmentation_node, self.lastResult or {})
            self.appendOutput("Interactive refinement prepared.")
            self.appendOutput(result.get("summary", ""))
        except Exception as error:
            self.output.setText(f"Interactive refinement error:\n{error}")

    def launchWorkspaceCommand(self, command_name):
        try:
            if not self.lastAiWorkspaceDir:
                self.output.setText("Export an AI workspace first, then launch an external backend from that workspace.")
                return
            workflow_path = os.path.abspath(os.path.join(MODULE_DIR, "slicer_workflow.py"))
            module = self._load_python_module("ent_slicer_workflow_runtime_launch", workflow_path)
            result = module.launch_workspace_command(self.lastAiWorkspaceDir, command_name)
            self.appendOutput(f"Launcher started: {result.get('commandName')}")
            self.appendOutput(f"Command file: {result.get('commandPath')}")
            if result.get("launchMode"):
                self.appendOutput(f"Launch mode: {result.get('launchMode')}")
            if result.get("pid"):
                self.appendOutput(f"PID: {result.get('pid')}")
            if result.get("logPath"):
                self.appendOutput(f"Launcher log: {result.get('logPath')}")
            if result.get("warning"):
                self.appendOutput(f"Launcher warning: {result.get('warning')}")
        except Exception as error:
            self.output.setText(f"Launcher error:\n{error}")

    def bootstrapExternalEnv(self):
        try:
            if not self.lastAiWorkspaceDir:
                self.output.setText("Export an AI workspace first, then bootstrap the external AI environment from that workspace.")
                return
            workflow_path = os.path.abspath(os.path.join(MODULE_DIR, "slicer_workflow.py"))
            module = self._load_python_module("ent_slicer_workflow_runtime_bootstrap", workflow_path)
            result = module.bootstrap_external_env(self.lastAiWorkspaceDir)
            self.appendOutput(f"AI env bootstrap started: {result.get('commandPath')}")
            if result.get("launchMode"):
                self.appendOutput(f"Launch mode: {result.get('launchMode')}")
            if result.get("pid"):
                self.appendOutput(f"PID: {result.get('pid')}")
            if result.get("logPath"):
                self.appendOutput(f"Launcher log: {result.get('logPath')}")
        except Exception as error:
            self.output.setText(f"AI env bootstrap error:\n{error}")

    def importRoundTripResults(self):
        try:
            if not self.lastAiWorkspaceDir:
                self.output.setText("Export an AI workspace first, or set up a workspace before importing round-trip results.")
                return
            if not self.lastVolumeNodeId:
                self.output.setText("Run an analysis first so a reference volume is available for round-trip import.")
                return
            volume_node = slicer.mrmlScene.GetNodeByID(self.lastVolumeNodeId)
            workflow_path = os.path.abspath(os.path.join(MODULE_DIR, "slicer_workflow.py"))
            module = self._load_python_module("ent_slicer_workflow_runtime_roundtrip", workflow_path)
            self.appendOutput("Searching AI workspace for round-trip predictions...")
            result = module.import_roundtrip_workspace(self.lastAiWorkspaceDir, volume_node)
            self.lastSegmentationNodeId = result.get("segmentationNodeId")
            self.appendOutput(f"Round-trip import completed from: {result.get('source')}")
            self.appendOutput(f"Imported segmentation: {result.get('segmentationNodeName')}")
            self.appendOutput("Auto-recompute started from imported segmentation...")
            self._autoRecomputeAfterRoundTrip()
        except Exception as error:
            self.output.setText(f"Round-trip import error:\n{error}")

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

    def checkAiRuntimeAdvisor(self):
        try:
            advisor_path = os.path.abspath(os.path.join(MODULE_DIR, "ai_runtime_advisor.py"))
            module = self._load_python_module("ent_ai_runtime_advisor_runtime", advisor_path)
            report = module.inspect_local_ai_runtimes()
            self.output.setText(report["summary"])
        except Exception as error:
            self.output.setText(f"AI runtime advisor error:\n{error}")

    def getSelectedPresetKey(self):
        return self.presetKeyByTitle.get(self.presetCombo.currentText, "ent_threshold")

    def _buildAnalysisConfig(self):
        return AnalysisConfig(
            preset_key=self.getSelectedPresetKey(),
            batch_mode=self.batchModeCombo.currentText,
            use_totalsegmentator=self.useTotalSegmentator.checked,
            save_report=self.saveReportCheck.checked,
            report_mode=self.reportModeCombo.currentText,
            export_html_report=self.exportHtmlReportCheck.checked,
            generate_preop_checklist=self.preopChecklistCheck.checked,
            auto_capture_screenshots=self.autoScreenshotsCheck.checked,
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

    def _buildRecomputeConfig(self):
        return AnalysisConfig(
            preset_key=self.getSelectedPresetKey(),
            batch_mode="active",
            use_totalsegmentator=False,
            save_report=self.saveReportCheck.checked,
            report_mode=self.reportModeCombo.currentText,
            export_html_report=self.exportHtmlReportCheck.checked,
            generate_preop_checklist=self.preopChecklistCheck.checked,
            auto_capture_screenshots=self.autoScreenshotsCheck.checked,
            export_results=False,
            export_rtstruct=False,
        )

    def _autoRecomputeAfterRoundTrip(self):
        if not self.lastVolumeNodeId or not self.lastSegmentationNodeId:
            return
        try:
            pipeline_path = os.path.abspath(os.path.join(REPO_ROOT, "slicer_scripts", "ent_analysis_pipeline.py"))
            module = self._load_python_module("ent_analysis_pipeline_runtime_roundtrip_recompute", pipeline_path)
            config = self._buildRecomputeConfig()
            result = module.recompute_ent_analysis(self.lastVolumeNodeId, self.lastSegmentationNodeId, config, log_callback=self.appendOutput)
            self.lastResult = result
            self.appendOutput(f"Round-trip recompute completed: {result.get('preset')}")
            if result.get("reportPath"):
                self.appendOutput(f"Report: {result.get('reportPath')}")
            if result.get("htmlReportPath"):
                self.appendOutput(f"HTML report: {result.get('htmlReportPath')}")
            sinus_report = result.get("sinusReport")
            if sinus_report:
                self.populateFindingsTable(sinus_report.get("findingRows") or [])
                self.appendOutput("")
                self.appendOutput(sinus_report.get("reportText", ""))
            else:
                mri_report = result.get("mriReport")
                if mri_report:
                    self.populateFindingsTable(mri_report.get("findingRows") or [])
                    self.appendOutput("")
                    self.appendOutput(mri_report.get("reportText", ""))
        except Exception as error:
            self.appendOutput(f"Round-trip recompute warning: {error}")

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
            if self.getSelectedPresetKey() == "mri_ent_support":
                self.output.setText(
                    "MRI workflow uses report text and slice screenshots. "
                    "These 3D view buttons are CT/FESS-oriented and are intentionally disabled for MRI studies."
                )
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
