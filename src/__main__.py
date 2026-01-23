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
import gi
gi.require_version('Gio', '2.0')
from gi.repository import Gio

resource_file = Path(__file__).parent / 'mobitouchrobots.gresource'
if resource_file.exists():
    resource = Gio.Resource.load(str(resource_file))
    resource._register()

from . import main

VERSION = os.environ.get('VERSION', '0.1.0-dev')
sys.exit(main.main(VERSION))
