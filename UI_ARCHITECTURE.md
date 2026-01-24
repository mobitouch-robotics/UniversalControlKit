# UI Architecture

## Directory Structure

```
src/
├── ui/
│   ├── protocols.py          # Abstract interfaces for UI components
│   ├── gtk/                  # GTK-specific implementation
│   │   ├── __init__.py
│   │   ├── gtk_app.py        # GTK application class
│   │   ├── gtk_window.py     # Main GTK window
│   │   ├── gtk_controller.py # GTK movement controller
│   │   └── gtk_camera.py     # GTK camera view
│   └── tk/                   # Tkinter implementation (cross-platform)
│       ├── __init__.py
│       ├── tk_app.py         # Tk application class
│       ├── tk_controller.py  # Tk movement controller
│       └── tk_camera.py      # Tk camera view
├── robot/
│   ├── robot.py              # Robot interface
│   ├── robot_go2.py          # Unitree Go2 implementation
│   └── robot_dummy.py        # Dummy robot for testing
└── __main__.py               # Entry point with UI selection

```

## Class Organization

### Protocols (`src/ui/protocols.py`)
- `MovementControllerProtocol` - Abstract interface for movement controllers
- `CameraViewProtocol` - Abstract interface for camera views
- `UIApp` - Abstract interface for UI applications

### GTK Implementation (`src/ui/gtk/`)
- `GtkApp` - Main GTK application (Adwaita)
- `GtkWindow` - Application window with camera and controls
- `GtkMovementController` - Keyboard-based movement control
- `GtkCameraView` - Camera feed display widget

### Tkinter Implementation (`src/ui/tk/`)
- `TkApp` - Main Tk application
- `TkMovementController` - Keyboard-based movement control
- `TkCameraView` - Camera feed display with AspectFill scaling

## Running the Application

### Tk UI (default, cross-platform):
```bash
python -m mobitouchrobots
ROBOT_IP=192.168.1.190 python -m mobitouchrobots
```

### GTK UI (Linux):
```bash
UI=gtk python -m mobitouchrobots
```

### Dummy Robot (offline testing):
```bash
ROBOT_IMPL=Dummy python -m mobitouchrobots
ROBOT_IMPL=Dummy UI=gtk python -m mobitouchrobots
```

## Environment Variables

- `UI` - UI framework selection: `tk` (default) or `gtk`
- `ROBOT_IMPL` - Robot implementation: `Go2` (default) or `Dummy`
- `ROBOT_IP` - Robot IP address (default: `192.168.1.190`)
- `ROBOT_CONN` - Connection method: `LocalSTA`, `LocalAP`, or `PublicNetwork`

## Key Bindings (both UIs)

- **Arrow Keys**: Move forward/back, rotate left/right
- **z/x**: Strafe left/right
- **Shift**: Rest position (lay down)
- **Tab**: Stand up
- **0**: Jump forward
