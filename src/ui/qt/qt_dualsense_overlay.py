import pathlib
import sys

from PyQt5.QtWidgets import QWidget, QPushButton, QLabel
from PyQt5.QtCore import Qt, QRectF, QByteArray, QPointF
from PyQt5.QtGui import QPainter, QColor, QPixmap, QFont, QPen, QBrush


def _resolve_ui_asset_path(filename: str) -> "str | None":
    """Resolve a path to an asset file in src/ui/, handling PyInstaller bundles."""
    current_ui_dir = pathlib.Path(__file__).resolve().parent.parent
    meipass = getattr(sys, "_MEIPASS", None)
    meipass_ui_dir = pathlib.Path(meipass) / "src" / "ui" if meipass else None
    resources_ui_dir = (
        pathlib.Path(sys.executable).resolve().parent.parent / "Resources" / "src" / "ui"
    )
    candidates = [current_ui_dir / filename]
    if meipass_ui_dir:
        candidates.append(meipass_ui_dir / filename)
    candidates.append(resources_ui_dir / filename)
    for c in candidates:
        if c.exists():
            return str(c)
    return None


def load_svg_as_white_pixmap(svg_path: str, size: int) -> "QPixmap | None":
    """Render an SVG file as a white QPixmap of the given square size."""
    try:
        from PyQt5.QtSvg import QSvgRenderer

        with open(svg_path, "r", encoding="utf-8") as f:
            content = f.read()
        content = content.replace('fill="#000000"', 'fill="white"')
        content = content.replace('fill="#000"', 'fill="white"')
        content = content.replace('fill="black"', 'fill="white"')
        data = QByteArray(content.encode("utf-8"))
        renderer = QSvgRenderer(data)
        pixmap = QPixmap(size, size)
        pixmap.fill(Qt.transparent)
        painter = QPainter(pixmap)
        painter.setRenderHint(QPainter.SmoothPixmapTransform)
        renderer.render(painter, QRectF(0, 0, size, size))
        painter.end()
        return pixmap
    except Exception:
        return None


# ---------------------------------------------------------------------------
# Gamepad profiles
#
# Each profile maps  input_string → (svg_x, svg_y, side, button_display_name)
# where coords are in the SVG viewBox space (0 0 128 128).
#
# _PROFILE_DEFAULT  – DualSense-shaped fallback for unrecognised controllers.
# _PROFILE_MATCH    – maps a lowercase substring of the controller name to a
#                     profile so the right one is chosen automatically at runtime.
# ---------------------------------------------------------------------------

# --- Sony DualSense / DualShock 4 -----------------------------------------
_PROFILE_DUALSENSE: dict = {
    "stick:0":  (45.5,  64.5, "left",  "L Stick"),
    "stick:1":  (82.5,  64.5, "right", "R Stick"),
    "Axis4:+":  (26.0,  34.0, "left",  "L2"),
    "Axis5:+":  (102.0, 34.0, "right", "R2"),
    "Button9":  (25.0,  28.0, "left",  "L1"),
    "Button10": (103.0, 28.0, "right", "R1"),
    "Button0":  (99.0,  56.0, "right", "×"),
    "Button1":  (107.0, 48.0, "right", "○"),
    "Button2":  (91.0,  48.0, "right", "□"),
    "Button3":  (99.0,  40.0, "right", "△"),
    "Button11": (29.0,  40.0, "left",  "↑"),
    "Button12": (29.0,  56.0, "left",  "↓"),
    "Button13": (21.0,  49.0, "left",  "←"),
    "Button14": (37.0,  49.0, "left",  "→"),
    "Button7":  (45.5,  64.5, "left",  "L3"),
    "Button8":  (82.5,  64.5, "right", "R3"),
    "Button6":  (75.0,  46.0, "right", "Options"),
}

