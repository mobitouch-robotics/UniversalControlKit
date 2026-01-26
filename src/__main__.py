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
import unitree_webrtc_connect.webrtc_driver # Initialize WebRTC driver early # noqa: F401

# Load GResource file for local development
use_ui = os.environ.get("UI", "qt")

# GResource registration for local GTK build.
if use_ui == "gtk" and not os.environ.get("FLATPAK_ID"):
    """Register compiled GResource if found in package or src."""
    from gi.repository import Gio

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

if use_ui == "gtk":
    from .ui.gtk import GtkApp
    app = GtkApp()
elif use_ui == "qt":
    from .ui.qt import QtApp
    app = QtApp()
else:
    print(f"Unknown UI type: {use_ui}", file=sys.stderr)
    sys.exit(1)

sys.exit(app.run())
