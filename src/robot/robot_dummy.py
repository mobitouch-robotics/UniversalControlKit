import asyncio
import threading
import os
import numpy as np
import math
import tempfile
from typing import Optional
from pathlib import Path
from .robot import Robot

class Robot_Dummy(Robot):
    def _init_mgl(self):
        import moderngl
        import numpy as np
        import math
        width, height = 640, 480
        self._mgl_ctx = moderngl.create_standalone_context()
        # Print OpenGL info for debugging hardware/software rendering
        print('[moderngl] OpenGL renderer:', self._mgl_ctx.info['GL_RENDERER'])
        print('[moderngl] OpenGL version:', self._mgl_ctx.info['GL_VERSION'])
        print('[moderngl] OpenGL vendor:', self._mgl_ctx.info['GL_VENDOR'])
        self._mgl_fbo = self._mgl_ctx.simple_framebuffer((width, height), components=3)
        # --- Shaders ---
        self._mgl_prog = self._mgl_ctx.program(
            vertex_shader='''
                #version 330
                uniform mat4 m_proj;
                uniform mat4 m_view;
                uniform mat4 m_model;
                in vec3 in_vert;
                in vec3 in_color;
                out vec3 v_color;
                void main() {
                    gl_Position = m_proj * m_view * m_model * vec4(in_vert, 1.0);
                    v_color = in_color;
                }
            ''',
            fragment_shader='''
                #version 330
                in vec3 v_color;
                out vec4 f_color;
                void main() {
                    f_color = vec4(v_color, 1.0);
                }
            '''
        )
        # --- Ground ---
        ground_verts = np.array([
            -10, 0, -10,  0.4, 0.7, 0.4,
             10, 0, -10,  0.4, 0.7, 0.4,
             10, 0,  10,  0.4, 0.7, 0.4,
            -10, 0,  10,  0.4, 0.7, 0.4,
        ], dtype='f4')
        ground_idx = np.array([0, 1, 2, 2, 3, 0], dtype='i4')
        self._mgl_vbo_ground = self._mgl_ctx.buffer(ground_verts.tobytes())
        self._mgl_ibo_ground = self._mgl_ctx.buffer(ground_idx.tobytes())
        self._mgl_vao_ground = self._mgl_ctx.vertex_array(
            self._mgl_prog,
            [(self._mgl_vbo_ground, '3f 3f', 'in_vert', 'in_color')],
            self._mgl_ibo_ground
        )
        # --- Cube ---
        cube_verts = np.array([
            # x, y, z,   r, g, b
            # Front face
            -0.5, 0,  0.5,  0.8, 0.3, 0.3,
             0.5, 0,  0.5,  0.8, 0.3, 0.3,
             0.5, 1,  0.5,  0.8, 0.3, 0.3,
            -0.5, 1,  0.5,  0.8, 0.3, 0.3,
            # Back face
            -0.5, 0, -0.5,  0.8, 0.3, 0.3,
             0.5, 0, -0.5,  0.8, 0.3, 0.3,
             0.5, 1, -0.5,  0.8, 0.3, 0.3,
            -0.5, 1, -0.5,  0.8, 0.3, 0.3,
        ], dtype='f4')
        cube_idx = np.array([
            0, 1, 2, 2, 3, 0,  # Front
            1, 5, 6, 6, 2, 1,  # Right
            5, 4, 7, 7, 6, 5,  # Back
            4, 0, 3, 3, 7, 4,  # Left
            3, 2, 6, 6, 7, 3,  # Top
            4, 5, 1, 1, 0, 4   # Bottom
        ], dtype='i4')
        self._mgl_vbo_cube = self._mgl_ctx.buffer(cube_verts.tobytes())
        self._mgl_ibo_cube = self._mgl_ctx.buffer(cube_idx.tobytes())
        self._mgl_vao_cube = self._mgl_ctx.vertex_array(
            self._mgl_prog,
            [(self._mgl_vbo_cube, '3f 3f', 'in_vert', 'in_color')],
            self._mgl_ibo_cube
        )
        # --- Robot (blue) ---
        robot_verts = cube_verts.copy()
        robot_verts[3::6] = 0.2  # r
        robot_verts[4::6] = 0.2  # g
        robot_verts[5::6] = 0.8  # b
        self._mgl_vbo_robot = self._mgl_ctx.buffer(robot_verts.tobytes())
        self._mgl_vao_robot = self._mgl_ctx.vertex_array(
            self._mgl_prog,
            [(self._mgl_vbo_robot, '3f 3f', 'in_vert', 'in_color')],
            self._mgl_ibo_cube
        )
        self._mgl_width = width
        self._mgl_height = height
    def __init__(self, *args, **kwargs):
        self.position = [0.0, 0.0, 0.0]  # x, y, z (y is up)
        self.angle = 0.0  # Smoothed yaw angle in degrees
        self.target_angle = 0.0  # Target yaw angle in degrees
        self.running = False
        self._vel_forward = 0.0
        self._vel_strafe = 0.0
        self._vel_yaw = 0.0
        self._timer = None

    def is_connected(self) -> bool:
        return self.running

    def connect(self):
        if self.running:
            return
        self.running = True
        # Start update timer for smooth movement
        import threading
        def update_loop():
            import time
            last = time.time()
            while self.running:
                now = time.time()
                dt = min(now - last, 0.05)
                last = now
                self._update_position(dt)
                time.sleep(0.016)
        self._timer = threading.Thread(target=update_loop, daemon=True)
        self._timer.start()

    def disconnect(self):
        print("[DEBUG] Robot_Dummy.disconnect called")
        self.running = False
        self._vel_forward = 0.0
        self._vel_strafe = 0.0
        self._vel_yaw = 0.0
        # No QtDummy3DView cleanup needed (legacy)

    def move(self, x: float = 0.0, y: float = 0.0, z: float = 0.0):
        """
        Set the robot's velocity for smooth movement.
        x = forward/back, y = strafe, z = rotate (yaw)
        """
        if not self.running:
            return
        self._vel_forward = x * 2.0  # units per second
        self._vel_strafe = y * 2.0
        # Instead of setting _vel_yaw directly, update target_angle for smoothing
        self._vel_yaw = z * 90.0  # degrees per second
        # Compute new target angle based on input
        self.target_angle = (self.target_angle + self._vel_yaw * 0.016) % 360

    def _update_position(self, dt):
        # Smoothly update position and angle based on velocity
        # Interpolate angle towards target_angle for smoothing
        angle_diff = (self.target_angle - self.angle + 540) % 360 - 180  # shortest path
        smoothing = min(1.0, dt * 10.0)  # smoothing factor, higher = faster
        self.angle = (self.angle + angle_diff * smoothing) % 360
        rad = math.radians(self.angle)
        forward = self._vel_forward * dt
        strafe = self._vel_strafe * dt
        self.position[0] += forward * math.sin(rad) + strafe * math.cos(rad)
        self.position[2] += forward * math.cos(rad) - strafe * math.sin(rad)

    def stop(self):
        pass

    def rest(self):
        pass

    def standup(self):
        pass

    def jump_forward(self):
        pass

    def get_camera_frame(self):
        # Only render if connected
        if not getattr(self, 'running', False):
            return None
        import time
        print('[DEBUG] Dummy get_camera_frame called (moderngl 3D cached)')
        # --- Frame rate limiter (default 30 FPS) ---
        min_interval = 1.0 / 30.0
        now = time.time()
        if not hasattr(self, '_last_frame_time'):
            self._last_frame_time = 0
            self._last_frame = None
        if not hasattr(self, '_last_frame') or (now - self._last_frame_time) >= min_interval or self._last_frame is None:
            try:
                import numpy as np
                import math
                if not hasattr(self, '_mgl_ctx'):
                    self._init_mgl()
                width, height = self._mgl_width, self._mgl_height
                self._mgl_fbo.use()
                self._mgl_fbo.clear(0.7, 0.8, 1.0, 1.0)

                # --- 3D Camera Setup ---
                def perspective(fovy, aspect, near, far):
                    f = 1.0 / math.tan(fovy / 2)
                    return np.array([
                        [f/aspect, 0, 0, 0],
                        [0, f, 0, 0],
                        [0, 0, (far+near)/(near-far), (2*far*near)/(near-far)],
                        [0, 0, -1, 0]
                    ], dtype='f4')

                def lookat(eye, target, up):
                    f = np.array(target) - np.array(eye)
                    f = f / np.linalg.norm(f)
                    u = np.array(up)
                    s = np.cross(f, u)
                    s = s / np.linalg.norm(s)
                    u = np.cross(s, f)
                    m = np.identity(4, dtype='f4')
                    m[0, :3] = s
                    m[1, :3] = u
                    m[2, :3] = -f
                    t = np.identity(4, dtype='f4')
                    t[:3, 3] = -np.array(eye)
                    return m @ t

                proj = perspective(math.radians(60), width/height, 0.1, 100)
                rx, ry, rz = self.position
                angle = self.angle
                cam_distance = 5.0
                cam_height = 2.5
                rad = math.radians(angle)
                cam_x = rx - cam_distance * math.sin(rad)
                cam_y = ry + cam_height
                cam_z = rz - cam_distance * math.cos(rad)
                view = lookat(
                    [cam_x, cam_y, cam_z],
                    [rx, ry + 0.5, rz],
                    [0, 1, 0]
                )

                prog = self._mgl_prog
                prog['m_proj'].write(proj.T.tobytes())
                prog['m_view'].write(view.T.tobytes())
                prog['m_model'].write(np.eye(4, dtype='f4').tobytes())
                self._mgl_vao_ground.render()

                def box_model(x, y, z, angle=0):
                    m = np.eye(4, dtype='f4')
                    m[:3, 3] = [x, y, z]
                    if angle != 0:
                        c, s = math.cos(math.radians(angle)), math.sin(math.radians(angle))
                        rot = np.array([
                            [c, 0, s, 0],
                            [0, 1, 0, 0],
                            [-s, 0, c, 0],
                            [0, 0, 0, 1]
                        ], dtype='f4')
                        m = m @ rot
                    return m

                # Draw 4 red boxes
                for bx, by, bz in [(2, 0, 2), (-2, 0, -2), (2, 0, -2), (-2, 0, 2)]:
                    prog['m_model'].write(box_model(bx, 0, bz).T.tobytes())
                    self._mgl_vao_cube.render()
                # Draw robot as blue box
                prog['m_model'].write(box_model(rx, 0, rz, angle).T.tobytes())
                self._mgl_vao_robot.render()

                # Read framebuffer
                data = self._mgl_fbo.read(components=3, alignment=1)
                img = np.frombuffer(data, dtype=np.uint8).reshape((height, width, 3))
                img = np.flipud(img)
                self._last_frame = img
                self._last_frame_time = now
            except Exception as e:
                print(f"[Dummy3D] moderngl render error: {e}")
                img = np.ones((480, 640, 3), dtype=np.uint8) * 255
                self._last_frame = img
                self._last_frame_time = now
        return self._last_frame

    def _draw_box_osmesa(self, GL):
        GL.glBegin(GL.GL_QUADS)
        # Top
        GL.glVertex3f(-0.5, 0.5, -0.5)
        GL.glVertex3f(0.5, 0.5, -0.5)
        GL.glVertex3f(0.5, 0.5, 0.5)
        GL.glVertex3f(-0.5, 0.5, 0.5)
        # Bottom
        GL.glVertex3f(-0.5, -0.5, -0.5)
        GL.glVertex3f(0.5, -0.5, -0.5)
        GL.glVertex3f(0.5, -0.5, 0.5)
        GL.glVertex3f(-0.5, -0.5, 0.5)
        # Front
        GL.glVertex3f(-0.5, -0.5, 0.5)
        GL.glVertex3f(0.5, -0.5, 0.5)
        GL.glVertex3f(0.5, 0.5, 0.5)
        GL.glVertex3f(-0.5, 0.5, 0.5)
        # Back
        GL.glVertex3f(-0.5, -0.5, -0.5)
        GL.glVertex3f(0.5, -0.5, -0.5)
        GL.glVertex3f(0.5, 0.5, -0.5)
        GL.glVertex3f(-0.5, 0.5, -0.5)
        # Left
        GL.glVertex3f(-0.5, -0.5, -0.5)
        GL.glVertex3f(-0.5, -0.5, 0.5)
        GL.glVertex3f(-0.5, 0.5, 0.5)
        GL.glVertex3f(-0.5, 0.5, -0.5)
        # Right
        GL.glVertex3f(0.5, -0.5, -0.5)
        GL.glVertex3f(0.5, -0.5, 0.5)
        GL.glVertex3f(0.5, 0.5, 0.5)
        GL.glVertex3f(0.5, 0.5, -0.5)
        GL.glEnd()

    def _draw_box(self):
        from OpenGL.GL import glBegin, glEnd, glVertex3f, GL_QUADS
        glBegin(GL_QUADS)
        # Top
        glVertex3f(-0.5, 0.5, -0.5)
        glVertex3f(0.5, 0.5, -0.5)
        glVertex3f(0.5, 0.5, 0.5)
        glVertex3f(-0.5, 0.5, 0.5)
        # Bottom
        glVertex3f(-0.5, -0.5, -0.5)
        glVertex3f(0.5, -0.5, -0.5)
        glVertex3f(0.5, -0.5, 0.5)
        glVertex3f(-0.5, -0.5, 0.5)
        # Front
        glVertex3f(-0.5, -0.5, 0.5)
        glVertex3f(0.5, -0.5, 0.5)
        glVertex3f(0.5, 0.5, 0.5)
        glVertex3f(-0.5, 0.5, 0.5)
        # Back
        glVertex3f(-0.5, -0.5, -0.5)
        glVertex3f(0.5, -0.5, -0.5)
        glVertex3f(0.5, 0.5, -0.5)
        glVertex3f(-0.5, 0.5, -0.5)
        # Left
        glVertex3f(-0.5, -0.5, -0.5)
        glVertex3f(-0.5, -0.5, 0.5)
        glVertex3f(-0.5, 0.5, 0.5)
        glVertex3f(-0.5, 0.5, -0.5)
        # Right
        glVertex3f(0.5, -0.5, -0.5)
        glVertex3f(0.5, -0.5, 0.5)
        glVertex3f(0.5, 0.5, 0.5)
        glVertex3f(0.5, 0.5, -0.5)
        glEnd()
