# window.py
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

import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")

from gi.repository import Gtk, Gdk, GLib, Adw
from .robot.robot_go2 import Robot_Go2

# from .robot.robot_dummy import Robot_Dummy
from .camera_view.camera_view import CameraView


@Gtk.Template(resource_path="/net/mobitouch/Robots/window.ui")
class MobitouchrobotsWindow(Adw.ApplicationWindow):
    __gtype_name__ = "MobitouchrobotsWindow"

    camera_view: CameraView = Gtk.Template.Child()

    def __init__(self, **kwargs):
        super().__init__(**kwargs)

        # Setup Robot Go2s
        self.robot = Robot_Go2(ip="192.168.1.190")
        self.robot.connect()
        self.camera_view.setup(self.robot.get_camera_frame)

        self._setup_movement()

    def _setup_movement(self):
        def _on_key_pressed(controller, keyval, keycode, state):
            """Track which arrow keys are currently held down."""
            if keyval in [Gdk.KEY_Up, Gdk.KEY_Down, Gdk.KEY_Left, Gdk.KEY_Right]:
                self.active_keys.add(keyval)
                return True
            return False

        def _on_key_released(controller, keyval, keycode, state):
            """Remove keys from tracking when they are released."""
            if keyval in self.active_keys:
                self.active_keys.remove(keyval)

        def _on_move_tick():
            """Processes relative movement based on active keys set."""
            if not self.active_keys:
                return True  # Continue timer even when idle

            dy = 0
            rotation_delta = 0

            # Movement logic
            if Gdk.KEY_Up in self.active_keys:
                dy -= 3
            if Gdk.KEY_Down in self.active_keys:
                dy += 3

            # Rotation logic (Degrees)
            if Gdk.KEY_Left in self.active_keys:
                rotation_delta -= 3  # Rotate counter-clockwise
            if Gdk.KEY_Right in self.active_keys:
                rotation_delta += 3  # Rotate clockwise

            # Apply rotation first so movement follows the new heading
            if rotation_delta != 0:
                self.robot.rotate(rotation_delta)

            # Apply movement (dx is 0 because we are moving forward/backward relative to heading)
            if dy != 0:
                self.robot.move(0, dy)

            return True  # Return True to keep the GLib timer running

        # Initialize movement state
        self.active_keys = set()
        # Keyboard Controller for fluid input
        key_controller = Gtk.EventControllerKey()
        key_controller.connect("key-pressed", _on_key_pressed)
        key_controller.connect("key-released", _on_key_released)
        self.add_controller(key_controller)
        # Start the movement loop (approx 60 FPS)
        GLib.timeout_add(16, _on_move_tick)
