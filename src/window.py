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
from gi.repository import Gtk, Adw
from .robot.robot_go2 import Robot_Go2
from .robot.robot_dummy import Robot_Dummy
from .camera_view.camera_view import CameraView
from .movement_controller import MovementController

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")


@Gtk.Template(resource_path="/net/mobitouch/Robots/window.ui")
class MobitouchrobotsWindow(Adw.ApplicationWindow):
    __gtype_name__ = "MobitouchrobotsWindow"

    camera_view: CameraView = Gtk.Template.Child()

    def __init__(self, **kwargs):
        super().__init__(**kwargs)

        # Setup Robot
        self.robot = Robot_Go2(ip="192.168.1.190")
        self.robot.connect()
        self.camera_view.setup(self.robot.get_camera_frame)

        # Setup movement controls
        self.movement_controller = MovementController(self.robot, self)
        self.movement_controller.setup()