# --- ASUS ROG Ally ------------------------------------------------------------
_PROFILE_ROG_ALLY: dict = {
    "stick:0":    (45.5,  64.5, "left",  "L Stick"),
    "stick:1":    (82.5,  64.5, "right", "R Stick"),
    "Axis4:+":    (26.0,  34.0, "left",  "L2"),
    "Axis5:+":    (102.0, 34.0, "right", "R2"),
    "Button4":    (25.0,  28.0, "left",  "L1"),
    "Button5":    (103.0, 28.0, "right", "R1"),
    "Button0":    (99.0,  56.0, "right", "A"),
    "Button1":    (107.0, 48.0, "right", "B"),
    "Button2":    (91.0,  48.0, "right", "X"),
    "Button3":    (99.0,  40.0, "right", "Y"),
    "Hat0:Up":    (29.0,  40.0, "left",  "↑"),
    "Hat0:Down":  (29.0,  56.0, "left",  "↓"),
    "Hat0:Left":  (21.0,  49.0, "left",  "←"),
    "Hat0:Right": (37.0,  49.0, "left",  "→"),
    "Button7":    (45.5,  64.5, "left",  "L3"),
    "Button8":    (82.5,  64.5, "right", "R3"),
    "Button6":    (75.0,  46.0, "right", "Menu"),
}

# Fallback for unrecognised controllers — same geometry as DualSense
_PROFILE_DEFAULT = _PROFILE_DUALSENSE

# Mapping: lowercase substring of controller name → specific profile
_PROFILE_MATCH: dict = {
    "dualsense": _PROFILE_DUALSENSE,
    "dualshock": _PROFILE_DUALSENSE,
    "rog ally":  _PROFILE_ROG_ALLY,
}


def _get_controller_profile(controller_cfg) -> "dict | None":
    """Return the best matching gamepad profile, or None for unrecognised controllers."""
    if controller_cfg is None:
        return None
    name = (getattr(controller_cfg, "name", None) or "").lower()
    for key, profile in _PROFILE_MATCH.items():
        if key in name:
            return profile
    return None


# ---------------------------------------------------------------------------
# Keyboard key-code → display name
#
# Qt stores keys as integers.  Special (non-printable) keys live in the
# 0x01000000+ range; printable keys equal their Unicode code point.
# _KEY_SPECIAL covers the non-printable ones we care about; everything else
# is decoded dynamically by _decode_input_str().
# ---------------------------------------------------------------------------
_KEY_SPECIAL: dict = {
    16777216: "Esc",
    16777217: "Tab",
    16777218: "Backtab",
    16777219: "Backspace",
    16777220: "Enter",
    16777221: "Return",
    16777222: "Insert",
    16777223: "Del",
    16777224: "Pause",
    16777225: "Print",
    16777232: "Home",
    16777233: "End",
    16777234: "←",
    16777235: "↑",
    16777236: "→",
    16777237: "↓",
    16777238: "PgUp",
    16777239: "PgDown",
    16777248: "Shift",
    16777249: "Ctrl",
    16777250: "Meta",
    16777251: "Alt",
    16777252: "CapsLock",
    16777253: "NumLock",
    16777254: "ScrollLock",
    16777264: "F1",  16777265: "F2",  16777266: "F3",  16777267: "F4",
    16777268: "F5",  16777269: "F6",  16777270: "F7",  16777271: "F8",
    16777272: "F9",  16777273: "F10", 16777274: "F11", 16777275: "F12",
}


def _decode_input_str(input_str: str) -> str:
    """Convert an input string like 'Key:65' to a human-readable label."""
    if not input_str.startswith("Key:"):
        return input_str  # e.g. "Button0", "Hat0:Up", "stick:0"
    try:
        code = int(input_str[4:])
    except ValueError:
        return input_str
    # 1. Special-key table
    if code in _KEY_SPECIAL:
        return _KEY_SPECIAL[code]
    # 2. Printable Unicode character (Qt key == code point for these)
    if 0x20 <= code <= 0x10FFFF:
        try:
            ch = chr(code)
            if ch.isprintable():
                return ch.upper() if ch.isalpha() else ch
        except (ValueError, OverflowError):
            pass
    # 3. Last resort: numeric code
    return f"Key {code}"

# ---------------------------------------------------------------------------
# Action display names
# ---------------------------------------------------------------------------
_ACTION_DISPLAY: dict = {
    # Individual directional actions (keyboard)
    "front":                   "Forward",
    "back":                    "Back",
    "side_left":               "Strafe Left",
    "side_right":              "Strafe Right",
    "rotate_left":             "Rotate Left",
    "rotate_right":            "Rotate Right",
    # Gamepad axes
    "movement_axes":           "Move",
    "rotation_axis":           "Rotate",
    "run":                     "Run",
    "slow":                    "Slow",
    "stand_up":                "Stand Up",
    "stand_down":              "Stand Down",
    "stretch":                 "Stretch",
    "sit":                     "Sit",
    "hello":                   "Hello",
    "jump_forward":            "Jump",
    "finger_heart":            "Heart",
    "dance1":                  "Dance",
    "toggle_flash_brightness": "Flash",
    "toggle_led_color":        "LED Color",
    "toggle_lidar":            "Lidar",
}

