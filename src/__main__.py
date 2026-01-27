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

import os, sys
import unitree_webrtc_connect.webrtc_driver # Initialize WebRTC driver early # noqa: F401
from .ui.protocols import UIApp

# UI library to use.
ui = os.environ.get("UI", "qt")

app: UIApp = None
if ui == "qt":
    from .ui.qt.qt_app import QtApp
    app = QtApp()
elif ui == "gtk":
    from .ui.gtk.gtk_app import GtkApp
    app = GtkApp()

if app is not None:
    sys.exit(app.run())
else:
    print(f"Error: Unknown UI '{ui}'. Supported UIs are 'qt' and 'gtk'.")
    sys.exit(1)
