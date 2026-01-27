from PyQt5.QtWidgets import QWidget, QVBoxLayout
from PyQt5.QtGui import QPalette, QColor
from .qt_top_panel import QtTopPanel
from src.robot.robot import Robot
from typing import Type
from PyQt5.QtWidgets import QWidget, QFormLayout, QLineEdit, QComboBox
from PyQt5.QtCore import Qt
from .qt_section import QtSection


class EditRobotView(QWidget):
    def property_requirement(self, name):
        """
        Returns:
            None: if property should not be displayed at all
            True: if property is required
            False: if property is optional
        """
        # Example logic: you can customize this per robot type or property
        # For now, assume all properties in self._properties are required unless marked as optional
        # If you want to hide a property, return None
        # If you want to mark as optional, return False
        # If required, return True
        prop = self._properties.get(name)
        if prop is None:
            return None
        # If property has 'optional' in its metadata, treat as optional
        if isinstance(prop, dict) and prop.get("optional", False):
            return False
        return True

    def __init__(
        self, robot: Robot | Type[Robot], parent=None, back_action=None, qt_app=None
    ):
        super().__init__(parent)
        self.robot = robot
        self.setup_background()

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
            # Create a temporary instance with no values set
            robot_instance = self.robot(id=None, name=None)
            properties = self.robot.properties()
        elif isinstance(self.robot, Robot):
            robot_instance = self.robot
            properties = self.robot.__class__.properties()
        else:
            robot_instance = None
            properties = {}

        self._properties = properties
        self.config_fields = {}
        for prop_name, prop_type in properties.items():
            requirement = (
                robot_instance.property_requirement(prop_name)
                if robot_instance
                else None
            )
            if requirement is None:
                continue  # Hide this property from the view
            if isinstance(prop_type, str) and prop_type.startswith("enum:"):
                options = prop_type[5:].split("|")
                combo = QComboBox()
                combo.addItems(options)
                # Load initial value from instance if available
                if robot_instance and hasattr(robot_instance, prop_name):
                    value = getattr(robot_instance, prop_name, None)
                    if value is not None and value in options:
                        combo.setCurrentText(str(value))
                config_layout.addRow(prop_name.replace("_", " ").capitalize(), combo)
                self.config_fields[prop_name] = combo
                # Update instance value on change
                if robot_instance:
                    combo.currentTextChanged.connect(
                        lambda val, pn=prop_name: setattr(robot_instance, pn, val)
                    )
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
                config_layout.addRow(prop_name.replace("_", " ").capitalize(), combo)
                self.config_fields[prop_name] = combo
                if robot_instance:
                    combo.currentTextChanged.connect(
                        lambda val, pn=prop_name: setattr(robot_instance, pn, val)
                    )
            else:
                line_edit = QLineEdit()
                if robot_instance and hasattr(robot_instance, prop_name):
                    value = getattr(robot_instance, prop_name, None)
                    if value is not None:
                        line_edit.setText(str(value))
                config_layout.addRow(
                    prop_name.replace("_", " ").capitalize(), line_edit
                )
                self.config_fields[prop_name] = line_edit
                if robot_instance:
                    line_edit.textChanged.connect(
                        lambda val, pn=prop_name: setattr(robot_instance, pn, val)
                    )

        config_section = QtSection("Configuration", config_widget)
        config_section.setContentsMargins(16, 0, 16, 0)
        layout.addWidget(config_section)

        # If adding a new robot, show Create button
        if isinstance(self.robot, type) and issubclass(self.robot, Robot):
            from PyQt5.QtWidgets import QPushButton

            create_btn = QPushButton("Create")
            create_btn.setStyleSheet(
                "font-size: 14px; padding: 8px 24px; background: #4caf50; color: white; border-radius: 6px;"
            )
            create_btn.setCursor(Qt.PointingHandCursor)
            layout.addWidget(create_btn, alignment=Qt.AlignRight)

            def on_create():
                from src.robot.robot_repository import RobotRepository

                repo = RobotRepository()
                # Use the temporary robot_instance with updated fields
                repo.add_robot(robot_instance)
                # Pop to root after creation
                if back_action:
                    back_action()

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
