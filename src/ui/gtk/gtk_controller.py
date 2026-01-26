import gi

gi.require_version("Gtk", "4.0")
from gi.repository import Gtk, GLib
from src.ui.protocols import MovementControllerProtocol


class GtkMovementController(MovementControllerProtocol):
    def __init__(self, robot, window):
        self.robot = robot
        self.window = window
        self.active_keys = set()
        self.movement_speed = 1.0
        self._timer_id = None

    def setup(self):
        key_controller = Gtk.EventControllerKey()
        key_controller.set_propagation_phase(Gtk.PropagationPhase.CAPTURE)
        key_controller.connect("key-pressed", self._on_key_pressed)
        key_controller.connect("key-released", self._on_key_released)
        self.window.add_controller(key_controller)
        self._timer_id = GLib.timeout_add(100, self._on_move_tick)

    def cleanup(self):
        if self._timer_id:
            GLib.Source.remove(self._timer_id)
            self._timer_id = None

    def _on_key_pressed(self, controller, keyval, keycode, state):
        self.active_keys.add(keyval)
        # Map keys to robot actions
        if keyval == Gtk.Keyval.KEY_Shift_L:
            self.robot.rest()
        elif keyval == Gtk.Keyval.KEY_Tab:
            self.robot.standup()
        elif keyval == Gtk.Keyval.KEY_0:
            self.robot.jump_forward()

    def _on_key_released(self, controller, keyval, keycode, state):
        if keyval in self.active_keys:
            self.active_keys.remove(keyval)

    def _on_move_tick(self):
        # Implement movement logic for active keys
        # ...existing code...
        return True
