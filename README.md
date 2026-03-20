# Universal Control Kit

Universal Control Kit is a modular, extensible Python application for controlling robots (such as Unitree Go2) with a modern, cross-platform UI. It supports both keyboard and real gamepad input, advanced robot actions, and direct integration with Unitree's WebRTC SDK for robust, low-latency communication.

## Features

- **Cross-platform UI:** PyQt5 interface for flexible user experience.
- **Gamepad & Keyboard Control:** Universal input handling with customizable mappings.
- **Robot Actions:** Support for walking, running, SPORT_MODE, sitting, stretching, dancing, waving, jumping, and more.
- **Real-time Camera Feed:** View robot camera stream directly in the app.
- **Flashlight & LED Control:** Adjust flashlight brightness and cycle LED colors from the UI or gamepad.
- **Lidar Integration:** Enable/disable lidar scanner and receive point cloud data (Go2).
- **Extensible Protocols:** Easily add new robot types or UI backends via protocol-based architecture.
- **Internationalization:** Ready for translation/localization with gettext and .po files.

## Architecture

- **src/robot/**: Robot implementations (Go2), action protocols, and hardware integration.
- **src/ui/qt/**: PyQt5-based UI, including gamepad controller, camera view, and robot selector.
-- **src/ui/gtk/**: (removed) GTK-based UI components have been removed.
- **unitree_webrtc_connect**: WebRTC SDK integration for real-time robot communication.
- **data/**: Desktop files, icons, schemas, and metadata for packaging and distribution.

## Getting Started

1. **No manual setup required:**
	- The project automatically creates and configures the Python environment when you use the launch options.
2. **Connect your robot:**
	- Supports LocalAP, LocalSTA, and Remote connection modes.
3. **Run the app:**
	- Use the provided launch options in your IDE (e.g., VS Code "Run" button or launch configuration) to start the application. Manual setup scripts or commands are not needed.

## Supported Robots

- **Unitree Go2** (full feature set)


## Project Goals

- Provide a user-friendly, hackable interface for advanced robot control
- Enable research, education, and rapid prototyping with real robots
- Support new robot models and features as SDK evolves

## License

This project is licensed under the MIT License. See [LICENSE](LICENSE) for details.

## Acknowledgements

- [Unitree Robotics](https://www.unitree.com/) for hardware and SDK
- [unitree_webrtc_connect](https://github.com/legion1581/unitree_webrtc_connect) for WebRTC integration
- Open source contributors and the robotics community
