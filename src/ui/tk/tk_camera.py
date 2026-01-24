from __future__ import annotations

try:
    import tkinter as tk
    from PIL import Image, ImageTk
except Exception:
    tk = None
    Image = None
    ImageTk = None

from ..protocols import CameraViewProtocol


class TkCameraView(CameraViewProtocol):
    def __init__(self, robot, root: tk.Tk):
        self.robot = robot
        self.root = root
        self.label = tk.Label(root, text="Connecting camera...") if tk else None
        if self.label:
            self.label.pack(fill=tk.BOTH, expand=True)
            # Prevent label from requesting size changes
            self.label.pack_propagate(False)
        self._timer_ms = 50
        self._frames = 0
        self._latest_frame = None

    def setup(self) -> None:
        if tk and self.label:
            self.root.after(self._timer_ms, self._update)

    def cleanup(self) -> None:
        pass

    def update_frame(self, frame) -> None:
        if not tk or not self.label:
            return
        if frame is None:
            try:
                self.label.configure(text="No camera frames yet...")
            except Exception:
                pass
            return
        # Fallback: if Pillow is unavailable, just show a text indicator
        if Image is None or ImageTk is None:
            try:
                self.label.configure(text="Camera active (Pillow not installed)")
            except Exception:
                pass
            return

        self._latest_frame = frame
        self._render_frame()

    def _render_frame(self):
        """Render the latest frame scaled to window size with AspectFill."""
        if not tk or not self.label or self._latest_frame is None:
            return
        if Image is None or ImageTk is None:
            return

        try:
            # Get current window dimensions
            label_width = self.label.winfo_width()
            label_height = self.label.winfo_height()

            # Skip if window not yet sized
            if label_width <= 1 or label_height <= 1:
                return

            # Create PIL image from frame
            img = Image.fromarray(self._latest_frame)
            img_width, img_height = img.size

            # Calculate AspectFill scaling (crop to fill while maintaining aspect)
            scale_w = label_width / img_width
            scale_h = label_height / img_height
            scale = max(scale_w, scale_h)  # Use larger scale to fill

            new_width = int(img_width * scale)
            new_height = int(img_height * scale)

            # Resize image
            img_resized = img.resize((new_width, new_height), Image.Resampling.LANCZOS)

            # Crop to exact label size (center crop)
            left = (new_width - label_width) // 2
            top = (new_height - label_height) // 2
            img_cropped = img_resized.crop(
                (left, top, left + label_width, top + label_height)
            )

            # Convert to PhotoImage and display
            photo = ImageTk.PhotoImage(img_cropped)
            self.label.configure(image=photo, text="")
            self.label.image = photo
            self._frames += 1
        except Exception:
            # If conversion fails, ignore to keep UI responsive
            pass

    def _update(self):
        frame = None
        try:
            frame = self.robot.get_camera_frame()
        except Exception:
            frame = None
        self.update_frame(frame)
        # Re-render on window resize
        if self._latest_frame is not None:
            self._render_frame()
        if tk:
            self.root.after(self._timer_ms, self._update)
