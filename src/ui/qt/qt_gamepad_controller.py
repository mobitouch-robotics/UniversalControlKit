from ..protocols import MovementControllerProtocol
from unitree_webrtc_connect.constants import VUI_COLOR
from PyQt5.QtCore import QTimer

# Requires: pip install pygame
import pygame


class GamepadMovementController(MovementControllerProtocol):
    def __init__(self, robot):
        super().__init__(robot)
        self._running = False
        self._gamepad_connected = False
        self._timer = None
        self._joystick = None
        self._axes = (0.0, 0.0, 0.0)
        self._prev_button_states = None
        self._flash_brightness = 0.0
        self._led_color_idx = 0
        self._lidar_enabled = True
        self._sent_zero_movement = False

    def _is_moving(self, x, y):
        return abs(x) > 0.01 or abs(y) > 0.01

    def setup(self):
        pygame.init()
        pygame.joystick.init()
        if pygame.joystick.get_count() > 0:
            self._joystick = pygame.joystick.Joystick(0)
            self._joystick.init()
            self._gamepad_connected = True
            self._timer = QTimer()
            self._timer.timeout.connect(self._poll_gamepad)
            self._timer.start(50)
        else:
            self._gamepad_connected = False
            self._joystick = None

    def cleanup(self):
        self._gamepad_connected = False
        if self._timer:
            self._timer.stop()
            self._timer = None
        if self._joystick:
            self._joystick.quit()
            self._joystick = None
        pygame.quit()

    def handle_key_press(self, key):
        # Gamepad controller does not handle keyboard keys
        return False

    def handle_key_release(self, key):
        # Gamepad controller does not handle keyboard keys
        return False

    def _poll_gamepad(self):
        pygame.event.pump()
        num_buttons = self._joystick.get_numbuttons()
        button_states = [self._joystick.get_button(i) for i in range(num_buttons)]
        # Map gamepad buttons to robot actions
        # Arrow Up: usually button 11 (D-pad up), Arrow Down: button 12 (D-pad down) on many controllers
        # Triangle: button 3, Square: button 0, X: button 1, Circle: button 2 (PlayStation layout)
        # D-pad Left: button 13, D-pad Right: button 14 (common mapping)
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

        # Button mapping
        if rising_edge(15):
            self._lidar_enabled = not self._lidar_enabled
            if hasattr(self.robot, "set_lidar"):
                self.robot.set_lidar(self._lidar_enabled)
        if rising_edge(0):  # X
            if hasattr(self.robot, "hello"):
                self.robot.hello()
        if rising_edge(1):  # Circle
            if hasattr(self.robot, "finger_heart"):
                self.robot.finger_heart()
        if rising_edge(2):  # Square
            if hasattr(self.robot, "dance1"):
                self.robot.dance1()
        if rising_edge(3):  # Triangle
            if hasattr(self.robot, "jump_forward"):
                self.robot.jump_forward()
        if rising_edge(11):
            if hasattr(self.robot, "recovery_stand"):
                self.robot.recovery_stand()
        if rising_edge(12):
            if hasattr(self.robot, "stand_down"):
                self.robot.stand_down()
        if rising_edge(13):
            if hasattr(self.robot, "stretch"):
                self.robot.stretch()
        if rising_edge(14):
            if hasattr(self.robot, "sit"):
                self.robot.sit()
        if rising_edge(9):
            # Cycle: 0 -> 1 -> 0.5 -> 0
            if self._flash_brightness == 0.0:
                self._flash_brightness = 1.0
            elif self._flash_brightness == 1.0:
                self._flash_brightness = 0.5
            else:
                self._flash_brightness = 0.0
            if hasattr(self.robot, "set_flashlight_brightness"):
                # Go2 expects 0-10, so scale 1.0 to 10, 0.5 to 5, 0 to 0
                val = int(self._flash_brightness * 10)
                self.robot.set_flashlight_brightness(val)
        if rising_edge(10):
            # Cycle color using VUI_COLOR values
            led_colors = [
                VUI_COLOR.RED,
                VUI_COLOR.GREEN,
                VUI_COLOR.BLUE,
                VUI_COLOR.YELLOW,
                VUI_COLOR.PURPLE,
            ]
            self._flash_brightness = 0.0
            self._led_color_idx = (self._led_color_idx + 1) % len(led_colors)
            color = led_colors[self._led_color_idx]
            if hasattr(self.robot, "set_led_color"):
                self.robot.set_led_color(color)

        # Print rising edge for any button
        for idx in range(num_buttons):
            if rising_edge(idx):
                print(f"Gamepad: Rising edge detected on button {idx}")

        # Update previous button states
        self._prev_button_states = button_states.copy()

        # Typical mapping: left stick X (axis 0), Y (axis 1), right stick X (axis 2 or 3)
        x_axis = self._joystick.get_axis(1)  # Forward/backward
        y_axis = self._joystick.get_axis(0)  # Strafe left/right
        z_axis = 0.0
        # Try to get right stick X for rotation if available
        if self._joystick.get_numaxes() > 2:
            z_axis = self._joystick.get_axis(2)
        # Deadzone filtering
        deadzone = 0.15
        x = -x_axis if abs(x_axis) > deadzone else 0.0
        y = -y_axis if abs(y_axis) > deadzone else 0.0  # Reverse left/right
        z = -z_axis if abs(z_axis) > deadzone else 0.0  # Reverse rotation

        # Detect left joystick press (L3/left stick press)
        # Button index for L3 varies by controller/driver
        l3_pressed = False
        # Use button 7 for L3 (left stick press) as determined from debug output
        if num_buttons > 7 and button_states[7]:
            l3_pressed = True

        # Speed logic: L2 (left trigger) for slow, RT (right trigger) or running for fast
        speed = 0.5
        rt_pressed = False
        l2_pressed = False
        num_axes = self._joystick.get_numaxes()
        # L2 is usually axis 4, RT is axis 5
        if num_axes > 4:
            l2_value = self._joystick.get_axis(4)
            # -1.0 (released) to 1.0 (pressed) or 0.0 (released) to 1.0 (pressed)
            if l2_value > 0.5:
                l2_pressed = True
        if num_axes > 5:
            rt_value = self._joystick.get_axis(5)
            if rt_value <= -0.9 or rt_value >= 0.9:
                if rt_value <= -0.9:
                    if rt_value > 0.5:
                        rt_pressed = True
                else:
                    if rt_value > 0.5:
                        rt_pressed = True
            else:
                if rt_value > 0.5:
                    rt_pressed = True

        # Toggle running flag if L3 is pressed while moving
        if l3_pressed and self._is_moving(x, y) and not self._running:
            self._running = True
        # Reset running flag if not moving
        if not self._is_moving(x, y):
            self._running = False

        # L2 overrides running/RT for slow walk
        if l2_pressed:
            speed = 0.25
        elif rt_pressed or self._running:
            speed = 1.0
        x *= speed
        y *= speed
        z  # *= speed
        # Only send move if robot is connected and move is available
        if self.robot.is_connected and hasattr(self.robot, "move"):
            if (x, y, z) == (0.0, 0.0, 0.0):
                if not self._sent_zero_movement:
                    self.robot.move(0, 0, 0)
                    self._sent_zero_movement = True
            else:
                self.robot.move(x, y, z)
                self._sent_zero_movement = False
