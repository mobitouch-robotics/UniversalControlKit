import sys
import gi

gi.require_version("Gtk", "4.0")
from gi.repository import Gtk, Gdk

from .gtk_robot_selector import GtkRobotSelector
from .gtk_window import GtkWindow
from src.robot.robot_go2 import Robot_Go2
from src.robot.robot_dummy import Robot_Dummy


class GtkApp:
    def __init__(self):
        self.window = Gtk.Window(title="MobiTouchRobots")
        self.window.set_default_size(800, 600)
        self.window.connect("destroy", self._on_destroy)
        key_controller = Gtk.EventControllerKey()
        key_controller.connect("key-pressed", self._on_key_press)
        self.window.add_controller(key_controller)
        self.selected_robot_type = None
        self.robot = None
        self._mainloop = None
        self._is_fullscreen = False

    def show_selector(self):
        self.window.present()
        selector = GtkRobotSelector(
            on_select=self._on_selector_select, on_exit=self._on_selector_exit
        )
        self.window.set_child(selector)
        self._enter_fullscreen()

    def _on_key_press(self, controller, keyval, keycode, state):
        from gi.repository import Gdk

        if keyval == Gdk.KEY_F11:
            if self._is_fullscreen:
                self._exit_fullscreen()
            else:
                self._enter_fullscreen()
            return True
        if keyval == Gdk.KEY_Escape and self._is_fullscreen:
            self._exit_fullscreen()
            return True
        return False

    def _enter_fullscreen(self):
        if not self._is_fullscreen:
            self.window.fullscreen()
            self._is_fullscreen = True

    def _exit_fullscreen(self):
        if self._is_fullscreen:
            self.window.unfullscreen()
            self._is_fullscreen = False

    def _on_selector_select(self, robot_type):
        self.selected_robot_type = robot_type
        self.show_robot_view()

    def _on_selector_exit(self):
        self._mainloop.quit()

    def show_robot_view(self):
        import logging

        logging.basicConfig(level=logging.DEBUG, format="[%(levelname)s] %(message)s")
        logging.debug(f"Selected robot type: {self.selected_robot_type}")
        try:
            if self.selected_robot_type == "go2":
                logging.debug("Creating Go2 robot...")
                self.robot = Robot_Go2(ip=None)
            elif self.selected_robot_type == "dummy":
                logging.debug("Creating Dummy robot...")
                self.robot = Robot_Dummy()
            else:
                logging.error(f"Unknown robot type: {self.selected_robot_type}")
                raise RuntimeError(f"Unknown robot type: {self.selected_robot_type}")
            logging.debug("Creating GtkWindow content...")
            robot_view = GtkWindow(self.robot, on_back=self.show_selector)
            self.window.set_child(robot_view)
        except Exception as e:
            logging.error(f"Exception during robot/window creation: {e}")
            self._mainloop.quit()

    def _on_destroy(self, *a):
        if self._mainloop:
            self._mainloop.quit()

    def run(self):
        from gi.repository import GLib

        self._mainloop = GLib.MainLoop()
        self.show_selector()
        self._mainloop.run()
