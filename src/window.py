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
import cv2, numpy, asyncio, threading, time
from gi.repository import Gtk, Gdk, GLib, Adw
from queue import Queue
from unitree_webrtc_connect.webrtc_driver import UnitreeWebRTCConnection, WebRTCConnectionMethod
from aiortc import MediaStreamTrack
from .robot_go2 import Robot_Go2

@Gtk.Template(resource_path='/net/mobitouch/Robots/window.ui')
class MobitouchrobotsWindow(Adw.ApplicationWindow):
    __gtype_name__ = 'MobitouchrobotsWindow'

    camera_image = Gtk.Template.Child()

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.robot = Robot_Go2(ip="192.168.1.190")
        self.robot.connect()
        GLib.timeout_add(33, self._update_ui)

    def _update_ui(self):
        frame = self.robot.get_camera_frame()
        if frame is not None:
            # GTK rendering from the robot's latest frame
            h, w, _ = frame.shape
            texture = Gdk.MemoryTexture.new(
                w, h,
                Gdk.MemoryFormat.R8G8B8,
                GLib.Bytes.new(frame.tobytes()),
                w * 3
            )
            self.camera_image.set_paintable(texture)
        return True

