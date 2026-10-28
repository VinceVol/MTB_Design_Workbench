__title__ = "FreeCAD MTB_Design Workbench - Init file"
__author__ = "Vincent Volpone"
__url__ = ["http://www.freecadweb.org"]


class MTB_Design(Workbench):
    def __init__(self):
        import os
        import MTB_Design

        translate = FreeCAD.Qt.translate
        translations_path = os.path.join(
            os.path.join(MTB_Design.get_module_path(), "Resources", "translations")
        )
        FreeCADGui.addLanguagePath(translations_path)
        FreeCADGui.updateLocale()

        self.__class__.MenuText = "MTB Design"
        self.__class__.ToolTip = translate(
            "Workbench", "Analyze MTB design for given rider"
        )
        self.__class__.Icon = os.path.join(
            MTB_Design.get_module_path(),
            "Resources",
            "icons",
            "MTB Design Icon.svg",
        )

    def Initialize(self):
        "This function is executed when FreeCAD starts"

        # Import all command modules to register their respective FreeCADGui commands
        import MTBKinematicsPicker
        import MTBRiderFit
        import MTBAnalysisRunner

        from PySide.QtCore import QT_TRANSLATE_NOOP

        # Add all three tools to the active workbench list
        self.list = [
            "MTB_Kinematics_Mapper",
            "MTB_Rider_Fit_Input",
            "MTB_Analysis_Runner",
        ]

        self.appendToolbar(
            QT_TRANSLATE_NOOP("MTB Design", "MTB Design Tools"), self.list
        )
        self.appendMenu(QT_TRANSLATE_NOOP("MTB Design", "MTB Design"), self.list)

    def Activated(self):
        return

    def Deactivated(self):
        return

    def ContextMenu(self, recipient):
        self.appendContextMenu(QT_TRANSLATE_NOOP("MTB Design", "MTB Design"), self.list)

    def GetClassName(self):
        return "Gui::PythonWorkbench"


Gui.addWorkbench(MTB_Design())
