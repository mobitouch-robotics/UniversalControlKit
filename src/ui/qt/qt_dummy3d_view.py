from PyQt5.QtWidgets import QOpenGLWidget
from PyQt5.QtCore import Qt, QTimer
from PyQt5.QtGui import QMatrix4x4, QVector3D
from OpenGL.GL import *
from OpenGL.GLU import gluPerspective, gluLookAt
from PIL import Image
import math

class QtDummy3DView(QOpenGLWidget):
    def cleanup(self):
        # No resources to clean up, but method is needed for compatibility
        pass
    def __init__(self, robot, parent=None):
        super().__init__(parent)
        self.robot = robot
        self.setMinimumSize(640, 480)
        self.setFocusPolicy(Qt.StrongFocus)
        self._timer = QTimer(self)
        self._timer.timeout.connect(self.update)
        self._timer.start(30)
        self._boxes = [
            (2, 0, 2),
            (-2, 0, -2),
            (2, 0, -2),
            (-2, 0, 2),
        ]
        self._grass_texture_id = None

    def initializeGL(self):
        glClearColor(0.7, 0.8, 1.0, 1.0)
        glEnable(GL_DEPTH_TEST)
        glEnable(GL_TEXTURE_2D)
        self._grass_texture_id = self._load_grass_texture()
    def _load_grass_texture(self):
        try:
            img = Image.open("grass_texture.png")
            img = img.transpose(Image.FLIP_TOP_BOTTOM)
            img_data = img.convert("RGB").tobytes()
            width, height = img.size
            tex_id = glGenTextures(1)
            glBindTexture(GL_TEXTURE_2D, tex_id)
            glTexImage2D(GL_TEXTURE_2D, 0, GL_RGB, width, height, 0, GL_RGB, GL_UNSIGNED_BYTE, img_data)
            glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_MIN_FILTER, GL_LINEAR)
            glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_MAG_FILTER, GL_LINEAR)
            return tex_id
        except Exception as e:
            print(f"[ERROR] Could not load grass texture: {e}")
            return None

    def resizeGL(self, w, h):
        glViewport(0, 0, w, h)
        glMatrixMode(GL_PROJECTION)
        glLoadIdentity()
        aspect = w / h if h != 0 else 1
        gluPerspective(60, aspect, 0.1, 100)
        glMatrixMode(GL_MODELVIEW)

    def paintGL(self):
        glClear(GL_COLOR_BUFFER_BIT | GL_DEPTH_BUFFER_BIT)
        glLoadIdentity()
        # Camera follows behind the robot (third-person/FPS style)
        rx, ry, rz = self.robot.position if hasattr(self.robot, 'position') else (0, 0, 0)
        angle = getattr(self.robot, 'angle', 0)
        cam_distance = 5.0
        cam_height = 2.5
        rad = math.radians(angle)
        # Camera is behind the robot, looking at it
        cam_x = rx - cam_distance * math.sin(rad)
        cam_y = ry + cam_height
        cam_z = rz - cam_distance * math.cos(rad)
        gluLookAt(cam_x, cam_y, cam_z, rx, ry + 0.5, rz, 0, 1, 0)
        # Ground with grass texture
        if self._grass_texture_id:
            glEnable(GL_TEXTURE_2D)
            glBindTexture(GL_TEXTURE_2D, self._grass_texture_id)
            glColor3f(1, 1, 1)
            glBegin(GL_QUADS)
            glTexCoord2f(0, 0)
            glVertex3f(-10, 0, -10)
            glTexCoord2f(1, 0)
            glVertex3f(10, 0, -10)
            glTexCoord2f(1, 1)
            glVertex3f(10, 0, 10)
            glTexCoord2f(0, 1)
            glVertex3f(-10, 0, 10)
            glEnd()
            glDisable(GL_TEXTURE_2D)
        else:
            glColor3f(0.4, 0.7, 0.4)
            glBegin(GL_QUADS)
            glVertex3f(-10, 0, -10)
            glVertex3f(10, 0, -10)
            glVertex3f(10, 0, 10)
            glVertex3f(-10, 0, 10)
            glEnd()
        # Boxes
        for bx, by, bz in self._boxes:
            self._draw_box(bx, 0.5, bz, 1, 1, 1, (0.8, 0.3, 0.3))
        # Robot as a simple box
        self._draw_box(rx, 0.5, rz, 1, 1, 1, (0.2, 0.2, 0.8), angle)

    def _draw_box(self, x, y, z, sx, sy, sz, color, angle=0):
        glPushMatrix()
        glTranslatef(x, y, z)
        if angle != 0:
            glRotatef(angle, 0, 1, 0)
        glScalef(sx, sy, sz)
        glColor3f(*color)
        # Draw cube
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
        glPopMatrix()
