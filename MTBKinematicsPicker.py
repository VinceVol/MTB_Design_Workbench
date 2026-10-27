import FreeCAD
import FreeCADGui
import json
import subprocess
import os
from PySide import QtCore, QtGui

# ---------------------------------------------------------------------------
# Selection Observer to capture vertex/point selections from the FreeCAD 3D view
# ---------------------------------------------------------------------------
class MTBSelectionObserver:
    def __init__(self, callback):
        self.callback = callback
        self.active = False

    def addSelection(self, doc, obj, sub, pnt):
        if not self.active:
            return
        
        obj_name = obj
        sub_name = sub
        
        try:
            freecad_obj = FreeCAD.ActiveDocument.getObject(obj_name)
            if not freecad_obj:
                return
            
            vector = None
            if pnt is not None:
                vector = FreeCAD.Vector(pnt)
            elif hasattr(freecad_obj, "Shape") and sub_name:
                sub_obj = freecad_obj.Shape.getSubObject(sub_name)
                if hasattr(sub_obj, "Point"):
                    vector = sub_obj.Point
                elif hasattr(sub_obj, "Vertexes") and len(sub_obj.Vertexes) > 0:
                    vector = sub_obj.Vertexes[0].Point
            
            if vector and self.callback:
                self.callback(obj_name, sub_name, vector)
            else:
                FreeCAD.Console.PrintWarning(f"Could not resolve coordinates for selection: {sub_name}\n")
                
        except Exception as e:
            FreeCAD.Console.PrintError(f"Selection error: {str(e)}\n")

    def clearSelection(self, doc):
        pass
    def setSelection(self, doc):
        pass
    def onDelete(self, doc):
        pass

