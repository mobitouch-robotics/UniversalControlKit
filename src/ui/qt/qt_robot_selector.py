from PyQt5.QtWidgets import (
    QDialog,
    QVBoxLayout,
    QPushButton,
    QLabel,
    QHBoxLayout,
    QSizePolicy,
    QSpacerItem,
)
from PyQt5.QtGui import QFont
from PyQt5.QtCore import Qt


class QtRobotSelector(QDialog):

    def __init__(self, parent=None):
        super().__init__(parent)
        self.selected_robot = None
        self.setWindowTitle("Select Robot")
        self.setModal(True)
        self.resize(500, 350)

        # Main layout with vertical centering
        main_layout = QVBoxLayout()
        main_layout.setContentsMargins(40, 40, 40, 40)
        main_layout.setSpacing(30)

        # Title label
        title = QLabel("Select which robot to use:")
        title.setAlignment(Qt.AlignCenter)
        title.setFont(QFont("Arial", 20, QFont.Bold))
        main_layout.addWidget(title)

        # (Removed fullscreen toggle button)

        # Spacer for vertical centering
        main_layout.addSpacerItem(
            QSpacerItem(20, 40, QSizePolicy.Minimum, QSizePolicy.Expanding)
        )

        # Button row
        btn_row = QHBoxLayout()
        btn_row.setSpacing(40)

        self.go2_btn = QPushButton("Go2 Robot")
        self.go2_btn.setFont(QFont("Arial", 16))
        self.go2_btn.setMinimumHeight(60)
        self.go2_btn.setMinimumWidth(180)
        self.go2_btn.setStyleSheet(
            "QPushButton { background-color: #1976D2; color: white; border-radius: 12px; } QPushButton:hover { background-color: #1565C0; }"
        )
        self.go2_btn.clicked.connect(lambda: self._select("go2"))
        btn_row.addWidget(self.go2_btn)

        self.dummy_btn = QPushButton("Dummy Robot")
        self.dummy_btn.setFont(QFont("Arial", 16))
        self.dummy_btn.setMinimumHeight(60)
        self.dummy_btn.setMinimumWidth(180)
        self.dummy_btn.setStyleSheet(
            "QPushButton { background-color: #388E3C; color: white; border-radius: 12px; } QPushButton:hover { background-color: #2E7D32; }"
        )
        self.dummy_btn.clicked.connect(lambda: self._select("dummy"))
        btn_row.addWidget(self.dummy_btn)

        main_layout.addLayout(btn_row)

        # Spacer for vertical centering
        main_layout.addSpacerItem(
            QSpacerItem(20, 40, QSizePolicy.Minimum, QSizePolicy.Expanding)
        )

        # Exit button to close the application
        exit_btn = QPushButton("Exit")
        exit_btn.setFixedWidth(140)
        # Apply dark styling only when the application/system is using a dark theme.
        try:
            is_dark = False
            # Prefer to query QApplication palette (works when running under Qt)
            try:
                from PyQt5.QtWidgets import QApplication
                from PyQt5.QtGui import QPalette

                app = QApplication.instance()
                if app is not None:
                    try:
                        bg = app.palette().color(QPalette.Window)
                        is_dark = bg.lightness() < 128
                    except Exception:
                        is_dark = False
            except Exception:
                is_dark = False

            # Fallback: on Windows query system preference via registry
            if not is_dark:
                try:
                    import platform

                    if platform.system() == "Windows":
                        import winreg

                        key = winreg.OpenKey(
                            winreg.HKEY_CURRENT_USER,
                            r"Software\Microsoft\Windows\CurrentVersion\Themes\Personalize",
                        )
                        val, _ = winreg.QueryValueEx(key, "AppsUseLightTheme")
                        is_dark = val == 0
                except Exception:
                    pass

            if is_dark:
                exit_btn.setStyleSheet(
                    "QPushButton { background-color: #424242; color: white; border-radius: 10px; padding: 10px; }"
                    "QPushButton:hover { background-color: #3a3a3a; }"
                    "QPushButton:pressed { background-color: #333333; }"
                )
        except Exception:
            # If detection fails, leave the default styling intact.
            pass
        exit_btn.clicked.connect(self._on_exit)
        main_layout.addWidget(exit_btn, alignment=Qt.AlignCenter)

        self.setLayout(main_layout)

    # Fullscreen toggling removed from selector UI

    def _select(self, robot_type):
        self.selected_robot = robot_type
        self.accept()

    def _on_exit(self):
        try:
            from PyQt5.QtWidgets import QApplication

            app = QApplication.instance()
            if app:
                app.quit()
                return
        except Exception:
            pass
        # Fallback: try to close parent window
        try:
            w = self.window()
            if w is not None:
                w.close()
        except Exception:
            pass
