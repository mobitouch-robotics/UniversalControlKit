# gtk_app.py
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

import sys
import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
gi.require_version("Gio", "2.0")
from gi.repository import Gtk, Gio, Adw

from .gtk_window import GtkWindow


class GtkApp(Adw.Application):
    """The main GTK application."""

    def __init__(self, robot_factory):
        super().__init__(
            application_id="net.mobitouch.Robots",
            flags=Gio.ApplicationFlags.DEFAULT_FLAGS,
            resource_base_path="/net/mobitouch/Robots",
        )
        self.robot_factory = robot_factory
        self.create_action("quit", lambda *_: self.quit(), ["<primary>q"])
        self.create_action("about", self.on_about_action)
        self.create_action("preferences", self.on_preferences_action)

    def do_activate(self):
        """Called when the application is activated."""
        win = self.props.active_window
        if not win:
            robot = self.robot_factory()
            win = GtkWindow(robot=robot, application=self)
        win.present()

    def on_about_action(self, *args):
        """Callback for the app.about action."""
        about = Adw.AboutDialog(
            application_name="mobitouchrobots",
            application_icon="net.mobitouch.Robots",
            developer_name="Damian Dudycz",
            version="0.1.0",
            developers=["Damian Dudycz"],
            copyright="© 2026 Damian Dudycz",
        )
        about.set_translator_credits(("translator-credits"))
        about.present(self.props.active_window)

    def on_preferences_action(self, widget, _):
        """Callback for the app.preferences action."""
        print("app.preferences action activated")

    def create_action(self, name, callback, shortcuts=None):
        """Add an application action."""
        action = Gio.SimpleAction.new(name, None)
        action.connect("activate", callback)
        self.add_action(action)
        if shortcuts:
            self.set_accels_for_action(f"app.{name}", shortcuts)

    def run(self):
        """Run the GTK application."""
        return super().run(sys.argv)