# ---------------------------------------------------------------------------
# Task Panel UI for Interactive Geometry Mapping
# ---------------------------------------------------------------------------
class MTBKinematicsTaskPanel:
    def __init__(self):
        self.form = QtGui.QWidget()
        self.layout = QtGui.QVBoxLayout(self.form)
        
        # Static baseline slots (Axles, BB, Cockpit, Core Shocks/Pivots)
        self.baseline_slots = [
            ("rear_axle", "Rear Axle (Hub Center)", "point"),
            ("front_axle", "Front Axle (Hub Center)", "point"),
            ("bottom_bracket", "Bottom Bracket (BB Center)", "point"),
            ("seat_saddle", "Saddle / Seat Reference", "point"),
            ("handlebar_grip", "Handlebar / Grip Center", "point"),
            ("front_shock_mount", "Front Shock Mount (Mandatory)", "point"),
            ("rear_shock_mount", "Rear Shock Mount (Mandatory)", "point"),
            ("main_pivot", "Main Pivot (Mandatory)", "point")
        ]
        
        # Line slots (e.g., shock body assembly)
        self.line_slots = [
            ("rear_shock_assembly", "Rear Shock Line (Start & End Vertex)", "line")
        ]
        
        # Dynamic tracking containers
        self.collected_points = {slot[0]: None for slot in self.baseline_slots}
        self.collected_lines = {slot[0]: {"p1": None, "p2": None} for slot in self.line_slots}
        self.dynamic_pivots = {} # key -> {"label": str, "vector": Vector}
        
        self.ui_elements = {}
        self.dynamic_pivot_layout = None
        
        title_label = QtGui.QLabel("<b>Mountain Bike Kinematics Geometry Mapper</b>")
        self.layout.addWidget(title_label)
        
        instructions = QtGui.QLabel(
            "Pick core vertices or line segments. Add extra linkage pivots as needed."
        )
        instructions.setWordWrap(True)
        self.layout.addWidget(instructions)
        
        # Scroll area for layout structure
        scroll_area = QtGui.QScrollArea()
        scroll_widget = QtGui.QWidget()
        self.main_grid = QtGui.QVBoxLayout(scroll_widget)
        
        # Render Baseline Points
        self.build_slot_section("Base Geometry & Core Pivots", self.baseline_slots)
        
        # Render Line Segments
        self.build_slot_section("Linkage / Shock Lines", self.line_slots)
        
        # Render Dynamic Pivots Container
        dyn_group = QtGui.QGroupBox("Additional Linkage Pivots")
        self.dynamic_pivot_layout = QtGui.QVBoxLayout(dyn_group)
        
        add_pivot_btn = QtGui.QPushButton("+ Add Linkage Pivot")
        add_pivot_btn.clicked.connect(self.add_dynamic_pivot_slot)
        self.dynamic_pivot_layout.addWidget(add_pivot_btn)
        
        self.main_grid.addWidget(dyn_group)
        scroll_widget.setLayout(self.main_grid)
        scroll_area.setWidget(scroll_widget)
        scroll_area.setWidgetResizable(True)
        self.layout.addWidget(scroll_area)
        
        # Action Buttons
        self.run_rust_btn = QtGui.QPushButton("Run Rust Kinematics Engine")
        self.run_rust_btn.setStyleSheet("font-weight: bold; background-color: #d0f0c0; padding: 8px;")
        self.run_rust_btn.clicked.connect(self.execute_rust_backend)
        self.layout.addWidget(self.run_rust_btn)
        
        # Active selection state
        self.current_target = None # Can be slot key or (line_key, 'p1'/'p2')
        self.observer = MTBSelectionObserver(self.on_point_picked)
        FreeCADGui.Selection.addObserver(self.observer)

    def build_slot_section(self, title, slots):
        group = QtGui.QGroupBox(title)
        grid = QtGui.QGridLayout(group)
        
        for idx, (key, label_text, slot_type) in enumerate(slots):
            lbl = QtGui.QLabel(label_text)
            status_lbl = QtGui.QLabel("[ Not Set ]")
            status_lbl.setStyleSheet("color: red;")
            
            btn = QtGui.QPushButton("Pick")
            btn.clicked.connect(lambda checked=False, k=key, st=slot_type: self.activate_slot(k, st))
            
            grid.addWidget(lbl, idx, 0)
            grid.addWidget(status_lbl, idx, 1)
            grid.addWidget(btn, idx, 2)
            
            self.ui_elements[key] = {"status": status_lbl, "button": btn, "type": slot_type}
            
        self.main_grid.addWidget(group)

    def add_dynamic_pivot_slot(self):
        pivot_id = f"extra_pivot_{len(self.dynamic_pivots) + 1}"
        default_label = f"Linkage Pivot {len(self.dynamic_pivots) + 1}"
        
        self.dynamic_pivots[pivot_id] = {"vector": None}
        
        row_widget = QtGui.QWidget()
        row_layout = QtGui.QHBoxLayout(row_widget)
        row_layout.setContentsMargins(0, 0, 0, 0)
        
        name_edit = QtGui.QLineEdit(default_label)
        status_lbl = QtGui.QLabel("[ Not Set ]")
        status_lbl.setStyleSheet("color: red;")
        
        btn = QtGui.QPushButton("Pick")
        btn.clicked.connect(lambda checked=False, k=pivot_id: self.activate_slot(k, "dynamic_point"))
        
        row_layout.addWidget(name_edit)
        row_layout.addWidget(status_lbl)
        row_layout.addWidget(btn)
        
        self.ui_elements[pivot_id] = {"status": status_lbl, "button": btn, "type": "dynamic_point", "name_edit": name_edit}
        
        # Insert above the add button
        self.dynamic_pivot_layout.insertWidget(self.dynamic_pivot_layout.count() - 1, row_widget)

    def activate_slot(self, key, slot_type):
        for k, el in self.ui_elements.items():
            el["button"].setStyleSheet("")
            
        if slot_type == "line":
            # Start sequence for line: expect 2 vertex picks
            self.current_target = {"key": key, "stage": "p1"}
            FreeCAD.Console.PrintMessage(f"Select START vertex for line: {key}\n")
        else:
            self.current_target = {"key": key, "stage": "point"}
            FreeCAD.Console.PrintMessage(f"Listening for point: {key}\n")
            
        self.observer.active = True
        self.ui_elements[key]["button"].setStyleSheet("background-color: yellow;")

    def on_point_picked(self, obj_name, sub_name, vector):
        if not self.current_target:
            return
            
        target = self.current_target
        key = target["key"]
        stage = target["stage"]
        
        if stage == "point" or stage == "dynamic_point":
            if key in self.collected_points:
                self.collected_points[key] = {"x": vector.x, "y": vector.y, "z": vector.z}
            elif key in self.dynamic_pivots:
                self.dynamic_pivots[key]["vector"] = {"x": vector.x, "y": vector.y, "z": vector.z}
                
            coord_str = f"({vector.x:.2f}, {vector.y:.2f}, {vector.z:.2f})"
            self.ui_elements[key]["status"].setText(coord_str)
            self.ui_elements[key]["status"].setStyleSheet("color: green;")
            self.ui_elements[key]["button"].setStyleSheet("")
            
            self.observer.active = False
            self.current_target = None
            
        elif stage == "p1":
            self.collected_lines[key]["p1"] = {"x": vector.x, "y": vector.y, "z": vector.z}
            coord_str = f"P1:({vector.x:.1f},{vector.y:.1f}) -> Pick P2"
            self.ui_elements[key]["status"].setText(coord_str)
            self.ui_elements[key]["status"].setStyleSheet("color: orange;")
            
            # Transition to stage p2
            self.current_target["stage"] = "p2"
            FreeCAD.Console.PrintMessage(f"Select END vertex for line: {key}\n")
            
        elif stage == "p2":
            self.collected_lines[key]["p2"] = {"x": vector.x, "y": vector.y, "z": vector.z}
            p1 = self.collected_lines[key]["p1"]
            p2 = self.collected_lines[key]["p2"]
            
            coord_str = f"Line Set ({p1['x']:.1f},{p1['y']:.1f} to {p2['x']:.1f},{p2['y']:.1f})"
            self.ui_elements[key]["status"].setText(coord_str)
            self.ui_elements[key]["status"].setStyleSheet("color: green;")
            self.ui_elements[key]["button"].setStyleSheet("")
            
            self.observer.active = False
            self.current_target = None

    def execute_rust_backend(self):
        # Validate mandatory items
        mandatory_keys = ["front_shock_mount", "rear_shock_mount", "main_pivot"]
        missing = [k for k in mandatory_keys if self.collected_points.get(k) is None]
        
        if missing:
            QtGui.QMessageBox.warning(
                self.form, 
                "Mandatory Geometry Missing", 
                f"Please ensure mandatory points are set: {', '.join(missing)}"
            )
            return

        # Bundle dynamic pivots with custom names if specified
        formatted_dynamic_pivots = {}
        for k, data in self.dynamic_pivots.items():
            if data["vector"] is not None:
                custom_name = self.ui_elements[k]["name_edit"].text().strip() or k
                formatted_dynamic_pivots[custom_name] = data["vector"]

        payload = {
            "base_points": self.collected_points,
            "lines": self.collected_lines,
            "additional_pivots": formatted_dynamic_pivots,
            "units": "mm"
        }

        import tempfile
        temp_dir = tempfile.gettempdir()
        json_path = os.path.join(temp_dir, "mtb_kinematics_input.json")
        
        with open(json_path, "w") as f:
            json.dump(payload, f, indent=4)
            
        FreeCAD.Console.PrintMessage(f"Exported kinematics payload to {json_path}\n")
        
        rust_binary_path = os.path.expanduser("~/projects/mtb_analytics/target/release/mtb_solver")
        if not os.path.exists(rust_binary_path):
            QtGui.QMessageBox.information(
                self.form, 
                "Rust Binary Notice", 
                f"Data exported successfully to:\n{json_path}\n\n(Rust binary not found at default path)"
            )
            return

        try:
            result = subprocess.run(
                [rust_binary_path, "--input", json_path],
                capture_output=True,
                text=True,
                check=True
            )
            FreeCAD.Console.PrintMessage("--- Rust Backend Output ---\n" + result.stdout)
            QtGui.QMessageBox.information(self.form, "Success", "Rust kinematics solver executed successfully!")
        except subprocess.CalledProcessError as e:
            FreeCAD.Console.PrintError("Rust execution failed:\n" + e.stderr)
            QtGui.QMessageBox.critical(self.form, "Execution Error", f"Rust solver failed: {e.stderr}")

    def accept(self):
        FreeCADGui.Selection.removeObserver(self.observer)
        FreeCADGui.Control.closeDialog()

    def reject(self):
        FreeCADGui.Selection.removeObserver(self.observer)
        FreeCADGui.Control.closeDialog()

# ---------------------------------------------------------------------------
# FreeCAD Command Registration
# ---------------------------------------------------------------------------
class OpenMTBKinematicsCommand:
    def GetResources(self):
        return {
            'Pixmap': '', 
            'MenuText': 'Open MTB Kinematics Mapper',
            'ToolTip': 'Launch interactive picker with line segments and flexible pivots'
        }

    def Activated(self):
        panel = MTBKinematicsTaskPanel()
        FreeCADGui.Control.showDialog(panel)

    def IsActive(self):
        return FreeCAD.ActiveDocument is not None

FreeCADGui.addCommand('MTB_Kinematics_Mapper', OpenMTBKinematicsCommand())
