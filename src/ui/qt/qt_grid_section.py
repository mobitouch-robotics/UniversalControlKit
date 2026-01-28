from PyQt5.QtWidgets import QWidget, QGridLayout, QScrollArea
from PyQt5.QtCore import Qt


class QtGridSection(QWidget):
    def showEvent(self, event):
        super().showEvent(event)
        # Force relayout after widget is shown to ensure correct width
        self._last_layout_width = None
        self._update_grid(force=True)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        # Only relayout if width has changed
        if (
            not hasattr(self, "_last_layout_width")
            or self._last_layout_width != self.width()
        ):
            self._last_layout_width = self.width()
            self._update_grid(force=True)

    def __init__(self, parent=None, panel_spacing=16):
        super().__init__(parent)
        self.panel_spacing = panel_spacing
        self._children = []
        self._current_cols = None
        self._max_width = 0
        self._min_next_width = 0
        # Create a QWidget to hold the grid, no layout
        self._container = QWidget(self)
        self._container.setObjectName("qt_grid_section_container")
        self._container.setGeometry(0, 0, self.width(), 100)  # initial height
        self._container.setMinimumWidth(0)
        self._container.setMinimumHeight(0)
        self._container.setMaximumHeight(16777215)
        self._container.setSizePolicy(self.sizePolicy())
        self._container.setVisible(True)

        from PyQt5.QtWidgets import QSizePolicy

        self.setSizePolicy(self.sizePolicy().horizontalPolicy(), QSizePolicy.Preferred)

    def set_children(self, widgets):
        self._children = list(widgets)
        self._update_grid(force=True)

    def add_child(self, widget):
        self._children.append(widget)
        self._update_grid(force=True)

    def remove_child(self, widget):
        if widget in self._children:
            self._children.remove(widget)
            self._update_grid(force=True)

    def _update_grid(self, force=False):
        # Remove all widgets from the container
        for child in self._container.findChildren(
            QWidget, options=Qt.FindDirectChildrenOnly
        ):
            child.setParent(None)
            child.hide()

        available_width = self.width()
        x = 0
        y = 0
        row_height = 0
        widgets_in_row = []
        total_height = 0

        for i, widget in enumerate(self._children):
            widget.setParent(self._container)
            widget.show()
            widget_width = max(
                widget.sizeHint().width(), widget.minimumWidth(), widget.width()
            )
            # Use the actual widget height after showing, or the max of sizeHint, minimumHeight, and height
            widget_height = max(
                widget.sizeHint().height(), widget.minimumHeight(), widget.height()
            )
            # If this widget doesn't fit in the current row, start a new row
            if widgets_in_row and (x + widget_width > available_width):
                # Move to next row
                x = 0
                y += row_height + self.panel_spacing
                total_height = y
                row_height = 0
                widgets_in_row = []
            widget.setGeometry(x, y, widget_width, widget_height)
            widgets_in_row.append(widget)
            x += widget_width + self.panel_spacing
            if widget_height > row_height:
                row_height = widget_height
        # Add the last row's height (no extra spacing after last row)
        if widgets_in_row:
            total_height = y + row_height
        if total_height <= 0:
            total_height = 1
        self._container.setVisible(True)
        self._container.setGeometry(0, 0, self.width(), total_height)
        self.setMinimumHeight(total_height)
        self.setMaximumHeight(total_height)
