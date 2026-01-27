# Register GResources for Gio. Only do this outside of Flatpak,
# as inside Flatpak the resources are already bundled.
if not os.environ.get("FLATPAK_ID"):
    import os
    from pathlib import Path
    from gi.repository import Gio

    pkg_dir = Path(__file__).parent
    candidates = [
        pkg_dir / "mobitouchrobots.gresource",
        pkg_dir.parent.parent / "src" / "mobitouchrobots.gresource",
    ]
    for resource_file in candidates:
        if resource_file.exists():
            resource = Gio.Resource.load(str(resource_file))
            resource._register()
            break
