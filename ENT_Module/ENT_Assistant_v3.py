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

        title = qt.QLabel(
            "<h2>ENT Assistant v3</h2>"
            "<p>Analyze ENT and head CT studies with threshold presets or open-source AI segmentation.</p>"
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

        self.useTotalSegmentator = qt.QCheckBox("Use TotalSegmentator when available")
        self.useTotalSegmentator.checked = True
        layout.addWidget(self.useTotalSegmentator)

        self.saveReportCheck = qt.QCheckBox("Save JSON report to repository /reports")
        self.saveReportCheck.checked = True
        layout.addWidget(self.saveReportCheck)

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

        self.runBtn = qt.QPushButton("Run CT analysis")
        self.runBtn.clicked.connect(self.runPipeline)
        layout.addWidget(self.runBtn)

        self.stackBtn = qt.QPushButton("Check open-source stack")
        self.stackBtn.clicked.connect(self.checkOpenSourceStack)
        layout.addWidget(self.stackBtn)

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

        self.presetCombo.currentIndexChanged.connect(self.updatePresetDescription)
        self.updatePresetDescription()

    def runPipeline(self):
        try:
            pipeline_path = os.path.abspath(os.path.join(REPO_ROOT, "slicer_scripts", "ent_analysis_pipeline.py"))
            module = self._load_python_module("ent_analysis_pipeline_runtime", pipeline_path)
            config = AnalysisConfig(
                preset_key=self.getSelectedPresetKey(),
                use_totalsegmentator=self.useTotalSegmentator.checked,
                save_report=self.saveReportCheck.checked,
                bone_threshold_min=self.boneMinSpin.value,
                bone_threshold_max=self.boneMaxSpin.value,
                air_threshold_min=self.airMinSpin.value,
                air_threshold_max=self.airMaxSpin.value,
            )

            self.output.clear()
            result = module.run_ent_analysis(config, log_callback=self.appendOutput)
            self.appendOutput("")
            self.appendOutput(f"Completed preset: {result['preset']}")
            if result.get("reportPath"):
                self.appendOutput(f"Report: {result['reportPath']}")
        except Exception as error:
            self.output.setText(f"Pipeline error:\n{error}")

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

    def _load_python_module(self, module_name, path):
        spec = importlib.util.spec_from_file_location(module_name, path)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return module
