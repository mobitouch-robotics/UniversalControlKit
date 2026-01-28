import math
import numpy as np
import moderngl
from PIL import Image
import os
import pywavefront
from .robot import Robot


class Dummy3DRenderer:
    def _init_person_plane(self):
        # Plane mesh: 1x2 units, centered at origin
        plane_verts = np.array(
            [
                [-0.5, 0, 0, 0.0, 1.0],
                [0.5, 0, 0, 1.0, 1.0],
                [0.5, 2, 0, 1.0, 0.0],
                [-0.5, 2, 0, 0.0, 0.0],
            ],
            dtype="f4",
        )
        plane_idx = np.array([0, 1, 2, 2, 3, 0], dtype="i4")
        self._mgl_vbo_person = self._mgl_ctx.buffer(plane_verts.tobytes())
        self._mgl_ibo_person = self._mgl_ctx.buffer(plane_idx.tobytes())
        self._mgl_prog_person = self._mgl_ctx.program(
            vertex_shader="""
                #version 330
                uniform mat4 m_proj;
                uniform mat4 m_view;
                uniform mat4 m_model;
                in vec3 in_vert;
                in vec2 in_uv;
                out vec2 v_uv;
                void main() {
                    gl_Position = m_proj * m_view * m_model * vec4(in_vert, 1.0);
                    v_uv = in_uv;
                }
            """,
            fragment_shader="""
                #version 330
                in vec2 v_uv;
                out vec4 f_color;
                uniform sampler2D u_tex;
                void main() {
                    vec4 tex = texture(u_tex, v_uv);
                    if (tex.a < 0.1) discard;
                    f_color = tex;
                }
            """,
        )
        # Load person.png texture
        person_path = os.path.abspath(
            os.path.join(os.path.dirname(__file__), "../../person.png")
        )
        try:
            img = Image.open(person_path).convert("RGBA")
            img = img.resize((256, 512))
            self._mgl_tex_person = self._mgl_ctx.texture(img.size, 4, img.tobytes())
            self._mgl_tex_person.build_mipmaps()
        except Exception as e:
            print(f"[Dummy3D] Could not load person.png: {e}")
            self._mgl_tex_person = None
        self._mgl_vao_person = self._mgl_ctx.vertex_array(
            self._mgl_prog_person,
            [(self._mgl_vbo_person, "3f 2f", "in_vert", "in_uv")],
            self._mgl_ibo_person,
        )

    def __init__(self, width=640, height=480):
        self.width = width
        self.height = height
        # Ensure width/height are set before _init_mgl
        self._init_mgl()

    def _init_mgl(self):
        self._mgl_ctx = moderngl.create_standalone_context()
        self._mgl_fbo = self._mgl_ctx.simple_framebuffer(
            (self.width, self.height), components=3
        )
        self._init_sky_sphere()
        self._init_ground()
        self._init_cube()
        self._init_person_plane()
        self._init_robot()
        self._load_textures()

    def _init_sky_sphere(self):
        segments = 32
        rings = 32
        radius = 100.0
        verts = []
        uvs = []
        idx = []
        for y in range(rings + 1):
            theta = (y / rings) * np.pi
            for x in range(segments + 1):
                phi = (x / segments) * (2 * np.pi)
                vx = radius * np.sin(theta) * np.cos(phi)
                vy = radius * np.cos(theta)
                vz = radius * np.sin(theta) * np.sin(phi)
                verts.append([vx, vy, vz])
                uvs.append([x / segments, y / rings])
        for y in range(rings):
            for x in range(segments):
                i0 = y * (segments + 1) + x
                i1 = i0 + 1
                i2 = i0 + (segments + 1)
                i3 = i2 + 1
                idx.extend([i0, i2, i1, i1, i2, i3])
        verts = np.array(verts, dtype="f4")
        uvs = np.array(uvs, dtype="f4")
        idx = np.array(idx, dtype="i4")
        vbo = self._mgl_ctx.buffer(np.hstack([verts, uvs]).astype("f4").tobytes())
        ibo = self._mgl_ctx.buffer(idx.tobytes())
        self._mgl_prog_skysphere = self._mgl_ctx.program(
            vertex_shader="""
                #version 330
                uniform mat4 m_proj;
                uniform mat4 m_view;
                in vec3 in_vert;
                in vec2 in_uv;
                out vec2 v_uv;
                out float v_blend;
                void main() {
                    gl_Position = m_proj * m_view * vec4(in_vert, 1.0);
                    v_uv = in_uv;
                    v_blend = in_uv.y;
                }
            """,
            fragment_shader="""
                #version 330
                in vec2 v_uv;
                in float v_blend;
                out vec4 f_color;
                uniform sampler2D u_tex;
                void main() {
                    vec4 sky = texture(u_tex, v_uv);
                    vec4 ground = vec4(1.0, 1.0, 1.0, 1.0);
                    float blend = smoothstep(0.0, 0.5, v_blend);
                    blend = clamp(blend, 0.05, 1.0);
                    f_color = mix(ground, sky, blend);
                }
            """,
        )
        self._mgl_vao_skysphere = self._mgl_ctx.vertex_array(
            self._mgl_prog_skysphere, [(vbo, "3f 2f", "in_vert", "in_uv")], ibo
        )

    def _init_ground(self):
        ground_size = 1000.0
        tile_repeat = 1000.0
        ground_verts = np.array(
            [
                -ground_size,
                0,
                -ground_size,
                0.4,
                0.7,
                0.4,
                0.0,
                0.0,
                ground_size,
                0,
                -ground_size,
                0.4,
                0.7,
                0.4,
                tile_repeat,
                0.0,
                ground_size,
                0,
                ground_size,
                0.4,
                0.7,
                0.4,
                tile_repeat,
                tile_repeat,
                -ground_size,
                0,
                ground_size,
                0.4,
                0.7,
                0.4,
                0.0,
                tile_repeat,
            ],
            dtype="f4",
        )
        ground_idx = np.array([0, 1, 2, 2, 3, 0], dtype="i4")
        self._mgl_prog_ground = self._mgl_ctx.program(
            vertex_shader="""
                #version 330
                uniform mat4 m_proj;
                uniform mat4 m_view;
                uniform mat4 m_model;
                in vec3 in_vert;
                in vec3 in_color;
                in vec2 in_uv;
                out vec3 v_color;
                out vec2 v_uv;
                void main() {
                    gl_Position = m_proj * m_view * m_model * vec4(in_vert, 1.0);
                    v_color = in_color;
                    v_uv = in_uv;
                }
            """,
            fragment_shader="""
                #version 330
                in vec3 v_color;
                in vec2 v_uv;
                out vec4 f_color;
                uniform sampler2D u_tex;
                void main() {
                    vec4 tex_color = texture(u_tex, v_uv);
                    f_color = tex_color;
                }
            """,
        )
        self._mgl_vbo_ground = self._mgl_ctx.buffer(ground_verts.tobytes())
        self._mgl_ibo_ground = self._mgl_ctx.buffer(ground_idx.tobytes())
        self._mgl_vao_ground = self._mgl_ctx.vertex_array(
            self._mgl_prog_ground,
            [(self._mgl_vbo_ground, "3f 3f 2f", "in_vert", "in_color", "in_uv")],
            self._mgl_ibo_ground,
        )

    def _init_cube(self):
        cube_verts = np.array(
            [
                -0.5,
                0,
                0.5,
                0.8,
                0.3,
                0.3,
                0.5,
                0,
                0.5,
                0.8,
                0.3,
                0.3,
                0.5,
                1,
                0.5,
                0.8,
                0.3,
                0.3,
                -0.5,
                1,
                0.5,
                0.8,
                0.3,
                0.3,
                -0.5,
                0,
                -0.5,
                0.8,
                0.3,
                0.3,
                0.5,
                0,
                -0.5,
                0.8,
                0.3,
                0.3,
                0.5,
                1,
                -0.5,
                0.8,
                0.3,
                0.3,
                -0.5,
                1,
                -0.5,
                0.8,
                0.3,
                0.3,
            ],
            dtype="f4",
        )
        cube_idx = np.array(
            [
                0,
                1,
                2,
                2,
                3,
                0,
                1,
                5,
                6,
                6,
                2,
                1,
                5,
                4,
                7,
                7,
                6,
                5,
                4,
                0,
                3,
                3,
                7,
                4,
                3,
                2,
                6,
                6,
                7,
                3,
                4,
                5,
                1,
                1,
                0,
                4,
            ],
            dtype="i4",
        )
        self._mgl_vbo_cube = self._mgl_ctx.buffer(cube_verts.tobytes())
        self._mgl_ibo_cube = self._mgl_ctx.buffer(cube_idx.tobytes())
        self._mgl_vao_cube = self._mgl_ctx.vertex_array(
            self._mgl_prog_ground,
            [(self._mgl_vbo_cube, "3f 3f", "in_vert", "in_color")],
            self._mgl_ibo_cube,
        )

    def _init_robot(self):
        # Load OBJ model
        obj_path = os.path.abspath(
            os.path.join(os.path.dirname(__file__), "../../robot.obj")
        )
        mtl_path = os.path.abspath(
            os.path.join(os.path.dirname(__file__), "../../robot.mtl")
        )
        try:
            self.robot_scene = pywavefront.Wavefront(
                obj_path, create_materials=True, collect_faces=True
            )
        except Exception as e:
            print(f"[Dummy3D] Could not load robot model: {e}")
            self.robot_scene = None

    def _load_textures(self):
        floor_path = os.path.join(os.path.dirname(__file__), "../../floor.png")
        floor_path = os.path.abspath(floor_path)
        try:
            img = Image.open(floor_path).convert("RGB")
            img = img.resize((512, 512))
            self._mgl_tex_floor = self._mgl_ctx.texture(img.size, 3, img.tobytes())
            self._mgl_tex_floor.build_mipmaps()
            self._mgl_tex_floor.use(location=0)
        except Exception as e:
            print(f"[Dummy3D] Could not load floor texture: {e}")
            self._mgl_tex_floor = None

        sky_path = os.path.join(os.path.dirname(__file__), "../../sky.png")
        sky_path = os.path.abspath(sky_path)
        try:
            img = Image.open(sky_path).convert("RGB")
            img = img.resize((512, 512))
            self._mgl_tex_sky = self._mgl_ctx.texture(img.size, 3, img.tobytes())
            self._mgl_tex_sky.build_mipmaps()
        except Exception as e:
            print(f"[Dummy3D] Could not load sky texture: {e}")
            self._mgl_tex_sky = None

    def render(self, position, angle):
        # Defensive: ensure width/height are set
        if not hasattr(self, "width") or not hasattr(self, "height"):
            self.width = 640
            self.height = 480
        # Defensive: ensure _mgl_fbo is initialized
        if not hasattr(self, "_mgl_fbo"):
            print("[Dummy3DRenderer] Forcing _init_mgl due to missing _mgl_fbo")
            self._init_mgl()
        width, height = self.width, self.height
        self._mgl_fbo.use()
        self._mgl_fbo.clear(1.0, 1.0, 1.0, 1.0)

        def perspective(fovy, aspect, near, far):
            f = 1.0 / math.tan(fovy / 2)
            return np.array(
                [
                    [f / aspect, 0, 0, 0],
                    [0, f, 0, 0],
                    [
                        0,
                        0,
                        (far + near) / (near - far),
                        (2 * far * near) / (near - far),
                    ],
                    [0, 0, -1, 0],
                ],
                dtype="f4",
            )

        def lookat(eye, target, up):
            f = np.array(target) - np.array(eye)
            f = f / np.linalg.norm(f)
            u = np.array(up)
            s = np.cross(f, u)
            s = s / np.linalg.norm(s)
            u = np.cross(s, f)
            m = np.identity(4, dtype="f4")
            m[0, :3] = s
            m[1, :3] = u
            m[2, :3] = -f
            t = np.identity(4, dtype="f4")
            t[:3, 3] = -np.array(eye)
            return m @ t

        proj = perspective(math.radians(60), width / height, 0.1, 2000)
        rx, ry, rz = position
        cam_distance = 5.0
        cam_height = 2.5
        rad = math.radians(angle)
        cam_x = rx - cam_distance * math.sin(rad)
        cam_y = ry + cam_height
        cam_z = rz - cam_distance * math.cos(rad)
        view = lookat([cam_x, cam_y, cam_z], [rx, ry + 0.5, rz], [0, 1, 0])

        # Sky sphere (background)
        if hasattr(self, "_mgl_tex_sky") and self._mgl_tex_sky:
            self._mgl_ctx.disable(moderngl.DEPTH_TEST)
            self._mgl_tex_sky.use(location=0)
            view_rot = view.copy()
            view_rot[0:3, 3] = 0.0
            self._mgl_prog_skysphere["m_proj"].write(proj.T.tobytes())
            self._mgl_prog_skysphere["m_view"].write(view_rot.T.tobytes())
            self._mgl_prog_skysphere["u_tex"].value = 0
            self._mgl_vao_skysphere.render()
            self._mgl_ctx.enable(moderngl.DEPTH_TEST)

        # Ground
        if hasattr(self, "_mgl_tex_floor") and self._mgl_tex_floor:
            self._mgl_tex_floor.use(location=0)
            self._mgl_prog_ground["u_tex"].value = 0
        self._mgl_prog_ground["m_proj"].write(proj.T.tobytes())
        self._mgl_prog_ground["m_view"].write(view.T.tobytes())
        self._mgl_prog_ground["m_model"].write(np.eye(4, dtype="f4").tobytes())
        self._mgl_vao_ground.render()

        # Boxes
        def box_model(x, y, z, angle=0):
            m = np.eye(4, dtype="f4")
            m[:3, 3] = [x, y, z]
            if angle != 0:
                c, s = math.cos(math.radians(angle)), math.sin(math.radians(angle))
                rot = np.array(
                    [[c, 0, s, 0], [0, 1, 0, 0], [-s, 0, c, 0], [0, 0, 0, 1]],
                    dtype="f4",
                )
                m = m @ rot
            return m

        # Four person planes, always facing the camera
        if hasattr(self, "_mgl_tex_person") and self._mgl_tex_person:
            self._mgl_tex_person.use(location=0)
            self._mgl_prog_person["u_tex"].value = 0
            self._mgl_prog_person["m_proj"].write(proj.T.tobytes())
            self._mgl_prog_person["m_view"].write(view.T.tobytes())
            # Calculate billboard rotation to face camera
            for px, pz in [(15, 15), (-15, -15), (15, -15), (-15, 15)]:
                # Billboard: rotate plane to face camera
                dx = cam_x - px
                dz = cam_z - pz
                billboard_angle = math.degrees(math.atan2(dx, dz))
                # Remove 180 degree adjustment to fix upside-down display
                m = np.eye(4, dtype="f4")
                m[:3, 3] = [px, 0, pz]
                c, s = math.cos(math.radians(billboard_angle)), math.sin(
                    math.radians(billboard_angle)
                )
                rot = np.array(
                    [[c, 0, s, 0], [0, 1, 0, 0], [-s, 0, c, 0], [0, 0, 0, 1]],
                    dtype="f4",
                )
                m = m @ rot
                self._mgl_prog_person["m_model"].write(m.T.tobytes())
                self._mgl_vao_person.render()
        # Robot as 3D model
        if hasattr(self, "robot_scene") and self.robot_scene:
            # Render robot mesh as solid gray, no texture, no UVs
            if not hasattr(self, "_mgl_prog_robot_solid"):
                self._mgl_prog_robot_solid = self._mgl_ctx.program(
                    vertex_shader="""
                        #version 330
                        uniform mat4 m_proj;
                        uniform mat4 m_view;
                        uniform mat4 m_model;
                        in vec3 in_vert;
                        void main() {
                            gl_Position = m_proj * m_view * m_model * vec4(in_vert, 1.0);
                        }
                    """,
                    fragment_shader="""
                        #version 330
                        out vec4 f_color;
                        void main() {
                            f_color = vec4(0.5, 0.5, 0.5, 1.0); // solid gray
                        }
                    """,
                )
            vertices = np.array(self.robot_scene.vertices, dtype="f4")
            for name, mesh in self.robot_scene.meshes.items():
                indices = np.array([i for face in mesh.faces for i in face], dtype="i4")
                # Use only the first 3 columns (x, y, z)
                if vertices.shape[1] >= 3:
                    vbo = self._mgl_ctx.buffer(vertices[:, :3].astype("f4").tobytes())
                    ibo = self._mgl_ctx.buffer(indices.tobytes())
                    vao = self._mgl_ctx.vertex_array(
                        self._mgl_prog_robot_solid, [(vbo, "3f", "in_vert")], ibo
                    )
                    # Scale and center transform
                    scale = 0.05
                    rot180 = np.array(
                        [[1, 0, 0, 0], [0, 1, 0, 0], [0, 0, 1, 0], [0, 0, 0, 1]],
                        dtype="f4",
                    )
                    model_matrix = box_model(rx, 0.2, rz, angle) @ rot180
                    model_matrix[:3, :3] *= scale
                    self._mgl_prog_robot_solid["m_proj"].write(proj.T.tobytes())
                    self._mgl_prog_robot_solid["m_view"].write(view.T.tobytes())
                    self._mgl_prog_robot_solid["m_model"].write(
                        model_matrix.T.tobytes()
                    )
                    vao.render()
                else:
                    print(f"[Dummy3D] Unsupported vertex format: {vertices.shape[1]}")
                    continue
        else:
            # Fallback: blue box
            self._mgl_prog_ground["m_model"].write(
                box_model(rx, 0, rz, angle).T.tobytes()
            )
            self._mgl_vao_robot.render()

        # Read framebuffer
        data = self._mgl_fbo.read(components=3, alignment=1)
        img = np.frombuffer(data, dtype=np.uint8).reshape((height, width, 3))
        img = np.flipud(img)
        return img

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
        self._vel_yaw = z * 360.0  # degrees per second
        # Compute new target angle based on input
        self.target_angle = (self.target_angle + self._vel_yaw * 0.016) % 360


