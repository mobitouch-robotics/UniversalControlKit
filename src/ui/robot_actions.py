import logging

from src.ui.controller_config import ControllerAction

_logger = logging.getLogger(__name__)


def invoke_robot_action(robot, action, *, flash_state=None, led_state=None, lidar_state=None):
    """Shared utility to invoke a robot action by ControllerAction enum or string.

    Toggle state holders (flash_state, led_state, lidar_state) are dicts with a
    single 'value' key so callers can maintain mutable state across calls.
    Example: flash_state = {'value': 0.0}
    """
    if not action:
        return

    action_enum = None
    if isinstance(action, ControllerAction):
        action_enum = action
    else:
        try:
            action_enum = ControllerAction(action) if isinstance(action, str) else None
        except Exception:
            action_enum = None

    # Movement/modifier actions are handled by individual controllers
    if action_enum in (ControllerAction.RUN, ControllerAction.SLOW,
                       ControllerAction.MOVEMENT, ControllerAction.ROTATION,
                       ControllerAction.PUSH_TO_TALK):
        return

    try:
        if action_enum == ControllerAction.JUMP and hasattr(robot, "jump_forward"):
            robot.jump_forward()
            return
        if action_enum == ControllerAction.FINGER_HEART and hasattr(robot, "finger_heart"):
            robot.finger_heart()
            return
        if action_enum == ControllerAction.STAND_UP and hasattr(robot, "stand_up"):
            robot.stand_up()
            if hasattr(robot, "recovery_stand"):
                try:
                    from PyQt5.QtCore import QTimer

                    def _call_recovery():
                        try:
                            robot.recovery_stand()
                        except Exception:
                            pass

                    QTimer.singleShot(2000, _call_recovery)
                except Exception:
                    pass
            return
        if action_enum == ControllerAction.SIT and hasattr(robot, "sit"):
            robot.sit()
            return
        if action_enum == ControllerAction.STRETCH and hasattr(robot, "stretch"):
            robot.stretch()
            return
        if action_enum == ControllerAction.HELLO and hasattr(robot, "hello"):
            robot.hello()
            return
        if action_enum == ControllerAction.DANCE1 and hasattr(robot, "dance1"):
            robot.dance1()
            return
        if action_enum == ControllerAction.STAND_DOWN and hasattr(robot, "stand_down"):
            robot.stand_down()
            return
        if action_enum == ControllerAction.TOGGLE_FLASH and hasattr(robot, "set_flashlight_brightness"):
            if flash_state is not None:
                v = flash_state.get('value', 0.0)
                if v == 0.0:
                    v = 1.0
                elif v == 1.0:
                    v = 0.5
                else:
                    v = 0.0
                flash_state['value'] = v
                robot.set_flashlight_brightness(int(v * 10))
            return
        if action_enum == ControllerAction.TOGGLE_LED and hasattr(robot, "set_led_color"):
            try:
                from unitree_webrtc_connect.constants import VUI_COLOR
                led_colors = [
                    VUI_COLOR.RED, VUI_COLOR.GREEN, VUI_COLOR.BLUE,
                    VUI_COLOR.YELLOW, VUI_COLOR.PURPLE,
                ]
                if led_state is not None:
                    idx = (led_state.get('value', 0) + 1) % len(led_colors)
                    led_state['value'] = idx
                    robot.set_led_color(led_colors[idx])
            except Exception:
                _logger.exception("Error toggling LED color")
            return
        if action_enum == ControllerAction.TOGGLE_LIDAR and hasattr(robot, "set_lidar"):
            if lidar_state is not None:
                v = not lidar_state.get('value', True)
                lidar_state['value'] = v
                robot.set_lidar(v)
            return

        # Legacy string actions
        if isinstance(action, str):
            if action == "stop_move" and hasattr(robot, "stop_move"):
                robot.stop_move()
                return
            if action == "connect" and hasattr(robot, "connect"):
                robot.connect()
                return
            if action == "disconnect" and hasattr(robot, "disconnect"):
                robot.disconnect()
                return

        _logger.info("Unknown or unsupported controller action: %s", action)
    except Exception:
        _logger.exception("Error invoking robot action '%s'", action)
