from ..protocols import KeyCode
from ..protocols import MovementControllerProtocol
from PyQt5.QtCore import Qt, QTimer
from PyQt5.QtWidgets import QWidget
from src.ui.controllers_repository import ControllersRepository
from src.ui.controller_config import ControllerAction


class QtMovementController(MovementControllerProtocol):

    DEFAULT_ACTION_KEY_MAP = {
        "front": Qt.Key_Up,
        "back": Qt.Key_Down,
        "side_left": Qt.Key_Z,
        "side_right": Qt.Key_X,
        "rotate_left": Qt.Key_Left,
        "rotate_right": Qt.Key_Right,
        ControllerAction.RUN.value: Qt.Key_Shift,
        ControllerAction.STAND_UP.value: Qt.Key_Tab,
        ControllerAction.JUMP.value: Qt.Key_0,
    }

    ONE_SHOT_ACTIONS = {
        ControllerAction.STAND_UP.value,
        ControllerAction.STAND_DOWN.value,
        ControllerAction.STRETCH.value,
        ControllerAction.SIT.value,
        ControllerAction.HELLO.value,
        ControllerAction.JUMP.value,
        ControllerAction.FINGER_HEART.value,
        ControllerAction.DANCE1.value,
        ControllerAction.TOGGLE_FLASH.value,
        ControllerAction.TOGGLE_LED.value,
        ControllerAction.TOGGLE_LIDAR.value,
    }

    LEGACY_KEYCODE_TO_QT = {
        KeyCode.UP: Qt.Key_Up,
        KeyCode.DOWN: Qt.Key_Down,
        KeyCode.LEFT: Qt.Key_Left,
        KeyCode.RIGHT: Qt.Key_Right,
        KeyCode.Z: Qt.Key_Z,
        KeyCode.X: Qt.Key_X,
        KeyCode.SHIFT: Qt.Key_Shift,
        KeyCode.TAB: Qt.Key_Tab,
        KeyCode.ZERO: Qt.Key_0,
    }

    LEGACY_NAME_TO_QT = {
        "UP": Qt.Key_Up,
        "DOWN": Qt.Key_Down,
        "LEFT": Qt.Key_Left,
        "RIGHT": Qt.Key_Right,
        "Z": Qt.Key_Z,
        "X": Qt.Key_X,
        "SHIFT": Qt.Key_Shift,
        "TAB": Qt.Key_Tab,
        "ZERO": Qt.Key_0,
    }

    def __init__(self, robot, window: QWidget):
        super().__init__(robot)
        self.window = window
        self.active_keys = set()
        self.movement_speed = 1.0
        self._timer_ms = 100
        self._timer = None
        self._sent_zero_movement = False
        self._flash_brightness = 0.0
        self._led_color_idx = 0
        self._lidar_enabled = True
        self._action_to_key = {}
        self._key_to_actions = {}
        self._load_keyboard_mappings()

    def setup(self):
        self._timer = QTimer()
        self._timer.timeout.connect(self._on_move_tick)
        self._timer.start(self._timer_ms)

    def cleanup(self):
        if self._timer:
            self._timer.stop()
            self._timer = None

    def _parse_mapped_key(self, value):
        if value is None:
            return None
        if isinstance(value, int):
            return value
        if isinstance(value, KeyCode):
            return self.LEGACY_KEYCODE_TO_QT.get(value)
        if not isinstance(value, str):
            return None
        if value.startswith("Key:"):
            try:
                return int(value.split(":", 1)[1])
            except Exception:
                return None
        if value in self.LEGACY_NAME_TO_QT:
            return self.LEGACY_NAME_TO_QT[value]
        return None

    def _load_keyboard_mappings(self):
        mappings = dict(self.DEFAULT_ACTION_KEY_MAP)
        try:
            repo = ControllersRepository()
            keyboard_cfg = None
            for cfg in repo.get_controllers():
                try:
                    if cfg.type.name == "KEYBOARD":
                        keyboard_cfg = cfg
                        break
                except Exception:
                    continue
            if keyboard_cfg is not None:
                for m in keyboard_cfg.mappings or []:
                    action = m.get("action")
                    mapped = self._parse_mapped_key(m.get("input"))
                    if action and mapped is not None:
                        mappings[action] = mapped
        except Exception:
            pass

        self._action_to_key = mappings
        self._key_to_actions = {}
        for action, qt_key in self._action_to_key.items():
            self._key_to_actions.setdefault(qt_key, []).append(action)

    def _normalize_runtime_key(self, key):
        if isinstance(key, KeyCode):
            return self.LEGACY_KEYCODE_TO_QT.get(key)
        if isinstance(key, int):
            return key
        return None

    def _invoke_robot_action(self, action: str):
        if not action:
            return
        try:
            action_enum = ControllerAction(action)
        except Exception:
            action_enum = None

        if action_enum in (ControllerAction.RUN, ControllerAction.SLOW, ControllerAction.MOVEMENT, ControllerAction.ROTATION):
            return

        if action_enum == ControllerAction.JUMP and hasattr(self.robot, "jump_forward"):
            self.robot.jump_forward()
            return
        if action_enum == ControllerAction.FINGER_HEART and hasattr(self.robot, "finger_heart"):
            self.robot.finger_heart()
            return
        if action_enum == ControllerAction.STAND_UP and hasattr(self.robot, "stand_up"):
            self.robot.stand_up()
            if hasattr(self.robot, "recovery_stand"):
                try:
                    def _call_recovery():
                        try:
                            self.robot.recovery_stand()
                        except Exception:
                            pass

                    QTimer.singleShot(2000, _call_recovery)
                except Exception:
                    pass
            return
        if action_enum == ControllerAction.SIT and hasattr(self.robot, "sit"):
            self.robot.sit()
            return
        if action_enum == ControllerAction.STRETCH and hasattr(self.robot, "stretch"):
            self.robot.stretch()
            return
        if action_enum == ControllerAction.HELLO and hasattr(self.robot, "hello"):
            self.robot.hello()
            return
        if action_enum == ControllerAction.DANCE1 and hasattr(self.robot, "dance1"):
            self.robot.dance1()
            return
        if action_enum == ControllerAction.STAND_DOWN and hasattr(self.robot, "stand_down"):
            self.robot.stand_down()
            return
        if action_enum == ControllerAction.TOGGLE_FLASH and hasattr(self.robot, "set_flashlight_brightness"):
            if self._flash_brightness == 0.0:
                self._flash_brightness = 1.0
            elif self._flash_brightness == 1.0:
                self._flash_brightness = 0.5
            else:
                self._flash_brightness = 0.0
            self.robot.set_flashlight_brightness(int(self._flash_brightness * 10))
            return
        if action_enum == ControllerAction.TOGGLE_LED and hasattr(self.robot, "set_led_color"):
            try:
                from unitree_webrtc_connect.constants import VUI_COLOR

                led_colors = [
                    VUI_COLOR.RED,
                    VUI_COLOR.GREEN,
                    VUI_COLOR.BLUE,
                    VUI_COLOR.YELLOW,
                    VUI_COLOR.PURPLE,
                ]
                self._led_color_idx = (self._led_color_idx + 1) % len(led_colors)
                self.robot.set_led_color(led_colors[self._led_color_idx])
            except Exception:
                pass
            return
        if action_enum == ControllerAction.TOGGLE_LIDAR and hasattr(self.robot, "set_lidar"):
            self._lidar_enabled = not self._lidar_enabled
            self.robot.set_lidar(self._lidar_enabled)
            return

    def handle_key_press(self, key: KeyCode):
        qt_key = self._normalize_runtime_key(key)
        if qt_key is None:
            return False

        already_pressed = qt_key in self.active_keys
        self.active_keys.add(qt_key)

        mapped_actions = self._key_to_actions.get(qt_key, [])
        if not mapped_actions:
            return False

        if not already_pressed:
            for action in mapped_actions:
                if action in self.ONE_SHOT_ACTIONS:
                    self._invoke_robot_action(action)
        return True

    def handle_key_release(self, key: KeyCode):
        qt_key = self._normalize_runtime_key(key)
        if qt_key is None:
            return False
        if qt_key in self.active_keys:
            self.active_keys.remove(qt_key)
        return qt_key in self._key_to_actions

    def _is_action_pressed(self, action_name: str):
        key = self._action_to_key.get(action_name)
        return key in self.active_keys if key is not None else False

    def _on_move_tick(self):
        x = 0.0
        y = 0.0
        z = 0.0

        if self._is_action_pressed("front"):
            x += self.movement_speed
        if self._is_action_pressed("back"):
            x -= self.movement_speed
        if self._is_action_pressed("side_left"):
            y += self.movement_speed
        if self._is_action_pressed("side_right"):
            y -= self.movement_speed
        if self._is_action_pressed("rotate_left"):
            z = 1.0
        if self._is_action_pressed("rotate_right"):
            z = -1.0

        if self._is_action_pressed(ControllerAction.SLOW.value):
            speed = 0.25
        elif self._is_action_pressed(ControllerAction.RUN.value):
            speed = 1.0
        else:
            speed = 0.5

        x *= speed
        y *= speed

        if x < 0 and z != 0:
            z = -z
        # Only send move if robot is connected and move is available
        if self.robot.is_connected and hasattr(self.robot, "move"):
            if (x, y, z) == (0.0, 0.0, 0.0):
                if not self._sent_zero_movement:
                    self.robot.move(0, 0, 0)
                    self._sent_zero_movement = True
            else:
                self.robot.move(x, y, z)
                self._sent_zero_movement = False


# Utility to map Qt key events to universal KeyCode
def qt_key_to_universal(event):
    qt_to_universal = {
        Qt.Key_Up: KeyCode.UP,
        Qt.Key_Down: KeyCode.DOWN,
        Qt.Key_Left: KeyCode.LEFT,
        Qt.Key_Right: KeyCode.RIGHT,
        Qt.Key_Z: KeyCode.Z,
        Qt.Key_X: KeyCode.X,
        Qt.Key_Shift: KeyCode.SHIFT,
        Qt.Key_Tab: KeyCode.TAB,
        Qt.Key_0: KeyCode.ZERO,
    }
    return qt_to_universal.get(event.key(), KeyCode.UNKNOWN)
