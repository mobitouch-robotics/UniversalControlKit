from ..protocols import MovementControllerProtocol
from ..robot_actions import invoke_robot_action as _shared_invoke
from PyQt5.QtCore import QTimer

# Requires: pip install pygame
import pygame
import logging
from src.ui.controller_config import ControllerAction

logger = logging.getLogger(__name__)


class GamepadMovementController(MovementControllerProtocol):
    def __init__(self, robot, controller=None, notifier=None):
        super().__init__(robot)
        self._running = False
        self._gamepad_connected = False
        self._timer = None
        self._joystick = None
        # Optional notifier callback: callable(action_name:str, state:bool)
        self._notifier = notifier
        # `controller` may be:
        #  - None: connect to the first available joystick
        #  - int: joystick index (0..N-1) or str: substring to match against joystick name or GUID (backwards compat)
        #  - ControllerConfig instance: use its guid/name and mappings
        self._joystick_id = None
        self._controller_cfg = None
        if controller is not None:
            # detect type
            try:
                # avoid importing ControllerConfig to prevent circular imports; duck-type
                if hasattr(controller, "type") and hasattr(controller, "mappings"):
                    self._controller_cfg = controller
                else:
                    self._joystick_id = controller
            except Exception:
                self._joystick_id = controller
        self._axes = (0.0, 0.0, 0.0)
        self._prev_button_states = None
        self._prev_axis_pressed = {}
        self._prev_hat_pressed = {}
        self._flash_state = {'value': 0.0}
        self._led_state = {'value': 0}
        self._lidar_state = {'value': True}
        self._sent_zero_movement = False

    @staticmethod
    def _is_hat_direction_pressed(hat_value, direction):
        if not isinstance(direction, str):
            return False
        try:
            x_val, y_val = hat_value
        except Exception:
            return False

        direction = direction.lower()
        if direction == 'up':
            return y_val > 0
        if direction == 'down':
            return y_val < 0
        if direction == 'left':
            return x_val < 0
        if direction == 'right':
            return x_val > 0
        return False

    def _is_moving(self, x, y):
        return abs(x) > 0.01 or abs(y) > 0.01

    def _invoke_robot_action(self, action):
        """Invoke a robot action via the shared utility."""
        # Handle PTT action: delegate to voice controller if available
        try:
            action_enum = action if isinstance(action, ControllerAction) else ControllerAction(action)
        except Exception:
            action_enum = None

        if action_enum == ControllerAction.PUSH_TO_TALK:
            # PTT is handled externally via the voice controller
            return

        _shared_invoke(
            self.robot, action,
            flash_state=self._flash_state,
            led_state=self._led_state,
            lidar_state=self._lidar_state,
        )

    def setup(self):
        pygame.init()
        pygame.joystick.init()
        count = pygame.joystick.get_count()
        self._gamepad_connected = False
        self._joystick = None
        if count > 0:
            selected = None
            # If an explicit integer index was provided, try to use only that
            if isinstance(self._joystick_id, int):
                candidates = [self._joystick_id]
            else:
                candidates = range(count)

            for i in candidates:
                if i < 0 or i >= count:
                    continue
                try:
                    j = pygame.joystick.Joystick(i)
                    j.init()
                except Exception:
                    continue

                matched = False
                if self._joystick_id is None:
                    matched = True
                elif isinstance(self._joystick_id, int):
                    matched = (i == self._joystick_id)
                elif isinstance(self._joystick_id, str):
                    # match against name or GUID (if available)
                    try:
                        name = j.get_name() or ""
                    except Exception:
                        name = ""
                    try:
                        if hasattr(j, "get_guid"):
                            guid_raw = j.get_guid()
                            guid = str(guid_raw) if guid_raw is not None else ""
                        else:
                            guid = ""
                    except Exception:
                        guid = ""
                    key = self._joystick_id.lower()
                    if key in name.lower() or (isinstance(guid, str) and key in guid.lower()):
                        matched = True

                if matched:
                    selected = j
                    break

            if selected:
                self._joystick = selected
                self._gamepad_connected = True
                try:
                    j_name = self._joystick.get_name() or ""
                except Exception:
                    j_name = ""
                try:
                    j_guid_raw = self._joystick.get_guid() if hasattr(self._joystick, "get_guid") else ""
                    j_guid = str(j_guid_raw) if j_guid_raw is not None else ""
                except Exception:
                    j_guid = ""
                logger.info(f"Gamepad connected: index={i} name='{j_name}' guid='{j_guid}'")
                self._timer = QTimer()
                self._timer.timeout.connect(self._poll_gamepad)
                self._timer.start(50)
            else:
                self._gamepad_connected = False
                self._joystick = None

    @staticmethod
    def list_gamepads():
        """Print available joysticks (index, name, guid)."""
        try:
            pygame.joystick.init()
        except Exception:
            pass
        count = pygame.joystick.get_count()
        if count <= 0:
            logger.info("No joysticks found")
            return
        logger.info("Available joysticks:")
        for i in range(count):
            try:
                jt = pygame.joystick.Joystick(i)
                try:
                    jt.init()
                except Exception:
                    pass
                try:
                    name = jt.get_name() or ""
                except Exception:
                    name = ""
                try:
                    guid_raw = jt.get_guid() if hasattr(jt, "get_guid") else ""
                    guid = str(guid_raw) if guid_raw is not None else ""
                except Exception:
                    guid = ""
                logger.info(f"  [{i}] name='{name}' guid='{guid}'")
            except Exception:
                logger.info(f"  [{i}] (failed to read joystick)")

    def cleanup(self):
        self._gamepad_connected = False
        if self._timer:
            self._timer.stop()
            self._timer = None
        if self._joystick:
            try:
                # quit may not exist on all pygame versions
                if hasattr(self._joystick, "quit"):
                    self._joystick.quit()
            except Exception:
                pass
            self._joystick = None
        pygame.quit()

    def _poll_gamepad(self):
        pygame.event.pump()
        # Guard against joystick disappearing between polls (e.g., view closed)
        if self._joystick is None:
            return

        num_buttons = self._joystick.get_numbuttons()
        button_states = [self._joystick.get_button(i) for i in range(num_buttons)]
        # Debug: raw sample of buttons and first few axes to help threshold debugging
        try:
            na = self._joystick.get_numaxes()
            sample_axes = [self._joystick.get_axis(i) for i in range(min(6, na))]
        except Exception:
            sample_axes = []
        # raw sample logged at debug level previously; removed debug noise
        # Ensure _prev_button_states is correct length and always initialized
        if (
            self._prev_button_states is None
            or len(self._prev_button_states) != num_buttons
        ):
            self._prev_button_states = [0] * num_buttons

        def rising_edge(idx):
            return (
                num_buttons > idx
                and button_states[idx]
                and (not self._prev_button_states[idx])
            )

        # Determine controller config and build mapping tables (buttons, axes, sticks)
        buttons_map = {}
        axes_map = {}
        hats_map = {}
        movement_stick = None
        rotation_stick = None
        # Resolve controller config: prefer explicitly provided config, otherwise match by GUID/name
        cfg = self._controller_cfg
        if cfg is None:
            try:
                from src.ui.controllers_repository import ControllersRepository

                repo = ControllersRepository()
                try:
                    name = self._joystick.get_name() or ""
                except Exception:
                    name = ""
                try:
                    guid_raw = self._joystick.get_guid() if hasattr(self._joystick, "get_guid") else ""
                    guid = str(guid_raw) if guid_raw is not None else ""
                except Exception:
                    guid = ""
                for c in repo.get_controllers():
                    try:
                        if getattr(c.type, "name", None) == 'JOYSTICK':
                            if c.guid and c.guid == guid:
                                cfg = c
                                break
                            if c.name and c.name in name:
                                cfg = c
                                break
                    except Exception:
                        continue
            except Exception:
                cfg = None

        # Parse mappings from the resolved controller config
        if cfg is not None:
            try:
                for m in cfg.mappings or []:
                    inp = m.get('input')
                    act = m.get('action')
                    # try to convert stored action string to ControllerAction enum
                    try:
                        act_enum = ControllerAction(act) if isinstance(act, str) else act
                    except Exception:
                        act_enum = act
                    if not inp or not act:
                        continue
                    try:
                        if isinstance(inp, str) and inp.startswith('Button'):
                            # ButtonN
                            try:
                                bidx = int(inp.replace('Button', ''))
                            except Exception:
                                continue
                            buttons_map.setdefault(bidx, []).append(act_enum)
                        elif isinstance(inp, str) and inp.startswith('Axis'):
                            # AxisN or AxisN:+ / AxisN:-
                            parts = inp.split(':')
                            try:
                                aidx = int(parts[0].replace('Axis', ''))
                            except Exception:
                                continue
                            direction = parts[1] if len(parts) > 1 else None
                            axes_map.setdefault(aidx, []).append((act_enum, direction))
                        elif isinstance(inp, str) and inp.startswith('Hat'):
                            # HatN:Up / HatN:Down / HatN:Left / HatN:Right
                            parts = inp.split(':')
                            try:
                                hidx = int(parts[0].replace('Hat', ''))
                            except Exception:
                                continue
                            direction = parts[1] if len(parts) > 1 else None
                            if direction:
                                hats_map.setdefault(hidx, []).append((act_enum, direction))
                        elif isinstance(inp, str) and inp.startswith('stick:'):
                            parts = inp.split(':')
                            try:
                                sid = int(parts[1])
                            except Exception:
                                sid = None
                            if act_enum == ControllerAction.MOVEMENT or (isinstance(act, str) and act == 'movement_axes'):
                                movement_stick = sid
                            elif act_enum == ControllerAction.ROTATION or (isinstance(act, str) and act == 'rotation_axis'):
                                rotation_stick = sid
                        elif isinstance(inp, int):
                            axes_map.setdefault(inp, []).append(act_enum)
                    except Exception:
                        continue
            except Exception:
                pass

        # Diagnostic info (INFO may be suppressed; useful during troubleshooting)
        try:
            logger.info("Parsed controller mappings: buttons=%s axes=%s hats=%s movement_stick=%s rotation_stick=%s",
                        list(buttons_map.keys()), list(axes_map.keys()), list(hats_map.keys()), movement_stick, rotation_stick)
        except Exception:
            pass

        # Handle button actions and compute modifier states (e.g., 'run', 'slow')
        run_active = False
        slow_active = False
        # Process button states: call mapped robot actions on rising edge,
        # but treat special mapping actions like 'movement_axes', 'rotation_axis',
        # and 'run' as controller-level behaviors rather than direct robot calls.
        for idx in range(num_buttons):
            acts = buttons_map.get(idx, [])
            cur = bool(button_states[idx]) if idx < len(button_states) else False
            prev = bool(self._prev_button_states[idx]) if idx < len(self._prev_button_states) else False
            try:
                logger.info("Button %s state cur=%s prev=%s mapped_actions=%s", idx, cur, prev, acts)
            except Exception:
                pass
            # Check each mapped action for this button
            for action in acts:
                try:
                    if action == ControllerAction.RUN or (isinstance(action, str) and action == 'run'):
                        # treat as modifier: active while button is held
                        if cur:
                            run_active = True
                    elif action == ControllerAction.SLOW or (isinstance(action, str) and action == 'slow'):
                        if cur:
                            slow_active = True
                    elif action == ControllerAction.MOVEMENT or action == ControllerAction.ROTATION or (isinstance(action, str) and action in ('movement_axes', 'rotation_axis')):
                        # these are handled elsewhere (stick mappings)
                        pass
                    else:
                        # normal robot action: trigger on rising edge
                        if cur and (not prev):
                            try:
                                logger.info("Invoking robot action '%s' from button %s", action, idx)
                                self._invoke_robot_action(action)
                            except Exception:
                                pass
                except Exception:
                    pass

        # Handle axis-as-button mappings (virtual buttons) and compute run_active
        try:
            axis_threshold = 0.9
            for aidx, acts in axes_map.items():
                try:
                    if aidx < 0 or aidx >= self._joystick.get_numaxes():
                        continue
                    val = self._joystick.get_axis(aidx)
                except Exception:
                    continue

                prev = self._prev_axis_pressed.get(aidx, False)
                any_pressed = False
                # acts may be a list of either action strings (backward compat)
                # or tuples (action, direction)
                for entry in acts:
                    try:
                        if isinstance(entry, tuple) or isinstance(entry, list):
                            action, direction = entry[0], entry[1]
                        else:
                            action, direction = entry, None

                        if direction == '+':
                            pressed = val > axis_threshold
                        elif direction == '-':
                            pressed = val < -axis_threshold
                        else:
                            pressed = abs(val) > axis_threshold

                        if pressed:
                            any_pressed = True
                            if action == ControllerAction.RUN or (isinstance(action, str) and action == 'run'):
                                run_active = True
                            elif action == ControllerAction.SLOW or (isinstance(action, str) and action == 'slow'):
                                slow_active = True
                            elif action == ControllerAction.MOVEMENT or action == ControllerAction.ROTATION or (isinstance(action, str) and action in ('movement_axes', 'rotation_axis')):
                                # handled in movement/rotation processing
                                pass
                            else:
                                if pressed and (not prev):
                                    try:
                                        logger.info("Invoking robot action '%s' from axis %s", action, aidx)
                                        self._invoke_robot_action(action)
                                    except Exception:
                                        pass
                    except Exception:
                        pass

                # store aggregate pressed state for this axis index
                self._prev_axis_pressed[aidx] = any_pressed
        except Exception:
            pass

        # Handle hat / D-pad mappings and compute modifier states.
        try:
            num_hats = self._joystick.get_numhats() if hasattr(self._joystick, 'get_numhats') else 0
            for hidx, acts in hats_map.items():
                try:
                    if hidx < 0 or hidx >= num_hats:
                        continue
                    hat_value = self._joystick.get_hat(hidx)
                except Exception:
                    continue

                for entry in acts:
                    try:
                        if isinstance(entry, tuple) or isinstance(entry, list):
                            action, direction = entry[0], entry[1]
                        else:
                            action, direction = entry, None

                        if not direction:
                            continue

                        direction_key = direction.lower()
                        pressed = self._is_hat_direction_pressed(hat_value, direction_key)
                        prev = self._prev_hat_pressed.get((hidx, direction_key), False)

                        if pressed:
                            if action == ControllerAction.RUN or (isinstance(action, str) and action == 'run'):
                                run_active = True
                            elif action == ControllerAction.SLOW or (isinstance(action, str) and action == 'slow'):
                                slow_active = True
                            elif action == ControllerAction.MOVEMENT or action == ControllerAction.ROTATION or (isinstance(action, str) and action in ('movement_axes', 'rotation_axis')):
                                pass
                            else:
                                if not prev:
                                    try:
                                        logger.info("Invoking robot action '%s' from hat %s %s", action, hidx, direction_key)
                                        self._invoke_robot_action(action)
                                    except Exception:
                                        pass

                        self._prev_hat_pressed[(hidx, direction_key)] = pressed
                    except Exception:
                        pass
        except Exception:
            pass

        # Update running/slow modifiers based on mapped inputs (slow has precedence)
        prev_running = getattr(self, '_running', False)
        prev_slow = getattr(self, '_slow', False)
        self._running = bool(run_active)
        self._slow = bool(slow_active)
        # Notify external listener if provided when modifier state changes
        try:
            if self._notifier is not None:
                if self._running != prev_running:
                    try:
                        self._notifier('run', self._running)
                    except Exception:
                        pass
                if self._slow != prev_slow:
                    try:
                        self._notifier('slow', self._slow)
                    except Exception:
                        pass
        except Exception:
            pass

        

        # Update previous button states
        self._prev_button_states = button_states.copy()

        # Determine movement/rotation axes; allow controller config to override via sticks
        x_axis = 0.0
        y_axis = 0.0
        z_axis = 0.0
        try:
            naxes = self._joystick.get_numaxes()
        except Exception:
            naxes = 0

        # Movement stick: prefer configured stick if available
        if movement_stick is not None:
            base = movement_stick * 2
            # forward/backward -> axis base+1, strafe -> axis base
            try:
                if base + 1 < naxes:
                    x_axis = self._joystick.get_axis(base + 1)
                if base < naxes:
                    y_axis = self._joystick.get_axis(base)
            except Exception:
                x_axis = 0.0
                y_axis = 0.0
        else:
            # Typical default mapping: axis 1 = forward/back, axis 0 = strafe
            try:
                if naxes > 1:
                    x_axis = self._joystick.get_axis(1)
                if naxes > 0:
                    y_axis = self._joystick.get_axis(0)
            except Exception:
                x_axis = 0.0
                y_axis = 0.0

        # Rotation stick: use configured stick if present, else default to axis 2 if present
        if rotation_stick is not None:
            base_r = rotation_stick * 2
            try:
                if base_r < naxes:
                    z_axis = self._joystick.get_axis(base_r)
            except Exception:
                z_axis = 0.0
        else:
            try:
                if naxes > 2:
                    z_axis = self._joystick.get_axis(2)
                else:
                    z_axis = 0.0
            except Exception:
                z_axis = 0.0
        # Deadzone filtering
        deadzone = 0.15
        x = -x_axis if abs(x_axis) > deadzone else 0.0
        y = -y_axis if abs(y_axis) > deadzone else 0.0  # Reverse left/right
        z = -z_axis if abs(z_axis) > deadzone else 0.0  # Reverse rotation

        # Speed logic: controlled by mapped 'run' and 'slow' inputs
        # Precedence: slow overrides run. Defaults: normal=0.5, run=1.0, slow=0.25
        if getattr(self, '_slow', False):
            speed = 0.25
        elif getattr(self, '_running', False):
            speed = 1.0
        else:
            speed = 0.5
        x *= speed
        y *= speed
        z  # *= speed
        # Computed movement logged previously; removed debug noise
        # Only send move if robot is connected and move is available
        if self.robot.is_connected and hasattr(self.robot, "move"):
            if (x, y, z) == (0.0, 0.0, 0.0):
                if not self._sent_zero_movement:
                    self.robot.move(0, 0, 0)
                    self._sent_zero_movement = True
            else:
                self.robot.move(x, y, z)
                self._sent_zero_movement = False
