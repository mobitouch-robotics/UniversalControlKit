# __main__.py
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

# __main__.py
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

import os
import sys
from pathlib import Path

# Load GResource file for local development
use_ui = os.environ.get("UI", "tk")


def _register_gresource():
    """Register compiled GResource if found in package or src."""
    try:
        import gi

        gi.require_version("Gio", "2.0")
        from gi.repository import Gio
    except Exception:
        return

    pkg_dir = Path(__file__).parent
    candidates = [
        pkg_dir / "mobitouchrobots.gresource",
        pkg_dir.parent / "src" / "mobitouchrobots.gresource",
    ]
    for resource_file in candidates:
        if resource_file.exists():
            resource = Gio.Resource.load(str(resource_file))
            resource._register()
            break


def _create_robot_factory():
    """Create a robot factory function based on environment variables."""
    from .robot.robot_go2 import Robot_Go2
    from .robot.robot_dummy import Robot_Dummy

    def factory():
        impl = os.environ.get("ROBOT_IMPL", "Go2").lower()
        if impl == "dummy":
            # Try to use GResources if available, otherwise use bundled files
            return Robot_Dummy(
                resource_path_video="/net/mobitouch/Robots/video.mp4",
                resource_path_robot="/net/mobitouch/Robots/robot_dummy.png",
            )
        ip = os.environ.get("ROBOT_IP", "192.168.1.190")
        conn = os.environ.get("ROBOT_CONN", "LocalSTA").lower()
        try:
            from unitree_webrtc_connect.webrtc_driver import WebRTCConnectionMethod

            conn_map = {
                "localsta": WebRTCConnectionMethod.LocalSTA,
                "localap": WebRTCConnectionMethod.LocalAP,
                "publicnetwork": WebRTCConnectionMethod.PublicNetwork,
            }
            method = conn_map.get(conn, WebRTCConnectionMethod.LocalSTA)
            return Robot_Go2(ip=ip, connection_method=method)
        except Exception:
            return Robot_Go2(ip=ip)

    return factory


if use_ui == "gtk":
    # GTK UI mode
    import gi

    gi.require_version("Gio", "2.0")
    _register_gresource()

    # Initialize WebRTC driver early
    import unitree_webrtc_connect.webrtc_driver  # noqa: F401

    from .ui.gtk import GtkApp

    app = GtkApp(robot_factory=_create_robot_factory())
    sys.exit(app.run())
else:
    # Qt UI mode (default, cross-platform, pure pip install)
    # Initialize WebRTC driver early to avoid asyncio conflicts
    import unitree_webrtc_connect.webrtc_driver  # noqa: F401

    from .ui.qt import QtApp

    # Register resources for Dummy robot if available
    _register_gresource()

    app = QtApp(robot_factory=_create_robot_factory())
    sys.exit(app.run())
