__title__ = "FreeCAD MTB_Design Workbench - Init file"
__author__ = "Vincent Volpone"
__url__ = ["http://www.freecadweb.org"]


class MTB_Design(Workbench):
    def __init__(self):
        import os

        from commands import MTB_Design

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
            MTB_Design.get_module_path(), "Resources", "icons", "curvedArray.svg"
        )

    def Initialize(self):
        "This function is executed when FreeCAD starts"
        # import here all the needed files that create your FreeCAD commands
        from PySide.QtCore import QT_TRANSLATE_NOOP

        self.examples = [
            "Horten_HIX",
            "FlyingWingS800",
            "FishingLure",
        ]  # A list of command names created in the line above
        self.list = [
            "CurvedArray",
            "CurvedPathArray",
            "CurvedSegment",
            "CurvedPathSegment",
            "InterpolatedMiddle",
            "SurfaceCut",
            "NotchConnector",
        ]  # A list of command names created in the line above
        self.appendToolbar(
            QT_TRANSLATE_NOOP("MTB Design", "MTB Design"), self.list
        )  # creates a new toolbar with your commands
        self.appendMenu(
            QT_TRANSLATE_NOOP("MTB Design", "MTB Design"), self.list
        )  # creates a new menu 'Curved Functions'
        self.appendMenu("MTB Design", "Separator")  # creates a new menu separator
        self.appendMenu(
            QT_TRANSLATE_NOOP("MTB Design", "Examples"), self.examples
        )  # creates a new menu

    def Activated(self):
        "This function is executed when the workbench is activated"
        return

    def Deactivated(self):
        "This function is executed when the workbench is deactivated"
        return

    def ContextMenu(self, recipient):
        "This is executed whenever the user right-clicks on screen"
        # 'recipient' will be either 'view' or 'tree'
        self.appendContextMenu(
            QT_TRANSLATE_NOOP("MTB Design", "MTB Design"), self.list
        )  # add commands to the context menu

    def GetClassName(self):
        # this function is mandatory if this is a full python workbench
        return "Gui::PythonWorkbench"


Gui.addWorkbench(MTB_Design())
