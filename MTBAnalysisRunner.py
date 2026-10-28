import FreeCAD
import FreeCADGui
import subprocess
import os
from PySide import QtCore, QtGui

# ---------------------------------------------------------------------------
# Path Resolution & Directory Setup
# ---------------------------------------------------------------------------
try:
    import MTB_Design
    _MODULE_PATH = MTB_Design.get_module_path()
except Exception:
    # Fallback if run as standalone macro
    _MODULE_PATH = os.path.dirname(__file__)

BIKES_DIR = os.path.join(_MODULE_PATH, "Bikes")
RIDERS_DIR = os.path.join(_MODULE_PATH, "Riders")

# Ensure directories exist
for d in [BIKES_DIR, RIDERS_DIR]:
    if not os.path.exists(d):
        try:
            os.makedirs(d, exist_ok=True)
        except Exception:
            pass

# ---------------------------------------------------------------------------
# Task Panel UI for Running Rust Analysis Engine
# ---------------------------------------------------------------------------
class MTBAnalysisTaskPanel:
    def __init__(self):
        self.form = QtGui.QWidget()
        self.layout = QtGui.QVBoxLayout(self.form)
        
        title_label = QtGui.QLabel("<b>MTB Kinematics & Rider Fit Analysis Runner</b>")
        self.layout.addWidget(title_label)
        
        instructions = QtGui.QLabel(
            "Select a saved bike profile and rider biometric profile, then execute the Rust backend solver."
        )
        instructions.setWordWrap(True)
        self.layout.addWidget(instructions)
        
        # Scroll area for clean layout structure
        scroll_area = QtGui.QScrollArea()
        scroll_widget = QtGui.QWidget()
        grid = QtGui.QGridLayout(scroll_widget)
        
        row = 0
        
        # ----------------------------------------------------
        # Profile Selection Section
        # ----------------------------------------------------
        # Bike Selection
        grid.addWidget(QtGui.QLabel("<b>Select Bike Profile:</b>"), row, 0)
        self.bike_combo = QtGui.QComboBox()
        grid.addWidget(self.bike_combo, row, 1)
        row += 1
        
        # Rider Selection
        grid.addWidget(QtGui.QLabel("<b>Select Rider Profile:</b>"), row, 0)
        self.rider_combo = QtGui.QComboBox()
        grid.addWidget(self.rider_combo, row, 1)
        row += 1
        
        # Refresh Button for Profiles
        self.refresh_btn = QtGui.QPushButton("Refresh Profile Lists")
        self.refresh_btn.clicked.connect(self.refresh_lists)
        grid.addWidget(self.refresh_btn, row, 0, 1, 2)
        row += 1
        
        # Separator line
        line = QtGui.QFrame()
        line.setFrameShape(QtGui.QFrame.HLine)
        line.setFrameShadow(QtGui.QFrame.Sunken)
        grid.addWidget(line, row, 0, 1, 2)
        row += 1
        
        # ----------------------------------------------------
        # Rust Binary Path Configuration
        # ----------------------------------------------------
        grid.addWidget(QtGui.QLabel("<b>Rust Executable Path:</b>"), row, 0)
        default_rust_path = os.path.expanduser("~/projects/mtb_analytics/target/release/mtb_solver")
        self.rust_path_edit = QtGui.QLineEdit(default_rust_path)
        grid.addWidget(self.rust_path_edit, row, 1)
        row += 1
        
        scroll_widget.setLayout(grid)
        scroll_area.setWidget(scroll_widget)
        scroll_area.setWidgetResizable(True)
        self.layout.addWidget(scroll_area)
        
        # Populate initial combo items
        self.refresh_lists()
        
        # ----------------------------------------------------
        # Action Execution Button
        # ----------------------------------------------------
        self.run_btn = QtGui.QPushButton("Execute Rust Analysis Engine")
        self.run_btn.setStyleSheet("font-weight: bold; background-color: #d0f0c0; padding: 10px;")
        self.run_btn.clicked.connect(self.execute_rust_engine)
        self.layout.addWidget(self.run_btn)

    def refresh_lists(self):
        # Populate Bikes
        self.bike_combo.clear()
        if os.path.exists(BIKES_DIR):
            bike_files = [f[:-5] for f in os.listdir(BIKES_DIR) if f.endswith(".json")]
            if bike_files:
                self.bike_combo.addItems(sorted(bike_files))
            else:
                self.bike_combo.addItem("-- No saved bikes --")
                
        # Populate Riders
        self.rider_combo.clear()
        if os.path.exists(RIDERS_DIR):
            rider_files = [f[:-5] for f in os.listdir(RIDERS_DIR) if f.endswith(".json")]
            if rider_files:
                self.rider_combo.addItems(sorted(rider_files))
            else:
                self.rider_combo.addItem("-- No saved riders --")

    def execute_rust_engine(self):
        selected_bike = self.bike_combo.currentText()
        selected_rider = self.rider_combo.currentText()
        
        if not selected_bike or selected_bike.startswith("--"):
            QtGui.QMessageBox.warning(self.form, "Missing Selection", "Please select a valid bike profile.")
            return
            
        if not selected_rider or selected_rider.startswith("--"):
            QtGui.QMessageBox.warning(self.form, "Missing Selection", "Please select a valid rider profile.")
            return
            
        bike_json_path = os.path.join(BIKES_DIR, f"{selected_bike}.json")
        rider_json_path = os.path.join(RIDERS_DIR, f"{selected_rider}.json")
        
        if not os.path.exists(bike_json_path):
            QtGui.QMessageBox.critical(self.form, "File Error", f"Bike JSON not found at:\n{bike_json_path}")
            return
            
        if not os.path.exists(rider_json_path):
            QtGui.QMessageBox.critical(self.form, "File Error", f"Rider JSON not found at:\n{rider_json_path}")
            return
            
        rust_binary_path = self.rust_path_edit.text().strip()
        if not os.path.exists(rust_binary_path):
            QtGui.QMessageBox.warning(
                self.form, 
                "Rust Binary Notice", 
                f"Selected profiles ready:\nBike: {bike_json_path}\nRider: {rider_json_path}\n\n(Rust binary not found at specified path: {rust_binary_path})"
            )
            return

        # Execute Rust Program via Subprocess
        # Example command structure: mtb_solver --bike <bike_path> --rider <rider_path>
        try:
            FreeCAD.Console.PrintMessage(f"Running Rust solver:\n  Binary: {rust_binary_path}\n  Bike: {bike_json_path}\n  Rider: {rider_json_path}\n")
            
            result = subprocess.run(
                [rust_binary_path, "--bike", bike_json_path, "--rider", rider_json_path],
                capture_output=True,
                text=True,
                check=True
            )
            
            FreeCAD.Console.PrintMessage("--- Rust Backend Output ---\n" + result.stdout)
            QtGui.QMessageBox.information(
                self.form, 
                "Success", 
                "Rust kinematics & fit analysis executed successfully!"
            )
            
        except subprocess.CalledProcessError as e:
            FreeCAD.Console.PrintError("Rust execution failed:\n" + e.stderr)
            QtGui.QMessageBox.critical(
                self.form, 
                "Execution Error", 
                f"Rust solver failed with exit code {e.returncode}:\n{e.stderr}"
            )
        except Exception as e:
            FreeCAD.Console.PrintError(f"Unexpected error running Rust binary: {str(e)}\n")
            QtGui.QMessageBox.critical(self.form, "Error", f"Failed to execute binary: {str(e)}")

    def accept(self):
        FreeCADGui.Control.closeDialog()

    def reject(self):
        FreeCADGui.Control.closeDialog()

# ---------------------------------------------------------------------------
# FreeCAD Command Registration
# ---------------------------------------------------------------------------
class OpenMTBAnalysisCommand:
    def GetResources(self):
        icon_path = os.path.join(MTB_Design.get_module_path(), "Resources", "icons", "Rust.svg")
        return {
            'Pixmap': icon_path, 
            'MenuText': 'Run MTB Analysis',
            'ToolTip': 'Select bike and rider profiles and execute the Rust analytics engine'
        }

    def Activated(self):
        panel = MTBAnalysisTaskPanel()
        FreeCADGui.Control.showDialog(panel)

    def IsActive(self):
        return FreeCAD.ActiveDocument is not None

FreeCADGui.addCommand('MTB_Analysis_Runner', OpenMTBAnalysisCommand())