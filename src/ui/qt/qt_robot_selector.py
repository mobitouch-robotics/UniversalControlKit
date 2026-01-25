from PyQt5.QtWidgets import QDialog, QVBoxLayout, QPushButton, QLabel, QHBoxLayout, QSizePolicy, QSpacerItem
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

        # Spacer for vertical centering
        main_layout.addSpacerItem(QSpacerItem(20, 40, QSizePolicy.Minimum, QSizePolicy.Expanding))

        # Button row
        btn_row = QHBoxLayout()
        btn_row.setSpacing(40)

        self.go2_btn = QPushButton("Go2 Robot")
        self.go2_btn.setFont(QFont("Arial", 16))
        self.go2_btn.setMinimumHeight(60)
        self.go2_btn.setMinimumWidth(180)
        self.go2_btn.setStyleSheet("QPushButton { background-color: #1976D2; color: white; border-radius: 12px; } QPushButton:hover { background-color: #1565C0; }")
        # Optionally set an icon if available
        # self.go2_btn.setIcon(QIcon('path/to/go2_icon.png'))
        self.go2_btn.clicked.connect(lambda: self._select("go2"))
        btn_row.addWidget(self.go2_btn)

        self.dummy_btn = QPushButton("Dummy Robot")
        self.dummy_btn.setFont(QFont("Arial", 16))
        self.dummy_btn.setMinimumHeight(60)
        self.dummy_btn.setMinimumWidth(180)
        self.dummy_btn.setStyleSheet("QPushButton { background-color: #388E3C; color: white; border-radius: 12px; } QPushButton:hover { background-color: #2E7D32; }")
        # Optionally set an icon if available
        # self.dummy_btn.setIcon(QIcon('path/to/dummy_icon.png'))
        self.dummy_btn.clicked.connect(lambda: self._select("dummy"))
        btn_row.addWidget(self.dummy_btn)

        main_layout.addLayout(btn_row)

        # Spacer for vertical centering
        main_layout.addSpacerItem(QSpacerItem(20, 40, QSizePolicy.Minimum, QSizePolicy.Expanding))

        self.setLayout(main_layout)

    def _select(self, robot_type):
        self.selected_robot = robot_type
        self.accept()
