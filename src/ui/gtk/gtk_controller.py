# gtk_controller.py
#
# Copyright 2026 Damian Dudycz
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <https://www.gnu.org/licenses/>.
#
# SPDX-License-Identifier: GPL-3.0-or-later

from gi.repository import Gtk, Gdk, GLib
from ..protocols import MovementControllerProtocol

class GtkMovementController(MovementControllerProtocol):
    """Handles keyboard-based robot movement control."""

    def __init__(self, robot, window):
        """
        Initialize the movement controller.

        Args:
            robot: The robot instance to control
            window: The GTK window to attach keyboard controls to
        """
        self.robot = robot
        self.window = window
        self.active_keys = set()
        self._timer_id = None
        self.movement_speed = 0.5  # Movement speed for all axes

    def setup(self):
        """Set up keyboard controls and start the movement loop."""
        # Keyboard Controller for fluid input
        key_controller = Gtk.EventControllerKey()
        key_controller.connect("key-pressed", self._on_key_pressed)
        key_controller.connect("key-released", self._on_key_released)
        self.window.add_controller(key_controller)

        # Start the movement loop at 10 Hz (100ms) - more reasonable for WebRTC
        self._timer_id = GLib.timeout_add(100, self._on_move_tick)

    def cleanup(self):
        """Stop the movement loop and cleanup resources."""
        if self._timer_id:
            GLib.source_remove(self._timer_id)
            self._timer_id = None

    def _on_key_pressed(self, controller, keyval, keycode, state):
        """Track which keys are currently held down."""
        if keyval in [
            Gdk.KEY_Up,
            Gdk.KEY_Down,
            Gdk.KEY_Left,
            Gdk.KEY_Right,
            Gdk.KEY_z,
            Gdk.KEY_x,
            Gdk.KEY_Shift_L,
            Gdk.KEY_Shift_R,
            Gdk.KEY_Tab,
            Gdk.KEY_0,
        ]:
            self.active_keys.add(keyval)
            # Handle rest command on Shift press
            if keyval in [Gdk.KEY_Shift_L, Gdk.KEY_Shift_R]:
                self.robot.rest()
            # Handle standup command on Tab press
            elif keyval == Gdk.KEY_Tab:
                self.robot.standup()
            # Handle jump forward on 0 key press
            elif keyval == Gdk.KEY_0:
                self.robot.jump_forward()
            return True
        return False

    def _on_key_released(self, controller, keyval, keycode, state):
        """Remove keys from tracking when they are released."""
        if keyval in self.active_keys:
            self.active_keys.remove(keyval)

    def _on_move_tick(self):
        """Processes relative movement based on active keys set."""
        x = 0.0  # Forward/backward velocity
        y = 0.0  # Strafe velocity (left/right)
        z = 0.0  # Rotation velocity

        # Forward/backward movement
        if Gdk.KEY_Up in self.active_keys:
            x = self.movement_speed  # Move forward
        if Gdk.KEY_Down in self.active_keys:
            x = -self.movement_speed  # Move backward

        # Strafing left/right
        if Gdk.KEY_z in self.active_keys:
            y = self.movement_speed  # Strafe left
        if Gdk.KEY_x in self.active_keys:
            y = -self.movement_speed  # Strafe right

        # Rotation
        if Gdk.KEY_Left in self.active_keys:
            z = 1.0  # Rotate counter-clockwise at max speed
        if Gdk.KEY_Right in self.active_keys:
            z = -1.0  # Rotate clockwise at max speed

        # Reverse rotation direction when moving backwards
        if x < 0 and z != 0:
            z = -z

        # Send command continuously while keys are pressed
        # This is required because the robot needs continuous commands to maintain movement
        self.robot.move(x, y, z)

        return True  # Return True to keep the GLib timer running
