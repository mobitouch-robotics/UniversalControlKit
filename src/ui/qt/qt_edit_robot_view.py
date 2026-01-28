from PyQt5.QtWidgets import QWidget, QVBoxLayout, QLabel
from PyQt5.QtGui import QPalette, QColor
from .qt_top_panel import QtTopPanel
from src.robot.robot import Robot
from typing import Type
from PyQt5.QtWidgets import QWidget, QFormLayout, QLineEdit, QComboBox
from PyQt5.QtCore import Qt
from .qt_section import QtSection


class EditRobotView(QWidget):

    def __init__(
        self, robot: Robot | Type[Robot], parent=None, back_action=None, qt_app=None
    ):
        super().__init__(parent)
        self.robot = robot
        self.setup_background()

        # Utility to set label font weight
        def set_label_weight(label, required):
            font = label.font()
            font.setBold(bool(required))
            label.setFont(font)

        # Wrap back_action to save repository if editing
        def wrapped_back_action():
            # Only save if editing an existing robot
            if isinstance(self.robot, Robot):
                from src.robot.robot_repository import RobotRepository

                repo = RobotRepository()
                repo.save_to_file(repo._storage_file)
            if back_action:
                back_action()

        layout = QVBoxLayout()
        layout.setContentsMargins(0, 0, 0, 0)
        self.top_panel = QtTopPanel(
            self,
            back_action=wrapped_back_action,
            title=self._get_title(),
            qt_app=qt_app,
        )
        layout.addWidget(self.top_panel)

        # Configuration section
        config_widget = QWidget()
        config_layout = QFormLayout()
        config_layout.setLabelAlignment(Qt.AlignLeft)
        config_layout.setFormAlignment(Qt.AlignLeft | Qt.AlignTop)
        config_layout.setFieldGrowthPolicy(QFormLayout.AllNonFixedFieldsGrow)
        config_widget.setLayout(config_layout)
        config_widget.setMinimumWidth(1)
        config_widget.setSizePolicy(
            config_widget.sizePolicy().horizontalPolicy(),
            config_widget.sizePolicy().verticalPolicy(),
        )

        # Get properties from robot class or instance
        if isinstance(self.robot, type) and issubclass(self.robot, Robot):
            # Create a temporary instance with no values set, use class name as name
            robot_instance = self.robot(id=None, name=self.robot.__name__)
            properties = self.robot.properties()
        elif isinstance(self.robot, Robot):
            robot_instance = self.robot
            properties = self.robot.__class__.properties()
        else:
            robot_instance = None
            properties = {}

        self._properties = properties
        self.config_fields = {}
        self._form_rows = {}
        self._form_row_indices = {}

        def make_update_visibility():
            def update_visibility():
                if not robot_instance:
                    return
                for prop_name in properties:
                    requirement = robot_instance.property_requirement(prop_name)
                    row = self._form_rows.get(prop_name)
                    idx = self._form_row_indices.get(prop_name)
                    if row is not None and idx is not None:
                        visible = requirement is not None
                        # Check if label widget still exists before calling set_label_weight
                        label = row[0]
                        field = row[1]
                        try:
                            if label is not None:
                                set_label_weight(label, requirement is True)
                        except RuntimeError:
                            # Widget was deleted, need to recreate and re-insert
                            from PyQt5.QtWidgets import QLabel, QLineEdit, QComboBox

                            prop_type = properties[prop_name]
                            label = QLabel(prop_name.replace("_", " ").capitalize())
                            set_label_weight(label, requirement is True)

                            # Disconnect old signals if any
                            def disconnect_signals(widget):
                                try:
                                    widget.currentTextChanged.disconnect()
                                except Exception:
                                    pass
                                try:
                                    widget.textChanged.disconnect()
                                except Exception:
                                    pass

                            if isinstance(prop_type, str) and prop_type.startswith(
                                "enum:"
                            ):
                                options = prop_type[5:].split("|")
                                field = QComboBox()
                                field.addItems(options)
                                if robot_instance and hasattr(
                                    robot_instance, prop_name
                                ):
                                    value = getattr(robot_instance, prop_name, None)
                                    if value is not None and value in options:
                                        field.setCurrentText(str(value))
                                disconnect_signals(field)

                                def on_change(val, pn=prop_name):
                                    setattr(robot_instance, pn, val)
                                    update_visibility()

                                field.currentTextChanged.connect(on_change)
                            elif isinstance(prop_type, type) and "Enum" in [
                                base.__name__ for base in prop_type.__mro__
                            ]:
                                options = prop_type.__members__.keys()
                                field = QComboBox()
                                field.addItems(options)
                                if robot_instance and hasattr(
                                    robot_instance, prop_name
                                ):
                                    value = getattr(robot_instance, prop_name, None)
                                    if value is not None and value in options:
                                        field.setCurrentText(str(value))
                                disconnect_signals(field)

                                def on_change(val, pn=prop_name):
                                    setattr(robot_instance, pn, val)
                                    update_visibility()

                                field.currentTextChanged.connect(on_change)
                            else:
                                field = QLineEdit()
                                if robot_instance and hasattr(
                                    robot_instance, prop_name
                                ):
                                    value = getattr(robot_instance, prop_name, None)
                                    if value is not None:
                                        field.setText(str(value))
                                disconnect_signals(field)

                                def on_change(val, pn=prop_name):
                                    setattr(robot_instance, pn, val)
                                    update_visibility()

                                field.textChanged.connect(on_change)
                            self._form_rows[prop_name] = (label, field)
                        # Remove row if not visible, re-insert if visible and not present
                        present = False
                        for i in range(config_layout.rowCount()):
                            if (
                                config_layout.itemAt(i, QFormLayout.LabelRole)
                                and config_layout.itemAt(
                                    i, QFormLayout.LabelRole
                                ).widget()
                                is label
                            ):
                                present = True
                                present_idx = i
                                break
                        if visible and not present:
                            config_layout.insertRow(idx, label, field)
                        elif not visible and present:
                            config_layout.removeRow(present_idx)

            return update_visibility

        update_visibility = make_update_visibility()

        row_idx = 0
        for prop_name, prop_type in properties.items():
            label = QLabel(prop_name.replace("_", " ").capitalize())
            requirement = (
                robot_instance.property_requirement(prop_name)
                if robot_instance
                else None
            )
            set_label_weight(label, requirement is True)
            if isinstance(prop_type, str) and prop_type.startswith("enum:"):
                options = prop_type[5:].split("|")
                combo = QComboBox()
                combo.addItems(options)
                if robot_instance and hasattr(robot_instance, prop_name):
                    value = getattr(robot_instance, prop_name, None)
                    if value is not None and value in options:
                        combo.setCurrentText(str(value))
                config_layout.addRow(label, combo)
                self.config_fields[prop_name] = combo
                self._form_rows[prop_name] = (label, combo)
                self._form_row_indices[prop_name] = row_idx
                row_idx += 1
                if robot_instance:

                    def on_change(val, pn=prop_name):
                        setattr(robot_instance, pn, val)
                        update_visibility()

                    combo.currentTextChanged.connect(on_change)
            elif isinstance(prop_type, type) and "Enum" in [
                base.__name__ for base in prop_type.__mro__
            ]:
                options = prop_type.__members__.keys()
                combo = QComboBox()
                combo.addItems(options)
                if robot_instance and hasattr(robot_instance, prop_name):
                    value = getattr(robot_instance, prop_name, None)
                    if value is not None and value in options:
                        combo.setCurrentText(str(value))
                config_layout.addRow(label, combo)
                self.config_fields[prop_name] = combo
                self._form_rows[prop_name] = (label, combo)
                self._form_row_indices[prop_name] = row_idx
                row_idx += 1
                if robot_instance:

                    def on_change(val, pn=prop_name):
                        setattr(robot_instance, pn, val)
                        update_visibility()

                    combo.currentTextChanged.connect(on_change)
            else:
                line_edit = QLineEdit()
                if robot_instance and hasattr(robot_instance, prop_name):
                    value = getattr(robot_instance, prop_name, None)
                    if value is not None:
                        line_edit.setText(str(value))
                config_layout.addRow(label, line_edit)
                self.config_fields[prop_name] = line_edit
                self._form_rows[prop_name] = (label, line_edit)
                self._form_row_indices[prop_name] = row_idx
                row_idx += 1
                if robot_instance:

                    def on_change(val, pn=prop_name):
                        setattr(robot_instance, pn, val)
                        update_visibility()

                    line_edit.textChanged.connect(on_change)

        # Initial visibility update
        update_visibility()

        config_section = QtSection("Configuration", config_widget)
        config_section.setContentsMargins(16, 0, 16, 0)
        layout.addWidget(config_section)

        # If adding a new robot, show Create button
        if isinstance(self.robot, type) and issubclass(self.robot, Robot):
            from PyQt5.QtWidgets import QPushButton

            create_btn = QPushButton("Create")
            create_btn.setStyleSheet(
                "font-size: 14px; padding: 8px 24px; background: #222; color: white; border-radius: 6px;"
            )
            create_btn.setCursor(Qt.PointingHandCursor)
            from PyQt5.QtWidgets import QHBoxLayout, QWidget as QW

            btn_row = QHBoxLayout()
            btn_row.addStretch(1)
            btn_row.addWidget(create_btn)
            btn_row.addStretch(1)
            btn_row_widget = QW()
            btn_row_widget.setLayout(btn_row)
            layout.addWidget(btn_row_widget)

            def on_create():
                from src.robot.robot_repository import RobotRepository

                repo = RobotRepository()
                # Use the temporary robot_instance with updated fields
                repo.add_robot(robot_instance)
                # Pop to root after creation
                if back_action:
                    back_action(pop_to_root=True)

            create_btn.clicked.connect(on_create)

        layout.addStretch(1)
        self.setLayout(layout)

    def _get_title(self):
        # If robot is a class (type), we're adding a new robot of this class
        if isinstance(self.robot, type) and issubclass(self.robot, Robot):
            return f"Add new {self.robot.__name__}"
        # If robot is an instance, we're editing
        elif isinstance(self.robot, Robot):
            return f"Edit {self.robot.name}"
        else:
            return "Edit robot"

    def setup_background(self):
        palette = self.palette()
        palette.setColor(QPalette.Window, QColor("#303032"))
        self.setAutoFillBackground(True)
        self.setPalette(palette)