# ---------------------------------------------------------------------------
# Colours
# ---------------------------------------------------------------------------
_COL_LINE  = QColor(180, 180, 180, 180)   # light gray connector lines
_COL_DOT   = QColor(180, 180, 180, 220)   # light gray anchor dots
_COL_LABEL = QColor(255, 255, 255, 230)
_COL_BG    = QColor(0,   0,   0,   210)


class QtDualSenseOverlay(QWidget):
    """Full-screen overlay with DualSense diagram and controller mapping annotations."""

    _SVG_FILENAME     = "dualsense-svgrepo-com.svg"
    _SVG_DISPLAY_SIZE = 320   # rendered size in px (square)
    _LABEL_FONT_SIZE  = 14
    _LABEL_ROW_H      = 26
    _DOT_RADIUS       = 3.5
    _LINE_WIDTH       = 3.0
    _LABEL_MARGIN     = 55   # px gap between image edge and nearest label char

    def __init__(self, parent: QWidget):
        super().__init__(parent)
        self.setStyleSheet("background: transparent;")
        self._controller_cfg = None
        self._cached_pixmap: "QPixmap | None" = None
        self._setup_ui()
        self._load_svg()
        self.hide()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def set_controller(self, controller_cfg) -> None:
        self._controller_cfg = controller_cfg
        name = ""
        if controller_cfg is not None:
            name = getattr(controller_cfg, "name", None) or ""
            if not name:
                cfg_type_name = getattr(getattr(controller_cfg, "type", None), "name", None)
                if cfg_type_name == "KEYBOARD":
                    name = "Keyboard"
        self.controller_name_label.setText(name)
        self.controller_name_label.setVisible(bool(name))
        self._reposition_children()
        self.update()

    # ------------------------------------------------------------------
    # Setup
    # ------------------------------------------------------------------

    def _setup_ui(self):
        self.controller_name_label = QLabel("", self)
        self.controller_name_label.setAlignment(Qt.AlignCenter)
        self.controller_name_label.setStyleSheet(
            "color: white; background: transparent; font-size: 18px; font-weight: bold;"
        )
        self.controller_name_label.setVisible(False)
        self.controller_name_label.adjustSize()

        self.close_btn = QPushButton("✕", self)
        self.close_btn.setFixedSize(40, 40)
        self.close_btn.setStyleSheet(
            "QPushButton { background: transparent; color: white; font-size: 20px; border: none; }"
            "QPushButton:hover { background: rgba(255,255,255,40); border-radius: 20px; }"
        )
        self.close_btn.setCursor(Qt.PointingHandCursor)
        self.close_btn.clicked.connect(self.hide)

    def _load_svg(self):
        svg_path = _resolve_ui_asset_path(self._SVG_FILENAME)
        if svg_path:
            self._cached_pixmap = load_svg_as_white_pixmap(svg_path, self._SVG_DISPLAY_SIZE)

    # ------------------------------------------------------------------
    # Mode detection
    # ------------------------------------------------------------------

    @staticmethod
    def _uses_list_view(controller_cfg) -> bool:
        """Return True when the plain text-list view should be used instead of SVG annotations."""
        if controller_cfg is None:
            return True
        cfg_type = getattr(controller_cfg, "type", None)
        if cfg_type is not None and getattr(cfg_type, "name", None) == "KEYBOARD":
            return True
        return _get_controller_profile(controller_cfg) is None

    # ------------------------------------------------------------------
    # Annotation helpers (SVG mode)
    # ------------------------------------------------------------------

    def _build_annotations(self) -> list:
        """Return [(svg_x, svg_y, side, action_label, btn_name), ...] for all mapped inputs."""
        if not self._controller_cfg or not self._controller_cfg.mappings:
            return []
        profile = _get_controller_profile(self._controller_cfg) or _PROFILE_DEFAULT
        result = []
        for mapping in self._controller_cfg.mappings:
            action    = mapping.get("action", "")
            input_str = (mapping.get("input") or "").strip()
            action_label = _ACTION_DISPLAY.get(action)
            anchor       = profile.get(input_str)
            if not action_label or not anchor:
                continue
            svg_x, svg_y, side, btn_name = anchor
            result.append((svg_x, svg_y, side, action_label, btn_name))
        return result

    # ------------------------------------------------------------------
    # List-view helpers (keyboard / unsupported gamepad)
    # ------------------------------------------------------------------

    def _build_list_items(self) -> list:
        """Return [(action_label, input_display), ...] for all mapped inputs."""
        if not self._controller_cfg or not self._controller_cfg.mappings:
            return []
        items = []
        for mapping in self._controller_cfg.mappings:
            action    = mapping.get("action", "")
            input_str = (mapping.get("input") or "").strip()
            action_label = _ACTION_DISPLAY.get(action)
            if not action_label:
                continue
            input_display = _decode_input_str(input_str) if input_str else "?"
            items.append((action_label, input_display))
        return items

    @staticmethod
    def _layout_ys(n: int, top_y: float, avail_h: float, row_h: float) -> list:
        if n == 0:
            return []
        step = min(row_h, avail_h / n)
        start = top_y + (avail_h - n * step) / 2 + step / 2
        return [start + i * step for i in range(n)]

    # ------------------------------------------------------------------
    # Painting  (SVG + annotations all drawn in one pass)
    # ------------------------------------------------------------------

    def paintEvent(self, event):
        w, h = self.width(), self.height()
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        painter.setRenderHint(QPainter.TextAntialiasing)

        painter.fillRect(self.rect(), _COL_BG)

        if self._uses_list_view(self._controller_cfg):
            self._paint_list_view(painter, w, h)
        else:
            img_size = self._SVG_DISPLAY_SIZE
            img_x = (w - img_size) // 2
            img_y = (h - img_size) // 2
            if self._cached_pixmap:
                painter.drawPixmap(img_x, img_y, img_size, img_size, self._cached_pixmap)
            self._paint_annotations(painter, img_x, img_y, img_size, w, h)

        super().paintEvent(event)

    def _paint_list_view(self, painter, w, h):
        """Plain text-list view used for keyboard and unsupported gamepads."""
        items = self._build_list_items()
        if not items:
            return

        font = QFont()
        font.setPixelSize(self._LABEL_FONT_SIZE)
        font.setBold(True)
        painter.setFont(font)
        fm = painter.fontMetrics()

        row_h    = self._LABEL_ROW_H + 4
        margin_x = 60
        top_y    = 80   # leave room for the name label child widget

        # Split into two columns if items don't fit in one
        avail_h  = h - top_y - 20
        max_rows = max(1, int(avail_h // row_h))
        if len(items) > max_rows:
            col2_items = items[max_rows:]
            col1_items = items[:max_rows]
        else:
            col1_items = items
            col2_items = []

        col1_x = margin_x
        col2_x = w // 2 + margin_x // 2

        def draw_item(x, y, action_label, input_display):
            label = f"{action_label}  –  {input_display}"
            # Shadow
            painter.setPen(QPen(QColor(0, 0, 0, 160)))
            painter.drawText(x + 1, y + 1, label)
            # Text
            painter.setPen(QPen(_COL_LABEL))
            painter.drawText(x, y, label)

        for i, (a, k) in enumerate(col1_items):
            y = top_y + int(i * row_h) + fm.ascent()
            draw_item(col1_x, y, a, k)

        for i, (a, k) in enumerate(col2_items):
            y = top_y + int(i * row_h) + fm.ascent()
            draw_item(col2_x, y, a, k)

    def _paint_annotations(self, painter, img_x, img_y, img_size, w, h):
        annotations = self._build_annotations()
        if not annotations:
            return

        scale = img_size / 128.0

        # Non-crossing sort rule for L-shaped connectors (horizontal from label → bend → diagonal to anchor).
        #
        # Two diagonals from the same bend_x to anchors at the same ay but different ax WILL cross
        # unless the label-y order matches the distance-from-bend order:
        #   ‣ LEFT side  (bend is LEFT of image, diagonals go RIGHTWARD):
        #       closer-to-bend = smaller ax → assign lower label-y slot → sort sx ASC
        #   ‣ RIGHT side (bend is RIGHT of image, diagonals go LEFTWARD):
        #       closer-to-bend = larger ax  → assign lower label-y slot → sort sx DESC
        #
        # Primary sort by sy ASC guarantees non-crossing for anchors at different y levels.
        # The secondary key handles equal-sy ties correctly per the above rule.
        left_anns  = sorted(
            [(sx, sy, lbl, btn) for sx, sy, side, lbl, btn in annotations if side == "left"],
            key=lambda a: (a[1],  a[0]),  # (sy ASC, sx ASC)  — smaller ax closer to left bend
        )
        right_anns = sorted(
            [(sx, sy, lbl, btn) for sx, sy, side, lbl, btn in annotations if side == "right"],
            key=lambda a: (a[1], -a[0]),  # (sy ASC, sx DESC) — larger ax closer to right bend
        )

        # Use the full overlay height minus a small padding so labels spread widely
        top_margin    = 30
        bottom_margin = 30
        avail_h = max(1, h - top_margin - bottom_margin)

        left_ys  = self._layout_ys(len(left_anns),  top_margin, avail_h, self._LABEL_ROW_H)
        right_ys = self._layout_ys(len(right_anns), top_margin, avail_h, self._LABEL_ROW_H)

        font = QFont()
        font.setPixelSize(self._LABEL_FONT_SIZE)
        font.setBold(True)
        painter.setFont(font)
        fm = painter.fontMetrics()

        def to_px(sx, sy):
            return img_x + sx * scale, img_y + sy * scale

        # The "bend" x is outside the image edge — the elbow of the L-shaped connector.
        # A larger gap pushes the elbow further out, making horizontal segments longer.
        bend_gap   = 30  # px gap between image edge and the bend point
        bend_left  = img_x - bend_gap
        bend_right = img_x + img_size + bend_gap

        label_right_x = img_x - self._LABEL_MARGIN        # right edge of left-side labels
        label_left_x  = img_x + img_size + self._LABEL_MARGIN  # left edge of right-side labels

        for (sx, sy, lbl, btn), ly in zip(left_anns, left_ys):
            ax, ay = to_px(sx, sy)
            self._draw_annotation(
                painter, fm, ax, ay,
                bend_x=bend_left, lx=label_right_x, ly=ly,
                label=f"{lbl} ({btn})", align_right=True,
            )

        for (sx, sy, lbl, btn), ly in zip(right_anns, right_ys):
            ax, ay = to_px(sx, sy)
            self._draw_annotation(
                painter, fm, ax, ay,
                bend_x=bend_right, lx=label_left_x, ly=ly,
                label=f"{lbl} ({btn})", align_right=False,
            )

    def _draw_annotation(self, painter, fm, ax, ay, bend_x, lx, ly, label, align_right):
        """Draw a 2-segment connector (horizontal elbow → diagonal) plus a label."""
        r = self._DOT_RADIUS

        painter.setPen(QPen(_COL_LINE, self._LINE_WIDTH))
        painter.setBrush(Qt.NoBrush)

        # Segment 1: horizontal from label edge to bend point (elbow at image edge)
        painter.drawLine(QPointF(lx, ly), QPointF(bend_x, ly))

        # Segment 2: diagonal from elbow to the button anchor on the gamepad image
        dot_edge_x = ax - r if align_right else ax + r
        painter.drawLine(QPointF(bend_x, ly), QPointF(dot_edge_x, ay))

        # Filled dot at the button anchor
        painter.setPen(Qt.NoPen)
        painter.setBrush(QBrush(_COL_DOT))
        painter.drawEllipse(QPointF(ax, ay), r, r)

        # Label text: "Action (Button)"
        text_w = fm.horizontalAdvance(label)
        asc    = fm.ascent()
        tx = int(lx - text_w) if align_right else int(lx)
        ty = int(ly + asc / 2)

        # Drop shadow
        painter.setPen(QPen(QColor(0, 0, 0, 160)))
        painter.drawText(tx + 1, ty + 1, label)
        # Main text
        painter.setPen(QPen(_COL_LABEL))
        painter.drawText(tx, ty, label)

    # ------------------------------------------------------------------
    # Layout
    # ------------------------------------------------------------------

    def _reposition_children(self):
        w, h = self.width(), self.height()
        self.close_btn.move(w - self.close_btn.width() - 16, 16)
        self.controller_name_label.adjustSize()
        lw = self.controller_name_label.width()
        self.controller_name_label.move((w - lw) // 2, 20)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self._reposition_children()
        self.update()

    def showEvent(self, event):
        super().showEvent(event)
        self._reposition_children()
        self.raise_()
