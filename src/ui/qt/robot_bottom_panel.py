from PyQt5.QtWidgets import QWidget, QHBoxLayout, QSizePolicy, QLabel, QPushButton
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

    def __init__(self, robot, parent=None, show_controller_callback=None):
        super().__init__(parent)
        self.robot = robot
        self._show_controller_callback = show_controller_callback
        self._voice_controller = None
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        self.layout = QHBoxLayout()
        self.layout.setContentsMargins(16, 8, 16, 8)
        self.layout.setSpacing(8)
        self.setLayout(self.layout)

        from PyQt5.QtWidgets import QSpacerItem
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

        # Temperature label
        self.temp_label = QLabel()
        self.temp_label.setStyleSheet("font-size: 11px; color: #bbb; background: transparent;")
        self.layout.addWidget(self.temp_label)
        self.temp_label.hide()

        # Add expanding spacer at the end to push all widgets to the left
        self.layout.addSpacerItem(
            QSpacerItem(0, 0, QSizePolicy.Expanding, QSizePolicy.Minimum)
        )

        # Voice status label (shows recognized text / status)
        self._voice_status_label = QLabel()
        self._voice_status_label.setStyleSheet(
            "color: #8af; font-size: 11px; background: transparent;"
        )
        self._voice_status_label.hide()
        self.layout.addWidget(self._voice_status_label)

        # PTT (push-to-talk) microphone button — hidden until voice controller is set
        self._ptt_btn = QPushButton()
        self._ptt_btn.setFixedSize(28, 28)
        self._ptt_btn.setStyleSheet(
            "QPushButton { background: transparent; border: none; }"
            "QPushButton:hover { background: rgba(255, 255, 255, 30); border-radius: 14px; }"
            "QPushButton:pressed { background: rgba(100, 150, 255, 80); border-radius: 14px; }"
        )
        self._ptt_btn.setToolTip("Push to talk (hold)")
        self._ptt_btn.setCursor(Qt.PointingHandCursor)
        self._ptt_btn.hide()
        # Wire press/release for PTT
        self._ptt_btn.pressed.connect(self._on_ptt_press)
        self._ptt_btn.released.connect(self._on_ptt_release)
        self.layout.addWidget(self._ptt_btn)

        # DualSense controller icon buttons (one per configured joystick controller)
        self._add_controller_icon_buttons()

        # Add link to robotics.mobitouch.net before Connect button
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
            # Stop movement immediately and schedule a delayed stand_down
            try:
                if hasattr(self.robot, "move") and callable(self.robot.move):
                    try:
                        self.robot.move(0, 0, 0)
                    except Exception:
                        pass
            except Exception:
                pass

            # Mark that a stand_down has been scheduled so cleanup doesn't duplicate it
            try:
                self.robot._stand_down_scheduled = True
            except Exception:
                pass

            # Schedule stand_down after 2s (disconnecting -> extra 1s wait)
            try:
                from PyQt5.QtCore import QTimer

                def _do_stand_down():
                    try:
                        if hasattr(self.robot, "stand_down") and callable(self.robot.stand_down):
                            self.robot.stand_down()
                    finally:
                        try:
                            self.robot._stand_down_scheduled = False
                        except Exception:
                            pass

                QTimer.singleShot(2000, _do_stand_down)
            except Exception:
                pass

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
        self._update_temperature()
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

    def _update_temperature(self):
        try:
            t = getattr(self.robot, 'temperature', None)
            if t is None:
                self.temp_label.setText('?°C')
                # show unknown explicitly
                self.temp_label.show()
            else:
                try:
                    self.temp_label.setText(f"{int(t)}°C")
                    self.temp_label.show()
                except Exception:
                    self.temp_label.setText('?°C')
                    self.temp_label.show()
        except Exception:
            try:
                self.temp_label.hide()
            except Exception:
                pass

    def set_voice_controller(self, voice_controller):
        """Connect a voice controller to the PTT button."""
        self._voice_controller = voice_controller
        self._ptt_btn.show()
        self._voice_status_label.show()
        # Set mic icon
        try:
            from .qt_dualsense_overlay import _resolve_ui_asset_path, load_svg_as_white_pixmap
            from PyQt5.QtGui import QIcon
            from PyQt5.QtCore import QSize
            mic_svg = _resolve_ui_asset_path("microphone.svg")
            if mic_svg:
                pixmap = load_svg_as_white_pixmap(mic_svg, 20)
                if pixmap:
                    self._ptt_btn.setIcon(QIcon(pixmap))
                    self._ptt_btn.setIconSize(QSize(20, 20))
        except Exception:
            self._ptt_btn.setText("🎤")

    def set_voice_status(self, text: str):
        """Update the voice status label text."""
        try:
            self._voice_status_label.setText(text)
            self._voice_status_label.show()
        except Exception:
            pass

    def _on_ptt_press(self):
        if self._voice_controller:
            self._voice_controller.start_recording()

    def _on_ptt_release(self):
        if self._voice_controller:
            self._voice_controller.stop_recording()

    def _add_controller_icon_buttons(self):
        """Add one icon button per configured controller (joystick and keyboard)."""
        from PyQt5.QtWidgets import QPushButton
        from PyQt5.QtGui import QIcon
        from PyQt5.QtCore import QSize
        from .qt_dualsense_overlay import _resolve_ui_asset_path, load_svg_as_white_pixmap
        from src.ui.controllers_repository import ControllersRepository

        try:
            repo = ControllersRepository()
            all_cfgs = repo.get_controllers()
        except Exception:
            all_cfgs = []

        gamepad_svg = _resolve_ui_asset_path("gamecontroller-fill-svgrepo-com.svg")
        keyboard_svg = _resolve_ui_asset_path("keyboard-shortcuts-svgrepo-com.svg")
        gamepad_pixmap  = load_svg_as_white_pixmap(gamepad_svg,  22) if gamepad_svg  else None
        keyboard_pixmap = load_svg_as_white_pixmap(keyboard_svg, 22) if keyboard_svg else None

        _btn_style = (
            "QPushButton { background: transparent; border: none; }"
            "QPushButton:hover { background: rgba(255, 255, 255, 30); border-radius: 14px; }"
        )

        self._controller_btns = []
        for cfg in all_cfgs:
            cfg_type_name = getattr(getattr(cfg, "type", None), "name", None)
            if cfg_type_name not in ("JOYSTICK", "KEYBOARD", "VOICE"):
                continue

            if cfg_type_name == "VOICE":
                # Voice controller icon is handled by the PTT button
                continue

            pixmap = keyboard_pixmap if cfg_type_name == "KEYBOARD" else gamepad_pixmap
            tooltip = cfg.name or ("Keyboard" if cfg_type_name == "KEYBOARD" else "Controller")

            btn = QPushButton(self)
            btn.setFixedSize(28, 28)
            btn.setStyleSheet(_btn_style)
            btn.setCursor(Qt.PointingHandCursor)
            btn.setToolTip(tooltip)
            if pixmap:
                btn.setIcon(QIcon(pixmap))
                btn.setIconSize(QSize(22, 22))
            if self._show_controller_callback:
                btn.clicked.connect(lambda _checked, c=cfg: self._show_controller_callback(c))
            self.layout.addWidget(btn)
            self._controller_btns.append(btn)

    def paintEvent(self, event):
        from PyQt5.QtGui import QPainter, QColor

        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        painter.fillRect(self.rect(), QColor(0, 0, 0, 100))
        super().paintEvent(event)

    def _open_link(self, link):
        import webbrowser
        webbrowser.open(link)
