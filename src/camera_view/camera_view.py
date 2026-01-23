from gi.repository import Gtk, Gdk, GLib


class CameraView(Gtk.Picture):
    __gtype_name__ = "CameraView"

    def __init__(self):
        super().__init__()
        self.get_camera_frame = None
        self._source_id = 0

        self.connect("realize", self._on_realize)
        self.connect("unrealize", self._on_unrealize)

    def setup(self, get_camera_frame_function):
        self.get_camera_frame = get_camera_frame_function

    def _on_realize(self, widget):
        if self._source_id == 0:
            self._source_id = GLib.timeout_add(33, self._update_frame)

    def _on_unrealize(self, widget):
        if self._source_id > 0:
            GLib.Source.remove(self._source_id)
            self._source_id = 0

    def _update_frame(self):
        if self.get_camera_frame:
            frame = self.get_camera_frame()
            if frame is not None:
                # Convert the frame to GTK-compatible texture
                width, height = frame.shape[1], frame.shape[0]
                texture = Gdk.MemoryTexture.new(
                    width,
                    height,
                    Gdk.MemoryFormat.R8G8B8,
                    GLib.Bytes.new(frame.tobytes()),
                    width * 3,
                )
                self.set_paintable(texture)
            return True
        self._source_id = 0
        return False
