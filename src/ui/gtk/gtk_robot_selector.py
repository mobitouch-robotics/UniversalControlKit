# gtk_robot_selector.py
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
from gi.repository import Gtk, Gdk


from gi.repository import GLib


class GtkRobotSelector(Gtk.Dialog):
    def __init__(self, parent=None):
        super().__init__(title="Select Robot", transient_for=parent)
        self.selected_robot = None
        self.set_modal(True)
        self.set_default_size(500, 350)
        self._response = None

        box = self.get_content_area()
        box.set_spacing(30)
        box.set_margin_top(40)
        box.set_margin_bottom(40)
        box.set_margin_start(40)
        box.set_margin_end(40)

        # Title label
        title = Gtk.Label(label="Select which robot to use:")
        title.set_halign(Gtk.Align.CENTER)
        title.set_valign(Gtk.Align.CENTER)
        title.set_margin_bottom(20)
        title.set_markup(
            "<span size='xx-large' weight='bold'>Select which robot to use:</span>"
        )
        box.append(title)

        # Spacer
        box.append(Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=20))

        # Button row
        btn_row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=40)

        go2_btn = Gtk.Button(label="Go2 Robot")
        go2_btn.set_size_request(180, 60)
        go2_btn.get_style_context().add_class("suggested-action")
        go2_btn.connect("clicked", lambda btn: self._select("go2"))
        btn_row.append(go2_btn)

        dummy_btn = Gtk.Button(label="Dummy Robot")
        dummy_btn.set_size_request(180, 60)
        dummy_btn.get_style_context().add_class("destructive-action")
        dummy_btn.connect("clicked", lambda btn: self._select("dummy"))
        btn_row.append(dummy_btn)

        box.append(btn_row)

        # Spacer
        box.append(Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=20))

        # Exit button
        exit_btn = Gtk.Button(label="Exit")
        exit_btn.set_size_request(140, 40)
        exit_btn.connect("clicked", self._on_exit)
        box.append(exit_btn)

        self.add_button("OK", Gtk.ResponseType.OK)
        self.add_button("Cancel", Gtk.ResponseType.CANCEL)
        self.set_default_response(Gtk.ResponseType.OK)
        self.connect("response", self._on_response)

    def run_modal(self):
        self.present()
        loop = GLib.MainLoop()
        self._loop = loop
        loop.run()
        return self._response

    def _on_response(self, dialog, response_id):
        self._response = response_id
        if hasattr(self, "_loop") and self._loop.is_running():
            self._loop.quit()

    def _select(self, robot_type):
        self.selected_robot = robot_type
        self.response(Gtk.ResponseType.OK)

    def _on_exit(self, btn):
        self.response(Gtk.ResponseType.CANCEL)
        self.close()
