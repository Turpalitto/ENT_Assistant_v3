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
        parent.helpText = "Автоматизированный анализ КТ околоносовых пазух"
        parent.acknowledgementText = "Не заменяет клиническое решение врача"


#
# ===============================
# WIDGET
# ===============================
#

class ENT_Assistant_v3Widget(ScriptedLoadableModuleWidget):

    def setup(self):
        super().setup()
        layout = self.layout

        layout.addWidget(qt.QLabel("<h2>ENT Assistant v3</h2>"))

        # -------------------------------
        # Запуск 3D Pipeline
        # -------------------------------
        self.runBtn = qt.QPushButton("🚀 Запустить LOR 3D Pipeline")
        layout.addWidget(self.runBtn)
        self.runBtn.clicked.connect(self.runPipeline)

        # -------------------------------
        # Git Update
        # -------------------------------
        self.updateBtn = qt.QPushButton("🔄 Обновить из GitHub")
        layout.addWidget(self.updateBtn)
        self.updateBtn.clicked.connect(self.updateFromGit)

        # -------------------------------
        # Reload Module
        # -------------------------------
        self.reloadBtn = qt.QPushButton("♻ Reload Module")
        layout.addWidget(self.reloadBtn)
        self.reloadBtn.clicked.connect(self.reloadModule)

        # Output field
        self.output = qt.QTextEdit()
        self.output.setReadOnly(True)
        layout.addWidget(self.output)

    # ===============================
    # RUN PIPELINE
    # ===============================
    def runPipeline(self):

        try:
            script_path = os.path.abspath(
                os.path.join(os.path.dirname(__file__), "..", "slicer_scripts", "ENT_LOR_3D_PIPELINE.py")
            )

            exec(open(script_path).read())

            self.output.setText("✅ Pipeline выполнен успешно")

        except Exception as e:
            self.output.setText(f"❌ Ошибка:\n{str(e)}")

    # ===============================
    # GIT UPDATE
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
                self.output.setText("✅ Обновление выполнено\n\n" + result.stdout)
            else:
                self.output.setText("❌ Ошибка обновления\n\n" + result.stderr)

        except Exception as e:
            self.output.setText(f"❌ Ошибка:\n{str(e)}")

    # ===============================
    # RELOAD MODULE
    # ===============================
    def reloadModule(self):
        slicer.util.reloadScriptedModule("ENT_Assistant_v3")
