import gi

gi.require_version("Gtk", "4.0")
from gi.repository import Gtk, Gdk, GLib
from src.ui.protocols import CameraViewProtocol


class GtkCameraView(CameraViewProtocol):
    def __init__(self, robot):
        self.robot = robot
        self.picture = Gtk.Picture()
        self.picture.set_content_fit(Gtk.ContentFit.COVER)
        self._source_id = 0
        self._latest_frame = None

    def setup(self):
        self._source_id = GLib.timeout_add(50, self._update)

    def cleanup(self):
        if self._source_id > 0:
            GLib.Source.remove(self._source_id)
            self._source_id = 0

    def update_frame(self, frame):
        self._latest_frame = frame
        self._render_frame()

    def _update(self):
        frame = (
            self.robot.get_camera_frame()
            if hasattr(self.robot, "get_camera_frame")
            else None
        )
        if frame is not None:
            self.update_frame(frame)
        return True

    def _render_frame(self):
        if self._latest_frame is None:
            return
        frame = self._latest_frame
        width, height = frame.shape[1], frame.shape[0]
        texture = Gdk.MemoryTexture.new(
            width,
            height,
            Gdk.MemoryFormat.R8G8B8,
            GLib.Bytes.new(frame.tobytes()),
            width * 3,
        )
        self.picture.set_paintable(texture)

    def get_widget(self):
        return self.picture
