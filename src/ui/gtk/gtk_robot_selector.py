import gi

gi.require_version("Gtk", "4.0")
from gi.repository import Gtk


class GtkRobotSelector(Gtk.Box):
    def __init__(self, on_select=None, on_exit=None):
        super().__init__(orientation=Gtk.Orientation.VERTICAL, spacing=30)
        self.set_margin_top(40)
        self.set_margin_bottom(40)
        self.set_margin_start(40)
        self.set_margin_end(40)
        self.on_select = on_select
        self.on_exit = on_exit

        # Title label
        title = Gtk.Label(label="Select which robot to use:")
        title.set_halign(Gtk.Align.CENTER)
        title.set_valign(Gtk.Align.CENTER)
        title.set_margin_bottom(20)
        title.set_markup(
            "<span size='xx-large' weight='bold'>Select which robot to use:</span>"
        )
        self.append(title)

        # Spacer
        self.append(Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=20))

        # Button row
        btn_row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=40)

        go2_btn = Gtk.Button(label="Go2 Robot")
        go2_btn.set_size_request(180, 60)
        go2_btn.connect("clicked", lambda btn: self._select("go2"))
        btn_row.append(go2_btn)

        dummy_btn = Gtk.Button(label="Dummy Robot")
        dummy_btn.set_size_request(180, 60)
        dummy_btn.connect("clicked", lambda btn: self._select("dummy"))
        btn_row.append(dummy_btn)

        self.append(btn_row)

        # Spacer
        self.append(Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=20))

        # Exit button
        exit_btn = Gtk.Button(label="Exit")
        exit_btn.set_size_request(140, 40)
        exit_btn.connect("clicked", self._on_exit)
        self.append(exit_btn)

    def _select(self, robot_type):
        if self.on_select:
            self.on_select(robot_type)

    def _on_exit(self, btn):
        if self.on_exit:
            self.on_exit()
