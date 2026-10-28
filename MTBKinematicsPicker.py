import FreeCAD
import FreeCADGui
import json
import os
from PySide import QtCore, QtGui

# ---------------------------------------------------------------------------
# Path Resolution & Bikes Directory Setup
# ---------------------------------------------------------------------------
try:
    import MTB_Design

    _MODULE_PATH = MTB_Design.get_module_path()
except Exception:
    # Fallback if run as standalone macro
    _MODULE_PATH = os.path.dirname(__file__)

BIKES_DIR = os.path.join(_MODULE_PATH, "Bikes")
if not os.path.exists(BIKES_DIR):
    try:
        os.makedirs(BIKES_DIR, exist_ok=True)
    except Exception:
        pass

# ---------------------------------------------------------------------------
# Module-level persistent cache across window open/close sessions
# ---------------------------------------------------------------------------
_SESSION_CACHE = {
    "profile_name": "default_bike",
    "collected_points": {},
    "dynamic_linkages": {},  # linkage_id -> {"name": str, "linkage_vertices": [...], "pivot_vertices": [...]}
}


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
                FreeCAD.Console.PrintWarning(
                    f"Could not resolve coordinates for selection: {sub_name}\n"
                )

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
            ("main_pivot", "Main Pivot (Mandatory)", "point"),
        ]

        # Restore or initialize collected baseline points from session cache
        if not _SESSION_CACHE["collected_points"]:
            _SESSION_CACHE["collected_points"] = {
                slot[0]: None for slot in self.baseline_slots
            }
        self.collected_points = _SESSION_CACHE["collected_points"]

        # Dynamic linkages container from session cache
        self.dynamic_linkages = _SESSION_CACHE["dynamic_linkages"]

        self.ui_elements = {}
        self.dynamic_linkage_layout = None

        title_label = QtGui.QLabel("<b>Mountain Bike Kinematics Geometry Mapper</b>")
        self.layout.addWidget(title_label)

        instructions = QtGui.QLabel(
            "Manage bike profiles, pick baseline geometry, and configure dynamic linkages. Profiles save to the Bikes/ folder."
        )
        instructions.setWordWrap(True)
        self.layout.addWidget(instructions)

        # Scroll area for layout structure
        scroll_area = QtGui.QScrollArea()
        scroll_widget = QtGui.QWidget()
        self.main_grid = QtGui.QVBoxLayout(scroll_widget)

        # ----------------------------------------------------
        # Bike Profile Manager Section (Load & Save)
        # ----------------------------------------------------
        profile_group = QtGui.QGroupBox("Bike Profile Manager")
        profile_layout = QtGui.QVBoxLayout(profile_group)

        load_row = QtGui.QHBoxLayout()
        load_row.addWidget(QtGui.QLabel("Saved Bikes:"))
        self.profile_combo = QtGui.QComboBox()
        self.refresh_profile_list()
        load_row.addWidget(self.profile_combo)

        load_btn = QtGui.QPushButton("Load Profile")
        load_btn.clicked.connect(self.load_selected_profile)
        load_row.addWidget(load_btn)
        profile_layout.addLayout(load_row)

        name_row = QtGui.QHBoxLayout()
        name_row.addWidget(QtGui.QLabel("Profile Filename:"))
        self.profile_name_edit = QtGui.QLineEdit(_SESSION_CACHE["profile_name"])
        name_row.addWidget(self.profile_name_edit)
        profile_layout.addLayout(name_row)

        self.main_grid.addWidget(profile_group)

        # Render Baseline Points
        self.build_slot_section("Base Geometry & Core Pivots", self.baseline_slots)

        # Render Dynamic Linkages Container
        dyn_group = QtGui.QGroupBox("Dynamic Linkages")
        self.dynamic_linkage_layout = QtGui.QVBoxLayout(dyn_group)

        add_linkage_btn = QtGui.QPushButton("+ Add Dynamic Linkage")
        add_linkage_btn.clicked.connect(lambda: self.add_dynamic_linkage_slot())
        self.dynamic_linkage_layout.addWidget(add_linkage_btn)

        # Rebuild UI for any previously cached dynamic linkages
        cached_linkage_keys = list(self.dynamic_linkages.keys())
        for linkage_id in cached_linkage_keys:
            self.add_dynamic_linkage_slot(existing_id=linkage_id)

        self.main_grid.addWidget(dyn_group)
        scroll_widget.setLayout(self.main_grid)
        scroll_area.setWidget(scroll_widget)
        scroll_area.setWidgetResizable(True)
        self.layout.addWidget(scroll_area)

        # Action Buttons
        self.save_btn = QtGui.QPushButton("Save Bike Profile")
        self.save_btn.setStyleSheet(
            "font-weight: bold; background-color: #d0f0c0; padding: 8px;"
        )
        self.save_btn.clicked.connect(self.save_bike_profile)
        self.layout.addWidget(self.save_btn)

        # Active selection state
        self.current_target = None
        self.observer = MTBSelectionObserver(self.on_point_picked)
        FreeCADGui.Selection.addObserver(self.observer)

    def refresh_profile_list(self):
        self.profile_combo.clear()
        if os.path.exists(BIKES_DIR):
            files = [f[:-5] for f in os.listdir(BIKES_DIR) if f.endswith(".json")]
            if files:
                self.profile_combo.addItems(sorted(files))
            else:
                self.profile_combo.addItem("-- No saved bikes --")

    def load_selected_profile(self):
        selected = self.profile_combo.currentText()
        if not selected or selected.startswith("--"):
            return

        json_path = os.path.join(BIKES_DIR, f"{selected}.json")
        if not os.path.exists(json_path):
            QtGui.QMessageBox.warning(
                self.form,
                "File Not Found",
                f"Could not find bike profile file: {json_path}",
            )
            return

        try:
            with open(json_path, "r") as f:
                data = json.load(f)

            # Load profile name and points
            self.profile_name_edit.setText(data.get("profile_name", selected))
            _SESSION_CACHE["profile_name"] = data.get("profile_name", selected)

            loaded_points = data.get("base_points", {})
            for k in self.collected_points:
                pt_val = loaded_points.get(k, None)
                self.collected_points[k] = pt_val
                _SESSION_CACHE["collected_points"][k] = pt_val

                # Update UI label status
                if k in self.ui_elements:
                    status_lbl = self.ui_elements[k]["status"]
                    if pt_val:
                        status_lbl.setText(
                            f"({pt_val['x']:.2f}, {pt_val['y']:.2f}, {pt_val['z']:.2f})"
                        )
                        status_lbl.setStyleSheet("color: green;")
                    else:
                        status_lbl.setText("[ Not Set ]")
                        status_lbl.setStyleSheet("color: red;")

            # Clear existing dynamic linkage UI boxes and reload
            for linkage_id in list(self.dynamic_linkages.keys()):
                box_w = self.dynamic_linkages[linkage_id]["ui"]["group_box"]
                box_w.setParent(None)
                box_w.deleteLater()
            self.dynamic_linkages.clear()

            loaded_linkages = data.get("additional_linkages", {})
            for idx, (link_name, link_content) in enumerate(loaded_linkages.items()):
                new_id = f"linkage_{idx + 1}"
                self.dynamic_linkages[new_id] = {
                    "name": link_name,
                    "linkage_vertices": link_content.get("linkage_vertices", []),
                    "pivot_vertices": link_content.get("pivot_vertices", []),
                }
                self.add_dynamic_linkage_slot(existing_id=new_id)

            FreeCAD.Console.PrintMessage(
                f"Successfully loaded bike profile: {selected}\n"
            )
            QtGui.QMessageBox.information(
                self.form,
                "Load Successful",
                f"Loaded bike profile '{selected}' successfully.",
            )
        except Exception as e:
            FreeCAD.Console.PrintError(f"Failed to load bike profile: {str(e)}\n")
            QtGui.QMessageBox.critical(
                self.form, "Load Error", f"Could not load bike profile: {str(e)}"
            )

    def build_slot_section(self, title, slots):
        group = QtGui.QGroupBox(title)
        grid = QtGui.QGridLayout(group)

        for idx, (key, label_text, slot_type) in enumerate(slots):
            lbl = QtGui.QLabel(label_text)
            status_lbl = QtGui.QLabel("[ Not Set ]")
            status_lbl.setStyleSheet("color: red;")

            # If loaded from cache, reflect current status
            if self.collected_points.get(key) is not None:
                pt = self.collected_points[key]
                status_lbl.setText(f"({pt['x']:.2f}, {pt['y']:.2f}, {pt['z']:.2f})")
                status_lbl.setStyleSheet("color: green;")

            btn = QtGui.QPushButton("Pick")
            btn.clicked.connect(
                lambda checked=False, k=key: self.activate_slot(k, "base")
            )

            reset_btn = QtGui.QPushButton("Reset")
            reset_btn.clicked.connect(
                lambda checked=False, k=key: self.reset_base_slot(k)
            )

            grid.addWidget(lbl, idx, 0)
            grid.addWidget(status_lbl, idx, 1)
            grid.addWidget(btn, idx, 2)
            grid.addWidget(reset_btn, idx, 3)

            self.ui_elements[key] = {
                "status": status_lbl,
                "button": btn,
                "type": slot_type,
            }

        self.main_grid.addWidget(group)

    def reset_base_slot(self, key):
        self.collected_points[key] = None
        _SESSION_CACHE["collected_points"][key] = None
        if key in self.ui_elements:
            self.ui_elements[key]["status"].setText("[ Not Set ]")
            self.ui_elements[key]["status"].setStyleSheet("color: red;")
        FreeCAD.Console.PrintMessage(f"Reset baseline point: {key}\n")

    def add_dynamic_linkage_slot(self, existing_id=None):
        if existing_id is None:
            linkage_id = f"linkage_{len(self.dynamic_linkages) + 1}"
            default_name = f"Linkage {len(self.dynamic_linkages) + 1}"
            self.dynamic_linkages[linkage_id] = {
                "name": default_name,
                "linkage_vertices": [],
                "pivot_vertices": [],
            }
        else:
            linkage_id = existing_id
            default_name = self.dynamic_linkages[linkage_id].get("name", linkage_id)

        link_data = self.dynamic_linkages[linkage_id]

        box = QtGui.QGroupBox(default_name)
        box_layout = QtGui.QVBoxLayout(box)

        # Name & Delete row
        top_row = QtGui.QHBoxLayout()
        name_label = QtGui.QLabel("Name:")
        name_edit = QtGui.QLineEdit(default_name)
        name_edit.textChanged.connect(
            lambda text, k=linkage_id: self.update_linkage_name(k, text)
        )

        del_btn = QtGui.QPushButton("Delete Linkage")
        del_btn.setStyleSheet("color: red;")
        del_btn.clicked.connect(
            lambda checked=False, k=linkage_id, box_w=box: self.remove_dynamic_linkage(
                k, box_w
            )
        )

        top_row.addWidget(name_label)
        top_row.addWidget(name_edit)
        top_row.addWidget(del_btn)
        box_layout.addLayout(top_row)

        # Linkage vertices row
        link_row = QtGui.QHBoxLayout()
        link_lbl = QtGui.QLabel("Geometry Vertices:")
        link_count = len(link_data["linkage_vertices"])
        link_status = QtGui.QLabel(f"[ {link_count} point(s) set ]")
        link_status.setStyleSheet("color: green;" if link_count > 0 else "color: red;")

        link_btn = QtGui.QPushButton("Pick Vertices")
        link_btn.clicked.connect(
            lambda checked=False, k=linkage_id: self.activate_slot(
                None, None, k, "linkage"
            )
        )

        link_reset_btn = QtGui.QPushButton("Reset")
        link_reset_btn.clicked.connect(
            lambda checked=False, k=linkage_id: self.reset_linkage_vertices(
                k, "linkage"
            )
        )

        link_row.addWidget(link_lbl)
        link_row.addWidget(link_status)
        link_row.addWidget(link_btn)
        link_row.addWidget(link_reset_btn)
        box_layout.addLayout(link_row)

        # Pivot vertices row
        pivot_row = QtGui.QHBoxLayout()
        pivot_lbl = QtGui.QLabel("Pivot Points:")
        pivot_count = len(link_data["pivot_vertices"])
        pivot_status = QtGui.QLabel(f"[ {pivot_count} point(s) set ]")
        pivot_status.setStyleSheet(
            "color: green;" if pivot_count > 0 else "color: red;"
        )

        pivot_btn = QtGui.QPushButton("Pick Pivots")
        pivot_btn.clicked.connect(
            lambda checked=False, k=linkage_id: self.activate_slot(
                None, None, k, "pivot"
            )
        )

        pivot_reset_btn = QtGui.QPushButton("Reset")
        pivot_reset_btn.clicked.connect(
            lambda checked=False, k=linkage_id: self.reset_linkage_vertices(k, "pivot")
        )

        pivot_row.addWidget(pivot_lbl)
        pivot_row.addWidget(pivot_status)
        pivot_row.addWidget(pivot_btn)
        pivot_row.addWidget(pivot_reset_btn)
        box_layout.addLayout(pivot_row)

        link_data["ui"] = {
            "group_box": box,
            "name_edit": name_edit,
            "linkage_status": link_status,
            "linkage_btn": link_btn,
            "pivot_status": pivot_status,
            "pivot_btn": pivot_btn,
        }

        # Insert above the add button
        self.dynamic_linkage_layout.insertWidget(
            self.dynamic_linkage_layout.count() - 1, box
        )

    def update_linkage_name(self, linkage_id, text):
        if linkage_id in self.dynamic_linkages:
            self.dynamic_linkages[linkage_id]["name"] = text
            self.dynamic_linkages[linkage_id]["ui"]["group_box"].setTitle(
                text or "Linkage"
            )

    def reset_linkage_vertices(self, linkage_id, sub_type):
        if linkage_id in self.dynamic_linkages:
            self.dynamic_linkages[linkage_id][f"{sub_type}_vertices"] = []
            status_lbl = self.dynamic_linkages[linkage_id]["ui"][f"{sub_type}_status"]
            status_lbl.setText("[ 0 point(s) set ]")
            status_lbl.setStyleSheet("color: red;")
            FreeCAD.Console.PrintMessage(
                f"Reset {sub_type} vertices for {linkage_id}\n"
            )

    def remove_dynamic_linkage(self, linkage_id, box_widget):
        if linkage_id in self.dynamic_linkages:
            del self.dynamic_linkages[linkage_id]
        box_widget.setParent(None)
        box_widget.deleteLater()
        FreeCAD.Console.PrintMessage(f"Removed dynamic linkage: {linkage_id}\n")

    def activate_slot(self, key, slot_type, linkage_id=None, sub_type=None):
        # Reset all button styles across baseline and dynamic linkages
        for el in self.ui_elements.values():
            if "button" in el:
                el["button"].setStyleSheet("")
        for data in self.dynamic_linkages.values():
            ui = data["ui"]
            ui["linkage_btn"].setStyleSheet("")
            ui["pivot_btn"].setStyleSheet("")

        if linkage_id is not None:
            self.current_target = {"linkage_id": linkage_id, "sub_type": sub_type}
            btn = self.dynamic_linkages[linkage_id]["ui"][f"{sub_type}_btn"]
            btn.setStyleSheet("background-color: yellow;")
            FreeCAD.Console.PrintMessage(
                f"Listening for {sub_type} vertices for linkage: {linkage_id} (Click multiple vertices as needed)\n"
            )
        else:
            self.current_target = {"key": key, "sub_type": "base"}
            self.ui_elements[key]["button"].setStyleSheet("background-color: yellow;")
            FreeCAD.Console.PrintMessage(f"Listening for point: {key}\n")

        self.observer.active = True

    def on_point_picked(self, obj_name, sub_name, vector):
        if not self.current_target:
            return

        target = self.current_target
        sub_type = target.get("sub_type")

        if sub_type == "base":
            key = target["key"]
            if key in self.collected_points:
                self.collected_points[key] = {
                    "x": vector.x,
                    "y": vector.y,
                    "z": vector.z,
                }
                _SESSION_CACHE["collected_points"][key] = {
                    "x": vector.x,
                    "y": vector.y,
                    "z": vector.z,
                }

            coord_str = f"({vector.x:.2f}, {vector.y:.2f}, {vector.z:.2f})"
            self.ui_elements[key]["status"].setText(coord_str)
            self.ui_elements[key]["status"].setStyleSheet("color: green;")
            self.ui_elements[key]["button"].setStyleSheet("")

            self.observer.active = False
            self.current_target = None

        elif sub_type in ["linkage", "pivot"]:
            linkage_id = target["linkage_id"]
            link_data = self.dynamic_linkages[linkage_id]

            pt_dict = {"x": vector.x, "y": vector.y, "z": vector.z}
            link_data[f"{sub_type}_vertices"].append(pt_dict)

            count = len(link_data[f"{sub_type}_vertices"])
            status_lbl = link_data["ui"][f"{sub_type}_status"]
            status_lbl.setText(f"[ {count} point(s) set ]")
            status_lbl.setStyleSheet("color: green;")

            FreeCAD.Console.PrintMessage(
                f"Added {sub_type} vertex to {linkage_id}: ({vector.x:.2f}, {vector.y:.2f}, {vector.z:.2f})\n"
            )

    def save_bike_profile(self):
        # Validate mandatory items
        mandatory_keys = ["front_shock_mount", "rear_shock_mount", "main_pivot"]
        missing = [k for k in mandatory_keys if self.collected_points.get(k) is None]

        if missing:
            QtGui.QMessageBox.warning(
                self.form,
                "Mandatory Geometry Missing",
                f"Please ensure mandatory baseline points are set: {', '.join(missing)}",
            )
            return

        # Update profile name cache
        profile_name = self.profile_name_edit.text().strip() or "default_bike"
        _SESSION_CACHE["profile_name"] = profile_name

        # Bundle dynamic linkages
        formatted_linkages = {}
        for k, data in self.dynamic_linkages.items():
            custom_name = data.get("name", k).strip() or k
            formatted_linkages[custom_name] = {
                "linkage_vertices": data["linkage_vertices"],
                "pivot_vertices": data["pivot_vertices"],
            }

        payload = {
            "profile_name": profile_name,
            "base_points": self.collected_points,
            "additional_linkages": formatted_linkages,
            "units": "mm",
        }

        # Save into Bikes/ folder
        if not os.path.exists(BIKES_DIR):
            os.makedirs(BIKES_DIR, exist_ok=True)

        json_path = os.path.join(BIKES_DIR, f"{profile_name}.json")

        try:
            with open(json_path, "w") as f:
                json.dump(payload, f, indent=4)

            self.refresh_profile_list()
            index = self.profile_combo.findText(profile_name)
            if index >= 0:
                self.profile_combo.setCurrentIndex(index)

            FreeCAD.Console.PrintMessage(f"Saved bike profile payload to {json_path}\n")
            QtGui.QMessageBox.information(
                self.form,
                "Save Successful",
                f"Bike profile '{profile_name}' saved successfully to:\n{json_path}",
            )
        except Exception as e:
            FreeCAD.Console.PrintError(f"Failed to save bike profile: {str(e)}\n")
            QtGui.QMessageBox.critical(
                self.form, "Save Error", f"Could not save file: {str(e)}"
            )

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
        icon_path = os.path.join(
            MTB_Design.get_module_path(), "Resources", "icons", "MTB Design Icon.svg"
        )
        return {
            "Pixmap": icon_path,
            "MenuText": "Open MTB Kinematics Mapper",
            "ToolTip": "Launch interactive picker with persistent profiles in Bikes/ folder",
        }

    def Activated(self):
        panel = MTBKinematicsTaskPanel()
        FreeCADGui.Control.showDialog(panel)

    def IsActive(self):
        return FreeCAD.ActiveDocument is not None


FreeCADGui.addCommand("MTB_Kinematics_Mapper", OpenMTBKinematicsCommand())
