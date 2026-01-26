import gi

gi.require_version("Gtk", "4.0")
from gi.repository import Gtk
from .gtk_camera import GtkCameraView
from .gtk_controller import GtkMovementController


class GtkWindow(Gtk.Box):
    def __init__(self, robot, on_back=None):
        super().__init__(orientation=Gtk.Orientation.VERTICAL, spacing=0)
        self.robot = robot
        self.on_back = on_back
        self.camera_view = GtkCameraView(robot)
        self.camera_view.setup()
        self.movement_controller = GtkMovementController(robot, self)
        self.movement_controller.setup()

        # Top row: Back, Connect, Disconnect buttons
        top_row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=16)

        back_btn = Gtk.Button(label="0 Back to Robot Selection")
        back_btn.set_size_request(220, 40)
        back_btn.connect("clicked", self._on_back)
        top_row.append(back_btn)

        connect_btn = Gtk.Button(label="Connect")
        connect_btn.set_size_request(120, 40)
        connect_btn.connect("clicked", self._on_connect)
        top_row.append(connect_btn)

        disconnect_btn = Gtk.Button(label="Disconnect")
        disconnect_btn.set_size_request(120, 40)
        disconnect_btn.connect("clicked", self._on_disconnect)
        disconnect_btn.set_sensitive(False)
        top_row.append(disconnect_btn)

        top_row.append(Gtk.Box())  # Stretch
        self._connect_btn = connect_btn
        self._disconnect_btn = disconnect_btn

        self.append(top_row)
        self.append(self.camera_view.get_widget())

    def _on_connect(self, btn):
        self._connect_btn.set_sensitive(False)
        self._disconnect_btn.set_sensitive(True)
        import threading

        threading.Thread(target=self.robot.connect, daemon=True).start()

    def _on_disconnect(self, btn):
        self._connect_btn.set_sensitive(True)
        self._disconnect_btn.set_sensitive(False)
        try:
            self.robot.disconnect()
        except Exception as e:
            print(f"[DEBUG] Exception in disconnect: {e}")

    def _on_back(self, btn):
        if self.on_back:
            self.on_back()

    def cleanup(self):
        self.camera_view.cleanup()
        self.movement_controller.cleanup()
