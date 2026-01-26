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
from .gtk_robot_selector import GtkRobotSelector


def _apply_windows_dark_titlebar(win, enable: bool = True):
    try:
        import platform

        if platform.system() != "Windows":
            return
        import ctypes
        from ctypes import wintypes

        DWMWA_USE_IMMERSIVE_DARK_MODE = 20
        DWMWA_USE_IMMERSIVE_DARK_MODE_BEFORE_20 = 19

        hwnd = int(win.get_window().get_handle()) if win.get_window() else None
        if hwnd is None:
            return
        dwmapi = ctypes.windll.dwmapi
        val = ctypes.c_int(1 if enable else 0)
        res = dwmapi.DwmSetWindowAttribute(
            wintypes.HWND(hwnd),
            ctypes.c_int(DWMWA_USE_IMMERSIVE_DARK_MODE),
            ctypes.byref(val),
            ctypes.sizeof(val),
        )
        if res != 0:
            try:
                dwmapi.DwmSetWindowAttribute(
                    wintypes.HWND(hwnd),
                    ctypes.c_int(DWMWA_USE_IMMERSIVE_DARK_MODE_BEFORE_20),
                    ctypes.byref(val),
                    ctypes.sizeof(val),
                )
            except Exception:
                pass
    except Exception:
        pass


def _try_enable_windows_uxtheme_dark(hwnd: int | None = None):
    try:
        import platform

        if platform.system() != "Windows":
            return
        import ctypes
        from ctypes import wintypes

        uxtheme = ctypes.WinDLL("uxtheme")
        try:
            SetPreferredAppMode = uxtheme.SetPreferredAppMode
            SetPreferredAppMode.argtypes = [ctypes.c_int]
            SetPreferredAppMode.restype = ctypes.c_int
            try:
                SetPreferredAppMode(1)
            except Exception:
                pass
        except Exception:
            pass

        try:
            AllowDarkModeForApp = uxtheme.AllowDarkModeForApp
            AllowDarkModeForApp.argtypes = [wintypes.BOOL]
            AllowDarkModeForApp.restype = wintypes.BOOL
            try:
                AllowDarkModeForApp(True)
            except Exception:
                pass
        except Exception:
            pass

        if hwnd is not None:
            try:
                AllowDarkModeForWindow = uxtheme.AllowDarkModeForWindow
                AllowDarkModeForWindow.argtypes = [wintypes.HWND, wintypes.BOOL]
                AllowDarkModeForWindow.restype = wintypes.BOOL
                try:
                    AllowDarkModeForWindow(wintypes.HWND(int(hwnd)), True)
                except Exception:
                    pass
            except Exception:
                pass
    except Exception:
        pass


class GtkApp(Adw.Application):
    """The main GTK application."""

    def __init__(self):
        super().__init__(
            application_id="net.mobitouch.Robots",
            flags=Gio.ApplicationFlags.DEFAULT_FLAGS,
            resource_base_path="/net/mobitouch/Robots",
        )
        self.create_action("quit", lambda *_: self.quit(), ["<primary>q"])
        self.create_action("about", self.on_about_action)
        self.create_action("preferences", self.on_preferences_action)
        # Detect Windows dark preference and configure GTK/Win32 best-effort
        self._is_dark = False
        try:
            import platform

            if platform.system() == "Windows":
                try:
                    import winreg

                    key = winreg.OpenKey(
                        winreg.HKEY_CURRENT_USER,
                        r"Software\Microsoft\Windows\CurrentVersion\Themes\Personalize",
                    )
                    val, _ = winreg.QueryValueEx(key, "AppsUseLightTheme")
                    self._is_dark = val == 0
                except Exception:
                    self._is_dark = False
                if self._is_dark:
                    try:
                        settings = Gtk.Settings.get_default()
                        settings.set_property("gtk-application-prefer-dark-theme", True)
                    except Exception:
                        pass
        except Exception:
            self._is_dark = False

    def do_activate(self):
        """Called when the application is activated."""
        win = self.props.active_window
        if not win:
            # Show selector dialog first (GTK implementation)
            try:
                from src.robot.robot_go2 import Robot_Go2
                from src.robot.robot_dummy import Robot_Dummy
            except Exception:
                Robot_Go2 = None
                Robot_Dummy = None

            try:
                selector = GtkRobotSelector(parent=None)
                response = selector.run()
                chosen = selector.selected_robot
                selector.destroy()
            except Exception:
                response = Gtk.ResponseType.CANCEL
                chosen = None

            if response == Gtk.ResponseType.OK and chosen:
                if chosen == "go2" and Robot_Go2 is not None:
                    robot = Robot_Go2(ip=None)
                elif chosen == "dummy" and Robot_Dummy is not None:
                    robot = Robot_Dummy()
                else:
                    # Fallback: try to create dummy
                    try:
                        robot = Robot_Dummy()
                    except Exception:
                        robot = None
                if robot is None:
                    return
                win = GtkWindow(robot=robot, application=self)
                # Best-effort: request dark caption on Win32 if applicable
                try:
                    if getattr(self, "_is_dark", False):
                        try:
                            _try_enable_windows_uxtheme_dark(None)
                        except Exception:
                            pass
                        try:
                            _apply_windows_dark_titlebar(win, True)
                        except Exception:
                            pass
                except Exception:
                    pass
            else:
                # User cancelled selector; quit app
                self.quit()
                return
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
