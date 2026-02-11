import os
import subprocess
import slicer
import qt
from slicer.ScriptedLoadableModule import *


#
# ===============================
# MODULE
# ===============================
#

class ENT_Assistant_v3(ScriptedLoadableModule):
    def __init__(self, parent):
        super().__init__(parent)
        parent.title = "ENT Assistant v3"
        parent.categories = ["ENT"]
        parent.contributors = ["ENT AI Assistant (2026)"]
        parent.helpText = "ENT Development Environment"
        parent.acknowledgementText = "Dev + Git integrated version"


#
# ===============================
# WIDGET
# ===============================
#

class ENT_Assistant_v3Widget(ScriptedLoadableModuleWidget):

    def setup(self):
        super().setup()
        layout = self.layout

        layout.addWidget(qt.QLabel("<h2>ENT Assistant v3 - Dev Mode</h2>"))

        # --------------------------------
        # LOR 3D Pipeline
        # --------------------------------
        self.runBtn = qt.QPushButton("🚀 Запустить LOR 3D Pipeline")
        layout.addWidget(self.runBtn)
        self.runBtn.clicked.connect(self.runPipeline)

        # --------------------------------
        # DEV Script
        # --------------------------------
        self.devBtn = qt.QPushButton("🧪 Запустить DEV Script")
        layout.addWidget(self.devBtn)
        self.devBtn.clicked.connect(self.runDevScript)

        # --------------------------------
        # Git Update
        # --------------------------------
        self.updateBtn = qt.QPushButton("🔄 Git Pull (Обновить)")
        layout.addWidget(self.updateBtn)
        self.updateBtn.clicked.connect(self.updateFromGit)

        # --------------------------------
        # Git Save + Push
        # --------------------------------
        self.pushBtn = qt.QPushButton("💾 Git Save + Push")
        layout.addWidget(self.pushBtn)
        self.pushBtn.clicked.connect(self.saveAndPush)

        # --------------------------------
        # Reload Module
        # --------------------------------
        self.reloadBtn = qt.QPushButton("♻ Reload Module")
        layout.addWidget(self.reloadBtn)
        self.reloadBtn.clicked.connect(self.reloadModule)

        # Output
        self.output = qt.QTextEdit()
        self.output.setReadOnly(True)
        layout.addWidget(self.output)


    # ===============================
    # RUN LOR PIPELINE
    # ===============================
    def runPipeline(self):
        try:
            script_path = os.path.abspath(
                os.path.join(os.path.dirname(__file__), "..", "slicer_scripts", "ENT_LOR_3D_PIPELINE.py")
            )

            exec(open(script_path).read())

            self.output.setText("✅ LOR 3D Pipeline выполнен")

        except Exception as e:
            self.output.setText(f"❌ Ошибка Pipeline:\n{str(e)}")


    # ===============================
    # RUN DEV SCRIPT
    # ===============================
    def runDevScript(self):
        try:
            script_path = os.path.abspath(
                os.path.join(os.path.dirname(__file__), "..", "slicer_scripts", "dev.py")
            )

            exec(open(script_path).read())

            self.output.setText("✅ DEV script выполнен")

        except Exception as e:
            self.output.setText(f"❌ Ошибка DEV:\n{str(e)}")


    # ===============================
    # GIT PULL
    # ===============================
    def updateFromGit(self):
        try:
            repo_path = os.path.abspath(
                os.path.join(os.path.dirname(__file__), "..")
            )

            result = subprocess.run(
                ["git", "pull"],
                cwd=repo_path,
                capture_output=True,
                text=True
            )

            if result.returncode == 0:
                self.output.setText("✅ Git Pull выполнен\n\n" + result.stdout)
            else:
                self.output.setText("❌ Git Pull ошибка\n\n" + result.stderr)

        except Exception as e:
            self.output.setText(f"❌ Ошибка:\n{str(e)}")


    # ===============================
    # GIT ADD + COMMIT + PUSH
    # ===============================
    def saveAndPush(self):
        try:
            repo_path = os.path.abspath(
                os.path.join(os.path.dirname(__file__), "..")
            )

            subprocess.run(["git", "add", "."], cwd=repo_path)

            subprocess.run(
                ["git", "commit", "-m", "Auto update from ENT module"],
                cwd=repo_path
            )

            result = subprocess.run(
                ["git", "push"],
                cwd=repo_path,
                capture_output=True,
                text=True
            )

            if result.returncode == 0:
                self.output.setText("✅ Git Push выполнен\n\n" + result.stdout)
            else:
                self.output.setText("⚠ Возможно нет изменений\n\n" + result.stderr)

        except Exception as e:
            self.output.setText(f"❌ Ошибка Push:\n{str(e)}")


    # ===============================
    # RELOAD MODULE
    # ===============================
    def reloadModule(self):
        slicer.util.reloadScriptedModule("ENT_Assistant_v3")
