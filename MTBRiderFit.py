import FreeCAD
import FreeCADGui
import json
import os
from PySide import QtCore, QtGui

# ---------------------------------------------------------------------------
# Path Resolution & Riders Directory Setup
# ---------------------------------------------------------------------------
try:
    import MTB_Design
    _MODULE_PATH = MTB_Design.get_module_path()
except Exception:
    # Fallback if run as standalone macro
    _MODULE_PATH = os.path.dirname(__file__)

RIDERS_DIR = os.path.join(_MODULE_PATH, "Riders")
if not os.path.exists(RIDERS_DIR):
    try:
        os.makedirs(RIDERS_DIR, exist_ok=True)
    except Exception:
        pass

# ---------------------------------------------------------------------------
# Module-level persistent cache across window open/close sessions
# ---------------------------------------------------------------------------
_RIDER_SESSION_CACHE = {
    "profile_name": "default_rider",
    "inseam": 820.0,      # mm
    "arm_length": 650.0,  # mm
    "torso_length": 600.0,# mm
    "rider_weight": 75.0, # kg
    "units_weight": "kg"
}

# ---------------------------------------------------------------------------
# Task Panel UI for Rider Characteristics & Biometric Fit
# ---------------------------------------------------------------------------
class MTBRiderFitTaskPanel:
    def __init__(self):
        self.form = QtGui.QWidget()
        self.layout = QtGui.QVBoxLayout(self.form)
        
        title_label = QtGui.QLabel("<b>Rider Biometric & Fit Characteristics</b>")
        self.layout.addWidget(title_label)
        
        instructions = QtGui.QLabel(
            "Manage rider profiles, adjust biometric dimensions, and save/load profiles from the Riders/ folder."
        )
        instructions.setWordWrap(True)
        self.layout.addWidget(instructions)
        
        # Scroll area for clean layout structure
        scroll_area = QtGui.QScrollArea()
        scroll_widget = QtGui.QWidget()
        grid = QtGui.QGridLayout(scroll_widget)
        
        row = 0
        
        # ----------------------------------------------------
        # Profile Manager Section (Load & Select)
        # ----------------------------------------------------
        load_group = QtGui.QGroupBox("Profile Manager")
        load_layout = QtGui.QHBoxLayout(load_group)
        
        load_layout.addWidget(QtGui.QLabel("Saved Profiles:"))
        self.profile_combo = QtGui.QComboBox()
        self.refresh_profile_list()
        load_layout.addWidget(self.profile_combo)
        
        load_btn = QtGui.QPushButton("Load Profile")
        load_btn.clicked.connect(self.load_selected_profile)
        load_layout.addWidget(load_btn)
        
        grid.addWidget(load_group, row, 0, 1, 3)
        row += 1
        
        # Profile Name Input (for saving)
        grid.addWidget(QtGui.QLabel("<b>Profile Filename:</b>"), row, 0)
        self.profile_name_edit = QtGui.QLineEdit(_RIDER_SESSION_CACHE["profile_name"])
        grid.addWidget(self.profile_name_edit, row, 1, 1, 2)
        row += 1
        
        # ----------------------------------------------------
        # Form Fields Configuration
        # ----------------------------------------------------
        # Inseam / Leg Length
        grid.addWidget(QtGui.QLabel("<b>Inseam / Leg Length:</b>"), row, 0)
        self.inseam_spin = QtGui.QDoubleSpinBox()
        self.inseam_spin.setRange(300.0, 1200.0)
        self.inseam_spin.setValue(_RIDER_SESSION_CACHE["inseam"])
        self.inseam_spin.setSingleStep(5.0)
        grid.addWidget(self.inseam_spin, row, 1)
        grid.addWidget(QtGui.QLabel("mm"), row, 2)
        row += 1
        
        # Arm Length (Reach)
        grid.addWidget(QtGui.QLabel("<b>Arm Length (Shoulder-Wrist):</b>"), row, 0)
        self.arm_spin = QtGui.QDoubleSpinBox()
        self.arm_spin.setRange(300.0, 1000.0)
        self.arm_spin.setValue(_RIDER_SESSION_CACHE["arm_length"])
        self.arm_spin.setSingleStep(5.0)
        grid.addWidget(self.arm_spin, row, 1)
        grid.addWidget(QtGui.QLabel("mm"), row, 2)
        row += 1
        
        # Torso Length
        grid.addWidget(QtGui.QLabel("<b>Torso Length:</b>"), row, 0)
        self.torso_spin = QtGui.QDoubleSpinBox()
        self.torso_spin.setRange(300.0, 900.0)
        self.torso_spin.setValue(_RIDER_SESSION_CACHE["torso_length"])
        self.torso_spin.setSingleStep(5.0)
        grid.addWidget(self.torso_spin, row, 1)
        grid.addWidget(QtGui.QLabel("mm"), row, 2)
        row += 1
        
        # Rider Weight
        grid.addWidget(QtGui.QLabel("<b>Rider Weight (Kit On):</b>"), row, 0)
        self.weight_spin = QtGui.QDoubleSpinBox()
        self.weight_spin.setRange(30.0, 200.0)
        self.weight_spin.setValue(_RIDER_SESSION_CACHE["rider_weight"])
        self.weight_spin.setSingleStep(0.5)
        grid.addWidget(self.weight_spin, row, 1)
        
        # Weight unit selector (kg / lbs)
        self.weight_unit_combo = QtGui.QComboBox()
        self.weight_unit_combo.addItems(["kg", "lbs"])
        if _RIDER_SESSION_CACHE["units_weight"] == "lbs":
            self.weight_unit_combo.setCurrentIndex(1)
        grid.addWidget(self.weight_unit_combo, row, 2)
        
        scroll_widget.setLayout(grid)
        scroll_area.setWidget(scroll_widget)
        scroll_area.setWidgetResizable(True)
        self.layout.addWidget(scroll_area)
        
        # ----------------------------------------------------
        # Action Buttons
        # ----------------------------------------------------
        btn_layout = QtGui.QHBoxLayout()
        
        self.save_export_btn = QtGui.QPushButton("Save Profile to Riders/")
        self.save_export_btn.setStyleSheet("font-weight: bold; background-color: #d0f0c0; padding: 8px;")
        self.save_export_btn.clicked.connect(self.export_rider_profile)
        
        self.reset_btn = QtGui.QPushButton("Reset Defaults")
        self.reset_btn.clicked.connect(self.reset_defaults)
        
        btn_layout.addWidget(self.save_export_btn)
        btn_layout.addWidget(self.reset_btn)
        self.layout.addLayout(btn_layout)

    def refresh_profile_list(self):
        self.profile_combo.clear()
        if os.path.exists(RIDERS_DIR):
            files = [f[:-5] for f in os.listdir(RIDERS_DIR) if f.endswith(".json")]
            if files:
                self.profile_combo.addItems(sorted(files))
            else:
                self.profile_combo.addItem("-- No saved profiles --")

    def load_selected_profile(self):
        selected = self.profile_combo.currentText()
        if not selected or selected.startswith("--"):
            return
            
        json_path = os.path.join(RIDERS_DIR, f"{selected}.json")
        if not os.path.exists(json_path):
            QtGui.QMessageBox.warning(self.form, "File Not Found", f"Could not find profile file: {json_path}")
            return
            
        try:
            with open(json_path, "r") as f:
                data = json.load(f)
                
            rider_data = data.get("rider_characteristics", {})
            
            # Populate UI fields
            self.profile_name_edit.setText(selected)
            self.inseam_spin.setValue(rider_data.get("inseam_leg_length", 820.0))
            self.arm_spin.setValue(rider_data.get("arm_length", 650.0))
            self.torso_spin.setValue(rider_data.get("torso_length", 600.0))
            self.weight_spin.setValue(rider_data.get("rider_weight", 75.0))
            
            units = rider_data.get("weight_units", "kg")
            if units == "lbs":
                self.weight_unit_combo.setCurrentIndex(1)
            else:
                self.weight_unit_combo.setCurrentIndex(0)
                
            self.update_cache_from_ui()
            FreeCAD.Console.PrintMessage(f"Successfully loaded rider profile: {selected}\n")
        except Exception as e:
            FreeCAD.Console.PrintError(f"Failed to load profile: {str(e)}\n")
            QtGui.QMessageBox.critical(self.form, "Load Error", f"Could not load profile: {str(e)}")

    def update_cache_from_ui(self):
        _RIDER_SESSION_CACHE["profile_name"] = self.profile_name_edit.text().strip() or "default_rider"
        _RIDER_SESSION_CACHE["inseam"] = self.inseam_spin.value()
        _RIDER_SESSION_CACHE["arm_length"] = self.arm_spin.value()
        _RIDER_SESSION_CACHE["torso_length"] = self.torso_spin.value()
        _RIDER_SESSION_CACHE["rider_weight"] = self.weight_spin.value()
        _RIDER_SESSION_CACHE["units_weight"] = self.weight_unit_combo.currentText()

    def reset_defaults(self):
        self.profile_name_edit.setText("default_rider")
        self.inseam_spin.setValue(820.0)
        self.arm_spin.setValue(650.0)
        self.torso_spin.setValue(600.0)
        self.weight_spin.setValue(75.0)
        self.weight_unit_combo.setCurrentIndex(0)
        self.update_cache_from_ui()
        FreeCAD.Console.PrintMessage("Rider characteristics reset to default values.\n")

    def export_rider_profile(self):
        self.update_cache_from_ui()
        profile_name = _RIDER_SESSION_CACHE["profile_name"]
        
        # Ensure directory exists
        if not os.path.exists(RIDERS_DIR):
            os.makedirs(RIDERS_DIR, exist_ok=True)
            
        json_path = os.path.join(RIDERS_DIR, f"{profile_name}.json")
        
        payload = {
            "profile_name": profile_name,
            "rider_characteristics": {
                "inseam_leg_length": _RIDER_SESSION_CACHE["inseam"],
                "arm_length": _RIDER_SESSION_CACHE["arm_length"],
                "torso_length": _RIDER_SESSION_CACHE["torso_length"],
                "rider_weight": _RIDER_SESSION_CACHE["rider_weight"],
                "weight_units": _RIDER_SESSION_CACHE["units_weight"],
                "length_units": "mm"
            }
        }
        
        try:
            with open(json_path, "w") as f:
                json.dump(payload, f, indent=4)
            
            self.refresh_profile_list()
            # Reselect the saved profile in combo
            index = self.profile_combo.findText(profile_name)
            if index >= 0:
                self.profile_combo.setCurrentIndex(index)
                
            FreeCAD.Console.PrintMessage(f"Rider profile successfully saved to {json_path}\n")
            QtGui.QMessageBox.information(
                self.form, 
                "Save Successful", 
                f"Rider profile saved successfully to:\n{json_path}"
            )
        except Exception as e:
            FreeCAD.Console.PrintError(f"Failed to save rider profile: {str(e)}\n")
            QtGui.QMessageBox.critical(self.form, "Save Error", f"Could not save file: {str(e)}")

    def accept(self):
        self.update_cache_from_ui()
        FreeCADGui.Control.closeDialog()

    def reject(self):
        self.update_cache_from_ui()
        FreeCADGui.Control.closeDialog()

# ---------------------------------------------------------------------------
# FreeCAD Command Registration for Rider Fit Tool
# ---------------------------------------------------------------------------
class OpenMTBRiderFitCommand:
    def GetResources(self):
        icon_path = os.path.join(MTB_Design.get_module_path(), "Resources", "icons", "Rider.svg")
        return {
            'Pixmap': icon_path,
            'MenuText': 'Input Rider Characteristics',
            'ToolTip': 'Launch biometric input panel and manage rider profile saves'
        }

    def Activated(self):
        panel = MTBRiderFitTaskPanel()
        FreeCADGui.Control.showDialog(panel)

    def IsActive(self):
        return FreeCAD.ActiveDocument is not None

FreeCADGui.addCommand('MTB_Rider_Fit_Input', OpenMTBRiderFitCommand())