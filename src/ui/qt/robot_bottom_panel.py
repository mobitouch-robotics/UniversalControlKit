from PyQt5.QtWidgets import QWidget, QHBoxLayout, QSizePolicy
from PyQt5.QtCore import Qt


class RobotBottomPanel(QWidget):
    def _update_connect_btn(self):
        from PyQt5.QtWidgets import QGraphicsOpacityEffect

        connecting = getattr(self.robot, "is_connecting", False)
        connected = getattr(self.robot, "is_connected", False)
        self.connect_btn.setDisabled(connecting)
        self.connect_btn.setGraphicsEffect(None)
        if connected:
            self.connect_btn.setText("Disconnect")
            self.connect_btn.setStyleSheet(
                "font-size: 12px; padding: 2px 8px; border-radius: 6px; background: #a33; color: #fff;"
            )
        else:
            self.connect_btn.setText("Connect")
            if connecting:
                self.connect_btn.setStyleSheet(
                    "font-size: 12px; padding: 2px 8px; border-radius: 6px; background: rgba(34, 51, 102, 0.4); color: #fff;"
                )
            else:
                self.connect_btn.setStyleSheet(
                    "font-size: 12px; padding: 2px 8px; border-radius: 6px; background: #223366; color: #fff;"
                )

    def cleanup(self):
        # Disconnect robot status observation if possible
        if hasattr(self.robot, "status_changed"):
            try:
                self.robot.status_changed.disconnect(self._on_robot_status_changed)
            except Exception:
                pass

    def __init__(self, robot, parent=None):
        super().__init__(parent)
        self.robot = robot
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        self.layout = QHBoxLayout()
        self.layout.setContentsMargins(16, 8, 16, 8)
        self.layout.setSpacing(8)
        self.setLayout(self.layout)

        from PyQt5.QtWidgets import QLabel, QSpacerItem
        from .qt_battery_bar import QTBatteryBar

        self.status_label = QLabel()
        self.status_label.setStyleSheet(
            "color: white; font-size: 12px; font-weight: bold; background: transparent;"
        )
        self.layout.addWidget(self.status_label)

        # Battery bar and label (140px width as in selector)
        self.battery_bar = QTBatteryBar(height=5)
        self.battery_bar.setFixedWidth(140)
        self.battery_label = QLabel()
        self.battery_label.setStyleSheet(
            "font-size: 11px; color: #bbb; background: transparent;"
        )
        self.layout.addWidget(self.battery_bar)
        self.layout.addWidget(self.battery_label)
        self.battery_bar.hide()
        self.battery_label.hide()

        # Add expanding spacer at the end to push all widgets to the left
        self.layout.addSpacerItem(
            QSpacerItem(0, 0, QSizePolicy.Expanding, QSizePolicy.Minimum)
        )

        # Add link to robotics.mobitouch.net before Connect button
        from PyQt5.QtWidgets import QLabel, QPushButton
        from PyQt5.QtGui import QCursor
        self.link_label = QLabel('<a href="https://robotics.mobitouch.net" style="text-decoration:none;">robotics.mobitouch.net</a>')
        self.link_label.setStyleSheet("font-size: 12px; color: #4af; background: transparent; text-decoration: none;")
        self.link_label.setOpenExternalLinks(False)
        self.link_label.setCursor(QCursor(Qt.PointingHandCursor))
        self.link_label.linkActivated.connect(self._open_link)
        self.layout.addWidget(self.link_label)

        # Connect/Disconnect button on the right
        self.connect_btn = QPushButton()
        self.connect_btn.setFixedHeight(24)
        self.connect_btn.setFixedWidth(90)
        self.connect_btn.setStyleSheet(
            "font-size: 12px; padding: 2px 8px; border-radius: 6px; background: #222; color: #fff;"
        )
        self.connect_btn.clicked.connect(self._on_connect_btn_clicked)
        self.layout.addWidget(self.connect_btn)

        self._register_robot_observer()
        self._update_status_label()
        self._update_battery()
        self._update_connect_btn()

    def _on_connect_btn_clicked(self):
        connected = getattr(self.robot, "is_connected", False)
        if connected:
            # Try to disconnect
            if hasattr(self.robot, "disconnect") and callable(self.robot.disconnect):
                self.robot.disconnect()
        else:
            # Try to connect
            if hasattr(self.robot, "connect") and callable(self.robot.connect):
                self.robot.connect()

    def _register_robot_observer(self):
        """Register observer for robot status updates (to be implemented)."""
        self.robot.status_changed.connect(self._on_robot_status_changed)

    def _on_robot_status_changed(self):
        self._update_status_label()
        self._update_battery()
        self._update_connect_btn()

    def _update_status_label(self):
        if getattr(self.robot, "is_connecting", False):
            status = "Connecting..."
        elif getattr(self.robot, "is_connected", False):
            status = "Connected"
        else:
            status = "Disconnected"
        self.status_label.setText(status)

    def _update_battery(self):
        connected = getattr(self.robot, "is_connected", False)
        battery = getattr(self.robot, "battery_status", 0)
        self.battery_bar.set_battery(battery, connected)
        if connected:
            self.battery_label.setText(f"{battery}%")
            self.battery_bar.show()
            self.battery_label.show()
        else:
            self.battery_bar.hide()
            self.battery_label.hide()

    def paintEvent(self, event):
        from PyQt5.QtGui import QPainter, QColor

        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        painter.fillRect(self.rect(), QColor(0, 0, 0, 100))
        super().paintEvent(event)

    def _open_link(self, link):
        import webbrowser
        webbrowser.open(link)
