# __main__.py
#
# Copyright (c) 2026 MobiTouch Sp. Z O. O.
#
# Permission is hereby granted, free of charge, to any person obtaining a copy
# of this software and associated documentation files (the "Software"), to deal
# in the Software without restriction, including without limitation the rights
# to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
# copies of the Software, and to permit persons to whom the Software is
# furnished to do so, subject to the following conditions:
#
# The above copyright notice and this permission notice shall be included in all
# copies or substantial portions of the Software.
#
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
# FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
# AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
# LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
# OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
# SOFTWARE.
#
# SPDX-License-Identifier: MIT

import os, sys
import unitree_webrtc_connect.webrtc_driver # Initialize WebRTC driver early # noqa: F401
from .ui.protocols import UIApp

# UI library to use.
ui = os.environ.get("UI", "qt")

app: UIApp = None
if ui == "qt":
    from .ui.qt.qt_app import QtApp
    app = QtApp()

if app is not None:
    sys.exit(app.run())
else:
    print(f"Error: Unknown UI '{ui}'. Supported UI is 'qt'.")
    sys.exit(1)