class Robot_Dummy(Robot):
    @classmethod
    def image(cls) -> str | None:
        return os.path.join(os.path.dirname(__file__), "robot_dummy.png")

    def property_requirement(self, name):
        if name == "name":
            return True
        return None

    @classmethod
    def properties(cls) -> dict:
        return {"name": "str"}

    @property
    def battery_status(self) -> int:
        return 100

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.name = kwargs.pop("name", None)
        self.position = [0.0, 0.0, 0.0]
        self.angle = 0.0
        self.target_angle = 0.0
        self.running = False
        self._vel_forward = 0.0
        self._vel_strafe = 0.0
        self._vel_yaw = 0.0
        self._timer = None
        self._renderer = Dummy3DRenderer()
        self._last_frame_time = 0
        self._last_frame = None
        self._is_connecting = False

    @property
    def is_connecting(self) -> bool:
        return getattr(self, "_is_connecting", False)

    @is_connecting.setter
    def is_connecting(self, value: bool):
        if getattr(self, "_is_connecting", False) != value:
            self._is_connecting = value
            self.notify_status_observers()

    @property
    def is_connected(self) -> bool:
        return self.running

    def connect(self):
        if self.running or self.is_connecting:
            return
        self.is_connecting = True
        import threading

        def do_connect():
            import time

            # Simulate connection delay
            time.sleep(0.5)
            self.running = True
            self.is_connecting = False
            self.notify_status_observers()

            def update_loop():
                last = time.time()
                while self.running:
                    now = time.time()
                    dt = min(now - last, 0.05)
                    last = now
                    self._update_position(dt)
                    time.sleep(0.016)

            self._timer = threading.Thread(target=update_loop, daemon=True)
            self._timer.start()

        threading.Thread(target=do_connect, daemon=True).start()

    def disconnect(self):
        print("[DEBUG] Robot_Dummy.disconnect called")
        self.running = False
        self.is_connecting = False
        self.notify_status_observers()
        self._vel_forward = 0.0
        self._vel_strafe = 0.0
        self._vel_yaw = 0.0

    def move(self, x: float = 0.0, y: float = 0.0, z: float = 0.0):
        if not self.running:
            return
        self._vel_forward = x * 5.0
        self._vel_strafe = y * 5.0
        self._vel_yaw = z * 360.0
        self.target_angle = (self.target_angle + self._vel_yaw * 0.016) % 360

    def _update_position(self, dt):
        angle_diff = (self.target_angle - self.angle + 540) % 360 - 180
        smoothing = min(1.0, dt * 10.0)
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
        if not self.running:
            return None
        import time

        min_interval = 1.0 / 30.0
        now = time.time()
        # Defensive: reinitialize renderer if _mgl_fbo is missing
        if not hasattr(self._renderer, "_mgl_fbo"):
            print("[Dummy3D] Reinitializing Dummy3DRenderer due to missing _mgl_fbo")
            self._renderer = Dummy3DRenderer()
        if (now - self._last_frame_time) >= min_interval or self._last_frame is None:
            try:
                img = self._renderer.render(self.position, self.angle)
                self._last_frame = img
                self._last_frame_time = now
            except Exception as e:
                print(f"[Dummy3D] moderngl render error: {e}")
                img = np.ones((480, 640, 3), dtype=np.uint8) * 255
                self._last_frame = img
                self._last_frame_time = now
        return self._last_frame
